from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import (
    workbench_analysis_service,
    workbench_asset_service,
    workbench_gate_service,
    workbench_generation_service,
    workbench_orchestrator_service,
    workbench_reporting_service,
    workbench_review_service,
    workbench_runtime_service,
    workbench_state_store,
)

from .candidate_normalizer import CandidateNormalizer
from .feature_flags import FeatureFlags
from .orchestrator_client import OrchestratorClient
from .orchestrator_client_factory import build_orchestrator_client
from .repository import WorkbenchGenerationRepository
from .scenario_engine import ScenarioEngine


def _identity_normalize_execution_record(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    _ = strict
    return payload if isinstance(payload, dict) else {}


def _identity_normalize_evidence_manifest(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    _ = strict
    return payload if isinstance(payload, dict) else {}


def _build_run_orchestrator_risk() -> Callable[..., dict[str, Any]]:
    settings = get_settings()

    def _run_orchestrator_risk(
        *,
        requirement_spec: dict[str, Any],
        execution_plan: dict[str, Any],
        execution_record: dict[str, Any],
        failure_analysis: dict[str, Any],
        failure_triage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        endpoint = f"{settings.orchestrator_url.rstrip('/')}/risk/evaluate"
        payload = {
            "requirement_spec": requirement_spec if isinstance(requirement_spec, dict) else {},
            "execution_plan": execution_plan if isinstance(execution_plan, dict) else {},
            "execution_record": execution_record if isinstance(execution_record, dict) else {},
            "failure_analysis": failure_analysis if isinstance(failure_analysis, dict) else {},
            "failure_triage": failure_triage if isinstance(failure_triage, dict) else {},
        }
        return workbench_orchestrator_service.post_json(
            endpoint,
            payload,
            timeout_seconds=settings.orchestrator_timeout_seconds,
            http_exception_cls=HTTPException,
            bad_gateway_status=status.HTTP_502_BAD_GATEWAY,
            gateway_timeout_status=status.HTTP_504_GATEWAY_TIMEOUT,
        )

    return _run_orchestrator_risk


_RUN_JOB_TTL_SECONDS = int(str(os.getenv("WORKBENCH_RUN_JOB_CACHE_TTL_SECONDS", "300")).strip() or "300")


def _is_within(path: Path, root: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except Exception:
        return False


@dataclass(frozen=True)
class WorkbenchRuntimeContext:
    ensure_dirs: Callable[[], None]
    now_iso: Callable[[], str]
    normalize_page_slug: Callable[[str], str]
    safe_case_id: Callable[[str], str]
    build_system_requirement: Callable[..., str]
    extract_page_from_url: Callable[..., tuple[str, str]]
    resolve_page_url: Callable[..., str]
    validate_page_surface_url: Callable[..., Any]
    extract_page_surface: Callable[..., dict[str, Any] | Any]
    normalize_page_surface: Callable[..., dict[str, Any]]
    normalize_page_object_draft: Callable[..., dict[str, Any]]
    build_surface_element_candidates: Callable[[str, dict[str, Any]], list[dict[str, Any]]]
    surface_confidence_summary: Callable[[dict[str, Any]], dict[str, Any]]
    enhance_page_object_from_surface: Callable[[str, dict[str, Any]], Any]
    build_requirement_steps: Callable[[str, str, str, dict[str, Any]], tuple[list[dict[str, Any]], dict[str, Any]]]
    build_page_object_quality: Callable[[str, str, dict[str, Any], Any], dict[str, Any]]
    build_requirement_spec_for_risk: Callable[..., dict[str, Any]]
    build_execution_plan_for_risk: Callable[..., dict[str, Any]]
    build_page_analysis_context: Callable[..., dict[str, Any]]
    build_test_point_review_items: Callable[[dict[str, Any]], list[dict[str, Any]]]
    build_review_section: Callable[..., dict[str, Any]]
    build_risk_review_items: Callable[[dict[str, Any]], list[dict[str, Any]]]
    review_decisions_for_run: Callable[..., dict[tuple[str, str], dict[str, Any]]]
    build_run_review_state_from_decisions: Callable[..., dict[str, Any]]
    build_item_review_state: Callable[..., dict[str, Any]]
    evaluate_risk_report: Callable[..., dict[str, Any]]
    build_execution_gate: Callable[..., dict[str, Any]]
    build_execution_gate_audit_snapshot: Callable[[dict[str, Any] | None], dict[str, Any]]
    build_test_point_asset_gate_context: Callable[..., dict[str, Any]]
    build_runtime_execution_record: Callable[..., dict[str, Any]]
    runtime_run_id: Callable[[dict[str, Any]], str]
    runtime_view_from_entry: Callable[[dict[str, Any]], dict[str, Any]]
    runtime_view_with_execution_record_preferred: Callable[[dict[str, Any]], dict[str, Any]]
    find_run_item: Callable[[str], dict[str, Any] | None]
    start_run: Callable[..., dict[str, Any]]
    wait_run_terminal: Callable[[str, int], tuple[dict[str, Any] | None, bool]]
    update_job: Callable[[str, dict[str, Any]], None]
    update_runtime_run: Callable[[str, dict[str, Any]], None]
    load_runtime_execution_record_from_artifacts: Callable[[Path], dict[str, Any]]
    report_allure_refresh: Callable[[], dict[str, Any]]
    build_run_command: Callable[[Path], tuple[list[str], dict[str, str]]]
    get_python_bin: Callable[[], str]
    read_case_yaml: Callable[..., tuple[dict[str, Any], str]]
    write_case_yaml: Callable[..., str]
    save_case_state: Callable[[str, dict[str, Any], Any], dict[str, Any]]
    save_test_point_plan: Callable[..., Path]
    append_history: Callable[[dict[str, Any]], None]
    append_runtime_run: Callable[[dict[str, Any]], None]
    read_json_list: Callable[[Path], list[dict[str, Any]]]
    normalize_test_point_plan: Callable[..., dict[str, Any]]
    steps_to_points: Callable[[str, str, list[dict[str, Any]]], dict[str, Any]]
    inherit_test_point_confidence_from_surface: Callable[..., dict[str, Any]]
    annotate_test_point_plan_review: Callable[[dict[str, Any]], dict[str, Any]]
    infer_targets: Callable[[str, Path], tuple[str, str]]
    collect_failure_entries: Callable[[], list[dict[str, Any]]]
    build_risk_report: Callable[..., dict[str, Any]]
    Path: type[Path]
    datetime: Any
    UTC: Any
    HTTPException: type[HTTPException]
    status: Any
    REPO_ROOT: Path
    RUNNER_ROOT: Path
    AI_CASES_ROOT: Path
    ASSETS_CASES_ROOT: Path
    ALLURE_RESULTS_ROOT: Path
    ALLURE_REPORT_ROOT: Path
    ALLURE_SNAPSHOTS_ROOT: Path

    def __getattr__(self, name: str) -> Any:
        alias_map = {
            "_normalize_page_slug": "normalize_page_slug",
            "_safe_case_id": "safe_case_id",
            "_build_system_requirement": "build_system_requirement",
            "_extract_page_from_url": "extract_page_from_url",
            "_resolve_page_url": "resolve_page_url",
            "_validate_page_surface_url": "validate_page_surface_url",
            "_extract_page_surface": "extract_page_surface",
            "_normalize_page_surface": "normalize_page_surface",
            "_normalize_page_object_draft": "normalize_page_object_draft",
            "_build_surface_element_candidates": "build_surface_element_candidates",
            "_surface_confidence_summary": "surface_confidence_summary",
            "_enhance_page_object_from_surface": "enhance_page_object_from_surface",
            "_build_requirement_steps": "build_requirement_steps",
            "_build_page_object_quality": "build_page_object_quality",
            "_build_requirement_spec_for_risk": "build_requirement_spec_for_risk",
            "_build_execution_plan_for_risk": "build_execution_plan_for_risk",
            "_build_page_analysis_context": "build_page_analysis_context",
            "_build_test_point_review_items": "build_test_point_review_items",
            "_build_review_section": "build_review_section",
            "_build_risk_review_items": "build_risk_review_items",
            "_build_run_review_state_from_decisions": "build_run_review_state_from_decisions",
            "_build_item_review_state": "build_item_review_state",
            "_evaluate_risk_report": "evaluate_risk_report",
            "_build_execution_gate": "build_execution_gate",
            "_build_execution_gate_audit_snapshot": "build_execution_gate_audit_snapshot",
            "_build_test_point_asset_gate_context": "build_test_point_asset_gate_context",
            "_build_runtime_execution_record": "build_runtime_execution_record",
            "_runtime_run_id": "runtime_run_id",
            "_runtime_view_from_entry": "runtime_view_from_entry",
            "_runtime_view_with_execution_record_preferred": "runtime_view_with_execution_record_preferred",
            "_find_run_item": "find_run_item",
            "_build_run_command": "build_run_command",
            "_get_python_bin": "get_python_bin",
            "_read_case_yaml": "read_case_yaml",
            "_write_case_yaml": "write_case_yaml",
            "_save_case_state": "save_case_state",
            "_save_test_point_plan": "save_test_point_plan",
            "_append_history": "append_history",
            "_append_runtime_run": "append_runtime_run",
            "_read_json_list": "read_json_list",
            "_normalize_test_point_plan_payload": "normalize_test_point_plan",
            "_steps_to_points": "steps_to_points",
            "_inherit_test_point_confidence_from_surface": "inherit_test_point_confidence_from_surface",
            "_annotate_test_point_plan_review": "annotate_test_point_plan_review",
            "_infer_targets": "infer_targets",
            "_collect_failure_entries": "collect_failure_entries",
            "_build_risk_report": "build_risk_report",
        }
        target = alias_map.get(name)
        if target and hasattr(self, target):
            return getattr(self, target)
        raise AttributeError(name)


@dataclass(frozen=True)
class WorkbenchGenerationContext:
    has_multisource_inputs: Callable[..., bool]
    resolve_effective_requirement: Callable[..., str]
    build_preview_response: Callable[..., dict[str, Any]]
    build_generated_case_payload: Callable[..., dict[str, Any]]
    prepare_auto_run_page_context: Callable[..., dict[str, Any]]
    build_auto_run_generate_failed_item: Callable[..., dict[str, Any]]
    persist_auto_run_generated_case: Callable[..., dict[str, Any]]
    build_auto_run_governance_context: Callable[..., dict[str, Any]]
    build_auto_run_item: Callable[..., dict[str, Any]]
    build_auto_run_summary: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class WorkbenchContext:
    db: Session
    orchestrator_client: OrchestratorClient
    candidate_normalizer: CandidateNormalizer
    scenario_engine: ScenarioEngine
    flags: FeatureFlags
    repository: WorkbenchGenerationRepository
    runtime: WorkbenchRuntimeContext
    generation: WorkbenchGenerationContext


def build_workbench_runtime_context() -> WorkbenchRuntimeContext:
    normalize_page_slug = workbench_gate_service.normalize_page_slug
    safe_case_id = workbench_gate_service.safe_case_id
    ensure_dirs = workbench_state_store.ensure_dirs
    runtime_root = workbench_state_store.REPO_ROOT
    runner_root = runtime_root / "runners" / "web-playwright-python"
    allure_report_root = runner_root / "allure-report"
    run_jobs: dict[str, dict[str, Any]] = {}
    run_jobs_lock = threading.Lock()

    runtime_view_from_entry = partial(
        workbench_runtime_service.runtime_view_from_entry,
        normalize_execution_record_payload=_identity_normalize_execution_record,
        normalize_page_slug=normalize_page_slug,
        build_page_analysis_context=workbench_analysis_service.build_page_analysis_context,
        build_item_review_state=partial(
            workbench_review_service.build_item_review_state,
            normalize_page_slug_fn=normalize_page_slug,
            build_page_analysis_context_fn=workbench_analysis_service.build_page_analysis_context,
            review_decisions_for_run_fn=partial(
                workbench_review_service.review_decisions_for_run,
                read_json_list_fn=workbench_state_store.read_json_list,
                review_decisions_file=workbench_state_store.REVIEW_DECISIONS_FILE,
                normalize_page_slug_fn=normalize_page_slug,
                normalize_review_type_fn=workbench_review_service.normalize_review_type,
                normalize_review_status_fn=workbench_review_service.normalize_review_status,
                sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
            ),
            build_test_point_review_items_fn=workbench_analysis_service.build_test_point_review_items,
            build_review_section_fn=workbench_analysis_service.build_review_section,
            build_risk_review_items_fn=workbench_analysis_service.build_risk_review_items,
        ),
        build_run_review_state_from_decisions=partial(
            workbench_review_service.build_run_review_state_from_decisions,
            review_decisions_for_run_fn=partial(
                workbench_review_service.review_decisions_for_run,
                read_json_list_fn=workbench_state_store.read_json_list,
                review_decisions_file=workbench_state_store.REVIEW_DECISIONS_FILE,
                normalize_page_slug_fn=normalize_page_slug,
                normalize_review_type_fn=workbench_review_service.normalize_review_type,
                normalize_review_status_fn=workbench_review_service.normalize_review_status,
                sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
            ),
            normalize_page_slug_fn=normalize_page_slug,
            build_review_section_fn=workbench_analysis_service.build_review_section,
        ),
        build_test_point_asset_gate_context=workbench_asset_service.build_test_point_asset_gate_context,
        build_execution_gate=workbench_gate_service.build_execution_gate,
        build_review_audit_summary=workbench_review_service.build_review_audit_summary,
        build_review_audit_timeline=workbench_review_service.build_review_audit_timeline,
        build_risk_report_summary=workbench_analysis_service.build_risk_report_summary,
        build_self_healing_summary=workbench_analysis_service.build_self_healing_summary,
        execution_gate_decision_for_run=workbench_gate_service.execution_gate_decision_for_run,
    )
    load_runtime_execution_record_from_artifacts = partial(
        workbench_runtime_service.load_runtime_execution_record_from_artifacts,
        normalize_evidence_manifest_payload=_identity_normalize_evidence_manifest,
        resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
        load_execution_record_payload_fn=partial(
            workbench_runtime_service.load_execution_record_payload,
            normalize_execution_record_payload=_identity_normalize_execution_record,
        ),
    )
    runtime_view_with_execution_record_preferred = partial(
        workbench_runtime_service.runtime_view_with_execution_record_preferred,
        runtime_view_from_entry_fn=runtime_view_from_entry,
        load_runtime_execution_record_from_artifacts=load_runtime_execution_record_from_artifacts,
        normalize_execution_record_payload=_identity_normalize_execution_record,
    )
    def _build_test_point_asset_semantic_summary(page: str, normalized_plan: dict[str, Any]) -> dict[str, Any]:
        return workbench_asset_service.build_test_point_asset_semantic_summary(
            page=page,
            normalized_plan=normalized_plan,
            normalize_page_slug_fn=normalize_page_slug,
            clamp_confidence=workbench_analysis_service._clamp_confidence,
        )

    def _build_test_point_asset_technique_summary(normalized_plan: dict[str, Any]) -> dict[str, Any]:
        return workbench_asset_service.build_test_point_asset_technique_summary(
            normalized_plan=normalized_plan,
        )

    def _normalize_test_point_plan_payload(payload: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        return workbench_analysis_service.normalize_test_point_plan(payload, strict=strict)

    upsert_test_point_asset_snapshot = partial(
        workbench_asset_service.upsert_test_point_asset_snapshot,
        now_iso_fn=workbench_state_store.now_iso,
        count_test_point_types_fn=workbench_asset_service.count_test_point_types,
        build_test_point_asset_semantic_summary_fn=_build_test_point_asset_semantic_summary,
        build_test_point_asset_technique_summary_fn=_build_test_point_asset_technique_summary,
        merge_reference_items_fn=workbench_asset_service.merge_reference_items,
    )
    save_case_state = partial(
        workbench_asset_service.save_case_state,
        safe_case_id_fn=safe_case_id,
        now_iso_fn=workbench_state_store.now_iso,
        derive_points_fn=workbench_asset_service.derive_points,
        state_case_file_fn=lambda project, case_id: workbench_asset_service.state_case_file(
            project,
            case_id,
            state_root=workbench_state_store.GENERATED_CASES_STATE_ROOT,
        ),
        state_case_versions_dir_fn=lambda project, case_id: workbench_asset_service.state_case_versions_dir(
            project,
            case_id,
            state_root=workbench_state_store.GENERATED_CASES_STATE_ROOT,
        ),
    )
    save_test_point_plan = partial(
        workbench_asset_service.save_test_point_plan,
        now_iso_fn=workbench_state_store.now_iso,
        normalize_test_point_plan_payload=_normalize_test_point_plan_payload,
        upsert_test_point_asset_snapshot=upsert_test_point_asset_snapshot,
        state_root=workbench_state_store.GENERATED_CASES_STATE_ROOT,
    )

    def _read_runtime_runs() -> list[dict[str, Any]]:
        return workbench_state_store.read_json_list(workbench_state_store.RUNTIME_RUNS_FILE)

    def _get_job(run_id: str) -> dict[str, Any] | None:
        with run_jobs_lock:
            job = run_jobs.get(run_id)
        if job:
            return runtime_view_with_execution_record_preferred(dict(job))
        for item in _read_runtime_runs():
            if workbench_runtime_service.runtime_run_id(item) == run_id:
                return runtime_view_with_execution_record_preferred(dict(item))
        return None

    def _store_run_job(run_id: str, job: dict[str, Any]) -> None:
        with run_jobs_lock:
            run_jobs[run_id] = dict(job)

    def _update_job(run_id: str, updates: dict[str, Any]) -> None:
        with run_jobs_lock:
            merged = dict(run_jobs.get(run_id, {"run_id": run_id}))
            merged.update(updates if isinstance(updates, dict) else {})
            merged["run_id"] = run_id
            run_jobs[run_id] = merged
        workbench_state_store.update_runtime_run(run_id, updates)

    def _find_run_item(run_id: str) -> dict[str, Any] | None:
        return workbench_runtime_service.find_run_item(
            run_id,
            get_job=_get_job,
            read_runtime_runs=_read_runtime_runs,
            runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
            runtime_view_with_execution_record_preferred_fn=runtime_view_with_execution_record_preferred,
        )

    def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
        return load_runtime_execution_record_from_artifacts(artifacts_dir)

    def _collect_failure_entries() -> list[dict[str, Any]]:
        return workbench_reporting_service.collect_failure_entries(
            collect_failure_entries_with_meta_fn=partial(
                workbench_reporting_service.collect_failure_entries_with_meta,
                compat_scan_enabled=False,
                artifact_roots=[workbench_state_store.WEB_UI_RUNS_DIR, workbench_state_store.WEB_UI_REPORTING_DIR],
                logger=None,
                normalize_evidence_manifest_payload=_identity_normalize_evidence_manifest,
                resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload=partial(
                    workbench_runtime_service.load_execution_record_payload,
                    normalize_execution_record_payload=_identity_normalize_execution_record,
                ),
                parse_analysis_file=partial(workbench_reporting_service.parse_analysis_file),
            ),
        )

    def _execute_run(job: dict[str, Any]) -> None:
        workbench_runtime_service.execute_run(
            job,
            build_run_command_fn=workbench_runtime_service.build_run_command,
            now_iso_fn=workbench_state_store.now_iso,
            update_job=_update_job,
            update_runtime_run=workbench_state_store.update_runtime_run,
            load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
            collect_failure_entries=_collect_failure_entries,
            is_within=_is_within,
            repo_root=runtime_root,
            runner_root=runner_root,
        )

    def _start_run(*, project: str, case_id: str, case_path: Path, source: str) -> dict[str, Any]:
        return workbench_runtime_service.start_run(
            project=project,
            case_id=case_id,
            case_path=case_path,
            source=source,
            runs_dir=workbench_state_store.WEB_UI_RUNS_DIR,
            now_iso_fn=workbench_state_store.now_iso,
            build_runtime_execution_record=partial(
                workbench_runtime_service.build_runtime_execution_record,
                normalize_execution_record_payload=_identity_normalize_execution_record,
            ),
            runtime_view_from_entry_fn=runtime_view_from_entry,
            store_run_job=_store_run_job,
            append_runtime_run=workbench_state_store.append_runtime_run,
            append_history=workbench_state_store.append_history,
            execute_run_fn=_execute_run,
        )

    def _wait_run_terminal(run_id: str, timeout_seconds: int) -> tuple[dict[str, Any] | None, bool]:
        try:
            return workbench_runtime_service.wait_run_terminal(
                run_id,
                timeout_seconds,
                find_run_item=_find_run_item,
            )
        except TypeError:
            return workbench_runtime_service.wait_run_terminal(run_id, timeout_seconds)

    def _report_allure_refresh() -> dict[str, Any]:
        return workbench_reporting_service.refresh_allure_report(
            python_bin=workbench_runtime_service.get_python_bin(repo_root=runtime_root),
            runner_root=runner_root,
            repo_root=runtime_root,
            allure_report_root=allure_report_root,
            run_command=subprocess.run,
            read_allure_summary=partial(
                workbench_reporting_service.read_allure_summary,
                allure_report_root=allure_report_root,
            ),
            read_allure_environment=partial(
                workbench_reporting_service.read_allure_environment,
                allure_report_root=allure_report_root,
            ),
            read_allure_executors=partial(
                workbench_reporting_service.read_allure_executors,
                allure_report_root=allure_report_root,
            ),
            ensure_allure_snapshot=partial(
                workbench_reporting_service.ensure_allure_snapshot,
                allure_report_root=allure_report_root,
                allure_snapshots_root=workbench_state_store.ALLURE_SNAPSHOTS_ROOT,
            ),
            get_allure_index_version=partial(
                workbench_reporting_service.get_allure_index_version,
                allure_report_root=allure_report_root,
            ),
        )

    return WorkbenchRuntimeContext(
        ensure_dirs=ensure_dirs,
        now_iso=workbench_state_store.now_iso,
        normalize_page_slug=normalize_page_slug,
        safe_case_id=safe_case_id,
        build_system_requirement=workbench_generation_service.build_system_requirement,
        extract_page_from_url=workbench_analysis_service.extract_page_from_url,
        resolve_page_url=workbench_analysis_service.resolve_page_url,
        validate_page_surface_url=workbench_analysis_service.validate_page_surface_url,
        extract_page_surface=workbench_analysis_service.extract_page_surface,
        normalize_page_surface=workbench_analysis_service.normalize_page_surface,
        normalize_page_object_draft=workbench_analysis_service.normalize_page_object_draft,
        build_surface_element_candidates=workbench_analysis_service.build_surface_element_candidates,
        surface_confidence_summary=workbench_analysis_service.surface_confidence_summary,
        enhance_page_object_from_surface=workbench_analysis_service.enhance_page_object_from_surface,
        build_requirement_steps=workbench_analysis_service.build_requirement_steps,
        build_page_object_quality=workbench_analysis_service.build_page_object_quality,
        build_requirement_spec_for_risk=workbench_generation_service.build_requirement_spec_for_risk,
        build_execution_plan_for_risk=workbench_generation_service.build_execution_plan_for_risk,
        build_page_analysis_context=workbench_analysis_service.build_page_analysis_context,
        build_test_point_review_items=workbench_analysis_service.build_test_point_review_items,
        build_review_section=workbench_analysis_service.build_review_section,
        build_risk_review_items=workbench_analysis_service.build_risk_review_items,
        review_decisions_for_run=partial(
            workbench_review_service.review_decisions_for_run,
            read_json_list_fn=workbench_state_store.read_json_list,
            review_decisions_file=workbench_state_store.REVIEW_DECISIONS_FILE,
            normalize_page_slug_fn=normalize_page_slug,
            normalize_review_type_fn=workbench_review_service.normalize_review_type,
            normalize_review_status_fn=workbench_review_service.normalize_review_status,
            sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
        ),
        build_run_review_state_from_decisions=partial(
            workbench_review_service.build_run_review_state_from_decisions,
            review_decisions_for_run_fn=partial(
                workbench_review_service.review_decisions_for_run,
                read_json_list_fn=workbench_state_store.read_json_list,
                review_decisions_file=workbench_state_store.REVIEW_DECISIONS_FILE,
                normalize_page_slug_fn=normalize_page_slug,
                normalize_review_type_fn=workbench_review_service.normalize_review_type,
                normalize_review_status_fn=workbench_review_service.normalize_review_status,
                sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
            ),
            normalize_page_slug_fn=normalize_page_slug,
            build_review_section_fn=workbench_analysis_service.build_review_section,
        ),
        build_item_review_state=partial(
            workbench_review_service.build_item_review_state,
            normalize_page_slug_fn=normalize_page_slug,
            build_page_analysis_context_fn=workbench_analysis_service.build_page_analysis_context,
            review_decisions_for_run_fn=partial(
                workbench_review_service.review_decisions_for_run,
                read_json_list_fn=workbench_state_store.read_json_list,
                review_decisions_file=workbench_state_store.REVIEW_DECISIONS_FILE,
                normalize_page_slug_fn=normalize_page_slug,
                normalize_review_type_fn=workbench_review_service.normalize_review_type,
                normalize_review_status_fn=workbench_review_service.normalize_review_status,
                sanitize_review_items_fn=workbench_review_service.sanitize_review_items,
            ),
            build_test_point_review_items_fn=workbench_analysis_service.build_test_point_review_items,
            build_review_section_fn=workbench_analysis_service.build_review_section,
            build_risk_review_items_fn=workbench_analysis_service.build_risk_review_items,
        ),
        evaluate_risk_report=partial(
            workbench_analysis_service.evaluate_risk_report,
            build_page_analysis_context_fn=workbench_analysis_service.build_page_analysis_context,
            build_requirement_spec_for_risk_fn=workbench_generation_service.build_requirement_spec_for_risk,
            build_execution_plan_for_risk_fn=workbench_generation_service.build_execution_plan_for_risk,
            find_run_item_fn=_find_run_item,
            build_runtime_execution_record_fn=partial(
                workbench_runtime_service.build_runtime_execution_record,
                normalize_execution_record_payload=_identity_normalize_execution_record,
            ),
            run_orchestrator_risk_fn=_build_run_orchestrator_risk(),
            build_risk_report_fn=workbench_analysis_service.build_risk_report,
            http_exception_cls=HTTPException,
        ),
        build_execution_gate=workbench_gate_service.build_execution_gate,
        build_execution_gate_audit_snapshot=workbench_gate_service.build_execution_gate_audit_snapshot,
        build_test_point_asset_gate_context=workbench_asset_service.build_test_point_asset_gate_context,
        build_runtime_execution_record=partial(
            workbench_runtime_service.build_runtime_execution_record,
            normalize_execution_record_payload=_identity_normalize_execution_record,
        ),
        runtime_run_id=workbench_runtime_service.runtime_run_id,
        runtime_view_from_entry=runtime_view_from_entry,
        runtime_view_with_execution_record_preferred=runtime_view_with_execution_record_preferred,
        find_run_item=_find_run_item,
        start_run=_start_run,
        wait_run_terminal=_wait_run_terminal,
        update_job=_update_job,
        update_runtime_run=workbench_state_store.update_runtime_run,
        load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
        report_allure_refresh=_report_allure_refresh,
        build_run_command=workbench_runtime_service.build_run_command,
        get_python_bin=workbench_runtime_service.get_python_bin,
        read_case_yaml=workbench_asset_service.read_case_yaml,
        write_case_yaml=workbench_asset_service.write_case_yaml,
        save_case_state=save_case_state,
        save_test_point_plan=save_test_point_plan,
        append_history=workbench_state_store.append_history,
        append_runtime_run=workbench_state_store.append_runtime_run,
        read_json_list=workbench_state_store.read_json_list,
        normalize_test_point_plan=workbench_analysis_service.normalize_test_point_plan,
        steps_to_points=workbench_analysis_service.steps_to_points,
        inherit_test_point_confidence_from_surface=workbench_analysis_service.inherit_test_point_confidence_from_surface,
        annotate_test_point_plan_review=workbench_analysis_service.annotate_test_point_plan_review,
        infer_targets=workbench_asset_service.infer_targets,
        collect_failure_entries=_collect_failure_entries,
        build_risk_report=workbench_analysis_service.build_risk_report,
        Path=Path,
        datetime=datetime,
        UTC=UTC,
        HTTPException=HTTPException,
        status=status,
        REPO_ROOT=workbench_state_store.REPO_ROOT,
        RUNNER_ROOT=workbench_state_store.REPO_ROOT / "runners" / "web-playwright-python",
        AI_CASES_ROOT=workbench_state_store.AI_CASES_ROOT,
        ASSETS_CASES_ROOT=workbench_state_store.ASSETS_CASES_ROOT,
        ALLURE_RESULTS_ROOT=workbench_state_store.REPO_ROOT / "runners" / "web-playwright-python" / "allure-results",
        ALLURE_REPORT_ROOT=workbench_state_store.REPO_ROOT / "runners" / "web-playwright-python" / "allure-report",
        ALLURE_SNAPSHOTS_ROOT=workbench_state_store.ALLURE_SNAPSHOTS_ROOT,
    )


def build_workbench_context(db: Session) -> WorkbenchContext:
    flags = FeatureFlags()
    repository = WorkbenchGenerationRepository(db)
    candidate_normalizer = CandidateNormalizer(flags)
    scenario_engine = ScenarioEngine(flags)
    orchestrator_client = build_orchestrator_client()
    runtime = build_workbench_runtime_context()
    generation = WorkbenchGenerationContext(
        has_multisource_inputs=workbench_generation_service.has_multisource_inputs,
        resolve_effective_requirement=partial(
            workbench_generation_service.resolve_effective_requirement,
            build_system_requirement=runtime.build_system_requirement,
        ),
        build_preview_response=partial(
            workbench_generation_service.build_preview_response,
            run_orchestrator_parse=orchestrator_client.parse,
            render_requirement_spec_markdown=orchestrator_client.render_requirement_spec_markdown,
            extract_quality_gate=orchestrator_client.extract_quality_gate,
        ),
        build_generated_case_payload=partial(
            workbench_generation_service.build_generated_case_payload,
            run_orchestrator_generate=orchestrator_client.generate,
            extract_quality_gate=orchestrator_client.extract_quality_gate,
            safe_case_id=runtime.safe_case_id,
            infer_targets=runtime.infer_targets,
            write_case_yaml=runtime.write_case_yaml,
            save_case_state=runtime.save_case_state,
            save_test_point_plan=runtime.save_test_point_plan,
            append_history=runtime.append_history,
            now_iso=runtime.now_iso,
            is_quality_gate_blocked=orchestrator_client.is_quality_gate_blocked,
            ai_cases_root=runtime.AI_CASES_ROOT,
            utc=runtime.UTC,
            datetime_module=runtime.datetime,
            http_exception_cls=runtime.HTTPException,
            bad_gateway_status=runtime.status.HTTP_502_BAD_GATEWAY,
            unprocessable_entity_status=422,
            allocate_case_id=repository.allocate_case_id,
        ),
        prepare_auto_run_page_context=partial(
            workbench_generation_service.prepare_auto_run_page_context,
            build_system_requirement=runtime.build_system_requirement,
            extract_page_from_url=runtime.extract_page_from_url,
            resolve_page_url=runtime.resolve_page_url,
            validate_page_surface_url=runtime.validate_page_surface_url,
            extract_page_surface=runtime.extract_page_surface,
            normalize_page_surface=runtime.normalize_page_surface,
            build_surface_element_candidates=runtime.build_surface_element_candidates,
            surface_confidence_summary=runtime.surface_confidence_summary,
            enhance_page_object_from_surface=runtime.enhance_page_object_from_surface,
            build_requirement_steps=runtime.build_requirement_steps,
            build_page_object_quality=runtime.build_page_object_quality,
            normalize_page_object_draft=runtime.normalize_page_object_draft,
        ),
        build_auto_run_generate_failed_item=workbench_generation_service.build_auto_run_generate_failed_item,
        persist_auto_run_generated_case=partial(
            workbench_generation_service.persist_auto_run_generated_case,
            safe_case_id=runtime.safe_case_id,
            write_case_yaml=runtime.write_case_yaml,
            read_case_yaml=runtime.read_case_yaml,
            save_case_state=runtime.save_case_state,
            normalize_test_point_plan_payload=runtime.normalize_test_point_plan,
            steps_to_points=runtime.steps_to_points,
            inherit_test_point_confidence_from_surface=runtime.inherit_test_point_confidence_from_surface,
            annotate_test_point_plan_review=runtime.annotate_test_point_plan_review,
            save_test_point_plan=runtime.save_test_point_plan,
            append_history=runtime.append_history,
            now_iso=runtime.now_iso,
            allocate_case_id=repository.allocate_case_id,
        ),
        build_auto_run_governance_context=partial(
            workbench_generation_service.build_auto_run_governance_context,
            build_page_analysis_context=runtime.build_page_analysis_context,
            build_item_review_state=runtime.build_item_review_state,
            evaluate_risk_report=runtime.evaluate_risk_report,
            build_execution_gate=runtime.build_execution_gate,
        ),
        build_auto_run_item=workbench_generation_service.build_auto_run_item,
        build_auto_run_summary=workbench_generation_service.build_auto_run_summary,
    )
    return WorkbenchContext(
        db=db,
        orchestrator_client=orchestrator_client,
        candidate_normalizer=candidate_normalizer,
        scenario_engine=scenario_engine,
        flags=flags,
        repository=repository,
        runtime=runtime,
        generation=generation,
    )
