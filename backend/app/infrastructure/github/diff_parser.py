from typing import Any

from app.domain.entities.pull_request import ChangedFile
from app.domain.services.diff_lines import commentable_lines

__all__ = ["commentable_lines", "parse_files"]


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