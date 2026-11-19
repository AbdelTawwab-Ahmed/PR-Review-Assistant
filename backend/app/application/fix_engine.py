import asyncio
import logging
from dataclasses import dataclass, field

from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.file_store import FileStore
from app.application.ports.llm_port import LLMError
from app.application.ports.sandbox_port import Workspace, WorkspaceProvider
from app.application.ports.validation_port import (
    SuiteResult,
    SuiteRunnerPort,
    SuiteStatus,
)
from app.application.static_analysis import run_analyzers
from app.application.workflow.agents.fixer import FileFix, FixerAgent
from app.domain.entities.finding import Finding
from app.domain.entities.fix_plan import FixAction, FixPlan
from app.domain.entities.fix_proposal import FileChange, FixProposal
from app.domain.entities.pull_request import PullRequest
from app.domain.enums import SEVERITY_LEVEL, FixStatus, Severity
from app.domain.services.diffing import count_changed_lines
from app.domain.services.edits import (
    EditRejectedError,
    apply_text_edit,
    python_syntax_error,
)

logger = logging.getLogger(__name__)

TRACKED_LEVEL = SEVERITY_LEVEL[Severity.MEDIUM]


@dataclass(frozen=True)
class FixSettings:
    max_attempts: int = 3
    max_changed_lines: int = 300
    max_file_chars: int = 60_000
    run_tests: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.max_changed_lines < 0:
            raise ValueError("max_changed_lines cannot be negative")
        if self.max_file_chars < 1:
            raise ValueError("max_file_chars must be at least 1")


@dataclass(frozen=True)
class Measurement:
    """What the checks say about the workspace at one moment."""

    findings: dict[tuple[str, str, str], int] = field(default_factory=dict)
    failed_tests: frozenset[str] = frozenset()
    suite_status: SuiteStatus | None = None
    output_tail: str = ""
    notes: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()


def failed_test_ids(suite: SuiteResult | None) -> frozenset[str]:
    if suite is None:
        return frozenset()

    ids: set[str] = set()

    for line in suite.failures:
        _, _, rest = line.partition(" ")
        test_id = rest.split(" - ")[0].strip()

        if test_id:
            ids.add(test_id)

    return frozenset(ids)


def find_regressions(before: Measurement, after: Measurement) -> list[str]:
    """Find problems introduced by the fix without blaming existing failures."""

    problems: list[str] = []

    if after.validation_errors:
        problems.append(
            "Validation could not be completed reliably:\n" + "\n".join(after.validation_errors)
        )

    broken = {SuiteStatus.ERROR, SuiteStatus.TIMED_OUT}

    if after.suite_status in broken:
        problems.append(
            f"The test run ended with status '{after.suite_status}'.\n{after.output_tail[-1000:]}"
        )

    if after.suite_status is SuiteStatus.NO_TESTS and before.suite_status not in (
        None,
        SuiteStatus.NO_TESTS,
    ):
        problems.append(
            "The test suite collected no tests after the fix, "
            "although tests were collected in the baseline."
        )

    new_failures = sorted(after.failed_tests - before.failed_tests)

    if new_failures:
        shown = "\n".join(new_failures[:10])
        tail = after.output_tail[-2000:]

        problems.append(f"New failing tests:\n{shown}\n\nTest output (tail):\n{tail}")

    new_findings = [
        f"{source}: {title} ({path})"
        for (source, title, path), count in after.findings.items()
        if count > before.findings.get((source, title, path), 0)
    ]

    if new_findings:
        problems.append("New static-analysis findings:\n" + "\n".join(sorted(new_findings)[:10]))

    return problems


def _bullets(header: str, items: list[str]) -> str:
    if not items:
        return ""

    return header + ":\n" + "\n".join(f"- {item}" for item in items)


async def _no_suite() -> None:
    return None


