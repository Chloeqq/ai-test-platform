"""ScoreEngine — 质量评分引擎。

评分维度：
  Data Completeness       30
  Assertion Quality       30
  Semantic Consistency    20
  Dependency Readiness    10
  Page Object Consistency 10
  总分                    100

阈值：
  ≥ 95  → PASS
  80-94 → REVIEW
  < 80  → REJECT
"""

from __future__ import annotations

from shared_backend.quality_gate import (
    CaseScore,
    RuleCategory,
    RuleResult,
)

# 维度权重
_CATEGORY_WEIGHTS: dict[RuleCategory, int] = {
    RuleCategory.DATA: 30,
    RuleCategory.ASSERTION: 30,
    RuleCategory.SEMANTIC: 20,
    RuleCategory.DEPENDENCY: 10,
    RuleCategory.PAGE_OBJECT: 10,
    RuleCategory.STEP: 0,            # 不单独计分，融入语义
    RuleCategory.REQUIREMENT: 0,     # 不单独计分
    RuleCategory.AI_GENERATION: 0,   # 不单独计分
}

# 默认满分
_DEFAULT_SCORES: dict[str, int] = {
    "data": 30,
    "assertion": 30,
    "semantic": 20,
    "dependency": 10,
    "page_object": 10,
}

# 扣分规则: Severity → 扣掉的比例
_PENALTY: dict[str, float] = {
    "fatal": 1.0,     # FATAL → 该维度归零
    "error": 0.5,     # ERROR → 扣 50%
    "warning": 0.25,  # WARNING → 扣 25%
    "info": 0.0,      # INFO → 不扣分
}


class ScoreEngine:
    """根据 RuleResult 列表计算 CaseScore。"""

    def calculate(self, results: list[RuleResult]) -> CaseScore:
        scores = dict(_DEFAULT_SCORES)

        # 按 category 分组失败结果
        for result in results:
            if result.passed:
                continue
            category_key = self._category_key(result.category)
            if category_key not in scores:
                continue
            penalty_ratio = _PENALTY.get(result.severity.value, 0.0)
            max_penalty = scores[category_key]
            deduction = int(max_penalty * penalty_ratio)
            scores[category_key] = max(0, scores[category_key] - deduction)

        total = sum(scores.values())
        return CaseScore(
            total_score=total,
            data_score=scores.get("data", 0),
            assertion_score=scores.get("assertion", 0),
            semantic_score=scores.get("semantic", 0),
            dependency_score=scores.get("dependency", 0),
            page_object_score=scores.get("page_object", 0),
        )

    @staticmethod
    def _category_key(category: RuleCategory) -> str:
        mapping = {
            RuleCategory.DATA: "data",
            RuleCategory.ASSERTION: "assertion",
            RuleCategory.SEMANTIC: "semantic",
            RuleCategory.DEPENDENCY: "dependency",
            RuleCategory.PAGE_OBJECT: "page_object",
            RuleCategory.STEP: "semantic",
            RuleCategory.REQUIREMENT: "semantic",
            RuleCategory.AI_GENERATION: "assertion",
        }
        return mapping.get(category, "semantic")
