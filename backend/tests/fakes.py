from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.application.ports.analyzer_port import AnalyzerResult
from app.application.ports.github_port import FileUpdate, GitHubError
from app.application.ports.llm_port import LLMError, ModelTier
from app.application.ports.sandbox_port import ExecResult, Workspace
from app.application.ports.validation_port import SuiteResult
from app.application.workflow.schemas import FindingOut, FindingsOut, ImpactOut
from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import ChangedFile, PullRequest
from app.domain.enums import FindingCategory, Severity

PATCH = "@@ -1,2 +1,3 @@\n import os\n+password = 'x'\n print(1)"

WORKSPACE = Workspace(
    source=Path("repo"),
    deps=Path("deps"),
)


def make_file(path: str = "src/a.py", patch: str | None = PATCH) -> ChangedFile:
    return ChangedFile(path, "modified", 1, 0, patch)


def make_pr(
    files: list[ChangedFile] | None = None,
    from_fork: bool = False,
) -> PullRequest:
    return PullRequest(
        repo_full_name="org/repo",
        number=1,
        title="Add login",
        author="dev",
        base_branch="main",
        head_branch="feat",
        head_sha="abc123",
        files=tuple(files if files is not None else [make_file()]),
        from_fork=from_fork,
    )


def finding_out(
    title: str,
    severity: Severity = Severity.MEDIUM,
    category: FindingCategory = FindingCategory.BUG,
    path: str | None = "src/a.py",
    line: int | None = 2,
) -> FindingOut:
    return FindingOut(
        category=category,
        severity=severity,
        title=title,
        description="details",
        file_path=path,
        line_start=line,
        line_end=line,
        suggestion="fix it",
    )


class FakeLLM:
    """Canned output per purpose; records every call."""

    def __init__(
        self,
        outputs: dict[str, BaseModel | list[BaseModel]] | None = None,
        failing: set[str] | None = None,
    ) -> None:
        self.outputs = outputs or {}
        self.failing = failing or set()
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type,
        tier: ModelTier = ModelTier.STRONG,
        purpose: str = "",
    ):
        self.calls.append({"purpose": purpose, "system": system, "user": user, "tier": tier})

        if purpose in self.failing:
            raise LLMError(f"{purpose} failed")

        if purpose in self.outputs:
            value = self.outputs[purpose]
            if isinstance(value, list):
                return value.pop(0) if len(value) > 1 else value[0]
            return value

        if schema is FindingsOut:
            return FindingsOut(findings=[])

        return ImpactOut(
            summary="No impact.",
            affected_components=[],
            breaking_changes=[],
            suggested_checks=[],
        )


class FakeGitHub:
    def __init__(
        self,
        pr: PullRequest,
        commit_error: GitHubError | None = None,
    ) -> None:
        self.pr = pr
        self.commit_error = commit_error
        self.commits: list[dict[str, Any]] = []
        self.pulls: list[dict[str, Any]] = []

    async def get_pull_request(
        self,
        repo_full_name: str,
        number: int,
    ) -> PullRequest:
        return self.pr

    async def commit_files_to_new_branch(
        self,
        repo_full_name: str,
        base_sha: str,
        branch: str,
        message: str,
        files: Sequence[FileUpdate],
    ) -> str:
        if self.commit_error:
            raise self.commit_error

        self.commits.append(
            {
                "repo": repo_full_name,
                "base_sha": base_sha,
                "branch": branch,
                "files": list(files),
            }
        )
        return "newsha123"

    async def open_pull_request(
        self,
        repo_full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        self.pulls.append(
            {
                "head": head,
                "base": base,
                "title": title,
                "body": body,
            }
        )
        return "https://github.com/org/repo/pull/99"


class FakeWorkspaces:
    def __init__(
        self,
        fail: Exception | None = None,
        workspace: Workspace | None = None,
    ) -> None:
        self.fail = fail
        self.workspace = workspace
        self.opened: list[tuple[str, str]] = []

    @asynccontextmanager
    async def open(self, repo_full_name: str, sha: str):
        if self.fail:
            raise self.fail

        self.opened.append((repo_full_name, sha))
        yield self.workspace if self.workspace is not None else WORKSPACE


class FakeSuiteRunner:
    """Returns queued results in order; the last one repeats."""

    def __init__(self, results: Sequence[SuiteResult]) -> None:
        self.results = list(results)
        self.calls: list[bool] = []

    async def run(
        self,
        workspace: Workspace,
        *,
        install_dependencies: bool = True,
    ) -> SuiteResult:
        self.calls.append(install_dependencies)

        if not self.results:
            raise RuntimeError("FakeSuiteRunner has no results configured")

        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


class FakeSandbox:
    """Returns queued results in order (then a default) and records every call."""

    def __init__(
        self,
        results: Sequence[ExecResult] | None = None,
        default: ExecResult | None = None,
    ) -> None:
        self.results = list(results or [])
        self.default = default or ExecResult(0, "", "")
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        workspace: Workspace,
        command: Sequence[str],
        *,
        workdir: str = ".",
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
        install_mode: bool = False,
    ) -> ExecResult:
        self.calls.append(
            {
                "command": list(command),
                "workdir": workdir,
                "env": dict(env or {}),
                "install_mode": install_mode,
            }
        )
        return self.results.pop(0) if self.results else self.default


class FakeAnalyzer:
    def __init__(
        self,
        name: str,
        findings: Sequence[Finding] = (),
        error: str | None = None,
    ) -> None:
        self.name = name
        self.findings = tuple(findings)
        self.error = error
        self.calls: list[list[str]] = []

    async def run(
        self,
        workspace: Workspace,
        paths: Sequence[str],
    ) -> AnalyzerResult:
        self.calls.append(list(paths))
        return AnalyzerResult(self.name, self.findings, self.error)
