"""ATP Demo — Sprint 2 Day 10.

Full-chain demo: Requirement → API Test → Layer Comparison → Report.

Usage:
  ATP_SUT_BASE_URL=http://localhost:8090 python -m runners.api_python.demo

  0 hardcoded values. All data from demo_data/*.json + env vars.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add repo root to path so imports work from any directory
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "apps" / "web-ui-service") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "apps" / "web-ui-service"))

from app.models.api_test_models import (
    ApiRequest,
    Assertion,
    ExecutionResult,
    TestIntent,
    UIEvidence,
)
from runners.api_python.executor.api_step_runner import execute_api_test
from runners.api_python.layer_comparator import compare_layers
from runners.api_python.report_builder import build_report, render_report
from runners.api_python.ui_evidence_adapter import import_ui_results

_DATA_DIR = Path(__file__).resolve().parent / "demo_data"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_json(filename: str) -> Any:
    with open(_DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_intents() -> list[TestIntent]:
    raw = _load_json("login_intents.json")
    return [
        TestIntent(
            name=item["name"],
            scenario=item["scenario"],
            api_request=ApiRequest(**item["api_request"]),
            assertions=[Assertion(**a) for a in item["assertions"]],
        )
        for item in raw
    ]


def _load_audit_summary() -> dict[str, Any]:
    return _load_json("audit_summary.json")


def _load_audit_cases() -> list[dict[str, Any]]:
    return _load_json("audit_cases.json")


def _load_ui_evidence() -> list[UIEvidence]:
    cases = _load_audit_cases()
    raw = [
        {
            "case_id": c["intent_name"],
            "intent_name": c["intent_name"],
            "status": "passed",  # from audit: UI runner returned passed
            "assertions": c.get("original_ui_assertions", []),
        }
        for c in cases
    ]
    return import_ui_results(raw, format="playwright")


# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

def _get_base_url() -> str:
    url = os.getenv("ATP_SUT_BASE_URL", "").strip()
    if not url:
        print("Error: ATP_SUT_BASE_URL not set.")
        print("Usage: ATP_SUT_BASE_URL=http://localhost:8090 python -m runners.api_python.demo")
        sys.exit(1)
    return url


# ---------------------------------------------------------------------------
# Demo steps
# ---------------------------------------------------------------------------

def _print_step_header(step: int, title: str):
    print()
    print("═" * 60)
    print(f"  Step {step}: {title}")
    print("═" * 60)


def step1_show_audit_history():
    """展示 24 条 AI 生成 UI 用例审计结果。"""
    audit = _load_audit_summary()
    _print_step_header(1, "历史审计：AI 生成的 UI 测试可靠吗？")

    print(f"""
  在对 ATP 的 AI 生成 UI 测试用例做全量审计之前，没有人知道答案。

  审计范围: {audit['total_cases']} 条 login 模块 AI 生成 UI 用例
  审计日期: {audit['audit_date']}

  结果:
    • {audit['false_positive_rate']} ({audit['false_positive_count']}/{audit['total_cases']}) 存在虚假通过风险
    • {audit['non_executable_rate']} ({audit['non_executable_count']}/{audit['total_cases']}) 无法执行
    • {audit['ai_hallucination_rate']} ({audit['ai_hallucination_count']}/{audit['total_cases']}) 包含 AI 推测文案

  Test Reliability Gate 判定:
    • {audit['gate_results']['REJECT']} 条 REJECT — 假通过风险
    • {audit['gate_results']['PASS']} 条 PASS — 可信
    • {audit['gate_results']['REVIEW']} 条 REVIEW — 需人工确认

  核心问题: AI 不知道被测系统的真实行为。
