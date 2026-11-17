from dataclasses import dataclass


@dataclass(frozen=True)
class PullRequestEvent:
    delivery_id: str
    action: str
    repo_full_name: str
    number: int
    head_sha: str
    base_branch: str
    head_branch: str
    title: str
    author: str
    sender: str
    draft: bool = False
