from dataclasses import dataclass, field
from uuid import uuid4

from app.domain.enums import FindingCategory, Severity


@dataclass(frozen=True)
class Finding:
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    source: str  # which agent or analyzer produced it
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    suggestion: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
