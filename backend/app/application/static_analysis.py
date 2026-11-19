import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.ports.analyzer_port import AnalyzerPort, AnalyzerResult
from app.application.ports.sandbox_port import Workspace
from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile
from app.domain.services.diff_filter import filter_findings_to_diff

logger = logging.getLogger(__name__)

ANALYZABLE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


@dataclass(frozen=True)
class StaticAnalysisOutcome:
    findings: tuple[Finding, ...] = ()
    notes: tuple[str, ...] = ()


def analyzable_paths(files: Sequence[ChangedFile], max_files: int) -> list[str]:
    paths = [
        file.path
        for file in files
        if file.status != "removed" and file.path.lower().endswith(ANALYZABLE_SUFFIXES)
    ]

    return paths[:max_files]


async def _run_one(
    analyzer: AnalyzerPort,
    workspace: Workspace,
    paths: Sequence[str],
) -> AnalyzerResult:
    try:
        return await analyzer.run(workspace, paths)
    except Exception as exc:
        logger.exception("Analyzer %s failed unexpectedly", analyzer.name)

        return AnalyzerResult(
            tool=analyzer.name,
            error=f"Unexpected analyzer error: {type(exc).__name__}: {exc}",
        )


async def run_analyzers(
    analyzers: Sequence[AnalyzerPort],
    workspace: Workspace,
    paths: Sequence[str],
) -> StaticAnalysisOutcome:
    """Run every analyzer in parallel and preserve individual failures."""

    if not paths or not analyzers:
        return StaticAnalysisOutcome()

    results = await asyncio.gather(
        *(_run_one(analyzer, workspace, paths) for analyzer in analyzers)
    )

    findings = tuple(finding for result in results for finding in result.findings)

    notes = tuple(f"{result.tool} failed: {result.error}" for result in results if result.error)

    return StaticAnalysisOutcome(
        findings=findings,
        notes=notes,
    )


async def run_static_analysis(
    analyzers: Sequence[AnalyzerPort],
    workspace: Workspace,
    files: Sequence[ChangedFile],
    paths: Sequence[str],
) -> StaticAnalysisOutcome:
    """Run analyzers and keep only findings on lines touched by the PR."""

    outcome = await run_analyzers(analyzers, workspace, paths)

    kept = tuple(filter_findings_to_diff(outcome.findings, files))

    return StaticAnalysisOutcome(
        findings=kept,
        notes=outcome.notes,
    )
