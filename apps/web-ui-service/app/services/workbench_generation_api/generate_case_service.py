from __future__ import annotations

from typing import Any

from shared_backend.case_ids import normalize_case_id

from .context import WorkbenchContext


class GenerateCaseService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

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
        batch_candidates = context.candidate_normalizer.normalize_candidates(payload.selected_candidates)
        if len(batch_candidates) > 20:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selected_candidates exceeds max size 20",
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
            items.append(item)
        return {
            "message": f"generated {len(items)} cases",
            "item": items[0] if items else {},
            "items": items,
            "count": len(items),
        }
