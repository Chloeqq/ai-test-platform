from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers import legacy_workbench
from app.services import workbench_case_consistency_service, workbench_gate_service


router = APIRouter(tags=["workbench-gate"])


@router.get("/api/workbench/execution-gate/config")
def get_execution_gate_config() -> dict[str, Any]:
    policy_baseline = legacy_workbench._execution_gate_policy_baseline()
    return {
        "item": {
            "version": "ExecutionGateConfigV1",
            "block_missing_required_threshold": max(
                1,
                int(getattr(legacy_workbench.SETTINGS, "execution_gate_block_missing_required_threshold", 2) or 2),
            ),
            "block_on_failed_status": bool(getattr(legacy_workbench.SETTINGS, "execution_gate_block_on_failed_status", True)),
            "block_on_risk_block": bool(getattr(legacy_workbench.SETTINGS, "execution_gate_block_on_risk_block", True)),
            "warn_on_pending_reviews": bool(getattr(legacy_workbench.SETTINGS, "execution_gate_warn_on_pending_reviews", True)),
            "warn_on_low_confidence_elements": bool(
                getattr(legacy_workbench.SETTINGS, "execution_gate_warn_on_low_confidence_elements", True)
            ),
            "warn_on_pending_test_points": bool(
                getattr(legacy_workbench.SETTINGS, "execution_gate_warn_on_pending_test_points", True)
            ),
            "block_missing_dependency_points_threshold": max(
                1,
                int(getattr(legacy_workbench.SETTINGS, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
            ),
            "warn_on_low_confidence_dependency_points": bool(
                getattr(legacy_workbench.SETTINGS, "execution_gate_warn_on_low_confidence_dependency_points", True)
            ),
            "decision_privileged_roles": [
                str(item).strip().lower()
                for item in getattr(legacy_workbench.SETTINGS, "execution_gate_decision_privileged_roles", [])
                if str(item).strip()
            ],
            "dual_approval_enabled": bool(getattr(legacy_workbench.SETTINGS, "execution_gate_dual_approval_enabled", False)),
            "dual_approval_bypass_roles": [
                str(item).strip().lower()
                for item in getattr(legacy_workbench.SETTINGS, "execution_gate_dual_approval_bypass_roles", [])
                if str(item).strip()
            ],
            "policy_baseline": policy_baseline,
            "updated_at": legacy_workbench._now_iso(),
        }
    }


@router.post("/api/workbench/execution-gate/decisions")
def save_execution_gate_decision(
    payload: legacy_workbench.ExecutionGateDecisionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    if str(payload.case_id or "").strip() and not workbench_case_consistency_service.is_case_tracked(
        payload.case_id,
        case_center_case_ids=case_center_case_ids,
    ):
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="case_id not found in case center",
        )
    actor = legacy_workbench._extract_review_actor(request)
    try:
        actor = legacy_workbench._require_authenticated_review_actor(actor)
    except legacy_workbench.HTTPException as exc:
        legacy_workbench._append_history(
            {
                "timestamp": legacy_workbench._now_iso(),
                "action": "execution_gate_decision_rejected_auth",
                "case_id": legacy_workbench._safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                "page": legacy_workbench._normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                "run_id": str(payload.run_id).strip(),
                "status": "rejected",
                "detail_summary": "执行门禁决策被拒绝：未登录或身份不可追溯",
                "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": legacy_workbench._reviewer_display_name(actor),
                "source": "execution-gate-decision",
                "note": "review_auth_required",
            }
        )
        raise exc
    try:
        workbench_gate_service.require_execution_gate_decision_permission(actor, payload.decision)
    except legacy_workbench.HTTPException as exc:
        legacy_workbench._append_history(
            {
                "timestamp": legacy_workbench._now_iso(),
                "action": "execution_gate_decision_rejected_permission",
                "case_id": legacy_workbench._safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                "page": legacy_workbench._normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                "run_id": str(payload.run_id).strip(),
                "status": "rejected",
                "detail_summary": "执行门禁决策被拒绝：当前角色无权限",
                "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": legacy_workbench._reviewer_display_name(actor),
                "source": "execution-gate-decision",
                "note": "review_permission_required",
            }
        )
        raise exc

    record = workbench_gate_service.upsert_execution_gate_decision(payload, actor=actor)
    gate_snapshot = legacy_workbench._resolve_execution_gate_audit_snapshot(
        project=record.get("project", "default"),
        run_id=record.get("run_id", ""),
        page=record.get("page", ""),
    )
    gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
    legacy_workbench._append_history(
        {
            "timestamp": record["updated_at"],
            "action": "execution_gate_decided",
            "case_id": record.get("case_id", ""),
            "page": record.get("page", ""),
            "run_id": record.get("run_id", ""),
            "status": "confirmed",
            "review_type": "execution_gate",
            "detail_summary": f"执行门禁人工决策：{record.get('decision', 'manual_review')}" + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
            "decision": record.get("decision", "manual_review"),
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "active"),
            "gate_reason_summary": gate_reason_summary,
            "matched_rules": gate_snapshot.get("matched_rules", []),
            "evidence": gate_snapshot.get("evidence", []),
            "metrics": gate_snapshot.get("metrics", {}),
            "config_snapshot": gate_snapshot.get("config_snapshot", {}),
            "note": record.get("note", ""),
            "confirmed_by": str(record.get("decided_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(record.get("decided_by_role", "")).strip() or "unknown",
            "actor_display": legacy_workbench._reviewer_display_name(
                {
                    "confirmed_by": record.get("decided_by", ""),
                    "confirmed_by_role": record.get("decided_by_role", ""),
                }
            ),
            "source": "execution-gate-decision",
        }
    )
    return {
        "item": record,
        "summary": {
            "project": record["project"],
            "run_id": record["run_id"],
            "page": record["page"],
            "decision": record["decision"],
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "active"),
            "note": record.get("note", ""),
            "decided_by": record.get("decided_by", "anonymous"),
            "decided_by_role": record.get("decided_by_role", "unknown"),
            "updated_at": record["updated_at"],
        },
    }


@router.post("/api/workbench/execution-gate/decisions/approve")
def approve_execution_gate_decision(
    payload: legacy_workbench.ExecutionGateDecisionActionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    existing_decision = legacy_workbench._execution_gate_decision_for_run(
        run_id=payload.run_id,
        project=payload.project,
        page=payload.page,
    )
    existing_case_id = str(existing_decision.get("case_id", "")).strip()
    if existing_case_id and not workbench_case_consistency_service.is_case_tracked(
        existing_case_id,
        case_center_case_ids=case_center_case_ids,
    ):
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="case_id not found in case center",
        )
    actor = legacy_workbench._extract_review_actor(request)
    try:
        actor = legacy_workbench._require_authenticated_review_actor(actor)
    except legacy_workbench.HTTPException as exc:
        legacy_workbench._append_history(
            {
                "timestamp": legacy_workbench._now_iso(),
                "action": "execution_gate_approve_rejected_auth",
                "case_id": "",
                "page": legacy_workbench._normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                "run_id": str(payload.run_id).strip(),
                "status": "rejected",
                "detail_summary": "执行门禁二次审批被拒绝：未登录或身份不可追溯",
                "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": legacy_workbench._reviewer_display_name(actor),
                "source": "execution-gate-decision",
                "note": "review_auth_required",
            }
        )
        raise exc
    record = workbench_gate_service.approve_execution_gate_decision(
        project=payload.project,
        run_id=payload.run_id,
        page=payload.page,
        actor=actor,
        note=payload.note,
    )
    gate_snapshot = legacy_workbench._resolve_execution_gate_audit_snapshot(
        project=record.get("project", "default"),
        run_id=record.get("run_id", ""),
        page=record.get("page", ""),
    )
    gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
    legacy_workbench._append_history(
        {
            "timestamp": record["updated_at"],
            "action": "execution_gate_approved",
            "case_id": record.get("case_id", ""),
            "page": record.get("page", ""),
            "run_id": record.get("run_id", ""),
            "status": "confirmed",
            "review_type": "execution_gate",
            "detail_summary": f"执行门禁二次审批通过：{record.get('decision', 'manual_review')}" + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
            "decision": record.get("decision", "manual_review"),
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "active"),
            "gate_reason_summary": gate_reason_summary,
            "matched_rules": gate_snapshot.get("matched_rules", []),
            "evidence": gate_snapshot.get("evidence", []),
            "metrics": gate_snapshot.get("metrics", {}),
            "config_snapshot": gate_snapshot.get("config_snapshot", {}),
            "note": record.get("note", ""),
            "confirmed_by": str(record.get("second_approver", "")).strip() or "anonymous",
            "confirmed_by_role": str(record.get("second_approver_role", "")).strip() or "unknown",
            "actor_display": legacy_workbench._reviewer_display_name(
                {
                    "confirmed_by": record.get("second_approver", ""),
                    "confirmed_by_role": record.get("second_approver_role", ""),
                }
            ),
            "source": "execution-gate-decision",
        }
    )
    return {
        "item": record,
        "summary": {
            "project": record["project"],
            "run_id": record["run_id"],
            "page": record["page"],
            "decision": record["decision"],
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "active"),
            "second_approver": record.get("second_approver", ""),
            "second_approver_role": record.get("second_approver_role", ""),
            "updated_at": record["updated_at"],
        },
    }


