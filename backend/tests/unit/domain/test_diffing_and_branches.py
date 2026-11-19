from app.domain.entities.fix_proposal import FileChange
from app.domain.services.branches import fix_branch_name, is_bot_branch
from app.domain.services.diffing import count_changed_lines, render_diff, unified_diff


def test_unified_diff_marks_changed_lines() -> None:
    diff = unified_diff("a.py", "x = 1\ny = 2\n", "x = 1\ny = 3\n")
    assert "--- a/a.py" in diff
    assert "-y = 2" in diff
    assert "+y = 3" in diff


def test_count_changed_lines() -> None:
    assert count_changed_lines("a\nb\n", "a\nb\n") == 0
    assert count_changed_lines("a\nb\n", "a\nc\n") == 2  # one removed, one added


def test_render_diff_covers_every_file() -> None:
    changes = [FileChange("a.py", "1\n", "2\n"), FileChange("b.py", "x\n", "y\n")]
    rendered = render_diff(changes)
    assert "a/a.py" in rendered and "a/b.py" in rendered


def test_fix_branches_are_recognized_as_bot_branches() -> None:
    name = fix_branch_name(7, "abcdef1234567")
    assert name == "prra/fix-pr7-abcdef1"
    assert is_bot_branch(name)
    assert not is_bot_branch("feature/login")
