from dataclasses import dataclass

from app.application.ports.llm_port import LLMPort, ModelTier
from app.application.workflow.agents.base import clip, pr_meta_block
from app.application.workflow.agents.prompts import FIXER_PROMPT
from app.application.workflow.diff_chunks import neutralize
from app.application.workflow.schemas import FileFixOut
from app.domain.entities.finding import Finding
from app.domain.entities.pull_request import PullRequest
from app.domain.services.edits import TextEdit

MAX_EDITS_PER_FILE = 20
MAX_PROBLEM_CHARS = 6000
FIRST_ATTEMPT = (
    "Fix the listed findings in the file above. Line numbers in <findings> refer to the "
    "original version of the file."
)
RETRY = (
    "Fix what is reported in <validation_output>. The file above is the current version, "
    "including your earlier edits."
)


@dataclass(frozen=True)
class FileFix:
    edits: tuple[TextEdit, ...]
    explanation: str


def _flat(text: str) -> str:
    return neutralize(" ".join(text.split()))


def findings_block(findings: list[Finding]) -> str:
    lines: list[str] = []
    for i, f in enumerate(findings, 1):
        if f.line_start and f.line_end:
            where = f"lines {f.line_start}-{f.line_end}"
        elif f.line_start:
            where = f"line {f.line_start}"
        else:
            where = "file level"
        lines.append(f"{i}. [{f.severity}] ({f.source}) {where}: {_flat(f.title)}")
        lines.append(f"   {_flat(f.description)}")
        if f.suggestion:
            lines.append(f"   suggestion: {_flat(f.suggestion)}")
    return "<findings>\n" + "\n".join(lines) + "\n</findings>"


class FixerAgent:
    name = "fixer"
    tier = ModelTier.STRONG

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def propose(
        self,
        pr: PullRequest,
        path: str,
        content: str,
        findings: list[Finding],
        problems: str | None = None,
    ) -> FileFix:
        safe_path = neutralize(path).replace('"', "&quot;")
        parts = [
            pr_meta_block(pr),
            findings_block(findings),
            f'<file path="{safe_path}">\n{neutralize(content)}\n</file>',
        ]
        if problems:
            parts.append(
                f"<validation_output>\n{neutralize(problems[:MAX_PROBLEM_CHARS])}\n</validation_output>"
            )
        parts.append(RETRY if problems else FIRST_ATTEMPT)
        out = await self._llm.generate_structured(
            system=FIXER_PROMPT,
            user="\n\n".join(parts),
            schema=FileFixOut,
            tier=self.tier,
            purpose=self.name,
        )
        edits = tuple(
            TextEdit(e.old_text, e.new_text) for e in out.edits[:MAX_EDITS_PER_FILE] if e.old_text.strip()
        )
        return FileFix(edits, clip(out.explanation, 500) or "")