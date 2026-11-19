import pytest

from app.application.ports.github_port import FileUpdate, GitHubError
from app.application.use_cases.publish_fix import FixPublishError, PublishFix
from app.domain.entities.fix_proposal import FileChange, FixProposal
from app.domain.enums import FixStatus
from tests.fakes import FakeGitHub, make_pr


def proposal(**overrides) -> FixProposal:
    values = {
        "status": FixStatus.VERIFIED,
        "base_sha": "abc123",
        "changes": (FileChange("src/a.py", "old\n", "new\n"),),
        "attempts": 1,
        "summary": "- `src/a.py`: Use verify() (cc @alice)",
        "notes": ("validated",),
    }
    return FixProposal(**{**values, **overrides})


async def test_publishes_a_new_branch_and_a_stacked_pull_request() -> None:
    github = FakeGitHub(make_pr())
    result = await PublishFix(github).execute("org/repo", 1, proposal())

    assert result.branch == "prra/fix-pr1-abc123"
    assert result.pull_request_url.endswith("/pull/99")
    commit = github.commits[0]
    assert commit["base_sha"] == "abc123"
    assert commit["files"] == [FileUpdate("src/a.py", "new\n")]
    pull = github.pulls[0]
    assert (pull["head"], pull["base"]) == ("prra/fix-pr1-abc123", "feat")  # never main


async def test_mentions_in_model_text_are_defused() -> None:
    github = FakeGitHub(make_pr())
    await PublishFix(github).execute("org/repo", 1, proposal())
    body = github.pulls[0]["body"]
    assert "@alice" not in body
    assert "@\u200balice" in body


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": FixStatus.FAILED},
        {"status": FixStatus.NOTHING_TO_FIX},
        {"changes": ()},
    ],
)
async def test_unpublishable_proposals_are_refused(kwargs: dict) -> None:
    github = FakeGitHub(make_pr())
    with pytest.raises(FixPublishError):
        await PublishFix(github).execute("org/repo", 1, proposal(**kwargs))
    assert github.commits == []


async def test_fork_pull_requests_are_refused() -> None:
    with pytest.raises(FixPublishError, match="fork"):
        await PublishFix(FakeGitHub(make_pr(from_fork=True))).execute("org/repo", 1, proposal())


async def test_stale_proposals_are_refused() -> None:
    github = FakeGitHub(make_pr())
    with pytest.raises(FixPublishError, match="changed"):
        await PublishFix(github).execute("org/repo", 1, proposal(base_sha="older"))
    assert github.commits == []


async def test_existing_fix_branch_gives_a_clear_error() -> None:
    github = FakeGitHub(make_pr(), commit_error=GitHubError("exists", 422))
    with pytest.raises(FixPublishError, match="already exists"):
        await PublishFix(github).execute("org/repo", 1, proposal())
