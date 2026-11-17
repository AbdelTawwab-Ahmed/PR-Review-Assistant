import json
from typing import Annotated

from fastapi import APIRouter, Header, status

from app.core.errors import ValidationFailedError
from app.infrastructure.github.webhook_parser import WebhookPayloadError, parse_pull_request_event
from app.interfaces.api.deps import GitHubBodyDep, HandlePREventDep

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    body: GitHubBodyDep,
    use_case: HandlePREventDep,
    x_github_event: Annotated[str | None, Header()] = None,
    x_github_delivery: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if x_github_event == "ping":
        return {"status": "pong"}
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": "unsupported_event"}
    if not x_github_delivery:
        raise ValidationFailedError("Missing X-GitHub-Delivery header")

    try:
        event = parse_pull_request_event(x_github_delivery, json.loads(body))
    except (ValueError, WebhookPayloadError) as exc:
        raise ValidationFailedError("Invalid webhook payload") from exc

    outcome = await use_case.execute(event)
    return {"status": outcome.value}
