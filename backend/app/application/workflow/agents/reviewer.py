from app.application.ports.llm_port import ModelTier
from app.application.workflow.agents.base import ChunkAnalysisAgent
from app.application.workflow.agents.prompts import REVIEWER_PROMPT


class ReviewerAgent(ChunkAnalysisAgent):
    name = "reviewer"
    system_prompt = REVIEWER_PROMPT
    tier = ModelTier.STRONG
