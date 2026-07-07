"""Workbench runtime view functions —— 从 runtime entry 构建 UI 视图。

提取自 workbench_runtime_service.py 以控制单文件大小在 1000 行以内。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from shared_backend.case_ids import normalize_case_id
from shared_backend.type_utils import dict_value as _dict_value

from app.services.workbench_runtime_service import (
    NormalizeEvidenceManifestPayload,
    NormalizeExecutionRecordPayload,
    NormalizePageSlug,
    BuildPageAnalysisContext,
    BuildItemReviewState,
    BuildRunReviewStateFromDecisions,
    BuildTestPointAssetGateContext,
    BuildExecutionGate,
    BuildReviewAuditSummary,
    BuildReviewAuditTimeline,
    BuildRiskReportSummary,
    BuildSelfHealingSummary,
    ExecutionGateDecisionForRun,
    LoadRuntimeExecutionRecordFromArtifacts,
    build_runtime_execution_record,
    runtime_run_id,
)


def load_runtime_execution_record_from_artifacts(
    artifacts_dir: Path,
    *,
    normalize_evidence_manifest_payload: NormalizeEvidenceManifestPayload,
    resolve_manifest_entries_fn: Callable[[Any, Path], list[Path]],
    load_execution_record_payload_fn: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """从 artifacts 目录加载最新的 execution record。"""
    if not artifacts_dir.exists():
        return {}
    manifest_candidates = sorted(
        artifacts_dir.rglob("evidence_manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for manifest_path in manifest_candidates:
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, ValueError):
            continue
        manifest = normalize_evidence_manifest_payload(raw_manifest)
        record_paths = resolve_manifest_entries_fn(manifest.get("execution_record_files"), manifest_path.parent)
        for record_path in record_paths:
            execution_record = load_execution_record_payload_fn(record_path)
            if execution_record:
                return execution_record

    candidates = sorted(
        artifacts_dir.rglob("execution_record.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {}
    return load_execution_record_payload_fn(candidates[0])


def runtime_view_from_entry(
    entry: dict[str, Any],
    *,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
    normalize_page_slug: NormalizePageSlug,
    build_page_analysis_context: BuildPageAnalysisContext,
    build_item_review_state: BuildItemReviewState,
    build_run_review_state_from_decisions: BuildRunReviewStateFromDecisions,
    build_test_point_asset_gate_context: BuildTestPointAssetGateContext,
    build_execution_gate: BuildExecutionGate,
    build_review_audit_summary: BuildReviewAuditSummary,
    build_review_audit_timeline: BuildReviewAuditTimeline,
    build_risk_report_summary: BuildRiskReportSummary,
    build_self_healing_summary: BuildSelfHealingSummary,
    execution_gate_decision_for_run: ExecutionGateDecisionForRun,
) -> dict[str, Any]:
    """从 runtime entry 构建完整的 UI 视图字典。"""
    source = entry if isinstance(entry, dict) else {}
    run_id = runtime_run_id(source)
    execution_record_raw = source.get("execution_record") if isinstance(source.get("execution_record"), dict) else {}
    if execution_record_raw:
        execution_record = normalize_execution_record_payload(execution_record_raw)
    else:
        execution_record = build_runtime_execution_record(
            run_id=run_id,
            case_id=str(source.get("case_id", "")).strip(),
            project=str(source.get("project", "mall")).strip() or "mall",
            source=str(source.get("source", "manual")).strip() or "manual",
            mode=str(source.get("mode", "generate_and_run")).strip() or "generate_and_run",
            status=str(source.get("status", "queued")).strip() or "queued",
            started_at=str(source.get("started_at", "")).strip(),
            finished_at=str(source.get("finished_at", "")).strip(),
            return_code=source.get("return_code"),
            created_at=str(source.get("created_at", "")).strip(),
            normalize_execution_record_payload=normalize_execution_record_payload,
        )

    status_value = str(source.get("status", "")).strip() or str(execution_record.get("status", "queued")).strip() or "queued"
    started_at = str(source.get("started_at", "")).strip() or str(execution_record.get("started_at", "")).strip()
    finished_at = str(source.get("finished_at", "")).strip() or str(execution_record.get("finished_at", "")).strip()
    mode_value = str(source.get("mode", "")).strip() or str(execution_record.get("mode", "generate_and_run")).strip() or "generate_and_run"
    project_value = str(source.get("project", execution_record.get("project", "mall"))).strip() or "mall"
    case_id_value = normalize_case_id(str(source.get("case_id", execution_record.get("case_id", ""))).strip()) if str(source.get("case_id", execution_record.get("case_id", ""))).strip() else ""
    inferred_page = [
        str(source.get("page", "")).strip(),
        str((source.get("page_surface", {}) or {}).get("page", "")).strip() if isinstance(source.get("page_surface"), dict) else "",
        str((source.get("page_object", {}) or {}).get("page", "")).strip() if isinstance(source.get("page_object"), dict) else "",
        str((source.get("test_points", {}) or {}).get("page", "")).strip() if isinstance(source.get("test_points"), dict) else "",
        str((execution_record.get("step_summary", {}) or {}).get("page", "")).strip() if isinstance(execution_record.get("step_summary"), dict) else "",
    ]
    page_value = ""
    for candidate in inferred_page:
        if candidate:
            page_value = normalize_page_slug(candidate)
            break

    has_model_payload = any(
        isinstance(source.get(key), dict)
        for key in ("page_surface", "page_surface_summary", "page_object", "page_object_summary", "test_points")
    )
    page_surface_payload = _dict_value(source.get("page_surface"))
    page_surface_summary = _dict_value(source.get("page_surface_summary"))
    if not page_surface_payload and page_surface_summary:
        page_surface_payload = {"confidence_summary": page_surface_summary}
    page_object_payload = _dict_value(source.get("page_object"))
    page_object_summary = _dict_value(source.get("page_object_summary"))
    if not page_object_payload and page_object_summary:
        page_object_payload = {"summary": page_object_summary}
    test_points_payload = _dict_value(source.get("test_points"))

    analysis_context: dict[str, Any] = {}
    if has_model_payload and page_value:
        analysis_context = build_page_analysis_context(
            page=page_value, project=project_value, case_id=case_id_value,
            page_url=str(source.get("page_url", "")).strip(),
            page_surface=page_surface_payload, page_object=page_object_payload,
            test_points=test_points_payload,
        )

    consumed_page_semantic_summary = _dict_value(analysis_context.get("page_semantic_summary")) or _dict_value(source.get("page_semantic_summary"))
    consumed_page_object_summary = _dict_value(analysis_context.get("page_object_summary")) or page_object_summary
    consumed_surface_summary = _dict_value(analysis_context.get("page_surface_summary")) or page_surface_summary
    consumed_test_points = _dict_value(analysis_context.get("test_points")) or test_points_payload
    consumed_model_versions = _dict_value(analysis_context.get("model_versions"))

    risk_report = _dict_value(source.get("risk_report"))
    if risk_report and any(consumed_model_versions.values()):
        risk_metadata = _dict_value(risk_report.get("metadata"))
        if not isinstance(risk_metadata.get("consumed_models"), dict):
            risk_metadata["consumed_models"] = consumed_model_versions
            risk_report = {**risk_report, "metadata": risk_metadata}

    stored_review_state = _dict_value(source.get("review_state"))
    review_state: dict[str, Any] = {}
    if has_model_payload and page_value:
        review_state = build_item_review_state(
            project=project_value, run_id=run_id, page=page_value,
            page_surface_summary=consumed_surface_summary,
            test_points=consumed_test_points,
            page_surface=_dict_value(analysis_context.get("page_surface")) or page_surface_payload,
            page_object=_dict_value(analysis_context.get("page_object")) or page_object_payload,
            risk_report=risk_report,
        )
    if not review_state:
        latest_review_state = build_run_review_state_from_decisions(project=project_value, run_id=run_id, page=page_value)
        review_state = latest_review_state or stored_review_state

    test_point_asset_context: dict[str, Any] = {}
    if page_value and case_id_value:
        test_point_asset_context = build_test_point_asset_gate_context(
            project=project_value, case_id=case_id_value, page=page_value,
            coverage=source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
            review_state=review_state if isinstance(review_state, dict) else {},
            risk_report=risk_report if isinstance(risk_report, dict) else {},
        )

    stored_execution_gate = _dict_value(source.get("execution_gate"))
    execution_gate = stored_execution_gate
    if (not isinstance(execution_gate, dict) or not execution_gate) and page_value and (has_model_payload or test_point_asset_context):
        execution_gate = build_execution_gate(
            page=page_value, final_status=status_value,
            coverage=source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
            page_surface_summary=consumed_surface_summary,
            page_semantic_summary=consumed_page_semantic_summary,
            page_object_summary=consumed_page_object_summary,
            test_points=consumed_test_points,
            review_state=review_state if isinstance(review_state, dict) else {},
            risk_report=risk_report if isinstance(risk_report, dict) else {},
            test_point_asset_context=test_point_asset_context,
        )
    latest_gate_decision = execution_gate_decision_for_run(run_id=run_id, project=project_value, page=page_value)
    if latest_gate_decision:
        approval_status = str(latest_gate_decision.get("approval_status", "approved")).strip() or "approved"
        record_status = str(latest_gate_decision.get("record_status", "active")).strip() or "active"
        gate_manual = {
            "decision": str(latest_gate_decision.get("decision", "")).strip(),
            "note": str(latest_gate_decision.get("note", "")).strip(),
            "decided_by": str(latest_gate_decision.get("decided_by", "")).strip() or "anonymous",
            "decided_by_role": str(latest_gate_decision.get("decided_by_role", "")).strip() or "unknown",
            "updated_at": str(latest_gate_decision.get("updated_at", "")).strip(),
            "approval_status": approval_status, "record_status": record_status,
            "second_approver": str(latest_gate_decision.get("second_approver", "")).strip(),
            "second_approver_role": str(latest_gate_decision.get("second_approver_role", "")).strip(),
            "second_approved_at": str(latest_gate_decision.get("second_approved_at", "")).strip(),
            "revoked_at": str(latest_gate_decision.get("revoked_at", "")).strip(),
            "revoked_by": str(latest_gate_decision.get("revoked_by", "")).strip(),
            "revoked_by_role": str(latest_gate_decision.get("revoked_by_role", "")).strip(),
        }
        if not isinstance(execution_gate, dict) or not execution_gate:
            execution_gate = {
                "version": "ExecutionGateV1", "page": page_value,
                "decision": gate_manual["decision"],
                "requires_review": gate_manual["decision"] != "allow",
                "blockers": [], "warnings": [], "metrics": {},
            }
        execution_gate["manual_decision"] = gate_manual
        execution_gate["approval_status"] = approval_status
        execution_gate["record_status"] = record_status
        execution_gate["second_approver"] = gate_manual["second_approver"]
        execution_gate["second_approver_role"] = gate_manual["second_approver_role"]
        execution_gate["second_approved_at"] = gate_manual["second_approved_at"]
        execution_gate["revoked_at"] = gate_manual["revoked_at"]
        execution_gate["revoked_by"] = gate_manual["revoked_by"]
        execution_gate["revoked_by_role"] = gate_manual["revoked_by_role"]
        if record_status == "revoked":
            execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
            execution_gate["decision_source"] = "manual_revoked"
            execution_gate["requires_review"] = bool(execution_gate.get("requires_review", False))
        elif approval_status == "pending_second_approval":
            execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
            execution_gate["decision_source"] = "manual_pending_second_approval"
            execution_gate["requires_review"] = True
        else:
            execution_gate["effective_decision"] = gate_manual["decision"]
            execution_gate["decision_source"] = "manual_override"
    elif isinstance(execution_gate, dict) and execution_gate:
        execution_gate["effective_decision"] = str(execution_gate.get("decision", "")).strip() or "allow"
        execution_gate["decision_source"] = "system"

    review_audit_summary = build_review_audit_summary(review_state)
    review_audit_timeline = build_review_audit_timeline(run_id=run_id, page=page_value)
    risk_summary = build_risk_report_summary(risk_report)
    self_healing_summary = build_self_healing_summary(
        execution_record=execution_record,
        artifacts_dir=str(source.get("artifacts_dir", "")).strip(),
    )

    return {
        "run_id": run_id, "project": project_value, "case_id": case_id_value,
        "case_path": str(source.get("case_path", "")).strip(),
        "page": page_value,
        "source": str(source.get("source", execution_record.get("source", "manual"))).strip() or "manual",
        "mode": mode_value, "status": status_value,
        "created_at": str(source.get("created_at", "")).strip(),
        "started_at": started_at, "finished_at": finished_at,
        "return_code": source.get("return_code"),
        "log_path": str(source.get("log_path", "")).strip(),
        "artifacts_dir": str(source.get("artifacts_dir", "")).strip(),
        "videos_dir": str(source.get("videos_dir", "")).strip(),
        "latest_failure": source.get("latest_failure", {}) if isinstance(source.get("latest_failure"), dict) else {},
        "coverage": source.get("coverage", {}) if isinstance(source.get("coverage"), dict) else {},
        "page_semantic": analysis_context.get("page_semantic", {}) if isinstance(analysis_context.get("page_semantic"), dict) else (source.get("page_semantic") if isinstance(source.get("page_semantic"), dict) else {}),
        "page_semantic_summary": consumed_page_semantic_summary,
        "page_object_summary": consumed_page_object_summary,
        "risk_report": risk_report, "risk_summary": risk_summary,
        "self_healing_summary": self_healing_summary,
        "execution_gate": execution_gate,
        "review_state": review_state,
        "review_audit_summary": review_audit_summary,
        "review_audit_timeline": review_audit_timeline,
        "execution_record": normalize_execution_record_payload({
            **execution_record,
            "run_id": run_id, "case_id": case_id_value, "project": project_value,
            "source": str(source.get("source", execution_record.get("source", "manual"))).strip() or "manual",
            "mode": mode_value, "status": status_value,
            "started_at": started_at, "finished_at": finished_at,
            "evidence_index": execution_record.get("evidence_index", {}),
            "metadata": {
                **(execution_record.get("metadata", {}) if isinstance(execution_record.get("metadata"), dict) else {}),
                "runtime_state_source": "runtime-store",
                "case_path": str(source.get("case_path", "")).strip(),
                "log_path": str(source.get("log_path", "")).strip(),
                "artifacts_dir": str(source.get("artifacts_dir", "")).strip(),
                "videos_dir": str(source.get("videos_dir", "")).strip(),
            },
        }),
    }


def runtime_view_with_execution_record_preferred(
    entry: dict[str, Any],
    *,
    runtime_view_from_entry_fn: Callable[[dict[str, Any]], dict[str, Any]],
    load_runtime_execution_record_from_artifacts: LoadRuntimeExecutionRecordFromArtifacts,
    normalize_execution_record_payload: NormalizeExecutionRecordPayload,
) -> dict[str, Any]:
    """构建 runtime view，优先使用 artifacts 中的 execution record 覆盖。"""
    view = runtime_view_from_entry_fn(entry)
    artifacts_dir_value = str(view.get("artifacts_dir", "")).strip()
    if not artifacts_dir_value:
        return view
    artifact_execution_record = load_runtime_execution_record_from_artifacts(Path(artifacts_dir_value))
    if not artifact_execution_record:
        return view

    runtime_execution_record = _dict_value(view.get("execution_record"))
    normalized_execution_record = normalize_execution_record_payload({
        **artifact_execution_record,
        "run_id": str(artifact_execution_record.get("run_id", "")).strip() or str(view.get("run_id", "")).strip(),
        "case_id": str(artifact_execution_record.get("case_id", "")).strip() or str(view.get("case_id", "")).strip(),
        "project": str(artifact_execution_record.get("project", "")).strip() or str(view.get("project", "mall")).strip(),
        "source": str(artifact_execution_record.get("source", "")).strip() or str(view.get("source", "manual")).strip(),
        "mode": str(artifact_execution_record.get("mode", "")).strip() or str(view.get("mode", "generate_and_run")).strip(),
        "metadata": {
            **(runtime_execution_record.get("metadata", {}) if isinstance(runtime_execution_record.get("metadata"), dict) else {}),
            **(artifact_execution_record.get("metadata", {}) if isinstance(artifact_execution_record.get("metadata"), dict) else {}),
            "runtime_realtime_supplement": True,
        },
    })
    evidence_index = normalized_execution_record.get("evidence_index", {}) if isinstance(normalized_execution_record.get("evidence_index"), dict) else {}
    runner_exit_code = evidence_index.get("runner_exit_code")
    return {
        **view,
        "status": str(normalized_execution_record.get("status", "")).strip() or str(view.get("status", "")).strip(),
        "started_at": str(normalized_execution_record.get("started_at", "")).strip() or str(view.get("started_at", "")).strip(),
        "finished_at": str(normalized_execution_record.get("finished_at", "")).strip() or str(view.get("finished_at", "")).strip(),
        "return_code": runner_exit_code if isinstance(runner_exit_code, int) else view.get("return_code"),
        "execution_record": normalized_execution_record,
    }
