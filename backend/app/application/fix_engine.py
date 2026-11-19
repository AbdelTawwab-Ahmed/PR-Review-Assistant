import asyncio
import logging
from dataclasses import dataclass, field

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.file_store import FileStore
from app.application.ports.llm_port import LLMError
from app.application.ports.sandbox_port import Workspace, WorkspaceProvider
from app.application.ports.validation_port import SuiteResult, SuiteRunnerPort, SuiteStatus
from app.application.static_analysis import run_analyzers
from app.application.workflow.agents.fixer import FileFix, FixerAgent
from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixAction, FixPlan
from app.domain.entities.fix_proposal import FileChange, FixProposal
from app.domain.entities.pull_request import PullRequest
from app.domain.enums import SEVERITY_LEVEL, FixStatus, Severity
from app.domain.services.diffing import count_changed_lines
from app.domain.services.edits import EditRejectedError, apply_text_edit, python_syntax_error

logger = logging.getLogger(__name__)

TRACKED_LEVEL = SEVERITY_LEVEL[Severity.MEDIUM]


@dataclass(frozen=True)
class FixSettings:
    max_attempts: int = 3
    max_changed_lines: int = 300
    max_file_chars: int = 60_000
    run_tests: bool = True


@dataclass(frozen=True)
class Measurement:
    """What the checks say about the workspace at one moment."""

    findings: dict[tuple[str, str, str], int] = field(default_factory=dict)
    failed_tests: frozenset[str] = frozenset()
    suite_status: SuiteStatus | None = None
    output_tail: str = ""
    notes: tuple[str, ...] = ()


def failed_test_ids(suite: SuiteResult | None) -> frozenset[str]:
    if suite is None:
        return frozenset()
    ids: set[str] = set()
    for line in suite.failures:  # "FAILED tests/test_a.py::test_x - message"
        _, _, rest = line.partition(" ")
        ids.add(rest.split(" - ")[0].strip())
    return frozenset(ids)


def find_regressions(before: Measurement, after: Measurement) -> list[str]:
    """Problems the fix introduced. Failures that already existed are not blamed on it."""
    problems: list[str] = []
    new_failures = sorted(after.failed_tests - before.failed_tests)
    if new_failures:
        shown = "\n".join(new_failures[:10])
        tail = after.output_tail[-2000:]
        problems.append(f"New failing tests:\n{shown}\n\nTest output (tail):\n{tail}")
    broken = {SuiteStatus.ERROR, SuiteStatus.TIMED_OUT}
    if after.suite_status in broken and before.suite_status not in broken:
        problems.append(
            f"The test run ended with status '{after.suite_status}'.\n{after.output_tail[-1000:]}"
        )
    new_findings = [
        f"{source}: {title} ({path})"
        for (source, title, path), count in after.findings.items()
        if count > before.findings.get((source, title, path), 0)
    ]
    if new_findings:
        problems.append("New static-analysis findings:\n" + "\n".join(sorted(new_findings)[:10]))
    return problems


def _bullets(header: str, items: list[str]) -> str:
    return header + ":\n" + "\n".join(f"- {item}" for item in items) if items else ""


async def _no_suite() -> None:
    return None


