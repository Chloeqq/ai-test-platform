"""Versioned zero-new-violations baseline storage."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from .ast_rules import (
    MAX_COMPLEXITY,
    MAX_FUNCTION_LINES,
    MAX_NESTING,
    MAX_PARAMETERS,
)
from .model import Violation, compare_violations
from .tool_rules import ToolVersions

SCHEMA_VERSION = 1


class BaselineError(RuntimeError):
    """Raised when a baseline is missing, stale, or attempts to grow."""


@dataclass(frozen=True, slots=True)
class Baseline:
    source_commit: str
    generated_at: str
    tools: ToolVersions
    violations: tuple[Violation, ...]

    @classmethod
    def load(cls, path: Path) -> Self:
        if not path.is_file():
            raise BaselineError(f"Missing quality baseline: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_schema(payload, path)
        tools = payload["tools"]
        return cls(
            source_commit=str(payload["source_commit"]),
            generated_at=str(payload["generated_at"]),
            tools=ToolVersions(
                python=str(tools["python"]),
                ruff=str(tools["ruff"]),
                mypy=str(tools["mypy"]),
            ),
            violations=tuple(
                Violation.from_dict(item) for item in payload["violations"]
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_commit": self.source_commit,
            "generated_at": self.generated_at,
            "tools": {
                "python": self.tools.python,
                "ruff": self.tools.ruff,
                "mypy": self.tools.mypy,
            },
            "thresholds": {
                "max_function_lines": MAX_FUNCTION_LINES,
                "max_complexity": MAX_COMPLEXITY,
                "max_parameters": MAX_PARAMETERS,
                "max_nesting": MAX_NESTING,
            },
            "summary": dict(sorted(violation_counts(self.violations).items())),
            "violations": [item.to_dict() for item in sorted(self.violations)],
        }


def create_baseline(
    root: Path,
    violations: list[Violation],
    tools: ToolVersions,
) -> Baseline:
    return Baseline(
        source_commit=_head_commit(root),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        tools=tools,
        violations=tuple(sorted(violations)),
    )


def write_baseline(
    path: Path,
    baseline: Baseline,
    *,
    existing: Baseline | None,
) -> None:
    if existing is not None:
        comparison = compare_violations(
            list(baseline.violations),
            list(existing.violations),
        )
        if comparison.new:
            rendered = "\n".join(item.render() for item in comparison.new)
            raise BaselineError(
                f"Baseline growth is forbidden. Fix these violations:\n{rendered}"
            )
    payload = baseline.to_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def violation_counts(
    violations: tuple[Violation, ...] | list[Violation],
) -> Counter[str]:
    return Counter(_category(item.rule) for item in violations)


def _category(rule: str) -> str:
    if rule.startswith("RUFF:"):
        return "ruff"
    if rule.startswith("MYPY:"):
        return "mypy"
    if rule.startswith("EQA"):
        return "custom_ast"
    return rule.lower()


def _head_commit(root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate_schema(payload: object, path: Path) -> None:
    if not isinstance(payload, dict):
        raise BaselineError(f"Invalid baseline object: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError(
            f"Unsupported baseline schema in {path}: {payload.get('schema_version')!r}"
        )
    required = {"source_commit", "generated_at", "tools", "violations"}
    missing = required.difference(payload)
    if missing:
        raise BaselineError(f"Baseline {path} is missing: {', '.join(sorted(missing))}")
