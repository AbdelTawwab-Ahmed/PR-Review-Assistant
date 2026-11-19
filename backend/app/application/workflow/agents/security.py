from app.application.ports.llm_port import ModelTier
from app.application.workflow.agents.base import ChunkAnalysisAgent
from app.application.workflow.agents.prompts import SECURITY_PROMPT


class SecurityAgent(ChunkAnalysisAgent):
    name = "security"
    system_prompt = SECURITY_PROMPT
    tier = ModelTier.STRONG
