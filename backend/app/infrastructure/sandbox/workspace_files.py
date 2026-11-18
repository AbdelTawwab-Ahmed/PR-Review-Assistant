from pathlib import Path

from app.application.ports.sandbox_port import SandboxError, Workspace

MAX_READ_BYTES = 2_000_000


class WorkspaceFiles:
    """Reads and edits files in the host-side workspace. Paths can never leave it.

    Bytes are read and written directly so the file's line endings survive untouched.
    """

    @staticmethod
    def _resolve(workspace: Workspace, path: str) -> Path:
        root = workspace.source.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise SandboxError("path escapes the workspace")
        return target

    def read(self, workspace: Workspace, path: str) -> str | None:
        target = self._resolve(workspace, path)
        if not target.is_file() or target.stat().st_size > MAX_READ_BYTES:
            return None
        try:
            return target.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            return None

    def write(self, workspace: Workspace, path: str, content: str) -> None:
        target = self._resolve(workspace, path)
        if not target.is_file():
            raise SandboxError("only existing files can be edited")
        target.write_bytes(content.encode("utf-8"))