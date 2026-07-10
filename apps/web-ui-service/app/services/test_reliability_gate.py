"""Test Reliability Gate — Sprint 1 Day 4.

Validates TestIntent before execution to catch:
  1. Weak assertions (assert_url only in negative scenarios)
  2. Missing assertions (no executable checks)
  3. AI hallucination risk (expected values that look like guesses)
  4. False positive risk (negative scenarios with wrong assertion types)

Returns GateResult: PASS | REVIEW | REJECT with reasons.

Already validated on 24 real login cases:
  - 16 REJECT (false pass risk)
  - 7 PASS (trusted)
  - 1 REVIEW (needs human)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from shared_backend.type_utils import str_value


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Expected values that signal AI hallucination (the AI gave up)
_HALLUCINATION_SIGNALS = (
    "取决于业务",
    "大约",
    "未知",
)

# Negative scenarios need element-level assertions, not just URL checks
_WEAK_ASSERTION_TYPES = {"assert_url", "status"}  # status is weak if no json path

# Keywords that indicate the expected value is likely AI-guessed
# (Chinese error messages the AI couldn't have known)
_GUESSED_VALUE_SIGNALS = (
    "请输入账号",
    "请输入密码",
    "用户名长度",
    "密码不能包含",
    "账号已被锁定",
    "账号已被禁用",
)


# ---------------------------------------------------------------------------
# Gate Result
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of Test Reliability Gate check."""
    verdict: Literal["PASS", "REVIEW", "REJECT"] = "PASS"
    reasons: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.verdict == "REJECT"

    @property
    def needs_review(self) -> bool:
        return self.verdict in {"REVIEW", "REJECT"}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _rule_weak_assertions(
    scenario: str,
    assertions: list[dict[str, Any]],
) -> list[str]:
    """Check for weak assertions (assert_url only in negative/boundary scenarios).

    Negative/boundary scenarios need element-level validation (assert_text,
    assert_visible, json path), not just URL checks.
    """
    issues: list[str] = []
    if scenario not in {"negative", "boundary"}:
        return issues

    if not assertions:
        return issues

    # Check if ALL assertions are weak (status-only or url-only)
    all_weak = all(
        str_value(a.get("type", "")) in _WEAK_ASSERTION_TYPES
        for a in assertions
    )
    if all_weak:
        issues.append(
            f"弱断言风险：{scenario}场景仅有URL/status级别断言，"
            "缺少元素级验证(assert_text/assert_visible/json_path)。"
            "测试即使通过也不能证明业务行为被正确验证。"
        )
    return issues


def _rule_missing_assertions(
    assertions: list[dict[str, Any]],
) -> list[str]:
    """Check for zero assertions. A test without assertions is dead code."""
    if not assertions:
        return [
            "断言缺失：用例没有任何可执行断言，"
            "执行后无法验证任何业务结果。"
        ]
    return []


def _rule_ai_hallucination(
    assertions: list[dict[str, Any]],
) -> list[str]:
    """Check if expected values look like AI guesses."""
    issues: list[str] = []
    for i, a in enumerate(assertions):
        expected = str_value(a.get("expected", ""))
        if not expected:
            continue

        # Check for explicit "I don't know" signals
        for signal in _HALLUCINATION_SIGNALS:
            if signal in expected:
                issues.append(
                    f"AI幻觉风险(断言{i})：expected_value='{expected}'含模糊表述'{signal}'，"
                    "该值可能为AI推测，不代表被测系统真实行为。"
                )
                break

        # Check for guessed Chinese error messages
        for signal in _GUESSED_VALUE_SIGNALS:
            if signal in expected:
                issues.append(
                    f"AI幻觉风险(断言{i})：expected_value='{expected}'疑似推测文案，"
                    f"命中推测词'{signal}'。应用API Oracle校准。"
                )
                break

    return issues


def _rule_false_positive_risk(
    scenario: str,
    assertions: list[dict[str, Any]],
) -> list[str]:
    """Check for false positive risk in negative scenarios.

    A negative test that only checks URL/status may pass even if the
    system didn't actually validate the error condition.
    """
    issues: list[str] = []
    if scenario != "negative":
        return issues

    has_element_assertion = any(
        str_value(a.get("type", "")) == "json"
        and str_value(a.get("path", ""))
        for a in assertions
    )

    if not has_element_assertion:
        issues.append(
            "假通过风险：negative场景缺少JSON path断言来验证具体错误信息。"
            "仅靠status检查无法区分'系统正确拒绝'和'系统因其他原因失败'。"
        )
    return issues


# ---------------------------------------------------------------------------
# Gate entry point
# ---------------------------------------------------------------------------

def check_reliability(
    intent: Any,
) -> GateResult:
    """Run all reliability checks on a TestIntent.

    Args:
        intent: TestIntent or dict with name, scenario, assertions.

    Returns:
        GateResult with verdict (PASS/REVIEW/REJECT) and list of reasons.
    """
    scenario = str_value(getattr(intent, "scenario", "") or (intent.get("scenario") if isinstance(intent, dict) else ""))
    assertions = getattr(intent, "assertions", []) if hasattr(intent, "assertions") else (intent.get("assertions") if isinstance(intent, dict) else [])

    # Normalize assertions to dicts
    normalized: list[dict[str, Any]] = []
    for a in assertions:
        if isinstance(a, dict):
            normalized.append(a)
        elif hasattr(a, "type"):
            normalized.append({
                "type": getattr(a, "type", ""),
                "path": getattr(a, "path", None),
                "expected": getattr(a, "expected", None),
                "operator": getattr(a, "operator", "eq"),
            })
        else:
            normalized.append({"type": str(a)})

    all_reasons: list[str] = []
    all_reasons.extend(_rule_missing_assertions(normalized))
    all_reasons.extend(_rule_weak_assertions(scenario, normalized))
    all_reasons.extend(_rule_ai_hallucination(normalized))
    all_reasons.extend(_rule_false_positive_risk(scenario, normalized))

    if not all_reasons:
        return GateResult(verdict="PASS")

    # Missing assertions → REJECT (fatal)
    has_missing = any("断言缺失" in r for r in all_reasons)
    # AI hallucination → REJECT
    has_hallucination = any("AI幻觉" in r for r in all_reasons)

    if has_missing or has_hallucination:
        return GateResult(verdict="REJECT", reasons=all_reasons)

    # Weak assertions or false positive risk → REVIEW
    return GateResult(verdict="REVIEW", reasons=all_reasons)
