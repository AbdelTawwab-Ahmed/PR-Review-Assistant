from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile
from app.domain.enums import FindingCategory, Severity
from app.domain.services.diff_filter import filter_findings_to_diff

PATCH = "@@ -1,2 +1,3 @@\n import os\n+x = 1\n print(1)"  # new-side lines 1-3
FILES = (
    ChangedFile("a.py", "modified", 1, 0, PATCH),
    ChangedFile("big.py", "modified", 500, 0, None),
)


def finding(path: str, line: int | None, end: int | None = None) -> Finding:
    return Finding(FindingCategory.BUG, Severity.LOW, "t", "d", "ruff", path, line, end)


def test_keeps_findings_on_diff_lines() -> None:
    assert filter_findings_to_diff([finding("a.py", 2)], FILES)


def test_drops_findings_outside_the_diff() -> None:
    assert filter_findings_to_diff([finding("a.py", 50)], FILES) == []


def test_drops_findings_in_untouched_files() -> None:
    assert filter_findings_to_diff([finding("other.py", 1)], FILES) == []


def test_keeps_file_level_findings_in_changed_files() -> None:
    assert filter_findings_to_diff([finding("a.py", None)], FILES)


def test_files_without_a_patch_keep_everything() -> None:
    assert filter_findings_to_diff([finding("big.py", 300)], FILES)


def test_multi_line_finding_overlapping_the_diff_is_kept() -> None:
    assert filter_findings_to_diff([finding("a.py", 3, 10)], FILES)
