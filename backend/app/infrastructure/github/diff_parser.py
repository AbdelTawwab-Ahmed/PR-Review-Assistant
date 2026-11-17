import re
from typing import Any

from app.domain.entities.pull_request import ChangedFile

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_files(raw_files: list[dict[str, Any]]) -> tuple[ChangedFile, ...]:
    return tuple(
        ChangedFile(
            path=f["filename"],
            status=f.get("status", "modified"),
            additions=int(f.get("additions", 0)),
            deletions=int(f.get("deletions", 0)),
            patch=f.get("patch"),
        )
        for f in raw_files
    )


def commentable_lines(patch: str | None) -> set[int]:
    """Line numbers (new side) that GitHub accepts for inline review comments."""
    lines: set[int] = set()
    if not patch:
        return lines
    current = 0
    in_hunk = False
    for raw in patch.splitlines():
        match = _HUNK.match(raw)
        if match:
            current = int(match.group(1))
            in_hunk = True
            continue
        if in_hunk and raw[:1] in ("+", " "):
            lines.add(current)
            current += 1
        # "-" lines and "\ No newline" markers do not exist on the new side
    return lines
