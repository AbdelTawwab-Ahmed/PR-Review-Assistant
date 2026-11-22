import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import Settings

logger = logging.getLogger(__name__)


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
        try:
            # Fast socket reachability check to prevent 10-minute node checkpoint hangs if DB is firewalled
            import socket
            from urllib.parse import urlparse

            clean_proto = (
                db_url.replace("postgresql+psycopg://", "http://")
                .replace("postgres://", "http://")
                .replace("postgresql://", "http://")
            )
            parsed = urlparse(clean_proto)
            host = parsed.hostname
            port = parsed.port or 5432
            if host:
                sock = socket.socket()
                sock.settimeout(2.0)
                try:
                    sock.connect((host, port))
                finally:
                    sock.close()

            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool

            clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            pool = AsyncConnectionPool(
                conninfo=clean_url,
                max_size=20,
                kwargs={"autocommit": True, "row_factory": dict_row},
                open=False,
            )
            checkpointer = AsyncPostgresSaver(pool)
            logger.info("Using PostgreSQL checkpointer backend.")
            return CheckpointerManager(checkpointer, pool=pool)
        except Exception as exc:
            logger.warning(
                "PostgreSQL checkpointer unreachable (%s); using fast in-memory checkpointing",
                exc,
            )

    return CheckpointerManager(MemorySaver())
