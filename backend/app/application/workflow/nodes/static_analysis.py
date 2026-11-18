import logging
from collections.abc import Sequence
from typing import Any

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.github_port import GitHubError
from app.application.ports.sandbox_port import SandboxError, WorkspaceProvider
from app.application.static_analysis import analyzable_paths, run_static_analysis
from app.application.workflow.state import StaticTask

logger = logging.getLogger(__name__)


def make_static_analysis(
    workspaces: WorkspaceProvider, analyzers: Sequence[AnalyzerPort], max_files: int
):
    async def static_analysis(task: StaticTask) -> dict[str, Any]:
        pr = task["pr"]
        paths = analyzable_paths(pr.files, max_files)
        if not paths:
            return {"notes": []}
        try:
            async with workspaces.open(pr.repo_full_name, pr.head_sha) as workspace:
                outcome = await run_static_analysis(analyzers, workspace, pr.files, paths)
        except (GitHubError, SandboxError) as exc:
            logger.warning("static analysis skipped: %s", exc)
            return {"notes": [f"static analysis skipped: {exc}"]}
        return {"findings": list(outcome.findings), "notes": list(outcome.notes)}

    return static_analysis
