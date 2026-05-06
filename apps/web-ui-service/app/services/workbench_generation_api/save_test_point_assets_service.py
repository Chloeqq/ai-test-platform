from __future__ import annotations

from pathlib import Path
from typing import Any

from shared_backend.case_ids import normalize_case_id

from app.services import workbench_asset_service, workbench_state_store

from .context import WorkbenchContext
from . import preview_store


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = _normalized_text(raw)
        if text and text not in items:
            items.append(text)
    return items


def _existing_test_point_asset_ids(project: str) -> list[str]:
    state_root = workbench_state_store.WEB_UI_STATE_ROOT / "test-points"
    project_dir = workbench_asset_service.state_project_dir(project, state_root=state_root)
    ids: list[str] = []
    for folder in (project_dir, project_dir / "plans"):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            case_id = _normalized_text(path.stem)
            if case_id and case_id not in ids:
                ids.append(case_id)
    return ids


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _preview_requirement(preview_id: str) -> tuple[str, dict[str, Any]]:
    normalized_preview_id = _normalized_text(preview_id)
    if not normalized_preview_id:
        return "", {}
    snapshot = preview_store.load_preview_snapshot(normalized_preview_id)
    preview_payload = _dict_value(snapshot.get("preview_payload"))
    item = _dict_value(preview_payload.get("item"))
    requirement_spec = _dict_value(item.get("requirement_spec"))
    requirement = (
        _normalized_text(requirement_spec.get("normalized_requirement"))
        or _normalized_text(requirement_spec.get("raw_requirement"))
        or _normalized_text(item.get("normalized_requirement"))
        or _normalized_text(item.get("raw_requirement"))
        or _normalized_text(snapshot.get("effective_requirement"))
    )
    return requirement, requirement_spec


def _candidate_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in (
        "intent_id",
        "title",
        "summary",
        "intent_type",
        "priority",
        "precondition",
        "steps",
        "steps_hint",
        "expected",
        "expected_result",
        "scene_type",
        "test_data_type",
        "involved_elements",
        "involved_element_codes",
        "tags",
        "review_status",
        "review_note",
        "reviewed_at",
        "reviewed_by",
    ):
        value = candidate.get(key)
        if isinstance(value, list):
            rows = _list_text(value)
            if rows:
                snapshot[key] = rows
            continue
        text = _normalized_text(value)
        if text:
            snapshot[key] = text
    return snapshot


def _build_point(candidate: dict[str, Any], *, index: int) -> dict[str, Any]:
    intent_id = _normalized_text(candidate.get("intent_id")) or f"candidate-{index:02d}"
    title = _normalized_text(candidate.get("title")) or intent_id
    summary = _normalized_text(candidate.get("summary")) or title
    steps = _list_text(candidate.get("steps"))
    involved_elements = _list_text(candidate.get("involved_elements"))
    expected = _normalized_text(candidate.get("expected") or candidate.get("expected_result"))
    precondition = _normalized_text(candidate.get("precondition"))
    point_type = _normalized_text(candidate.get("intent_type")) or "functional"
    action = "candidate"
    if point_type in {"boundary", "negative", "abnormal"}:
        action = "review"
    point_steps = [
        {
            "action": "candidate_step",
            "target": "",
            "value": step,
            "raw_text": step,
        }
        for step in steps
    ]
    if not point_steps:
        point_steps = [
            {
                "action": "candidate_step",
                "target": "",
                "value": summary,
                "raw_text": summary,
            }
        ]
    warnings: list[str] = []
    if not steps:
        warnings.append("缺少结构化步骤。")
    if not involved_elements:
        warnings.append("缺少涉及元素。")
    return {
        "key": intent_id,
        "intent_id": intent_id,
        "point_type": point_type,
        "action": action,
        "description": summary,
        "step_index": index,
        "dependencies": [],
        "source_ids": [intent_id],
        "steps": point_steps,
        "warnings": warnings,
        "requires_review": bool(warnings),
        "involved_elements": involved_elements,
        "expected_result": expected,
        "precondition": precondition,
        "tags": _list_text(candidate.get("tags")),
        "priority": _normalized_text(candidate.get("priority")) or "P1",
        "confidence": 0.8 if steps else 0.6,
        "metadata": {
            "candidate_snapshot": _candidate_snapshot(candidate),
            "traceability": {
                "source_ids": [intent_id],
                "intent_ids": [intent_id],
            },
        },
    }


