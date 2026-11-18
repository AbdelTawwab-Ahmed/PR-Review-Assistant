from typing import Protocol

from app.application.ports.sandbox_port import Workspace


class FileStore(Protocol):
    def read(self, workspace: Workspace, path: str) -> str | None: ...

    def write(self, workspace: Workspace, path: str, content: str) -> None: ...