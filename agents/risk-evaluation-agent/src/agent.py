from __future__ import annotations

from typing import Any

from .schema import RiskFactor, RiskReport


class RiskEvaluationAgent:
    def evaluate(
        self,
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        factors: list[RiskFactor] = []
        score = 0
        triage = failure_triage if isinstance(failure_triage, dict) else {}

        priority = str(requirement_spec.get("priority", "P2")).upper()
        priority_score = {"P0": 35, "P1": 22, "P2": 12, "P3": 6}.get(priority, 10)
        score += priority_score
        factors.append(RiskFactor(factor="business_priority", score=priority_score, reason=f"priority={priority}"))

        status = str(execution_record.get("status", "generated")).lower()
        status_score_map = {
            "failed": 45,
            "coverage_gap": 32,
            "broken": 45,
            "passed": 6,
            "generated": 12,
            "running": 18,
        }
        status_score = status_score_map.get(status, 15)
        score += status_score
        factors.append(RiskFactor(factor="execution_status", score=status_score, reason=f"status={status}"))

        risk_level_from_failure = str(failure_analysis.get("risk_level", "")).lower()
        failure_score_map = {"critical": 30, "high": 24, "medium": 14, "low": 5}
        failure_score = failure_score_map.get(risk_level_from_failure, 8)
        score += failure_score
        factors.append(
            RiskFactor(
                factor="failure_analysis",
                score=failure_score,
                reason=f"failure_risk={risk_level_from_failure or 'unknown'}",
            )
        )

        retries = int(((execution_plan.get("retry_policy") or {}).get("max_retries", 0)) or 0)
        retry_penalty = min(10, retries * 2)
        score += retry_penalty
        factors.append(RiskFactor(factor="retry_strategy", score=retry_penalty, reason=f"max_retries={retries}"))

        total_steps = int(((execution_record.get("step_summary") or {}).get("total_steps", 0)) or 0)
        complexity_score = min(12, max(0, total_steps - 4))
        score += complexity_score
        factors.append(RiskFactor(factor="case_complexity", score=complexity_score, reason=f"steps={total_steps}"))

        triage_severity = str(triage.get("severity", "")).upper()
        triage_severity_score = {"S0": 24, "S1": 18, "S2": 10, "S3": 5, "S4": 2}.get(triage_severity, 0)
        if triage_severity_score:
            score += triage_severity_score
            factors.append(
                RiskFactor(
                    factor="triage_severity",
                    score=triage_severity_score,
                    reason=f"severity={triage_severity}",
                )
            )

        if bool(triage.get("requires_manual_review", False)):
            score += 8
            factors.append(
                RiskFactor(
                    factor="triage_manual_review",
                    score=8,
                    reason="triage requires manual review",
                )
            )

        score = max(0, min(score, 100))
        risk_level = self._to_level(score)
        gate_decision = self._to_gate_decision(score=score, status=status, risk_level=risk_level)
        recommendation = self._recommendation(gate_decision=gate_decision, risk_level=risk_level, status=status)

        report = RiskReport(
            version="RiskReportV1",
            risk_score=score,
            risk_level=risk_level,
            gate_decision=gate_decision,
            recommendation=recommendation,
            factors=factors,
            metadata={
                "priority": priority,
                "status": status,
                "failure_risk": risk_level_from_failure or "unknown",
                "triage_queue": str(triage.get("queue", "")).strip(),
            },
        )
        return report.to_dict()

    @staticmethod
    def _to_level(score: int) -> str:
        if score >= 75:
            return "high"
        if score >= 45:
            return "medium"
        return "low"

    @staticmethod
    def _to_gate_decision(*, score: int, status: str, risk_level: str) -> str:
        if status in {"failed", "coverage_gap", "broken"}:
            return "block"
        if score >= 75 or risk_level == "high":
            return "manual_review"
        if score >= 45:
            return "manual_review"
        return "allow"

    @staticmethod
    def _recommendation(*, gate_decision: str, risk_level: str, status: str) -> str:
        if gate_decision == "block":
            return f"当前状态 {status}，建议阻断发布并先修复失败或覆盖缺口。"
        if gate_decision == "manual_review":
            return f"风险等级 {risk_level}，建议人工复核后再决定发布。"
        return "风险可控，可放行并持续观察趋势。"