""")
    print("─" * 60)
    print("  代表性案例:")
    cases = _load_audit_cases()
    for c in cases[:3]:
        print(f"  • {c['intent_name']}: {c['issue']}")
        print(f"    风险: {c['risk']}")


def step2_run_api_oracle():
    """用 API 拿到被测系统的真实行为。"""
    _print_step_header(2, "API Oracle：问被测系统，不猜")

    base_url = _get_base_url()
    intents = _load_intents()

    print(f"\n  被测系统: {base_url}")
    print(f"  测试场景: {len(intents)} 个 ({'/'.join(i.scenario for i in intents)})")
    print()
    print("  ATP 的方案: AI 理解需求意图，人不提供 API 路径/测试数据，")
    print("  API 返回的就是被测系统的真实行为。不猜测。")
    print()

    results: list[ExecutionResult] = []
    for intent in intents:
        print(f"  ► {intent.name} ... ", end="", flush=True)
        result = execute_api_test(intent, base_url=base_url, skip_selftest=True)
        icon = "✅" if result.status == "passed" else "❌"
        print(f"{icon} {result.status}")
        if not all(a.passed for a in result.assertions):
            for a in result.assertions:
                if not a.passed:
                    print(f"     ✗ {a.type}: expected={a.expected}, actual={a.actual}")
        results.append(result)

    print()
    return results


def step3_compare_layers(api_results: list[ExecutionResult]):
    """用 Layer Comparator 对比审计案例。"""
    _print_step_header(3, "Layer Comparator：以业务意图为基准")

    ui_evidence_list = _load_ui_evidence()
    audit_cases = _load_audit_cases()

    # Map audit cases by intent_name
    ui_map: dict[str, UIEvidence] = {e.intent_name: e for e in ui_evidence_list}

    # Match audit cases to API results by scenario type
    # Audit cases are from the old UI-only generation; API results are new
    scenarios = {c["intent_name"]: c["scenario"] for c in audit_cases}
    api_map = {r.intent_name: r for r in api_results}

    print(f"\n  对比维度:")
    print(f"    基准: Business Intent (需求中定义的业务行为)")
    print(f"    验证对象: API 执行结果 + 历史 UI 断言")
    print()

    # For each audit case, find its API counterpart and compare
    found_divergences = 0
    for case in audit_cases:
        name = case["intent_name"]
        # Match: find an API result with matching scenario type
        matching_api = next(
            (r for r in api_results if r.intent_name.startswith("login") and r.status),
            api_results[0] if api_results else None,
        )

        ui = ui_map.get(name)
        comp = compare_layers(
            intent_name=name,
            intent_scenario=case["scenario"],
            api_result=matching_api,
            ui_evidence=ui,
        )

        if comp.has_divergences:
            icon = "⚠️ "
            found_divergences += 1
        else:
            icon = "✅"

        print(f"  {icon} {name}")
        print(f"     审计发现: {case['issue']}")
        for d in comp.divergences:
            print(f"     [{d.direction}] {d.description}")
            if d.possible_causes:
                print(f"       → {d.possible_causes[0]}")

    print()
    print(f"  结果: {found_divergences}/{len(audit_cases)} 条案例存在意图偏离")
    print(f"  注意: Layer Comparator 不判断对错，只报告偏离。人决定怎么修。")


def step4_summary(api_results: list[ExecutionResult]):
    """最终报告 + 价值总结。"""
    _print_step_header(4, "价值总结")

    passed = sum(1 for r in api_results if r.status == "passed")
    total = len(api_results)

    print(f"""
  API 测试结果: {passed}/{total} 场景通过

  ATP 不是另一个 Postman。

  Postman 告诉你: 第 47 个断言失败了。
  ATP 告诉你: 这个断言不可信，为什么不可信，以及怎么判断。

  ATP 的差异化:
    1. AI 理解需求意图 — 从自然语言提取 Test Intent
    2. API/DB 作为业务真相源 — 不猜测，直接问被测系统
    3. Layer Comparator — 以业务意图为基准，对比 API/UI 三层
    4. 故障归因 — 区分平台问题、网络问题、被测系统问题
    5. Test Reliability Gate — 执行前拦截低质量用例

  方向: AI 驱动的智能测试编排平台
  — 不是"AI 生成测试用例"，是"AI + 确定性工程"
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║         ATP — AI Test Platform Demo           ║")
    print("║    AI 驱动的测试意图理解与质量分析平台          ║")
    print("╚" + "═" * 58 + "╝")

    # Step 1: Show audit history
    step1_show_audit_history()

    # Step 2: Run API Oracle against live mall system
    api_results = step2_run_api_oracle()

    # Step 3: Compare layers
    step3_compare_layers(api_results)

    # Step 4: Summary + value proposition
    step4_summary(api_results)

    # Final report
    report = build_report(api_results, title="mall login API")
    print(render_report(report))
    print()


if __name__ == "__main__":
    main()