@router.post("/api/workbench/execution-gate/decisions/revoke")
def revoke_execution_gate_decision(
    payload: legacy_workbench.ExecutionGateDecisionActionPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    existing_decision = legacy_workbench._execution_gate_decision_for_run(
        run_id=payload.run_id,
        project=payload.project,
        page=payload.page,
    )
    existing_case_id = str(existing_decision.get("case_id", "")).strip()
    if existing_case_id and not workbench_case_consistency_service.is_case_tracked(
        existing_case_id,
        case_center_case_ids=case_center_case_ids,
    ):
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_404_NOT_FOUND,
            detail="case_id not found in case center",
        )
    actor = legacy_workbench._extract_review_actor(request)
    try:
        actor = legacy_workbench._require_authenticated_review_actor(actor)
    except legacy_workbench.HTTPException as exc:
        legacy_workbench._append_history(
            {
                "timestamp": legacy_workbench._now_iso(),
                "action": "execution_gate_revoke_rejected_auth",
                "case_id": "",
                "page": legacy_workbench._normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                "run_id": str(payload.run_id).strip(),
                "status": "rejected",
                "detail_summary": "执行门禁撤销被拒绝：未登录或身份不可追溯",
                "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": legacy_workbench._reviewer_display_name(actor),
                "source": "execution-gate-decision",
                "note": "review_auth_required",
            }
        )
        raise exc
    record = workbench_gate_service.revoke_execution_gate_decision(
        project=payload.project,
        run_id=payload.run_id,
        page=payload.page,
        actor=actor,
        note=payload.note,
    )
    gate_snapshot = legacy_workbench._resolve_execution_gate_audit_snapshot(
        project=record.get("project", "default"),
        run_id=record.get("run_id", ""),
        page=record.get("page", ""),
    )
    gate_reason_summary = str(gate_snapshot.get("gate_reason_summary", "")).strip()
    legacy_workbench._append_history(
        {
            "timestamp": record["updated_at"],
            "action": "execution_gate_revoked",
            "case_id": record.get("case_id", ""),
            "page": record.get("page", ""),
            "run_id": record.get("run_id", ""),
            "status": "confirmed",
            "review_type": "execution_gate",
            "detail_summary": f"执行门禁决策已撤销：{record.get('decision', 'manual_review')}" + (f"（{gate_reason_summary}）" if gate_reason_summary else ""),
            "decision": record.get("decision", "manual_review"),
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "revoked"),
            "gate_reason_summary": gate_reason_summary,
            "matched_rules": gate_snapshot.get("matched_rules", []),
            "evidence": gate_snapshot.get("evidence", []),
            "metrics": gate_snapshot.get("metrics", {}),
            "config_snapshot": gate_snapshot.get("config_snapshot", {}),
            "note": record.get("note", ""),
            "confirmed_by": str(record.get("revoked_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(record.get("revoked_by_role", "")).strip() or "unknown",
            "actor_display": legacy_workbench._reviewer_display_name(
                {
                    "confirmed_by": record.get("revoked_by", ""),
                    "confirmed_by_role": record.get("revoked_by_role", ""),
                }
            ),
            "source": "execution-gate-decision",
        }
    )
    return {
        "item": record,
        "summary": {
            "project": record["project"],
            "run_id": record["run_id"],
            "page": record["page"],
            "decision": record["decision"],
            "approval_status": record.get("approval_status", "approved"),
            "record_status": record.get("record_status", "revoked"),
            "revoked_by": record.get("revoked_by", ""),
            "revoked_by_role": record.get("revoked_by_role", ""),
            "updated_at": record["updated_at"],
        },
    }