class FixEngine:
    """Generates fixes for a plan, applies them in a host-side workspace and verifies them.

    One workspace (one download) serves the whole retry loop. Untrusted code only ever runs
    in the sandbox, which sees this workspace read-only.
    """

    def __init__(
        self,
        *,
        workspaces: WorkspaceProvider,
        files: FileStore,
        fixer: FixerAgent,
        analyzers: tuple[AnalyzerPort, ...] = (),
        suite_runner: SuiteRunnerPort | None = None,
        settings: FixSettings | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._files = files
        self._fixer = fixer
        self._analyzers = analyzers
        self._suite_runner = suite_runner
        self._settings = settings or FixSettings()

    @property
    def _can_validate(self) -> bool:
        return bool(self._analyzers) or (
            self._suite_runner is not None and self._settings.run_tests
        )

    async def run(self, pr: PullRequest, plan: FixPlan, findings: list[Finding]) -> FixProposal:
        settings = self._settings
        by_id = {f.id: f for f in findings}
        notes: list[str] = []

        async with self._workspaces.open(pr.repo_full_name, pr.head_sha) as ws:
            originals = self._read_originals(ws, plan, notes)
            actions = [a for a in plan.actions if a.file_path in originals]
            if not actions:
                return FixProposal(
                    FixStatus.NOTHING_TO_FIX,
                    pr.head_sha,
                    summary="No file could be fixed automatically.",
                    notes=tuple(notes),
                )
            paths = [a.file_path for a in actions]
            targeted = tuple(i for a in actions for i in a.finding_ids)

            baseline = await self._measure(ws, paths, install=True) if self._can_validate else None
            if baseline:
                notes.extend(baseline.notes)

            current = dict(originals)
            explanations: dict[str, str] = {}
            problems: str | None = None
            status = FixStatus.FAILED
            attempts = 0

            for attempt in range(1, settings.max_attempts + 1):
                attempts = attempt
                fixes = await self._generate(pr, actions, by_id, current, problems, notes)
                if all(fix is None for fix in fixes.values()):
                    break  # every model call failed; already noted
                explanations.update(
                    {p: fix.explanation for p, fix in fixes.items() if fix and fix.edits}
                )
                if not any(fix and fix.edits for fix in fixes.values()):
                    notes.append("the fixer proposed no changes")
                    if current == originals:
                        status = FixStatus.NOTHING_TO_FIX
                    break

                proposed, rejections = self._apply(current, fixes)
                if proposed == current:
                    problems = _bullets("These edits were rejected", rejections)
                    continue
                changed = sum(count_changed_lines(originals[p], proposed[p]) for p in proposed)
                if changed > settings.max_changed_lines:
                    problems = "Your edits changed too many lines. Make smaller, targeted edits."
                    continue

                for path, text in proposed.items():
                    if text != current[path]:
                        self._files.write(ws, path, text)
                current = proposed

                if baseline is None:
                    notes.append("not validated: no sandbox tools are enabled")
                    status = FixStatus.UNVERIFIED
                    break
                after = await self._measure(ws, paths, install=False)
                regressions = find_regressions(baseline, after)
                if not regressions:
                    notes.append("validated: no new failing tests or static-analysis findings")
                    status = FixStatus.VERIFIED
                    break
                problems = "\n\n".join(regressions)
                if rejections:
                    problems += "\n\n" + _bullets("These edits were rejected", rejections)

        if status not in (FixStatus.VERIFIED, FixStatus.UNVERIFIED):
            if problems:
                notes.append(f"last problem: {problems[:300]}")
            return FixProposal(
                status,
                pr.head_sha,
                attempts=attempts,
                targeted_finding_ids=targeted,
                summary="No fix could be verified." if status is FixStatus.FAILED else "",
                notes=tuple(notes),
            )

        changes = tuple(
            FileChange(p, originals[p], current[p]) for p in paths if current[p] != originals[p]
        )
        summary = "\n".join(
            f"- `{c.path}`: {explanations.get(c.path) or 'updated'}" for c in changes
        )
        return FixProposal(status, pr.head_sha, changes, attempts, targeted, summary, tuple(notes))

    def _read_originals(self, ws: Workspace, plan: FixPlan, notes: list[str]) -> dict[str, str]:
        originals: dict[str, str] = {}
        for action in plan.actions:
            content = self._files.read(ws, action.file_path)
            if content is None:
                notes.append(
                    f"{action.file_path}: could not be read (missing, binary or not UTF-8)"
                )
            elif len(content) > self._settings.max_file_chars:
                notes.append(f"{action.file_path}: too large to fix automatically")
            else:
                originals[action.file_path] = content
        return originals

    async def _generate(
        self,
        pr: PullRequest,
        actions: list[FixAction],
        by_id: dict[str, Finding],
        current: dict[str, str],
        problems: str | None,
        notes: list[str],
    ) -> dict[str, FileFix | None]:
        async def one(action: FixAction) -> tuple[str, FileFix | None]:
            targeted = [by_id[i] for i in action.finding_ids if i in by_id]
            try:
                fix = await self._fixer.propose(
                    pr, action.file_path, current[action.file_path], targeted, problems
                )
            except LLMError as exc:
                logger.warning("fixer failed for %s: %s", action.file_path, exc)
                notes.append(f"{action.file_path}: the fixer failed ({exc})")
                return action.file_path, None
            return action.file_path, fix

        return dict(await asyncio.gather(*(one(a) for a in actions)))

    @staticmethod
    def _apply(
        current: dict[str, str], fixes: dict[str, FileFix | None]
    ) -> tuple[dict[str, str], list[str]]:
        """Apply edits in memory, one writer, in order. Bad edits are rejected, not guessed."""
        proposed = dict(current)
        rejections: list[str] = []
        for path, fix in fixes.items():
            if fix is None or not fix.edits:
                continue
            text = proposed[path]
            for edit in fix.edits:
                try:
                    text = apply_text_edit(text, edit.old_text, edit.new_text)
                except EditRejectedError as exc:
                    rejections.append(f"{path}: {exc}")
            error = python_syntax_error(path, text)
            if error:
                rejections.append(f"{path}: {error}; all edits to this file were discarded")
                continue
            proposed[path] = text
        return proposed, rejections

    async def _measure(self, ws: Workspace, paths: list[str], *, install: bool) -> Measurement:
        run_tests = self._suite_runner is not None and self._settings.run_tests
        outcome, suite = await asyncio.gather(
            run_analyzers(self._analyzers, ws, paths),
            self._suite_runner.run(ws, install_dependencies=install) if run_tests else _no_suite(),
        )
        counts: dict[tuple[str, str, str], int] = {}
        for f in outcome.findings:
            if SEVERITY_LEVEL[f.severity] >= TRACKED_LEVEL:
                key = (f.source, f.title, f.file_path or "")
                counts[key] = counts.get(key, 0) + 1
        notes = list(outcome.notes)
        if suite is not None:
            notes.extend(suite.notes)
        return Measurement(
            findings=counts,
            failed_tests=failed_test_ids(suite),
            suite_status=suite.status if suite else None,
            output_tail=suite.output_tail if suite else "",
            notes=tuple(notes),
        )
