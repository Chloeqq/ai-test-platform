from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings
from datetime_compat import UTC
from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import now_iso as _now_iso

from . import workbench_state_store as state_store

PAGE_ALIAS_MAP = {
    "addprouct": "addproduct",
    "add-product": "addproduct",
}


def _settings() -> Any:
    return get_settings()


from shared_backend.type_utils import dedup_keep_order as _dedup_keep_order


def _normalize_page_slug(value: str) -> str:
    normalized = "".join(ch for ch in str(value).strip().lower() if ch.isalnum() or ch in {"-", "_"})
    normalized = PAGE_ALIAS_MAP.get(normalized, normalized)
    return normalized or "product"


def _safe_case_id(raw: str) -> str:
    text = str(raw).strip()
    if not text:
        return f"case-general-{datetime.now(UTC).strftime('%H%M%S')}"
    return normalize_case_id(text)


def _normalize_history_text_list(value: Any, *, limit: int = 10) -> list[str]:
    items = value if isinstance(value, list) else []
    normalized = [str(item).strip() for item in items if str(item).strip()]
    return _dedup_keep_order(normalized)[:limit]


def normalize_page_slug(value: str) -> str:
    return _normalize_page_slug(value)


def safe_case_id(raw: str) -> str:
    return _safe_case_id(raw)


def normalize_history_text_list(value: Any, *, limit: int = 10) -> list[str]:
    return _normalize_history_text_list(value, limit=limit)


def _payload_value(payload: Any, key: str, default: Any = "") -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def normalize_execution_gate_decision(value: str) -> str:
    decision = str(value or "").strip().lower()
    if decision in {"allow", "block", "manual_review"}:
        return decision
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="decision must be one of: allow, block, manual_review",
    )


def execution_gate_decision_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("project", "mall")).strip() or "mall",
        str(item.get("run_id", "")).strip(),
        _normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else "",
    )


def normalized_role(value: str) -> str:
    return str(value or "").strip().lower()


def is_execution_gate_privileged_role(role: str) -> bool:
    normalized = normalized_role(role)
    settings = _settings()
    allowed = {
        normalized_role(item)
        for item in getattr(settings, "execution_gate_decision_privileged_roles", [])
        if str(item).strip()
    }
    if not allowed:
        allowed = {"admin"}
    return normalized in allowed


def can_bypass_dual_approval(role: str) -> bool:
    normalized = normalized_role(role)
    settings = _settings()
    bypass_roles = {
        normalized_role(item)
        for item in getattr(settings, "execution_gate_dual_approval_bypass_roles", [])
        if str(item).strip()
    }
    if not bypass_roles:
        bypass_roles = {"admin"}
    return normalized in bypass_roles


def require_execution_gate_decision_permission(actor: dict[str, str], decision: str) -> None:
    normalized_decision = normalize_execution_gate_decision(decision)
    role = normalized_role(actor.get("confirmed_by_role", ""))
    if normalized_decision == "manual_review":
        return
    if is_execution_gate_privileged_role(role):
        return
    settings = _settings()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "execution_gate_decision_forbidden",
            "message": f"当前角色 {role or 'unknown'} 无权执行门禁决策 {normalized_decision}。",
            "allowed_roles": sorted(
                {
                    normalized_role(item)
                    for item in getattr(settings, "execution_gate_decision_privileged_roles", [])
                    if str(item).strip()
                }
                or {"admin"}
            ),
        },
    )


