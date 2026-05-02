from __future__ import annotations

import json
import shutil
from datetime_compat import UTC
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Callable
import uuid
from shared_backend.case_ids import normalize_case_id


ReadDefectItems = Callable[[], list[dict[str, Any]]]
WriteDefectItems = Callable[[list[dict[str, Any]]], None]
CollectExecutionRecords = Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
NormalizeExecutionMeta = Callable[[dict[str, Any] | None], dict[str, Any]]
CollectFailureEntries = Callable[[], list[dict[str, Any]]]
CollectFailureEntriesWithMeta = Callable[[], tuple[list[dict[str, Any]], dict[str, Any]]]
NormalizeFailureAnalysis = Callable[[dict[str, Any] | None], dict[str, Any]]
NormalizeFailureEvidenceMeta = Callable[[dict[str, Any] | None], dict[str, Any]]
RunCommand = Callable[..., Any]
ReadAllureSummary = Callable[[], dict[str, Any]]
EnsureAllureSnapshot = Callable[[int], str]
GetAllureIndexVersion = Callable[[], int]
ClampConfidence = Callable[[Any], float]
FindRunItem = Callable[[str], dict[str, Any] | None]
IsWithin = Callable[[Path, Path], bool]
NormalizeFailureEntry = Callable[[dict[str, Any] | None], dict[str, Any]]
BuildRiskReportSummary = Callable[[dict[str, Any] | None], dict[str, Any]]
BuildSelfHealingSummary = Callable[..., dict[str, Any]]
BuildPageSemanticSummary = Callable[[dict[str, Any]], dict[str, Any]]
NormalizeEvidenceManifestPayload = Callable[[dict[str, Any]], dict[str, Any]]
ResolveManifestEntries = Callable[[Any, Path], list[Path]]
LoadExecutionRecordPayload = Callable[[Path], dict[str, Any]]
ParseAnalysisFile = Callable[[Path], dict[str, Any]]
ResolveRunFailureSnapshot = Callable[[str], dict[str, Any]]
ReviewerDisplayName = Callable[[dict[str, Any]], str]
NowIsoFn = Callable[[], str]
ReadJsonList = Callable[[Path], list[dict[str, Any]]]
WriteJsonList = Callable[[Path, list[dict[str, Any]]], None]


