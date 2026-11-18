from collections import defaultdict
from dataclasses import dataclass


@dataclass
class _Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class TokenTracker:
    """Cumulative token usage per purpose. Cost and per-run attribution come with observability."""

    def __init__(self) -> None:
        self._by_purpose: dict[str, _Usage] = defaultdict(_Usage)

    def record(self, *, purpose: str, input_tokens: int, output_tokens: int) -> None:
        usage = self._by_purpose[purpose]
        usage.calls += 1
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens

    def snapshot(self) -> dict[str, dict]:
        by_purpose = {
            name: {
                "calls": u.calls,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
            }
            for name, u in self._by_purpose.items()
        }
        total = {
            "calls": sum(u["calls"] for u in by_purpose.values()),
            "input_tokens": sum(u["input_tokens"] for u in by_purpose.values()),
            "output_tokens": sum(u["output_tokens"] for u in by_purpose.values()),
        }
        return {"total": total, "by_purpose": by_purpose}
