
from collections.abc import Sequence

from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixAction, FixPlan
from app.domain.entities.pull_request import ChangedFile
from app.domain.enums import SEVERITY_LEVEL, FindingCategory, Severity
from app.domain.services.edits import is_editable_path


def plan_fixes(
    findings: Sequence[Finding],
    files: Sequence[ChangedFile],
    *,
    min_severity: Severity = Severity.MEDIUM,
    max_files: int = 5,
    max_findings_per_file: int = 8,
) -> FixPlan:
    """Pick serious findings in editable files changed by the PR."""
    editable = {
        file.path
        for file in files
        if file.status != "removed" and is_editable_path(file.path)
    }
    threshold = SEVERITY_LEVEL[min_severity]
    by_file: dict[str, list[Finding]] = {}

    for finding in findings:
        if finding.file_path not in editable:
            continue

        if (
            finding.category is FindingCategory.STYLE
            or SEVERITY_LEVEL[finding.severity] < threshold
        ):
            continue

        by_file.setdefault(finding.file_path, []).append(finding)

    def worst(items: list[Finding]) -> int:
        return max(SEVERITY_LEVEL[f.severity] for f in items)

    ranked = sorted(
        by_file.items(),
        key=lambda item: (-worst(item[1]), item[0]),
    )[:max_files]

    actions = []
    for path, items in ranked:
        top = sorted(
            items,
            key=lambda finding: -SEVERITY_LEVEL[finding.severity],
        )[:max_findings_per_file]

        actions.append(
            FixAction(
                path,
                "; ".join(f.title for f in top),
                tuple(f.id for f in top),
            )
        )

    return FixPlan(
        actions=tuple(actions),
        rationale=f"{len(actions)} file(s) with findings of severity {min_severity} or higher",
    )
