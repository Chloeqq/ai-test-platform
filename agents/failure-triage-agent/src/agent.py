# mypy: ignore-errors

from __future__ import annotations

from typing import Any

from .schema import FailureTriage, TriageAction


class FailureTriageAgent:
    def triage(
        self,
        *,
        failure_analysis: dict[str, Any],
        execution_record: dict[str, Any],
        evidence_manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        category = str(failure_analysis.get("failure_category", "unknown")).strip().lower() or "unknown"
        failure_source = str(failure_analysis.get("failure_source", "unknown")).strip().lower() or "unknown"
        risk_level = str(failure_analysis.get("risk_level", "medium")).strip().lower() or "medium"
        status = str(execution_record.get("status", "generated")).strip().lower() or "generated"
        page = str((execution_record.get("step_summary") or {}).get("page", "")).strip() or str((report or {}).get("page", "")).strip()

        confidence = self._normalize_confidence(failure_analysis.get("confidence", 0.5))
        source_confidence = self._normalize_confidence(failure_analysis.get("failure_source_confidence", confidence))
        owner_team = self._owner_team(category=category, failure_source=failure_source)
        queue = self._queue(category=category, failure_source=failure_source, risk_level=risk_level)
        severity = self._severity(status=status, risk_level=risk_level)
        requires_manual_review = (
            bool(failure_analysis.get("requires_manual_review", False))
            or source_confidence < 0.7
            or category == "unknown"
            or failure_source == "unknown"
            or risk_level in {"high", "critical"}
            or confidence < 0.65
        )

        action_types = (execution_record.get("step_summary") or {}).get("action_types", [])
        if not isinstance(action_types, list):
            action_types = []
        action_signature = ",".join(sorted(str(item).strip() for item in action_types if str(item).strip())) or "none"
        bucket_key = f"{failure_source}|{category}|{page or 'unknown-page'}|{action_signature}"
        triage_label = f"{failure_source}:{category}:{risk_level}:{status}"

        actions = self._actions(
            category=category,
            failure_source=failure_source,
            owner_team=owner_team,
            queue=queue,
            risk_level=risk_level,
        )
        triage = FailureTriage(
            version="FailureTriageV1",
            triage_label=triage_label,
            failure_class=category,
            severity=severity,
            owner_team=owner_team,
            queue=queue,
            bucket_key=bucket_key,
            duplicate_of="",
            requires_manual_review=requires_manual_review,
            confidence=confidence,
            signals={
                "status": status,
                "risk_level": risk_level,
                "page": page,
                "failure_source": failure_source,
                "failure_source_confidence": source_confidence,
                "evidence_total_files": int(evidence_manifest.get("total_files", 0) or 0),
                "suggestion_file_count": len(evidence_manifest.get("suggestion_files", []) or []),
                "analysis_file_count": len(evidence_manifest.get("analysis_files", []) or []),
            },
            actions=actions,
            metadata={
                "source": "failure-triage-agent",
                "category": category,
                "failure_source": failure_source,
            },
        )
        return triage.to_dict()

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.5
        return max(0.0, min(confidence, 1.0))

    @staticmethod
    def _owner_team(*, category: str, failure_source: str) -> str:
        if failure_source == "app_bug":
            return "product-engineering"
        if failure_source == "page_analysis":
            return "qa-platform"
        if failure_source == "page_object":
            return "qa-automation"
        if failure_source == "case_design":
            return "qa-design"
        if category in {"environment", "network", "authentication", "timeout"}:
            return "qa-infra"
        if category in {"locator", "assertion", "data"}:
            return "qa-automation"
        return "qa-triage"

    @staticmethod
    def _queue(*, category: str, failure_source: str, risk_level: str) -> str:
        if risk_level in {"high", "critical"}:
            return "priority-triage"
        source_mapping = {
            "app_bug": "product-regression",
            "page_analysis": "page-analysis-review",
            "page_object": "ui-regression",
            "case_design": "case-design-review",
        }
        if failure_source in source_mapping:
            return source_mapping[failure_source]
        mapping = {
            "environment": "infra-investigation",
            "network": "infra-investigation",
            "authentication": "access-control",
            "timeout": "infra-investigation",
            "locator": "ui-regression",
            "assertion": "product-regression",
            "data": "test-data",
        }
        return mapping.get(category, "manual-triage")

    @staticmethod
    def _severity(*, status: str, risk_level: str) -> str:
        if status in {"failed", "broken", "coverage_gap"}:
            if risk_level == "critical":
                return "S0"
            if risk_level == "high":
                return "S1"
            if risk_level == "medium":
                return "S2"
            return "S3"
        if status == "running":
            return "S3"
        return "S4"

    @staticmethod
    def _actions(*, category: str, failure_source: str, owner_team: str, queue: str, risk_level: str) -> list[TriageAction]:
        items = [
            TriageAction(
                action=f"create_ticket:{queue}",
                owner=owner_team,
                reason=f"按来源 {failure_source} / 分类 {category} 进入 {queue} 队列处理。",
            )
        ]
        if failure_source == "page_analysis":
            items.append(
                TriageAction(
                    action="review_page_surface_and_required_elements",
                    owner="qa-platform",
                    reason="需要复核页面分析结果、页面类型判断和关键元素识别。",
                )
            )
        if failure_source == "case_design":
            items.append(
                TriageAction(
                    action="review_assertions_and_test_points",
                    owner="qa-design",
                    reason="需要复核测试点、断言和测试数据假设是否过期。",
                )
            )
        if failure_source == "app_bug":
            items.append(
                TriageAction(
                    action="collect_backend_logs",
                    owner="product-engineering",
                    reason="需要补充服务端日志和接口错误证据，确认是否为真实应用缺陷。",
                )
            )
        if category in {"locator", "assertion"}:
            items.append(
                TriageAction(
                    action="collect_dom_snapshot",
                    owner="qa-automation",
                    reason="补充页面结构证据用于定位页面对象或断言漂移。",
                )
            )
        if category in {"network", "environment", "authentication", "timeout"}:
            items.append(
                TriageAction(
                    action="collect_infra_logs",
                    owner="qa-infra",
                    reason="补充基础设施日志定位环境层故障。",
                )
            )
        if risk_level in {"high", "critical"}:
            items.append(
                TriageAction(
                    action="block_release_candidate",
                    owner="release-manager",
                    reason="高风险失败默认阻断候选发布，待复核后解除。",
                )
            )
        return items
