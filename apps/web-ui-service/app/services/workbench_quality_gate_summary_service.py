from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from datetime_compat import UTC

PageNormalizer = Callable[[str], str]


def _extract_history_quality_gate(entry: dict[str, Any]) -> dict[str, Any] | None:
    direct = entry.get("quality_gate")
    if isinstance(direct, dict):
        return direct
    return None


def _quality_gate_event_from_history(entry: dict[str, Any]) -> dict[str, Any] | None:
    gate = _extract_history_quality_gate(entry)
    if not isinstance(gate, dict):
        return None
    raw_blockers = gate.get("blockers")
    blockers = [item for item in raw_blockers if isinstance(item, dict)] if isinstance(raw_blockers, list) else []
    decision = str(gate.get("decision", "")).strip().lower()
    if not decision:
        decision = "block" if blockers else "allow"
    return {
        "timestamp": str(entry.get("timestamp", "")).strip() or datetime.now(UTC).isoformat(),
        "action": str(entry.get("action", "")).strip(),
        "case_id": str(entry.get("case_id", "")).strip(),
        "page": str(entry.get("page", "")).strip(),
        "decision": decision,
        "stage": str(gate.get("stage", "")).strip() or "orchestrate",
        "blockers": blockers,
    }


def _quality_gate_remediation_for_code(code: str) -> dict[str, str]:
    normalized = str(code).strip().lower()
    catalog: dict[str, dict[str, str]] = {
        "low_parse_confidence": {
            "title": "补充需求上下文并降低歧义",
            "suggestion": "补齐业务目标、前置条件、预期结果，并补充 PRD/OpenAPI/Git Diff 至少一种输入源。",
            "owner": "产品/测试设计",
            "priority": "P0",
        },
        "insufficient_test_intents": {
            "title": "增加关键测试点覆盖",
            "suggestion": "明确主流程、异常流程、权限边界，确保至少覆盖 1 个核心功能测试点。",
            "owner": "测试设计",
            "priority": "P0",
        },
        "high_ambiguity_present": {
            "title": "先消歧再生成",
            "suggestion": "针对高歧义条目逐条澄清，至少明确判定标准、阈值和业务规则。",
            "owner": "产品/测试设计",
            "priority": "P0",
        },
        "coverage_gap_ratio_high": {
            "title": "补齐可追溯覆盖",
            "suggestion": "将未映射需求项补充为结构化测试点，降低 coverage gap 后再触发生成。",
            "owner": "测试设计",
            "priority": "P1",
        },
        "missing_design_input": {
            "title": "提供可设计输入",
            "suggestion": "至少填写需求描述或输入源内容，避免空输入触发无效生成。",
            "owner": "提测人",
            "priority": "P0",
        },
        "missing_page_resolution": {
            "title": "明确目标页面",
            "suggestion": "补充页面标识或 URL，确保能解析出有效 page slug。",
            "owner": "提测人",
            "priority": "P0",
        },
    }
    return catalog.get(
        normalized,
        {
            "title": "补充输入并重试",
            "suggestion": "检查需求完整性、页面上下文与输入源格式后重试。",
            "owner": "测试设计",
            "priority": "P1",
        },
    )


