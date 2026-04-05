from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from datetime_compat import UTC
from shared_backend.case_ids import normalize_case_id

NormalizeExecutionRecordPayload = Callable[[dict[str, Any]], dict[str, Any]]
NormalizeEvidenceManifestPayload = Callable[[dict[str, Any]], dict[str, Any]]
ResolveManifestEntries = Callable[[Any, Path], list[Path]]
LoadExecutionRecordPayload = Callable[[Path], dict[str, Any]]
RuntimeViewFromEntry = Callable[[dict[str, Any]], dict[str, Any]]
ReadJsonList = Callable[[Path], list[dict[str, Any]]]
ExecutionRecordTimeValue = Callable[[dict[str, Any]], str]
UtcNow = Callable[[], datetime]
ParseIsoDatetime = Callable[[str], datetime | None]
ClampConfidence = Callable[[Any], float]


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _scope_from_factor(factor: str) -> str | None:
    normalized = str(factor or "").strip().lower()
    mapping = {
        "api_contract": "api_contract_regression",
        "permission": "permission_smoke",
        "ui_selector": "ui_selector_smoke",
        "business_rule": "business_rule_regression",
    }
    return mapping.get(normalized)


def _gate_recommendation_for_item(
    *,
    governance_level: str,
    has_traceability_gap: bool,
    source_count: int,
    top_factor: dict[str, Any] | None,
) -> tuple[str, str]:
    normalized_level = str(governance_level or "").strip().lower()
    factor_name = str((top_factor or {}).get("factor", "")).strip().lower()
    if normalized_level == "critical":
        return "block", "critical 治理风险任务默认提升为 block，先治理再放行。"
    if normalized_level == "high":
        return "manual_review", "high 治理风险任务默认进入人工复核。"
    if has_traceability_gap and source_count > 0:
        return "manual_review", "多源任务存在 traceability 缺口，建议先人工复核。"
    if factor_name in {"api_contract", "business_rule", "permission"}:
        return "manual_review", f"{factor_name} 变更影响较大，建议提升到人工复核。"
    return "allow", "当前治理信号可控，可按默认门禁策略执行。"


def _strict_mode_status_for_item(
    *,
    task_source: str,
    manifest_action: str,
    has_manifest: bool,
    runtime_realtime: bool,
    evidence_health_status: str,
) -> tuple[str, str]:
    normalized_source = str(task_source or "").strip().lower()
    normalized_action = str(manifest_action or "").strip().lower()
    normalized_health = str(evidence_health_status or "").strip().lower()
    if (
        normalized_source == "manifest"
        and has_manifest
        and normalized_action == "ok"
        and normalized_health == "healthy"
        and not runtime_realtime
    ):
        return "ready", "任务已稳定走 manifest-first 路径，可作为 strict-mode 候选。"
    if normalized_source == "runtime_realtime" or normalized_action == "await_runtime_flush" or runtime_realtime:
        return "caution", "任务仍依赖 runtime 视图补充，建议等待 evidence manifest 落盘后再收紧。"
    return "blocked", "任务仍依赖 compat builder、缺失 manifest 或存在 runtime fallback，暂不适合关闭 compat builder。"


def parse_optional_bool_query(value: Any) -> bool | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def execution_record_time_value(record: dict[str, Any]) -> str:
    return (
        str(record.get("finished_at", "")).strip()
        or str(record.get("started_at", "")).strip()
        or str(record.get("created_at", "")).strip()
    )


