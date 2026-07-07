from __future__ import annotations

from typing import Any

from shared_backend.case_ids import normalize_case_id
from shared_backend.execution_compiler import ExecutionCompilerError
from shared_backend.element_binding import enrich_candidate_with_element_codes

from .context import WorkbenchContext
from . import preview_store
from . import constants as _c
from ..workbench_generation_compiler.runtime.generate_pipeline import resolve_page_object


class GenerateCaseService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    @staticmethod
    def _compact_state(value: Any) -> dict[str, Any]:
        state = value if isinstance(value, dict) else {}
        compact: dict[str, Any] = {}
        asset_id = str(state.get("asset_id", "")).strip()
        if asset_id:
            compact["asset_id"] = asset_id
        version_raw = state.get("version")
        if isinstance(version_raw, int):
            compact["version"] = version_raw
        updated_at = str(state.get("updated_at", "")).strip()
        if updated_at:
            compact["updated_at"] = updated_at
        return compact

    @staticmethod
    def _compact_quality_gate(value: Any) -> dict[str, Any]:
        gate = value if isinstance(value, dict) else {}
        compact: dict[str, Any] = {}
        decision = str(gate.get("decision", "")).strip()
        if decision:
            compact["decision"] = decision
        stage = str(gate.get("stage", "")).strip()
        if stage:
            compact["stage"] = stage
        blockers = gate.get("blockers")
        if isinstance(blockers, list):
            compact["blocker_count"] = len(blockers)
        return compact

    def _to_public_item(self, item: Any) -> dict[str, Any]:
        raw = item if isinstance(item, dict) else {}
        compact: dict[str, Any] = {}
        for key in ("case_id", "project", "page", "path", "test_points_path"):
            value = raw.get(key)
            text = str(value or "").strip()
            if text:
                compact[key] = text

        state = raw.get("state") if isinstance(raw.get("state"), dict) else {}
        title = str(raw.get("title", "")).strip() or str(state.get("title", "")).strip()
        if title:
            compact["title"] = title
        priority = str(raw.get("priority", "")).strip() or str(state.get("priority", "")).strip()
        if priority:
            compact["priority"] = priority

        synced_case_raw = raw.get("synced_case")
        if isinstance(synced_case_raw, dict):
            synced_case: dict[str, Any] = {}
            synced_id = synced_case_raw.get("id")
            if isinstance(synced_id, int):
                synced_case["id"] = synced_id
            synced_case_id = str(synced_case_raw.get("case_id", "")).strip()
            if synced_case_id:
                synced_case["case_id"] = synced_case_id
            synced_project_code = str(synced_case_raw.get("project_code", "")).strip()
            if synced_project_code:
                synced_case["project_code"] = synced_project_code
            if synced_case:
                compact["synced_case"] = synced_case

        compact_state = self._compact_state(state)
        if compact_state:
            compact["state"] = compact_state

        compact_quality_gate = self._compact_quality_gate(raw.get("quality_gate"))
        if compact_quality_gate:
            compact["quality_gate"] = compact_quality_gate
        return compact

    def _build_generated_case_payload(
        self,
        *,
        payload: Any,
        normalized_page: str,
        effective_requirement: str,
        multisource_enabled: bool,
        input_sources: list[dict[str, Any]],
        openapi_spec: dict[str, Any],
        existing_case_ids: list[str],
        selected_candidate: dict[str, Any] | None,
        mode: str = "generate",
    ) -> dict[str, Any]:
        return self._context.generation.build_generated_case_payload(
            payload=payload,
            normalized_page=normalized_page,
            effective_requirement=effective_requirement,
            multisource_enabled=multisource_enabled,
            input_sources=input_sources,
            openapi_spec=openapi_spec,
            existing_case_ids=existing_case_ids,
            selected_candidate=selected_candidate,
            mode=mode,
            save_test_point_plan=self._context.runtime.save_test_point_plan,
        )

    def execute(self, payload: Any, *, mode: str = "generate") -> dict[str, Any]:
        context = self._context
        runtime = context.runtime
        generation = context.generation
        repository = context.repository
        runtime.ensure_dirs()
        normalized_page = runtime.normalize_page_slug(payload.page) if payload.page.strip() else ""
        if not normalized_page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )
        requirement_text = payload.requirement.strip()
        input_sources = [item for item in payload.input_sources if isinstance(item, dict)]
        openapi_spec = payload.openapi_spec if isinstance(payload.openapi_spec, dict) else {}
        has_multisource_inputs = generation.has_multisource_inputs(
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
        effective_requirement = generation.resolve_effective_requirement(
            requirement_text=requirement_text,
            normalized_page=normalized_page,
            multisource_enabled=has_multisource_inputs,
        )
        if not effective_requirement and not has_multisource_inputs and not normalized_page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_400_BAD_REQUEST,
                detail="requirement must not be empty when no page or additional input sources are provided",
            )
        existing_case_ids = repository.collect_existing_case_ids(assets_cases_root=runtime.ASSETS_CASES_ROOT)
        selected_intent_ids = [
            str(item or "").strip()
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if str(item or "").strip()
        ]
        raw_candidates = [item for item in list(payload.selected_candidates or []) if isinstance(item, dict)]
        enriched_candidates = preview_store.resolve_selected_candidates(
            preview_id=str(getattr(payload, "preview_id", "") or "").strip(),
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        try:
            page_object = resolve_page_object(payload.project, normalized_page)
        except ExecutionCompilerError:
            page_object = {}
        if isinstance(page_object, dict) and page_object:
            enriched_candidates = [
                enrich_candidate_with_element_codes(candidate, page_object) if isinstance(candidate, dict) else candidate
                for candidate in enriched_candidates
            ]
        batch_candidates = context.candidate_normalizer.normalize_candidates(enriched_candidates)
        if len(batch_candidates) > _c.MAX_CANDIDATES:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"selected_candidates exceeds max size {_c.MAX_CANDIDATES}",
            )

        if not batch_candidates:
            result = self._build_generated_case_payload(
                payload=payload,
                normalized_page=normalized_page,
                effective_requirement=effective_requirement,
                multisource_enabled=has_multisource_inputs,
                input_sources=input_sources,
                openapi_spec=openapi_spec,
                existing_case_ids=existing_case_ids,
                selected_candidate=None,
                mode=mode,
            )
            item = repository.sync_generated_case_item(
                result=result,
                payload=payload,
                selected_candidate=None,
                write_case_yaml=runtime.write_case_yaml,
                save_case_state=runtime.save_case_state,
                append_history=runtime.append_history,
                now_iso=runtime.now_iso,
                ai_cases_root=runtime.AI_CASES_ROOT,
                http_exception_cls=runtime.HTTPException,
            )
            public_item = self._to_public_item(item)
            return {
                "message": "generated 1 cases",
                "item": public_item,
                "items": [public_item],
                "count": 1,
            }

        items: list[dict[str, Any]] = []
        for candidate in batch_candidates:
            candidate_tags = candidate.get("tags")
            candidate_intent_id = str(candidate.get("intent_id", "")).strip()
            candidate_update = {
                "title": str(candidate.get("title", "")).strip() or payload.title,
                "priority": str(candidate.get("priority", "")).strip() or payload.priority,
                "tags": candidate_tags if isinstance(candidate_tags, list) and candidate_tags else payload.tags,
                "selected_candidates": [candidate],
                "selected_intent_ids": [candidate_intent_id] if candidate_intent_id else [],
            }
            if hasattr(payload, "model_copy"):
                candidate_payload = payload.model_copy(deep=True, update=candidate_update)  # type: ignore[attr-defined]
            else:
                candidate_payload = payload.copy(deep=True, update=candidate_update)  # type: ignore[attr-defined]
            result = self._build_generated_case_payload(
                payload=candidate_payload,
                normalized_page=normalized_page,
                effective_requirement=self._context.candidate_normalizer.build_candidate_requirement(
                    effective_requirement,
                    candidate,
                ),
                multisource_enabled=has_multisource_inputs,
                input_sources=input_sources,
                openapi_spec=openapi_spec,
                existing_case_ids=existing_case_ids,
                selected_candidate=candidate,
                mode=mode,
            )
            item = repository.sync_generated_case_item(
                result=result,
                payload=candidate_payload,
                selected_candidate=candidate,
                write_case_yaml=runtime.write_case_yaml,
                save_case_state=runtime.save_case_state,
                append_history=runtime.append_history,
                now_iso=runtime.now_iso,
                ai_cases_root=runtime.AI_CASES_ROOT,
                http_exception_cls=runtime.HTTPException,
            )
            case_id = normalize_case_id(str(item.get("case_id", "")).strip(), fallback="").strip()
            if case_id and case_id not in existing_case_ids:
                existing_case_ids.append(case_id)
            items.append(self._to_public_item(item))
        return {
            "message": f"generated {len(items)} cases",
            "item": items[0] if items else {},
            "items": items,
            "count": len(items),
        }
