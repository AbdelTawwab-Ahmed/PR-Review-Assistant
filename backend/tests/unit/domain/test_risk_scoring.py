import pytest

from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile, PullRequest
from app.domain.enums import FindingCategory, RiskLevel, Severity
from app.domain.services.risk_scoring import compute_risk, level_for


def make_pr(*files: ChangedFile) -> PullRequest:
    return PullRequest(
        repo_full_name="org/repo",
        number=1,
        title="t",
        author="a",
        base_branch="main",
        head_branch="feat",
        head_sha="abc123",
        files=files,
    )


def make_finding(severity: Severity) -> Finding:
    return Finding(FindingCategory.BUG, severity, "title", "desc", source="reviewer")


def factor_names(report) -> set[str]:
    return {f.name for f in report.factors}


def test_small_docs_change_is_low_risk() -> None:
    report = compute_risk(make_pr(ChangedFile("README.md", "modified", 5, 2)), [])
    assert report.score == 0
    assert report.level is RiskLevel.LOW


def test_large_change_adds_size_factor() -> None:
    pr = make_pr(ChangedFile("docs/big.md", "modified", 600, 0))
    report = compute_risk(pr, [])
    assert report.score == 30
    assert "size" in factor_names(report)


def test_critical_finding_adds_points() -> None:
    pr = make_pr(ChangedFile("README.md", "modified", 1, 0))
    report = compute_risk(pr, [make_finding(Severity.CRITICAL)])
    assert report.score == 25
    assert report.level is RiskLevel.MEDIUM


def test_findings_points_are_capped() -> None:
    pr = make_pr(ChangedFile("README.md", "modified", 1, 0))
    report = compute_risk(pr, [make_finding(Severity.CRITICAL)] * 3)
    assert report.score == 40


def test_sensitive_file_is_flagged() -> None:
    pr = make_pr(
        ChangedFile("src/auth/login.py", "modified", 5, 0),
        ChangedFile("tests/test_login.py", "modified", 5, 0),
    )
    report = compute_risk(pr, [])
    assert "sensitive_files" in factor_names(report)


def test_code_without_tests_is_flagged() -> None:
    report = compute_risk(make_pr(ChangedFile("src/utils.py", "modified", 5, 0)), [])
    assert "no_tests" in factor_names(report)


def test_code_with_tests_is_not_flagged() -> None:
    pr = make_pr(
        ChangedFile("src/utils.py", "modified", 5, 0),
        ChangedFile("tests/test_utils.py", "added", 10, 0),
    )
    assert "no_tests" not in factor_names(compute_risk(pr, []))


def test_score_never_exceeds_100() -> None:
    files = [ChangedFile(f"src/auth/f{i}.py", "modified", 100, 0) for i in range(25)]
    report = compute_risk(make_pr(*files), [make_finding(Severity.CRITICAL)] * 5)
    assert report.score == 100
    assert report.level is RiskLevel.CRITICAL


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0, RiskLevel.LOW),
        (24, RiskLevel.LOW),
        (25, RiskLevel.MEDIUM),
        (49, RiskLevel.MEDIUM),
        (50, RiskLevel.HIGH),
        (74, RiskLevel.HIGH),
        (75, RiskLevel.CRITICAL),
        (100, RiskLevel.CRITICAL),
    ],
)
def test_level_boundaries(score: int, level: RiskLevel) -> None:
    assert level_for(score) is level
