import ast
from dataclasses import dataclass
from pathlib import PurePosixPath

EDITABLE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")
FORBIDDEN_DIRS = (".git/", ".github/", "node_modules/", ".venv/", "venv/")
FORBIDDEN_NAMES = frozenset({"setup.py"})


class EditRejectedError(ValueError):
    """An edit that cannot be applied safely."""


@dataclass(frozen=True)
class TextEdit:
    old_text: str
    new_text: str


def is_editable_path(path: str) -> bool:
    """The fixer may only touch source files: no CI, manifests, configs or hidden dirs."""
    posix = path.replace("\\", "/")
    parts = PurePosixPath(posix).parts

    if not posix or posix.startswith("/") or ":" in posix or ".." in parts:
        return False

    lowered = posix.lower()

    if not lowered.endswith(EDITABLE_SUFFIXES):
        return False

    if any(f"/{d}" in f"/{lowered}" for d in FORBIDDEN_DIRS):
        return False

    return parts[-1].lower() not in FORBIDDEN_NAMES


def apply_text_edit(content: str, old: str, new: str) -> str:
    """Replace the one exact occurrence of `old`. Line endings of the file are preserved."""
    if not old.strip():
        raise EditRejectedError("old_text is empty")

    crlf = "\r\n" in content
    text = content.replace("\r\n", "\n")
    old_n = old.replace("\r\n", "\n")
    new_n = new.replace("\r\n", "\n")

    count = text.count(old_n)

    if count == 0:
        raise EditRejectedError("old_text was not found in the file (it must match exactly)")

    if count > 1:
        raise EditRejectedError(f"old_text matches {count} places; include more surrounding lines")

    if old_n == new_n:
        raise EditRejectedError("the edit does not change anything")

    result = text.replace(old_n, new_n, 1)

    return result.replace("\n", "\r\n") if crlf else result


def python_syntax_error(path: str, content: str) -> str | None:
    if not path.lower().endswith(".py"):
        return None

    try:
        ast.parse(content)
    except SyntaxError as exc:
        return f"syntax error at line {exc.lineno}: {exc.msg}"
    except (ValueError, RecursionError):
        return "the file could not be parsed"

    return None
