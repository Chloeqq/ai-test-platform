from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, status
from shared_backend.case_ids import build_case_id, match_case_id, next_case_sequence, normalize_case_id
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import yaml

from app.core.database import get_db
from app.models.test_case import TestCase
from app.services import test_case_service, workbench_generation_service
from . import legacy_workbench


router = APIRouter(tags=["workbench-generation"])


def _collect_existing_case_ids(db: Session) -> list[str]:
    items: list[str] = []
    try:
        db_case_ids = db.execute(select(TestCase.case_id)).scalars().all()
    except SQLAlchemyError:
        db_case_ids = []
    for raw_case_id in db_case_ids:
        normalized_case_id = normalize_case_id(str(raw_case_id or "").strip(), fallback="").strip()
        if normalized_case_id and match_case_id(normalized_case_id):
            items.append(normalized_case_id)
    assets_root = Path(legacy_workbench.ASSETS_CASES_ROOT)
    if assets_root.exists():
        for path in assets_root.rglob("*.yaml"):
            normalized_case_id = normalize_case_id(path.stem, fallback="").strip()
            if normalized_case_id and match_case_id(normalized_case_id):
                items.append(normalized_case_id)
    deduped: list[str] = []
    for value in items:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _next_case_id_for_conflict(current_case_id: str, existing_case_ids: list[str]) -> str:
    normalized_current_case_id = normalize_case_id(str(current_case_id or "").strip(), fallback="").strip()
    matched = match_case_id(normalized_current_case_id)
    if not matched:
        return normalized_current_case_id
    sequence = next_case_sequence(
        existing_case_ids=existing_case_ids,
        page=matched.group("page"),
        module=matched.group("module"),
        project=matched.group("project"),
        client=matched.group("client"),
        page_code=matched.group("page"),
        module_code=matched.group("module"),
        case_type=matched.group("case_type"),
        source=matched.group("source"),
    )
    return build_case_id(
        page=matched.group("page"),
        module=matched.group("module"),
        sequence=sequence,
        project=matched.group("project"),
        client=matched.group("client"),
        page_code=matched.group("page"),
        module_code=matched.group("module"),
        case_type=matched.group("case_type"),
        source=matched.group("source"),
    )


def _normalize_generate_candidates(raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            continue
        title = str(raw_candidate.get("title", "")).strip()
        summary = str(raw_candidate.get("summary", "")).strip()
        intent_type = str(raw_candidate.get("intent_type", "")).strip().lower()
        priority = str(raw_candidate.get("priority", "")).strip().upper()
        raw_tags = raw_candidate.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, list):
            for item in raw_tags:
                tag = str(item or "").strip()
                if tag and tag not in tags:
                    tags.append(tag)
        requirement_hint = summary or title
        if not requirement_hint and not intent_type:
            continue
        normalized.append(
            {
                "title": title,
                "summary": summary,
                "intent_type": intent_type,
                "priority": priority,
                "tags": tags,
                "requirement_hint": requirement_hint,
            }
        )
    return normalized


def _build_candidate_requirement(base_requirement: str, candidate: dict[str, Any]) -> str:
    requirement = str(base_requirement or "").strip()
    hint = str(candidate.get("requirement_hint", "")).strip()
    intent_type = str(candidate.get("intent_type", "")).strip()
    if not hint and not intent_type:
        return requirement
    lines = [requirement] if requirement else []
    if hint:
        lines.append(f"测试意图：{hint}")
    if intent_type:
        lines.append(f"测试类型：{intent_type}")
    return "\n".join(line for line in lines if line).strip()


