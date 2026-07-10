"""Layer Comparator — Sprint 2 Day 8.

Compares Business Intent (benchmark) against API and UI results,
reporting divergences without judging which layer is "correct".

Three-layer model:
  Business Intent  ← benchmark ("what should happen")
       │
  ┌────┴────┐
  ▼         ▼
API Result  UI Result
(actual)    (observed)

Returns LayerComparison with divergences for human judgment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.api_test_models import ExecutionResult, UIEvidence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LayerDivergence:
    """A single divergence between intent and actual result."""
    direction: str
    # "intent_api" — API result doesn't match business intent
    # "intent_ui"  — UI result doesn't match business intent

    intent_expected: str = ""
    # What the business intent expected (human-readable)

    actual_value: str = ""
    # What was actually observed

    actual_source: str = ""
    # "api" | "ui"

    description: str = ""
    # Human-readable description of the divergence

    possible_causes: list[str] = field(default_factory=list)
    # [A) ..., B) ..., C) ...]

    requires_human: bool = True


@dataclass
class LayerComparison:
    """Result of comparing Business Intent against API and UI."""
    intent_name: str = ""
    divergences: list[LayerDivergence] = field(default_factory=list)

    @property
    def has_divergences(self) -> bool:
        return len(self.divergences) > 0

    @property
    def intent_api_divergences(self) -> list[LayerDivergence]:
        return [d for d in self.divergences if d.direction == "intent_api"]

    @property
    def intent_ui_divergences(self) -> list[LayerDivergence]:
        return [d for d in self.divergences if d.direction == "intent_ui"]


# ---------------------------------------------------------------------------
# Intent → API comparison
# ---------------------------------------------------------------------------

def _compare_intent_api(
    intent_name: str,
    intent_scenario: str,
    api_result: ExecutionResult,
) -> list[LayerDivergence]:
    """Compare Business Intent against API execution result."""
    divergences: list[LayerDivergence] = []

    # Check: did the API fail when it shouldn't have?
    if intent_scenario == "positive" and api_result.status == "failed":
        divergences.append(LayerDivergence(
            direction="intent_api",
            intent_expected=f"业务意图期望 {intent_name} 成功",
            actual_value=f"API 执行失败: failure_layer={api_result.failure_layer}",
            actual_source="api",
            description=f"正向场景 {intent_name} 的 API 验证失败",
            possible_causes=[
                "A) 被测系统存在 Bug",
                "B) API 请求参数配置错误",
                "C) 网络或环境问题",
            ],
        ))

    # Check: did the API succeed when it should have failed?
    if intent_scenario == "negative" and api_result.status == "passed":
        # For negative scenarios, the API returning 200 is expected (mall behavior)
        # So "passed" means the assertions matched. But if the assertions expected
        # failure (e.g., code=500) and got it, that's correct.
        # We only flag if the API result seems suspicious.
        pass  # Negative scenario with API passing assertions is normal for mall

    # Check: any individual assertion failures
    failed_assertions = [a for a in api_result.assertions if not a.passed]
    for fa in failed_assertions:
        divergences.append(LayerDivergence(
            direction="intent_api",
            intent_expected=f"断言: {fa.type} {fa.path or ''} = {fa.expected}",
            actual_value=str(fa.actual),
            actual_source="api",
            description=f"API 断言失败: 期望 {fa.expected}, 实际 {fa.actual}",
            possible_causes=[
                "A) 被测系统行为与预期不符",
                "B) 断言期望值配置错误",
                "C) 被测系统接口已变更",
            ],
        ))

    # Check: platform/network failures
    if api_result.platform_error:
        divergences.append(LayerDivergence(
            direction="intent_api",
            intent_expected="平台正常运行",
            actual_value=f"平台异常: {api_result.platform_error_details}",
            actual_source="api",
            description=f"ATP 平台自身故障，API 测试结果不可信",
            possible_causes=[
                "A) ATP HTTP Client 故障",
                "B) 自检端点不可达",
                "C) 网络配置问题",
            ],
        ))

    if api_result.failure_layer == "network":
        divergences.append(LayerDivergence(
            direction="intent_api",
            intent_expected="被测系统可达",
            actual_value=f"网络不可达: {api_result.evidence.get('error', 'unknown')}",
            actual_source="api",
            description=f"无法连接被测系统",
            possible_causes=[
                "A) 被测系统未启动",
                "B) 网络配置错误",
                "C) 防火墙/安全组拦截",
            ],
        ))

    return divergences


# ---------------------------------------------------------------------------
# Intent → UI comparison
# ---------------------------------------------------------------------------

def _compare_intent_ui(
    intent_name: str,
    intent_scenario: str,
    api_result: ExecutionResult,
    ui_evidence: UIEvidence | None,
) -> list[LayerDivergence]:
    """Compare Business Intent against UI test result."""
    divergences: list[LayerDivergence] = []

    if ui_evidence is None:
        return divergences  # No UI data → no divergence to report

    # Check: UI status mismatch with intent
    if intent_scenario == "positive" and ui_evidence.status == "failed":
        divergences.append(LayerDivergence(
            direction="intent_ui",
            intent_expected=f"正向场景 UI 测试应通过",
            actual_value=f"UI 测试失败: status={ui_evidence.status}",
            actual_source="ui",
            description=f"正向场景 {intent_name} 的 UI 测试失败",
            possible_causes=[
                "A) 被测系统 UI 存在 Bug",
                "B) UI 断言配置错误",
                "C) 页面元素定位失败",
            ],
        ))

    # Check: negative scenarios where UI passed suspiciously
    if intent_scenario == "negative" and ui_evidence.status == "passed":
        # For negative scenarios, UI passing could mean:
        # - The error message was displayed correctly → legitimate pass
        # - The test has no real assertions → false positive
        has_assertions = len(ui_evidence.assertions) > 0
        if not has_assertions:
            divergences.append(LayerDivergence(
                direction="intent_ui",
                intent_expected=f"负向场景应有可验证的 UI 断言",
                actual_value="UI 测试通过但无断言",
                actual_source="ui",
                description=f"负向场景 {intent_name} UI 测试通过但没有断言，可能是假通过",
                possible_causes=[
                    "A) UI 测试缺少有效断言",
                    "B) 被测系统未做校验但测试碰巧通过",
                    "C) 断言被静默跳过",
                ],
            ))

    # Compare UI assertions with API actual values
    for ua in ui_evidence.assertions:
        if not ua.expected:
            continue

        # Check if UI expected value looks like an AI hallucination
        hallucination_signals = ("请输入", "请输出", "长度至少", "不能超过", "不能包含")
        is_suspicious = any(s in ua.expected for s in hallucination_signals)

        if is_suspicious:
            # Try to find corresponding API value
            api_messages = _extract_api_message(api_result)
            divergences.append(LayerDivergence(
                direction="intent_ui",
                intent_expected=f"UI 断言值应反映真实系统行为",
                actual_value=f"UI 断言期望 '{ua.expected}' (疑似AI推测)",
                actual_source="ui",
                description=(
                    f"UI 断言期望值 '{ua.expected}' 包含疑似AI推测的文案。"
                    f"API 实际返回: {api_messages}"
                ),
                possible_causes=[
                    "A) AI 推测了错误文案（应从 API 获取真实值）",
                    "B) 被测系统 UI 文案确实为 " + ua.expected,
                    "C) 被测系统 UI 文案已变更",
                ],
            ))

        # Check if assertion target looks wrong
        if ua.type == "assert_text" and ua.target.endswith("-btn"):
            divergences.append(LayerDivergence(
                direction="intent_ui",
                intent_expected="断言目标应为错误/消息展示元素",
                actual_value=f"断言目标为按钮元素: {ua.target}",
                actual_source="ui",
                description=f"UI 断言 assert_text 的目标 {ua.target} 是按钮元素，"
                            f"错误提示通常不会出现在按钮文本中",
                possible_causes=[
                    "A) 断言目标配置错误（应指向 toast/error 元素）",
                    "B) 被测系统确实在按钮上显示错误信息",
                    "C) element role 标注缺失",
                ],
            ))

    return divergences


def _extract_api_message(api_result: ExecutionResult) -> str:
    """Extract human-readable message from API result."""
    evidence = api_result.evidence
    if isinstance(evidence, dict):
        response = evidence.get("response", {})
        if isinstance(response, dict):
            body = response.get("body", {})
            if isinstance(body, dict):
                msg = body.get("message", "")
                code = body.get("code", "")
                if msg:
                    return f"code={code}, message='{msg}'"
    return "无 API 响应数据"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compare_layers(
    intent_name: str,
    intent_scenario: str,
    api_result: ExecutionResult | None = None,
    ui_evidence: UIEvidence | None = None,
) -> LayerComparison:
    """Compare Business Intent against API and UI results.

    This is the main public API. It does NOT judge which layer is correct —
    it only reports divergences for human judgment.

    Args:
        intent_name: Name of the business intent (e.g. "login_success").
        intent_scenario: "positive" | "negative" | "boundary".
        api_result: API execution result (None if API test not run).
        ui_evidence: UI test result (None if no UI test available).

    Returns:
        LayerComparison with list of LayerDivergence items.
    """
    comparison = LayerComparison(intent_name=intent_name)

    if api_result is not None:
        comparison.divergences.extend(
            _compare_intent_api(intent_name, intent_scenario, api_result)
        )

    comparison.divergences.extend(
        _compare_intent_ui(intent_name, intent_scenario, api_result or ExecutionResult(), ui_evidence)
    )

    return comparison


def compare_all(
    intent_names: list[str],
    intent_scenarios: dict[str, str],
    api_results: dict[str, ExecutionResult],
    ui_evidence_map: dict[str, UIEvidence | None],
) -> list[LayerComparison]:
    """Compare all intents and return a list of LayerComparison results.

    Convenience for batch comparison.
    """
    return [
        compare_layers(
            intent_name=name,
            intent_scenario=intent_scenarios.get(name, "positive"),
            api_result=api_results.get(name),
            ui_evidence=ui_evidence_map.get(name),
        )
        for name in intent_names
    ]
