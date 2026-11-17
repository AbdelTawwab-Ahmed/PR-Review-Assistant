from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.application.ports.github_port import GitHubError
from app.application.ports.llm_port import LLMError
from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError, UpstreamError

router = APIRouter(prefix="/dev", tags=["dev"])


class AnalyzeRequest(BaseModel):
    repo_full_name: str
    pr_number: int


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