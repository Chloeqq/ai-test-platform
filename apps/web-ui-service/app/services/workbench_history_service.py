from __future__ import annotations

from typing import Any, Callable

from . import workbench_quality_gate_summary_service


PageNormalizer = Callable[[str], str]
SnapshotResolver = Callable[[str], dict[str, Any]]


def _enrich_history_row(
    item: dict[str, Any],
    *,
    resolve_governance_snapshot: SnapshotResolver,
    resolve_failure_snapshot: SnapshotResolver,
) -> dict[str, Any]:
    row = dict(item)
    run_id = str(row.get("run_id", "")).strip()
    governance_snapshot = resolve_governance_snapshot(run_id) if run_id else {}
    if governance_snapshot:
        risk_summary = governance_snapshot.get("risk_summary", {}) if isinstance(governance_snapshot.get("risk_summary"), dict) else {}
        self_healing_summary = governance_snapshot.get("self_healing_summary", {}) if isinstance(governance_snapshot.get("self_healing_summary"), dict) else {}
        page_semantic_summary = governance_snapshot.get("page_semantic_summary", {}) if isinstance(governance_snapshot.get("page_semantic_summary"), dict) else {}
        if risk_summary:
            row.setdefault("risk_summary", risk_summary)
        if self_healing_summary:
            row.setdefault("self_healing_summary", self_healing_summary)
        if page_semantic_summary:
            row.setdefault("page_semantic_summary", page_semantic_summary)

    run_failure = resolve_failure_snapshot(run_id) if run_id else {}
    if run_failure:
        analysis = run_failure.get("analysis", {}) if isinstance(run_failure.get("analysis"), dict) else {}
        row.setdefault("failure_analysis", analysis)
        row.setdefault("failure_source", analysis.get("failure_source", ""))
        row.setdefault("failure_source_reason", analysis.get("failure_source_reason", ""))
        row.setdefault("source_evidence", analysis.get("source_evidence", []))
        row.setdefault("requires_manual_review", bool(analysis.get("requires_manual_review", False)))
        if not str(row.get("detail_summary", "")).strip():
            row["detail_summary"] = f"失败来源={analysis.get('failure_source', '-') or '-'}；人工复核={'是' if analysis.get('requires_manual_review') else '否'}"

    if not str(row.get("detail_summary", "")).strip():
        risk_summary = row.get("risk_summary", {}) if isinstance(row.get("risk_summary"), dict) else {}
        self_healing_summary = row.get("self_healing_summary", {}) if isinstance(row.get("self_healing_summary"), dict) else {}
        if risk_summary:
            row["detail_summary"] = (
                f"风险={risk_summary.get('risk_level', '-') or '-'}"
                f"；门禁={risk_summary.get('gate_decision', '-') or '-'}"
                f"；主因子={((risk_summary.get('top_factor', {}) if isinstance(risk_summary.get('top_factor'), dict) else {}).get('factor', '-')) or '-'}"
            )
        elif isinstance(row.get("page_semantic_summary"), dict) and row.get("page_semantic_summary"):
            semantic_summary = row.get("page_semantic_summary", {})
            row["detail_summary"] = (
                f"语义={semantic_summary.get('page_type', '-') or '-'}"
                f"；领域={semantic_summary.get('business_domain', '-') or '-'}"
                f"；目标={semantic_summary.get('primary_goal', '-') or '-'}"
            )
        elif self_healing_summary:
            row["detail_summary"] = (
                f"自愈状态={self_healing_summary.get('status', '-') or '-'}"
                f"；边界={((self_healing_summary.get('boundary', {}) if isinstance(self_healing_summary.get('boundary'), dict) else {}).get('advice_type', '-')) or '-'}"
            )
    return row