class FixEngine:
    """Generates, applies and verifies proposed fixes."""

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

    async def run(
        self,
        pr: PullRequest,
        plan: FixPlan,
        findings: list[Finding],
    ) -> FixProposal:
        settings = self._settings
        by_id = {finding.id: finding for finding in findings}
        notes: list[str] = []

        async with self._workspaces.open(
            pr.repo_full_name,
            pr.head_sha,
        ) as workspace:
            originals = self._read_originals(workspace, plan, notes)

            actions = [action for action in plan.actions if action.file_path in originals]

            if not actions:
                return FixProposal(
                    FixStatus.NOTHING_TO_FIX,
                    pr.head_sha,
                    summary="No file could be fixed automatically.",
                    notes=tuple(notes),
                )

            paths = [action.file_path for action in actions]

            targeted = tuple(finding_id for action in actions for finding_id in action.finding_ids)

            baseline = None

            if self._can_validate:
                baseline = await self._measure(
                    workspace,
                    paths,
                    install=True,
                )

                notes.extend(baseline.notes)

                if baseline.validation_errors:
                    notes.extend(
                        f"baseline validation failed: {error}"
                        for error in baseline.validation_errors
                    )
                    baseline = None

                elif baseline.suite_status is SuiteStatus.NO_TESTS and not self._analyzers:
                    notes.append(
                        "No tests were collected and no static analyzers "
                        "are enabled. Verification is unavailable."
                    )
                    baseline = None

            current = dict(originals)
            explanations: dict[str, str] = {}
            problems: str | None = None
            status = FixStatus.FAILED
            attempts = 0

            for attempt in range(1, settings.max_attempts + 1):
                attempts = attempt

                fixes = await self._generate(
                    pr,
                    actions,
                    by_id,
                    current,
                    problems,
                    notes,
                )

                if all(fix is None for fix in fixes.values()):
                    break

                explanations.update(
                    {path: fix.explanation for path, fix in fixes.items() if fix and fix.edits}
                )

                if not any(fix and fix.edits for fix in fixes.values()):
                    notes.append("The fixer proposed no changes.")

                    if current == originals:
                        status = FixStatus.NOTHING_TO_FIX

                    break

                proposed, rejections = self._apply(current, fixes)

                if rejections:
                    notes.append(_bullets("Some edits were rejected", rejections))

                if proposed == current:
                    problems = _bullets(
                        "These edits were rejected",
                        rejections,
                    )
                    continue

                changed = sum(
                    count_changed_lines(originals[path], proposed[path]) for path in proposed
                )

                if changed > settings.max_changed_lines:
                    problems = "Your edits changed too many lines. Make smaller, targeted edits."
                    continue

                for path, content in proposed.items():
                    if content != current[path]:
                        self._files.write(workspace, path, content)

                current = proposed

                if baseline is None:
                    notes.append(
                        "not validated: the proposed changes were applied "
                        "in the workspace, but no reliable baseline "
                        "validation was available."
                    )
                    status = FixStatus.UNVERIFIED
                    break

                after = await self._measure(
                    workspace,
                    paths,
                    install=False,
                )

                notes.extend(after.notes)

                if after.validation_errors:
                    notes.extend(
                        f"post-fix validation failed: {error}" for error in after.validation_errors
                    )
                    status = FixStatus.UNVERIFIED
                    break

                regressions = find_regressions(baseline, after)

                if not regressions:
                    notes.append("validated: no new failing tests or static-analysis findings")

                    if after.suite_status is SuiteStatus.NO_TESTS and self._analyzers:
                        notes.append(
                            "Verification was based on static analysis only; "
                            "no tests were collected."
                        )

                    status = FixStatus.VERIFIED
                    break

                problems = "\n\n".join(regressions)

                if rejections:
                    problems += "\n\n" + _bullets(
                        "These edits were rejected",
                        rejections,
                    )

        if status not in (
            FixStatus.VERIFIED,
            FixStatus.UNVERIFIED,
        ):
            if problems:
                notes.append(f"last problem: {problems[:300]}")

            return FixProposal(
                status,
                pr.head_sha,
                attempts=attempts,
                targeted_finding_ids=targeted,
                summary=("No fix could be verified." if status is FixStatus.FAILED else ""),
                notes=tuple(notes),
            )

        changes = tuple(
            FileChange(path, originals[path], current[path])
            for path in paths
            if current[path] != originals[path]
        )

        summary = "\n".join(
            f"- `{change.path}`: {explanations.get(change.path) or 'updated'}" for change in changes
        )

        return FixProposal(
            status,
            pr.head_sha,
            changes,
            attempts,
            targeted,
            summary,
            tuple(notes),
        )

    def _read_originals(
        self,
        workspace: Workspace,
        plan: FixPlan,
        notes: list[str],
    ) -> dict[str, str]:
        originals: dict[str, str] = {}

        for action in plan.actions:
            content = self._files.read(workspace, action.file_path)

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
        async def one(
            action: FixAction,
        ) -> tuple[str, FileFix | None]:
            targeted = [
                by_id[finding_id] for finding_id in action.finding_ids if finding_id in by_id
            ]

            try:
                fix = await self._fixer.propose(
                    pr,
                    action.file_path,
                    current[action.file_path],
                    targeted,
                    problems,
                )

            except LLMError as exc:
                logger.warning(
                    "Fixer failed for %s: %s",
                    action.file_path,
                    exc,
                )
                notes.append(f"{action.file_path}: the fixer failed ({exc})")
                return action.file_path, None

            except Exception as exc:
                logger.exception(
                    "Unexpected fixer error for %s",
                    action.file_path,
                )
                notes.append(
                    f"{action.file_path}: unexpected fixer error ({type(exc).__name__}: {exc})"
                )
                return action.file_path, None

            return action.file_path, fix

        return dict(await asyncio.gather(*(one(action) for action in actions)))

    @staticmethod
    def _apply(
        current: dict[str, str],
        fixes: dict[str, FileFix | None],
    ) -> tuple[dict[str, str], list[str]]:
        """Apply edits atomically per file, rejecting invalid edits."""

        proposed = dict(current)
        rejections: list[str] = []

        for path, fix in fixes.items():
            if fix is None or not fix.edits:
                continue

            text = proposed[path]
            rejected = False

            for edit in fix.edits:
                try:
                    text = apply_text_edit(
                        text,
                        edit.old_text,
                        edit.new_text,
                    )

                except EditRejectedError as exc:
                    rejections.append(f"{path}: {exc}")
                    rejected = True
                    break

            if rejected:
                continue

            error = python_syntax_error(path, text)

            if error:
                rejections.append(f"{path}: {error}; all edits to this file were discarded")
                continue

            proposed[path] = text

        return proposed, rejections

    async def _run_suite(
        self,
        workspace: Workspace,
        *,
        install: bool,
    ) -> SuiteResult | None:
        if self._suite_runner is None or not self._settings.run_tests:
            return None

        try:
            return await self._suite_runner.run(
                workspace,
                install_dependencies=install,
            )

        except Exception as exc:
            logger.exception("Test suite runner failed unexpectedly")

            message = f"Test suite runner failed unexpectedly: {type(exc).__name__}: {exc}"

            return SuiteResult(
                status=SuiteStatus.ERROR,
                validation_errors=(message,),
                notes=(message,),
            )

    async def _measure(
        self,
        workspace: Workspace,
        paths: list[str],
        *,
        install: bool,
    ) -> Measurement:
        outcome, suite = await asyncio.gather(
            run_analyzers(
                self._analyzers,
                workspace,
                paths,
            ),
            self._run_suite(
                workspace,
                install=install,
            ),
        )

        counts: dict[tuple[str, str, str], int] = {}

        for finding in outcome.findings:
            if SEVERITY_LEVEL[finding.severity] >= TRACKED_LEVEL:
                key = (
                    finding.source,
                    finding.title,
                    finding.file_path or "",
                )

                counts[key] = counts.get(key, 0) + 1

        notes = list(outcome.notes)
        validation_errors: list[str] = list(outcome.notes)

        if suite is not None:
            notes.extend(suite.notes)
            validation_errors.extend(suite.validation_errors)

            if suite.failures_truncated:
                validation_errors.append(
                    "The test failure list is incomplete; regression comparison is unreliable."
                )

            if suite.status in (
                SuiteStatus.ERROR,
                SuiteStatus.TIMED_OUT,
            ):
                validation_errors.append(f"Test validation ended with status '{suite.status}'.")

            if suite.status is SuiteStatus.FAILED:
                total_failures = suite.failed + suite.errors

                if total_failures == 0:
                    validation_errors.append(
                        "Pytest reported a failed run without parseable failure counts."
                    )

                elif len(suite.failures) < total_failures:
                    validation_errors.append(
                        "The test failure list does not contain all reported failures."
                    )

        return Measurement(
            findings=counts,
            failed_tests=failed_test_ids(suite),
            suite_status=suite.status if suite else None,
            output_tail=suite.output_tail if suite else "",
            notes=tuple(notes),
            validation_errors=tuple(dict.fromkeys(validation_errors)),
        )
