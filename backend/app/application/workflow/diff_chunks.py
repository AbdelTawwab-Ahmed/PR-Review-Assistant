import re
from dataclasses import dataclass

from app.domain.entities.pull_request import ChangedFile
from app.domain.services.diff_lines import annotate_patch

SKIP_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".woff", ".woff2", ".pdf", ".zip", ".snap",
)  # fmt: skip
SKIP_NAMES = frozenset({"package-lock.json", "pnpm-lock.yaml"})
SKIP_DIRS = ("node_modules/", "dist/", "build/", "vendor/", "__pycache__/", ".venv/")
TRUNCATION_NOTE = "\n[... diff truncated ...]"

# The PR author controls all of this text, so our own delimiter tags are defused.
_OWN_TAGS = re.compile(r"</(file|diff|pr_meta|file_list)\s*>", re.IGNORECASE)


def neutralize(text: str) -> str:
    return _OWN_TAGS.sub(r"<\\/\1>", text)


@dataclass(frozen=True)
class RenderedFile:
    path: str
    text: str


@dataclass(frozen=True)
class ChunkPlan:
    chunks: tuple[tuple[RenderedFile, ...], ...]
    skipped: tuple[str, ...]


def is_reviewable(file: ChangedFile) -> bool:
    if file.status == "removed" or not file.patch:
        return False
    path = file.path.replace("\\", "/").lower()
    name = path.rsplit("/", 1)[-1]
    if name in SKIP_NAMES or path.endswith(SKIP_SUFFIXES):
        return False
    return not any(f"/{d}" in f"/{path}" for d in SKIP_DIRS)


def render_file(file: ChangedFile, max_chars: int) -> RenderedFile:
    header = f'<file path="{neutralize(file.path).replace(chr(34), "&quot;")}" status="{file.status}">\n'
    footer = "\n</file>"
    body = neutralize(annotate_patch(file.patch))
    room = max_chars - len(header) - len(footer)
    if len(body) > room:
        body = body[: max(0, room - len(TRUNCATION_NOTE))] + TRUNCATION_NOTE
    return RenderedFile(file.path, header + body + footer)


def build_chunks(files: tuple[ChangedFile, ...], max_chars: int, max_chunks: int) -> ChunkPlan:
    chunks: list[tuple[RenderedFile, ...]] = []
    skipped: list[str] = []
    current: list[RenderedFile] = []
    size = 0
    for file in files:
        if not is_reviewable(file):
            continue
        rendered = render_file(file, max_chars)
        if current and size + len(rendered.text) > max_chars:
            chunks.append(tuple(current))
            current, size = [], 0
        if len(chunks) >= max_chunks:
            skipped.append(file.path)  # cost guard: very large PRs are analyzed partially
            continue
        current.append(rendered)
        size += len(rendered.text)
    if current:
        chunks.append(tuple(current))
    return ChunkPlan(tuple(chunks), tuple(skipped))