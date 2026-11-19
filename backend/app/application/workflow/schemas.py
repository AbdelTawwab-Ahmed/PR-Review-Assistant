from pydantic import BaseModel

from app.domain.enums import FindingCategory, Severity


# Strict-schema friendly: every field is required (nullable where needed), no constraints.
class FindingOut(BaseModel):
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    suggestion: str | None


class FindingsOut(BaseModel):
    findings: list[FindingOut]


class ImpactOut(BaseModel):
    summary: str
    affected_components: list[str]
    breaking_changes: list[str]
    suggested_checks: list[str]


class EditOut(BaseModel):
    old_text: str
    new_text: str


class FileFixOut(BaseModel):
    edits: list[EditOut]
    explanation: str
