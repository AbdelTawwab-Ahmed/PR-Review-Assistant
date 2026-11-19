from pathlib import Path

import pytest

from app.application.ports.sandbox_port import SandboxError, Workspace
from app.infrastructure.sandbox.workspace_files import WorkspaceFiles


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    (source / "binary.py").write_bytes(b"\xff\xfe\x00")
    return Workspace(source, tmp_path / "deps")


def test_read_and_write_keep_line_endings(workspace: Workspace) -> None:
    files = WorkspaceFiles()
    assert files.read(workspace, "a.py") == "x = 1\r\ny = 2\r\n"
    files.write(workspace, "a.py", "x = 1\r\ny = 3\r\n")
    assert (workspace.source / "a.py").read_bytes() == b"x = 1\r\ny = 3\r\n"


def test_missing_and_binary_files_read_as_none(workspace: Workspace) -> None:
    files = WorkspaceFiles()
    assert files.read(workspace, "missing.py") is None
    assert files.read(workspace, "binary.py") is None


def test_paths_cannot_escape_the_workspace(workspace: Workspace) -> None:
    files = WorkspaceFiles()
    with pytest.raises(SandboxError):
        files.read(workspace, "../outside.py")
    with pytest.raises(SandboxError):
        files.write(workspace, "../outside.py", "x")


def test_only_existing_files_can_be_written(workspace: Workspace) -> None:
    with pytest.raises(SandboxError):
        WorkspaceFiles().write(workspace, "new.py", "x")
