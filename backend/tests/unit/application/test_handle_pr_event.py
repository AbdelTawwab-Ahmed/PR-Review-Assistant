import pytest

from app.application.events import PullRequestEvent
from app.application.use_cases.handle_pr_event import EventOutcome, HandlePullRequestEvent
from app.infrastructure.cache.memory_cache import InMemoryCache


class FakeDispatcher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[PullRequestEvent] = []

    async def dispatch(self, event: PullRequestEvent) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.events.append(event)


def make_event(**overrides) -> PullRequestEvent:
    values = {
        "delivery_id": "d1",
        "action": "opened",
        "repo_full_name": "org/repo",
        "number": 1,
        "head_sha": "abc",
        "base_branch": "main",
        "head_branch": "feat",
        "title": "t",
        "author": "dev",
        "sender": "dev",
        "draft": False,
    }
    return PullRequestEvent(**{**values, **overrides})


async def test_new_event_is_dispatched() -> None:
    dispatcher = FakeDispatcher()
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    assert await use_case.execute(make_event()) is EventOutcome.ACCEPTED
    assert len(dispatcher.events) == 1


async def test_same_delivery_is_processed_once() -> None:
    dispatcher = FakeDispatcher()
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    await use_case.execute(make_event())
    assert await use_case.execute(make_event()) is EventOutcome.DUPLICATE
    assert len(dispatcher.events) == 1


@pytest.mark.parametrize("action", ["closed", "labeled", "edited", "converted_to_draft"])
async def test_unhandled_actions_are_ignored(action: str) -> None:
    dispatcher = FakeDispatcher()
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    assert await use_case.execute(make_event(action=action)) is EventOutcome.IGNORED
    assert dispatcher.events == []


async def test_draft_prs_are_ignored() -> None:
    use_case = HandlePullRequestEvent(InMemoryCache(), FakeDispatcher())
    assert await use_case.execute(make_event(draft=True)) is EventOutcome.IGNORED


async def test_events_from_the_bot_are_ignored_case_insensitively() -> None:
    use_case = HandlePullRequestEvent(InMemoryCache(), FakeDispatcher(), bot_login="Review-Bot")
    assert await use_case.execute(make_event(sender="review-bot")) is EventOutcome.IGNORED


async def test_failed_dispatch_releases_the_delivery() -> None:
    dispatcher = FakeDispatcher(fail=True)
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    with pytest.raises(RuntimeError):
        await use_case.execute(make_event())

    dispatcher.fail = False
    assert await use_case.execute(make_event()) is EventOutcome.ACCEPTED


async def test_bot_fix_branches_are_ignored() -> None:
    dispatcher = FakeDispatcher()
    use_case = HandlePullRequestEvent(InMemoryCache(), dispatcher)
    outcome = await use_case.execute(make_event(head_branch="prra/fix-pr1-abc1234"))
    assert outcome is EventOutcome.IGNORED
    assert dispatcher.events == []
