import asyncio
import re
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from app.application.ports.github_port import GitHubPort
from app.application.ports.sandbox_port import SandboxError, Workspace
from app.infrastructure.sandbox.archive import extract_tar_gz

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


class WorkspaceFactory:
    """Downloads one commit into a temp folder and deletes it afterwards."""

    def __init__(
        self,
        github: GitHubPort,
        *,
        max_archive_mb: int = 200,
        max_files: int = 20000,
        base_dir: Path | None = None,
    ) -> None:
        self._github = github
        self._max_bytes = max_archive_mb * 1024 * 1024
        self._max_files = max_files
        self._base_dir = base_dir

    @asynccontextmanager
    async def open(self, repo_full_name: str, sha: str) -> AsyncIterator[Workspace]:
        if not _REPO.match(repo_full_name) or not _SHA.match(sha):
            raise SandboxError("invalid repository or commit reference")
        root = Path(tempfile.mkdtemp(prefix="prra-ws-", dir=self._base_dir))
        try:
            data = await self._github.download_archive(repo_full_name, sha, self._max_bytes)
            source, deps = root / "source", root / "deps"
            source.mkdir()
            deps.mkdir()
            deps.chmod(0o777)  # only ever mounted into sandbox containers
            await asyncio.to_thread(
                extract_tar_gz, data, source, max_bytes=self._max_bytes, max_files=self._max_files
            )
            yield Workspace(source=source, deps=deps)
        finally:
            await asyncio.to_thread(shutil.rmtree, root, True)
