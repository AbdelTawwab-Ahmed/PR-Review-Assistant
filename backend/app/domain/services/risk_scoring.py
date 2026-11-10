from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.risk_report import RiskFactor, RiskReport
from app.domain.enums import RiskLevel, Severity

SEVERITY_POINTS: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 15,
    Severity.MEDIUM: 5,
    Severity.LOW: 1,
    Severity.INFO: 0,
}
FINDINGS_CAP = 40

SENSITIVE_MARKERS = (
    "auth",
    "security",
    "secret",
    "credential",
    "password",
    "migration",
    ".github/workflows",
    "dockerfile",
    "docker-compose",
    "pyproject.toml",
    "requirements",
    "package.json",
    ".env",
)
CODE_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cs", ".rb", ".php")
TEST_SUFFIXES = ("_test.py", ".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx")


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _is_test_file(path: str) -> bool:
    p = _norm(path)
    name = p.rsplit("/", 1)[-1]
    return "/tests/" in f"/{p}" or name.startswith("test_") or name.endswith(TEST_SUFFIXES)


def _size_factor(pr: PullRequest) -> RiskFactor | None:
    total = pr.total_changes
    if total <= 50:
        return None
    points = 10 if total <= 200 else 20 if total <= 500 else 30
    return RiskFactor("size", points, f"{total} changed lines")


def _file_count_factor(pr: PullRequest) -> RiskFactor | None:
    count = pr.files_changed
    if count > 20:
        return RiskFactor("file_count", 10, f"{count} files changed")
    if count > 10:
        return RiskFactor("file_count", 5, f"{count} files changed")
    return None


def _findings_factor(findings: list[Finding]) -> RiskFactor | None:
    points = min(FINDINGS_CAP, sum(SEVERITY_POINTS[f.severity] for f in findings))
    if points == 0:
        return None
    return RiskFactor("findings", points, f"{len(findings)} findings")


def _sensitive_factor(pr: PullRequest) -> RiskFactor | None:
    hits = [f.path for f in pr.files if any(m in _norm(f.path) for m in SENSITIVE_MARKERS)]
    if not hits:
        return None
    return RiskFactor(
        "sensitive_files", 20 if len(hits) >= 3 else 10, f"{len(hits)} sensitive files"
    )


def _missing_tests_factor(pr: PullRequest) -> RiskFactor | None:
    paths = [f.path for f in pr.files]
    has_code = any(_norm(p).endswith(CODE_EXTENSIONS) and not _is_test_file(p) for p in paths)
    has_tests = any(_is_test_file(p) for p in paths)
    if has_code and not has_tests:
        return RiskFactor("no_tests", 10, "code changed without test changes")
    return None


def level_for(score: int) -> RiskLevel:
    if score < 25:
        return RiskLevel.LOW
    if score < 50:
        return RiskLevel.MEDIUM
    if score < 75:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def compute_risk(pr: PullRequest, findings: list[Finding]) -> RiskReport:
    candidates = (
        _size_factor(pr),
        _file_count_factor(pr),
        _findings_factor(findings),
        _sensitive_factor(pr),
        _missing_tests_factor(pr),
    )
    factors = tuple(f for f in candidates if f is not None)
    score = min(100, sum(f.points for f in factors))
    return RiskReport(score=score, level=level_for(score), factors=factors)
