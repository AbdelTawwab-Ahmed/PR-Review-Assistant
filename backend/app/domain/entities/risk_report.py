from dataclasses import dataclass

from app.domain.enums import RiskLevel


@dataclass(frozen=True)
class RiskFactor:
    name: str
    points: int
    reason: str


@dataclass(frozen=True)
class RiskReport:
    score: int  # 0-100
    level: RiskLevel
    factors: tuple[RiskFactor, ...] = ()
