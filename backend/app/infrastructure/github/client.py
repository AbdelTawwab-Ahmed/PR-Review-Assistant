import logging
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.application.caching import get_or_compute, pr_diff_key
from app.application.ports.cache_port import CachePort
from app.application.ports.github_port import (
    FileUpdate,
    GitHubError,
    ReviewComment,
)
from app.domain.entities.pull_request import ChangedFile, PullRequest
from app.infrastructure.github.diff_parser import parse_files

logger = logging.getLogger(__name__)

MAX_FILES = 3000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
ARCHIVE_HOSTS = {"codeload.github.com"}


class GitHubClient:
    def __init__(
        self,
        token: str,
        api_url: str = "https://api.github.com",
        cache: CachePort | None = None,
        cache_ttl_seconds: int = 86400,
        http: httpx.AsyncClient | None = None,
        per_page: int = 100,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._http = http or httpx.AsyncClient(
            base_url=api_url,
            headers=headers,
            timeout=httpx.Timeout(15.0),
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

        self._cache = cache
        self._ttl = cache_ttl_seconds
        self._per_page = per_page

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_pull_request(
        self,
        repo_full_name: str,
        number: int,
    ) -> PullRequest:
        pr = await self._get_json(f"/repos/{repo_full_name}/pulls/{number}")

        head_sha = pr["head"]["sha"]
        base_repo = pr["base"]["repo"]["full_name"]
        head_repo = (pr["head"].get("repo") or {}).get("full_name")

        files = await self._load_files(repo_full_name, number, head_sha)

        return PullRequest(
            repo_full_name=base_repo,
            number=pr["number"],
            title=pr["title"],
            author=pr["user"]["login"],
            base_branch=pr["base"]["ref"],
            head_branch=pr["head"]["ref"],
            head_sha=head_sha,
            files=files,
            draft=bool(pr.get("draft", False)),
            from_fork=(head_repo is not None and head_repo.lower() != base_repo.lower()),
        )

    async def list_open_pulls(
        self,
        repo_full_name: str,
    ) -> list[dict[str, Any]]:
        return await self._get_json(f"/repos/{repo_full_name}/pulls?state=open")

    async def download_archive(
        self,
        repo_full_name: str,
        ref: str,
        max_bytes: int = MAX_ARCHIVE_BYTES,
    ) -> bytes:
        """Download a repository tarball at a specific commit or ref."""
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")

        path = f"/repos/{repo_full_name}/tarball/{ref}"

        request = self._http.build_request("GET", path)
        response = await self._send_streaming_request(request)

        try:
            if response.status_code not in (200, 302, 301):
                self._raise_response_error(response, "GET", path)

            if response.status_code in (301, 302):
                location = response.headers.get("location")
                if not location:
                    raise GitHubError("GitHub archive redirect has no location")

                redirect_url = urljoin(str(response.url), location)
                parsed = urlparse(redirect_url)

                if (
                    parsed.scheme != "https"
                    or parsed.hostname not in ARCHIVE_HOSTS
                    or parsed.username
                    or parsed.password
                ):
                    raise GitHubError("GitHub returned an unsafe archive redirect")

                await response.aclose()

                # Build a fresh request without the GitHub Authorization header.
                redirect_request = httpx.Request("GET", redirect_url)
                response = await self._send_streaming_request(redirect_request)

                if response.status_code != 200:
                    self._raise_response_error(
                        response,
                        "GET",
                        "repository archive redirect",
                    )

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise GitHubError("repository archive exceeds the size limit")
                except ValueError:
                    pass

            archive = bytearray()

            async for chunk in response.aiter_bytes():
                archive.extend(chunk)
                if len(archive) > max_bytes:
                    raise GitHubError("repository archive exceeds the size limit")

            if not archive:
                raise GitHubError("GitHub returned an empty repository archive")

            return bytes(archive)

        finally:
            await response.aclose()

    async def _send_streaming_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        try:
            return await self._http.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub archive download failed: {exc}") from exc

    @staticmethod
    def _raise_response_error(
        response: httpx.Response,
        method: str,
        path: str,
    ) -> None:
        if response.headers.get("x-ratelimit-remaining") == "0":
            logger.warning("GitHub rate limit exhausted")

        raise GitHubError(
            f"{method} {path} returned {response.status_code}",
            response.status_code,
        )

    async def post_comment(
        self,
        repo_full_name: str,
        number: int,
        body: str,
    ) -> None:
        await self._request(
            "POST",
            f"/repos/{repo_full_name}/issues/{number}/comments",
            json={"body": body},
        )

    async def post_review(
        self,
        repo_full_name: str,
        number: int,
        commit_sha: str,
        body: str,
        comments: list[ReviewComment],
    ) -> None:
        # The bot only comments; it never approves or requests changes by itself.
        payload: dict[str, Any] = {
            "commit_id": commit_sha,
            "body": body,
            "event": "COMMENT",
        }

        if comments:
            payload["comments"] = [
                {
                    "path": c.path,
                    "line": c.line,
                    "side": "RIGHT",
                    "body": c.body,
                }
                for c in comments
            ]

        try:
            await self._request(
                "POST",
                f"/repos/{repo_full_name}/pulls/{number}/reviews",
                json=payload,
            )
        except GitHubError as exc:
            if exc.status_code != 422 or not comments:
                raise

            # One bad line number rejects the whole review: fall back to a plain comment.
            logger.warning(
                "inline review rejected for %s#%s, posting plain comment",
                repo_full_name,
                number,
            )

            lines = "\n".join(f"- `{c.path}:{c.line}` {c.body}" for c in comments)

            await self.post_comment(
                repo_full_name,
                number,
                f"{body}\n\n{lines}",
            )

    async def commit_files_to_new_branch(
        self,
        repo_full_name: str,
        base_sha: str,
        branch: str,
        message: str,
        files: Sequence[FileUpdate],
    ) -> str:
        """Create a commit on top of base_sha and point a NEW branch at it."""
        repo = f"/repos/{repo_full_name}"

        base_commit = await self._get_json(f"{repo}/git/commits/{base_sha}")

        tree = await self._post_json(
            f"{repo}/git/trees",
            {
                "base_tree": base_commit["tree"]["sha"],
                "tree": [
                    {
                        "path": file.path,
                        "mode": "100644",
                        "type": "blob",
                        "content": file.content,
                    }
                    for file in files
                ],
            },
        )

        commit = await self._post_json(
            f"{repo}/git/commits",
            {
                "message": message,
                "tree": tree["sha"],
                "parents": [base_sha],
            },
        )

        # POST fails if the branch already exists, so nothing is overwritten.
        await self._post_json(
            f"{repo}/git/refs",
            {
                "ref": f"refs/heads/{branch}",
                "sha": commit["sha"],
            },
        )

        return commit["sha"]

    async def open_pull_request(
        self,
        repo_full_name: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        created = await self._post_json(
            f"/repos/{repo_full_name}/pulls",
            {
                "title": title,
                "head": head,
                "base": base,
                "body": body,
            },
        )

        return created["html_url"]

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> Any:
        return (await self._request("POST", path, json=payload)).json()

    async def _load_files(
        self,
        repo_full_name: str,
        number: int,
        head_sha: str,
    ) -> tuple[ChangedFile, ...]:
        async def producer() -> list[dict[str, Any]]:
            raw: list[dict[str, Any]] = []

            for page in range(1, MAX_FILES // self._per_page + 1):
                batch = await self._get_json(
                    f"/repos/{repo_full_name}/pulls/{number}/files",
                    params={
                        "per_page": self._per_page,
                        "page": page,
                    },
                )

                raw.extend(batch)

                if len(batch) < self._per_page:
                    break

            return [asdict(file) for file in parse_files(raw)]

        if self._cache is None:
            cached = await producer()
        else:
            key = pr_diff_key(repo_full_name, head_sha)
            cached = await get_or_compute(
                self._cache,
                key,
                producer,
                self._ttl,
            )

        return tuple(ChangedFile(**item) for item in cached)

    async def _get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._request("GET", path, params=params)
        return response.json()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = await self._http.request(
                method,
                path,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub request failed: {exc}") from exc

        if response.status_code >= 400:
            self._raise_response_error(response, method, path)

        return response
