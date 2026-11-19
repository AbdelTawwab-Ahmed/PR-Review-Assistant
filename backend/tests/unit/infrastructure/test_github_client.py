import json

import httpx
import pytest

from app.application.ports.github_port import FileUpdate, GitHubError, ReviewComment
from app.infrastructure.cache.memory_cache import InMemoryCache
from app.infrastructure.github.client import GitHubClient

PR_JSON = {
    "number": 7,
    "title": "Fix bug",
    "draft": False,
    "user": {"login": "dev"},
    "head": {"sha": "abc123", "ref": "feat"},
    "base": {"ref": "main", "repo": {"full_name": "org/repo"}},
}
FILE_A = {
    "filename": "a.py",
    "status": "modified",
    "additions": 3,
    "deletions": 1,
    "patch": "@@ -1 +1,3 @@\n x\n+y\n+z",
}
FILE_B = {"filename": "b.md", "status": "added", "additions": 2, "deletions": 0}
FILE_PAGES = {1: [FILE_A], 2: [FILE_B]}


def make_client(handler, cache=None, per_page: int = 100) -> GitHubClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.com",
    )
    return GitHubClient(token="t", cache=cache, http=http, per_page=per_page)


def pr_handler(calls: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)

        if path == "/repos/org/repo/pulls/7":
            return httpx.Response(200, json=PR_JSON)

        if path == "/repos/org/repo/pulls/7/files":
            page = int(request.url.params.get("page", "1"))
            return httpx.Response(200, json=FILE_PAGES.get(page, []))

        return httpx.Response(404, json={"message": "Not Found"})

    return handler


async def test_get_pull_request_maps_fields_and_paginates() -> None:
    client = make_client(pr_handler([]), per_page=1)
    pr = await client.get_pull_request("org/repo", 7)

    assert pr.head_sha == "abc123"
    assert pr.base_branch == "main"
    assert [f.path for f in pr.files] == ["a.py", "b.md"]
    assert pr.files[1].patch is None
    assert pr.total_changes == 6


async def test_files_are_cached_by_sha() -> None:
    calls: list[str] = []
    client = make_client(pr_handler(calls), cache=InMemoryCache(), per_page=1)

    await client.get_pull_request("org/repo", 7)
    file_calls = sum(1 for c in calls if c.endswith("/files"))
    assert file_calls > 0

    pr = await client.get_pull_request("org/repo", 7)

    assert sum(1 for c in calls if c.endswith("/files")) == file_calls
    assert [f.path for f in pr.files] == ["a.py", "b.md"]


async def test_missing_pr_raises_github_error() -> None:
    client = make_client(pr_handler([]))

    with pytest.raises(GitHubError) as exc_info:
        await client.get_pull_request("org/repo", 999)

    assert exc_info.value.status_code == 404


async def test_review_is_comment_only_with_inline_comments() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={})

    client = make_client(handler)
    await client.post_review(
        "org/repo",
        7,
        "abc123",
        "Summary",
        [ReviewComment("a.py", 3, "x")],
    )

    assert seen[0]["event"] == "COMMENT"
    assert seen[0]["commit_id"] == "abc123"
    assert seen[0]["comments"] == [{"path": "a.py", "line": 3, "side": "RIGHT", "body": "x"}]


async def test_review_falls_back_to_plain_comment_on_422() -> None:
    posted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/reviews"):
            return httpx.Response(422, json={"message": "Unprocessable"})

        posted.append(json.loads(request.content))
        return httpx.Response(201, json={})

    client = make_client(handler)
    await client.post_review(
        "org/repo",
        7,
        "abc123",
        "Summary",
        [ReviewComment("a.py", 3, "Bug here")],
    )

    assert len(posted) == 1
    assert "a.py:3" in posted[0]["body"]


async def test_non_422_review_error_is_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = make_client(handler)

    with pytest.raises(GitHubError):
        await client.post_review("org/repo", 7, "abc123", "Summary", [])


async def test_fork_pull_requests_are_flagged() -> None:
    forked = {
        **PR_JSON,
        "head": {
            **PR_JSON["head"],
            "repo": {"full_name": "someone/repo"},
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=forked)

    pr = await make_client(handler).get_pull_request("org/repo", 7)

    assert pr.from_fork is True


async def test_commit_files_to_new_branch_uses_the_git_data_api() -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))

        if request.method == "GET":
            return httpx.Response(200, json={"tree": {"sha": "tree0"}})

        if request.url.path.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "tree1"})

        if request.url.path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "commit1"})

        return httpx.Response(201, json={})

    sha = await make_client(handler).commit_files_to_new_branch(
        "org/repo",
        "base1",
        "prra/fix-pr1-abc1234",
        "msg",
        [FileUpdate("a.py", "x = 1\n")],
    )

    assert sha == "commit1"
    assert [(method, path) for method, path, _ in seen] == [
        ("GET", "/repos/org/repo/git/commits/base1"),
        ("POST", "/repos/org/repo/git/trees"),
        ("POST", "/repos/org/repo/git/commits"),
        ("POST", "/repos/org/repo/git/refs"),
    ]
    assert seen[1][2]["base_tree"] == "tree0"
    assert seen[1][2]["tree"] == [
        {
            "path": "a.py",
            "mode": "100644",
            "type": "blob",
            "content": "x = 1\n",
        }
    ]
    assert seen[2][2]["parents"] == ["base1"]
    assert seen[3][2] == {
        "ref": "refs/heads/prra/fix-pr1-abc1234",
        "sha": "commit1",
    }


async def test_open_pull_request_returns_the_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["base"] == "feat"
        return httpx.Response(
            201,
            json={"html_url": "https://github.com/org/repo/pull/9"},
        )

    url = await make_client(handler).open_pull_request(
        "org/repo",
        "prra/x",
        "feat",
        "t",
        "b",
    )

    assert url.endswith("/pull/9")


async def test_download_archive_returns_the_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/org/repo/tarball/abc123"
        return httpx.Response(200, content=b"tarball")

    assert await make_client(handler).download_archive("org/repo", "abc123", 1000) == b"tarball"


async def test_download_archive_enforces_the_size_limit() -> None:
    client = make_client(lambda request: httpx.Response(200, content=b"x" * 100))

    with pytest.raises(GitHubError):
        await client.download_archive("org/repo", "abc123", 50)


async def test_download_archive_reports_http_errors() -> None:
    client = make_client(lambda request: httpx.Response(404, json={}))

    with pytest.raises(GitHubError) as exc_info:
        await client.download_archive("org/repo", "abc123", 1000)

    assert exc_info.value.status_code == 404
