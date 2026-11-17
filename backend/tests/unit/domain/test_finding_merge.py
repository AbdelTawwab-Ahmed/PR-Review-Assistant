from app.domain.entities.finding import Finding
from app.domain.enums import FindingCategory, Severity
from app.domain.services.finding_merge import merge_findings


def fnd(
    severity: Severity,
    title: str = "Null deref",
    path: str = "a.py",
    line: int = 3,
    source: str = "reviewer",
) -> Finding:
    return Finding(FindingCategory.BUG, severity, title, "d", source, path, line)


def test_duplicates_keep_highest_severity() -> None:
    merged = merge_findings([fnd(Severity.MEDIUM), fnd(Severity.HIGH, source="security")])
    assert len(merged) == 1
    assert merged[0].severity is Severity.HIGH


def test_title_matching_ignores_case_and_spacing() -> None:
    merged = merge_findings([fnd(Severity.LOW, title="Null  Deref"), fnd(Severity.LOW, title="null deref")])
    assert len(merged) == 1


def test_sorted_by_severity_then_location() -> None:
    merged = merge_findings(
        [
            fnd(Severity.LOW, path="b.py"),
            fnd(Severity.CRITICAL, title="x", path="z.py"),
            fnd(Severity.LOW, title="y", path="a.py"),
        ]
    )
    assert [f.severity for f in merged] == [Severity.CRITICAL, Severity.LOW, Severity.LOW]
    assert [f.file_path for f in merged] == ["z.py", "a.py", "b.py"]