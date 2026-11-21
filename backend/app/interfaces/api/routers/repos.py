from typing import Annotated, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.container import Container
from app.interfaces.api.deps import get_container

router = APIRouter(prefix="/repos", tags=["repos"])


class MonitorRepoRequest(BaseModel):
    repo_url: str


class StopMonitorRequest(BaseModel):
    repo: str


@router.get("/listening")
async def list_monitored_repositories(
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    repos = await container.repo_monitor.get_monitored_repos()
    return {"repositories": repos, "count": len(repos)}


@router.post("/listen", status_code=status.HTTP_200_OK)
async def listen_to_repository(
    body: MonitorRepoRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    dispatched = await container.repo_monitor.add_repo(body.repo_url)
    return {
        "status": "listening",
        "input": body.repo_url,
        "dispatched_prs": dispatched,
        "message": f"Listening for any new or updated PRs on this repository. Immediately checked and queued {len(dispatched)} PR(s).",
    }


@router.delete("/listen", status_code=status.HTTP_200_OK)
async def stop_listening(
    body: StopMonitorRequest,
    container: Annotated[Container, Depends(get_container)],
) -> dict[str, Any]:
    await container.repo_monitor.remove_repo(body.repo)
    return {"status": "stopped", "repo": body.repo}
