import re
import tomllib
from pathlib import Path

PROJECT_MARKERS = (
    "pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini", "setup.py", "requirements.txt",
)  # fmt: skip
REQUIREMENT_FILES = (
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "dev-requirements.txt", "test-requirements.txt",
)  # fmt: skip
EXTRA_GROUPS = ("dev", "test", "tests")
MAX_FILE_BYTES = 1_000_000

_VERSION = r"[<>=!~]=?\s*[A-Za-z0-9.*+!_-]+"
_SPEC = re.compile(
    rf"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,\s-]+\])?\s*"
    rf"({_VERSION}(\s*,\s*{_VERSION})*)?\s*(;[^#]*)?$"
)


def clean_spec(line: str) -> str | None:
    """Accept only plain `name[extras] version ; marker` requirements.

    Options (-r, --index-url, -e), URLs and direct references are dropped, so a PR cannot
    point the install step at another package index or run a build script.
    """
    line = line.split(" #")[0].strip()
    if not line or line.startswith(("#", "-")) or "://" in line or "@" in line.split(";")[0]:
        return None
    return line if _SPEC.match(line) else None


def detect_python_project(source: Path) -> str:
    """Folder (relative to the repo root) holding the Python project."""
    if any((source / marker).is_file() for marker in PROJECT_MARKERS):
        return "."
    children = sorted(p for p in source.iterdir() if p.is_dir() and not p.name.startswith("."))
    for child in children:
        if any((child / marker).is_file() for marker in PROJECT_MARKERS):
            return child.name
    return "."


def _read(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def collect_requirement_specs(project: Path, max_specs: int = 300) -> tuple[str, ...]:
    candidates: list[str] = []
    for name in REQUIREMENT_FILES:
        candidates.extend(_read(project / name).splitlines())
    try:
        data = tomllib.loads(_read(project / "pyproject.toml"))
    except tomllib.TOMLDecodeError:
        data = {}
    meta = data.get("project", {})
    candidates.extend(meta.get("dependencies", []))
    extras = meta.get("optional-dependencies", {})
    for group in EXTRA_GROUPS:
        candidates.extend(extras.get(group, []))

    specs = (clean_spec(c) for c in candidates if isinstance(c, str))
    return tuple(dict.fromkeys(s for s in specs if s))[:max_specs]