def apply_no_store_headers(response: Any) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def collect_failure_entries_with_meta(
    *,
    compat_scan_enabled: bool,
    artifact_roots: list[Path],
    logger: Any,
    normalize_evidence_manifest_payload: NormalizeEvidenceManifestPayload,
    resolve_manifest_entries: ResolveManifestEntries,
    load_execution_record_payload: LoadExecutionRecordPayload,
    parse_analysis_file: ParseAnalysisFile,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    consumed_analysis_paths: set[Path] = set()
    compat_used_count = 0
    compat_disabled_skipped = 0
    invalid_manifest_count = 0
    missing_manifest_count = 0
    safe_logger = logger if logger is not None else logging.getLogger(__name__)

    for artifact_root in artifact_roots:
        if not artifact_root.exists():
            continue
        for manifest_path in sorted(artifact_root.rglob("evidence_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
            except Exception:
                safe_logger.warning("invalid evidence_manifest.json at %s; keep compatibility scan path", manifest_path)
                invalid_manifest_count += 1
                continue
            manifest = normalize_evidence_manifest_payload(raw_manifest)
            manifest_root = manifest_path.parent
            analysis_paths = resolve_manifest_entries(manifest.get("analysis_files"), manifest_root)
            if not analysis_paths:
                continue
            suggestion_paths = resolve_manifest_entries(manifest.get("suggestion_files"), manifest_root)
            record_paths = resolve_manifest_entries(manifest.get("execution_record_files"), manifest_root)
            for index, analysis_path in enumerate(analysis_paths):
                resolved_analysis_path = analysis_path.resolve()
                if resolved_analysis_path in consumed_analysis_paths:
                    continue
                consumed_analysis_paths.add(resolved_analysis_path)
                case_dir = analysis_path.parent
                suggestion_path = suggestion_paths[index] if index < len(suggestion_paths) else (suggestion_paths[0] if suggestion_paths else case_dir / "suggestion.json")
                execution_record_path = record_paths[index] if index < len(record_paths) else (record_paths[0] if record_paths else case_dir / "execution_record.json")
                execution_record = load_execution_record_payload(execution_record_path)
                case_id = normalize_case_id(str(execution_record.get("case_id", case_dir.name)).strip() or case_dir.name)
                case_title = str(execution_record.get("case_title", case_id)).strip() or case_id
                finished_at = str(execution_record.get("finished_at", "")).strip() or datetime.fromtimestamp(analysis_path.stat().st_mtime, tz=UTC).isoformat()
                screenshot_path = case_dir / "failed.png"
                html_path = case_dir / "page.html"
                meta_path = case_dir / "meta.txt"
                video_candidates = list(case_dir.glob("*.webm"))
                video_path = max(video_candidates, key=lambda p: p.stat().st_mtime) if video_candidates else None
                analysis = parse_analysis_file(analysis_path)
                record_metadata = _dict_value(execution_record.get("metadata"))
                record_failed_step = _dict_value(record_metadata.get("failed_step"))
                record_element_impact = _dict_value(record_metadata.get("element_impact"))
                if record_failed_step and not _dict_value(analysis.get("failed_step")):
                    analysis["failed_step"] = record_failed_step
                if record_element_impact and not _dict_value(analysis.get("element_impact")):
                    analysis["element_impact"] = record_element_impact
                suggestion_payload: dict[str, Any] = {}
                if suggestion_path.exists():
                    try:
                        suggestion_payload = json.loads(suggestion_path.read_text(encoding="utf-8")) or {}
                    except Exception:
                        suggestion_payload = {}
                entries.append(
                    {
                        "case_id": case_id,
                        "case_title": case_title,
                        "finished_at": finished_at,
                        "analysis": analysis,
                        "suggestion": suggestion_payload,
                        "artifact_dir": str(case_dir.resolve()),
                        "analysis_path": str(analysis_path.resolve()),
                        "suggestion_path": str(suggestion_path.resolve()) if suggestion_path.exists() else "",
                        "screenshot_path": str(screenshot_path.resolve()) if screenshot_path.exists() else "",
                        "html_path": str(html_path.resolve()) if html_path.exists() else "",
                        "meta_path": str(meta_path.resolve()) if meta_path.exists() else "",
                        "video_path": str(video_path.resolve()) if video_path else "",
                        "evidence_source": "manifest",
                        "manifest_path": str(manifest_path.resolve()),
                        "failed_step": _dict_value(analysis.get("failed_step")),
                        "element_impact": _dict_value(analysis.get("element_impact")),
                    }
                )
        for analysis_path in sorted(artifact_root.rglob("analysis.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
            resolved_analysis_path = analysis_path.resolve()
            if resolved_analysis_path in consumed_analysis_paths:
                continue
            missing_manifest_count += 1
            compat_disabled_skipped += 1
            safe_logger.warning(
                "evidence_manifest missing for %s; strict manifest-first mode skips this entry",
                analysis_path.parent,
            )
            continue
    entries.sort(key=lambda item: item.get("finished_at", ""), reverse=True)
    trimmed = entries[:200]
    manifest_count = sum(1 for item in trimmed if str(item.get("evidence_source", "")).strip().lower() == "manifest")
    compat_count = sum(1 for item in trimmed if str(item.get("evidence_source", "")).strip().lower() == "compat_scan")
    warnings: list[str] = []
    if invalid_manifest_count > 0:
        warnings.append(f"检测到 {invalid_manifest_count} 个无效 evidence_manifest.json，已跳过。")
    if compat_count > 0:
        warnings.append(f"检测到 {compat_count} 条证据通过 compat_scan 读取，建议补齐 evidence_manifest。")
    if compat_disabled_skipped > 0:
        warnings.append(f"兼容扫描已禁用，跳过 {compat_disabled_skipped} 条缺少 manifest 的证据。")

    total_visible_entries = manifest_count + compat_count
    manifest_first_ratio = round((manifest_count / total_visible_entries), 3) if total_visible_entries else 1.0
    compat_scan_ratio = round((compat_count / total_visible_entries), 3) if total_visible_entries else 0.0
    policy_mode = "strict"
    if compat_count > 0:
        health = "degraded"
    elif compat_disabled_skipped > 0 or invalid_manifest_count > 0:
        health = "warning"
    else:
        health = "healthy"

    meta = {
        "compat_scan_enabled": False,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_entry_count": manifest_count,
        "compat_scan_entry_count": compat_count,
        "compat_scan_used_count": compat_used_count,
        "compat_scan_skipped_count": compat_disabled_skipped,
        "invalid_manifest_count": invalid_manifest_count,
        "missing_manifest_count": missing_manifest_count,
        "total_visible_entries": total_visible_entries,
        "manifest_first_ratio": manifest_first_ratio,
        "compat_scan_ratio": compat_scan_ratio,
        "warnings": warnings,
    }
    return trimmed, meta


def collect_failure_entries(*, collect_failure_entries_with_meta_fn: Callable[[], tuple[list[dict[str, Any]], dict[str, Any]]]) -> list[dict[str, Any]]:
    entries, _meta = collect_failure_entries_with_meta_fn()
    return entries


def normalize_failure_evidence_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    source = meta if isinstance(meta, dict) else {}
    compat_scan_enabled = bool(source.get("compat_scan_enabled", True))
    manifest_entry_count = int(source.get("manifest_entry_count", 0) or 0)
    compat_scan_entry_count = int(source.get("compat_scan_entry_count", 0) or 0)
    compat_scan_used_count = int(source.get("compat_scan_used_count", compat_scan_entry_count) or 0)
    compat_scan_skipped_count = int(source.get("compat_scan_skipped_count", 0) or 0)
    invalid_manifest_count = int(source.get("invalid_manifest_count", 0) or 0)
    missing_manifest_count = int(source.get("missing_manifest_count", 0) or 0)
    total_visible_entries = int(source.get("total_visible_entries", manifest_entry_count + compat_scan_entry_count) or 0)
    manifest_first_ratio = source.get("manifest_first_ratio")
    if manifest_first_ratio is None:
        manifest_first_ratio = round((manifest_entry_count / total_visible_entries), 3) if total_visible_entries else 1.0
    compat_scan_ratio = source.get("compat_scan_ratio")
    if compat_scan_ratio is None:
        compat_scan_ratio = round((compat_scan_entry_count / total_visible_entries), 3) if total_visible_entries else 0.0
    policy_mode = str(source.get("policy_mode", "compat" if compat_scan_enabled else "strict")).strip() or (
        "compat" if compat_scan_enabled else "strict"
    )
    health = str(source.get("health", "")).strip().lower()
    if not health:
        if compat_scan_entry_count > 0:
            health = "degraded"
        elif compat_scan_skipped_count > 0 or invalid_manifest_count > 0:
            health = "warning"
        else:
            health = "healthy"
    warnings_raw = source.get("warnings")
    warnings = [str(item).strip() for item in warnings_raw] if isinstance(warnings_raw, list) else []
    warnings = [item for item in warnings if item]
    return {
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_entry_count": manifest_entry_count,
        "compat_scan_entry_count": compat_scan_entry_count,
        "compat_scan_used_count": compat_scan_used_count,
        "compat_scan_skipped_count": compat_scan_skipped_count,
        "invalid_manifest_count": invalid_manifest_count,
        "missing_manifest_count": missing_manifest_count,
        "total_visible_entries": total_visible_entries,
        "manifest_first_ratio": float(manifest_first_ratio),
        "compat_scan_ratio": float(compat_scan_ratio),
        "warnings": warnings,
    }


def normalize_execution_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    source = meta if isinstance(meta, dict) else {}
    compat_scan_enabled = bool(source.get("compat_scan_enabled", True))
    manifest_record_count = int(source.get("manifest_record_count", 0) or 0)
    compat_scan_record_count = int(source.get("compat_scan_record_count", 0) or 0)
    runtime_realtime_count = int(source.get("runtime_realtime_count", 0) or 0)
    compat_scan_used_count = int(source.get("compat_scan_used_count", compat_scan_record_count) or 0)
    compat_scan_skipped_count = int(source.get("compat_scan_skipped_count", 0) or 0)
    invalid_manifest_count = int(source.get("invalid_manifest_count", 0) or 0)
    invalid_execution_record_count = int(source.get("invalid_execution_record_count", 0) or 0)
    missing_manifest_count = int(source.get("missing_manifest_count", 0) or 0)
    total_visible_records = int(
        source.get(
            "total_visible_records",
            manifest_record_count + compat_scan_record_count + runtime_realtime_count,
        )
        or 0
    )
    manifest_first_ratio = source.get("manifest_first_ratio")
    if manifest_first_ratio is None:
        manifest_first_ratio = round((manifest_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    compat_scan_ratio = source.get("compat_scan_ratio")
    if compat_scan_ratio is None:
        compat_scan_ratio = round((compat_scan_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    policy_mode = str(source.get("policy_mode", "compat" if compat_scan_enabled else "strict")).strip() or (
        "compat" if compat_scan_enabled else "strict"
    )
    health = str(source.get("health", "")).strip().lower()
    if not health:
        if compat_scan_record_count > 0:
            health = "degraded"
        elif compat_scan_skipped_count > 0 or invalid_manifest_count > 0 or invalid_execution_record_count > 0:
            health = "warning"
        else:
            health = "healthy"
    warnings_raw = source.get("warnings")
    warnings = [str(item).strip() for item in warnings_raw] if isinstance(warnings_raw, list) else []
    warnings = [item for item in warnings if item]
    readiness_score = max(
        0.0,
        min(
            1.0,
            round(
                float(manifest_first_ratio) * 0.55
                + (1 - float(compat_scan_ratio)) * 0.25
                + (0.0 if missing_manifest_count > 0 else 0.1)
                + (0.0 if invalid_manifest_count > 0 or invalid_execution_record_count > 0 else 0.1),
                3,
            ),
        ),
    )
    if health == "healthy" and compat_scan_record_count == 0 and missing_manifest_count == 0 and invalid_manifest_count == 0 and invalid_execution_record_count == 0:
        readiness_status = "ready"
    elif readiness_score >= 0.55:
        readiness_status = "caution"
    else:
        readiness_status = "blocked"
    if readiness_status == "ready":
        readiness_reason = "manifest-first 路径稳定，可评估更严格环境。"
    elif readiness_status == "caution":
        readiness_reason = "manifest-first 已占主导，但仍有 compat 路径需要清理。"
    else:
        readiness_reason = "仍存在缺失 manifest 或 invalid record，不建议关闭 compat_scan。"
    blocking_reasons: list[str] = []
    if missing_manifest_count > 0:
        blocking_reasons.append(f"missing_manifest={missing_manifest_count}")
    if invalid_manifest_count > 0:
        blocking_reasons.append(f"invalid_manifest={invalid_manifest_count}")
    if invalid_execution_record_count > 0:
        blocking_reasons.append(f"invalid_execution_record={invalid_execution_record_count}")
    if compat_scan_record_count > 0:
        blocking_reasons.append(f"compat_scan_record={compat_scan_record_count}")
    improvement_actions: list[str] = []
    if missing_manifest_count > 0:
        improvement_actions.append("补齐 evidence manifest 产物。")
    if compat_scan_record_count > 0:
        improvement_actions.append("减少 compat_scan 命中，优先消费 manifest-first execution record。")
    if invalid_manifest_count > 0 or invalid_execution_record_count > 0:
        improvement_actions.append("修复 invalid manifest / execution record 结构。")
    return {
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_record_count": manifest_record_count,
        "compat_scan_record_count": compat_scan_record_count,
        "runtime_realtime_count": runtime_realtime_count,
        "compat_scan_used_count": compat_scan_used_count,
        "compat_scan_skipped_count": compat_scan_skipped_count,
        "invalid_manifest_count": invalid_manifest_count,
        "invalid_execution_record_count": invalid_execution_record_count,
        "missing_manifest_count": missing_manifest_count,
        "total_visible_records": total_visible_records,
        "manifest_first_ratio": float(manifest_first_ratio),
        "compat_scan_ratio": float(compat_scan_ratio),
        "strict_mode_readiness": {
            "score": readiness_score,
            "status": readiness_status,
            "reason": readiness_reason,
            "can_disable_compat_scan": readiness_status == "ready",
            "blocking_reasons": blocking_reasons,
            "improvement_actions": improvement_actions[:3],
            "signals": {
                "manifest_record_count": manifest_record_count,
                "compat_scan_record_count": compat_scan_record_count,
                "missing_manifest_count": missing_manifest_count,
                "invalid_manifest_count": invalid_manifest_count,
                "invalid_execution_record_count": invalid_execution_record_count,
            },
        },
        "warnings": warnings,
    }


def normalize_failure_source_value(value: Any) -> str:
    source = str(value or "").strip().lower()
    if source in {"page_object", "page_analysis", "case_design", "app_bug", "environment", "unknown"}:
        return source
    return "unknown"


def sanitize_failure_source_feedback(
    feedback: dict[str, Any] | None,
    *,
    predicted_source: str,
) -> dict[str, Any]:
    item = feedback if isinstance(feedback, dict) else {}
    corrected_source = normalize_failure_source_value(
        item.get("corrected_failure_source", item.get("corrected_source", predicted_source))
    )
    decision = str(item.get("decision", "")).strip().lower()
    if decision not in {"accepted", "corrected", "rejected"}:
        decision = "accepted" if corrected_source == predicted_source else "corrected"
    if decision == "accepted":
        corrected_source = predicted_source
    if decision == "rejected" and corrected_source == predicted_source:
        corrected_source = ""
    reason = str(item.get("reason", item.get("note", ""))).strip()
    return {
        "decision": decision,
        "corrected_failure_source": corrected_source,
        "reason": reason,
    }


def record_failure_source_calibration_sample(
    *,
    review_record: dict[str, Any],
    feedback: dict[str, Any] | None = None,
    resolve_run_failure_snapshot_fn: ResolveRunFailureSnapshot,
    clamp_confidence: ClampConfidence,
    reviewer_display_name_fn: ReviewerDisplayName,
    now_iso_fn: NowIsoFn,
    read_json_list_fn: ReadJsonList,
    write_json_list_fn: WriteJsonList,
    calibration_file: Path,
) -> dict[str, Any]:
    review_type = str(review_record.get("review_type", "")).strip().lower()
    review_status = str(review_record.get("status", "")).strip().lower()
    if review_status != "confirmed":
        return {}
    if review_type != "risk" and not isinstance(feedback, dict):
        return {}

    run_id = str(review_record.get("run_id", "")).strip()
    if not run_id:
        return {}
    failure_snapshot = resolve_run_failure_snapshot_fn(run_id)
    analysis = failure_snapshot.get("analysis") if isinstance(failure_snapshot.get("analysis"), dict) else {}
    if not analysis:
        return {}

    predicted_source = normalize_failure_source_value(analysis.get("failure_source", "unknown"))
    normalized_feedback = sanitize_failure_source_feedback(feedback, predicted_source=predicted_source)
    confirmed_source = str(normalized_feedback.get("corrected_failure_source", "")).strip()
    sample = {
        "version": "FailureSourceCalibrationV1",
        "sample_id": str(uuid.uuid4()),
        "project": str(review_record.get("project", "mall")).strip() or "mall",
        "run_id": run_id,
        "case_id": str(review_record.get("case_id", "")).strip(),
        "page": str(review_record.get("page", "")).strip(),
        "review_type": review_type,
        "review_status": review_status,
        "predicted_failure_source": predicted_source,
        "predicted_failure_source_reason": str(analysis.get("failure_source_reason", "")).strip(),
        "predicted_failure_source_confidence": clamp_confidence(analysis.get("failure_source_confidence", 0)),
        "predicted_requires_manual_review": bool(analysis.get("requires_manual_review", False)),
        "predicted_source_evidence": analysis.get("source_evidence", []) if isinstance(analysis.get("source_evidence"), list) else [],
        "human_decision": normalized_feedback["decision"],
        "confirmed_failure_source": confirmed_source,
        "feedback_reason": normalized_feedback["reason"],
        "usable_for_training": bool(confirmed_source) and normalized_feedback["decision"] in {"accepted", "corrected"},
        "confirmed_by": str(review_record.get("confirmed_by", "")).strip() or "anonymous",
        "confirmed_by_role": str(review_record.get("confirmed_by_role", "")).strip() or "unknown",
        "confirmed_by_source": str(review_record.get("confirmed_by_source", "")).strip() or "system_default",
        "actor_display": reviewer_display_name_fn(review_record),
        "created_at": str(review_record.get("updated_at", "")).strip() or now_iso_fn(),
    }
    items = read_json_list_fn(calibration_file)
    items.insert(0, sample)
    write_json_list_fn(calibration_file, items[:5000])
    return sample


def list_defect_items(case_id: str, *, read_items: ReadDefectItems) -> list[dict[str, Any]]:
    items = [
        {
            **item,
            "case_id": normalize_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else "",
        }
        for item in read_items()
    ]
    normalized_case_id = normalize_case_id(str(case_id or "").strip()) if str(case_id or "").strip() else ""
    if normalized_case_id:
        items = [item for item in items if str(item.get("case_id", "")).strip() == normalized_case_id]
    items.sort(key=lambda item: str(item.get("linked_at", "")), reverse=True)
    return items


def load_defect_items(*, read_items: ReadDefectItems) -> list[dict[str, Any]]:
    return list_defect_items("", read_items=read_items)


def add_defect_item(
    *,
    case_id: str,
    defect_id: str,
    defect_url: str,
    system: str,
    note: str,
    read_items: ReadDefectItems,
    write_items: WriteDefectItems,
) -> dict[str, Any]:
    entry = {
        "case_id": normalize_case_id(str(case_id).strip()) if str(case_id).strip() else "",
        "defect_id": str(defect_id).strip(),
        "defect_url": str(defect_url).strip(),
        "system": str(system).strip() or "manual",
        "note": str(note).strip(),
        "linked_at": datetime.now(UTC).isoformat(),
    }
    items = read_items()
    exists = any(
        str(item.get("case_id", "")).strip() == entry["case_id"]
        and str(item.get("defect_id", "")).strip() == entry["defect_id"]
        for item in items
    )
    if not exists:
        items.insert(0, entry)
        write_items(items[:1000])
    return entry


def build_report_overview(
    *,
    collect_execution_records_with_meta: CollectExecutionRecords,
    normalize_execution_meta: NormalizeExecutionMeta,
    collect_failure_entries: CollectFailureEntries,
    normalize_failure_analysis_view: NormalizeFailureAnalysis,
    read_defect_items: ReadDefectItems,
) -> dict[str, Any]:
    run_entries, execution_meta_raw = collect_execution_records_with_meta(limit=1000)
    execution_meta = normalize_execution_meta(execution_meta_raw)
    total_runs = len(run_entries)
    passed = sum(1 for item in run_entries if str(item.get("status", "")).lower() == "passed")
    failed = sum(1 for item in run_entries if str(item.get("status", "")).lower() == "failed")
    pass_rate = round((passed / total_runs * 100) if total_runs else 0.0, 1)
    failure_entries = collect_failure_entries()
    high_risk = sum(1 for item in failure_entries if str(item["analysis"].get("risk_level", "")).lower() == "high")
    actionable = sum(
        1
        for item in failure_entries
        if str((item.get("suggestion") or {}).get("advice_type", "")).strip() not in {"", "no_change"}
        and float((item.get("suggestion") or {}).get("confidence", 0) or 0) >= 0.5
    )
    health_score = max(0, min(100, int(pass_rate - high_risk * 6 - max(failed - passed, 0) * 2)))

    defect_map: dict[str, list[dict[str, Any]]] = {}
    for item in read_defect_items():
        normalized_defect_case_id = normalize_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else ""
        defect_map.setdefault(normalized_defect_case_id, []).append(item)

    recent_failures = []
    for item in failure_entries[:30]:
        case_id = normalize_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else ""
        links = defect_map.get(case_id, [])
        analysis = normalize_failure_analysis_view(item.get("analysis") if isinstance(item.get("analysis"), dict) else {})
        recent_failures.append(
            {
                "case_id": case_id,
                "case_title": item.get("case_title", case_id),
                "summary": analysis.get("summary", ""),
                "risk_level": analysis.get("risk_level", ""),
                "failure_source": analysis.get("failure_source", ""),
                "source_evidence": analysis.get("source_evidence", []),
                "requires_manual_review": bool(analysis.get("requires_manual_review", False)),
                "finished_at": item.get("finished_at", ""),
                "defects": links,
                "defect_count": len(links),
                "artifact_dir": item.get("artifact_dir", ""),
            }
        )

    return {
        "summary": {
            "total_runs": total_runs,
            "passed_runs": passed,
            "failed_runs": failed,
            "pass_rate": pass_rate,
            "health_score": health_score,
            "high_risk_failures": high_risk,
            "actionable_suggestions": actionable,
        },
        "recent_failures": recent_failures[:20],
        "execution_meta": execution_meta,
    }


def build_report_failures(
    *,
    case_id: str,
    keyword: str,
    defect_status: str,
    collect_failure_entries_with_meta: CollectFailureEntriesWithMeta,
    normalize_failure_evidence_meta: NormalizeFailureEvidenceMeta,
    read_defect_items: ReadDefectItems,
) -> dict[str, Any]:
    defect_map: dict[str, list[dict[str, Any]]] = {}
    for item in read_defect_items():
        normalized_defect_case_id = normalize_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else ""
        defect_map.setdefault(normalized_defect_case_id, []).append(item)

    entries, evidence_meta_raw = collect_failure_entries_with_meta()
    evidence_meta = normalize_failure_evidence_meta(evidence_meta_raw)
    rows: list[dict[str, Any]] = []
    for item in entries:
        normalized_case_id = normalize_case_id(str(item.get("case_id", "")).strip()) if str(item.get("case_id", "")).strip() else ""
        links = defect_map.get(normalized_case_id, [])
        failed_step = _dict_value(item.get("failed_step")) or _dict_value(item["analysis"].get("failed_step"))
        element_impact = _dict_value(item.get("element_impact")) or _dict_value(item["analysis"].get("element_impact"))
        rows.append(
            {
                "case_id": normalized_case_id,
                "case_title": item.get("case_title", normalized_case_id),
                "finished_at": item.get("finished_at", ""),
                "summary": item["analysis"].get("summary", ""),
                "failure_category": item["analysis"].get("failure_category", ""),
                "failure_source": item["analysis"].get("failure_source", ""),
                "failure_source_reason": item["analysis"].get("failure_source_reason", ""),
                "source_evidence": item["analysis"].get("source_evidence", []),
                "likely_cause": item["analysis"].get("likely_cause", ""),
                "risk_level": item["analysis"].get("risk_level", ""),
                "recommended_action": item["analysis"].get("recommended_action", ""),
                "confidence": item["analysis"].get("confidence", ""),
                "requires_manual_review": bool(item["analysis"].get("requires_manual_review", False)),
                "failed_step": failed_step,
                "element_impact": element_impact,
                "governance_href": str(element_impact.get("governance_href", "")).strip(),
                "suggestion": item.get("suggestion", {}),
                "artifact_dir": item.get("artifact_dir", ""),
                "analysis_path": item.get("analysis_path", ""),
                "suggestion_path": item.get("suggestion_path", ""),
                "screenshot_path": item.get("screenshot_path", ""),
                "html_path": item.get("html_path", ""),
                "meta_path": item.get("meta_path", ""),
                "video_path": item.get("video_path", ""),
                "evidence_source": str(item.get("evidence_source", "")).strip() or "unknown",
                "manifest_path": item.get("manifest_path", ""),
                "defects": links,
                "defect_count": len(links),
            }
        )

    normalized_case_id = normalize_case_id(str(case_id).strip()) if str(case_id).strip() else ""
    if normalized_case_id:
        rows = [item for item in rows if item["case_id"] == normalized_case_id]
    normalized_keyword = str(keyword).strip().lower()
    if normalized_keyword:
        rows = [
            item
            for item in rows
            if normalized_keyword in item["case_id"].lower()
            or normalized_keyword in str(item.get("case_title", "")).lower()
            or normalized_keyword in str(item.get("summary", "")).lower()
            or any(normalized_keyword in str(link.get("defect_id", "")).lower() for link in item.get("defects", []))
        ]
    mode = str(defect_status).strip().lower()
    if mode == "linked":
        rows = [item for item in rows if item.get("defect_count", 0) > 0]
    elif mode == "unlinked":
        rows = [item for item in rows if item.get("defect_count", 0) == 0]

    return {"items": rows[:80], "evidence_meta": evidence_meta}


def parse_analysis_file(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "summary": "",
        "failure_category": "",
        "failure_source": "",
        "failure_source_reason": "",
        "failure_source_confidence": "",
        "likely_cause": "",
        "risk_level": "",
        "recommended_action": "",
        "requires_manual_review": False,
        "confidence": "",
        "evidence_used": [],
        "failed_step": {},
        "element_impact": {},
        "source_evidence": [],
        "source_file": str(path),
    }
    key_map = {
        "Summary": "summary",
        "Failure Category": "failure_category",
        "Failure Source": "failure_source",
        "Failure Source Reason": "failure_source_reason",
        "Failure Source Confidence": "failure_source_confidence",
        "Likely Cause": "likely_cause",
        "Risk Level": "risk_level",
        "Recommended Action": "recommended_action",
        "Requires Manual Review": "requires_manual_review",
        "Confidence": "confidence",
        "Evidence Used": "evidence_used",
        "Failed Step": "failed_step",
        "Element Impact": "element_impact",
        "Source Evidence": "source_evidence",
    }
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return parsed
    for raw_line in text.splitlines():
        if ": " not in raw_line:
            continue
        prefix, value = raw_line.split(": ", 1)
        target = key_map.get(prefix.strip())
        if target:
            if target == "requires_manual_review":
                parsed[target] = value.strip().lower() in {"1", "true", "yes", "on", "y", "是"}
            elif target == "evidence_used":
                parsed[target] = [item.strip() for item in value.split(",") if item.strip()]
            elif target == "source_evidence":
                try:
                    loaded = json.loads(value.strip())
                except Exception:
                    loaded = []
                parsed[target] = loaded if isinstance(loaded, list) else []
            elif target in {"failed_step", "element_impact"}:
                try:
                    loaded = json.loads(value.strip())
                except Exception:
                    loaded = {}
                parsed[target] = loaded if isinstance(loaded, dict) else {}
            else:
                parsed[target] = value.strip()

    payload = _parse_last_json_object(text)
    if payload:
        for field in (
            "summary",
            "failure_category",
            "failure_source",
            "failure_source_reason",
            "failure_source_confidence",
            "likely_cause",
            "risk_level",
            "recommended_action",
            "confidence",
        ):
            if not str(parsed.get(field, "")).strip():
                parsed[field] = payload.get(field, parsed.get(field, ""))
        if not parsed.get("requires_manual_review", False):
            parsed["requires_manual_review"] = bool(payload.get("requires_manual_review", False))
        if not isinstance(parsed.get("source_evidence"), list) or not parsed.get("source_evidence"):
            source_evidence = payload.get("source_evidence")
            if isinstance(source_evidence, list):
                parsed["source_evidence"] = source_evidence
        if not isinstance(parsed.get("evidence_used"), list) or not parsed.get("evidence_used"):
            evidence_used = payload.get("evidence_used")
            if isinstance(evidence_used, list):
                parsed["evidence_used"] = evidence_used
        if not _dict_value(parsed.get("failed_step")) and isinstance(payload.get("failed_step"), dict):
            parsed["failed_step"] = payload.get("failed_step")
        if not _dict_value(parsed.get("element_impact")) and isinstance(payload.get("element_impact"), dict):
            parsed["element_impact"] = payload.get("element_impact")
    return parsed


def _parse_last_json_object(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() != "{":
            continue
        candidate = "\n".join(lines[index:]).strip()
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def normalize_failure_analysis_view(analysis: dict[str, Any] | None) -> dict[str, Any]:
    source = analysis if isinstance(analysis, dict) else {}
    failure_source = str(source.get("failure_source", "")).strip().lower()
    failure_source_reason = str(source.get("failure_source_reason", "")).strip()
    risk_level = str(source.get("risk_level", "")).strip().lower()
    recommended_action = str(source.get("recommended_action", "")).strip()
    try:
        source_confidence = float(source.get("failure_source_confidence", source.get("confidence", 0)) or 0)
    except (TypeError, ValueError):
        source_confidence = 0.0
    source_confidence = max(0.0, min(1.0, source_confidence))
    try:
        confidence = float(source.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    requires_manual_review = bool(
        source.get("requires_manual_review", False)
        or failure_source in {"", "unknown"}
        or source_confidence < 0.7
        or confidence < 0.65
    )
    return {
        "summary": str(source.get("summary", "")).strip(),
        "failure_category": str(source.get("failure_category", "")).strip().lower(),
        "failure_source": failure_source or "unknown",
        "failure_source_reason": failure_source_reason or "Failure source reason not available.",
        "failure_source_confidence": source_confidence,
        "likely_cause": str(source.get("likely_cause", "")).strip(),
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "confidence": confidence if confidence else source.get("confidence", ""),
        "requires_manual_review": requires_manual_review,
        "evidence_used": source.get("evidence_used", []) if isinstance(source.get("evidence_used"), list) else [],
        "source_evidence": source.get("source_evidence", []) if isinstance(source.get("source_evidence"), list) else [],
        "failed_step": _dict_value(source.get("failed_step")),
        "element_impact": _dict_value(source.get("element_impact")),
        "source_file": str(source.get("source_file", "")).strip(),
    }


def normalize_failure_entry_view(entry: dict[str, Any] | None) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    normalized = dict(source)
    normalized["analysis"] = normalize_failure_analysis_view(_dict_value(source.get("analysis")))
    return normalized


def build_run_failure_source_summary(
    failures: list[dict[str, Any]],
    *,
    clamp_confidence: ClampConfidence,
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    total = 0
    manual_review_count = 0
    low_confidence_count = 0
    confidence_sum = 0.0
    confidence_count = 0

    for item in failures:
        if not isinstance(item, dict):
            continue
        analysis = _dict_value(item.get("analysis"))
        source = str(analysis.get("failure_source", "")).strip().lower() or "unknown"
        source_counts[source] = int(source_counts.get(source, 0) or 0) + 1
        total += 1

        if bool(analysis.get("requires_manual_review", False)):
            manual_review_count += 1

        confidence = clamp_confidence(
            analysis.get(
                "failure_source_confidence",
                analysis.get("confidence", 0),
            )
        )
        confidence_sum += confidence
        confidence_count += 1
        if confidence < 0.7:
            low_confidence_count += 1

    top_source = ""
    top_source_count = 0
    if source_counts:
        top_source = max(
            source_counts,
            key=lambda key: (
                int(source_counts.get(key, 0) or 0),
                key,
            ),
        )
        top_source_count = int(source_counts.get(top_source, 0) or 0)

    avg_confidence = round(confidence_sum / confidence_count, 3) if confidence_count > 0 else 0.0
    return {
        "version": "FailureSourceSummaryV1",
        "total_failures": total,
        "source_counts": dict(sorted(source_counts.items())),
        "top_source": top_source or "unknown",
        "top_source_count": top_source_count,
        "requires_manual_review_count": manual_review_count,
        "low_confidence_count": low_confidence_count,
        "average_failure_source_confidence": avg_confidence,
    }


def resolve_run_failure_snapshot(
    run_id: str,
    *,
    find_run_item: FindRunItem,
    normalize_failure_entry_view: NormalizeFailureEntry,
    collect_failure_entries: CollectFailureEntries,
    is_within_fn: IsWithin,
) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {}
    run_item = find_run_item(normalized_run_id)
    if not isinstance(run_item, dict):
        return {}
    latest_failure = _dict_value(run_item.get("latest_failure"))
    if latest_failure:
        return normalize_failure_entry_view(latest_failure)
    artifacts_dir = Path(str(run_item.get("artifacts_dir", "")).strip())
    if artifacts_dir.exists():
        failures = [
            normalize_failure_entry_view(item)
            for item in collect_failure_entries()
            if is_within_fn(Path(item.get("artifact_dir", "")), artifacts_dir)
        ]
        if failures:
            return failures[0]
    return {}


def resolve_run_governance_snapshot(
    run_id: str,
    *,
    find_run_item: FindRunItem,
    build_risk_report_summary: BuildRiskReportSummary,
    build_self_healing_summary: BuildSelfHealingSummary,
    build_page_semantic_summary: BuildPageSemanticSummary,
) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return {}
    run_item = find_run_item(normalized_run_id)
    if not isinstance(run_item, dict):
        return {}
    risk_summary = run_item.get("risk_summary") if isinstance(run_item.get("risk_summary"), dict) else build_risk_report_summary(
        _dict_value(run_item.get("risk_report"))
    )
    self_healing_summary = (
        run_item.get("self_healing_summary")
        if isinstance(run_item.get("self_healing_summary"), dict)
        else build_self_healing_summary(
            execution_record=_dict_value(run_item.get("execution_record")),
            artifacts_dir=str(run_item.get("artifacts_dir", "")).strip(),
        )
    )
    page_semantic_summary = (
        run_item.get("page_semantic_summary")
        if isinstance(run_item.get("page_semantic_summary"), dict)
        else build_page_semantic_summary(
            _dict_value(run_item.get("page_semantic")),
        )
    )
    return {
        "risk_summary": risk_summary if isinstance(risk_summary, dict) else {},
        "self_healing_summary": self_healing_summary if isinstance(self_healing_summary, dict) else {},
        "page_semantic_summary": page_semantic_summary if isinstance(page_semantic_summary, dict) else {},
    }


def build_report_context(
    *,
    git_rev_parse_head: str,
    git_log_subject: str,
    git_branch: str,
    collect_execution_records_with_meta: CollectExecutionRecords,
    normalize_execution_meta: NormalizeExecutionMeta,
    image_tag: str,
    base_url: str,
    browser: str,
    environment: str,
) -> dict[str, Any]:
    run_entries, execution_meta_raw = collect_execution_records_with_meta(limit=200)
    execution_meta = normalize_execution_meta(execution_meta_raw)
    latest_entry = run_entries[0] if run_entries else {}
    latest_record = _dict_value(latest_entry.get("execution_record"))
    latest_run_id = str(latest_record.get("run_id", "")).strip()
    latest_started_at = str(latest_record.get("started_at", "")).strip()
    return {
        "git": {
            "commit_id": git_rev_parse_head,
            "commit_message": git_log_subject,
            "branch": git_branch,
        },
        "build": {
            "build_version": git_rev_parse_head[:12] if git_rev_parse_head else "",
            "image_tag": image_tag,
            "build_time": latest_started_at,
        },
        "execution": {
            "base_url": base_url,
            "browser": browser,
            "environment": environment,
            "runner": "pytest + playwright",
            "latest_run_id": latest_run_id,
            "latest_execution_source": str(latest_entry.get("source", "")).strip(),
            "execution_meta": execution_meta,
        },
    }


def build_report_performance(
    *,
    collect_execution_records_with_meta: CollectExecutionRecords,
    normalize_execution_meta: NormalizeExecutionMeta,
) -> dict[str, Any]:
    run_entries, execution_meta_raw = collect_execution_records_with_meta(limit=1000)
    execution_meta = normalize_execution_meta(execution_meta_raw)
    duration_rows: list[dict[str, Any]] = []
    for item in run_entries:
        execution_record = _dict_value(item.get("execution_record"))
        started = str(execution_record.get("started_at", "")).strip()
        finished = str(execution_record.get("finished_at", "")).strip()
        if not started or not finished:
            continue
        try:
            started_dt = datetime.fromisoformat(started)
            finished_dt = datetime.fromisoformat(finished)
            duration = max(0.0, (finished_dt - started_dt).total_seconds())
        except Exception:
            duration = 0.0
        duration_rows.append(
            {
                "run_id": execution_record.get("run_id", ""),
                "case_id": execution_record.get("case_id", ""),
                "status": execution_record.get("status", ""),
                "duration_seconds": duration,
                "finished_at": finished,
                "source": item.get("source", ""),
            }
        )
    duration_rows.sort(key=lambda item: item["finished_at"], reverse=True)
    avg_duration = round(sum(item["duration_seconds"] for item in duration_rows) / len(duration_rows), 2) if duration_rows else 0.0
    max_duration = round(max((item["duration_seconds"] for item in duration_rows), default=0.0), 2)
    latest = duration_rows[0]["duration_seconds"] if len(duration_rows) >= 1 else 0.0
    previous = duration_rows[1]["duration_seconds"] if len(duration_rows) >= 2 else 0.0
    delta = round(latest - previous, 2) if previous else 0.0
    slowest = sorted(duration_rows, key=lambda item: item["duration_seconds"], reverse=True)[:10]
    return {
        "summary": {
            "average_duration_seconds": avg_duration,
            "max_duration_seconds": max_duration,
            "latest_delta_seconds": delta,
            "sample_count": len(duration_rows),
        },
        "slow_cases": slowest,
        "execution_meta": execution_meta,
    }


def build_report_allure(
    *,
    available: bool,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
) -> dict[str, Any]:
    version = get_allure_index_version() if available else 0
    summary = read_allure_summary() if available else {}
    allure_index = ensure_allure_snapshot(version=version) if available else "/allure/index.html"
    return {
        "allure_index": allure_index,
        "available": available,
        "version": version,
        "summary": summary,
    }


def build_report_allure_refresh(
    *,
    command_result: Any,
    available: bool,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
) -> dict[str, Any]:
    summary = read_allure_summary() if available else {}
    return_code = int(getattr(command_result, "returncode", 1))
    if return_code != 0:
        return {
            "error": {
                "message": "allure generate failed",
                "return_code": return_code,
                "stdout": str(getattr(command_result, "stdout", "") or "").strip()[-4000:],
                "stderr": str(getattr(command_result, "stderr", "") or "").strip()[-4000:],
            }
    }
    version = get_allure_index_version() if available else 0
    allure_index = ensure_allure_snapshot(version=version) if available else "/allure/index.html"
    return {
        "available": available,
        "version": version,
        "allure_index": allure_index,
        "return_code": return_code,
        "stdout": str(getattr(command_result, "stdout", "") or "").strip()[-4000:],
        "stderr": str(getattr(command_result, "stderr", "") or "").strip()[-4000:],
        "summary": summary,
    }


def refresh_allure_report(
    *,
    python_bin: str,
    runner_root: Path,
    repo_root: Path,
    allure_report_root: Path,
    run_command: RunCommand,
    read_allure_summary: ReadAllureSummary,
    ensure_allure_snapshot: EnsureAllureSnapshot,
    get_allure_index_version: GetAllureIndexVersion,
) -> dict[str, Any]:
    command = [
        python_bin,
        str(runner_root / "tools" / "manage_allure.py"),
        "generate",
    ]
    command_result = run_command(
        command,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    available = (allure_report_root / "index.html").exists()
    return build_report_allure_refresh(
        command_result=command_result,
        available=available,
        read_allure_summary=read_allure_summary,
        ensure_allure_snapshot=ensure_allure_snapshot,
        get_allure_index_version=get_allure_index_version,
    )


def get_allure_index_version(*, allure_report_root: Path) -> int:
    candidates = [
        allure_report_root / "index.html",
        allure_report_root / "widgets" / "summary.json",
        allure_report_root / "history" / "history-trend.json",
    ]
    versions: list[int] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            versions.append(int(path.stat().st_mtime_ns))
        except Exception:
            continue
    return max(versions) if versions else 0


def read_allure_summary(*, allure_report_root: Path) -> dict[str, Any]:
    summary_path = allure_report_root / "widgets" / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def ensure_allure_snapshot(
    *,
    version: int,
    allure_report_root: Path,
    allure_snapshots_root: Path,
) -> str:
    if version <= 0:
        return "/allure/index.html"
    target = allure_snapshots_root / str(version)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(allure_report_root, target)
        snapshot_dirs = sorted(
            [item for item in allure_snapshots_root.iterdir() if item.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for stale in snapshot_dirs[10:]:
            shutil.rmtree(stale, ignore_errors=True)
    return f"/allure-snapshots/{version}/index.html"
