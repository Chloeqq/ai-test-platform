"""CaseQualityGate — 统一质量门禁入口。

所有 AI 生成 Case 必须经过此节点。
"""

from __future__ import annotations

from shared_backend.quality_gate import (
    GateContext,
    RuleEngine,
    ValidationReport,
)

from .scoring import ScoreEngine


class CaseQualityGate:
    """用例质量门禁统一入口。

    流程：
    1. 调用 RuleEngine 执行全部规则
    2. 调用 ScoreEngine 计算质量评分
    3. 生成 ValidationReport
    4. 输出 Decision
    """

    def __init__(self) -> None:
        self._engine = RuleEngine()
        self._scoring = ScoreEngine()

    def evaluate(self, context: GateContext) -> ValidationReport:
        """评估用例质量。"""
        results = self._engine.execute_all(context)
        score = self._scoring.calculate(results)
        decision = self._engine.aggregate(results).decision

        case_id = (context.case_yaml or {}).get("id", "")
        return ValidationReport(
            case_id=case_id,
            results=results,
            decision=decision,
            score=score,
            summary=f"Decision: {decision.value.upper()}, Score: {score.total_score} ({score.grade})",
        )
