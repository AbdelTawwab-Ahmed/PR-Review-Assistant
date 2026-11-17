from typing import Protocol

from app.application.events import PullRequestEvent


class RunDispatcher(Protocol):
    async def dispatch(self, event: PullRequestEvent) -> None: ...
