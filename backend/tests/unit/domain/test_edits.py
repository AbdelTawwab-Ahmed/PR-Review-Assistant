import pytest

from app.domain.services.edits import (
    EditRejectedError,
    apply_text_edit,
    is_editable_path,
    python_syntax_error,
)


def test_only_source_files_are_editable() -> None:
    assert is_editable_path("src/app.py")
    assert is_editable_path("web/App.tsx")
    for bad in [
        "README.md", ".github/workflows/ci.py", "../x.py", "/etc/x.py", "C:/x.py",
        "setup.py", "node_modules/a/b.js", "pyproject.toml", "app/.git/hooks/x.py",
    ]:  # fmt: skip
        assert not is_editable_path(bad), bad


def test_replaces_one_unique_snippet() -> None:
    assert apply_text_edit("a = 1\nb = 2\n", "b = 2\n", "b = 3\n") == "a = 1\nb = 3\n"


def test_missing_snippet_is_rejected() -> None:
    with pytest.raises(EditRejectedError, match="not found"):
        apply_text_edit("a = 1\n", "zzz", "y")


def test_ambiguous_snippet_is_rejected() -> None:
    with pytest.raises(EditRejectedError, match="2 places"):
        apply_text_edit("x = 1\nx = 1\n", "x = 1", "x = 2")


def test_empty_and_noop_edits_are_rejected() -> None:
    with pytest.raises(EditRejectedError):
        apply_text_edit("a\n", "  ", "b")
    with pytest.raises(EditRejectedError):
        apply_text_edit("a\n", "a", "a")


def test_crlf_files_keep_their_line_endings() -> None:
    content = "a = 1\r\nb = 2\r\n"
    assert apply_text_edit(content, "b = 2\n", "b = 3\n") == "a = 1\r\nb = 3\r\n"


def test_python_syntax_check() -> None:
    assert python_syntax_error("a.py", "x = 1\n") is None
    assert "syntax error" in python_syntax_error("a.py", "if (:\n")
    assert python_syntax_error("a.js", "if (:") is None
