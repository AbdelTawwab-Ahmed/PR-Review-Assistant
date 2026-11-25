import logging
import threading
from collections.abc import Mapping
from typing import Any

from app.application.ports.llm_port import LLMError
from app.application.workflow.agents.base import ChunkAnalysisAgent
from app.application.workflow.state import ChunkTask

logger = logging.getLogger(__name__)


def make_analyze_chunk(agents: Mapping[str, ChunkAnalysisAgent]):
    async def analyze_chunk(task: ChunkTask) -> dict[str, Any]:
        agent = agents[task["agent"]]
        logger.info(
            "Multi-threaded Agent Execution: Starting '%s' analysis on thread '%s' for %d file(s)",
            agent.name,
            threading.current_thread().name,
            len(task["chunk"]),
        )
        try:
            findings = await agent.analyze(task["pr"], task["chunk"])
            logger.info(
                "Multi-threaded Agent Execution: Agent '%s' completed with %d finding(s)",
                agent.name,
                len(findings),
            )
        except LLMError as exc:
            logger.warning("%s failed on a chunk: %s", agent.name, exc)
            # One failed call must not sink the whole run; record it so the report is honest.
            count = len(task["chunk"])
            return {"notes": [f"{agent.name} could not analyze {count} file(s): {exc}"]}
        return {"findings": findings}

    return analyze_chunk
