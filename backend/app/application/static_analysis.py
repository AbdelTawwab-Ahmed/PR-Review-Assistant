import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.sandbox_port import Workspace
from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile
from app.domain.services.diff_filter import filter_findings_to_diff

ANALYZABLE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")


@dataclass(frozen=True)
class StaticAnalysisOutcome:
    findings: tuple[Finding, ...] = ()
    notes: tuple[str, ...] = ()


def analyzable_paths(files: Sequence[ChangedFile], max_files: int) -> list[str]:
    paths = [
        f.path
        for f in files
        if f.status != "removed" and f.path.lower().endswith(ANALYZABLE_SUFFIXES)
    ]
    return paths[:max_files]


async def run_analyzers(
    analyzers: Sequence[AnalyzerPort], workspace: Workspace, paths: Sequence[str]
) -> StaticAnalysisOutcome:
    """Run every analyzer in parallel; no diff filtering."""
    if not paths or not analyzers:
        return StaticAnalysisOutcome()
    results = await asyncio.gather(*(a.run(workspace, paths) for a in analyzers))
    findings = tuple(f for r in results for f in r.findings)
    notes = tuple(f"{r.tool} failed: {r.error}" for r in results if r.error)
    return StaticAnalysisOutcome(findings, notes)


async def run_static_analysis(
    analyzers: Sequence[AnalyzerPort],
    workspace: Workspace,
    files: Sequence[ChangedFile],
    paths: Sequence[str],
) -> StaticAnalysisOutcome:
    """Like run_analyzers, but keeps only findings on lines the PR touched."""
    outcome = await run_analyzers(analyzers, workspace, paths)
    kept = tuple(filter_findings_to_diff(outcome.findings, files))
    return StaticAnalysisOutcome(kept, outcome.notes)