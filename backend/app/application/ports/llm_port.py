from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelTier(StrEnum):
    FAST = "fast"  # summaries, simple classification
    STRONG = "strong"  # review, security, fixing


class LLMError(Exception):
    """The model call failed or returned unusable output."""


class LLMPort(Protocol):
    async def generate_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        tier: ModelTier = ModelTier.STRONG,
        purpose: str = "",
    ) -> T: ...