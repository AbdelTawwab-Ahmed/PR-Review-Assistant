from collections.abc import Sequence
from dataclasses import dataclass

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.github_port import GitHubPort
from app.application.ports.sandbox_port import WorkspaceProvider
from app.application.ports.validation_port import SuiteResult, SuiteRunnerPort
from app.application.static_analysis import analyzable_paths, run_static_analysis
from app.domain.entities.finding import Finding


@dataclass(frozen=True)
class ValidationReport:
    repo_full_name: str
    pr_number: int
    head_sha: str
    findings: tuple[Finding, ...]
    notes: tuple[str, ...]
    suite: SuiteResult | None


class ValidatePullRequest:
    def __init__(
        self,
        github: GitHubPort,
        workspaces: WorkspaceProvider,
        analyzers: Sequence[AnalyzerPort],
        suite_runner: SuiteRunnerPort,
        max_files: int = 200,
    ) -> None:
        self._github = github
        self._workspaces = workspaces

        self._analyzers = analyzers
        self._suite_runner = suite_runner
        self._max_files = max_files

    async def execute(
        self, repo_full_name: str, pr_number: int, *, run_tests: bool = True
    ) -> ValidationReport:
        pr = await self._github.get_pull_request(repo_full_name, pr_number)
        paths = analyzable_paths(pr.files, self._max_files)
        async with self._workspaces.open(repo_full_name, pr.head_sha) as workspace:
            outcome = await run_static_analysis(self._analyzers, workspace, pr.files, paths)
            suite = await self._suite_runner.run(workspace) if run_tests else None
        return ValidationReport(
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            head_sha=pr.head_sha,
            findings=outcome.findings,
            notes=outcome.notes,
            suite=suite,
        )
