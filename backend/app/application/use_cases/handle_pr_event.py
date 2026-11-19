import logging
from enum import StrEnum

from app.application.events import PullRequestEvent
from app.application.ports.cache_port import CachePort
from app.application.ports.run_dispatcher import RunDispatcher
from app.domain.services.branches import is_bot_branch

logger = logging.getLogger(__name__)

HANDLED_ACTIONS = frozenset({"opened", "reopened", "synchronize", "ready_for_review"})


class EventOutcome(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    IGNORED = "ignored"


class HandlePullRequestEvent:
    def __init__(
        self,
        cache: CachePort,
        dispatcher: RunDispatcher,
        bot_login: str = "",
        dedup_ttl_seconds: int = 86400,
    ) -> None:
        self._cache = cache
        self._dispatcher = dispatcher
        self._bot_login = bot_login.lower()
        self._ttl = dedup_ttl_seconds

    async def execute(self, event: PullRequestEvent) -> EventOutcome:
        if event.action not in HANDLED_ACTIONS or event.draft:
            return EventOutcome.IGNORED

        if self._bot_login and event.sender.lower() == self._bot_login:
            return EventOutcome.IGNORED

        if is_bot_branch(event.head_branch):
            return EventOutcome.IGNORED

        key = f"webhook:delivery:{event.delivery_id}"
        if not await self._cache.set_if_absent(key, True, self._ttl):
            logger.info("duplicate delivery %s ignored", event.delivery_id)
            return EventOutcome.DUPLICATE

        try:
            await self._dispatcher.dispatch(event)
        except Exception:
            await self._cache.delete(key)  # let GitHub's redelivery be processed
            raise

        return EventOutcome.ACCEPTED