def collect_execution_records_with_meta(
    *,
    limit: int,
    compat_scan_enabled: bool,
    artifact_roots: list[Path],
    logger: Any,
    normalize_evidence_manifest_payload: NormalizeEvidenceManifestPayload,
    resolve_manifest_entries: ResolveManifestEntries,
    load_execution_record_payload: LoadExecutionRecordPayload,
    execution_record_time_value: ExecutionRecordTimeValue,
    runtime_jobs: list[dict[str, Any]],
    runtime_runs_file: Path,
    runtime_view_from_entry: RuntimeViewFromEntry,
    read_json_list: ReadJsonList,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    consumed_record_paths: set[Path] = set()
    compat_used_count = 0
    compat_disabled_skipped = 0
    invalid_manifest_count = 0
    invalid_record_count = 0
    missing_manifest_count = 0

    for artifact_root in artifact_roots:
        if not artifact_root.exists():
            continue
        for manifest_path in sorted(artifact_root.rglob("evidence_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
            except Exception:
                invalid_manifest_count += 1
                logger.warning("invalid evidence_manifest.json at %s while collecting execution records", manifest_path)
                continue
            manifest = normalize_evidence_manifest_payload(raw_manifest)
            manifest_root = manifest_path.parent
            record_paths = resolve_manifest_entries(manifest.get("execution_record_files"), manifest_root)
            if not record_paths:
                continue
            for record_path in record_paths:
                resolved_record_path = record_path.resolve()
                if resolved_record_path in consumed_record_paths:
                    continue
                consumed_record_paths.add(resolved_record_path)
                execution_record = load_execution_record_payload(record_path)
                if not execution_record:
                    invalid_record_count += 1
                    continue
                finished_at = execution_record_time_value(execution_record)
                if not finished_at:
                    finished_at = datetime.fromtimestamp(record_path.stat().st_mtime, tz=UTC).isoformat()
                items.append(
                    {
                        "run_id": str(execution_record.get("run_id", "")).strip(),
                        "case_id": str(execution_record.get("case_id", "")).strip(),
                        "status": str(execution_record.get("status", "queued")).strip() or "queued",
                        "finished_at": finished_at,
                        "execution_record": execution_record,
                        "execution_record_path": str(record_path.resolve()),
                        "manifest_path": str(manifest_path.resolve()),
                        "source": "manifest",
                    }
                )
        for record_path in sorted(artifact_root.rglob("execution_record.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            resolved_record_path = record_path.resolve()
            if resolved_record_path in consumed_record_paths:
                continue
            missing_manifest_count += 1
            if not compat_scan_enabled:
                compat_disabled_skipped += 1
                logger.warning(
                    "execution_record missing manifest linkage for %s; compatibility scan disabled, record skipped",
                    record_path,
                )
                continue
            compat_used_count += 1
            consumed_record_paths.add(resolved_record_path)
            execution_record = load_execution_record_payload(record_path)
            if not execution_record:
                invalid_record_count += 1
                continue
            finished_at = execution_record_time_value(execution_record)
            if not finished_at:
                finished_at = datetime.fromtimestamp(record_path.stat().st_mtime, tz=UTC).isoformat()
            items.append(
                {
                    "run_id": str(execution_record.get("run_id", "")).strip(),
                    "case_id": str(execution_record.get("case_id", "")).strip(),
                    "status": str(execution_record.get("status", "queued")).strip() or "queued",
                    "finished_at": finished_at,
                    "execution_record": execution_record,
                    "execution_record_path": str(record_path.resolve()),
                    "manifest_path": "",
                    "source": "compat_scan",
                }
            )

    items.sort(key=lambda item: str(item.get("finished_at", "")), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in items:
        execution_record = _dict_value(item.get("execution_record"))
        run_id = str(item.get("run_id", "")).strip() or str(execution_record.get("run_id", "")).strip()
        dedupe_key = run_id or str(item.get("execution_record_path", "")).strip()
        if not dedupe_key or dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped.append(item)
        if len(deduped) >= limit:
            break

    active_statuses = {"queued", "running", "pending"}
    runtime_items: list[dict[str, Any]] = [dict(item) for item in runtime_jobs]
    runtime_items.extend(read_json_list(runtime_runs_file))
    for runtime_item in runtime_items:
        run_view = runtime_view_from_entry(runtime_item)
        execution_record = _dict_value(run_view.get("execution_record"))
        if not execution_record:
            continue
        status_value = str(execution_record.get("status", "")).strip().lower()
        run_id = str(execution_record.get("run_id", "")).strip()
        if status_value not in active_statuses:
            continue
        if run_id and run_id in seen_ids:
            continue
        finished_at = execution_record_time_value(execution_record)
        dedupe_key = run_id or f"runtime:{run_view.get('case_id', '')}:{run_view.get('started_at', '')}"
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped.append(
            {
                "run_id": run_id,
                "case_id": str(execution_record.get("case_id", "")).strip(),
                "status": str(execution_record.get("status", "queued")).strip() or "queued",
                "finished_at": finished_at,
                "execution_record": normalize_execution_record_payload(
                    {
                        **execution_record,
                        "metadata": {
                            **(
                                execution_record.get("metadata", {})
                                if isinstance(execution_record.get("metadata"), dict)
                                else {}
                            ),
                            "runtime_realtime_supplement": True,
                        },
                    }
                ),
                "execution_record_path": "",
                "manifest_path": "",
                "source": "runtime_realtime",
            }
        )

    deduped.sort(
        key=lambda item: (
            str(item.get("finished_at", "")),
            str(_dict_value(item.get("execution_record")).get("started_at", "")),
        ),
        reverse=True,
    )

    runtime_fallback_used = False
    if not deduped:
        runtime_fallback_used = True
        for runtime_item in read_json_list(runtime_runs_file):
            run_view = runtime_view_from_entry(runtime_item)
            execution_record = _dict_value(run_view.get("execution_record"))
            if not execution_record:
                continue
            deduped.append(
                {
                    "run_id": str(execution_record.get("run_id", "")).strip(),
                    "case_id": str(execution_record.get("case_id", "")).strip(),
                    "status": str(execution_record.get("status", "queued")).strip() or "queued",
                    "finished_at": execution_record_time_value(execution_record),
                    "execution_record": execution_record,
                    "execution_record_path": "",
                    "manifest_path": "",
                    "source": "runtime_fallback",
                }
            )
        deduped.sort(
            key=lambda item: (
                str(item.get("finished_at", "")),
                str(_dict_value(item.get("execution_record")).get("started_at", "")),
            ),
            reverse=True,
        )

    trimmed = deduped[:limit]
    source_counts: dict[str, int] = defaultdict(int)
    for item in trimmed:
        source_counts[str(item.get("source", "unknown")).strip() or "unknown"] += 1

    warnings: list[str] = []
    if invalid_manifest_count > 0:
        warnings.append(f"检测到 {invalid_manifest_count} 个无效 evidence_manifest.json，已跳过。")
    if invalid_record_count > 0:
        warnings.append(f"检测到 {invalid_record_count} 个无效 execution_record.json，已跳过。")
    if int(source_counts.get("compat_scan", 0)) > 0:
        warnings.append(
            f"检测到 {int(source_counts.get('compat_scan', 0))} 条 execution_record 通过兼容扫描回退读取，建议 runner 全量输出 manifest。"
        )
    if compat_disabled_skipped > 0:
        warnings.append(f"兼容扫描已禁用，跳过 {compat_disabled_skipped} 条未绑定 manifest 的 execution_record。")
    if runtime_fallback_used:
        warnings.append("未发现可用 execution_record 落盘记录，当前报告临时回退 runtime-runs.json。")

    manifest_record_count = int(source_counts.get("manifest", 0))
    compat_scan_record_count = int(source_counts.get("compat_scan", 0))
    runtime_realtime_count = int(source_counts.get("runtime_realtime", 0))
    runtime_fallback_count = int(source_counts.get("runtime_fallback", 0))
    total_visible_records = manifest_record_count + compat_scan_record_count + runtime_realtime_count + runtime_fallback_count
    manifest_first_ratio = round((manifest_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    fallback_ratio = round((compat_scan_record_count / max(1, (manifest_record_count + compat_scan_record_count))), 3)
    policy_mode = "compat" if compat_scan_enabled else "strict"
    if runtime_fallback_used or runtime_fallback_count > 0:
        health = "critical"
    elif compat_scan_record_count > 0:
        health = "degraded"
    elif compat_disabled_skipped > 0 or invalid_manifest_count > 0 or invalid_record_count > 0:
        health = "warning"
    else:
        health = "healthy"

    meta = {
        "compat_scan_enabled": compat_scan_enabled,
        "policy_mode": policy_mode,
        "health": health,
        "manifest_record_count": manifest_record_count,
        "compat_scan_record_count": compat_scan_record_count,
        "runtime_realtime_count": runtime_realtime_count,
        "runtime_fallback_count": runtime_fallback_count,
        "compat_scan_used_count": compat_used_count,
        "compat_scan_skipped_count": compat_disabled_skipped,
        "invalid_manifest_count": invalid_manifest_count,
        "invalid_execution_record_count": invalid_record_count,
        "missing_manifest_count": missing_manifest_count,
        "runtime_fallback_used": runtime_fallback_used,
        "total_visible_records": total_visible_records,
        "manifest_first_ratio": manifest_first_ratio,
        "fallback_ratio": fallback_ratio,
        "warnings": warnings,
    }
    return trimmed, meta


def build_task_evidence_freshness(
    *,
    task_source: str,
    queue_status: str,
    started_at: str,
    finished_at: str,
    created_at: str,
    has_manifest: bool,
    utc_now: UtcNow,
    parse_iso_datetime: ParseIsoDatetime,
) -> dict[str, Any]:
    source_value = str(task_source or "").strip().lower()
    queue_value = str(queue_status or "").strip().lower()
    if source_value == "runtime_realtime" and queue_value in {"queued", "running"}:
        reference_time = finished_at or started_at or created_at
        reference_dt = parse_iso_datetime(reference_time)
        age_seconds = max(0, int((utc_now() - reference_dt).total_seconds())) if reference_dt else None
        return {
            "status": "live",
            "reason": "任务仍处于 runtime 实时态，证据可能仍在持续写入。",
            "age_seconds": age_seconds,
            "reference_time": reference_time,
            "stale": False,
            "source_window_hours": 0,
        }
    if source_value == "runtime_fallback":
        reference_time = finished_at or started_at or created_at
        reference_dt = parse_iso_datetime(reference_time)
        age_seconds = max(0, int((utc_now() - reference_dt).total_seconds())) if reference_dt else None
        return {
            "status": "stale",
            "reason": "任务当前仅依赖 runtime_fallback，缺少稳定落盘证据事实源。",
            "age_seconds": age_seconds,
            "reference_time": reference_time,
            "stale": True,
            "source_window_hours": 0,
        }

    reference_time = finished_at or started_at or created_at
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        return {
            "status": "unknown",
            "reason": "任务缺少可用于判断证据时效的时间戳。",
            "age_seconds": None,
            "reference_time": reference_time,
            "stale": False,
            "source_window_hours": 0,
        }

    age_seconds = max(0, int((utc_now() - reference_dt).total_seconds()))
    freshness_window_hours = 24 if has_manifest else (12 if source_value == "compat_scan" else 6)
    freshness_window_seconds = freshness_window_hours * 3600
    if age_seconds <= freshness_window_seconds:
        freshness_status = "fresh"
        freshness_reason = "任务证据仍处于新鲜窗口内。"
    elif age_seconds <= freshness_window_seconds * 3:
        freshness_status = "aging"
        freshness_reason = "任务证据已超出新鲜窗口，建议尽快完成治理或复核。"
    else:
        freshness_status = "stale"
        freshness_reason = "任务证据已进入陈旧区间，建议优先回填或重新执行。"
    return {
        "status": freshness_status,
        "reason": freshness_reason,
        "age_seconds": age_seconds,
        "reference_time": reference_time,
        "stale": freshness_status == "stale",
        "source_window_hours": freshness_window_hours,
    }


def build_task_governance_risk(item: dict[str, Any]) -> dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    evidence_health = row.get("evidence_health", {}) if isinstance(row.get("evidence_health"), dict) else {}
    evidence_freshness = row.get("evidence_freshness", {}) if isinstance(row.get("evidence_freshness"), dict) else {}
    health_status = str(evidence_health.get("status", "unknown")).strip().lower() or "unknown"
    freshness_status = str(evidence_freshness.get("status", "unknown")).strip().lower() or "unknown"
    manifest_action = str(row.get("manifest_action", "inspect_source")).strip().lower() or "inspect_source"

    health_score = {
        "healthy": 0,
        "degraded": 3,
        "warning": 2,
        "unknown": 4,
    }.get(health_status, 2)
    freshness_score = {
        "fresh": 0,
        "live": 1,
        "aging": 2,
        "stale": 3,
        "unknown": 2,
    }.get(freshness_status, 2)
    action_score = {
        "ok": 0,
        "await_runtime_flush": 2,
        "backfill_manifest": 3,
        "inspect_source": 4,
    }.get(manifest_action, 2)

    total_score = health_score + freshness_score + action_score
    if total_score >= 6:
        level = "critical"
        reason = "证据健康、时效与 manifest 治理信号叠加后属于高优先治理任务。"
    elif total_score >= 4:
        level = "high"
        reason = "任务存在明显证据治理风险，建议优先关注。"
    elif total_score >= 2:
        level = "medium"
        reason = "任务存在一定治理风险，可纳入常规处理队列。"
    else:
        level = "low"
        reason = "任务证据治理状态整体稳定。"
    return {
        "level": level,
        "score": total_score,
        "reason": reason,
    }


def build_execution_task_view(
    entry: dict[str, Any],
    *,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
    build_task_evidence_freshness_fn: Callable[..., dict[str, Any]],
    utc_now: UtcNow,
    parse_iso_datetime: ParseIsoDatetime,
) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    execution_record = normalize_execution_record_payload(_dict_value(source.get("execution_record")))
    step_summary = _dict_value(execution_record.get("step_summary"))
    metadata = _dict_value(execution_record.get("metadata"))
    multisource = _dict_value(metadata.get("multisource"))
    source_summary = _dict_value(multisource.get("source_summary"))
    traceability_summary = _dict_value(multisource.get("traceability_summary"))
    change_impact = _dict_value(multisource.get("change_impact"))
    embedded_execution_plan = _dict_value(metadata.get("execution_plan"))
    scheduling_hints = _dict_value(metadata.get("scheduling_hints"))
    retry_policy_raw = (
        _dict_value(source.get("retry_policy"))
        if isinstance(source.get("retry_policy"), dict)
        else (
            _dict_value(metadata.get("retry_policy"))
            if isinstance(metadata.get("retry_policy"), dict)
            else (
                _dict_value(embedded_execution_plan.get("retry_policy"))
                if isinstance(embedded_execution_plan.get("retry_policy"), dict)
                else {}
            )
        )
    )
    dependencies_raw = (
        _list_value(source.get("dependencies"))
        if isinstance(source.get("dependencies"), list)
        else (
            _list_value(metadata.get("dependencies"))
            if isinstance(metadata.get("dependencies"), list)
            else (
                _list_value(embedded_execution_plan.get("dependencies"))
                if isinstance(embedded_execution_plan.get("dependencies"), list)
                else []
            )
        )
    )
    run_id = str(source.get("run_id", "")).strip() or str(execution_record.get("run_id", "")).strip()
    status_value = str(source.get("status", "")).strip() or str(execution_record.get("status", "queued")).strip() or "queued"
    queue_status = "queued" if status_value in {"queued", "pending"} else ("running" if status_value == "running" else "completed")
    task_source = str(source.get("source", "")).strip() or "unknown"
    runner = str(metadata.get("runner", "")).strip() or "playwright"
    queue_name = str(scheduling_hints.get("queue", "")).strip() or ("active-runtime" if task_source == "runtime_realtime" else "default")
    resource_profile = str(scheduling_hints.get("resource_profile", "")).strip() or "default"
    expected_total_seconds = int(scheduling_hints.get("expected_total_seconds", 0) or 0)
    evidence_index = execution_record.get("evidence_index", {}) if isinstance(execution_record.get("evidence_index"), dict) else {}
    total_files = int(evidence_index.get("total_files", 0) or 0)
    runner_exit_code = evidence_index.get("runner_exit_code")
    has_manifest = bool(str(source.get("manifest_path", "")).strip())
    try:
        retry_max_retries = max(0, int(retry_policy_raw.get("max_retries", 0) or 0))
    except Exception:
        retry_max_retries = 0
    try:
        retry_backoff_seconds = max(0, int(retry_policy_raw.get("backoff_seconds", 0) or 0))
    except Exception:
        retry_backoff_seconds = 0
    retry_enabled_raw = retry_policy_raw.get("enabled")
    retry_enabled = bool(retry_enabled_raw) if retry_enabled_raw is not None else retry_max_retries > 0
    dependencies: list[str] = []
    for item in dependencies_raw:
        dependency_value = normalize_case_id(str(item).strip()) if str(item).strip() else ""
        if dependency_value and dependency_value not in dependencies:
            dependencies.append(dependency_value)
    freshness = build_task_evidence_freshness_fn(
        task_source=task_source,
        queue_status=queue_status,
        started_at=str(execution_record.get("started_at", "")).strip(),
        finished_at=str(execution_record.get("finished_at", "")).strip(),
        created_at=str(execution_record.get("created_at", "")).strip(),
        has_manifest=has_manifest,
        utc_now=utc_now,
        parse_iso_datetime=parse_iso_datetime,
    )
    if has_manifest:
        evidence_health_status = "healthy"
        evidence_health_reason = "任务已绑定 evidence_manifest。"
        manifest_action = "ok"
    elif task_source == "compat_scan":
        evidence_health_status = "degraded"
        evidence_health_reason = "任务通过 execution_record 兼容扫描回退读取。"
        manifest_action = "backfill_manifest"
    elif task_source in {"runtime_realtime", "runtime_fallback"}:
        evidence_health_status = "warning"
        evidence_health_reason = "任务当前依赖 runtime 视图补充，证据落盘仍待完成。"
        manifest_action = "await_runtime_flush"
    else:
        evidence_health_status = "unknown"
        evidence_health_reason = "任务证据来源未明确。"
        manifest_action = "inspect_source"
    strict_mode_status, strict_mode_reason = _strict_mode_status_for_item(
        task_source=task_source,
        manifest_action=manifest_action,
        has_manifest=has_manifest,
        runtime_realtime=bool(metadata.get("runtime_realtime_supplement", False)),
        evidence_health_status=evidence_health_status,
    )
    source_count = 0
    try:
        source_count = max(
            int(source_summary.get("source_count", 0) or 0),
            int(traceability_summary.get("source_input_count", 0) or 0),
        )
    except Exception:
        source_count = 0
    source_types = [
        str(item).strip()
        for item in _list_value(source_summary.get("source_types"))
        if str(item).strip()
    ]
    try:
        traceability_completeness = float(traceability_summary.get("traceability_completeness", 0.0) or 0.0)
    except Exception:
        traceability_completeness = 0.0
    try:
        gap_point_count = int(traceability_summary.get("gap_point_count", 0) or 0)
    except Exception:
        gap_point_count = 0
    try:
        partial_count = int(traceability_summary.get("partial_count", 0) or 0)
    except Exception:
        partial_count = 0
    try:
        orphan_point_count = int(traceability_summary.get("orphan_point_count", 0) or 0)
    except Exception:
        orphan_point_count = 0
    try:
        orphan_step_count = int(traceability_summary.get("orphan_step_count", 0) or 0)
    except Exception:
        orphan_step_count = orphan_point_count
    try:
        unmapped_changed_area_count = int(traceability_summary.get("unmapped_changed_area_count", 0) or 0)
    except Exception:
        unmapped_changed_area_count = 0
    traceability_status = str(
        traceability_summary.get("status", traceability_summary.get("intent_coverage_status", ""))
    ).strip() or "unknown"
    source_coverage_status = str(traceability_summary.get("source_coverage_status", "")).strip() or "unknown"
    intent_coverage_status = str(traceability_summary.get("intent_coverage_status", "")).strip() or traceability_status
    coverage_breakdown = (
        traceability_summary.get("coverage_breakdown")
        if isinstance(traceability_summary.get("coverage_breakdown"), dict)
        else {}
    )
    source_breakdown = (
        traceability_summary.get("source_breakdown")
        if isinstance(traceability_summary.get("source_breakdown"), dict)
        else {}
    )
    partial_source_ids = [
        str(item).strip()
        for item in _list_value(traceability_summary.get("partial_source_ids"))
        if str(item).strip()
    ]
    uncovered_source_ids = [
        str(item).strip()
        for item in _list_value(traceability_summary.get("uncovered_source_ids"))
        if str(item).strip()
    ]
    orphan_step_keys = [
        str(item).strip()
        for item in _list_value(traceability_summary.get("orphan_step_keys"))
        if str(item).strip()
    ]
    changed_areas = [
        str(item).strip()
        for item in _list_value(change_impact.get("changed_areas"))
        if str(item).strip()
    ]
    top_factor = _dict_value(change_impact.get("top_factor"))
    recommended_regression_scope = [
        str(item).strip()
        for item in _list_value(change_impact.get("recommended_regression_scope"))
        if str(item).strip()
    ]
    impact_score = _int_value(change_impact.get("impact_score"))
    return {
        "task_id": run_id or str(source.get("execution_record_path", "")).strip(),
        "run_id": run_id,
        "case_id": normalize_case_id(str(source.get("case_id", "")).strip() or str(execution_record.get("case_id", "")).strip())
        if str(source.get("case_id", "")).strip() or str(execution_record.get("case_id", "")).strip()
        else "",
        "project": str(execution_record.get("project", "default")).strip() or "default",
        "page": str(step_summary.get("page", "")).strip(),
        "runner": runner,
        "status": status_value,
        "queue_status": queue_status,
        "queue": queue_name,
        "resource_profile": resource_profile,
        "expected_total_seconds": expected_total_seconds,
        "source": task_source,
        "mode": str(execution_record.get("mode", "generate_and_run")).strip() or "generate_and_run",
        "started_at": str(execution_record.get("started_at", "")).strip(),
        "finished_at": str(execution_record.get("finished_at", "")).strip(),
        "created_at": str(execution_record.get("created_at", "")).strip(),
        "execution_record_path": str(source.get("execution_record_path", "")).strip(),
        "manifest_path": str(source.get("manifest_path", "")).strip(),
        "has_manifest": has_manifest,
        "runtime_realtime": bool(metadata.get("runtime_realtime_supplement", False)),
        "step_summary": step_summary,
        "evidence_index": evidence_index,
        "evidence_health": {
            "status": evidence_health_status,
            "reason": evidence_health_reason,
            "total_files": total_files,
            "runner_exit_code": runner_exit_code if isinstance(runner_exit_code, int) else None,
            "execution_requested": bool(evidence_index.get("execution_requested", False)),
            "has_manifest": has_manifest,
        },
        "evidence_freshness": freshness,
        "retry": {
            "enabled": retry_enabled,
            "max_retries": retry_max_retries,
            "backoff_seconds": retry_backoff_seconds,
        },
        "dependency": {
            "dependencies": dependencies,
            "dependency_count": len(dependencies),
            "has_dependencies": bool(dependencies),
        },
        "manifest_action": manifest_action,
        "strict_mode": {
            "status": strict_mode_status,
            "reason": strict_mode_reason,
        },
        "scheduling_hints": scheduling_hints,
        "multisource_summary": {
            "source_count": source_count,
            "source_types": source_types,
            "traceability_completeness": traceability_completeness,
            "gap_point_count": gap_point_count,
            "partial_count": partial_count,
            "orphan_point_count": orphan_point_count,
            "orphan_step_count": orphan_step_count,
            "unmapped_changed_area_count": unmapped_changed_area_count,
            "traceability_status": traceability_status,
            "intent_coverage_status": intent_coverage_status,
            "source_coverage_status": source_coverage_status,
            "coverage_breakdown": coverage_breakdown,
            "source_breakdown": source_breakdown,
            "partial_source_ids": partial_source_ids,
            "uncovered_source_ids": uncovered_source_ids,
            "orphan_step_keys": orphan_step_keys,
            "has_traceability_gap": bool(source_count > 0 and (gap_point_count > 0 or partial_count > 0 or orphan_point_count > 0 or traceability_completeness < 1.0)),
            "changed_areas": changed_areas,
            "impact_score": impact_score,
            "top_factor": top_factor,
            "recommended_regression_scope": recommended_regression_scope,
            "why_manual_review": str(change_impact.get("why_manual_review", "")).strip(),
            "why_blocked": str(change_impact.get("why_blocked", "")).strip(),
        },
    }


def build_execution_task_summary(
    *,
    items: list[dict[str, Any]],
    filter_snapshot: dict[str, Any],
    execution_meta: dict[str, Any],
    build_task_governance_risk_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = defaultdict(int)
    queue_counts: dict[str, int] = defaultdict(int)
    runner_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    evidence_health_counts: dict[str, int] = defaultdict(int)
    evidence_freshness_counts: dict[str, int] = defaultdict(int)
    manifest_action_counts: dict[str, int] = defaultdict(int)
    strict_mode_status_counts: dict[str, int] = defaultdict(int)
    manifest_backfill_freshness_counts: dict[str, int] = defaultdict(int)
    governance_risk_counts: dict[str, int] = defaultdict(int)
    multisource_source_type_counts: dict[str, int] = defaultdict(int)
    recommended_regression_scope_counts: dict[str, int] = defaultdict(int)
    gate_recommendation_counts: dict[str, int] = defaultdict(int)
    governance_risk_top_items: list[dict[str, Any]] = []
    has_manifest_count = 0
    retry_enabled_task_count = 0
    dependency_task_count = 0
    manifest_backfill_candidate_count = 0
    multisource_task_count = 0
    traceability_gap_task_count = 0
    traceability_partial_task_count = 0
    traceability_orphan_task_count = 0
    traceability_unmapped_area_task_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status_counts[str(item.get("status", "unknown")).strip() or "unknown"] += 1
        queue_counts[str(item.get("queue_status", "unknown")).strip() or "unknown"] += 1
        runner_counts[str(item.get("runner", "unknown")).strip() or "unknown"] += 1
        source_counts[str(item.get("source", "unknown")).strip() or "unknown"] += 1
        evidence_health = _dict_value(item.get("evidence_health"))
        evidence_health_counts[str(evidence_health.get("status", "unknown")).strip() or "unknown"] += 1
        evidence_freshness = _dict_value(item.get("evidence_freshness"))
        freshness_status = str(evidence_freshness.get("status", "unknown")).strip() or "unknown"
        evidence_freshness_counts[freshness_status] += 1
        manifest_action = str(item.get("manifest_action", "unknown")).strip() or "unknown"
        manifest_action_counts[manifest_action] += 1
        strict_mode = _dict_value(item.get("strict_mode"))
        strict_mode_status = str(strict_mode.get("status", "unknown")).strip() or "unknown"
        strict_mode_status_counts[strict_mode_status] += 1
        multisource_summary = _dict_value(item.get("multisource_summary"))
        source_count = _int_value(multisource_summary.get("source_count"))
        if source_count > 0:
            multisource_task_count += 1
        if bool(multisource_summary.get("has_traceability_gap", False)):
            traceability_gap_task_count += 1
        if _int_value(multisource_summary.get("partial_count")) > 0:
            traceability_partial_task_count += 1
        if _int_value(multisource_summary.get("orphan_point_count")) > 0:
            traceability_orphan_task_count += 1
        if _int_value(multisource_summary.get("unmapped_changed_area_count")) > 0:
            traceability_unmapped_area_task_count += 1
        for source_type in _list_value(multisource_summary.get("source_types")):
            normalized_source_type = str(source_type).strip()
            if normalized_source_type:
                multisource_source_type_counts[normalized_source_type] += 1
        governance_risk = build_task_governance_risk_fn(item)
        gate_recommendation, gate_recommendation_reason = _gate_recommendation_for_item(
            governance_level=str(governance_risk.get("level", "")).strip(),
            has_traceability_gap=bool(multisource_summary.get("has_traceability_gap", False)),
            source_count=source_count,
            top_factor=_dict_value(multisource_summary.get("top_factor")),
        )
        governance_risk_counts[str(governance_risk.get("level", "unknown")).strip() or "unknown"] += 1
        gate_recommendation_counts[gate_recommendation] += 1
        scope_values = (
            _list_value(multisource_summary.get("recommended_regression_scope"))
            if isinstance(multisource_summary.get("recommended_regression_scope"), list)
            else []
        )
        normalized_scopes = [str(scope).strip() for scope in scope_values if str(scope).strip()]
        if not normalized_scopes:
            top_factor_value = _dict_value(multisource_summary.get("top_factor"))
            factor_scope = _scope_from_factor(
                str(top_factor_value.get("factor", "")).strip()
            )
            if factor_scope:
                normalized_scopes = [factor_scope]
        for scope in normalized_scopes:
            recommended_regression_scope_counts[scope] += 1
        governance_risk_top_items.append(
            {
                "task_id": str(item.get("task_id", "")).strip(),
                "run_id": str(item.get("run_id", "")).strip(),
                "case_id": str(item.get("case_id", "")).strip(),
                "page": str(item.get("page", "")).strip(),
                "source": str(item.get("source", "")).strip(),
                "queue_status": str(item.get("queue_status", "")).strip(),
                "manifest_action": manifest_action,
                "strict_mode_status": strict_mode_status,
                "strict_mode_reason": str(strict_mode.get("reason", "")).strip(),
                "evidence_health_status": str(evidence_health.get("status", "")).strip(),
                "evidence_freshness_status": freshness_status,
                "source_count": source_count,
                "source_types": _list_value(multisource_summary.get("source_types")),
                "traceability_completeness": multisource_summary.get("traceability_completeness", 0.0),
                "traceability_status": str(multisource_summary.get("traceability_status", "")).strip(),
                "has_traceability_gap": bool(multisource_summary.get("has_traceability_gap", False)),
                "changed_areas": _list_value(multisource_summary.get("changed_areas")),
                "top_factor": _dict_value(multisource_summary.get("top_factor")),
                "recommended_regression_scope": normalized_scopes,
                "gate_recommendation": gate_recommendation,
                "gate_recommendation_reason": gate_recommendation_reason,
                "governance_risk_level": str(governance_risk.get("level", "")).strip(),
                "governance_risk_score": int(governance_risk.get("score", 0) or 0),
                "governance_risk_reason": str(governance_risk.get("reason", "")).strip(),
            }
        )
        if manifest_action == "backfill_manifest":
            manifest_backfill_candidate_count += 1
            manifest_backfill_freshness_counts[freshness_status] += 1
        if bool(item.get("has_manifest", False)):
            has_manifest_count += 1
        retry = item.get("retry", {}) if isinstance(item.get("retry"), dict) else {}
        if bool(retry.get("enabled", False)):
            retry_enabled_task_count += 1
        dependency = item.get("dependency", {}) if isinstance(item.get("dependency"), dict) else {}
        if bool(dependency.get("has_dependencies", False)):
            dependency_task_count += 1
    total_tasks = len(items)
    manifest_first_task_count = int(source_counts.get("manifest", 0) or 0)
    compat_fallback_task_count = int(source_counts.get("compat_scan", 0) or 0)
    runtime_supplement_task_count = int(source_counts.get("runtime_realtime", 0) or 0) + int(source_counts.get("runtime_fallback", 0) or 0)
    if int(manifest_backfill_freshness_counts.get("stale", 0) or 0) > 0:
        manifest_backfill_priority = "urgent"
    elif int(manifest_backfill_freshness_counts.get("aging", 0) or 0) > 0:
        manifest_backfill_priority = "normal"
    elif manifest_backfill_candidate_count > 0:
        manifest_backfill_priority = "low"
    else:
        manifest_backfill_priority = "none"
    if int(governance_risk_counts.get("critical", 0) or 0) > 0:
        governance_risk_priority = "critical"
    elif int(governance_risk_counts.get("high", 0) or 0) > 0:
        governance_risk_priority = "high"
    elif int(governance_risk_counts.get("medium", 0) or 0) > 0:
        governance_risk_priority = "medium"
    elif int(governance_risk_counts.get("low", 0) or 0) > 0:
        governance_risk_priority = "low"
    else:
        governance_risk_priority = "none"
    governance_risk_top_items.sort(
        key=lambda item: (
            -int(item.get("governance_risk_score", 0) or 0),
            str(item.get("task_id", "")),
            str(item.get("run_id", "")),
        )
    )
    strict_mode_readiness = _dict_value(execution_meta.get("strict_mode_readiness"))
    strict_mode_ready_task_count = int(strict_mode_status_counts.get("ready", 0) or 0)
    strict_mode_caution_task_count = int(strict_mode_status_counts.get("caution", 0) or 0)
    strict_mode_blocked_task_count = int(strict_mode_status_counts.get("blocked", 0) or 0)
    strict_mode_can_disable_compat_builder = bool(strict_mode_readiness.get("can_disable_compat_builder", False)) or (
        total_tasks > 0
        and strict_mode_ready_task_count == total_tasks
        and strict_mode_caution_task_count == 0
        and strict_mode_blocked_task_count == 0
    )
    if int(gate_recommendation_counts.get("block", 0) or 0) > 0:
        recommended_regression_pack = "broad_regression"
    elif int(gate_recommendation_counts.get("manual_review", 0) or 0) > 0:
        recommended_regression_pack = "smoke_plus_impacted"
    else:
        recommended_regression_pack = "targeted_regression"
    return {
        "total_tasks": total_tasks,
        "status_counts": dict(sorted(status_counts.items())),
        "queue_status_counts": dict(sorted(queue_counts.items())),
        "runner_counts": dict(sorted(runner_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "evidence_health_counts": dict(sorted(evidence_health_counts.items())),
        "evidence_freshness_counts": dict(sorted(evidence_freshness_counts.items())),
        "manifest_action_counts": dict(sorted(manifest_action_counts.items())),
        "strict_mode_status_counts": dict(sorted(strict_mode_status_counts.items())),
        "manifest_first_task_count": manifest_first_task_count,
        "compat_fallback_task_count": compat_fallback_task_count,
        "runtime_supplement_task_count": runtime_supplement_task_count,
        "manifest_backfill_candidate_count": manifest_backfill_candidate_count,
        "manifest_backfill_freshness_counts": dict(sorted(manifest_backfill_freshness_counts.items())),
        "manifest_backfill_priority": manifest_backfill_priority,
        "multisource_task_count": multisource_task_count,
        "traceability_gap_task_count": traceability_gap_task_count,
        "traceability_partial_task_count": traceability_partial_task_count,
        "traceability_orphan_task_count": traceability_orphan_task_count,
        "traceability_unmapped_area_task_count": traceability_unmapped_area_task_count,
        "multisource_source_type_counts": dict(sorted(multisource_source_type_counts.items())),
        "recommended_regression_scope_counts": dict(sorted(recommended_regression_scope_counts.items())),
        "gate_recommendation_counts": dict(sorted(gate_recommendation_counts.items())),
        "recommended_regression_pack": recommended_regression_pack,
        "governance_risk_counts": dict(sorted(governance_risk_counts.items())),
        "governance_risk_priority": governance_risk_priority,
        "governance_risk_top_items": governance_risk_top_items[:5],
        "has_manifest_task_count": has_manifest_count,
        "no_manifest_task_count": max(total_tasks - has_manifest_count, 0),
        "retry_enabled_task_count": retry_enabled_task_count,
        "dependency_task_count": dependency_task_count,
        "manifest_first_ratio_visible": round((manifest_first_task_count / max(1, total_tasks)), 3),
        "compat_fallback_ratio_visible": round((compat_fallback_task_count / max(1, total_tasks)), 3),
        "runtime_supplement_ratio_visible": round((runtime_supplement_task_count / max(1, total_tasks)), 3),
        "strict_mode_ready_task_count": strict_mode_ready_task_count,
        "strict_mode_caution_task_count": strict_mode_caution_task_count,
        "strict_mode_blocked_task_count": strict_mode_blocked_task_count,
        "strict_mode_ready_ratio_visible": round((strict_mode_ready_task_count / max(1, total_tasks)), 3),
        "strict_mode_can_disable_compat_builder": strict_mode_can_disable_compat_builder,
        "retry_enabled_ratio_visible": round((retry_enabled_task_count / max(1, total_tasks)), 3),
        "dependency_ratio_visible": round((dependency_task_count / max(1, total_tasks)), 3),
        "strict_mode_readiness": strict_mode_readiness,
        "filter_snapshot": filter_snapshot,
        "execution_meta": execution_meta if isinstance(execution_meta, dict) else {},
    }