def _matches_history_filters(
    row: dict[str, Any],
    *,
    action_filter: str,
    actor_filter: str,
    status_filter: str,
    keyword_filter: str,
    risk_gate_decision_filter: str,
    self_healing_status_filter: str,
    normalize_page_slug: PageNormalizer,
) -> bool:
    action_value = str(row.get("action", "")).strip().lower()
    status_value = str(row.get("status", "")).strip().lower()
    actor_value = str(row.get("actor_display") or row.get("confirmed_by") or "").strip().lower()
    risk_summary = row.get("risk_summary", {}) if isinstance(row.get("risk_summary"), dict) else {}
    self_healing_summary = row.get("self_healing_summary", {}) if isinstance(row.get("self_healing_summary"), dict) else {}
    risk_gate_value = str(risk_summary.get("gate_decision", "")).strip().lower()
    self_healing_status_value = str(self_healing_summary.get("status", "")).strip().lower()
    normalized_page = normalize_page_slug(str(row.get("page", "")).strip()) if str(row.get("page", "")).strip() else ""

    if action_filter and action_value != action_filter:
        return False
    if status_filter and status_value != status_filter:
        return False
    if actor_filter and actor_filter not in actor_value:
        return False
    if risk_gate_decision_filter and risk_gate_value != risk_gate_decision_filter:
        return False
    if self_healing_status_filter and self_healing_status_value != self_healing_status_filter:
        return False
    if keyword_filter:
        haystack = [
            row.get("timestamp", ""),
            row.get("action", ""),
            row.get("case_id", ""),
            row.get("run_id", ""),
            row.get("page", ""),
            normalized_page,
            row.get("actor_display", ""),
            row.get("confirmed_by", ""),
            row.get("status", ""),
            row.get("detail_summary", ""),
            row.get("note", ""),
        ]
        haystack_text = " ".join(str(item or "").lower() for item in haystack)
        if keyword_filter not in haystack_text:
            return False
    return True


def _pick_top_bucket(counts: dict[str, int]) -> dict[str, Any]:
    if not counts:
        return {}
    key, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return {"value": key, "count": count}


