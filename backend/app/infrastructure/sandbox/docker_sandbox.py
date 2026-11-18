import asyncio
import contextlib
import logging
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.application.ports.sandbox_port import ExecResult, SandboxError, Workspace

logger = logging.getLogger(__name__)

# Runs inside the container: copy the read-only source into the scratch tmpfs, then exec.
# `$0` is the working directory, so the real command and its arguments arrive as "$@".
ENTRYPOINT = 'cp -R /src/. /workspace/ && cd "/workspace/$0" && exec "$@"'

TMP_DIR = "/tmp"  # noqa: S108  # nosec B108

BASE_ENV = {
    "HOME": TMP_DIR,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_NO_CACHE_DIR": "1",
    "SEMGREP_SEND_METRICS": "off",
    "SEMGREP_ENABLE_VERSION_CHECK": "0",
}
_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SandboxLimits:
    memory_mb: int = 2048
    cpus: float = 1.0
    pids: int = 512
    workspace_mb: int = 512
    tmp_mb: int = 256
    timeout_seconds: int = 120
    output_limit_bytes: int = 5_000_000


async def _drain(stream: asyncio.StreamReader | None, limit: int) -> tuple[bytes, bool]:
    """Read a stream to the end but keep at most `limit` bytes in memory."""
    buffer = bytearray()
    truncated = False
    if stream is None:
        return b"", False
    while chunk := await stream.read(65536):
        room = max(0, limit - len(buffer))
        buffer += chunk[:room]
        if len(chunk) > room:
            truncated = True
    return bytes(buffer), truncated


def _mount_source(path: Path) -> str:
    if "," in str(path):
        raise SandboxError("workspace path must not contain commas")
    return str(path)


class DockerSandbox:
    """Runs one command per throwaway container.


    No network, read-only root and source, scratch tmpfs, non-root user, no capabilities,
    CPU/memory/process limits, hard timeout. The only environment is what is listed here,
    so host secrets never reach the container. `install_mode` is the single exception:
    network on and the deps folder writable, used only to download wheels.
    """

    def __init__(
        self,
        *,
        image: str,
        limits: SandboxLimits | None = None,
        docker_bin: str = "docker",
        max_concurrency: int = 2,
    ) -> None:
        self._image = image
        self._limits = limits or SandboxLimits()
        self._docker = docker_bin
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def build_command(
        self,
        name: str,
        workspace: Workspace,
        command: Sequence[str],
        *,
        workdir: str = ".",
        env: Mapping[str, str] | None = None,
        install_mode: bool = False,
    ) -> list[str]:
        if ".." in PurePosixPath(workdir).parts or workdir.startswith("/"):
            raise SandboxError("invalid working directory")
        extra_env = dict(env or {})

        if not all(_ENV_KEY.match(key) for key in extra_env):
            raise SandboxError("invalid environment variable name")

        lim = self._limits
        deps_mount = f"type=bind,source={_mount_source(workspace.deps)},target=/deps"
        workspace_tmpfs = (
            f"/workspace:rw,exec,nosuid,nodev,size={lim.workspace_mb}m,uid=10001,gid=10001"
        )
        args = [
            self._docker, "run", "--rm", "--name", name,
            "--network", "bridge" if install_mode else "none",
            "--memory", f"{lim.memory_mb}m", "--memory-swap", f"{lim.memory_mb}m",
            "--cpus", str(lim.cpus), "--pids-limit", str(lim.pids),
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001",
            "--tmpfs", workspace_tmpfs,
            "--tmpfs", f"{TMP_DIR}:rw,noexec,nosuid,nodev,size={lim.tmp_mb}m,uid=10001,gid=10001",
            "--mount", f"type=bind,source={_mount_source(workspace.source)},target=/src,readonly",
            "--mount", deps_mount if install_mode else f"{deps_mount},readonly",
            "--workdir", "/workspace",
        ]  # fmt: skip
        for key, value in {**BASE_ENV, **extra_env}.items():
            args += ["--env", f"{key}={value}"]
        args += [self._image, "sh", "-c", ENTRYPOINT, workdir, *command]
        return args

    async def run(
        self,
        workspace: Workspace,
        command: Sequence[str],
        *,
        workdir: str = ".",
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
        install_mode: bool = False,
    ) -> ExecResult:
        timeout = timeout_seconds or self._limits.timeout_seconds
        name = f"prra-sbx-{uuid.uuid4().hex[:12]}"
        args = self.build_command(
            name, workspace, command, workdir=workdir, env=env, install_mode=install_mode
        )
        async with self._semaphore:
            started = time.monotonic()
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise SandboxError("Docker CLI not found: install Docker and start it") from exc

            reader = asyncio.ensure_future(self._collect(proc))
            timed_out = False
            try:
                done, _ = await asyncio.wait({reader}, timeout=timeout)
                if not done:
                    timed_out = True
                    await self._force_remove(name)
                out, err, truncated = await asyncio.wait_for(
                    reader, timeout=15 if timed_out else None
                )
            except TimeoutError:
                out, err, truncated = b"", b"", False
            finally:
                if proc.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        proc.kill()
                    await self._force_remove(name)

        code = proc.returncode if proc.returncode is not None else -1
        stderr = err.decode(errors="replace")
        if code == 125 and not timed_out:  # docker itself failed: daemon down, image missing
            raise SandboxError(f"docker could not start the sandbox: {stderr.strip()[-300:]}")
        return ExecResult(
            exit_code=code,
            stdout=out.decode(errors="replace"),
            stderr=stderr,
            timed_out=timed_out,
            truncated=truncated,
            duration_seconds=round(time.monotonic() - started, 2),
        )

    async def _collect(self, proc: asyncio.subprocess.Process) -> tuple[bytes, bytes, bool]:
        limit = self._limits.output_limit_bytes
        (out, out_cut), (err, err_cut), _ = await asyncio.gather(
            _drain(proc.stdout, limit), _drain(proc.stderr, limit), proc.wait()
        )
        return out, err, out_cut or err_cut

    async def _force_remove(self, name: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._docker, "rm", "-f", name,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            await asyncio.wait_for(proc.wait(), timeout=15)
        except (OSError, TimeoutError):
            logger.warning("could not remove sandbox container %s", name)
