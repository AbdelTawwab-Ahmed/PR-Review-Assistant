import pytest

from app.infrastructure.github.webhook_parser import WebhookPayloadError, parse_pull_request_event

PAYLOAD = {
    "action": "opened",
    "pull_request": {
        "number": 7,
        "title": "Fix bug",
        "draft": False,
        "user": {"login": "dev"},
        "head": {"sha": "abc123", "ref": "feat"},
        "base": {"ref": "main"},
    },
    "repository": {"full_name": "org/repo"},
    "sender": {"login": "dev"},
}


def test_parses_event() -> None:
    event = parse_pull_request_event("d-1", PAYLOAD)
    assert event.delivery_id == "d-1"
    assert event.repo_full_name == "org/repo"
    assert event.number == 7
    assert event.head_sha == "abc123"
    assert event.head_branch == "feat"
    assert event.sender == "dev"
    assert event.draft is False


def test_missing_sender_becomes_empty() -> None:
    payload = {k: v for k, v in PAYLOAD.items() if k != "sender"}
    assert parse_pull_request_event("d-1", payload).sender == ""


@pytest.mark.parametrize("payload", [{}, {"action": "opened"}, [], "text", None])
def test_malformed_payload_raises(payload) -> None:
    with pytest.raises(WebhookPayloadError):
        parse_pull_request_event("d-1", payload)
