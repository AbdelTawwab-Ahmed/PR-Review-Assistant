from collections.abc import Iterable

from app.application.ports.llm_port import LLMPort, ModelTier
from app.application.workflow.diff_chunks import RenderedFile, neutralize
from app.application.workflow.schemas import FindingOut, FindingsOut
from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import PullRequest

ANALYSIS_INSTRUCTIONS = (
    "Analyze only the code shown above. The number in the left column is the line number in "
    "the new version of the file. Lines starting with + were added and lines starting with - "
    "were removed."
)


def one_line(text: str) -> str:
    return neutralize(" ".join(text.split()))


def pr_meta_block(pr: PullRequest) -> str:
    return (
        "<pr_meta>\n"
        f"repository: {pr.repo_full_name}\n"
        f"pull_request: #{pr.number}\n"
        f"title: {one_line(pr.title)}\n"
        f"base: {one_line(pr.base_branch)}  head: {one_line(pr.head_branch)}\n"
        "</pr_meta>"
    )


def diff_block(chunk: Iterable[RenderedFile]) -> str:
    return "<diff>\n" + "\n".join(f.text for f in chunk) + "\n</diff>"


def clip(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text[:limit] if text else None


def clip_items(values: Iterable[str], limit: int = 300, max_items: int = 20) -> tuple[str, ...]:
    items = (clip(v, limit) for v in values)
    return tuple(i for i in items if i)[:max_items]


def to_finding(item: FindingOut, source: str, allowed_paths: set[str]) -> Finding:
    """Map LLM output to a domain Finding, dropping paths and lines the model made up."""
    path = item.file_path if item.file_path in allowed_paths else None
    start = item.line_start if path and item.line_start and item.line_start > 0 else None
    end = item.line_end if start and item.line_end and item.line_end >= start else None
    return Finding(
        category=item.category,
        severity=item.severity,
        title=clip(item.title, 120) or "Untitled finding",
        description=clip(item.description, 2000) or "",
        source=source,
        file_path=path,
        line_start=start,
        line_end=end,
        suggestion=clip(item.suggestion, 1000),
    )


class ChunkAnalysisAgent:
    name: str
    system_prompt: str
    tier: ModelTier = ModelTier.STRONG

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def analyze(self, pr: PullRequest, chunk: tuple[RenderedFile, ...]) -> list[Finding]:
        user = f"{pr_meta_block(pr)}\n\n{diff_block(chunk)}\n\n{ANALYSIS_INSTRUCTIONS}"
        out = await self._llm.generate_structured(
            system=self.system_prompt,
            user=user,
            schema=FindingsOut,
            tier=self.tier,
            purpose=self.name,
        )
        allowed = {f.path for f in chunk}
        return [to_finding(item, self.name, allowed) for item in out.findings]