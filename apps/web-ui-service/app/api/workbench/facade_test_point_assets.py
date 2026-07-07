
"""WorkbenchFacade 混入 —— 测试点资产相关方法。

提取自 facade.py 以控制单文件大小在 2500 行以内。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from shared_backend.datetime_compat import UTC
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence
import yaml

from fastapi import HTTPException, Response, status
from shared_backend import get_dictionary_items
from shared_backend.case_ids import match_case_id, normalize_case_id
from shared_backend.element_binding import build_element_alias_map, resolve_element_code, resolve_involved_element_codes
from shared_backend.schemas.contracts import normalize_test_point_plan_v1
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.workbench import constants, store
from app.services import test_point_asset_store
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core import page_analysis_rules
from app.repositories.page_object_repository import PageObjectRepository
from app.repositories.test_case_repository import TestCaseRepository
from app.models.page_object import PageElement
from app.models.test_case import TestCase, TestCaseExecution
from app.services import (
    test_project_service,
    test_case_service,
    test_data_pool_service,
    workbench_analysis_service,
    workbench_asset_service,
    workbench_case_consistency_service,
    workbench_gate_service,
    workbench_governance_service,
    workbench_history_service,
    workbench_reporting_service,
    workbench_review_service,
    workbench_runtime_service,
    workbench_scheduler_service,
    workbench_task_service,
)
from app.services.workbench_asset_views import check_generate_gate, check_approve_point_gate
from app.services.workbench_generation_api.payloads import GenerateCasePayload as GenerationGenerateCasePayload
from app.services.workbench_generation_api.usecase_factory import build_generate_case_usecase

from ._http import get_json as _get_json
from ._helpers import (
    build_empty_trend as _build_empty_trend,
    default_overview as _default_overview,
    is_within as _is_within,
    normalize_generation_case_source as _normalize_generation_case_source,
    normalize_optional_project_code as _normalize_optional_project_code,
    normalize_test_point_review_status as _normalize_test_point_review_status,
    parse_iso_datetime as _parse_iso_datetime,
    python_literal as _python_literal,
    read_json_file as _read_json_file,
    safe_python_identifier as _safe_python_identifier,
    safe_rollback_or_invalidate as _safe_rollback_or_invalidate,
    text as _text,
    text_list as _text_list,
    to_utc as _to_utc,
    utc_now as _utc_now,
    validate_test_point_review_status as _validate_test_point_review_status,
    write_json_file as _write_json_file,
)
from .service import WorkbenchService
from .service import (
    _append_history,
    _append_runtime_run,
    _build_execution_task_summary,
    _build_execution_task_view,
    _collect_execution_records_with_meta,
    _collect_failure_entries,
    _collect_failure_entries_with_meta,
    _ensure_dirs,
    _execution_record_time_value,
    _load_runtime_execution_record_from_artifacts,
    _normalize_execution_record_payload,
    _normalize_failure_entry_view,
    _read_json_list,
    _runtime_run_id,
    _runtime_view_from_entry,
    _runtime_view_with_execution_record_preferred,
    _safe_case_id,
    _sync_stage_a_workbench_state,
    _sync_stage_b_workbench_gate,
    _update_runtime_run,
    _write_json_list,
)
import logging
LOGGER = logging.getLogger(__name__)
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

# 从 facade 导入模块级 helper 函数（facade 在导入本混入前已定义这些函数）
from .facade_helpers import (  # noqa: E402
    _settings, _build_runtime_view_from_entry, _attach_test_point_asset_summary,
    _review_status_from_point, _review_status_from_candidate, _review_summary_from_points,
    _test_point_asset_state_paths, _is_generation_qualified_element,
    _page_object_generation_context, _test_point_generation_state,
    _normalize_points_involved_elements, _review_history_from_point,
    _normalize_asset_involved_elements_on_read,
    _asset_display_title,
    _build_test_point_script_preview, _source_identity_from_case,
    _structured_requirement_metadata_from_case, _existing_case_id_for_source_intent,
    _case_family_prefix, _point_title, _point_review_status, _generated_case_plan_items,
    _generation_failure_summary, _record_generation_failure, _generation_failure_index,
    _build_generation_diagnostics_for_asset, _source_asset_index, _source_asset_for_case,
    _asset_title_index, _intent_type_from_case, _active_state_from_case,
    _page_object_url_map, _latest_execution_map, _persist_runtime_run_to_case_center,
    _workbench_test_case_list_item, _steps_from_candidate, _candidate_snapshot_from_candidate,
    _manual_point_from_candidate, _point_step_texts, _steps_hint_from_current_steps,
    _candidate_from_asset_point,
)


class WorkbenchFacadeTestPointAssetsMixin:
    """测试点资产管理的混入类。"""
    def list_test_point_assets(
        self,
        *,
        project: str,
        page: str,
        keyword: str,
        source_type: str,
        coverage_status: str,
        review_status: str,
        gate_decision: str,
        selection_state: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_point_assets 接口实现。"""
        store.ensure_dirs()
        # DB 事实源:把 DB 中缺失缓存文件的资产回写为缓存,保证文件枚举与 DB 一致。
        db_asset_ids: set[str] = set()
        try:
            test_point_asset_store.sync_cache_from_db(
                db,
                project=project,
                project_dir=workbench_asset_service.state_project_dir(project, state_root=constants.TEST_POINTS_ROOT),
            )
            db_asset_ids = set(test_point_asset_store.list_asset_ids(db, project=project))
        except Exception:  # noqa: BLE001 - 缓存重建降级,不阻断列表
            LOGGER.warning("test point asset cache sync from DB failed for %s", project, exc_info=True)
        payload = workbench_asset_service.build_test_point_asset_items(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            db_asset_ids=db_asset_ids,
            state_project_dir=lambda code: workbench_asset_service.state_project_dir(code, state_root=constants.TEST_POINTS_ROOT),
            normalize_page_slug=workbench_gate_service.normalize_page_slug,
            load_test_point_asset=lambda project_value, case_id_value: (
                test_point_asset_store.load_asset(db, project=project_value, asset_id=case_id_value)
                or workbench_asset_service.load_test_point_asset_with_root(
                    project_value,
                    case_id_value,
                    state_root=constants.TEST_POINTS_ROOT,
                )
            ),
            latest_run_snapshot_for_case=lambda project, case_id, page="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project,
                case_id=case_id,
                page=page,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            build_coverage_summary=lambda items, filter_snapshot: workbench_asset_service.build_test_point_asset_coverage_summary(
                items=items,
                filter_snapshot=filter_snapshot,
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        # DB 事实源:有 DB 数据时过滤掉文件残留的已删除资产
        if db_asset_ids:
            items = payload.get("items", [])
            if isinstance(items, list):
                payload["items"] = [item for item in items if isinstance(item, dict) and item.get("asset_id", "") in db_asset_ids]
                payload["count"] = len(payload["items"])
        payload["coverage_summary"] = workbench_asset_service.build_test_point_asset_coverage_summary(
            items=payload.get("items", []),
            filter_snapshot=payload["selection_summary"].get("filter_snapshot", {}),
        )
        return payload

    def get_test_point_asset_coverage_summary(self, *, project: str, page: str, keyword: str, source_type: str, coverage_status: str, review_status: str, gate_decision: str, selection_state: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset_coverage_summary 接口实现。"""
        payload = self.list_test_point_assets(
            project=project,
            page=page,
            keyword=keyword,
            source_type=source_type,
            coverage_status=coverage_status,
            review_status=review_status,
            gate_decision=gate_decision,
            selection_state=selection_state,
            db=db,
        )
        return {"item": payload.get("coverage_summary", {})}

    def list_test_point_reviews(
        self,
        *,
        project: str,
        page: str,
        keyword: str,
        status_filter: str,
        intent_type: str,
        priority: str,
        can_generate: str,
        page_index: int,
        page_size: int,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_point_reviews 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        normalized_page = workbench_gate_service.normalize_page_slug(_text(page)) if _text(page) else ""
        normalized_status = _normalize_test_point_review_status(status_filter) if _text(status_filter) else ""
        normalized_type = _text(intent_type).lower()
        normalized_priority = _text(priority).upper()
        can_generate_filter = _text(can_generate).lower()
        keyword_value = _text(keyword).lower()
        project_dir = workbench_asset_service.state_project_dir(normalized_project, state_root=constants.TEST_POINTS_ROOT)
        case_ids: set[str] = set()
        if project_dir.exists():
            case_ids.update(file.stem for file in project_dir.glob("*.json") if file.is_file())
            plans_dir = project_dir / "plans"
            if plans_dir.exists():
                case_ids.update(file.stem for file in plans_dir.glob("*.json") if file.is_file())

        page_context_cache: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        for case_id in sorted(case_ids):
            asset = workbench_asset_service.load_test_point_asset_with_root(
                normalized_project,
                case_id,
                state_root=constants.TEST_POINTS_ROOT,
            )
            if not asset:
                continue
            asset_id = _text(asset.get("asset_id")) or case_id
            asset_page = workbench_gate_service.normalize_page_slug(_text(asset.get("page"))) if _text(asset.get("page")) else ""
            if normalized_page and asset_page != normalized_page:
                continue
            plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
            points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
            if asset_page not in page_context_cache:
                page_context_cache[asset_page] = _page_object_generation_context(db, project=normalized_project, page=asset_page)
            page_context = page_context_cache[asset_page]
            for point in points:
                candidate = _candidate_from_asset_point(
                    point,
                    fallback_title=_text(asset.get("title")) or asset_id,
                    fallback_priority=_text(asset.get("priority")) or "P1",
                )
                point_status = _review_status_from_candidate(candidate)
                if normalized_status and point_status != normalized_status:
                    continue
                row_type = _text(candidate.get("intent_type")).lower()
                row_priority = _text(candidate.get("priority")).upper()
                if normalized_type and row_type != normalized_type:
                    continue
                if normalized_priority and row_priority != normalized_priority:
                    continue
                generation_state = _test_point_generation_state(point, page_context=page_context)
                if can_generate_filter in {"true", "yes", "ready", "can_generate", "available"} and generation_state["can_generate"] is not True:
                    continue
                if can_generate_filter in {"false", "no", "blocked", "block"} and generation_state["can_generate"] is True:
                    continue
                steps = _text_list(candidate.get("steps"))
                row = {
                    "asset_id": asset_id,
                    "asset_title": _text(asset.get("title")) or asset_id,
                    "project": normalized_project,
                    "page": asset_page,
                    "page_url": _text(page_context.get("page_url")),
                    "intent_id": _text(candidate.get("intent_id")),
                    "title": _text(candidate.get("title") or candidate.get("summary")),
                    "summary": _text(candidate.get("summary") or candidate.get("title")),
                    "intent_type": _text(candidate.get("intent_type")) or "functional",
                    "priority": _text(candidate.get("priority")) or _text(asset.get("priority")) or "P1",
                    "precondition": _text(candidate.get("precondition")),
                    "steps": steps,
                    "steps_summary": " / ".join(steps[:3]),
                    "expected": _text(candidate.get("expected") or candidate.get("expected_result")),
                    "involved_elements": _text_list(candidate.get("involved_elements")),
                    "review_status": point_status,
                    "review_note": _text(candidate.get("review_note")),
                    "reviewed_at": _text(candidate.get("reviewed_at")),
                    "reviewed_by": _text(candidate.get("reviewed_by")),
                    "element_binding_status": generation_state["element_binding_status"],
                    "involved_element_codes": generation_state["involved_element_codes"],
                    "unknown_elements": generation_state["unknown_elements"],
                    "element_bindings": generation_state["element_bindings"],
                    "can_generate": generation_state["can_generate"],
                    "generation_blockers": generation_state["generation_blockers"],
                    "review_history": _review_history_from_point(point),
                    "updated_at": _text(asset.get("updated_at")),
                }
                haystack = " ".join(
                    [
                        row["asset_id"],
                        row["asset_title"],
                        row["page"],
                        row["intent_id"],
                        row["title"],
                        row["summary"],
                        row["steps_summary"],
                        row["expected"],
                        " ".join(row["generation_blockers"]),
                    ]
                ).lower()
                if keyword_value and keyword_value not in haystack:
                    continue
                items.append(row)

        items.sort(
            key=lambda item: (
                str(item.get("updated_at", "")).strip(),
                str(item.get("asset_id", "")).strip(),
                str(item.get("intent_id", "")).strip(),
            ),
            reverse=True,
        )
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        page_items = items[start:end]
        summary = {
            "total": total_items,
            "pending_count": sum(1 for item in items if item.get("review_status") == "pending"),
            "approved_count": sum(1 for item in items if item.get("review_status") == "approved"),
            "rejected_count": sum(1 for item in items if item.get("review_status") == "rejected"),
            "can_generate_count": sum(1 for item in items if item.get("can_generate") is True),
            "blocked_count": sum(1 for item in items if item.get("can_generate") is not True),
        }
        return {
            "items": page_items,
            "summary": summary,
            "filters": {
                "project": normalized_project,
                "page": normalized_page,
                "keyword": keyword_value,
                "status": normalized_status,
                "intent_type": normalized_type,
                "priority": normalized_priority,
                "can_generate": can_generate_filter,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def batch_review_test_points(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.batch_review_test_points 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(getattr(payload, "project", "")) or "mall"
        project_record = test_project_service.ensure_project_active_for_write(db, normalized_project)
        normalized_project = _text(getattr(project_record, "project_code", normalized_project)) or normalized_project
        next_status = _validate_test_point_review_status(getattr(payload, "status", ""))
        note = _text(getattr(payload, "note", ""))
        reviewed_by = _text(getattr(payload, "reviewed_by", "")) or "admin"
        reviewed_at = store.now_iso()
        grouped: dict[str, set[str]] = defaultdict(set)
        for decision in getattr(payload, "decisions", []) or []:
            asset_id = _safe_case_id(getattr(decision, "asset_id", "") if not isinstance(decision, dict) else decision.get("asset_id", ""))
            intent_id = _text(getattr(decision, "intent_id", "") if not isinstance(decision, dict) else decision.get("intent_id", ""))
            if asset_id and intent_id:
                grouped[asset_id].add(intent_id)
        if not grouped:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="decisions must not be empty")

        updated_count = 0
        affected_assets: list[str] = []
        missing: list[dict[str, str]] = []
        for asset_id, intent_ids in grouped.items():
            asset_path, plan_path = _test_point_asset_state_paths(normalized_project, asset_id)
            asset_payload = _read_json_file(asset_path)
            plan_payload = _read_json_file(plan_path)
            if not asset_payload and not plan_payload:
                missing.append({"asset_id": asset_id, "intent_id": "*", "reason": "asset_not_found"})
                continue
            plan = plan_payload if plan_payload else asset_payload.get("plan") if isinstance(asset_payload.get("plan"), dict) else {}
            if not isinstance(plan, dict) or not plan:
                missing.append({"asset_id": asset_id, "intent_id": "*", "reason": "plan_not_found"})
                continue
            points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
            changed_intent_ids: set[str] = set()
            for point in points:
                point_id = _text(point.get("intent_id") or point.get("key"))
                if point_id not in intent_ids:
                    continue
                # Phase 4.2: Review approve 前检查 point 质量（assertion + candidate_step）
                if next_status == "approved":
                    check_approve_point_gate(point)
                point["review_status"] = next_status
                point["review_note"] = note if next_status == "rejected" else note
                point["reviewed_at"] = reviewed_at
                point["reviewed_by"] = reviewed_by
                metadata = point.get("metadata") if isinstance(point.get("metadata"), dict) else {}
                review_history = metadata.get("review_history") if isinstance(metadata.get("review_history"), list) else []
                review_history = [item for item in review_history if isinstance(item, dict)]
                review_history.append(
                    {
                        "reviewed_at": reviewed_at,
                        "reviewed_by": reviewed_by,
                        "status": next_status,
                        "note": note if next_status == "rejected" else note,
                    }
                )
                metadata["review_history"] = review_history
                point["metadata"] = metadata
                changed_intent_ids.add(point_id)
            metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
            for intent_id in sorted(intent_ids - changed_intent_ids):
                missing.append({"asset_id": asset_id, "intent_id": intent_id, "reason": "intent_not_found"})
            if not changed_intent_ids:
                continue
            review_summary = {
                **(plan.get("review_summary") if isinstance(plan.get("review_summary"), dict) else {}),
                **_review_summary_from_points(points),
            }
            plan["review_summary"] = review_summary
            plan["updated_at"] = reviewed_at
            if metadata:
                metadata["review_updated_at"] = reviewed_at
                plan["metadata"] = metadata
            if plan_path.exists() or plan_payload:
                _write_json_file(plan_path, plan)
            if asset_payload:
                asset_payload["plan"] = plan
                asset_payload["review_summary"] = review_summary
                asset_payload["updated_at"] = reviewed_at
                asset_payload["version"] = int(asset_payload.get("version", 0) or 0) + 1
                _write_json_file(asset_path, asset_payload)
            updated_count += len(changed_intent_ids)
            affected_assets.append(asset_id)
            # DB 同步:审核状态变更写入 test_point_assets
            try:
                if asset_payload:
                    test_point_asset_store.save_asset(db, project=normalized_project, bundle=asset_payload)
            except Exception:  # noqa: BLE001 - DB 同步降级,不阻断审核
                LOGGER.warning("test point asset DB sync failed for review %s/%s", normalized_project, asset_id, exc_info=True)
        store.append_history(
            {
                "timestamp": reviewed_at,
                "action": "batch_review_test_points",
                "project": normalized_project,
                "status": next_status,
                "updated_count": updated_count,
                "asset_ids": affected_assets,
            },
            db=db,
        )
        return {
            "message": f"updated {updated_count} test points",
            "updated_count": updated_count,
            "status": next_status,
            "affected_assets": affected_assets,
            "missing": missing,
        }

    def list_workbench_test_cases(
        self,
        *,
        project: str,
        page: str,
        source_asset: str,
        intent_type: str,
        priority: str,
        execution_status: str,
        active_status: str,
        keyword: str,
        page_index: int,
        page_size: int,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_workbench_test_cases 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_page = workbench_gate_service.normalize_page_slug(_text(page)) if _text(page) else ""
        normalized_source_asset = _text(source_asset)
        normalized_intent_type = _text(intent_type).lower()
        normalized_priority = _text(priority).upper()
        normalized_execution_status = _text(execution_status).lower()
        normalized_active_status = _text(active_status).lower() or "active"
        keyword_value = _text(keyword).lower()
        repo = TestCaseRepository(db)
        status_filter = "deprecated" if normalized_active_status == "deprecated" else None
        exclude_status_filter = "deprecated" if normalized_active_status == "active" else None
        cases = repo.list_filtered(
            project_code=normalized_project,
            page_code=normalized_page or None,
            priority=normalized_priority or None,
            last_execution_result=normalized_execution_status or None,
            status=status_filter,
            exclude_status=exclude_status_filter,
            order_by=TestCase.case_id.asc(),
        )
        asset_index = _source_asset_index(normalized_project)
        page_url_map = _page_object_url_map(
            db,
            project=normalized_project,
            page_codes=[_text(case.page_code) for case in cases],
        )
        latest_executions = _latest_execution_map(db, case_ids=[int(case.id) for case in cases])
        items: list[dict[str, Any]] = []
        for case in cases:
            source_asset_hit = _source_asset_for_case(case, asset_index)
            item = _workbench_test_case_list_item(
                case,
                source_asset=source_asset_hit,
                page_url_map=page_url_map,
                latest_execution=latest_executions.get(int(case.id)),
            )
            if normalized_source_asset and normalized_source_asset not in {
                _text(item.get("source_asset_id")),
                _text(item.get("source_asset_title")),
            }:
                continue
            if normalized_intent_type and _text(item.get("intent_type")).lower() != normalized_intent_type:
                continue
            haystack = " ".join(
                [
                    _text(item.get("case_id")),
                    _text(item.get("title")),
                    _text(item.get("source_asset_id")),
                    _text(item.get("source_asset_title")),
                    _text(item.get("page")),
                    _text(item.get("priority")),
                    _text(item.get("last_execution_result")),
                ]
            ).lower()
            if keyword_value and keyword_value not in haystack:
                continue
            items.append(item)
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "items": items[start:end],
            "summary": {
                "total": total_items,
                "active_count": sum(1 for item in items if item.get("active_status") == "active"),
                "deprecated_count": sum(1 for item in items if item.get("active_status") == "deprecated"),
                "passed_count": sum(1 for item in items if item.get("last_execution_result") == "passed"),
                "failed_count": sum(1 for item in items if item.get("last_execution_result") == "failed"),
                "not_run_count": sum(1 for item in items if item.get("last_execution_result") in {"", "unknown"}),
            },
            "filters": {
                "project": normalized_project,
                "page": normalized_page,
                "source_asset": normalized_source_asset,
                "intent_type": normalized_intent_type,
                "priority": normalized_priority,
                "execution_status": normalized_execution_status,
                "active_status": normalized_active_status,
                "keyword": keyword_value,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def list_test_case_generation_failures(
        self,
        *,
        project: str,
        asset_id: str,
        keyword: str,
        page_index: int,
        page_size: int,
    ) -> dict[str, Any]:
        """WorkbenchFacade.list_test_case_generation_failures 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_asset = _safe_case_id(asset_id)
        keyword_value = _text(keyword).lower()
        asset_index = _asset_title_index(normalized_project)
        latest_failures = list(_generation_failure_index(normalized_project, normalized_asset).values())
        items: list[dict[str, Any]] = []
        for failure in sorted(latest_failures, key=lambda item: _text(item.get("timestamp")), reverse=True):
            item_asset_id = _safe_case_id(_text(failure.get("asset_id")))
            asset_meta = asset_index.get(item_asset_id, {})
            item = {
                "project": normalized_project,
                "asset_id": item_asset_id,
                "asset_title": _text(asset_meta.get("asset_title")) or item_asset_id,
                "page": _text(failure.get("page")) or _text(asset_meta.get("page")),
                "intent_id": _text(failure.get("intent_id")),
                "title": _text(failure.get("title")) or _text(failure.get("intent_id")),
                "failure_type": _text(failure.get("failure_type")) or "编译失败",
                "stage": _text(failure.get("stage")) or "compile",
                "code": _text(failure.get("code")),
                "message": _text(failure.get("message")),
                "reason": _text(failure.get("reason")),
                "suggestion": _text(failure.get("suggestion")),
                "failed_at": _text(failure.get("timestamp")),
                "detail": failure.get("detail") if isinstance(failure.get("detail"), (dict, str)) else "",
                "asset_url": f"/assets/test-points/{item_asset_id}?project={normalized_project}",
            }
            haystack = " ".join(
                [
                    item["asset_id"],
                    item["asset_title"],
                    item["page"],
                    item["intent_id"],
                    item["title"],
                    item["failure_type"],
                    item["stage"],
                    item["code"],
                    item["message"],
                    item["reason"],
                ]
            ).lower()
            if keyword_value and keyword_value not in haystack:
                continue
            items.append(item)
        total_items = len(items)
        safe_page_size = max(1, min(int(page_size or 20), 200))
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size) if total_items else 1
        safe_page = max(1, min(int(page_index or 1), total_pages))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "items": items[start:end],
            "summary": {
                "total": total_items,
                "asset_count": len({_text(item.get("asset_id")) for item in items if _text(item.get("asset_id"))}),
                "intent_count": len({_text(item.get("intent_id")) for item in items if _text(item.get("intent_id"))}),
            },
            "filters": {
                "project": normalized_project,
                "asset_id": normalized_asset,
                "keyword": keyword_value,
            },
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
            },
        }

    def get_workbench_test_case(self, *, case_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_workbench_test_case 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_case_id = _text(case_id)
        repo = TestCaseRepository(db)
        case = repo.get_by_case_id_and_project(normalized_case_id, normalized_project)
        if case is None:
            case = repo.get_by_case_id(normalized_case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
        detail = test_case_service.get_test_case_detail(db, str(case.id))
        case = detail.case
        source_asset_hit = _source_asset_for_case(case, _source_asset_index(_text(case.project_code) or normalized_project))
        page_url_map = _page_object_url_map(db, project=_text(case.project_code) or normalized_project, page_codes=[_text(case.page_code)])
        repo = TestCaseRepository(db)
        executions = repo.list_executions_by_case_ids([int(case.id)])[:5]
        versions = repo.list_versions_by_case_id(int(case.id), limit=10)
        latest_execution = executions[0] if executions else None
        requirement_metadata = _structured_requirement_metadata_from_case(case)
        item = _workbench_test_case_list_item(
            case,
            source_asset=source_asset_hit,
            page_url_map=page_url_map,
            latest_execution=latest_execution,
        )
        item.update(
            {
                "precondition": _text(case.precondition_state) or requirement_metadata.get("precondition", ""),
                "steps": case.test_steps if isinstance(case.test_steps, list) else [],
                "steps_text": _text(case.test_steps_text),
                "expected_result": _text(case.expected_result),
                "involved_elements": [
                    _text(step.get("target"))
                    for step in (case.test_steps if isinstance(case.test_steps, list) else [])
                    if isinstance(step, dict) and _text(step.get("target")) and _text(step.get("target")) != "element:"
                ],
                "script_code": _text(case.script_code),
                "source_ref": _text(case.source_ref),
                "versions": [
                    {
                        "version_no": int(version.version_no or 0),
                        "changed_by": _text(version.changed_by),
                        "change_summary": _text(version.change_summary),
                        "created_at": version.created_at.isoformat() if hasattr(version.created_at, "isoformat") else "",
                    }
                    for version in versions
                ],
                "executions": [
                    {
                        "status": _text(execution.status),
                        "duration_ms": int(execution.duration_ms or 0),
                        "report_url": _text(execution.report_url),
                        "executed_at": execution.executed_at.isoformat() if hasattr(execution.executed_at, "isoformat") else "",
                    }
                    for execution in executions
                ],
            }
        )
        return {"item": item}

    def delete_workbench_test_cases(
        self,
        *,
        project: str,
        case_ids: list[str],
        delete_all: bool,
        confirm_text: str = "",
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.delete_workbench_test_cases 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_case_ids = [_text(item) for item in (case_ids or []) if _text(item)]
        if delete_all and _text(confirm_text) != f"清空{normalized_project}":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "delete_all_confirmation_required",
                    "message": f"请输入确认文本：清空{normalized_project}",
                },
            )
        if not delete_all and not normalized_case_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="case_ids must not be empty",
            )

        repo = TestCaseRepository(db)
        if delete_all:
            rows = repo.list_all_case_id_pairs_by_project(normalized_project)
        else:
            rows = repo.list_case_id_and_id_pairs_by_case_ids(normalized_project, normalized_case_ids)
        found_case_ids = {_text(row_case_id) for _row_id, row_case_id in rows if _text(row_case_id)}
        missing_case_ids = [case_id for case_id in normalized_case_ids if case_id not in found_case_ids]

        if not rows:
            if not delete_all and len(normalized_case_ids) == 1:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test case not found")
            return {
                "message": "no test cases deleted",
                "project": normalized_project,
                "deleted_count": 0,
                "deleted_case_ids": [],
                "missing_case_ids": missing_case_ids,
                "delete_all": bool(delete_all),
            }

        target_ids = [int(row_id) for row_id, _row_case_id in rows]
        deleted_case_ids = [_text(row_case_id) for _row_id, row_case_id in rows if _text(row_case_id)]
        deleted_count = int(test_case_service.batch_delete_test_cases(db, ids=target_ids) or 0)
        store.append_history(
            {
                "timestamp": _utc_now().isoformat(),
                "action": "delete_workbench_test_cases",
                "project": normalized_project,
                "delete_all": bool(delete_all),
                "deleted_count": deleted_count,
                "deleted_case_ids": deleted_case_ids,
                "missing_case_ids": missing_case_ids,
            },
            db=db,
        )
        return {
            "message": f"deleted {deleted_count} test cases",
            "project": normalized_project,
            "deleted_count": deleted_count,
            "deleted_case_ids": deleted_case_ids,
            "missing_case_ids": missing_case_ids,
            "delete_all": bool(delete_all),
        }

    def get_test_point_asset(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset 接口实现。"""
        store.ensure_dirs()
        payload = workbench_asset_service.build_test_point_asset_detail(
            project=project,
            asset_id=asset_id,
            load_test_point_asset=lambda project_value, case_id_value: (
                test_point_asset_store.load_asset(db, project=project_value, asset_id=case_id_value)
                or workbench_asset_service.load_test_point_asset_with_root(
                    project_value,
                    case_id_value,
                    state_root=constants.TEST_POINTS_ROOT,
                )
            ),
            latest_run_snapshot_for_case=lambda project, case_id, page="": workbench_asset_service.latest_run_snapshot_for_case(
                project=project,
                case_id=case_id,
                page=page,
                safe_case_id_fn=workbench_gate_service.safe_case_id,
                normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                runtime_jobs=store.list_run_jobs(),
                runtime_runs_file=constants.RUNTIME_RUNS_FILE,
                runtime_view_with_execution_record_preferred_fn=lambda item: item if isinstance(item, dict) else {},
                read_json_list_fn=store.read_json_list,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
            ),
            build_traceability_summary=lambda asset, latest_run: workbench_asset_service.build_test_point_asset_traceability_summary(
                asset=asset,
                latest_run=latest_run,
                build_test_point_asset_technique_summary_fn=workbench_asset_service.build_test_point_asset_technique_summary,
                build_review_audit_summary_fn=workbench_review_service.build_review_audit_summary,
                build_page_semantic_summary_fn=workbench_analysis_service.build_page_semantic_summary,
                build_risk_report_summary_fn=workbench_analysis_service.build_risk_report_summary,
                build_execution_gate_fn=workbench_gate_service.build_execution_gate,
                build_execution_gate_audit_snapshot_fn=workbench_gate_service.build_execution_gate_audit_snapshot,
                clamp_confidence=page_analysis_rules.clamp_confidence,
            ),
            build_selection_summary=lambda traceability_summary: workbench_asset_service.build_test_point_asset_selection_summary(
                traceability_summary=traceability_summary
            ),
            clamp_confidence=page_analysis_rules.clamp_confidence,
        )
        if not payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
        if item:
            item["generation_diagnostics"] = _build_generation_diagnostics_for_asset(project, item)
            _normalize_asset_involved_elements_on_read(item, project=project, db=db)
        return payload

    def get_test_point_asset_coverage_matrix(self, *, asset_id: str, project: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_test_point_asset_coverage_matrix 接口实现。"""
        payload = self.get_test_point_asset(asset_id=asset_id, project=project, db=db)
        item = payload.get("item", {}) if isinstance(payload.get("item"), dict) else {}
        return {"item": item.get("coverage_matrix", {}) if isinstance(item.get("coverage_matrix"), dict) else {}}

    def upsert_test_point_asset(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.upsert_test_point_asset 接口实现。"""
        store.ensure_dirs()
        project = _text(getattr(payload, "project", "")) or "mall"
        test_project_service.ensure_project_active_for_write(db, project)
        raw_asset_id = _text(getattr(payload, "asset_id", ""))
        if not raw_asset_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_id must not be empty")
        asset_id = _safe_case_id(raw_asset_id)
        page = workbench_gate_service.normalize_page_slug(_text(getattr(payload, "page", "")))
        if not page:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="page must not be empty")
        incoming_title = _text(getattr(payload, "title", ""))
        title = _asset_display_title(incoming_title, page=page, asset_id=asset_id, candidates=getattr(payload, "selected_candidates", []))
        priority = _text(getattr(payload, "priority", "")) or "P1"
        source_type = _text(getattr(payload, "source_type", "")) or "manual"
        requirement = _text(getattr(payload, "requirement", "")) or title
        asset_path, existing_plan_path = _test_point_asset_state_paths(project, asset_id)
        existing_asset_payload = _read_json_file(asset_path)
        existing_plan_payload = _read_json_file(existing_plan_path)
        embedded_plan = (
            existing_asset_payload.get("plan")
            if isinstance(existing_asset_payload.get("plan"), dict)
            else {}
        )
        existing_plan = existing_plan_payload if isinstance(existing_plan_payload, dict) and existing_plan_payload else embedded_plan
        existing_points = (
            [point for point in existing_plan.get("points", []) if isinstance(point, dict)]
            if isinstance(existing_plan.get("points"), list)
            else []
        )
        incoming_points_raw = getattr(payload, "points", [])
        incoming_points = [item for item in incoming_points_raw if isinstance(item, dict)] if isinstance(incoming_points_raw, list) else []
        selected_candidates_raw = getattr(payload, "selected_candidates", [])
        selected_candidates = [item for item in selected_candidates_raw if isinstance(item, dict)]
        if incoming_points:
            points = incoming_points
        elif selected_candidates:
            points = [_manual_point_from_candidate(candidate, index=index) for index, candidate in enumerate(selected_candidates, start=1)]
        elif existing_points:
            points = existing_points
        else:
            selected_candidates = [
                {
                    "intent_id": asset_id,
                    "title": title,
                    "summary": title,
                    "priority": priority,
                    "steps": [requirement],
                    "expected": "手工维护测试点",
                }
            ]
            points = [_manual_point_from_candidate(candidate, index=index) for index, candidate in enumerate(selected_candidates, start=1)]
        if len(selected_candidates) > 200:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="selected_candidates exceeds max size 200")
        page_context = _page_object_generation_context(db, project=project, page=page)
        points = _normalize_points_involved_elements(points, page_context=page_context)
        selected_intent_ids = [intent_id for intent_id in [_text(item.get("intent_id") or item.get("key")) for item in points] if intent_id]
        technique_distribution: dict[str, int] = {}
        for point in points:
            intent_type = _text(point.get("intent_type") or point.get("point_type")) or source_type or "manual"
            technique_distribution[intent_type] = int(technique_distribution.get(intent_type, 0) or 0) + 1
        existing_metadata = existing_plan.get("metadata") if isinstance(existing_plan.get("metadata"), dict) else {}
        selected_candidate_snapshots = (
            [_candidate_snapshot_from_candidate(candidate) for candidate in selected_candidates]
            if selected_candidates
            else existing_metadata.get("selected_candidates", [])
            if isinstance(existing_metadata.get("selected_candidates"), list)
            else []
        )
        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": asset_id,
            "page": page,
            "title": title,
            "priority": priority,
            "source_type": source_type,
            "requirement": [requirement],
            "generated_at": _text(existing_plan.get("generated_at")) or store.now_iso(),
            "points": points,
            "coverage": {
                "status": "preview",
                "coverage_ratio": 1.0 if points else 0.0,
                "generated_case_count": len(points),
                "expected_case_count": len(points),
                "missing_scenarios": [],
                "covered_scenarios": selected_intent_ids,
            },
            "review_summary": {
                "total_points": len(points),
                "mainline_point_count": len(points),
                "design_only_point_count": 0,
                "technique_distribution": technique_distribution,
            },
            "metadata": {
                **existing_metadata,
                "saved_by": "web-ui-service",
                "origin": source_type,
                "selected_intent_ids": selected_intent_ids,
                "selected_candidates": selected_candidate_snapshots,
                "asset_title": title,
                "normalized_requirement": requirement,
            },
            "involved_elements": _text_list(
                [
                    element
                    for point in points
                    for element in _text_list(point.get("involved_elements"))
                ]
            ),
            "confidence": 0.85,
            "requires_review": False,
        }

        def _normalize_test_point_plan_payload(plan_payload: dict[str, Any], _strict: bool = False) -> dict[str, Any]:
            """WorkbenchFacade._normalize_test_point_plan_payload 接口实现。"""
            normalized_plan, _warnings = normalize_test_point_plan_v1(plan_payload)
            return normalized_plan

        def _upsert_test_point_asset_snapshot(**kwargs: Any) -> dict[str, Any]:
            """WorkbenchFacade._upsert_test_point_asset_snapshot 接口实现。"""
            return workbench_asset_service.upsert_test_point_asset_snapshot(
                **kwargs,
                now_iso_fn=store.now_iso,
                count_test_point_types_fn=workbench_asset_service.count_test_point_types,
                build_test_point_asset_semantic_summary_fn=lambda resolved_page, normalized_plan: workbench_asset_service.build_test_point_asset_semantic_summary(
                    page=resolved_page,
                    normalized_plan=normalized_plan,
                    normalize_page_slug_fn=workbench_gate_service.normalize_page_slug,
                    clamp_confidence=page_analysis_rules.clamp_confidence,
                ),
                build_test_point_asset_technique_summary_fn=lambda normalized_plan: workbench_asset_service.build_test_point_asset_technique_summary(
                    normalized_plan=normalized_plan
                ),
                merge_reference_items_fn=workbench_asset_service.merge_reference_items,
            )

        plan_path = workbench_asset_service.save_test_point_plan(
            project=project,
            case_id=asset_id,
            page=page,
            page_url="",
            requirement=requirement,
            plan=plan,
            now_iso_fn=store.now_iso,
            normalize_test_point_plan_payload=_normalize_test_point_plan_payload,
            upsert_test_point_asset_snapshot=_upsert_test_point_asset_snapshot,
            state_root=constants.TEST_POINTS_ROOT,
        )
        # DB 事实源:把刚写入缓存的资产 bundle 同步为 DB 权威记录(写穿)。
        try:
            _bundle = workbench_asset_service.load_test_point_asset_with_root(
                project, asset_id, state_root=constants.TEST_POINTS_ROOT,
            )
            if isinstance(_bundle, dict) and _bundle:
                test_point_asset_store.save_asset(db, project=project, bundle=_bundle)
        except Exception:  # noqa: BLE001 - DB 写穿降级,不阻断保存
            LOGGER.warning("test point asset DB write-through failed for %s/%s", project, asset_id, exc_info=True)
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "upsert_test_point_asset",
                "project": project,
                "case_id": asset_id,
                "page": page,
                "path": str(plan_path.resolve()),
            },
            db=db,
        )
        detail = self.get_test_point_asset(asset_id=asset_id, project=project, db=db)
        item = detail.get("item", {}) if isinstance(detail.get("item"), dict) else {}
        return {
            "message": "test point asset saved",
            "count": 1 if item else 0,
            "item": item,
            "items": [item] if item else [],
        }

    def delete_test_point_asset(self, *, asset_id: str, project: str, db: Session, cascade_cases: bool = False) -> dict[str, Any]:
        """WorkbenchFacade.delete_test_point_asset 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        project_record = test_project_service.ensure_project_active_for_write(db, normalized_project)
        normalized_project = _text(getattr(project_record, "project_code", normalized_project)) or normalized_project
        raw_asset_id = _text(asset_id)
        normalized_asset_id = _safe_case_id(raw_asset_id)
        candidate_asset_ids: list[str] = []
        for candidate in (normalized_asset_id, raw_asset_id):
            normalized_candidate = _text(candidate)
            if normalized_candidate and normalized_candidate not in candidate_asset_ids:
                candidate_asset_ids.append(normalized_candidate)
        # 先删文件缓存,再删 DB 权威记录。
        removed_paths: list[str] = []
        removed_path_set: set[str] = set()

        def _remove_if_exists(path: Path) -> None:
            """WorkbenchFacade._remove_if_exists 接口实现。"""
            if not path.exists():
                return
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            resolved_path = str(path.resolve())
            if resolved_path in removed_path_set:
                return
            removed_path_set.add(resolved_path)
            removed_paths.append(resolved_path)

        def _remove_asset_files_in_project(project_dir: Path) -> None:
            """WorkbenchFacade._remove_asset_files_in_project 接口实现。"""
            for candidate_asset_id in candidate_asset_ids:
                _remove_if_exists(project_dir / f"{candidate_asset_id}.json")
                _remove_if_exists(project_dir / "plans" / f"{candidate_asset_id}.json")
                _remove_if_exists(project_dir / "versions" / candidate_asset_id)

        # 1) Hard delete in current project.
        project_dir = workbench_asset_service.state_project_dir(normalized_project, state_root=constants.TEST_POINTS_ROOT)
        _remove_asset_files_in_project(project_dir)

        # 2) Linked cases are not deleted by default. Case deletion is a separate
        # destructive action and must be explicitly requested by a governance flow.
        deleted_case_count = 0
        if cascade_cases and Path(constants.ASSETS_CASES_ROOT).exists():
            for candidate_asset_id in candidate_asset_ids:
                for yaml_path in Path(constants.ASSETS_CASES_ROOT).rglob(f"{candidate_asset_id}.yaml"):
                    _remove_if_exists(yaml_path)

            try:
                deleted_case_count = int(test_case_service.batch_delete_test_cases(db, case_ids=candidate_asset_ids) or 0)
            except HTTPException as exc:
                if int(exc.status_code or 0) not in {status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST}:
                    raise

        # DB 权威删除:文件已清理,现在删 DB 记录。
        for _candidate_asset_id in candidate_asset_ids:
            try:
                test_point_asset_store.delete_asset(db, project=normalized_project, asset_id=_candidate_asset_id)
            except Exception:  # noqa: BLE001 - DB 删除降级,不阻断返回
                LOGGER.warning("test point asset DB delete failed for %s/%s", normalized_project, _candidate_asset_id, exc_info=True)
        if not removed_paths and deleted_case_count <= 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "delete_test_point_asset",
                "project": normalized_project,
                "case_id": normalized_asset_id,
                "removed_paths": removed_paths,
                "cascade_cases": bool(cascade_cases),
                "deleted_case_count": deleted_case_count,
            },
            db=db,
        )
        return {
            "item": {
                "asset_id": normalized_asset_id,
                "project": normalized_project,
                "deleted": True,
                "deleted_count": len(removed_paths),
                "deleted_paths": removed_paths,
                "deleted_case_count": deleted_case_count,
                "cascade_cases": bool(cascade_cases),
                "asset_id_aliases": candidate_asset_ids,
            }
        }

    def batch_delete_test_point_assets(self, *, project: str, asset_ids: list[str], db: Session) -> dict[str, Any]:
        """WorkbenchFacade.batch_delete_test_point_assets 接口实现。"""
        normalized_project = _text(project) or "mall"
        deleted: list[str] = []
        missing: list[str] = []
        for raw_asset_id in asset_ids:
            candidate_asset_id = _text(raw_asset_id)
            if not candidate_asset_id:
                continue
            try:
                self.delete_test_point_asset(asset_id=candidate_asset_id, project=normalized_project, db=db)
                deleted.append(_safe_case_id(candidate_asset_id))
            except HTTPException as exc:
                if int(exc.status_code or 0) == status.HTTP_404_NOT_FOUND:
                    missing.append(_safe_case_id(candidate_asset_id))
                    continue
                raise
        return {
            "deleted_count": len(deleted),
            "deleted_asset_ids": deleted,
            "missing_count": len(missing),
            "missing_asset_ids": missing,
        }

    def generate_cases_from_test_point_assets(
        self,
        *,
        project: str,
        asset_ids: list[str],
        intent_ids: list[str] | None = None,
        source: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.generate_cases_from_test_point_assets 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(project) or "mall"
        case_source = _normalize_generation_case_source(source)
        selected_asset_ids = [_safe_case_id(item) for item in asset_ids if _text(item)]
        selected_intent_filter = {_text(item) for item in (intent_ids or []) if _text(item)}
        if not selected_asset_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_ids must not be empty")
        usecase = build_generate_case_usecase(db)
        generated_items: list[dict[str, Any]] = []
        skipped_assets: list[dict[str, str]] = []
        processed_assets = 0

        for asset_id in selected_asset_ids:
            asset = workbench_asset_service.load_test_point_asset_with_root(
                normalized_project,
                asset_id,
                state_root=constants.TEST_POINTS_ROOT,
            )
            if not asset:
                skipped_assets.append({"asset_id": asset_id, "reason": "asset_not_found"})
                continue
            page = workbench_gate_service.normalize_page_slug(_text(asset.get("page")))
            if not page:
                skipped_assets.append({"asset_id": asset_id, "reason": "asset_page_empty"})
                continue
            page_context = _page_object_generation_context(db, project=normalized_project, page=page)
            if not bool(page_context.get("page_object_found")):
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_not_governed",
                        "message": "; ".join(str(item) for item in page_context.get("base_blockers", []) if str(item).strip()),
                    }
                )
                continue
            page_url = _text(page_context.get("page_url"))
            if not page_url:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_url_missing",
                        "message": "请到页面对象管理补齐页面 URL",
                    }
                )
                continue
            if int(page_context.get("qualified_element_count", 0) or 0) <= 0:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "page_object_no_qualified_elements",
                        "message": "页面对象缺少可生成元素：需满足 status=active + review_status=approved + stability_level 为 high/medium",
                    }
                )
                continue
            requirement_list = asset.get("requirement") if isinstance(asset.get("requirement"), list) else []
            requirement = _text(" ".join(_text(item) for item in requirement_list if _text(item))) or _text(asset.get("title")) or asset_id
            title = _text(asset.get("title")) or asset_id
            priority = _text(asset.get("priority")) or "P1"
            plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
            points = plan.get("points") if isinstance(plan.get("points"), list) else []
            check_generate_gate(asset)
            approved_points = []
            for point in points:
                if not isinstance(point, dict) or _review_status_from_point(point) != "approved":
                    continue
                point_intent_id = _text(point.get("intent_id") or point.get("key"))
                if selected_intent_filter and point_intent_id not in selected_intent_filter:
                    continue
                approved_points.append(point)
            if not approved_points:
                message = "没有已通过测试点可生成"
                reason = "no_approved_test_points"
                if selected_intent_filter:
                    message = "所选测试点未通过审核或不存在，无法生成"
                    reason = "selected_intents_not_approved_or_missing"
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": reason,
                        "message": message,
                    }
                )
                continue
            candidates = [
                _candidate_from_asset_point(point, fallback_title=title, fallback_priority=priority)
                for point in approved_points
                if isinstance(point, dict)
            ]
            for candidate in candidates:
                candidate["source_asset_id"] = asset_id
                candidate["source_asset_title"] = title
            if not candidates:
                skipped_assets.append(
                    {
                        "asset_id": asset_id,
                        "reason": "no_approved_test_points",
                        "message": "没有已通过测试点可生成",
                    }
                )
                continue
            # Generate one approved intent at a time. The compiler enforces strict
            # selected_intent_ids coverage, so a single bad test point must not
            # hide already generated cases or fail the whole asset batch.
            chunks = [[candidate] for candidate in candidates]
            if not chunks:
                chunks = [candidates]
            processed_assets += 1
            for chunk in chunks:
                selected_intent_ids = [
                    intent_id
                    for intent_id in [_text(item.get("intent_id")) for item in chunk]
                    if intent_id
                ]
                generation_payload = GenerationGenerateCasePayload(
                    project=normalized_project,
                    page=page,
                    requirement=requirement,
                    title=title,
                    case_id=_existing_case_id_for_source_intent(
                        db,
                        project=normalized_project,
                        page=page,
                        source_asset_id=asset_id,
                        intent_id=selected_intent_ids[0] if selected_intent_ids else "",
                    ),
                    priority=priority,
                    page_url=page_url,
                    source=case_source,
                    selected_candidates=chunk,
                    selected_intent_ids=selected_intent_ids,
                )
                try:
                    response = usecase.execute(generation_payload)
                except HTTPException as exc:
                    failure_summary = _record_generation_failure(
                        project=normalized_project,
                        asset_id=asset_id,
                        page=page,
                        intent_id=selected_intent_ids[0] if selected_intent_ids else "",
                        title=_text(chunk[0].get("title") or chunk[0].get("summary")) if chunk else "",
                        detail=exc.detail,
                    )
                    skipped_assets.append(
                        {
                            "asset_id": asset_id,
                            "intent_id": selected_intent_ids[0] if selected_intent_ids else "",
                            "reason": f"generate_failed:{_text(exc.detail) or exc.status_code}",
                            "message": failure_summary.get("message", ""),
                            "failure_type": failure_summary.get("failure_type", ""),
                            "suggestion": failure_summary.get("suggestion", ""),
                        }
                    )
                    _safe_rollback_or_invalidate(db)
                    continue
                response_items = response.get("items") if isinstance(response.get("items"), list) else []
                if response_items:
                    generated_items.extend([item for item in response_items if isinstance(item, dict)])
                    continue
                response_item = response.get("item")
                if isinstance(response_item, dict) and response_item:
                    generated_items.append(response_item)

        if not generated_items:
            primary = skipped_assets[0] if skipped_assets else {}
            detail_message = _text(primary.get("message")) or _text(primary.get("reason")) or "没有可生成的测试点"
            _safe_rollback_or_invalidate(db)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": _text(primary.get("reason")) or "no_generated_cases",
                    "message": detail_message,
                    "skipped": skipped_assets,
                },
            )
        return {
            "message": f"generated {len(generated_items)} cases",
            "count": len(generated_items),
            "items": generated_items,
            "summary": {
                "total_assets": len(selected_asset_ids),
                "processed_assets": processed_assets,
                "skipped_assets": len(skipped_assets),
                "skipped": skipped_assets,
            },
        }

    def preview_test_point_script(
        self,
        *,
        project: str,
        asset_id: str,
        intent_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """WorkbenchFacade.preview_test_point_script 接口实现。"""
        normalized_project = _text(project) or "mall"
        normalized_asset_id = _safe_case_id(asset_id)
        normalized_intent_id = _text(intent_id)
        if not normalized_asset_id or not normalized_intent_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="asset_id and intent_id are required")

        asset = workbench_asset_service.load_test_point_asset_with_root(
            normalized_project,
            normalized_asset_id,
            state_root=constants.TEST_POINTS_ROOT,
        )
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point asset not found")
        page = workbench_gate_service.normalize_page_slug(_text(asset.get("page")))
        plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
        points = [point for point in plan.get("points", []) if isinstance(point, dict)] if isinstance(plan.get("points"), list) else []
        point = next(
            (
                row
                for row in points
                if _text(row.get("intent_id") or row.get("key")) == normalized_intent_id
            ),
            None,
        )
        if point is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="test point intent not found")

        page_context = _page_object_generation_context(db, project=normalized_project, page=page)
        generation_state = _test_point_generation_state(point, page_context=page_context)
        if generation_state["can_generate"] is not True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "test_point_not_generatable",
                    "message": "当前测试点不可生成脚本",
                    "blockers": generation_state["generation_blockers"],
                },
            )
        candidate = _candidate_from_asset_point(
            point,
            fallback_title=_text(asset.get("title")) or normalized_asset_id,
            fallback_priority=_text(asset.get("priority")) or "P1",
        )
        script_code = _build_test_point_script_preview(asset=asset, candidate=candidate, page_context=page_context)
        return {
            "item": {
                "project": normalized_project,
                "asset_id": _text(asset.get("asset_id")) or normalized_asset_id,
                "asset_title": _text(asset.get("title")) or normalized_asset_id,
                "intent_id": normalized_intent_id,
                "title": _text(candidate.get("title") or candidate.get("summary")),
                "page": page,
                "page_url": _text(page_context.get("page_url")),
                "can_generate": True,
                "script_code": script_code,
            }
        }

    def run_case(self, *, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.run_case 接口实现。"""
        store.ensure_dirs()
        normalized_project = _text(getattr(payload, "project", "")) or "mall"
        normalized_case_id = _safe_case_id(getattr(payload, "case_id", ""))
        if not workbench_case_consistency_service.is_case_tracked(
            normalized_case_id,
            case_center_case_ids=workbench_case_consistency_service.load_case_center_case_ids(db),
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")

        case_for_run = TestCaseRepository(db).get_by_case_id_and_project(normalized_case_id, normalized_project)
        if case_for_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in project case center")
        case_for_run = test_case_service.get_test_case_detail(db, str(case_for_run.id)).case
        runtime_case_script = _text(case_for_run.script_code)

        def _safe_source_case_path() -> Path:
            """返回展示/历史记录用路径，但不把源 YAML 变成执行前置条件。

            `script_code` 是执行唯一事实源。只要它存在，这个路径只作为
            `start_run()` 的元数据传入，随后会被运行态 YAML 替换，因此源
            YAML 缺失不能阻断执行。这里仍尽量把路径收敛到
            `assets/test-cases` 下，避免运行记录落入任意用户传入路径。
            """
            source_ref = _text(getattr(case_for_run, "source_ref", ""))
            if source_ref:
                source_ref_path = Path(source_ref).expanduser()
                if not source_ref_path.is_absolute():
                    source_ref_path = constants.REPO_ROOT / source_ref_path
                source_ref_path = source_ref_path.resolve()
                if _is_within(source_ref_path, constants.ASSETS_CASES_ROOT):
                    return source_ref_path
            return (constants.AI_CASES_ROOT / f"{normalized_case_id}.yaml").resolve()

        source_case_path = _safe_source_case_path()
        if not runtime_case_script.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "empty_case_script",
                    "message": "用例脚本为空，无法执行",
                    "case_id": normalized_case_id,
                },
            )

        def _build_runtime_execution_record(**kwargs: Any) -> dict[str, Any]:
            """WorkbenchFacade._build_runtime_execution_record 接口实现。"""
            return workbench_runtime_service.build_runtime_execution_record(
                **kwargs,
                normalize_execution_record_payload=_normalize_execution_record_payload,
            )

        def _runtime_view_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
            """WorkbenchFacade._runtime_view_from_entry 接口实现。

            委托给模块级 _build_runtime_view_from_entry。
            """
            return _build_runtime_view_from_entry(entry)

        def _load_runtime_execution_record_from_artifacts(artifacts_dir: Path) -> dict[str, Any]:
            """WorkbenchFacade._load_runtime_execution_record_from_artifacts 接口实现。"""
            return workbench_runtime_service.load_runtime_execution_record_from_artifacts(
                artifacts_dir,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries_fn=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload_fn=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
            )

        def _collect_failure_entries_with_meta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_with_meta 接口实现。"""
            return workbench_reporting_service.collect_failure_entries_with_meta(
                compat_scan_enabled=False,
                artifact_roots=[constants.RUNNER_ROOT / "artifacts", *sorted(constants.WEB_UI_RUNS_DIR.glob("*-artifacts"))],
                logger=None,
                normalize_evidence_manifest_payload=lambda payload: payload if isinstance(payload, dict) else {},
                resolve_manifest_entries=lambda entries, root: workbench_runtime_service.resolve_manifest_entries(entries, root=root),
                load_execution_record_payload=lambda path: workbench_runtime_service.load_execution_record_payload(
                    path,
                    normalize_execution_record_payload=_normalize_execution_record_payload,
                ),
                parse_analysis_file=workbench_reporting_service.parse_analysis_file,
            )

        def _collect_failure_entries() -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries 接口实现。"""
            entries, _meta = _collect_failure_entries_with_meta()
            return entries

        def _build_run_command(case_path_value: Path) -> tuple[list[str], dict[str, str]]:
            """WorkbenchFacade._build_run_command 接口实现。"""
            runner_environ = os.environ.copy()
            runner_environ["DSL_DATA_POOL_JSON"] = test_data_pool_service.serialize_runner_data_pool_snapshot(db)
            return workbench_runtime_service.build_run_command(
                case_path_value,
                get_python_bin_fn=lambda: workbench_runtime_service.get_python_bin(repo_root=constants.REPO_ROOT),
                repo_root=constants.REPO_ROOT,
                allure_results_root=constants.ALLURE_RESULTS_ROOT,
                environ=runner_environ,
            )

        def _execute_run(job: dict[str, Any]) -> None:
            """WorkbenchFacade._execute_run 接口实现。"""
            try:
                workbench_runtime_service.execute_run(
                    job,
                    build_run_command_fn=_build_run_command,
                    now_iso_fn=store.now_iso,
                    update_job=store.update_run_job,
                    update_runtime_run=store.update_runtime_run,
                    load_runtime_execution_record_from_artifacts=_load_runtime_execution_record_from_artifacts,
                    collect_failure_entries=_collect_failure_entries,
                    is_within=_is_within,
                    repo_root=constants.REPO_ROOT,
                    runner_root=constants.RUNNER_ROOT,
                )
            finally:
                final_job = store.get_run_job(_text(job.get("run_id"))) or job
                _persist_runtime_run_to_case_center(db, final_job)

        job = workbench_runtime_service.start_run(
            project=normalized_project,
            case_id=normalized_case_id,
            case_path=source_case_path,
            source=getattr(payload, "source", "manual"),
            runs_dir=constants.WEB_UI_RUNS_DIR,
            now_iso_fn=store.now_iso,
            build_runtime_execution_record=_build_runtime_execution_record,
            runtime_view_from_entry_fn=_runtime_view_from_entry,
            store_run_job=store.store_run_job,
            append_runtime_run=store.append_runtime_run,
            append_history=store.append_history,
            execute_run_fn=_execute_run,
            runtime_case_script=runtime_case_script,
        )
        return {"item": job}

    def list_runs(self, *, limit: int, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.list_runs 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = [
            _attach_test_point_asset_summary(
                _runtime_view_from_entry(item)
            )
            for item in store.read_runtime_run_items()
        ]
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items[:limit]}

    def get_run(self, *, run_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.get_run 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        job = store.get_run_job(run_id)
        if job:
            item = _attach_test_point_asset_summary(_runtime_view_from_entry(job))
            if workbench_case_consistency_service.is_case_tracked(item.get("case_id", ""), case_center_case_ids=case_center_case_ids):
                return {"item": item}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

        for item in store.read_runtime_run_items():
            if workbench_runtime_service.runtime_run_id(item) != run_id:
                continue
            response_item = _attach_test_point_asset_summary(_runtime_view_from_entry(item))
            if workbench_case_consistency_service.is_case_tracked(
                response_item.get("case_id", ""),
                case_center_case_ids=case_center_case_ids,
            ):
                return {"item": response_item}
            break
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    def rerun_case(self, *, run_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.rerun_case 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        run_item = self._service._find_run_item(run_id) if hasattr(self._service, "_find_run_item") else None
        if not run_item:
            run_item = workbench_runtime_service.find_run_item(
                run_id,
                get_job=store.get_run_job,
                read_runtime_runs=store.read_runtime_run_items,
                runtime_run_id_fn=workbench_runtime_service.runtime_run_id,
                runtime_view_with_execution_record_preferred_fn=_runtime_view_with_execution_record_preferred,
            )
        if not run_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        if not workbench_case_consistency_service.is_case_tracked(
            run_item.get("case_id", ""),
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        project = _text(run_item.get("project")) or "mall"
        case_id = _safe_case_id(run_item.get("case_id", ""))
        if not case_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run case_id not found")
        response = self.run_case(
            payload=SimpleNamespace(project=project, case_id=case_id, source="rerun", case_path=""),
            db=db,
        )
        new_job = response.get("item", {}) if isinstance(response.get("item"), dict) else {}
        store.append_history(
            {
                "timestamp": store.now_iso(),
                "action": "rerun_case",
                "case_id": case_id,
                "from_run_id": run_id,
                "run_id": new_job.get("run_id", ""),
                "queue_status": "queued",
            },
            db=db,
        )
        return {"item": new_job}

    def list_defects(self, *, case_id: str, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.list_defects 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        items = workbench_reporting_service.list_defect_items(
            case_id,
            read_items=lambda: store.list_defect_items(case_id),
        )
        filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
            items,
            case_center_case_ids=case_center_case_ids,
        )
        return {"items": filtered_items}

    def add_defect(self, payload: Any, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.add_defect 接口实现。"""
        store.ensure_dirs()
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)
        if not workbench_case_consistency_service.is_case_tracked(
            payload.case_id,
            case_center_case_ids=case_center_case_ids,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_id not found in case center")
        with store.FILE_LOCK:
            entry = workbench_reporting_service.add_defect_item(
                case_id=payload.case_id,
                defect_id=payload.defect_id,
                defect_url=payload.defect_url,
                system=payload.system,
                note=payload.note,
                read_items=lambda: store.read_json_list(store.DEFECT_LINKS_FILE),
                write_items=lambda items: store.write_json_list(store.DEFECT_LINKS_FILE, items),
            )
        return {"item": entry}

    def report_overview(self, response: Response, db: Session) -> dict[str, Any]:
        """WorkbenchFacade.report_overview 接口实现。"""
        store.ensure_dirs()
        workbench_reporting_service.apply_no_store_headers(response)
        case_center_case_ids = workbench_case_consistency_service.load_case_center_case_ids(db)

        def _collect_execution_records_with_meta_filtered(*, limit: int = 1000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            """WorkbenchFacade._collect_execution_records_with_meta_filtered 接口实现。"""
            rows, meta = _collect_execution_records_with_meta(limit=limit)
            filtered_rows, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                rows,
                case_center_case_ids=case_center_case_ids,
                case_id_resolver=lambda row: (
                    row.get("case_id")
                    or (
                        row.get("execution_record", {}).get("case_id")
                        if isinstance(row.get("execution_record"), dict)
                        else ""
                    )
                ),
            )
            return filtered_rows, meta

        def _collect_failure_entries_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._collect_failure_entries_filtered 接口实现。"""
            entries, _meta = _collect_failure_entries_with_meta()
            filtered_entries, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                entries,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_entries

        def _read_defect_items_filtered() -> list[dict[str, Any]]:
            """WorkbenchFacade._read_defect_items_filtered 接口实现。"""
            items = store.list_defect_items()
            filtered_items, _filter_meta = workbench_case_consistency_service.filter_records_by_case_center(
                items,
                case_center_case_ids=case_center_case_ids,
            )
            return filtered_items

        return workbench_reporting_service.build_report_overview(
            collect_execution_records_with_meta=_collect_execution_records_with_meta_filtered,
            normalize_execution_meta=workbench_reporting_service.normalize_execution_meta,
            collect_failure_entries=_collect_failure_entries_filtered,
            normalize_failure_analysis_view=workbench_reporting_service.normalize_failure_analysis_view,
            read_defect_items=_read_defect_items_filtered,
        )

