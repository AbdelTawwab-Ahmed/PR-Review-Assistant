from collections.abc import Sequence

from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile
from app.domain.services.diff_lines import commentable_lines


def filter_findings_to_diff(
    findings: Sequence[Finding], files: Sequence[ChangedFile]
) -> list[Finding]:
    """Keep findings in changed files that touch the diff. Files without a patch keep all."""
    lines_by_path: dict[str, set[int] | None] = {
        f.path: (commentable_lines(f.patch) if f.patch is not None else None) for f in files
    }
    kept: list[Finding] = []
    for finding in findings:
        if finding.file_path not in lines_by_path:
            continue
        diff_lines = lines_by_path[finding.file_path]
        if diff_lines is None or finding.line_start is None:
            kept.append(finding)
            continue
        end = finding.line_end or finding.line_start
        if diff_lines & set(range(finding.line_start, end + 1)):
            kept.append(finding)
    return kept
