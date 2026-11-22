import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.application.events import PullRequestEvent
from app.application.ports.github_port import GitHubPort
from app.application.ports.repositories import ReviewRunRepository
from app.application.use_cases.analyze_pull_request import AnalyzePullRequest
from app.domain.entities.review_run import ReviewRun
from app.domain.enums import RunStatus

logger = logging.getLogger(__name__)


class AsyncioRunDispatcher:
    """Dispatches PR review analysis in the background using asyncio."""

    def __init__(
        self,
        analysis: AnalyzePullRequest,
        repository: ReviewRunRepository,
        github: GitHubPort,
        telemetry: Any | None = None,
    ) -> None:
        self._analysis = analysis
        self._repository = repository
        self._github = github
        self._telemetry = telemetry

    async def dispatch(self, event: PullRequestEvent) -> None:
        logger.info(
            "Dispatching PR review for %s#%s @ %s (action: %s)",
            event.repo_full_name,
            event.number,
            event.head_sha[:7],
            event.action,
        )
        if self._telemetry and getattr(self._telemetry, "is_enabled", False):
            self._telemetry.track_event(
                "ReviewRunDispatched",
                {
                    "repo": event.repo_full_name,
                    "pr": str(event.number),
                    "head_sha": event.head_sha[:7],
                    "action": event.action,
                },
            )
        asyncio.create_task(self._process_pr(event))

    async def _process_pr(self, event: PullRequestEvent) -> None:
        run_id = f"{event.repo_full_name}#{event.number}#{event.head_sha[:7]}"
        run = ReviewRun(
            id=run_id,
            repo_full_name=event.repo_full_name,
            pr_number=event.number,
            head_sha=event.head_sha,
            status=RunStatus.ANALYZING,
        )
        try:
            await self._repository.save(run)
        except Exception as exc:
            logger.warning("Failed saving initial run %s: %s", run_id, exc)

        try:
            logger.info("Executing LangGraph analysis for %s", run_id)
            thread_id = run_id
            result = await self._analysis.execute(
                event.repo_full_name,
                event.number,
                propose_fixes=True,
                run_id=thread_id,
            )

            # Update run entity with findings and risk
            run.findings = list(result.findings)
            run.risk = result.risk
            run.updated_at = datetime.now(UTC)

            if result.awaiting_approval:
                run.status = RunStatus.AWAITING_APPROVAL
            elif getattr(result, "awaiting_plan_approval", False):
                run.status = RunStatus.AWAITING_PLAN_APPROVAL
            else:
                run.status = RunStatus.READY_TO_MERGE

            await self._repository.save(run)
            logger.info("Run %s completed with status: %s", run_id, run.status)

            risk_level = (
                getattr(result.risk.level, "value", str(result.risk.level))
                if result.risk
                else "UNKNOWN"
            )
            risk_score = result.risk.score if result.risk else 0

            if self._telemetry and getattr(self._telemetry, "is_enabled", False):
                self._telemetry.track_event(
                    "ReviewRunCompleted",
                    {
                        "run_id": run_id,
                        "repo": event.repo_full_name,
                        "pr": str(event.number),
                        "status": run.status.value,
                        "findings_count": str(len(run.findings)),
                        "risk_score": str(risk_score),
                        "risk_level": str(risk_level),
                    },
                )

            # Post formatted markdown review comment on the PR

            comment_body = [
                "## 🤖 PR Review Assistant Analysis",
                "",
                f"- **Overall Risk Level:** `{risk_level}` (Score: {risk_score}/100)",
                f"- **Findings Detected:** {len(result.findings)}",
                "",
            ]

            if result.findings:
                comment_body.append("### 🔍 Key Findings")
                for f in result.findings[:5]:
                    sev = getattr(f.severity, "value", str(f.severity))
                    loc = f"{f.file_path}:{f.line_start}" if f.file_path else "general"
                    comment_body.append(
                        f"- **[{sev.upper()}]** `{loc}` — **{f.title}**: {f.description}"
                    )
                if len(result.findings) > 5:
                    comment_body.append(
                        f"\n*...and {len(result.findings) - 5} more findings in dashboard.*"
                    )
                comment_body.append("")

            if result.fix_proposal and result.fix_proposal.publishable:
                comment_body.extend(
                    [
                        "### 💡 Automated Fix Proposal",
                        f"{result.fix_proposal.summary}",
                        "",
                        f"👉 **[Review & Approve Fix in Dashboard](https://gbgai2-front-ctc9b7ebcefsbcdy.westus3-01.azurewebsites.net/runs/{run_id})**",
                    ]
                )

            try:
                await self._github.post_comment(
                    event.repo_full_name,
                    event.number,
                    "\n".join(comment_body),
                )
                logger.info(
                    "Posted review comment on GitHub PR %s#%s",
                    event.repo_full_name,
                    event.number,
                )
            except Exception as exc:
                logger.warning(
                    "Failed posting GitHub comment on %s#%s: %s",
                    event.repo_full_name,
                    event.number,
                    exc,
                )

        except Exception as exc:
            logger.exception("Error processing PR review %s: %s", run_id, exc)
            if self._telemetry and getattr(self._telemetry, "is_enabled", False):
                self._telemetry.track_exception(
                    exc,
                    {
                        "run_id": run_id,
                        "repo": event.repo_full_name,
                        "pr": str(event.number),
                    },
                )
                self._telemetry.track_event(
                    "ReviewRunFailed",
                    {
                        "run_id": run_id,
                        "repo": event.repo_full_name,
                        "pr": str(event.number),
                        "error": str(exc),
                    },
                )
            run.status = RunStatus.FAILED
            run.failure_history.append(str(exc))
            run.updated_at = datetime.now(UTC)
            try:
                await self._repository.save(run)
            except Exception as save_exc:
                logger.debug("Failed to persist failed run status: %s", save_exc)
