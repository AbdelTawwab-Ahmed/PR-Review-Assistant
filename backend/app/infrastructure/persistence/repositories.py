from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, select

from app.application.ports.repositories import ReviewRunRepository
from app.core.config import Settings
from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixAction, FixPlan
from app.domain.entities.review_run import ReviewRun
from app.domain.entities.risk_report import RiskFactor, RiskReport
from app.domain.enums import ApprovalDecision, FindingCategory, RiskLevel, RunStatus, Severity
from app.infrastructure.persistence.database import DatabaseManager
from app.infrastructure.persistence.models import ReviewRunModel


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "id": f.id,
        "category": f.category.value,
        "severity": f.severity.value,
        "title": f.title,
        "description": f.description,
        "source": f.source,
        "file_path": f.file_path,
        "line_start": f.line_start,
        "line_end": f.line_end,
        "suggestion": f.suggestion,
    }


def _dict_to_finding(d: dict[str, Any]) -> Finding:
    return Finding(
        id=d["id"],
        category=FindingCategory(d["category"]),
        severity=Severity(d["severity"]),
        title=d["title"],
        description=d.get("description", ""),
        source=d.get("source", ""),
        file_path=d.get("file_path"),
        line_start=d.get("line_start"),
        line_end=d.get("line_end"),
        suggestion=d.get("suggestion"),
    )


