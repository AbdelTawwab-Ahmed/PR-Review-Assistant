import logging
from dataclasses import asdict
from typing import Any

import httpx

from app.application.caching import get_or_compute, pr_diff_key
from app.application.ports.cache_port import CachePort
from app.application.ports.github_port import GitHubError, ReviewComment
from app.domain.entities.pull_request import ChangedFile, PullRequest
from app.infrastructure.github.diff_parser import parse_files

logger = logging.getLogger(__name__)

MAX_FILES = 3000  # GitHub's cap for the PR files endpoint


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

    async def get_pull_request(self, repo_full_name: str, number: int) -> PullRequest:
        pr = await self._get_json(f"/repos/{repo_full_name}/pulls/{number}")
        head_sha = pr["head"]["sha"]
        files = await self._load_files(repo_full_name, number, head_sha)
        return PullRequest(
            repo_full_name=pr["base"]["repo"]["full_name"],
            number=pr["number"],
            title=pr["title"],
            author=pr["user"]["login"],
            base_branch=pr["base"]["ref"],
            head_branch=pr["head"]["ref"],
            head_sha=head_sha,
            files=files,
            draft=bool(pr.get("draft", False)),
        )

    async def post_comment(self, repo_full_name: str, number: int, body: str) -> None:
        await self._request(
            "POST", f"/repos/{repo_full_name}/issues/{number}/comments", json={"body": body}
        )

    async def post_review(
        self,
        repo_full_name: str,
        number: int,
        commit_sha: str,
        body: str,
        comments: list[ReviewComment],
    ) -> None:
        # event=COMMENT on purpose: the bot never approves or requests changes by itself.
        payload: dict[str, Any] = {"commit_id": commit_sha, "body": body, "event": "COMMENT"}
        if comments:
            payload["comments"] = [
                {"path": c.path, "line": c.line, "side": "RIGHT", "body": c.body} for c in comments
            ]
        try:
            await self._request(
                "POST", f"/repos/{repo_full_name}/pulls/{number}/reviews", json=payload
            )
        except GitHubError as exc:
            if exc.status_code != 422 or not comments:
                raise
            # One bad line number rejects the whole review: fall back to a plain comment.
            logger.warning(
                "inline review rejected for %s#%s, posting plain comment", repo_full_name, number
            )
            lines = "\n".join(f"- `{c.path}:{c.line}` {c.body}" for c in comments)
            await self.post_comment(repo_full_name, number, f"{body}\n\n{lines}")

    async def _load_files(
        self, repo_full_name: str, number: int, head_sha: str
    ) -> tuple[ChangedFile, ...]:
        async def producer() -> list[dict[str, Any]]:
            raw: list[dict[str, Any]] = []
            for page in range(1, MAX_FILES // self._per_page + 1):
                batch = await self._get_json(
                    f"/repos/{repo_full_name}/pulls/{number}/files",
                    params={"per_page": self._per_page, "page": page},
                )
                raw.extend(batch)
                if len(batch) < self._per_page:
                    break
            return [asdict(f) for f in parse_files(raw)]

        if self._cache is None:
            cached = await producer()
        else:
            key = pr_diff_key(repo_full_name, head_sha)
            cached = await get_or_compute(self._cache, key, producer, self._ttl)
        return tuple(ChangedFile(**item) for item in cached)

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", path, params=params)
        return response.json()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub request failed: {exc}") from exc
        if response.status_code >= 400:
            if response.headers.get("x-ratelimit-remaining") == "0":
                logger.warning("GitHub rate limit exhausted")
            raise GitHubError(
                f"{method} {path} returned {response.status_code}", response.status_code
            )
        return response
