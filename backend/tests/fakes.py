from typing import Any

from pydantic import BaseModel

from app.application.ports.llm_port import LLMError, ModelTier
from app.application.workflow.schemas import FindingOut, FindingsOut, ImpactOut
from app.domain.entities.pull_request import ChangedFile, PullRequest
from app.domain.enums import FindingCategory, Severity

PATCH = "@@ -1,2 +1,3 @@\n import os\n+password = 'x'\n print(1)"


def make_file(path: str = "src/a.py", patch: str | None = PATCH) -> ChangedFile:
    return ChangedFile(path, "modified", 1, 0, patch)


def make_pr(files: list[ChangedFile] | None = None) -> PullRequest:
    return PullRequest(
        repo_full_name="org/repo",
        number=1,
        title="Add login",
        author="dev",
        base_branch="main",
        head_branch="feat",
        head_sha="abc123",
        files=tuple(files if files is not None else [make_file()]),
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
    """Canned output per `purpose` ("reviewer", "security", "impact"); records every call."""

    def __init__(
        self, outputs: dict[str, BaseModel] | None = None, failing: set[str] | None = None
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
            return self.outputs[purpose]
        if schema is FindingsOut:
            return FindingsOut(findings=[])
        return ImpactOut(
            summary="No impact.", affected_components=[], breaking_changes=[], suggested_checks=[]
        )


class FakeGitHub:
    def __init__(self, pr: PullRequest) -> None:
        self.pr = pr

    async def get_pull_request(self, repo_full_name: str, number: int) -> PullRequest:
        return self.pr