def _coverage_matrix_from_requirement_spec(
    requirement_spec: dict[str, Any],
    *,
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    point_by_intent = {
        _normalized_text(point.get("intent_id")): _normalized_text(point.get("key"))
        for point in points
        if isinstance(point, dict) and _normalized_text(point.get("intent_id")) and _normalized_text(point.get("key"))
    }
    raw_rows = requirement_spec.get("coverage_matrix")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                continue
            intent_ids = _list_text(raw_row.get("intent_ids"))
            point_keys = [point_by_intent[intent_id] for intent_id in intent_ids if point_by_intent.get(intent_id)]
            rows.append(
                {
                    "row_id": _normalized_text(raw_row.get("row_id")) or f"coverage-row-{index:02d}",
                    "traceability_status": _normalized_text(raw_row.get("traceability_status")) or "covered",
                    "source_ids": _list_text(raw_row.get("source_ids")),
                    "intent_ids": intent_ids,
                    "point_keys": point_keys,
                    "changed_areas": _list_text(raw_row.get("changed_areas")),
                    "explanation": _normalized_text(raw_row.get("explanation")),
                }
            )
    if rows:
        return rows
    intent_ids = _list_text(
        [
            str(point.get("intent_id", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("intent_id", "")).strip()
        ]
    )
    point_keys = _list_text(
        [
            str(point.get("key", "")).strip()
            for point in points
            if isinstance(point, dict) and str(point.get("key", "")).strip()
        ]
    )
    if not intent_ids and not point_keys:
        return []
    return [
        {
            "row_id": "selected-intents",
            "traceability_status": "covered",
            "source_ids": ["source-01"],
            "intent_ids": intent_ids,
            "point_keys": point_keys,
            "changed_areas": [],
            "explanation": "derived from selected test intents",
        }
    ]


def _intent_type_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for candidate in candidates:
        intent_type = _normalized_text(candidate.get("intent_type")) or "functional"
        distribution[intent_type] = int(distribution.get(intent_type, 0) or 0) + 1
    return dict(sorted(distribution.items()))


def _first_candidate_title(candidates: list[dict[str, Any]], *, page: str) -> str:
    for candidate in candidates:
        title = _normalized_text(candidate.get("title")) or _normalized_text(candidate.get("summary"))
        if title:
            return title
    return f"{page} 测试点资产集" if page else "测试点资产集"


class SaveTestPointAssetsService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    def execute(self, payload: Any) -> dict[str, Any]:
        context = self._context
        runtime = context.runtime
        repository = context.repository
        runtime.ensure_dirs()

        project = _normalized_text(getattr(payload, "project", "")) or "mall"
        page = runtime.normalize_page_slug(_normalized_text(getattr(payload, "page", "")))
        if not page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )

        requirement_text = _normalized_text(getattr(payload, "requirement", ""))
        input_sources = [item for item in (getattr(payload, "input_sources", None) or []) if isinstance(item, dict)]
        openapi_spec = getattr(payload, "openapi_spec", None)
        openapi_spec = openapi_spec if isinstance(openapi_spec, dict) else {}
        has_multisource_inputs = context.generation.has_multisource_inputs(
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            prd_text=getattr(payload, "prd_text", ""),
            prd_url=getattr(payload, "prd_url", ""),
            user_story=getattr(payload, "user_story", ""),
            git_diff=getattr(payload, "git_diff", ""),
            git_diff_path=getattr(payload, "git_diff_path", ""),
            openapi_url=getattr(payload, "openapi_url", ""),
            defect_ticket=getattr(payload, "defect_ticket", ""),
            runtime_logs=getattr(payload, "runtime_logs", ""),
        )
        effective_requirement = context.generation.resolve_effective_requirement(
            requirement_text=requirement_text,
            normalized_page=page,
            multisource_enabled=has_multisource_inputs,
        )

        raw_candidates = [item for item in list(getattr(payload, "selected_candidates", []) or []) if isinstance(item, dict)]
        selected_intent_ids = [
            _normalized_text(item)
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if _normalized_text(item)
        ]
        preview_id = _normalized_text(getattr(payload, "preview_id", ""))
        preview_requirement, requirement_spec = _preview_requirement(preview_id)
        if preview_requirement:
            effective_requirement = preview_requirement

        raw_candidates = preview_store.resolve_selected_candidates(
            preview_id=preview_id,
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        batch_candidates = context.candidate_normalizer.normalize_candidates(raw_candidates)
        if len(batch_candidates) > 200:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selected_candidates exceeds max size 200",
            )
        if not batch_candidates:
            return {
                "message": "no selected candidates to save",
                "count": 0,
                "items": [],
            }

        requested_case_id = _normalized_text(getattr(payload, "case_id", ""))
        existing_case_ids = repository.collect_existing_case_ids(assets_cases_root=runtime.AI_CASES_ROOT.parent)
        for case_id in _existing_test_point_asset_ids(project):
            if case_id not in existing_case_ids:
                existing_case_ids.append(case_id)
        candidate_case_id = repository.allocate_case_id(
            requested_case_id=requested_case_id,
            project=project,
            page=page,
            module=page,
            ai_cases_root=runtime.AI_CASES_ROOT,
            existing_case_ids=existing_case_ids,
        )
        points = [_build_point(candidate, index=index) for index, candidate in enumerate(batch_candidates, start=1)]
        selected_ids = [
            _normalized_text(candidate.get("intent_id"))
            for candidate in batch_candidates
            if _normalized_text(candidate.get("intent_id"))
        ]
        involved_elements = _list_text(
            [
                element
                for candidate in batch_candidates
                for element in _list_text(candidate.get("involved_elements"))
            ]
        )
        asset_title = _first_candidate_title(batch_candidates, page=page)
        parse_confidence = requirement_spec.get("parse_confidence")
        try:
            confidence = float(parse_confidence) if parse_confidence is not None else 0.8
        except (TypeError, ValueError):
            confidence = 0.8
        plan = {
            "version": "TestPointPlanV1",
            "project": project,
            "case_id": candidate_case_id,
            "page": page,
            "title": asset_title,
            "priority": _normalized_text(requirement_spec.get("priority")) or _normalized_text(getattr(payload, "priority", "")) or "P1",
            "source_type": "selection_save",
            "requirement": [effective_requirement] if effective_requirement else [],
            "generated_at": runtime.now_iso(),
            "points": points,
            "coverage": {
                "status": "full",
                "coverage_ratio": 1.0 if points else 0.0,
                "generated_case_count": len(points),
                "expected_case_count": len(points),
                "missing_scenarios": [],
                "covered_scenarios": selected_ids,
            },
            "review_summary": {
                "total_points": len(points),
                "mainline_point_count": len(points),
                "design_only_point_count": 0,
                "technique_distribution": _intent_type_distribution(batch_candidates),
            },
            "metadata": {
                "saved_by": "web-ui-service",
                "origin": "selection_save",
                "preview_id": preview_id,
                "asset_title": asset_title,
                "selected_intent_ids": selected_ids,
                "selected_candidates": [_candidate_snapshot(candidate) for candidate in batch_candidates],
                "coverage_matrix": _coverage_matrix_from_requirement_spec(requirement_spec, points=points),
                "requirement_source": "preview.normalized_requirement" if preview_requirement else "payload.requirement",
                "normalized_requirement": effective_requirement,
                "parse_confidence": parse_confidence,
            },
            "involved_elements": involved_elements,
            "confidence": max(0.0, min(1.0, confidence)),
            "warnings": [],
            "requires_review": False,
        }
        plan_path = runtime.save_test_point_plan(
            project=project,
            case_id=candidate_case_id,
            page=page,
            page_url="",
            requirement=effective_requirement,
            plan=plan,
        )
        asset_path = workbench_asset_service.state_case_file(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        asset = workbench_asset_service.load_test_point_asset_with_root(
            project,
            candidate_case_id,
            state_root=workbench_state_store.WEB_UI_STATE_ROOT / "test-points",
        )
        runtime.append_history(
            {
                "timestamp": runtime.now_iso(),
                "action": "save_test_point_asset",
                "case_id": candidate_case_id,
                "page": page,
                "project": project,
                "path": str(asset_path.resolve()),
                "plan_path": str(Path(plan_path).resolve()),
                "intent_count": len(selected_ids) or len(points),
            }
        )

        return {
            "message": "saved 1 test point asset",
            "count": 1,
            "items": [
                {
                    "case_id": candidate_case_id,
                    "project": project,
                    "page": page,
                    "title": asset_title,
                    "intent_ids": selected_ids,
                    "intent_count": len(selected_ids) or len(points),
                    "plan_path": str(Path(plan_path).resolve()),
                    "asset_path": str(asset_path.resolve()),
                    "asset": asset,
                }
            ],
        }
