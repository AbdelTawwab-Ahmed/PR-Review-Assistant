from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.application.ports.github_port import GitHubError
from app.application.ports.llm_port import LLMError
from app.application.ports.sandbox_port import SandboxError
from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError, UpstreamError
from app.domain.services.diffing import render_diff

router = APIRouter(prefix="/dev", tags=["dev"])


class AnalyzeRequest(BaseModel):
    repo_full_name: str
    pr_number: int


class FixRequest(AnalyzeRequest):
    pass


class ValidateRequest(AnalyzeRequest):
    run_tests: bool = True


@router.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.azure_openai_endpoint:
        raise ServiceUnavailableError("Azure OpenAI is not configured")

    container = request.app.state.container

    try:
        result = await container.analysis.execute(
            body.repo_full_name,
            body.pr_number,
        )
    except (GitHubError, LLMError) as exc:
        raise UpstreamError(str(exc)) from exc

    return {
        **asdict(result),
        "usage": container.token_tracker.snapshot(),
    }


@router.post("/fix")
async def fix(
    body: FixRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.azure_openai_endpoint:
        raise ServiceUnavailableError("Azure OpenAI is not configured")

    container = request.app.state.container

    try:
        result = await container.analysis.execute(
            body.repo_full_name,
            body.pr_number,
            propose_fixes=True,
        )
    except (GitHubError, LLMError, SandboxError) as exc:
        raise UpstreamError(str(exc)) from exc

    proposal = result.fix_proposal

    return {
        "analysis": {
            "head_sha": result.head_sha,
            "findings": len(result.findings),
            "risk": asdict(result.risk),
            "notes": list(result.notes),
        },
        "proposal": {
            "status": proposal.status,
            "attempts": proposal.attempts,
            "summary": proposal.summary,
            "notes": list(proposal.notes),
            "files": [change.path for change in proposal.changes],
            "diff": render_diff(proposal.changes),
        },
        "usage": container.token_tracker.snapshot(),
    }


@router.post("/validate")
async def validate(
    body: ValidateRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.sandbox_enabled:
        raise ServiceUnavailableError("Sandbox is disabled (set SANDBOX_ENABLED=true)")

    container = request.app.state.container

    try:
        report = await container.validation.execute(
            body.repo_full_name,
            body.pr_number,
            run_tests=body.run_tests,
        )
    except (GitHubError, SandboxError) as exc:
        raise UpstreamError(str(exc)) from exc

    return asdict(report)