def upsert_execution_gate_decision(payload: Any, *, actor: dict[str, str] | None = None) -> dict[str, Any]:
    normalized_page = _normalize_page_slug(str(_payload_value(payload, "page", "")).strip())
    actor_info = actor if isinstance(actor, dict) else {}
    actor_role = normalized_role(actor_info.get("confirmed_by_role", ""))
    normalized_decision = normalize_execution_gate_decision(str(_payload_value(payload, "decision", "")).strip())
    settings = _settings()
    dual_approval_enabled = bool(getattr(settings, "execution_gate_dual_approval_enabled", False))
    approval_status = "approved"
    if normalized_decision == "block" and dual_approval_enabled and not can_bypass_dual_approval(actor_role):
        approval_status = "pending_second_approval"
    entry = {
        "project": str(_payload_value(payload, "project", "mall") or "mall").strip() or "mall",
        "run_id": str(_payload_value(payload, "run_id", "")).strip(),
        "case_id": _safe_case_id(str(_payload_value(payload, "case_id", "")).strip()) if str(_payload_value(payload, "case_id", "")).strip() else "",
        "page": normalized_page,
        "decision": normalized_decision,
        "record_status": "active",
        "approval_status": approval_status,
        "second_approver": "",
        "second_approver_role": "",
        "second_approved_at": "",
        "revoked_at": "",
        "revoked_by": "",
        "revoked_by_role": "",
        "note": str(_payload_value(payload, "note", "") or "").strip(),
        "decided_by": str(actor_info.get("confirmed_by", "")).strip() or "anonymous",
        "decided_by_role": str(actor_info.get("confirmed_by_role", "")).strip() or "unknown",
        "decided_by_source": str(actor_info.get("confirmed_by_source", "")).strip() or "system_default",
        "updated_at": _now_iso(),
    }
    identity = execution_gate_decision_identity(entry)
    with state_store.FILE_LOCK:
        items = state_store.read_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE)
        for item in items:
            if execution_gate_decision_identity(item) != identity:
                continue
            created_at = str(item.get("created_at", "")).strip() or entry["updated_at"]
            existing_second_approver = str(item.get("second_approver", "")).strip()
            existing_second_role = str(item.get("second_approver_role", "")).strip()
            existing_second_time = str(item.get("second_approved_at", "")).strip()
            item.clear()
            item.update({**entry, "created_at": created_at})
            if entry["approval_status"] == "approved" and existing_second_approver:
                item["second_approver"] = existing_second_approver
                item["second_approver_role"] = existing_second_role
                item["second_approved_at"] = existing_second_time
            state_store.write_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE, items[:1000])
            return dict(item)
        record = {**entry, "created_at": entry["updated_at"]}
        items.insert(0, record)
        state_store.write_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE, items[:1000])
        return record


def execution_gate_decision_for_run(
    *,
    run_id: str,
    project: str = "",
    page: str = "",
    read_json_list: Any | None = None,
) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    normalized_project = str(project or "").strip()
    normalized_page = _normalize_page_slug(page) if str(page).strip() else ""
    if not normalized_run_id:
        return {}
    reader = read_json_list if callable(read_json_list) else state_store.read_json_list
    for item in reader(state_store.EXECUTION_GATE_DECISIONS_FILE):
        if str(item.get("run_id", "")).strip() != normalized_run_id:
            continue
        if normalized_project and str(item.get("project", "")).strip() != normalized_project:
            continue
        item_page = _normalize_page_slug(str(item.get("page", "")).strip()) if str(item.get("page", "")).strip() else ""
        if normalized_page and item_page != normalized_page:
            continue
        decision = str(item.get("decision", "")).strip()
        if decision not in {"allow", "block", "manual_review"}:
            continue
        return {
            "project": str(item.get("project", "mall")).strip() or "mall",
            "run_id": normalized_run_id,
            "case_id": str(item.get("case_id", "")).strip(),
            "page": item_page,
            "decision": decision,
            "record_status": str(item.get("record_status", "active")).strip() or "active",
            "approval_status": str(item.get("approval_status", "approved")).strip() or "approved",
            "second_approver": str(item.get("second_approver", "")).strip(),
            "second_approver_role": str(item.get("second_approver_role", "")).strip(),
            "second_approved_at": str(item.get("second_approved_at", "")).strip(),
            "revoked_at": str(item.get("revoked_at", "")).strip(),
            "revoked_by": str(item.get("revoked_by", "")).strip(),
            "revoked_by_role": str(item.get("revoked_by_role", "")).strip(),
            "note": str(item.get("note", "")).strip(),
            "decided_by": str(item.get("decided_by", "")).strip() or "anonymous",
            "decided_by_role": str(item.get("decided_by_role", "")).strip() or "unknown",
            "decided_by_source": str(item.get("decided_by_source", "")).strip() or "system_default",
            "updated_at": str(item.get("updated_at", "")).strip(),
            "created_at": str(item.get("created_at", "")).strip(),
        }
    return {}


