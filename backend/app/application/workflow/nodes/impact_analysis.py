import logging
from typing import Any

from app.application.ports.llm_port import LLMError
from app.application.workflow.agents.impact import ImpactAgent
from app.application.workflow.state import ImpactTask

logger = logging.getLogger(__name__)


def make_impact_analysis(agent: ImpactAgent):
    async def impact_analysis(task: ImpactTask) -> dict[str, Any]:
        try:
            report = await agent.analyze(task["pr"], task["chunk"])
        except LLMError as exc:
            logger.warning("impact analysis failed: %s", exc)
            return {"notes": ["impact analysis could not be completed"]}
        return {"impact": report}

    return impact_analysis