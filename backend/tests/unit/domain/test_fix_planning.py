from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile
from app.domain.enums import FindingCategory, Severity
from app.domain.services.fix_planning import plan_fixes

FILES = [
    ChangedFile("a.py", "modified", 1, 0, "x"),
    ChangedFile("b.py", "modified", 1, 0, "x"),
    ChangedFile("gone.py", "removed", 0, 1, "x"),
    ChangedFile("README.md", "modified", 1, 0, "x"),
]


def finding(
    severity: Severity,
    path: str | None = "a.py",
    category: FindingCategory = FindingCategory.BUG,
    title: str = "t",
) -> Finding:
    return Finding(category, severity, title, "d", "reviewer", path, 1)


def test_only_serious_findings_are_selected() -> None:
    low, medium = finding(Severity.LOW), finding(Severity.MEDIUM)
    plan = plan_fixes([low, medium], FILES)
    assert plan.actions[0].finding_ids == (medium.id,)


def test_style_findings_are_skipped() -> None:
    assert plan_fixes([finding(Severity.HIGH, category=FindingCategory.STYLE)], FILES).is_empty


def test_only_changed_editable_files_are_planned() -> None:
    findings = [finding(Severity.HIGH, p) for p in ("other.py", "gone.py", "README.md", None)]
    assert plan_fixes(findings, FILES).is_empty


def test_files_are_capped_and_ordered_by_worst_severity() -> None:
    findings = [finding(Severity.MEDIUM, "a.py"), finding(Severity.CRITICAL, "b.py")]
    plan = plan_fixes(findings, FILES, max_files=1)
    assert [a.file_path for a in plan.actions] == ["b.py"]


def test_min_severity_is_configurable() -> None:
    assert plan_fixes([finding(Severity.MEDIUM)], FILES, min_severity=Severity.HIGH).is_empty
