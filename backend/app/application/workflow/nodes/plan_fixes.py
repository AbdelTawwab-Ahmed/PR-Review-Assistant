import logging
from typing import Any

from app.application.fix_engine import FixEngine
from app.application.ports.github_port import GitHubError
from app.application.ports.sandbox_port import SandboxError
from app.application.workflow.state import ReviewState
from app.domain.entities.fix_proposal import FixProposal
from app.domain.enums import FixStatus

logger = logging.getLogger(__name__)


def make_apply_fixes(engine: FixEngine):
    async def apply_fixes(state: ReviewState) -> dict[str, Any]:
        pr = state["pr"]
        try:
            proposal = await engine.run(pr, state["fix_plan"], state["final_findings"])
        except (GitHubError, SandboxError) as exc:
            logger.warning("fix generation failed: %s", exc)
            proposal = FixProposal(
                FixStatus.FAILED, pr.head_sha, notes=(f"fix generation failed: {exc}",)
            )
        return {"proposal": proposal}

    return apply_fixes