def _sync_generated_case_item(
    *,
    result: dict[str, Any],
    payload: legacy_workbench.GenerateCasePayload,
    db: Session,
) -> dict[str, Any]:
    item_raw = result.get("item")
    item: dict[str, Any] = item_raw if isinstance(item_raw, dict) else {}
    if not isinstance(item_raw, dict):
        result["item"] = item
    yaml_content = str(item.get("yaml_content", "")).strip()
    if not yaml_content:
        return item
    case_yaml = yaml.safe_load(yaml_content) or {}
    if not isinstance(case_yaml, dict):
        return item
    source_path = str(item.get("path", "")).strip()
    try:
        synchronized = test_case_service.upsert_test_case_from_workbench(
            db,
            project_code=payload.project,
            case_yaml=case_yaml,
            source_path=source_path,
        )
    except legacy_workbench.HTTPException as exc:
        detail_text = str(getattr(exc, "detail", "")).lower()
        if int(getattr(exc, "status_code", 0) or 0) != 409 or "case_id already exists" not in detail_text:
            raise
        current_case_id = normalize_case_id(str(case_yaml.get("id", "")).strip(), fallback="").strip()
        retry_case_id = _next_case_id_for_conflict(
            current_case_id,
            _collect_existing_case_ids(db),
        )
        if not retry_case_id or retry_case_id == current_case_id:
            raise
        old_path = Path(source_path).resolve() if source_path else None
        retry_path = Path(legacy_workbench.AI_CASES_ROOT) / f"{retry_case_id}.yaml"
        case_yaml["id"] = retry_case_id
        final_text = legacy_workbench._write_case_yaml(retry_path, case_yaml)
        state_entry = legacy_workbench._save_case_state(payload.project, case_yaml, retry_path)
        item["case_id"] = retry_case_id
        item["path"] = str(retry_path.resolve())
        item["yaml_content"] = final_text
        item["state"] = state_entry
        legacy_workbench._append_history(
            {
                "timestamp": legacy_workbench._now_iso(),
                "action": "generate_case_retry_on_conflict",
                "case_id": retry_case_id,
                "replaced_case_id": current_case_id,
                "path": str(retry_path.resolve()),
                "previous_path": str(old_path) if old_path else "",
            }
        )
        synchronized = test_case_service.upsert_test_case_from_workbench(
            db,
            project_code=payload.project,
            case_yaml=case_yaml,
            source_path=str(retry_path.resolve()),
        )
    item["synced_case"] = {
        "id": synchronized.id,
        "case_id": synchronized.case_id,
        "project_code": synchronized.project_code,
    }
    return item


@router.post("/api/workbench/generate", status_code=status.HTTP_201_CREATED)
def generate_case(payload: legacy_workbench.GenerateCasePayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    normalized_page = legacy_workbench._normalize_page_slug(payload.page) if payload.page.strip() else ""
    requirement_text = payload.requirement.strip()
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        prd_text=payload.prd_text,
        prd_url=payload.prd_url,
        user_story=payload.user_story,
        git_diff=payload.git_diff,
        git_diff_path=payload.git_diff_path,
        openapi_url=payload.openapi_url,
        defect_ticket=payload.defect_ticket,
        runtime_logs=payload.runtime_logs,
    )
    effective_requirement = workbench_generation_service.resolve_effective_requirement(
        requirement_text=requirement_text,
        normalized_page=normalized_page,
        multisource_enabled=has_multisource_inputs,
        build_system_requirement=legacy_workbench._build_system_requirement,
    )
    if not effective_requirement and not has_multisource_inputs and not normalized_page:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="requirement must not be empty when no page or additional input sources are provided",
        )
    existing_case_ids = _collect_existing_case_ids(db)
    batch_candidates = _normalize_generate_candidates(payload.selected_candidates)
    if len(batch_candidates) > 20:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="selected_candidates exceeds max size 20",
        )
    if not batch_candidates:
        result = workbench_generation_service.build_generated_case_payload(
            payload=payload,
            normalized_page=normalized_page,
            effective_requirement=effective_requirement,
            multisource_enabled=has_multisource_inputs,
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            run_orchestrator_generate=legacy_workbench._run_orchestrator_generate,
            extract_quality_gate=legacy_workbench._extract_quality_gate,
            safe_case_id=legacy_workbench._safe_case_id,
            infer_targets=legacy_workbench._infer_targets,
            write_case_yaml=legacy_workbench._write_case_yaml,
            save_case_state=legacy_workbench._save_case_state,
            append_history=legacy_workbench._append_history,
            now_iso=legacy_workbench._now_iso,
            is_quality_gate_blocked=legacy_workbench._is_quality_gate_blocked,
            ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            utc=legacy_workbench.UTC,
            datetime_module=legacy_workbench.datetime,
            http_exception_cls=legacy_workbench.HTTPException,
            bad_gateway_status=legacy_workbench.status.HTTP_502_BAD_GATEWAY,
            unprocessable_entity_status=422,
            existing_case_ids=existing_case_ids,
        )
        item = _sync_generated_case_item(result=result, payload=payload, db=db)
        result["item"] = item
        result["items"] = [item]
        result["count"] = 1
        return result

    items: list[dict[str, Any]] = []
    for candidate in batch_candidates:
        candidate_tags = candidate.get("tags")
        candidate_update = {
            "title": str(candidate.get("title", "")).strip() or payload.title,
            "priority": str(candidate.get("priority", "")).strip() or payload.priority,
            "tags": candidate_tags if isinstance(candidate_tags, list) and candidate_tags else payload.tags,
            "selected_candidates": [],
        }
        if hasattr(payload, "model_copy"):
            candidate_payload = payload.model_copy(  # type: ignore[attr-defined]
                deep=True,
                update=candidate_update,
            )
        else:
            candidate_payload = payload.copy(  # type: ignore[attr-defined]
                deep=True,
                update=candidate_update,
            )
        result = workbench_generation_service.build_generated_case_payload(
            payload=candidate_payload,
            normalized_page=normalized_page,
            effective_requirement=_build_candidate_requirement(effective_requirement, candidate),
            multisource_enabled=has_multisource_inputs,
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            run_orchestrator_generate=legacy_workbench._run_orchestrator_generate,
            extract_quality_gate=legacy_workbench._extract_quality_gate,
            safe_case_id=legacy_workbench._safe_case_id,
            infer_targets=legacy_workbench._infer_targets,
            write_case_yaml=legacy_workbench._write_case_yaml,
            save_case_state=legacy_workbench._save_case_state,
            append_history=legacy_workbench._append_history,
            now_iso=legacy_workbench._now_iso,
            is_quality_gate_blocked=legacy_workbench._is_quality_gate_blocked,
            ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            utc=legacy_workbench.UTC,
            datetime_module=legacy_workbench.datetime,
            http_exception_cls=legacy_workbench.HTTPException,
            bad_gateway_status=legacy_workbench.status.HTTP_502_BAD_GATEWAY,
            unprocessable_entity_status=422,
            existing_case_ids=existing_case_ids,
        )
        item = _sync_generated_case_item(result=result, payload=candidate_payload, db=db)
        case_id = normalize_case_id(str(item.get("case_id", "")).strip(), fallback="").strip()
        if case_id and case_id not in existing_case_ids:
            existing_case_ids.append(case_id)
        items.append(item)

    return {
        "message": f"generated {len(items)} cases",
        "item": items[0] if items else {},
        "items": items,
        "count": len(items),
    }


