import logging
from collections.abc import Mapping
from typing import Any

from app.application.ports.llm_port import LLMError
from app.application.workflow.agents.base import ChunkAnalysisAgent
from app.application.workflow.state import ChunkTask

logger = logging.getLogger(__name__)


def make_analyze_chunk(agents: Mapping[str, ChunkAnalysisAgent]):
    async def analyze_chunk(task: ChunkTask) -> dict[str, Any]:
        agent = agents[task["agent"]]
        try:
            findings = await agent.analyze(task["pr"], task["chunk"])
        except LLMError as exc:
            logger.warning("%s failed on a chunk: %s", agent.name, exc)
            # One failed call must not sink the whole run; record it so the report is honest.
            return {"notes": [f"{agent.name} could not analyze {len(task['chunk'])} file(s)"]}
        return {"findings": findings}

    return analyze_chunk
