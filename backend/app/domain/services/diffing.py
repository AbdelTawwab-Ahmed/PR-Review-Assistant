import difflib
from collections.abc import Sequence

from app.domain.entities.fix_proposal import FileChange


def unified_diff(path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def count_changed_lines(old: str, new: str) -> int:
    lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            lineterm="",
            n=0,
        )
    )[2:]

    return sum(1 for line in lines if line.startswith(("+", "-")))


def render_diff(changes: Sequence[FileChange]) -> str:
    return "\n".join(unified_diff(c.path, c.old_content, c.new_content) for c in changes)
