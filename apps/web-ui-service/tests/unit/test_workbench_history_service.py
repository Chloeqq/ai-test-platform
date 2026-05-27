# ruff: noqa: E402
from __future__ import annotations

from datetime_compat import UTC
from datetime import datetime
from pathlib import Path

import sys


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))

from app.services import workbench_history_service as history_service


def test_list_history_enriches_rows_and_builds_governance_summary() -> None:
    history_items = [
        {
            "timestamp": "2026-03-22T10:00:00+00:00",
            "action": "review_confirmed",
            "run_id": "run-1",
            "case_id": "tc-product-001",
            "page": "product",
            "confirmed_by": "betty",
            "actor_display": "betty (admin)",
            "status": "confirmed",
        }
    ]

    result = history_service.list_history(
        history_items,
        resolve_governance_snapshot=lambda _run_id: {
            "risk_summary": {
                "risk_level": "medium",
                "gate_decision": "manual_review",
                "requires_review": True,
                "top_factor": {"factor": "pending_review_sections"},
            },
            "self_healing_summary": {
                "status": "rejected",
                "boundary": {"allowed": False, "advice_type": "assertion_update"},
            },
            "page_semantic_summary": {
                "page_type": "form",
                "business_domain": "product",
                "primary_goal": "商品编辑",
            },
        },
        resolve_failure_snapshot=lambda _run_id: {
            "analysis": {
                "failure_source": "page_object",
                "failure_source_reason": "locator mismatch",
                "source_evidence": [{"supports": "page_object"}],
                "requires_manual_review": False,
            }
        },
        normalize_page_slug=lambda value: str(value).strip().lower(),
        actor="betty",
        status="confirmed",
    )

    assert result["summary"]["total_items"] == 1
    assert result["summary"]["risk_gate_counts"] == {"manual_review": 1}
    assert result["summary"]["self_healing_status_counts"] == {"rejected": 1}
    assert result["summary"]["risk_requires_review_count"] == 1
    assert result["summary"]["boundary_rejected_count"] == 1
    row = result["items"][0]
    assert row["failure_source"] == "page_object"
    assert row["failure_source_reason"] == "locator mismatch"
    assert row["detail_summary"].startswith("失败来源=page_object")


def test_summarize_quality_gate_events_aggregates_alerts_and_trends() -> None:
    now_utc = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    history_items = [
        {
            "timestamp": now_utc.isoformat(),
            "action": "generate_case_blocked_by_quality_gate",
            "case_id": "tc-product-001",
            "page": "product",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "block",
                "blockers": [
                    {
                        "code": "low_parse_confidence",
                        "category": "quality",
                        "severity": "high",
                        "alert_code": "REQQG_CONFIDENCE_LOW",
                        "message": "parse confidence too low",
                        "value": 0.21,
                        "threshold": 0.5,
                    }
                ],
            },
        },
        {
            "timestamp": now_utc.isoformat(),
            "action": "generate_case",
            "case_id": "tc-product-002",
            "page": "product",
            "quality_gate": {
                "version": "RequirementQualityGateV1",
                "stage": "orchestrate",
                "decision": "allow",
                "blockers": [],
            },
        },
    ]

    result = history_service.summarize_quality_gate_events(
        history_items,
        limit=100,
        alert_code="REQQG_CONFIDENCE_LOW",
        page="product",
        normalize_page_slug=lambda value: str(value).strip().lower(),
    )

    assert result["total_events"] == 1
    assert result["blocked_events"] == 1
    assert result["allow_events"] == 0
    assert result["blocker_distribution"][0]["alert_code"] == "REQQG_CONFIDENCE_LOW"
    assert result["alert_details"][0]["remediation"]["title"]
    assert result["recent_blocked"][0]["blocker_alert_codes"] == ["REQQG_CONFIDENCE_LOW"]
    assert result["summary_24h"]["top_page"] == "product"