def _sort_history_rows(rows: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    normalized_sort = str(sort or "timestamp_desc").strip().lower() or "timestamp_desc"
    if normalized_sort == "timestamp_asc":
        return sorted(rows, key=lambda row: str(row.get("timestamp", "")))
    if normalized_sort == "action_asc":
        return sorted(rows, key=lambda row: (str(row.get("action", "")), str(row.get("timestamp", ""))), reverse=False)
    if normalized_sort == "status_asc":
        return sorted(rows, key=lambda row: (str(row.get("status", "")), str(row.get("timestamp", ""))), reverse=False)
    if normalized_sort == "gate_asc":
        return sorted(
            rows,
            key=lambda row: (
                str((row.get("risk_summary", {}) if isinstance(row.get("risk_summary"), dict) else {}).get("gate_decision", "")),
                str(row.get("timestamp", "")),
            ),
            reverse=False,
        )
    if normalized_sort == "self_healing_asc":
        return sorted(
            rows,
            key=lambda row: (
                str((row.get("self_healing_summary", {}) if isinstance(row.get("self_healing_summary"), dict) else {}).get("status", "")),
                str(row.get("timestamp", "")),
            ),
            reverse=False,
        )
    return sorted(rows, key=lambda row: str(row.get("timestamp", "")), reverse=True)


def _paginate_rows(rows: list[dict[str, Any]], *, page: int, page_size: int) -> dict[str, Any]:
    total_items = len(rows)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    normalized_page = min(max(1, page), total_pages)
    start_index = (normalized_page - 1) * page_size
    page_items = rows[start_index:start_index + page_size]
    return {
        "items": page_items,
        "page": normalized_page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _build_history_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    risk_gate_counts: dict[str, int] = {}
    self_healing_status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    boundary_rejected_count = 0
    risk_requires_review_count = 0
    for row in rows:
        risk_summary = row.get("risk_summary", {}) if isinstance(row.get("risk_summary"), dict) else {}
        self_healing_summary = row.get("self_healing_summary", {}) if isinstance(row.get("self_healing_summary"), dict) else {}
        action_value = str(row.get("action", "")).strip().lower()
        risk_gate_value = str(risk_summary.get("gate_decision", "")).strip().lower()
        self_healing_status_value = str(self_healing_summary.get("status", "")).strip().lower()
        if action_value:
            action_counts[action_value] = action_counts.get(action_value, 0) + 1
        if risk_gate_value:
            risk_gate_counts[risk_gate_value] = risk_gate_counts.get(risk_gate_value, 0) + 1
        if self_healing_status_value:
            self_healing_status_counts[self_healing_status_value] = self_healing_status_counts.get(self_healing_status_value, 0) + 1
        if bool(risk_summary.get("requires_review", False)):
            risk_requires_review_count += 1
        boundary = self_healing_summary.get("boundary", {}) if isinstance(self_healing_summary.get("boundary"), dict) else {}
        if self_healing_status_value == "rejected" or (boundary and boundary.get("allowed") is False):
            boundary_rejected_count += 1
    return {
        "total_items": len(rows),
        "risk_gate_counts": risk_gate_counts,
        "self_healing_status_counts": self_healing_status_counts,
        "action_counts": action_counts,
        "risk_requires_review_count": risk_requires_review_count,
        "boundary_rejected_count": boundary_rejected_count,
        "top_action": _pick_top_bucket(action_counts),
        "top_risk_gate": _pick_top_bucket(risk_gate_counts),
        "top_self_healing_status": _pick_top_bucket(self_healing_status_counts),
    }


def list_history(
    history_items: list[dict[str, Any]],
    *,
    resolve_governance_snapshot: SnapshotResolver | None = None,
    resolve_failure_snapshot: SnapshotResolver | None = None,
    normalize_page_slug: PageNormalizer | None = None,
    limit: int = 500,
    page: int = 1,
    page_size: int = 50,
    keyword: str = "",
    sort: str = "timestamp_desc",
    action: str = "",
    actor: str = "",
    status: str = "",
    risk_gate_decision: str = "",
    self_healing_status: str = "",
) -> dict[str, Any]:
    normalize_page = normalize_page_slug or (lambda value: str(value).strip().lower())
    resolve_governance = resolve_governance_snapshot or (lambda _run_id: {})
    resolve_failure = resolve_failure_snapshot or (lambda _run_id: {})

    normalized_limit = max(1, int(limit or 500))
    normalized_page = max(1, int(page or 1))
    normalized_page_size = min(max(1, int(page_size or 50)), 100)
    keyword_filter = str(keyword).strip().lower()
    action_filter = str(action).strip().lower()
    actor_filter = str(actor).strip().lower()
    status_filter = str(status).strip().lower()
    risk_gate_decision_filter = str(risk_gate_decision).strip().lower()
    self_healing_status_filter = str(self_healing_status).strip().lower()

    rows: list[dict[str, Any]] = []
    for item in history_items:
        if not isinstance(item, dict):
            continue
        row = _enrich_history_row(
            item,
            resolve_governance_snapshot=resolve_governance,
            resolve_failure_snapshot=resolve_failure,
        )
        if not _matches_history_filters(
            row,
            action_filter=action_filter,
            actor_filter=actor_filter,
            status_filter=status_filter,
            keyword_filter=keyword_filter,
            risk_gate_decision_filter=risk_gate_decision_filter,
            self_healing_status_filter=self_healing_status_filter,
            normalize_page_slug=normalize_page,
        ):
            continue
        rows.append(row)
        if len(rows) >= normalized_limit:
            break

    sorted_rows = _sort_history_rows(rows, sort)
    summary = _build_history_summary(sorted_rows)
    pagination = _paginate_rows(sorted_rows, page=normalized_page, page_size=normalized_page_size)
    return {
        "items": pagination["items"],
        "summary": summary,
        "pagination": {
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "total_items": pagination["total_items"],
            "total_pages": pagination["total_pages"],
        },
        "meta": {
            "keyword": keyword_filter,
            "sort": str(sort or "timestamp_desc").strip().lower() or "timestamp_desc",
            "limit": normalized_limit,
        },
    }


def summarize_quality_gate_events(
    history_items: list[dict[str, Any]],
    *,
    limit: int = 500,
    alert_code: str = "",
    page: str = "",
    normalize_page_slug: PageNormalizer | None = None,
) -> dict[str, Any]:
    return workbench_quality_gate_summary_service.summarize_quality_gate_events(
        history_items,
        limit=limit,
        alert_code=alert_code,
        page=page,
        normalize_page_slug=normalize_page_slug,
    )
