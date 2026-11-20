import logging
from typing import Any

from app.application.use_cases.publish_fix import FixPublishError, PublishFix
from app.application.workflow.state import ReviewState
from app.domain.enums import ApprovalDecision

logger = logging.getLogger(__name__)


def make_update_pr(publisher: PublishFix | None):
    async def update_pr(state: ReviewState) -> dict[str, Any]:
        decision = state.get("approval_decision")
        if decision != ApprovalDecision.APPROVE:
            return {"notes": [f"Update PR skipped (decision was {decision})"]}

        proposal = state.get("proposal")
        if not proposal or not proposal.publishable:
            return {"notes": ["Update PR skipped: proposal is not publishable"]}

        if publisher is None:
            logger.warning("Update PR skipped: no publisher provided")
            return {"notes": ["Update PR skipped: no publisher configured"]}

        try:
            published = await publisher.execute(
                repo_full_name=state["repo_full_name"],
                pr_number=state["pr_number"],
                proposal=proposal,
            )
            logger.info(
                "Fix successfully published to %s (%s)",
                published.branch,
                published.pull_request_url,
            )
            return {
                "published_branch": published.branch,
                "published_pr_url": published.pull_request_url,
                "notes": [
                    f"Fix branch created: {published.branch}",
                    f"Pull request opened: {published.pull_request_url}",
                ],
            }
        except FixPublishError as exc:
            logger.warning("Failed to publish fix: %s", exc)
            return {"notes": [f"Failed to publish fix: {exc}"]}
        except Exception as exc:
            logger.exception("Unexpected error publishing fix: %s", exc)
            return {"notes": [f"Unexpected error publishing fix: {exc}"]}

    return update_pr
