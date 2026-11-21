from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.review_run import ReviewRun


class ReviewRunRepository(Protocol):
    async def save(self, run: ReviewRun) -> None:
        """Save or update a review run."""
        ...

    async def get_by_id(self, run_id: str) -> ReviewRun | None:
        """Retrieve a review run by its unique ID."""
        ...

    async def list_by_repo(
        self,
        repo_full_name: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        """List runs for a specific repository, ordered by updated_at descending."""
        ...

    async def list_by_pr(
        self,
        repo_full_name: str,
        pr_number: int,
        *,
        limit: int = 20,
    ) -> Sequence[ReviewRun]:
        """List runs for a specific pull request, ordered by created_at descending."""
        ...

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        """List all runs across all repositories, ordered by updated_at descending."""
        ...
