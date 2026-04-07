from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers import legacy_workbench
from app.services import workbench_case_consistency_service


router = APIRouter(tags=["workbench-reviews"])


@router.post("/api/workbench/reviews")
def save_review(
    payload: legacy_workbench.WorkbenchReviewPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
    if not workbench_case_consistency_service.is_case_tracked(
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
                "action": "review_rejected_auth",
                "case_id": legacy_workbench._safe_case_id(payload.case_id) if str(payload.case_id).strip() else "",
                "page": legacy_workbench._normalize_page_slug(payload.page) if str(payload.page).strip() else "",
                "run_id": str(payload.run_id).strip(),
                "status": "rejected",
                "review_type": legacy_workbench._normalize_review_type(payload.review_type),
                "review_item_count": len(payload.items),
                "review_items": [
                    str(item.get("label") or item.get("key") or "").strip()
                    for item in payload.items[:10]
                    if isinstance(item, dict) and str(item.get("label") or item.get("key") or "").strip()
                ],
                "detail_summary": "确认点提交被拒绝：未登录或身份不可追溯",
                "confirmed_by": str(actor.get("confirmed_by", "")).strip() or "anonymous",
                "confirmed_by_role": str(actor.get("confirmed_by_role", "")).strip() or "unknown",
                "actor_display": legacy_workbench._reviewer_display_name(actor),
                "source": "workbench-review",
                "note": "review_auth_required",
            }
        )
        raise exc
    record = legacy_workbench._upsert_review_decision(payload, actor=actor)
    review_type = str(record.get("review_type", "")).strip() or "unknown"
    status_value = str(record.get("status", "")).strip() or "confirmed"
    reviewed_items_raw = record.get("items")
    reviewed_items: list[Any] = reviewed_items_raw if isinstance(reviewed_items_raw, list) else []
    item_labels = [
        str(item.get("label") or item.get("key") or "").strip()
        for item in reviewed_items
        if isinstance(item, dict) and str(item.get("label") or item.get("key") or "").strip()
    ]
    legacy_workbench._append_history(
        {
            "timestamp": record["updated_at"],
            "action": f"review_{status_value}",
            "case_id": record.get("case_id", ""),
            "page": record.get("page", ""),
            "run_id": record.get("run_id", ""),
            "status": status_value,
            "review_type": review_type,
            "review_item_count": len(reviewed_items),
            "review_items": item_labels[:10],
            "detail_summary": f"{review_type} 确认 {len(reviewed_items)} 项",
            "confirmed_by": str(record.get("confirmed_by", "")).strip() or "anonymous",
            "confirmed_by_role": str(record.get("confirmed_by_role", "")).strip() or "unknown",
            "actor_display": legacy_workbench._reviewer_display_name(record),
            "source": "workbench-review",
            "note": record.get("note", ""),
        }
    )
    calibration_sample = legacy_workbench._record_failure_source_calibration_sample(
        review_record=record,
        feedback=payload.failure_source_feedback if isinstance(payload.failure_source_feedback, dict) else None,
    )
    if calibration_sample:
        legacy_workbench._append_history(
            {
                "timestamp": calibration_sample.get("created_at", legacy_workbench._now_iso()),
                "action": "failure_source_calibration_recorded",
                "case_id": calibration_sample.get("case_id", ""),
                "page": calibration_sample.get("page", ""),
                "run_id": calibration_sample.get("run_id", ""),
                "status": "recorded",
                "review_type": calibration_sample.get("review_type", ""),
                "detail_summary": f"failure_source 校准样本已记录：{calibration_sample.get('predicted_failure_source', '-') or '-'} -> {calibration_sample.get('confirmed_failure_source', '-') or '-'}",
                "confirmed_by": calibration_sample.get("confirmed_by", "anonymous"),
                "confirmed_by_role": calibration_sample.get("confirmed_by_role", "unknown"),
                "actor_display": calibration_sample.get("actor_display", legacy_workbench._reviewer_display_name(record)),
                "source": "failure-source-calibration",
                "decision": calibration_sample.get("human_decision", ""),
                "note": calibration_sample.get("feedback_reason", ""),
            }
        )
    return {
        "item": record,
        "summary": {
            "project": record["project"],
            "run_id": record["run_id"],
            "page": record["page"],
            "review_type": record["review_type"],
            "status": record["status"],
            "candidate_count": len(record["items"]),
            "confirmed_by": record.get("confirmed_by", "anonymous"),
            "confirmed_by_role": record.get("confirmed_by_role", "unknown"),
            "updated_at": record["updated_at"],
        },
        "calibration_sample": calibration_sample,
    }