def approve_execution_gate_decision(
    *,
    project: str,
    run_id: str,
    page: str,
    actor: dict[str, str],
    note: str = "",
) -> dict[str, Any]:
    normalized_page = _normalize_page_slug(page)
    normalized_project = str(project or "mall").strip() or "mall"
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id is required")
    actor_name = str(actor.get("confirmed_by", "")).strip() or "anonymous"
    actor_role = normalized_role(actor.get("confirmed_by_role", ""))
    if not is_execution_gate_privileged_role(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "execution_gate_approve_forbidden",
                "message": "当前角色无权执行门禁二次审批。",
            },
        )
    with state_store.FILE_LOCK:
        items = state_store.read_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE)
        for item in items:
            if execution_gate_decision_identity(item) != (normalized_project, normalized_run_id, normalized_page):
                continue
            if str(item.get("record_status", "active")).strip().lower() == "revoked":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="execution gate decision already revoked")
            if str(item.get("approval_status", "approved")).strip().lower() != "pending_second_approval":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="execution gate decision does not require second approval")
            if str(item.get("decided_by", "")).strip() == actor_name:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="second approver must be different from decision maker")
            item["approval_status"] = "approved"
            item["second_approver"] = actor_name
            item["second_approver_role"] = str(actor.get("confirmed_by_role", "")).strip() or "unknown"
            item["second_approved_at"] = _now_iso()
            if note:
                existing_note = str(item.get("note", "")).strip()
                item["note"] = f"{existing_note} | second_approval: {note}".strip(" |")
            item["updated_at"] = _now_iso()
            state_store.write_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE, items[:1000])
            return dict(item)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="execution gate decision not found")


def revoke_execution_gate_decision(
    *,
    project: str,
    run_id: str,
    page: str,
    actor: dict[str, str],
    note: str = "",
) -> dict[str, Any]:
    normalized_page = _normalize_page_slug(page)
    normalized_project = str(project or "mall").strip() or "mall"
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_id is required")
    actor_name = str(actor.get("confirmed_by", "")).strip() or "anonymous"
    actor_role = normalized_role(actor.get("confirmed_by_role", ""))
    with state_store.FILE_LOCK:
        items = state_store.read_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE)
        for item in items:
            if execution_gate_decision_identity(item) != (normalized_project, normalized_run_id, normalized_page):
                continue
            if str(item.get("record_status", "active")).strip().lower() == "revoked":
                return dict(item)
            decision_maker = str(item.get("decided_by", "")).strip()
            if actor_name != decision_maker and not is_execution_gate_privileged_role(actor_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "execution_gate_revoke_forbidden",
                        "message": "当前角色无权撤销该门禁决策。",
                    },
                )
            item["record_status"] = "revoked"
            item["revoked_by"] = actor_name
            item["revoked_by_role"] = str(actor.get("confirmed_by_role", "")).strip() or "unknown"
            item["revoked_at"] = _now_iso()
            if note:
                existing_note = str(item.get("note", "")).strip()
                item["note"] = f"{existing_note} | revoked: {note}".strip(" |")
            item["updated_at"] = _now_iso()
            state_store.write_json_list(state_store.EXECUTION_GATE_DECISIONS_FILE, items[:1000])
            return dict(item)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="execution gate decision not found")


def build_execution_gate_audit_snapshot(execution_gate: dict[str, Any] | None) -> dict[str, Any]:
    gate = execution_gate if isinstance(execution_gate, dict) else {}
    blockers = _normalize_history_text_list(gate.get("blockers"), limit=10)
    warnings = _normalize_history_text_list(gate.get("warnings"), limit=10)
    evidence = _normalize_history_text_list(gate.get("evidence"), limit=10)
    matched_rules = [{"level": "blocker", "message": message} for message in blockers] + [
        {"level": "warning", "message": message} for message in warnings
    ]
    reason_items = blockers[:2] or warnings[:2] or evidence[:2]
    reason_summary = "；".join(reason_items)
    extra_count = max(len(blockers if blockers else warnings if warnings else evidence) - len(reason_items), 0)
    if reason_summary and extra_count > 0:
        reason_summary = f"{reason_summary} 等 {extra_count + len(reason_items)} 项"
    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    config_snapshot = gate.get("config_snapshot") if isinstance(gate.get("config_snapshot"), dict) else {}
    return {
        "decision": str(gate.get("decision", "")).strip() or "allow",
        "effective_decision": str(gate.get("effective_decision", "")).strip() or str(gate.get("decision", "")).strip() or "allow",
        "decision_source": str(gate.get("decision_source", "")).strip() or "system",
        "matched_rules": matched_rules[:10],
        "gate_reason_summary": reason_summary,
        "evidence": evidence[:10],
        "metrics": metrics,
        "config_snapshot": config_snapshot,
    }


