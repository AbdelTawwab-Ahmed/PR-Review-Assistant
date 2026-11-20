"""Azure Container Apps Dynamic Sessions sandbox.

Implements ``SandboxPort`` by executing commands inside Azure-managed
code-interpreter sessions.  Each call gets its own session identifier
so that concurrent runs never share state.

When the service is unavailable or not configured the caller should
fall back to ``DockerSandbox`` — the container wiring in ``container.py``
handles that decision.
"""

import asyncio
import base64
import io
import logging
import tarfile
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.application.ports.sandbox_port import (
    ExecResult,
    SandboxError,
    Workspace,
)

logger = logging.getLogger(__name__)

# Azure sessions execute Python; we wrap shell commands via subprocess.
_EXEC_TEMPLATE = """\
import subprocess, sys, os
os.chdir({workdir!r})
for k, v in {env!r}.items():
    os.environ[k] = v
proc = subprocess.run(
    {command!r},
    capture_output=True,
    timeout={timeout},
)
sys.stdout.buffer.write(proc.stdout)
sys.stderr.buffer.write(proc.stderr)
sys.exit(proc.returncode)
"""

_UPLOAD_TEMPLATE = """\
import base64, tarfile, io, os, sys
data = base64.b64decode({b64!r})
os.makedirs({dest!r}, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
    tar.extractall({dest!r}, filter="data")
print("uploaded", flush=True)
"""

OUTPUT_LIMIT = 5_000_000


@dataclass(frozen=True)
class DynamicSessionsConfig:
    """Configuration for the Azure Dynamic Sessions endpoint."""

    pool_endpoint: str = ""
    max_session_seconds: int = 300
    max_concurrency: int = 2
    upload_chunk_bytes: int = 4_000_000
    output_limit_bytes: int = OUTPUT_LIMIT

    # Auth: managed identity or API key.
    # When running on Azure Container Apps with a managed identity,
    # leave api_key empty and the SDK picks up the identity.
    api_key: str = ""

    # Extra headers forwarded to the pool endpoint (e.g. for
    # preview API versions).
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        return bool(self.pool_endpoint)


def _tar_directory(directory: Path) -> bytes:
    """Create an in-memory tar.gz of *directory*."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(directory), arcname=".")
    return buf.getvalue()


class DynamicSessionsSandbox:
    """Run commands in Azure Container Apps Dynamic Sessions.

    Each ``run()`` call creates a fresh session so that parallel
    executions are fully isolated.  Source and dependency directories
    from the ``Workspace`` are uploaded as compressed tarballs and
    extracted inside the session.
    """

    def __init__(
        self,
        config: DynamicSessionsConfig,
    ) -> None:
        if not config.is_configured:
            raise SandboxError("Dynamic Sessions pool endpoint is not configured")
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                config.max_session_seconds + 30,
                connect=15,
            ),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}),
                **config.extra_headers,
            },
        )

    # -- public interface (SandboxPort) ------------------------------------

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
        timeout = timeout_seconds or self._config.max_session_seconds
        session_id = uuid.uuid4().hex[:16]

        async with self._semaphore:
            started = time.monotonic()
            try:
                await self._upload_workspace(session_id, workspace)
                result = await self._execute(
                    session_id,
                    list(command),
                    workdir=workdir,
                    env=dict(env or {}),
                    timeout=timeout,
                )
            except httpx.TimeoutException:
                return ExecResult(
                    exit_code=-1,
                    stdout="",
                    stderr="session timed out",
                    timed_out=True,
                    duration_seconds=round(time.monotonic() - started, 2),
                )
            except httpx.HTTPStatusError as exc:
                raise SandboxError(
                    f"Dynamic Sessions API error: {exc.response.status_code}"
                ) from exc
            except httpx.HTTPError as exc:
                raise SandboxError(f"Dynamic Sessions connection error: {exc}") from exc

            duration = round(time.monotonic() - started, 2)

        return ExecResult(
            exit_code=result["exit_code"],
            stdout=result["stdout"][:OUTPUT_LIMIT],
            stderr=result["stderr"][:OUTPUT_LIMIT],
            timed_out=False,
            truncated=(
                len(result["stdout"]) > OUTPUT_LIMIT or len(result["stderr"]) > OUTPUT_LIMIT
            ),
            duration_seconds=duration,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- internals ---------------------------------------------------------

    def _url(self, path: str, session_id: str) -> str:
        base = self._config.pool_endpoint.rstrip("/")
        return f"{base}{path}?identifier={session_id}&api-version=2024-10-02-preview"

    async def _upload_workspace(
        self,
        session_id: str,
        workspace: Workspace,
    ) -> None:
        """Upload source and deps directories into the session."""
        for label, directory, dest in [
            ("source", workspace.source, "/mnt/user/source"),
            ("deps", workspace.deps, "/mnt/user/deps"),
        ]:
            if not directory.exists():
                continue
            tar_bytes = await asyncio.to_thread(_tar_directory, directory)
            b64 = base64.b64encode(tar_bytes).decode()
            code = _UPLOAD_TEMPLATE.format(b64=b64, dest=dest)
            resp = await self._client.post(
                self._url("/code/execute", session_id),
                json={
                    "properties": {
                        "codeInputType": "inline",
                        "executionType": "synchronous",
                        "code": code,
                    },
                },
            )
            resp.raise_for_status()
            logger.debug(
                "uploaded %s to session %s (%d bytes)",
                label,
                session_id,
                len(tar_bytes),
            )

    async def _execute(
        self,
        session_id: str,
        command: list[str],
        *,
        workdir: str,
        env: dict[str, str],
        timeout: int,
    ) -> dict[str, object]:
        """Execute a shell command inside the session."""
        full_workdir = f"/mnt/user/source/{workdir}".rstrip("/")
        code = _EXEC_TEMPLATE.format(
            workdir=full_workdir,
            env=env,
            command=command,
            timeout=timeout,
        )

        resp = await self._client.post(
            self._url("/code/execute", session_id),
            json={
                "properties": {
                    "codeInputType": "inline",
                    "executionType": "synchronous",
                    "code": code,
                    "timeoutInSeconds": timeout,
                },
            },
        )
        resp.raise_for_status()
        body = resp.json()
        props = body.get("properties", {})

        stdout = props.get("stdout", "") or ""
        stderr = props.get("stderr", "") or ""
        exit_code = props.get("exitCode")

        # The API may not always surface exitCode directly;
        # treat execution errors as non-zero.
        if exit_code is None:
            exit_code = 0 if props.get("status") == "Succeeded" else 1

        return {
            "exit_code": int(exit_code),
            "stdout": str(stdout),
            "stderr": str(stderr),
        }
