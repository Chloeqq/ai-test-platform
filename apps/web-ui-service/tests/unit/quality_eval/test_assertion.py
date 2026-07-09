"""AssertionQualityEvaluator 单元测试。"""

from __future__ import annotations

from app.services.quality_eval_service import AssertionQualityEvaluator, GeneratedCase


def _make_item():
    return __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item()


def test_all_strong_assertions() -> None:
    """全部是强断言 → 满分。"""
    evaluator = AssertionQualityEvaluator()
    generated = GeneratedCase(
        steps=[{"action": "click"}, {"action": "fill"}],
        assertions=[
            {"type": "url", "target": "/dashboard"},
            {"type": "visible", "target": "欢迎文本"},
            {"type": "text", "target": "登录成功"},
        ],
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.assertion_score == 100.0
    assert scores.assertion_detail["strong_assertions"] == 3
    assert scores.assertion_detail["weak_assertions"] == 0


def test_mixed_assertions() -> None:
    """强弱混合 → 分数低于满分。"""
    evaluator = AssertionQualityEvaluator()
    generated = GeneratedCase(
        steps=[{"action": "click"}],
        assertions=[
            {"type": "url", "target": "/dashboard"},       # strong
            {"type": "title", "target": "首页"},            # weak
        ],
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.assertion_score == 50.0  # 1/2 strong
    assert scores.assertion_detail["strong_assertions"] == 1
    assert scores.assertion_detail["weak_assertions"] == 1


def test_zero_assertions() -> None:
    """零断言 → 0 分。"""
    evaluator = AssertionQualityEvaluator()
    generated = GeneratedCase(assertions=[])
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.assertion_score == 0.0
    assert "zero_assertion_count" in scores.assertion_detail["issues"]


def test_weak_dominant_issue() -> None:
    """弱断言居多 → 标记 weak_assertion_dominant。"""
    evaluator = AssertionQualityEvaluator()
    generated = GeneratedCase(
        steps=[{"action": "click"}],
        assertions=[
            {"type": "title", "target": "首页"},
            {"type": "exists", "target": "按钮"},
            {"type": "visible", "target": "文本"},         # one strong
        ],
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert "weak_assertion_dominant" in scores.assertion_detail["issues"]


def test_gate_rule_hit_penalty() -> None:
    """命中 rule_003 或 rule_008 → 额外扣分。"""
    evaluator = AssertionQualityEvaluator()
    generated = GeneratedCase(
        steps=[{"action": "click"}],
        assertions=[{"type": "url", "target": "/dashboard"}],
        gate_rule_hits=["rule_003", "rule_008", "rule_009"],  # 3 个断言相关规则
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.assertion_score == 70.0  # 100 - 3*10
    assert scores.assertion_detail["gate_rule_hits"] == ["rule_003", "rule_008", "rule_009"]