@router.post("/api/workbench/preview-test-points")
def preview_test_points(payload: legacy_workbench.GenerateCasePayload) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    requirement_text = payload.requirement.strip()
    normalized_page = legacy_workbench._normalize_page_slug(payload.page) if payload.page.strip() else ""
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        prd_text=payload.prd_text,
        prd_url=payload.prd_url,
        user_story=payload.user_story,
        git_diff=payload.git_diff,
        git_diff_path=payload.git_diff_path,
        openapi_url=payload.openapi_url,
        defect_ticket=payload.defect_ticket,
        runtime_logs=payload.runtime_logs,
    )
    effective_requirement = workbench_generation_service.resolve_effective_requirement(
        requirement_text=requirement_text,
        normalized_page=normalized_page,
        multisource_enabled=has_multisource_inputs,
        build_system_requirement=legacy_workbench._build_system_requirement,
    )
    if not effective_requirement and not has_multisource_inputs and not normalized_page:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="requirement must not be empty when no page or additional input sources are provided",
        )
    return workbench_generation_service.build_preview_test_points_payload(
        effective_requirement=effective_requirement,
        normalized_page=normalized_page,
        source=payload.source,
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        prd_text=payload.prd_text,
        prd_url=payload.prd_url,
        user_story=payload.user_story,
        git_diff=payload.git_diff,
        git_diff_path=payload.git_diff_path,
        openapi_url=payload.openapi_url,
        defect_ticket=payload.defect_ticket,
        runtime_logs=payload.runtime_logs,
        run_orchestrator_parse=legacy_workbench._run_orchestrator_parse,
        render_requirement_spec_markdown=legacy_workbench._render_requirement_spec_markdown,
        extract_quality_gate=legacy_workbench._extract_quality_gate,
    )


