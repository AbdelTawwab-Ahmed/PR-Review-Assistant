from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.pull_request import PullRequest


class GitHubError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ReviewComment:
    path: str
    line: int
    body: str


@dataclass(frozen=True)
class FileUpdate:
    path: str
    content: str


class GitHubPort(Protocol):
    async def get_pull_request(
        self,
        repo_full_name: str,
        number: int,
    ) -> PullRequest: ...

    async def post_comment(
        self,
        repo_full_name: str,
        number: int,
        body: str,
    ) -> None: ...

    async def post_review(
        self,
        repo_full_name: str,
        number: int,
        commit_sha: str,
        body: str,
        comments: list[ReviewComment],
    ) -> None: ...

    async def download_archive(
        self,
        repo_full_name: str,
        ref: str,
        max_bytes: int,
    ) -> bytes: ...

    async def commit_files_to_new_branch(
        self,
        repo_full_name: str,
        base_sha: str,
        branch: str,
        message: str,
        files: Sequence[FileUpdate],
    ) -> str: ...

    async def open_pull_request(
        self,
        repo_full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str: ...