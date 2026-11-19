from dataclasses import dataclass

from app.application.fix_engine import FixEngine
from app.application.ports.analyzer_port import AnalyzerPort
from app.application.ports.github_port import GitHubPort
from app.application.ports.llm_port import LLMPort
from app.application.ports.sandbox_port import WorkspaceProvider
from app.domain.enums import Severity


@dataclass(frozen=True)
class WorkflowDeps:
    github: GitHubPort
    llm: LLMPort
    chunk_chars: int = 24000
    max_chunks: int = 8
    workspaces: WorkspaceProvider | None = None
    analyzers: tuple[AnalyzerPort, ...] = ()
    max_analyzed_files: int = 200
    fix_engine: FixEngine | None = None
    fix_min_severity: Severity = Severity.MEDIUM
    fix_max_files: int = 5

    @property
    def static_analysis_enabled(self) -> bool:
        return self.workspaces is not None and bool(self.analyzers)
