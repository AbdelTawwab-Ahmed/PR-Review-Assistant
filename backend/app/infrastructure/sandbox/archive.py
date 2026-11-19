import io
import tarfile
from pathlib import Path, PurePosixPath

from app.application.ports.sandbox_port import SandboxError


def extract_tar_gz(data: bytes, dest: Path, *, max_bytes: int, max_files: int) -> int:
    """Extract a GitHub tarball into `dest`, dropping its top-level folder.

    The archive comes from an untrusted repository: links and special files are skipped,
    and total size and file count are capped before anything is written.
    """
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            members: list[tarfile.TarInfo] = []
            total = 0
            for member in tar.getmembers():
                parts = PurePosixPath(member.name).parts[1:]
                if not parts or not (member.isfile() or member.isdir()):
                    continue
                total += member.size
                if total > max_bytes or len(members) >= max_files:
                    raise SandboxError("repository is too large to analyze")
                member.name = "/".join(parts)
                members.append(member)
            # The "data" filter blocks absolute paths, path traversal and unsafe permissions.
            tar.extractall(dest, members=members, filter="data")  # noqa: S202
    except SandboxError:
        raise
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise SandboxError("could not extract the repository archive") from exc
    return len(members)
