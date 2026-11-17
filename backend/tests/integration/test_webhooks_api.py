import json

import pytest
from fastapi.testclient import TestClient

from app.application.events import PullRequestEvent
from app.application.use_cases.handle_pr_event import HandlePullRequestEvent
from app.core.config import Settings, get_settings
from app.infrastructure.cache.memory_cache import InMemoryCache
from app.infrastructure.github.webhook_signature import compute_signature
from app.interfaces.api.deps import get_handle_pr_event
from app.main import create_app

SECRET = "s3cret"
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


class RecordingDispatcher:
    def __init__(self) -> None:
        self.events: list[PullRequestEvent] = []

    async def dispatch(self, event: PullRequestEvent) -> None:
        self.events.append(event)


@pytest.fixture
def dispatcher() -> RecordingDispatcher:
    return RecordingDispatcher()


@pytest.fixture
def client(dispatcher: RecordingDispatcher) -> TestClient:
    app = create_app()
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    app.dependency_overrides[get_settings] = lambda: Settings(github_webhook_secret=SECRET)
    app.dependency_overrides[get_handle_pr_event] = lambda: use_case
    return TestClient(app)


def send(client: TestClient, payload, *, event="pull_request", delivery="d-1", secret=SECRET):
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
        "X-Hub-Signature-256": compute_signature(secret, body),
        "Content-Type": "application/json",
    }
    return client.post("/api/webhooks/github", content=body, headers=headers)


def test_valid_event_is_accepted(client: TestClient, dispatcher: RecordingDispatcher) -> None:
    response = send(client, PAYLOAD)
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert dispatcher.events[0].head_sha == "abc123"


def test_wrong_signature_is_rejected(client: TestClient, dispatcher: RecordingDispatcher) -> None:
    response = send(client, PAYLOAD, secret="wrong")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert dispatcher.events == []


def test_missing_signature_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/webhooks/github",
        content=b"{}",
        headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "d-1"},
    )
    assert response.status_code == 401


def test_ping_is_answered(client: TestClient) -> None:
    response = send(client, {"zen": "Keep it logically awesome."}, event="ping")
    assert response.status_code == 202
    assert response.json() == {"status": "pong"}


def test_other_events_are_ignored(client: TestClient, dispatcher: RecordingDispatcher) -> None:
    response = send(client, {"ref": "refs/heads/main"}, event="push")
    assert response.json()["status"] == "ignored"
    assert dispatcher.events == []


def test_redelivery_is_reported_as_duplicate(
    client: TestClient, dispatcher: RecordingDispatcher
) -> None:
    send(client, PAYLOAD, delivery="d-9")
    response = send(client, PAYLOAD, delivery="d-9")
    assert response.json() == {"status": "duplicate"}
    assert len(dispatcher.events) == 1


def test_malformed_payload_returns_422(client: TestClient) -> None:
    response = send(client, {"action": "opened"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
