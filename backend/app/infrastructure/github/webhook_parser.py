from typing import Any

from app.application.events import PullRequestEvent


class WebhookPayloadError(ValueError):
    """The webhook payload does not have the expected shape."""


def parse_pull_request_event(delivery_id: str, payload: Any) -> PullRequestEvent:
    try:
        pr = payload["pull_request"]
        return PullRequestEvent(
            delivery_id=delivery_id,
            action=payload["action"],
            repo_full_name=payload["repository"]["full_name"],
            number=pr["number"],
            head_sha=pr["head"]["sha"],
            base_branch=pr["base"]["ref"],
            head_branch=pr["head"]["ref"],
            title=pr["title"],
            author=pr["user"]["login"],
            sender=payload.get("sender", {}).get("login", ""),
            draft=bool(pr.get("draft", False)),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise WebhookPayloadError("Malformed pull_request payload") from exc
