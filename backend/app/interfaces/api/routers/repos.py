import uuid
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.application.events import PullRequestEvent
from app.application.use_cases.handle_pr_event import EventOutcome
from app.core.container import Container
from app.interfaces.api.deps import get_container

router = APIRouter(prefix="/repos", tags=["repos"])


class MonitorRepoRequest(BaseModel):
    repo_url: str


class StopMonitorRequest(BaseModel):
    repo: str


class AnalyzeRepoRequest(BaseModel):
    repo: str
    pr_number: int | None = None


def clean_repo_name(raw: str) -> tuple[str, int | None]:
    """Extract owner/repo and optional pr_number from any GitHub URL or shorthand."""
    clean = raw.strip().strip("/")
    pr_number = None

    if "github.com/" in clean:
        clean = clean.split("github.com/")[-1].strip("/")

    if "/pull/" in clean:
        parts = clean.split("/pull/")
        clean = parts[0].strip("/")
        try:
            pr_number = int(parts[1].split("/")[0].split("?")[0].split("#")[0])
        except (IndexError, ValueError):
            pass
    elif "#" in clean:
        parts = clean.split("#")
        clean = parts[0].strip("/")
        try:
            pr_number = int(parts[1])
        except (IndexError, ValueError):
            pass

    clean = clean.removesuffix(".git")
    parts = clean.split("/")
    if len(parts) >= 2:
        clean = f"{parts[0]}/{parts[1]}"

    return clean, pr_number


@router.get("/user-repos")
async def list_user_repositories(
    container: Annotated[Container, Depends(get_container)],
) -> list[dict[str, Any]]:
    """List accessible repositories for the connected GitHub PAT."""
    try:
        raw_repos = await container.github._get_json("/user/repos?sort=updated&per_page=30")
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description"),
                "language": r.get("language") or "Code",
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "default_branch": r.get("default_branch", "main"),
                "updated_at": r.get("updated_at"),
                "private": r.get("private", False),
            }
            for r in raw_repos
        ]
    except Exception:
        # Fallback to empty if token cannot list user repos
        return []


@router.get("/details")
async def get_repo_details(
    repo: str,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    """Fetch rich repository metadata and open pull requests for any GitHub repo."""
    repo_clean, pr_from_url = clean_repo_name(repo)
    if not repo_clean or "/" not in repo_clean:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository format. Please enter an owner/repo or GitHub URL.",
        )

    try:
        info = await container.github._get_json(f"/repos/{repo_clean}")
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_clean}' not found or inaccessible. {exc}",
        ) from exc

    try:
        pulls = await container.github.list_open_pulls(repo_clean)
    except Exception:
        pulls = []

    return {
        "repo": {
            "id": info["id"],
            "name": info["name"],
            "full_name": info["full_name"],
            "description": info.get("description") or "No description provided.",
            "stars": info.get("stargazers_count", 0),
            "forks": info.get("forks_count", 0),
            "language": info.get("language") or "Codebase",
            "default_branch": info.get("default_branch", "main"),
            "owner": {
                "login": info["owner"]["login"],
                "avatar_url": info["owner"].get("avatar_url"),
            },
            "html_url": info.get("html_url"),
        },
        "url_pr_number": pr_from_url,
        "open_prs": [
            {
                "number": p["number"],
                "title": p.get("title", f"PR #{p['number']}"),
                "author": p.get("user", {}).get("login", ""),
                "avatar_url": p.get("user", {}).get("avatar_url", ""),
                "head_sha": p.get("head", {}).get("sha", ""),
                "head_branch": p.get("head", {}).get("ref", ""),
                "base_branch": p.get("base", {}).get("ref", ""),
                "created_at": p.get("created_at"),
            }
            for p in pulls
        ],
    }


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_repository(
    body: AnalyzeRepoRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    """Trigger an AI-powered multi-agent review for a repository."""
    repo_clean, pr_from_url = clean_repo_name(body.repo)
    pr_num = body.pr_number or pr_from_url

    if pr_num is None:
        # Find active open PR on the repo
        open_prs = await container.github.list_open_pulls(repo_clean)
        if open_prs:
            pr_num = open_prs[0]["number"]
        else:
            try:
                all_prs = await container.github._get_json(f"/repos/{repo_clean}/pulls?state=all&per_page=5")
                if all_prs:
                    pr_num = all_prs[0]["number"]
            except Exception:
                pass
            if pr_num is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"No pull requests found on {repo_clean}. Please open a pull request or specify a PR number (e.g. {repo_clean}#1).",
                )

    pr_info = await container.github.get_pull_request(repo_clean, pr_num)
    event = PullRequestEvent(
        delivery_id=f"manual-{pr_info.head_sha[:7]}-{uuid.uuid4().hex[:8]}",
        action="synchronize",
        repo_full_name=repo_clean,
        number=pr_num,
        head_sha=pr_info.head_sha,
        base_branch=pr_info.base_branch,
        head_branch=pr_info.head_branch,
        title=pr_info.title,
        author=pr_info.author,
        sender=pr_info.author,
    )
    outcome = await container.handle_pr_event.execute(event)
    if outcome == EventOutcome.DUPLICATE:
        await container.handle_pr_event._dispatcher.dispatch(event)
        outcome = EventOutcome.ACCEPTED
    run_id = f"{repo_clean}#{pr_num}#{pr_info.head_sha[:7]}"

    return {
        "status": outcome.value,
        "run_id": run_id,
        "repo": repo_clean,
        "pr_number": pr_num,
        "title": pr_info.title,
        "head_sha": pr_info.head_sha,
        "dashboard_url": f"/runs/{run_id}",
    }


@router.get("/listening")
async def list_monitored_repositories(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if not container.repo_monitor:
        return {"repositories": [], "count": 0}
    try:
        repos = await container.repo_monitor.get_monitored_repos()
        return {"repositories": repos, "count": len(repos)}
    except Exception:
        return {"repositories": [], "count": 0}


@router.post("/listen", status_code=status.HTTP_200_OK)
async def listen_to_repository(
    body: MonitorRepoRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if not container.repo_monitor:
        raise HTTPException(
            status_code=503,
            detail="Repository monitor service is not active on backend.",
        )
    repo_clean, _ = clean_repo_name(body.repo_url)
    dispatched = await container.repo_monitor.add_repo(repo_clean)
    return {
        "status": "listening",
        "repo": repo_clean,
        "dispatched_prs": dispatched,
        "message": f"Listening for any new or updated PRs on {repo_clean}. Immediately checked and queued {len(dispatched)} PR(s).",
    }


@router.delete("/listen", status_code=status.HTTP_200_OK)
async def stop_listening(
    body: StopMonitorRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    if not container.repo_monitor:
        return {"status": "stopped", "repo": body.repo}
    repo_clean, _ = clean_repo_name(body.repo)
    await container.repo_monitor.remove_repo(repo_clean)
    return {"status": "stopped", "repo": repo_clean}
