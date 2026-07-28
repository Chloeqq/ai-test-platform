"""Stable violation and baseline comparison models."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, order=True, slots=True)
class Violation:
    """A stable, reader-facing quality violation."""

    rule: str
    path: str
    line: int
    message: str
    fix: str
    symbol: str = ""

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.rule, self.path, self.symbol, self.message)

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.rule}: {self.message} | fix: {self.fix}"

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "fix": self.fix,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> Self:
        return cls(
            rule=str(payload["rule"]),
            path=str(payload["path"]),
            line=_required_int(payload["line"], field="line"),
            message=str(payload["message"]),
            fix=str(payload["fix"]),
            symbol=str(payload.get("symbol", "")),
        )


@dataclass(frozen=True, slots=True)
class Comparison:
    """Difference between current and accepted baseline violations."""

    new: tuple[Violation, ...]
    resolved: tuple[Violation, ...]

    @property
    def passed(self) -> bool:
        return not self.new and not self.resolved


def compare_violations(
    current: list[Violation],
    baseline: list[Violation],
) -> Comparison:
    """Compare violation multisets while ignoring line-number drift."""

    current_counts = Counter(item.key for item in current)
    baseline_counts = Counter(item.key for item in baseline)
    new = _expand_difference(current, current_counts - baseline_counts)
    resolved = _expand_difference(baseline, baseline_counts - current_counts)
    return Comparison(new=tuple(new), resolved=tuple(resolved))


def _expand_difference(
    source: list[Violation],
    difference: Counter[tuple[str, str, str, str]],
) -> list[Violation]:
    remaining = difference.copy()
    selected: list[Violation] = []
    for item in sorted(source):
        if remaining[item.key] < 1:
            continue
        selected.append(item)
        remaining[item.key] -= 1
    return selected


def _required_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value
