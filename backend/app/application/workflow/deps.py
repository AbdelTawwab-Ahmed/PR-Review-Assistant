from dataclasses import dataclass

from app.application.ports.github_port import GitHubPort
from app.application.ports.llm_port import LLMPort


@dataclass(frozen=True)
class WorkflowDeps:
    github: GitHubPort
    llm: LLMPort
    chunk_chars: int = 24000
    max_chunks: int = 8