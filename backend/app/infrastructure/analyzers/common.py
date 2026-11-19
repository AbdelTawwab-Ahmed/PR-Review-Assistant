from collections.abc import Sequence
from pathlib import PurePosixPath

from app.application.ports.sandbox_port import ExecResult

WORKSPACE_ROOT = "/workspace"
TEST_SUFFIXES = ("_test.py", ".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx")


def container_paths(paths: Sequence[str], suffixes: tuple[str, ...]) -> list[str]:
    """Repo-relative paths -> absolute paths inside the sandbox, filtered by file type."""
    result: list[str] = []
    for path in paths:
        posix = path.replace("\\", "/").lstrip("/")
        if ".." in PurePosixPath(posix).parts or not posix.lower().endswith(suffixes):
            continue
        result.append(f"{WORKSPACE_ROOT}/{posix}")
    return result


def repo_path(filename: str) -> str:
    name = filename.replace("\\", "/")
    if name.startswith(f"{WORKSPACE_ROOT}/"):
        name = name[len(WORKSPACE_ROOT) + 1 :]
    return name.removeprefix("./")


def is_test_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    name = p.rsplit("/", 1)[-1]
    in_test_dir = "/tests/" in f"/{p}" or "/test/" in f"/{p}"
    return in_test_dir or name.startswith("test_") or name.endswith(TEST_SUFFIXES)


def describe_failure(result: ExecResult) -> str:
    if result.timed_out:
        return "timed out"
    if result.truncated:
        return "output too large"
    if result.exit_code == 137:
        return "killed, probably out of memory"
    detail = result.stderr.strip()[-300:]
    return f"exit code {result.exit_code}" + (f": {detail}" if detail else "")
