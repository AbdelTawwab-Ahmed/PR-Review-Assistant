from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.application.ports.github_port import GitHubError
from app.application.ports.llm_port import LLMError
from app.application.ports.sandbox_port import SandboxError
from app.application.use_cases.publish_fix import FixPublishError
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, ServiceUnavailableError, UpstreamError
from app.domain.services.diffing import render_diff

router = APIRouter(prefix="/dev", tags=["dev"])


class AnalyzeRequest(BaseModel):
    repo_full_name: str
    pr_number: int


class FixRequest(AnalyzeRequest):
    publish: bool = False


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
        result = await container.analysis.execute(body.repo_full_name, body.pr_number)
    except (GitHubError, LLMError) as exc:
        raise UpstreamError(str(exc)) from exc
    return {**asdict(result), "usage": container.token_tracker.snapshot()}


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
            body.repo_full_name, body.pr_number, propose_fixes=True
        )
        proposal = result.fix_proposal
        published = None
        if body.publish:
            published = await container.publisher.execute(
                body.repo_full_name, body.pr_number, proposal
            )
    except FixPublishError as exc:
        raise ConflictError(str(exc)) from exc
    except (GitHubError, LLMError, SandboxError) as exc:
        raise UpstreamError(str(exc)) from exc

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
            "files": [c.path for c in proposal.changes],
            "diff": render_diff(proposal.changes),
        },
        "published": asdict(published) if published else None,
        "usage": container.token_tracker.snapshot(),
    }
