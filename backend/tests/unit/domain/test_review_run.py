import pytest

from app.domain.entities.review_run import ReviewRun
from app.domain.enums import ApprovalDecision, RunStatus
from app.domain.exceptions import InvalidApprovalError, InvalidTransitionError


def make_run(**kwargs) -> ReviewRun:
    return ReviewRun(repo_full_name="org/repo", pr_number=1, head_sha="abc123", **kwargs)


def advance(run: ReviewRun, *statuses: RunStatus) -> None:
    for status in statuses:
        run.transition_to(status)


def test_happy_path_reaches_ready_to_merge() -> None:
    run = make_run()
    advance(
        run,
        RunStatus.ANALYZING,
        RunStatus.PLANNING,
        RunStatus.FIXING,
        RunStatus.VALIDATING,
        RunStatus.AWAITING_APPROVAL,
    )
    run.apply_approval(ApprovalDecision.APPROVE)
    assert run.status is RunStatus.UPDATING_PR
    run.transition_to(RunStatus.READY_TO_MERGE)
    assert run.is_terminal


def test_invalid_transition_raises() -> None:
    run = make_run()
    with pytest.raises(InvalidTransitionError):
        run.transition_to(RunStatus.FIXING)


def test_validation_failure_retries_then_fails() -> None:
    run = make_run(max_retries=1)
    advance(run, RunStatus.ANALYZING, RunStatus.PLANNING, RunStatus.FIXING, RunStatus.VALIDATING)

    run.register_validation_failure("tests failed")
    assert run.status is RunStatus.PLANNING
    assert run.retry_count == 1

    advance(run, RunStatus.FIXING, RunStatus.VALIDATING)
    run.register_validation_failure("tests failed again")
    assert run.status is RunStatus.FAILED
    assert run.failure_history == ["tests failed", "tests failed again"]


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (ApprovalDecision.APPROVE, RunStatus.UPDATING_PR),
        (ApprovalDecision.REJECT, RunStatus.REJECTED),
        (ApprovalDecision.REQUEST_CHANGES, RunStatus.PLANNING),
    ],
)
def test_approval_decisions(decision: ApprovalDecision, expected: RunStatus) -> None:
    run = make_run()
    advance(
        run,
        RunStatus.ANALYZING,
        RunStatus.PLANNING,
        RunStatus.FIXING,
        RunStatus.VALIDATING,
        RunStatus.AWAITING_APPROVAL,
    )
    run.apply_approval(decision)
    assert run.status is expected
    assert run.approval is decision


def test_approval_outside_approval_stage_raises() -> None:
    run = make_run()
    with pytest.raises(InvalidApprovalError):
        run.apply_approval(ApprovalDecision.APPROVE)
