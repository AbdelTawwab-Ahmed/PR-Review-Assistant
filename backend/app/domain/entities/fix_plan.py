from dataclasses import dataclass


@dataclass(frozen=True)
class FixAction:
    file_path: str
    description: str
    finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FixPlan:
    actions: tuple[FixAction, ...] = ()
    rationale: str = ""
    attempt: int = 1

    @property
    def is_empty(self) -> bool:
        return not self.actions
