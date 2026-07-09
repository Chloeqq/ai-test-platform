"""HallucinationEvaluator 单元测试。"""

from __future__ import annotations

from app.services.quality_eval_service import HallucinationEvaluator, GeneratedCase


def _make_item(**kwargs):
    return __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item(**kwargs)


def test_no_hallucination() -> None:
    """所有引用都在预期范围内 → 满分。"""
    evaluator = HallucinationEvaluator()
    item = _make_item(expected_page_codes=["login", "dashboard"])
    generated = GeneratedCase(
        page_codes=["login", "dashboard"],
        steps=[],
    )
    scores = evaluator.evaluate(item, generated)
    assert scores.hallucination_score == 100.0
    assert len(scores.hallucination_flags) == 0


def test_fake_page_detection() -> None:
    """引用了预期之外的页面 → 标记假页面。"""
    evaluator = HallucinationEvaluator()
    item = _make_item(expected_page_codes=["login", "dashboard"])
    generated = GeneratedCase(
        page_codes=["login", "dashboard", "old_admin_panel"],  # old_admin_panel 不在预期中
        steps=[],
    )
    scores = evaluator.evaluate(item, generated)
    assert scores.hallucination_score < 100
    assert any("FAKE_PAGE" in f or "假页面" in f for f in scores.hallucination_flags)


def test_unverified_locator() -> None:
    """元素定位指向未知页面 → 标记未验证定位。"""
    evaluator = HallucinationEvaluator()
    item = _make_item(expected_page_codes=["login"])
    generated = GeneratedCase(
        page_codes=["login"],
        steps=[
            {"action": "click", "target": "element:unknown_page_btn"}  # 不在 login 页面中
        ],
    )
    scores = evaluator.evaluate(item, generated)
    assert any("未验证元素定位" in f for f in scores.hallucination_flags)


def test_unverified_locator_dedup() -> None:
    """多个未验证元素 → 只标记一次（flag code 去重）。"""
    evaluator = HallucinationEvaluator()
    item = _make_item(expected_page_codes=["login"])
    generated = GeneratedCase(
        page_codes=["login"],
        steps=[
            {"action": "click", "target": "element:btn_a"},
            {"action": "click", "target": "element:btn_b"},
            {"action": "click", "target": "element:btn_c"},
        ],
    )
    scores = evaluator.evaluate(item, generated)
    # 三个元素都未验证，但"未验证元素定位" flag 只会出现一次
    unverified_count = sum(1 for f in scores.hallucination_flags if "未验证元素定位" in f)
    assert unverified_count == 1


def test_known_issues_supplement() -> None:
    """从 known_issues 中识别幻觉标签。"""
    evaluator = HallucinationEvaluator()
    item = _make_item(
        expected_page_codes=["login"],
        known_issues=["假页面引用:old_page", "数据捏造:重复手机号"],
    )
    generated = GeneratedCase(page_codes=["login"], steps=[])
    scores = evaluator.evaluate(item, generated)
    assert len(scores.hallucination_flags) >= 2
