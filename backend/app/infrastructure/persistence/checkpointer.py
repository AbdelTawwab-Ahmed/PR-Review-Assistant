import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import Settings
from app.infrastructure.persistence.database import is_postgres_reachable

logger = logging.getLogger(__name__)


class ResilientCheckpointer(BaseCheckpointSaver):
    """Wraps primary checkpointer and falls back to MemorySaver on any connection error."""

    def __init__(self, primary: Any, fallback: MemorySaver) -> None:
        super().__init__()
        self.primary = primary
        self.fallback = fallback
        self.use_fallback = False

    def _activate_fallback(self, exc: Exception, operation: str) -> None:
        if not self.use_fallback:
            logger.warning(
                "Checkpointer %s failed: %s; switching to in-memory MemorySaver",
                operation,
                exc,
            )
            self.use_fallback = True

    async def aget_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:
        if not self.use_fallback and hasattr(self.primary, "aget_tuple"):
            try:
                return await self.primary.aget_tuple(config)
            except Exception as exc:
                self._activate_fallback(exc, "aget_tuple")
        return await self.fallback.aget_tuple(config)

    async def alist(
        self,
        config: dict[str, Any] | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if not self.use_fallback and hasattr(self.primary, "alist"):
            try:
                async for item in self.primary.alist(
                    config, filter=filter, before=before, limit=limit
                ):
                    yield item
                return
            except Exception as exc:
                self._activate_fallback(exc, "alist")
        async for item in self.fallback.alist(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict[str, Any]:
        if not self.use_fallback and hasattr(self.primary, "aput"):
            try:
                return await self.primary.aput(config, checkpoint, metadata, new_versions)
            except Exception as exc:
                self._activate_fallback(exc, "aput")
        return await self.fallback.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        if not self.use_fallback and hasattr(self.primary, "aput_writes"):
            try:
                await self.primary.aput_writes(config, writes, task_id)
                return
            except Exception as exc:
                self._activate_fallback(exc, "aput_writes")
        await self.fallback.aput_writes(config, writes, task_id)

    def get_tuple(self, config: dict[str, Any]) -> CheckpointTuple | None:
        if not self.use_fallback and hasattr(self.primary, "get_tuple"):
            try:
                return self.primary.get_tuple(config)
            except Exception as exc:
                self._activate_fallback(exc, "get_tuple")
        return self.fallback.get_tuple(config)

    def list(
        self,
        config: dict[str, Any] | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if not self.use_fallback and hasattr(self.primary, "list"):
            try:
                yield from self.primary.list(config, filter=filter, before=before, limit=limit)
                return
            except Exception as exc:
                self._activate_fallback(exc, "list")
        yield from self.fallback.list(config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict[str, Any]:
        if not self.use_fallback and hasattr(self.primary, "put"):
            try:
                return self.primary.put(config, checkpoint, metadata, new_versions)
            except Exception as exc:
                self._activate_fallback(exc, "put")
        return self.fallback.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: dict[str, Any],
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        if not self.use_fallback and hasattr(self.primary, "put_writes"):
            try:
                self.primary.put_writes(config, writes, task_id)
                return
            except Exception as exc:
                self._activate_fallback(exc, "put_writes")
        self.fallback.put_writes(config, writes, task_id)


class CheckpointerManager:
    def __init__(self, checkpointer: Any, pool: Any = None) -> None:
        self.checkpointer = checkpointer
        self._pool = pool

    async def setup(self) -> None:
        if self._pool is not None and hasattr(self._pool, "open"):
            try:
                await self._pool.open()
            except Exception as exc:
                logger.warning("Failed to open checkpointer pool: %s", exc)
        if hasattr(self.checkpointer, "setup"):
            try:
                await self.checkpointer.setup()
                logger.info("Checkpointer setup completed.")
            except Exception as exc:
                logger.warning("Checkpointer setup failed: %s", exc)

    async def aclose(self) -> None:
        if self._pool is not None and hasattr(self._pool, "close"):
            try:
                await self._pool.close()
                logger.info("Checkpointer connection pool closed.")
            except Exception as exc:
                logger.warning("Error closing checkpointer connection pool: %s", exc)


def build_checkpointer(settings: Settings) -> CheckpointerManager:
    db_url = settings.database_url.get_secret_value()
    if settings.checkpointer_backend == "postgres" and db_url:
        if not is_postgres_reachable(db_url, timeout=3.0):
            logger.info("PostgreSQL host unreachable; using fast in-memory checkpointing.")
            return CheckpointerManager(MemorySaver())
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool

            clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            pool = AsyncConnectionPool(
                conninfo=clean_url,
                max_size=10,
                timeout=4.0,
                kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 3},
                open=False,
            )
            postgres_saver = AsyncPostgresSaver(pool)
            resilient = ResilientCheckpointer(postgres_saver, MemorySaver())
            logger.info("Using resilient PostgreSQL checkpointer backend with in-memory fallback.")
            return CheckpointerManager(resilient, pool=pool)
        except Exception as exc:
            logger.warning(
                "PostgreSQL checkpointer error (%s); falling back to in-memory checkpointing",
                exc,
            )

    return CheckpointerManager(MemorySaver())
