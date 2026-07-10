"""Unit tests for Layer Comparator — Sprint 2 Day 8."""
from __future__ import annotations

from app.models.api_test_models import (
    AssertionResult,
    ExecutionResult,
    UIAssertion,
    UIEvidence,
)
from runners.api_python.layer_comparator import (
    LayerComparison,
    LayerDivergence,
    compare_all,
    compare_layers,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _api_passed(name="login_success") -> ExecutionResult:
    return ExecutionResult(
        intent_name=name,
        status="passed",
        failure_layer=None,
        platform_error=False,
        assertions=[AssertionResult(type="status", expected=200, actual=200, passed=True)],
        evidence={"response": {"body": {"code": 200, "message": "操作成功"}}},
    )


def _api_failed(name="login_failed", failure_layer="business_rule") -> ExecutionResult:
    return ExecutionResult(
        intent_name=name,
        status="failed",
        failure_layer=failure_layer,
        platform_error=False,
        assertions=[AssertionResult(type="status", expected=200, actual=500, passed=False)],
        evidence={"response": {"body": {"code": 500, "message": "用户名或密码错误"}}},
    )


def _ui_passed(intent_name="login_success", target="home-btn") -> UIEvidence:
    return UIEvidence(
        case_id="case_001", intent_name=intent_name, status="passed",
        assertions=[UIAssertion(type="assert_visible", target=target, expected="首页可见", actual="首页可见")],
    )


def _ui_with_ai_hallucination() -> UIEvidence:
    return UIEvidence(
        case_id="case_002", intent_name="login_failed", status="passed",
        assertions=[UIAssertion(type="assert_text", target="login-submit-btn",
                                expected="请输入账号", actual="登录")],
    )


# ---------------------------------------------------------------------------
# Intent → API comparison
# ---------------------------------------------------------------------------

def test_intent_api_aligned():
    """Positive scenario + API passed → no divergence."""
    comp = compare_layers("login_success", "positive", api_result=_api_passed())
    assert not comp.has_divergences


def test_intent_api_positive_failed():
    """Positive scenario + API failed → divergence."""
    comp = compare_layers("login_success", "positive", api_result=_api_failed())
    assert comp.has_divergences
    assert any(d.direction == "intent_api" for d in comp.divergences)


def test_intent_api_network_error():
    """API network error → divergence."""
    api = ExecutionResult(intent_name="test", status="failed", failure_layer="network",
                          platform_error=False, evidence={"error": "timeout"})
    comp = compare_layers("test", "positive", api_result=api)
    assert any("连接" in d.description for d in comp.divergences)


def test_intent_api_platform_error():
    """Platform error → divergence."""
    api = ExecutionResult(intent_name="test", status="failed", platform_error=True,
                          platform_error_details="selftest FAIL")
    comp = compare_layers("test", "positive", api_result=api)
    assert any("平台" in d.description for d in comp.divergences)


# ---------------------------------------------------------------------------
# Intent → UI comparison
# ---------------------------------------------------------------------------

def test_intent_ui_aligned():
    """Positive scenario + UI passed + non-suspicious assertion → no UI divergence."""
    comp = compare_layers("login_success", "positive",
                          api_result=_api_passed(), ui_evidence=_ui_passed())
    intent_ui = comp.intent_ui_divergences
    assert len(intent_ui) == 0


def test_intent_ui_missing():
    """No UI evidence → no UI divergence (just no data)."""
    comp = compare_layers("login_success", "positive", ui_evidence=None)
    # No UI evidence means no UI divergence — not "missing", just "not provided"
    assert len(comp.intent_ui_divergences) == 0


def test_intent_ui_ai_hallucination():
    """UI assertion with AI-guessed text → divergence."""
    comp = compare_layers("login_failed", "negative",
                          api_result=_api_failed(), ui_evidence=_ui_with_ai_hallucination())
    # Should detect both: AI hallucination + wrong target (btn)
    assert any("AI推测" in d.description for d in comp.divergences)


def test_intent_ui_wrong_target():
    """assert_text on a button → divergence."""
    comp = compare_layers("login_failed", "negative",
                          api_result=_api_failed(), ui_evidence=_ui_with_ai_hallucination())
    assert any("按钮" in d.description for d in comp.divergences)


def test_intent_ui_negative_no_assertions():
    """Negative scenario UI passed without assertions → false positive risk."""
    ui = UIEvidence(case_id="c1", intent_name="login_failed", status="passed", assertions=[])
    comp = compare_layers("login_failed", "negative", api_result=_api_failed(), ui_evidence=ui)
    assert any("假通过" in d.description for d in comp.divergences)


# ---------------------------------------------------------------------------
# LayerComparison dataclass
# ---------------------------------------------------------------------------

def test_comparison_properties():
    comp = LayerComparison(
        intent_name="test",
        divergences=[
            LayerDivergence(direction="intent_api", description="api issue"),
            LayerDivergence(direction="intent_ui", description="ui issue"),
            LayerDivergence(direction="intent_ui", description="ui issue 2"),
        ],
    )
    assert comp.has_divergences
    assert len(comp.intent_api_divergences) == 1
    assert len(comp.intent_ui_divergences) == 2


def test_comparison_no_divergences():
    comp = LayerComparison(intent_name="clean")
    assert not comp.has_divergences
    assert len(comp.intent_api_divergences) == 0
    assert len(comp.intent_ui_divergences) == 0


# ---------------------------------------------------------------------------
# compare_all
# ---------------------------------------------------------------------------

def test_compare_all_batch():
    api_map = {
        "intent_a": _api_passed("intent_a"),
        "intent_b": _api_failed("intent_b"),
    }
    ui_map = {
        "intent_a": _ui_passed("intent_a"),
        "intent_b": None,
    }
    scenarios = {"intent_a": "positive", "intent_b": "negative"}

    results = compare_all(
        intent_names=["intent_a", "intent_b"],
        intent_scenarios=scenarios,
        api_results=api_map,
        ui_evidence_map=ui_map,
    )
    assert len(results) == 2
    assert results[0].intent_name == "intent_a"
    assert results[1].intent_name == "intent_b"
    # intent_b has API failure divergence
    assert results[1].has_divergences
