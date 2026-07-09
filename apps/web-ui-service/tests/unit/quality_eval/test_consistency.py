"""ConsistencyEvaluator / 加权评分 / ExecutabilityEvaluator 单元测试。"""

from __future__ import annotations

from app.services.quality_eval_service import (
    ConsistencyEvaluator,
    EvalScores,
    ExecutabilityEvaluator,
    GeneratedCase,
)


def _make_item():
    return __import__("tests.unit.quality_eval.conftest", fromlist=["make_item"]).make_item()


# ── ConsistencyEvaluator ──────────────────────────────────────

def test_consistency_identical_cases() -> None:
    """完全相同的用例 → 100 分。"""
    cases = [
        GeneratedCase(steps=[{}] * 3, assertions=[{}] * 2, page_codes=["a", "b"], scenario_types=["s1", "s2"]),
        GeneratedCase(steps=[{}] * 3, assertions=[{}] * 2, page_codes=["a", "b"], scenario_types=["s1", "s2"]),
    ]
    assert ConsistencyEvaluator.compute_consistency(cases) == 100.0


def test_consistency_different_cases() -> None:
    """不同的用例 → 分数低于满分。"""
    cases = [
        GeneratedCase(steps=[{}] * 5, assertions=[{}] * 4, page_codes=["a", "b", "c"], scenario_types=["s1", "s2", "s3"]),
        GeneratedCase(steps=[{}] * 2, assertions=[{}] * 1, page_codes=["a"], scenario_types=["s1"]),
    ]
    score = ConsistencyEvaluator.compute_consistency(cases)
    assert 50 < score < 100


def test_consistency_single_case() -> None:
    """单个 case → 100 分（无需比较）。"""
    assert ConsistencyEvaluator.compute_consistency([GeneratedCase()]) == 100.0


def test_consistency_empty() -> None:
    """空列表 → 100 分。"""
    assert ConsistencyEvaluator.compute_consistency([]) == 100.0


# ── Cosine Similarity ─────────────────────────────────────────

def test_cosine_sim_identical() -> None:
    assert ConsistencyEvaluator._cosine_sim([1, 2, 3], [1, 2, 3]) == 1.0


def test_cosine_sim_orthogonal() -> None:
    assert ConsistencyEvaluator._cosine_sim([1, 0, 0], [0, 1, 0]) == 0.0


def test_cosine_sim_zero_vector() -> None:
    assert ConsistencyEvaluator._cosine_sim([0, 0, 0], [1, 2, 3]) == 0.0


# ── EvalScores.compute_weighted ────────────────────────────────

def test_weighted_score_perfect() -> None:
    scores = EvalScores(
        coverage_score=100, assertion_score=100, executability_score=100,
        consistency_score=100, robustness_score=100, hallucination_score=100,
    )
    assert scores.compute_weighted() == 100.0


def test_weighted_score_all_zero() -> None:
    scores = EvalScores()
    assert scores.compute_weighted() == 0.0


def test_weighted_score_custom_weights() -> None:
    scores = EvalScores(coverage_score=100, assertion_score=50)
    result = scores.compute_weighted({"coverage": 0.5, "assertion_quality": 0.5})
    assert result == 75.0  # 100*0.5 + 50*0.5


# ── ExecutabilityEvaluator ────────────────────────────────────

def test_executability_perfect() -> None:
    evaluator = ExecutabilityEvaluator()
    generated = GeneratedCase(
        compilation_passed=True,
        gate_decision="PASS",
        execution_passed=True,
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.executability_score == 100.0


def test_executability_compile_failed() -> None:
    evaluator = ExecutabilityEvaluator()
    generated = GeneratedCase(
        compilation_passed=False,
        compilation_errors=["unknown action type"],
        gate_decision="REVIEW",
        execution_passed=True,
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.executability_score <= 65  # 0 compile + 15 gate + 50 exec


def test_executability_rejected() -> None:
    evaluator = ExecutabilityEvaluator()
    generated = GeneratedCase(
        compilation_passed=True,
        gate_decision="REJECT",
        execution_passed=False,
        execution_failed_step=3,
    )
    scores = evaluator.evaluate(_make_item(), generated)
    assert scores.executability_score <= 35  # 20 compile + 0 gate + max(0, 25-15)
