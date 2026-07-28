from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.ci.evie_ai_quality.ast_rules import scan_ast_rules
from scripts.ci.evie_ai_quality.baseline import (
    Baseline,
    BaselineError,
    write_baseline,
)
from scripts.ci.evie_ai_quality.model import Violation, compare_violations
from scripts.ci.evie_ai_quality.tool_rules import (
    ToolVersions,
    scan_format,
    scan_mypy,
    scan_ruff,
)


def test_compliant_service_has_no_custom_ast_violations(tmp_path: Path) -> None:
    source = """
from collections.abc import Callable

def build_value(value: str, clock: Callable[[], str]) -> str:
    return f"{value}:{clock()}"
"""
    assert _scan_source(tmp_path, "services", source) == []


def _long_function_source() -> str:
    statements = "\n".join(f"    value_{index} = {index}" for index in range(41))
    return f"def too_long() -> int:\n{statements}\n    return value_40\n"


def _complex_function_source() -> str:
    branches = "\n".join(
        f"    if value == {index}:\n        return {index}" for index in range(10)
    )
    return f"def complex_value(value: int) -> int:\n{branches}\n    return -1\n"


def _nested_function_source() -> str:
    return """
def nested(a: bool, b: bool, c: bool, d: bool) -> bool:
    if a:
        if b:
            if c:
                if d:
                    return True
    return False
"""


@pytest.mark.parametrize(
    ("source", "expected_rule"),
    [
        (
            "from datetime import datetime\n"
            "def current_time() -> object:\n"
            "    return datetime.now()\n",
            "EQA001",
        ),
        (_long_function_source(), "EQA002"),
        (
            "def overloaded(a: int, b: int, c: int, d: int, e: int, f: int) -> int:\n"
            "    return a + b + c + d + e + f\n",
            "EQA003",
        ),
        (_complex_function_source(), "EQA004"),
        (_nested_function_source(), "EQA005"),
        (
            "def allowed(principal: object) -> bool:\n"
            '    return principal.role == "admin"\n',
            "EQA006",
        ),
        ('review_status = "pending"\n', "EQA006"),
        (
            "def create(factory: object) -> object:\n"
            '    return factory(review_status="pending")\n',
            "EQA006",
        ),
        ('ERROR_CODE = "EVIE_SAMPLE_FAILURE"\n', "EQA007"),
        (
            "from typing import Any\n"
            "def convert(value: Any) -> str:\n"
            "    return str(value)\n",
            "EQA008",
        ),
        (
            "from app.services.evie_ai.example import Example\n",
            "EQA009",
        ),
        (
            "from app.services.execution_compiler import compile_case\n",
            "EQA010",
        ),
    ],
)
def test_each_custom_ast_violation_is_rejected(
    tmp_path: Path,
    source: str,
    expected_rule: str,
) -> None:
    layer = "repositories" if expected_rule in {"EQA007", "EQA009"} else "services"
    violations = _scan_source(tmp_path, layer, source)
    assert expected_rule in {item.rule for item in violations}


def test_ruff_and_format_samples_fail_with_stable_rules(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.py"
    path.write_text("import os\n\nvalue={1:2}\n", encoding="utf-8")

    ruff = scan_ruff(tmp_path, [path], python_bin=sys.executable)
    formatting = scan_format(tmp_path, [path], python_bin=sys.executable)

    assert "RUFF:F401" in {item.rule for item in ruff}
    assert [item.rule for item in formatting] == ["FORMAT"]


def test_compliant_ruff_and_format_sample_passes(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("VALUE = {1: 2}\n", encoding="utf-8")

    assert scan_ruff(tmp_path, [path], python_bin=sys.executable) == []
    assert scan_format(tmp_path, [path], python_bin=sys.executable) == []


def test_mypy_sample_fails_with_stable_rule(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text('value: int = "wrong"\n', encoding="utf-8")

    violations = scan_mypy(
        tmp_path,
        ("sample.py",),
        python_bin=sys.executable,
    )

    assert "MYPY:assignment" in {item.rule for item in violations}


def test_historical_violation_does_not_block_when_line_moves() -> None:
    baseline = [_violation(line=10)]
    current = [_violation(line=25)]

    assert compare_violations(current, baseline).passed


def test_new_violation_blocks() -> None:
    baseline = [_violation(line=10)]
    current = [*baseline, _violation(rule="EQA002", symbol="new_function")]

    comparison = compare_violations(current, baseline)

    assert len(comparison.new) == 1
    assert not comparison.passed


def test_resolved_violation_requires_baseline_shrink() -> None:
    comparison = compare_violations([], [_violation()])

    assert len(comparison.resolved) == 1
    assert not comparison.passed


def test_baseline_writer_rejects_growth(tmp_path: Path) -> None:
    existing = _baseline((_violation(),))
    growing = _baseline(
        (_violation(), _violation(rule="EQA002", symbol="new_function"))
    )

    with pytest.raises(BaselineError, match="Baseline growth is forbidden"):
        write_baseline(tmp_path / "baseline.json", growing, existing=existing)


def test_violation_output_contains_location_rule_and_fix() -> None:
    rendered = _violation().render()

    assert rendered.startswith("sample.py:10: EQA001:")
    assert "| fix:" in rendered


def _scan_source(tmp_path: Path, layer: str, source: str) -> list[Violation]:
    path = (
        tmp_path / "apps" / "web-ui-service" / "app" / layer / "evie_ai" / "sample.py"
    )
    path.parent.mkdir(parents=True)
    path.write_text(source.strip() + "\n", encoding="utf-8")
    return scan_ast_rules(tmp_path, [path])


def _violation(
    *,
    rule: str = "EQA001",
    line: int = 10,
    symbol: str = "sample",
) -> Violation:
    return Violation(
        rule=rule,
        path="sample.py",
        line=line,
        message="sample violation",
        fix="fix the sample",
        symbol=symbol,
    )


def _baseline(violations: tuple[Violation, ...]) -> Baseline:
    return Baseline(
        source_commit="0" * 40,
        generated_at="2026-07-28T00:00:00+00:00",
        tools=ToolVersions(
            python="Python 3.13.2",
            ruff="ruff 0.15.9",
            mypy="mypy 1.20.0",
        ),
        violations=violations,
    )
