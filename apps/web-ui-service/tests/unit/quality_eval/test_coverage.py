"""CoverageEvaluator 单元测试。"""

from __future__ import annotations

from app.services.quality_eval_service import CoverageEvaluator, GeneratedCase


def test_coverage_full_match() -> None:
    """全部预期场景都被覆盖 → 100 分 + extra bonus。"""
    evaluator = CoverageEvaluator()
    item = __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(
        expected_coverage=["登录成功", "密码错误", "验证码过期"],
    )
    generated = GeneratedCase(scenario_types=["登录成功", "密码错误", "验证码过期"])

    scores = evaluator.evaluate(item, generated)
    assert scores.coverage_score >= 90  # 90 base + bonus for extra
    assert scores.coverage_detail["coverage_rate"] == 1.0
    assert len(scores.coverage_detail["missed_scenarios"]) == 0


def test_coverage_partial_match() -> None:
    """只覆盖部分场景 → 分数居中。"""
    evaluator = CoverageEvaluator()
    item = __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(
        expected_coverage=["登录成功", "密码错误", "验证码过期", "账号锁定", "记住密码"],
    )
    generated = GeneratedCase(scenario_types=["登录成功", "密码错误"])

    scores = evaluator.evaluate(item, generated)
    assert 30 < scores.coverage_score < 70
    assert scores.coverage_detail["coverage_rate"] == 0.4
    assert len(scores.coverage_detail["missed_scenarios"]) == 3


def test_coverage_no_match() -> None:
    """完全不匹配 → 低分。"""
    evaluator = CoverageEvaluator()
    item = __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(
        expected_coverage=["登录成功", "密码错误"],
    )
    generated = GeneratedCase(scenario_types=["商品搜索", "购物车结算"])

    scores = evaluator.evaluate(item, generated)
    assert scores.coverage_score <= 20
    assert scores.coverage_detail["coverage_rate"] == 0.0


def test_coverage_extra_scenario_bonus() -> None:
    """AI 自主发现额外场景 → 加 bonus 分。"""
    evaluator = CoverageEvaluator()
    item = __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(
        expected_coverage=["登录成功"],
    )
    generated = GeneratedCase(scenario_types=["登录成功", "验证码安全校验", "异地登录检测"])

    scores = evaluator.evaluate(item, generated)
    assert scores.coverage_score > 90  # 90 base + bonus
    assert len(scores.coverage_detail["extra_scenarios"]) == 2


def test_coverage_empty_expected() -> None:
    """未定义预期覆盖 → 返回满分 100（不做评判）。"""
    evaluator = CoverageEvaluator()
    item = __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(
        expected_coverage=[],
    )
    generated = GeneratedCase(scenario_types=["登录成功"])

    scores = evaluator.evaluate(item, generated)
    assert scores.coverage_score == 100.0


def test_fuzzy_match_contains() -> None:
    """模糊匹配：包含关系。"""
    assert CoverageEvaluator._fuzzy_match("登录成功", "用户输入正确密码后登录成功") is True
    assert CoverageEvaluator._fuzzy_match("商品搜索", "购物车结算") is False


def test_fuzzy_match_similar() -> None:
    """模糊匹配：高相似度文本。"""
    assert CoverageEvaluator._fuzzy_match("手机验证码登录", "手机号验证码登录") is True
