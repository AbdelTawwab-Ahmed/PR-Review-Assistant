from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactReport:
    summary: str
    affected_components: tuple[str, ...] = ()
    breaking_changes: tuple[str, ...] = ()
    suggested_checks: tuple[str, ...] = ()