import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.infrastructure.persistence.models import Base

logger = logging.getLogger(__name__)


def normalize_database_url(url: str) -> str:
    """Ensure PostgreSQL URLs use the psycopg async driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


class DatabaseManager:
    def __init__(self, db_url: str) -> None:
        async_url = normalize_database_url(db_url)
        self._engine: AsyncEngine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True,
        )
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessionmaker() as sess:
            try:
                yield sess
            except Exception:
                await sess.rollback()
                raise

    async def setup(self) -> None:
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created successfully.")
        except Exception as exc:
            logger.warning("Database setup failed: %s", exc)

    async def aclose(self) -> None:
        try:
            await self._engine.dispose()
            logger.info("Database engine disposed.")
        except Exception as exc:
            logger.warning("Error disposing database engine: %s", exc)


def build_database_manager(settings: Settings) -> DatabaseManager | None:
    db_url = settings.database_url.get_secret_value()
    if settings.checkpointer_backend == "postgres" and db_url:
        try:
            return DatabaseManager(db_url)
        except Exception as exc:
            logger.warning("Could not initialize DatabaseManager (%s)", exc)
    return None