@router.post("/api/workbench/auto-run")
def auto_run(payload: legacy_workbench.AutoRunPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    legacy_workbench._sync_stage_a_workbench_state()
    legacy_workbench._ensure_dirs()
    requirement_text = payload.requirement.strip()
    input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
    openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
    has_multisource_inputs = workbench_generation_service.has_multisource_inputs(
        input_sources=input_sources,
        openapi_spec=openapi_spec,
        prd_text=payload.prd_text,
        prd_url=payload.prd_url,
        user_story=payload.user_story,
        git_diff=payload.git_diff,
        git_diff_path=payload.git_diff_path,
        openapi_url=payload.openapi_url,
        defect_ticket=payload.defect_ticket,
        runtime_logs=payload.runtime_logs,
    )
    raw_urls = [str(item).strip() for item in payload.page_urls if str(item).strip()]
    if not raw_urls:
        raise legacy_workbench.HTTPException(
            status_code=legacy_workbench.status.HTTP_400_BAD_REQUEST,
            detail="page_urls must not be empty",
        )

    items: list[dict[str, Any]] = []
    for raw_url in raw_urls:
        page_context = workbench_generation_service.prepare_auto_run_page_context(
            raw_url=raw_url,
            requirement_text=requirement_text,
            multisource_enabled=has_multisource_inputs,
            build_system_requirement=legacy_workbench._build_system_requirement,
            extract_page_from_url=legacy_workbench._extract_page_from_url,
            resolve_page_url=legacy_workbench._resolve_page_url,
            validate_page_surface_url=legacy_workbench._validate_page_surface_url,
            extract_page_surface=legacy_workbench._extract_page_surface,
            normalize_page_surface=legacy_workbench._normalize_page_surface,
            build_surface_element_candidates=legacy_workbench._build_surface_element_candidates,
            surface_confidence_summary=legacy_workbench._surface_confidence_summary,
            enhance_page_object_from_surface=legacy_workbench._enhance_page_object_from_surface,
            build_requirement_steps=legacy_workbench._build_requirement_steps,
            build_page_object_quality=legacy_workbench._build_page_object_quality,
            normalize_page_object_draft=legacy_workbench._normalize_page_object_draft,
        )
        page_url = str(page_context["page_url"])
        page = str(page_context["page"])
        resolved_page_url = str(page_context["resolved_page_url"])
        effective_requirement = str(page_context["effective_requirement"])
        surface = page_context["surface"] if isinstance(page_context["surface"], dict) else {}
        page_object_path = page_context["page_object_path"]
        steps = page_context["steps"] if isinstance(page_context["steps"], list) else []
        coverage = page_context["coverage"] if isinstance(page_context["coverage"], dict) else {}
        page_object_quality = (
            page_context["page_object_quality"] if isinstance(page_context["page_object_quality"], dict) else {}
        )
        page_object_summary = (
            page_context["page_object_summary"] if isinstance(page_context["page_object_summary"], dict) else {}
        )
        enriched_requirement = f"{effective_requirement}\n目标页面 {page}"
        orchestrator_result: dict[str, Any]
        case_id = ""
        case_path = legacy_workbench.Path()
        test_points: dict[str, Any] = {}
        test_point_path = legacy_workbench.Path()
        requirement_spec: dict[str, Any] = legacy_workbench._build_requirement_spec_for_risk(
            page=page,
            requirement=effective_requirement,
            quality_gate={},
        )
        quality_gate: dict[str, Any] = {}

        try:
            orchestrator_result = legacy_workbench._run_orchestrator_generate(
                requirement=enriched_requirement,
                page=page,
                source=payload.source,
                input_sources=input_sources,
                openapi_spec=openapi_spec or None,
                prd_text=payload.prd_text,
                prd_url=payload.prd_url,
                user_story=payload.user_story,
                git_diff=payload.git_diff,
                git_diff_path=payload.git_diff_path,
                openapi_url=payload.openapi_url,
                defect_ticket=payload.defect_ticket,
                runtime_logs=payload.runtime_logs,
            )
            orchestrator_requirement_spec = orchestrator_result.get("requirement_spec")
            if isinstance(orchestrator_requirement_spec, dict):
                requirement_spec = orchestrator_requirement_spec
            quality_gate = legacy_workbench._extract_quality_gate(requirement_spec) or {}
            generated_result = workbench_generation_service.persist_auto_run_generated_case(
                orchestrator_result=orchestrator_result,
                project=payload.project,
                page=page,
                resolved_page_url=resolved_page_url,
                effective_requirement=effective_requirement,
                steps=steps,
                coverage=coverage,
                surface=surface,
                page_object_path=page_object_path,
                repo_root=legacy_workbench.REPO_ROOT,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
                path_cls=legacy_workbench.Path,
                safe_case_id=legacy_workbench._safe_case_id,
                datetime_module=legacy_workbench.datetime,
                utc=legacy_workbench.UTC,
                http_exception_cls=legacy_workbench.HTTPException,
                bad_gateway_status=legacy_workbench.status.HTTP_502_BAD_GATEWAY,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                normalize_test_point_plan_payload=legacy_workbench._normalize_test_point_plan_payload,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
            )
            case_id = str(generated_result["case_id"])
            case_path = generated_result["case_path"]
            case_yaml = generated_result["case_yaml"] if isinstance(generated_result.get("case_yaml"), dict) else {}
            if case_yaml:
                test_case_service.upsert_test_case_from_workbench(
                    db,
                    project_code=payload.project,
                    case_yaml=case_yaml,
                    source_path=str(case_path),
                )
            test_points = generated_result["test_points"] if isinstance(generated_result["test_points"], dict) else {}
            test_point_path = generated_result["test_point_path"]
        except legacy_workbench.HTTPException as exc:
            blocked_by_quality_gate, blocked_gate = legacy_workbench._is_quality_gate_blocked(exc.detail)
            if blocked_by_quality_gate and isinstance(blocked_gate, dict):
                legacy_workbench._append_history(
                    {
                        "timestamp": legacy_workbench._now_iso(),
                        "action": "auto_generate_case_blocked_by_quality_gate",
                        "case_id": case_id,
                        "page": page,
                        "page_url": resolved_page_url,
                        "quality_gate": blocked_gate,
                        "fallback_reason": exc.detail,
                    }
                )
                items.append(
                    workbench_generation_service.build_auto_run_generate_failed_item(
                        page_url=page_url,
                        resolved_page_url=resolved_page_url,
                        page=page,
                        surface=surface,
                        page_object_path=page_object_path,
                        page_object_quality=page_object_quality,
                        page_object_summary=page_object_summary,
                        coverage=coverage,
                        quality_gate=blocked_gate,
                        runner_script=str(
                            (legacy_workbench.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()
                        ),
                    )
                )
                continue
            fallback_result = workbench_generation_service.persist_auto_run_fallback_case(
                page=page,
                effective_requirement=effective_requirement,
                resolved_page_url=resolved_page_url,
                steps=steps,
                project=payload.project,
                page_object_path=page_object_path,
                surface=surface,
                coverage=coverage,
                fallback_reason=exc.detail,
                build_fallback_case=legacy_workbench._build_fallback_case,
                safe_case_id=legacy_workbench._safe_case_id,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            )
            case_id = str(fallback_result["case_id"])
            case_path = fallback_result["case_path"]
            case_yaml = fallback_result["case_yaml"] if isinstance(fallback_result.get("case_yaml"), dict) else {}
            if case_yaml:
                test_case_service.upsert_test_case_from_workbench(
                    db,
                    project_code=payload.project,
                    case_yaml=case_yaml,
                    source_path=str(case_path),
                )
            test_points = fallback_result["test_points"] if isinstance(fallback_result["test_points"], dict) else {}
            test_point_path = fallback_result["test_point_path"]
        except Exception as exc:  # pragma: no cover
            fallback_result = workbench_generation_service.persist_auto_run_fallback_case(
                page=page,
                effective_requirement=effective_requirement,
                resolved_page_url=resolved_page_url,
                steps=steps,
                project=payload.project,
                page_object_path=page_object_path,
                surface=surface,
                coverage=coverage,
                fallback_reason=str(exc),
                build_fallback_case=legacy_workbench._build_fallback_case,
                safe_case_id=legacy_workbench._safe_case_id,
                write_case_yaml=legacy_workbench._write_case_yaml,
                read_case_yaml=legacy_workbench._read_case_yaml,
                save_case_state=legacy_workbench._save_case_state,
                steps_to_points=legacy_workbench._steps_to_points,
                inherit_test_point_confidence_from_surface=legacy_workbench._inherit_test_point_confidence_from_surface,
                annotate_test_point_plan_review=legacy_workbench._annotate_test_point_plan_review,
                save_test_point_plan=legacy_workbench._save_test_point_plan,
                append_history=legacy_workbench._append_history,
                now_iso=legacy_workbench._now_iso,
                ai_cases_root=legacy_workbench.AI_CASES_ROOT,
            )
            case_id = str(fallback_result["case_id"])
            case_path = fallback_result["case_path"]
            case_yaml = fallback_result["case_yaml"] if isinstance(fallback_result.get("case_yaml"), dict) else {}
            if case_yaml:
                test_case_service.upsert_test_case_from_workbench(
                    db,
                    project_code=payload.project,
                    case_yaml=case_yaml,
                    source_path=str(case_path),
                )
            test_points = fallback_result["test_points"] if isinstance(fallback_result["test_points"], dict) else {}
            test_point_path = fallback_result["test_point_path"]

        run_job = legacy_workbench._start_run(
            project=payload.project,
            case_id=case_id,
            case_path=case_path,
            source="auto-run",
        )
        run_id = str(run_job.get("run_id", "")).strip()
        final_item, timed_out = legacy_workbench._wait_run_terminal(run_id, timeout_seconds=payload.wait_seconds)
        final_status = str((final_item or run_job).get("status", "running")).strip() or "running"
        has_step_coverage_gap = str(coverage.get("status", "full")).lower() != "full"
        has_page_object_gap = str(page_object_summary.get("status", "full")).lower() != "full"
        if (has_step_coverage_gap or has_page_object_gap) and final_status.lower() == "passed":
            final_status = "coverage_gap"
            legacy_workbench._update_job(
                run_id,
                {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
            )
            legacy_workbench._update_runtime_run(
                run_id,
                {"status": final_status, "coverage": coverage, "page_object_summary": page_object_summary},
            )
        else:
            legacy_workbench._update_job(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})
            legacy_workbench._update_runtime_run(run_id, {"coverage": coverage, "page_object_summary": page_object_summary})

        governance_context = workbench_generation_service.build_auto_run_governance_context(
            project=payload.project,
            run_id=run_id,
            case_id=case_id,
            page=page,
            page_url=resolved_page_url,
            effective_requirement=effective_requirement,
            quality_gate=quality_gate,
            steps=steps,
            final_status=final_status,
            surface=surface,
            page_object_quality=page_object_quality,
            page_object_summary=page_object_summary,
            test_points=test_points,
            coverage=coverage,
            requirement_spec=requirement_spec,
            build_page_analysis_context=legacy_workbench._build_page_analysis_context,
            build_item_review_state=legacy_workbench._build_item_review_state,
            evaluate_risk_report=legacy_workbench._evaluate_risk_report,
            build_execution_gate=legacy_workbench._build_execution_gate,
        )
        analysis_context = (
            governance_context["analysis_context"] if isinstance(governance_context["analysis_context"], dict) else {}
        )
        risk_report = governance_context["risk_report"] if isinstance(governance_context["risk_report"], dict) else {}
        review_state = governance_context["review_state"] if isinstance(governance_context["review_state"], dict) else {}
        execution_gate = (
            governance_context["execution_gate"] if isinstance(governance_context["execution_gate"], dict) else {}
        )
        sync_payload = governance_context["sync_payload"] if isinstance(governance_context["sync_payload"], dict) else {}
        legacy_workbench._update_job(run_id, sync_payload)
        legacy_workbench._update_runtime_run(run_id, sync_payload)
        items.append(
            workbench_generation_service.build_auto_run_item(
                page_url=page_url,
                resolved_page_url=resolved_page_url,
                page=page,
                surface=surface,
                analysis_context=analysis_context,
                case_id=case_id,
                case_path=case_path,
                page_object_path=page_object_path,
                page_object_quality=page_object_quality,
                page_object_summary=page_object_summary,
                test_point_path=test_point_path,
                test_points=test_points,
                run_id=run_id,
                final_status=final_status,
                coverage=coverage,
                timed_out=timed_out,
                risk_report=risk_report,
                execution_gate=execution_gate,
                review_state=review_state,
                runner_script=str((legacy_workbench.RUNNER_ROOT / "tests" / "test_yaml_ai_generated.py").resolve()),
            )
        )

    allure_payload: dict[str, Any] = {}
    allure_error: Any = ""
    try:
        allure_payload = legacy_workbench.report_allure_refresh()
    except legacy_workbench.HTTPException as exc:
        allure_error = exc.detail

    return {
        "summary": workbench_generation_service.build_auto_run_summary(
            project=payload.project,
            raw_urls=raw_urls,
            items=items,
        ),
        "items": items,
        "allure": {
            "refresh": allure_payload,
            "error": allure_error,
        },
    }