def _risk_to_dict(r: RiskReport | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {
        "score": r.score,
        "level": r.level.value,
        "factors": [{"name": f.name, "points": f.points, "reason": f.reason} for f in r.factors],
    }


def _dict_to_risk(d: dict[str, Any] | None) -> RiskReport | None:
    if not d:
        return None
    factors = tuple(
        RiskFactor(name=f["name"], points=f["points"], reason=f["reason"])
        for f in d.get("factors", [])
    )
    return RiskReport(score=d["score"], level=RiskLevel(d["level"]), factors=factors)


def _fix_plan_to_dict(p: FixPlan | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "rationale": p.rationale,
        "attempt": p.attempt,
        "actions": [
            {
                "file_path": a.file_path,
                "description": a.description,
                "finding_ids": list(a.finding_ids),
            }
            for a in p.actions
        ],
    }


def _dict_to_fix_plan(d: dict[str, Any] | None) -> FixPlan | None:
    if not d:
        return None
    actions = tuple(
        FixAction(
            file_path=a["file_path"],
            description=a["description"],
            finding_ids=tuple(a.get("finding_ids", ())),
        )
        for a in d.get("actions", [])
    )
    return FixPlan(actions=actions, rationale=d.get("rationale", ""), attempt=d.get("attempt", 1))


def review_run_to_dict(r: ReviewRun) -> dict[str, Any]:
    return {
        "id": r.id,
        "repo_full_name": r.repo_full_name,
        "pr_number": r.pr_number,
        "head_sha": r.head_sha,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "retry_count": r.retry_count,
        "max_retries": r.max_retries,
        "approval": r.approval.value if r.approval and hasattr(r.approval, "value") else (r.approval if r.approval else None),
        "findings": [_finding_to_dict(f) if hasattr(f, "category") else f for f in r.findings],
        "risk": _risk_to_dict(r.risk) if hasattr(r.risk, "level") else r.risk,
        "fix_plan": _fix_plan_to_dict(r.fix_plan) if hasattr(r.fix_plan, "actions") else r.fix_plan,
        "failure_history": list(r.failure_history or []),
        "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
        "updated_at": r.updated_at.isoformat() if hasattr(r.updated_at, "isoformat") else str(r.updated_at),
    }


def _model_to_entity(m: ReviewRunModel) -> ReviewRun:
    try:
        status_val = RunStatus(m.status)
    except Exception:
        status_val = RunStatus.PENDING

    findings = []
    for f in (m.findings_data or []):
        try:
            findings.append(_dict_to_finding(f))
        except Exception:
            pass

    approval_val = None
    if m.approval:
        try:
            approval_val = ApprovalDecision(m.approval)
        except Exception:
            approval_val = None

    return ReviewRun(
        id=m.id,
        repo_full_name=m.repo_full_name,
        pr_number=m.pr_number,
        head_sha=m.head_sha,
        status=status_val,
        findings=findings,
        risk=_dict_to_risk(m.risk_data),
        fix_plan=_dict_to_fix_plan(m.fix_plan_data),
        retry_count=m.retry_count or 0,
        max_retries=m.max_retries or 3,
        failure_history=list(m.failure_history or []),
        approval=approval_val,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class PostgresReviewRunRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def save(self, run: ReviewRun) -> None:
        try:
            async with self._db.session() as session:
                model = ReviewRunModel(
                    id=run.id,
                    repo_full_name=run.repo_full_name,
                    pr_number=run.pr_number,
                    head_sha=run.head_sha,
                    status=run.status.value,
                    retry_count=run.retry_count,
                    max_retries=run.max_retries,
                    approval=run.approval.value if run.approval else None,
                    findings_data=[_finding_to_dict(f) for f in run.findings],
                    risk_data=_risk_to_dict(run.risk),
                    fix_plan_data=_fix_plan_to_dict(run.fix_plan),
                    failure_history=list(run.failure_history),
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                )
                await session.merge(model)
                await session.commit()
        except Exception:
            pass

    async def get_by_id(self, run_id: str) -> ReviewRun | None:
        try:
            async with self._db.session() as session:
                stmt = select(ReviewRunModel).where(ReviewRunModel.id == run_id)
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()
                return _model_to_entity(model) if model else None
        except Exception:
            return None

    async def list_by_repo(
        self,
        repo_full_name: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        try:
            async with self._db.session() as session:
                stmt = (
                    select(ReviewRunModel)
                    .where(ReviewRunModel.repo_full_name == repo_full_name)
                    .order_by(desc(ReviewRunModel.updated_at))
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                return [_model_to_entity(m) for m in result.scalars().all()]
        except Exception:
            return []

    async def list_by_pr(
        self,
        repo_full_name: str,
        pr_number: int,
        *,
        limit: int = 20,
    ) -> Sequence[ReviewRun]:
        try:
            async with self._db.session() as session:
                stmt = (
                    select(ReviewRunModel)
                    .where(
                        ReviewRunModel.repo_full_name == repo_full_name,
                        ReviewRunModel.pr_number == pr_number,
                    )
                    .order_by(desc(ReviewRunModel.created_at))
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return [_model_to_entity(m) for m in result.scalars().all()]
        except Exception:
            return []

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        try:
            async with self._db.session() as session:
                stmt = (
                    select(ReviewRunModel)
                    .order_by(desc(ReviewRunModel.updated_at))
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                return [_model_to_entity(m) for m in result.scalars().all()]
        except Exception:
            return []


class InMemoryReviewRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, ReviewRun] = {}

    async def save(self, run: ReviewRun) -> None:
        self._runs[run.id] = run

    async def get_by_id(self, run_id: str) -> ReviewRun | None:
        return self._runs.get(run_id)

    async def list_by_repo(
        self,
        repo_full_name: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        matches = [r for r in self._runs.values() if r.repo_full_name == repo_full_name]
        matches.sort(key=lambda r: r.updated_at, reverse=True)
        return matches[offset : offset + limit]

    async def list_by_pr(
        self,
        repo_full_name: str,
        pr_number: int,
        *,
        limit: int = 20,
    ) -> Sequence[ReviewRun]:
        matches = [
            r
            for r in self._runs.values()
            if r.repo_full_name == repo_full_name and r.pr_number == pr_number
        ]
        matches.sort(key=lambda r: r.created_at, reverse=True)
        return matches[:limit]

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        matches = list(self._runs.values())
        matches.sort(key=lambda r: r.updated_at, reverse=True)
        return matches[offset : offset + limit]


def build_review_run_repository(
    settings: Settings, db_manager: DatabaseManager | None
) -> ReviewRunRepository:
    if settings.checkpointer_backend == "postgres" and db_manager is not None:
        return PostgresReviewRunRepository(db_manager)
    return InMemoryReviewRunRepository()