def summarize_quality_gate_events(
    history_items: list[dict[str, Any]],
    *,
    limit: int = 500,
    alert_code: str = "",
    page: str = "",
    normalize_page_slug: PageNormalizer | None = None,
) -> dict[str, Any]:
    normalize_page = normalize_page_slug or (lambda value: str(value).strip().lower())
    normalized_alert = str(alert_code).strip().lower()
    normalized_page = normalize_page(page) if str(page).strip() else ""
    normalized_limit = max(1, int(limit or 500))

    events = [_quality_gate_event_from_history(item) for item in history_items[:normalized_limit]]

    def _row_matches(row: dict[str, Any]) -> bool:
        if normalized_page:
            row_page = normalize_page(str(row.get("page", "")).strip()) if str(row.get("page", "")).strip() else ""
            if row_page != normalized_page:
                return False
        if normalized_alert:
            blockers = row.get("blockers")
            blocker_rows = blockers if isinstance(blockers, list) else []
            for blocker in blocker_rows:
                if not isinstance(blocker, dict):
                    continue
                alert = str(blocker.get("alert_code", "")).strip().lower()
                code = str(blocker.get("code", "")).strip().lower()
                if normalized_alert in {alert, code}:
                    return True
            return False
        return True

    rows = [item for item in events if isinstance(item, dict) and _row_matches(item)]

    total_events = len(rows)
    blocked_events = [row for row in rows if str(row.get("decision", "")).lower() == "block"]
    allow_events = [row for row in rows if str(row.get("decision", "")).lower() == "allow"]

    blocker_counter: dict[str, dict[str, Any]] = {}
    alert_details_map: dict[str, dict[str, Any]] = {}
    for event in blocked_events:
        for blocker in event.get("blockers", []):
            code = str(blocker.get("alert_code", "")).strip() or str(blocker.get("code", "")).strip() or "UNKNOWN"
            row = blocker_counter.get(code)
            if row is None:
                row = {
                    "alert_code": code,
                    "code": str(blocker.get("code", "")).strip() or code,
                    "category": str(blocker.get("category", "unknown")).strip() or "unknown",
                    "severity": str(blocker.get("severity", "medium")).strip() or "medium",
                    "count": 0,
                }
                blocker_counter[code] = row
            row["count"] = int(row.get("count", 0)) + 1

            detail = alert_details_map.get(code)
            blocker_code = str(blocker.get("code", "")).strip() or code
            if detail is None:
                remediation = _quality_gate_remediation_for_code(blocker_code)
                detail = {
                    "alert_code": code,
                    "code": blocker_code,
                    "category": str(blocker.get("category", "unknown")).strip() or "unknown",
                    "severity": str(blocker.get("severity", "medium")).strip() or "medium",
                    "count": 0,
                    "remediation": remediation,
                    "samples": [],
                }
                alert_details_map[code] = detail
            detail["count"] = int(detail.get("count", 0)) + 1
            samples = detail.get("samples")
            if isinstance(samples, list) and len(samples) < 20:
                samples.append(
                    {
                        "timestamp": event.get("timestamp", ""),
                        "action": event.get("action", ""),
                        "case_id": event.get("case_id", ""),
                        "page": event.get("page", ""),
                        "stage": event.get("stage", ""),
                        "message": str(blocker.get("message", "")).strip(),
                        "value": blocker.get("value"),
                        "threshold": blocker.get("threshold"),
                    }
                )

    blocker_distribution = sorted(
        blocker_counter.values(),
        key=lambda item: (-int(item.get("count", 0)), str(item.get("alert_code", ""))),
    )
    alert_details = sorted(
        alert_details_map.values(),
        key=lambda item: (-int(item.get("count", 0)), str(item.get("alert_code", ""))),
    )

    trend_map: dict[str, dict[str, int]] = defaultdict(lambda: {"allow": 0, "block": 0})
    for row in rows:
        timestamp = str(row.get("timestamp", "")).strip()
        day_key = timestamp[:10] if len(timestamp) >= 10 else ""
        if not day_key:
            continue
        decision = str(row.get("decision", "")).strip().lower()
        if decision == "block":
            trend_map[day_key]["block"] += 1
        elif decision == "allow":
            trend_map[day_key]["allow"] += 1
    trend = [
        {"date": day_key, "allow": data["allow"], "block": data["block"]}
        for day_key, data in sorted(trend_map.items())
    ][-14:]

    parsed_rows: list[tuple[dict[str, Any], datetime]] = []
    latest_seen: datetime | None = None
    for row in rows:
        timestamp = str(row.get("timestamp", "")).strip()
        if not timestamp:
            continue
        parsed_text = timestamp.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(parsed_text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
        except Exception:
            continue
        parsed_rows.append((row, parsed))
        if latest_seen is None or parsed > latest_seen:
            latest_seen = parsed

    anchor_source = latest_seen or datetime.now(UTC)
    anchor_utc = anchor_source.replace(minute=0, second=0, microsecond=0)
    hour_start = anchor_utc - timedelta(hours=23)
    hourly_buckets: dict[datetime, dict[str, int]] = {
        hour_start + timedelta(hours=idx): {"allow": 0, "block": 0}
        for idx in range(24)
    }
    for row, parsed in parsed_rows:
        hour_key = parsed.replace(minute=0, second=0, microsecond=0)
        if hour_key not in hourly_buckets:
            continue
        decision = str(row.get("decision", "")).strip().lower()
        if decision == "block":
            hourly_buckets[hour_key]["block"] += 1
        elif decision == "allow":
            hourly_buckets[hour_key]["allow"] += 1
    decision_trend_24h = []
    for hour in sorted(hourly_buckets):
        allow_count = hourly_buckets[hour]["allow"]
        block_count = hourly_buckets[hour]["block"]
        total_count = allow_count + block_count
        decision_trend_24h.append(
            {
                "hour": hour.strftime("%H:%M"),
                "allow": allow_count,
                "block": block_count,
                "total": total_count,
                "block_rate": round(block_count / max(1, total_count), 3) if total_count else 0.0,
            }
        )
    blocked_24h = 0
    total_24h = 0
    for item in decision_trend_24h:
        block_value = item.get("block")
        total_value = item.get("total")
        if isinstance(block_value, int):
            blocked_24h += block_value
        if isinstance(total_value, int):
            total_24h += total_value
    block_rate_24h = round(blocked_24h / max(1, total_24h), 3) if total_24h else 0.0

    blocker_24h_counter: dict[str, int] = defaultdict(int)
    page_24h_counter: dict[str, int] = defaultdict(int)
    blocked_event_parsed_rows = [(row, parsed) for row, parsed in parsed_rows if row in blocked_events]
    for row, parsed in blocked_event_parsed_rows:
        if parsed < hour_start:
            continue
        page_key = normalize_page(str(row.get("page", "")).strip()) if str(row.get("page", "")).strip() else ""
        if page_key:
            page_24h_counter[page_key] += 1
        for blocker in row.get("blockers", []):
            code = str(blocker.get("alert_code", "")).strip() or str(blocker.get("code", "")).strip() or "UNKNOWN"
            blocker_24h_counter[code] += 1
    top_alert_24h = ""
    top_alert_24h_count = 0
    for code, count in blocker_24h_counter.items():
        if count > top_alert_24h_count:
            top_alert_24h = code
            top_alert_24h_count = count
    top_page_24h = ""
    top_page_24h_count = 0
    for page_key, count in page_24h_counter.items():
        if count > top_page_24h_count:
            top_page_24h = page_key
            top_page_24h_count = count

    recent_blocked = []
    for row in blocked_events[:20]:
        codes = []
        for blocker in row.get("blockers", []):
            alert = str(blocker.get("alert_code", "")).strip()
            if alert:
                codes.append(alert)
        recent_blocked.append(
            {
                "timestamp": row.get("timestamp", ""),
                "action": row.get("action", ""),
                "case_id": row.get("case_id", ""),
                "page": row.get("page", ""),
                "stage": row.get("stage", ""),
                "blocker_alert_codes": codes,
            }
        )

    block_rate = round(len(blocked_events) / max(1, total_events), 3) if total_events else 0.0
    return {
        "total_events": total_events,
        "allow_events": len(allow_events),
        "blocked_events": len(blocked_events),
        "block_rate": block_rate,
        "summary_24h": {
            "total_events": total_24h,
            "blocked_events": blocked_24h,
            "block_rate": block_rate_24h,
            "top_alert_code": top_alert_24h,
            "top_alert_count": top_alert_24h_count,
            "top_page": top_page_24h,
            "top_page_count": top_page_24h_count,
        },
        "blocker_distribution": blocker_distribution,
        "alert_details": alert_details,
        "decision_trend": trend,
        "decision_trend_24h": decision_trend_24h,
        "recent_blocked": recent_blocked,
        "updated_at": datetime.now(UTC).isoformat(),
    }