def resolve_execution_gate_audit_snapshot(
    *,
    project: str,
    run_id: str,
    page: str,
    find_run_item: Any,
    normalize_page_slug_fn: Any,
    build_execution_gate_audit_snapshot_fn: Any,
) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {}
    normalize_page_slug = normalize_page_slug_fn if callable(normalize_page_slug_fn) else _normalize_page_slug
    normalized_page = normalize_page_slug(page) if str(page).strip() else ""
    run_item = find_run_item(normalized_run_id) if callable(find_run_item) else None
    if not isinstance(run_item, dict):
        return {}
    run_project = str(run_item.get("project", "mall")).strip() or "mall"
    run_page = normalize_page_slug(str(run_item.get("page", "")).strip()) if str(run_item.get("page", "")).strip() else ""
    if str(project or "mall").strip() and run_project != (str(project or "mall").strip() or "mall"):
        return {}
    if normalized_page and run_page and normalized_page != run_page:
        return {}
    execution_gate = run_item.get("execution_gate") if isinstance(run_item.get("execution_gate"), dict) else {}
    builder = build_execution_gate_audit_snapshot_fn if callable(build_execution_gate_audit_snapshot_fn) else build_execution_gate_audit_snapshot
    return builder(execution_gate)


def execution_gate_policy_baseline() -> dict[str, Any]:
    settings = _settings()
    block_missing_required_threshold = max(
        1,
        int(getattr(settings, "execution_gate_block_missing_required_threshold", 2) or 2),
    )
    block_missing_dependency_points_threshold = max(
        1,
        int(getattr(settings, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
    )
    decision_privileged_roles = [
        str(item).strip().lower()
        for item in getattr(settings, "execution_gate_decision_privileged_roles", [])
        if str(item).strip()
    ] or ["admin"]
    dual_approval_bypass_roles = [
        str(item).strip().lower()
        for item in getattr(settings, "execution_gate_dual_approval_bypass_roles", [])
        if str(item).strip()
    ] or ["admin"]
    dual_approval_enabled = bool(getattr(settings, "execution_gate_dual_approval_enabled", False))
    return {
        "version": "ExecutionGatePolicyBaselineV1",
        "system_decision_rules": {
            "block": _dedup_keep_order(
                [
                    "执行状态为 failed/generate_failed 时直接阻断。"
                    if bool(getattr(settings, "execution_gate_block_on_failed_status", True))
                    else "",
                    f"Page Object 缺失必需元素达到 {block_missing_required_threshold} 个时阻断。",
                    f"未识别依赖元素影响测试点达到 {block_missing_dependency_points_threshold} 个时阻断。",
                    "风险评估 gate_decision=block 时阻断。"
                    if bool(getattr(settings, "execution_gate_block_on_risk_block", True))
                    else "",
                ]
            ),
            "manual_review": _dedup_keep_order(
                [
                    "存在待确认分组时进入人工复核。"
                    if bool(getattr(settings, "execution_gate_warn_on_pending_reviews", True))
                    else "",
                    "存在低置信度页面元素时进入人工复核。"
                    if bool(getattr(settings, "execution_gate_warn_on_low_confidence_elements", True))
                    else "",
                    "存在待确认测试点时进入人工复核。"
                    if bool(getattr(settings, "execution_gate_warn_on_pending_test_points", True))
                    else "",
                    "存在受低置信度依赖元素影响的测试点时进入人工复核。"
                    if bool(getattr(settings, "execution_gate_warn_on_low_confidence_dependency_points", True))
                    else "",
                    "覆盖状态非 full 时进入人工复核。",
                    "存在 skip 建议测试点时进入人工复核。",
                ]
            ),
            "allow": [
                "未命中阻断规则，且不存在需人工复核的 warning 时自动放行。"
            ],
        },
        "manual_override_boundary": {
            "allowed_decisions": ["manual_review", "allow", "block"],
            "authenticated_required": True,
            "manual_review_roles": ["any_authenticated_user"],
            "allow_block_roles": decision_privileged_roles,
            "dual_approval": {
                "enabled": dual_approval_enabled,
                "applies_to": ["block"] if dual_approval_enabled else [],
                "bypass_roles": dual_approval_bypass_roles if dual_approval_enabled else [],
                "rule": "当 dual approval 开启时，非豁免角色提交 block 需要二次审批。"
                if dual_approval_enabled
                else "当前未启用二次审批。",
            },
            "revoke_boundary": {
                "allowed_actors": ["decision_maker", "privileged_role"],
                "rule": "撤销仅允许原决策人或具备 privileged role 的用户执行。",
            },
        },
        "non_goals": [
            "AI 不直接决定 pass/fail。",
            "AI 不直接决定 execution gate 最终人工 override。",
            "Self-healing 不允许修改业务断言和业务流程。",
        ],
    }


def build_execution_gate(
    *,
    page: str,
    final_status: str,
    coverage: dict[str, Any],
    page_surface_summary: dict[str, Any],
    page_semantic_summary: dict[str, Any],
    page_object_summary: dict[str, Any],
    test_points: dict[str, Any],
    review_state: dict[str, Any],
    risk_report: dict[str, Any] | None = None,
    test_point_asset_context: dict[str, Any] | None = None,
    dedup_keep_order_fn: Any | None = None,
) -> dict[str, Any]:
    settings = _settings()
    dedup_keep_order = dedup_keep_order_fn if callable(dedup_keep_order_fn) else _dedup_keep_order
    status_value = str(final_status or "").strip().lower() or "unknown"
    coverage_status = str((coverage or {}).get("status", "full")).strip().lower() or "full"
    pending_sections = int((review_state or {}).get("pending_sections", 0) or 0)
    low_confidence_elements = int((page_surface_summary or {}).get("low_confidence_count", 0) or 0)
    semantic_requires_review = bool((page_semantic_summary or {}).get("requires_review", False))
    semantic_page_type = str((page_semantic_summary or {}).get("page_type", "")).strip().lower() or "unknown"
    semantic_business_domain = str((page_semantic_summary or {}).get("business_domain", "")).strip().lower() or "generic"
    semantic_primary_goal = str((page_semantic_summary or {}).get("primary_goal", "")).strip() or "inspect_page"
    missing_required = int((page_object_summary or {}).get("missing_required_count", 0) or 0)
    point_summary = (test_points or {}).get("review_summary", {}) if isinstance(test_points, dict) else {}
    asset_context = test_point_asset_context if isinstance(test_point_asset_context, dict) else {}
    asset_review_summary = asset_context.get("review_summary", {}) if isinstance(asset_context.get("review_summary"), dict) else {}
    asset_selection_summary = asset_context.get("selection_summary", {}) if isinstance(asset_context.get("selection_summary"), dict) else {}
    asset_traceability_summary = asset_context.get("traceability_summary", {}) if isinstance(asset_context.get("traceability_summary"), dict) else {}
    pending_test_points = int(point_summary.get("pending_review_count", asset_review_summary.get("pending_review_count", 0)) or 0)
    skip_suggestions = int(point_summary.get("skip_suggestion_count", asset_review_summary.get("skip_suggestion_count", 0)) or 0)
    dependency_review_points = int(point_summary.get("dependency_review_count", asset_review_summary.get("dependency_review_count", 0)) or 0)
    low_confidence_dependency_points = int(point_summary.get("low_confidence_dependency_point_count", asset_review_summary.get("low_confidence_dependency_point_count", 0)) or 0)
    missing_dependency_points = int(point_summary.get("missing_dependency_point_count", asset_review_summary.get("missing_dependency_point_count", 0)) or 0)
    dependency_skip_points = int(point_summary.get("dependency_skip_count", asset_review_summary.get("dependency_skip_count", 0)) or 0)
    asset_selection_state = str(asset_selection_summary.get("selection_state", "")).strip().lower()
    asset_ready_for_regression = bool(asset_selection_summary.get("ready_for_regression", False))
    asset_selection_reasons = asset_selection_summary.get("reasons", []) if isinstance(asset_selection_summary.get("reasons"), list) else []
    block_missing_required_threshold = max(1, int(getattr(settings, "execution_gate_block_missing_required_threshold", 2) or 2))
    block_missing_dependency_points_threshold = max(
        1,
        int(getattr(settings, "execution_gate_block_missing_dependency_points_threshold", 1) or 1),
    )
    block_on_failed_status = bool(getattr(settings, "execution_gate_block_on_failed_status", True))
    block_on_risk_block = bool(getattr(settings, "execution_gate_block_on_risk_block", True))
    warn_on_pending_reviews = bool(getattr(settings, "execution_gate_warn_on_pending_reviews", True))
    warn_on_low_confidence_elements = bool(getattr(settings, "execution_gate_warn_on_low_confidence_elements", True))
    warn_on_pending_test_points = bool(getattr(settings, "execution_gate_warn_on_pending_test_points", True))
    warn_on_low_confidence_dependency_points = bool(
        getattr(settings, "execution_gate_warn_on_low_confidence_dependency_points", True)
    )

    blockers: list[str] = []
    warnings: list[str] = []
    evidence: list[str] = []

    if block_on_failed_status and status_value in {"generate_failed", "failed"}:
        blockers.append(f"执行状态为 {status_value}。")
        evidence.append(f"执行状态={status_value}，按门禁规则直接阻断。")
    if missing_required >= block_missing_required_threshold:
        blockers.append(f"Page Object 缺失必需元素 {missing_required} 个。")
        evidence.append(f"Page Object 缺失必需元素 {missing_required} 个，达到阻断阈值 {block_missing_required_threshold}。")
    elif missing_required > 0:
        warnings.append(f"Page Object 缺失必需元素 {missing_required} 个。")
        evidence.append(f"Page Object 缺失必需元素 {missing_required} 个，低于阻断阈值 {block_missing_required_threshold}。")
    if missing_dependency_points >= block_missing_dependency_points_threshold:
        blockers.append(f"存在依赖元素未识别的测试点 {missing_dependency_points} 个。")
        evidence.append(
            f"页面分析未识别依赖元素影响测试点 {missing_dependency_points} 个，达到阻断阈值 {block_missing_dependency_points_threshold}。"
        )
    elif missing_dependency_points > 0:
        warnings.append(f"存在依赖元素未识别的测试点 {missing_dependency_points} 个。")
        evidence.append(
            f"页面分析未识别依赖元素影响测试点 {missing_dependency_points} 个，低于阻断阈值 {block_missing_dependency_points_threshold}。"
        )

    if coverage_status != "full":
        warnings.append(f"覆盖状态为 {coverage_status}。")
        evidence.append(f"覆盖状态={coverage_status}。")
    if warn_on_low_confidence_elements and low_confidence_elements > 0:
        warnings.append(f"存在低置信度页面元素 {low_confidence_elements} 个。")
        evidence.append(f"页面分析识别到低置信度元素 {low_confidence_elements} 个。")
    if semantic_requires_review:
        warnings.append("页面语义摘要仍要求人工复核。")
        evidence.append(
            f"页面语义为 page_type={semantic_page_type} / domain={semantic_business_domain} / goal={semantic_primary_goal}，当前仍要求人工复核。"
        )
    elif semantic_page_type != "unknown":
        evidence.append(
            f"页面语义判定为 {semantic_page_type}，业务域={semantic_business_domain}，主目标={semantic_primary_goal}。"
        )
    if warn_on_pending_test_points and pending_test_points > 0:
        warnings.append(f"存在待确认测试点 {pending_test_points} 个。")
        evidence.append(f"测试点层存在待确认项 {pending_test_points} 个。")
    if skip_suggestions > 0:
        warnings.append(f"存在建议跳过测试点 {skip_suggestions} 个。")
        evidence.append(f"测试点层存在建议跳过项 {skip_suggestions} 个。")
    if dependency_review_points > 0:
        evidence.append(f"共有 {dependency_review_points} 个测试点消费了页面元素依赖传播结果。")
    if warn_on_low_confidence_dependency_points and low_confidence_dependency_points > 0:
        warnings.append(f"存在受低置信度元素影响的测试点 {low_confidence_dependency_points} 个。")
        evidence.append(f"低置信度元素影响测试点 {low_confidence_dependency_points} 个。")
    if dependency_skip_points > 0:
        evidence.append(f"其中 {dependency_skip_points} 个 skip 建议由依赖传播直接触发。")
    if warn_on_pending_reviews and pending_sections > 0:
        warnings.append(f"存在待确认分组 {pending_sections} 个。")
        evidence.append(f"当前仍有待确认分组 {pending_sections} 个。")
    if asset_selection_state == "blocked":
        blockers.append("测试点资产选择摘要判定为 blocked。")
        evidence.extend([f"测试点资产选择摘要：{reason}" for reason in asset_selection_reasons[:3]] or ["测试点资产选择摘要为 blocked。"])
    elif asset_selection_state == "needs_review":
        warnings.append("测试点资产选择摘要要求人工复核。")
        evidence.extend([f"测试点资产选择摘要：{reason}" for reason in asset_selection_reasons[:3]] or ["测试点资产选择摘要为 needs_review。"])
    elif asset_selection_state == "ready" and asset_ready_for_regression:
        evidence.append("测试点资产选择摘要判定可直接进入回归。")

    if isinstance(risk_report, dict) and risk_report:
        risk_gate = str(risk_report.get("gate_decision", "")).strip().lower()
        if block_on_risk_block and risk_gate == "block":
            blockers.append("风险评估 gate_decision=block。")
            evidence.append("风险评估结果为 block，门禁按规则阻断。")
        elif risk_gate and risk_gate != "allow":
            warnings.append(f"风险评估 gate_decision={risk_gate}。")
            evidence.append(f"风险评估结果为 {risk_gate}。")

    if blockers:
        decision = "block"
    elif warnings:
        decision = "manual_review"
    else:
        decision = "allow"

    return {
        "version": "ExecutionGateV1",
        "page": page,
        "decision": decision,
        "effective_decision": decision,
        "decision_source": "system",
        "requires_review": decision != "allow",
        "blockers": dedup_keep_order(blockers),
        "warnings": dedup_keep_order(warnings),
        "evidence": dedup_keep_order(evidence),
        "metrics": {
            "status": status_value,
            "coverage_status": coverage_status,
            "low_confidence_elements": low_confidence_elements,
            "semantic_requires_review": semantic_requires_review,
            "semantic_page_type": semantic_page_type,
            "semantic_business_domain": semantic_business_domain,
            "missing_page_object_elements": missing_required,
            "pending_test_points": pending_test_points,
            "skip_suggestions": skip_suggestions,
            "dependency_review_points": dependency_review_points,
            "low_confidence_dependency_points": low_confidence_dependency_points,
            "missing_dependency_points": missing_dependency_points,
            "dependency_skip_points": dependency_skip_points,
            "pending_review_sections": pending_sections,
            "asset_selection_state": asset_selection_state or "unknown",
            "asset_ready_for_regression": asset_ready_for_regression,
        },
        "config_snapshot": {
            "block_missing_required_threshold": block_missing_required_threshold,
            "block_missing_dependency_points_threshold": block_missing_dependency_points_threshold,
            "block_on_failed_status": block_on_failed_status,
            "block_on_risk_block": block_on_risk_block,
            "warn_on_pending_reviews": warn_on_pending_reviews,
            "warn_on_low_confidence_elements": warn_on_low_confidence_elements,
            "warn_on_pending_test_points": warn_on_pending_test_points,
            "warn_on_low_confidence_dependency_points": warn_on_low_confidence_dependency_points,
        },
        "test_point_asset_context": {
            "asset_id": _safe_case_id(str(asset_context.get("asset_id", "")).strip()) if str(asset_context.get("asset_id", "")).strip() else "",
            "selection_state": asset_selection_state or "unknown",
            "selection_reasons": dedup_keep_order([str(item).strip() for item in asset_selection_reasons if str(item).strip()])[:5],
            "review_status": str((asset_traceability_summary.get("review", {}) if isinstance(asset_traceability_summary.get("review"), dict) else {}).get("test_point_status", "")).strip() or "unknown",
            "coverage_status": str((asset_traceability_summary.get("coverage", {}) if isinstance(asset_traceability_summary.get("coverage"), dict) else {}).get("asset_status", "")).strip() or "unknown",
        },
        "manual_decision": {},
    }
