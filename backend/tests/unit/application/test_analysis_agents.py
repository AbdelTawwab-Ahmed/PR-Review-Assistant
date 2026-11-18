from app.application.workflow.agents.impact import ImpactAgent
from app.application.workflow.agents.reviewer import ReviewerAgent
from app.application.workflow.agents.security import SecurityAgent
from app.application.workflow.diff_chunks import render_file
from app.application.workflow.schemas import FindingsOut, ImpactOut
from app.domain.enums import FindingCategory, Severity
from tests.fakes import FakeLLM, finding_out, make_file, make_pr


def chunk():
    return (render_file(make_file("src/a.py"), 10_000),)


async def test_reviewer_maps_output_to_domain_findings() -> None:
    llm = FakeLLM(
        {"reviewer": FindingsOut(findings=[finding_out("Hardcoded password", Severity.HIGH)])}
    )
    findings = await ReviewerAgent(llm).analyze(make_pr(), chunk())
    assert len(findings) == 1
    assert findings[0].source == "reviewer"
    assert findings[0].severity is Severity.HIGH
    assert (findings[0].file_path, findings[0].line_start) == ("src/a.py", 2)


async def test_unknown_file_path_is_dropped_but_finding_is_kept() -> None:
    llm = FakeLLM({"reviewer": FindingsOut(findings=[finding_out("Bug", path="ghost.py", line=5)])})
    (finding,) = await ReviewerAgent(llm).analyze(make_pr(), chunk())
    assert finding.file_path is None
    assert finding.line_start is None


async def test_invalid_line_numbers_are_cleaned() -> None:
    llm = FakeLLM({"reviewer": FindingsOut(findings=[finding_out("Bug", line=0)])})
    (finding,) = await ReviewerAgent(llm).analyze(make_pr(), chunk())
    assert finding.line_start is None
    assert finding.line_end is None


async def test_prompt_marks_diff_as_untrusted_and_numbers_lines() -> None:
    llm = FakeLLM()
    await SecurityAgent(llm).analyze(make_pr(), chunk())
    call = llm.calls[0]
    assert call["purpose"] == "security"
    assert "untrusted" in call["system"].lower()
    assert "<diff>" in call["user"]
    assert "    2 +password = 'x'" in call["user"]


async def test_security_findings_keep_their_category() -> None:
    out = FindingsOut(
        findings=[finding_out("SQL injection", Severity.CRITICAL, FindingCategory.SECURITY)]
    )
    (finding,) = await SecurityAgent(FakeLLM({"security": out})).analyze(make_pr(), chunk())
    assert finding.category is FindingCategory.SECURITY


async def test_impact_agent_maps_report() -> None:
    llm = FakeLLM(
        {
            "impact": ImpactOut(
                summary=" Touches login. ",
                affected_components=["auth", " "],
                breaking_changes=[],
                suggested_checks=["Run auth tests"],
            )
        }
    )
    report = await ImpactAgent(llm).analyze(make_pr(), chunk())
    assert report.summary == "Touches login."
    assert report.affected_components == ("auth",)
    assert report.suggested_checks == ("Run auth tests",)
    assert "- src/a.py (modified, +1/-0)" in llm.calls[0]["user"]
