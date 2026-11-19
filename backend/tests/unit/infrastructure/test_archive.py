import io
import tarfile
from pathlib import Path

import pytest

from app.application.ports.sandbox_port import SandboxError
from app.infrastructure.sandbox.archive import extract_tar_gz


def make_tar(entries: dict[str, bytes], symlinks: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buffer.getvalue()


def extract(data: bytes, dest: Path, **kwargs) -> int:
    return extract_tar_gz(
        data,
        dest,
        max_bytes=kwargs.get("max_bytes", 10_000),
        max_files=kwargs.get("max_files", 100),
    )


def test_strips_the_top_level_folder(tmp_path: Path) -> None:
    extract(make_tar({"owner-repo-abc/src/app.py": b"print(1)"}), tmp_path)
    assert (tmp_path / "src" / "app.py").read_bytes() == b"print(1)"


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(SandboxError):
        extract(make_tar({"top/../../evil.txt": b"x"}), dest)
    assert not (tmp_path / "evil.txt").exists()


def test_symlinks_are_skipped(tmp_path: Path) -> None:
    extract(make_tar({"top/a.txt": b"a"}, {"top/link": "/etc/passwd"}), tmp_path)
    assert (tmp_path / "a.txt").exists()
    assert not (tmp_path / "link").is_symlink()


def test_too_many_files_are_rejected(tmp_path: Path) -> None:
    data = make_tar({f"top/f{i}.txt": b"x" for i in range(3)})
    with pytest.raises(SandboxError):
        extract(data, tmp_path, max_files=2)


def test_oversized_archives_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        extract(make_tar({"top/big.bin": b"x" * 100}), tmp_path, max_bytes=50)


def test_garbage_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        extract(b"not a tar", tmp_path)
