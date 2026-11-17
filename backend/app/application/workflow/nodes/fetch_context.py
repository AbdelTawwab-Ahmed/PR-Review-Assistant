from typing import Any

from app.application.ports.github_port import GitHubPort
from app.application.workflow.state import ReviewState


def make_fetch_context(github: GitHubPort):
    async def fetch_context(state: ReviewState) -> dict[str, Any]:
        pr = await github.get_pull_request(state["repo_full_name"], state["pr_number"])
        return {"pr": pr}

    return fetch_context