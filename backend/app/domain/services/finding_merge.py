from app.domain.entities.finding import Finding
from app.domain.enums import Severity

_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def merge_findings(findings: list[Finding]) -> list[Finding]:
    """Drop duplicates (keeping the highest severity) and sort by severity, then location."""
    best: dict[tuple, Finding] = {}
    for f in findings:
        key = (f.file_path, f.line_start, f.category, _norm(f.title))
        current = best.get(key)
        if current is None or _RANK[f.severity] < _RANK[current.severity]:
            best[key] = f
    return sorted(
        best.values(),
        key=lambda f: (_RANK[f.severity], f.file_path or "", f.line_start or 0, f.title),
    )