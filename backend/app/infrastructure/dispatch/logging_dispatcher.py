import logging

from app.application.events import PullRequestEvent

logger = logging.getLogger(__name__)


class LoggingRunDispatcher:
    """Placeholder until the LangGraph runner exists (ai-analysis branch)."""

    async def dispatch(self, event: PullRequestEvent) -> None:
        logger.info(
            "PR event accepted: %s#%s @ %s (%s)",
            event.repo_full_name,
            event.number,
            event.head_sha[:7],
            event.action,
        )
