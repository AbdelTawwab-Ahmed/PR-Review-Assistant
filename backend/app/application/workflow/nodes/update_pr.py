import logging
from typing import Any

from app.application.ports.github_port import GitHubError
from app.application.use_cases.publish_fix import FixPublishError, PublishFix
from app.application.workflow.state import ReviewState
from app.domain.enums import ApprovalDecision, FixStatus

logger = logging.getLogger(__name__)


def make_update_pr(publisher: PublishFix | None, *, allow_unverified: bool = False):
    async def update_pr(state: ReviewState) -> dict[str, Any]:
        decision = state.get("approval_decision")
        if decision != ApprovalDecision.APPROVE:
            return {"notes": [f"Update PR skipped (decision was {decision})"]}

        proposal = state.get("proposal")
        is_eligible = proposal is not None and (
            proposal.publishable
            or (
                allow_unverified
                and proposal.status is FixStatus.UNVERIFIED
                and bool(proposal.changes)
            )
        )
        if not is_eligible or proposal is None:
            return {"notes": ["Update PR skipped: proposal is not publishable"]}

        if publisher is None:
            logger.warning("Update PR skipped: no publisher provided")
            return {"notes": ["Update PR skipped: no publisher configured"]}

        try:
            published = await publisher.execute(
                repo_full_name=state["repo_full_name"],
                pr_number=state["pr_number"],
                proposal=proposal,
                allow_unverified=allow_unverified,
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
        except GitHubError as exc:
            if exc.status_code in (401, 403, 404):
                msg = (
                    f"GitHub write permission denied (HTTP {exc.status_code}): "
                    "the configured GitHub token does not have contributor/push access "
                    "to create branches or pull requests on this repository. "
                    "You can still review and copy the generated fix diff below."
                )
            else:
                msg = f"Failed to publish fix on GitHub: {exc}"
            logger.warning("Failed to publish fix: %s", msg)
            return {"notes": [msg]}
        except Exception as exc:
            logger.exception("Unexpected error publishing fix: %s", exc)
            return {"notes": [f"Unexpected error publishing fix: {exc}"]}

    return update_pr
