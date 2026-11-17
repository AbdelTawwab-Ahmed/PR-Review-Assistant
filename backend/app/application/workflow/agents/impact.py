from app.application.ports.llm_port import LLMPort, ModelTier
from app.application.workflow.agents.base import (
    clip,
    clip_items,
    diff_block,
    neutralize,
    pr_meta_block,
)
from app.application.workflow.agents.prompts import IMPACT_PROMPT
from app.application.workflow.diff_chunks import RenderedFile
from app.application.workflow.schemas import ImpactOut
from app.domain.entities.impact_report import ImpactReport
from app.domain.entities.pull_request import PullRequest

MAX_LISTED_FILES = 200


class ImpactAgent:
    name = "impact"
    tier = ModelTier.STRONG

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def analyze(self, pr: PullRequest, chunk: tuple[RenderedFile, ...]) -> ImpactReport:
        listing = "\n".join(
            f"- {neutralize(f.path)} ({f.status}, +{f.additions}/-{f.deletions})"
            for f in pr.files[:MAX_LISTED_FILES]
        )
        user = (
            f"{pr_meta_block(pr)}\n\n<file_list>\n{listing}\n</file_list>\n\n"
            f"{diff_block(chunk)}\n\nAssess the impact of the change shown above."
        )
        out = await self._llm.generate_structured(
            system=IMPACT_PROMPT,
            user=user,
            schema=ImpactOut,
            tier=self.tier,
            purpose=self.name,
        )
        return ImpactReport(
            summary=clip(out.summary, 1500) or "",
            affected_components=clip_items(out.affected_components),
            breaking_changes=clip_items(out.breaking_changes),
            suggested_checks=clip_items(out.suggested_checks),
        )