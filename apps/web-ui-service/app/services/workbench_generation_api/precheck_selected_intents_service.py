from __future__ import annotations

from typing import Any

from shared_backend import ExecutionCompilerError
from shared_backend.element_binding import resolve_involved_element_codes
from shared_backend.type_utils import str_value as _normalized_text

from .context import WorkbenchContext
from . import preview_store
from ..workbench_generation_compiler.runtime.generate_pipeline import resolve_page_object


_NON_DOM_INVOLVED_ELEMENTS = {
    "页面",
    "当前页面",
    "浏览器地址栏",
    "地址栏",
    "工作台URL",
    "登录页面URL",
    "工作台首页URL",
    "dashboard",
    "home",
}

_URL_PATH_LIKE_RE = __import__("re").compile(r"^(/[a-zA-Z0-9_\-./]*[a-zA-Z])|(#[a-zA-Z])|([a-z]+://)")


def _is_non_dom_involved_element(value: Any) -> bool:
    normalized = _normalized_text(value)
    if normalized in _NON_DOM_INVOLVED_ELEMENTS:
        return True
    if normalized.endswith("URL") or normalized.endswith("Url"):
        return True
    if _URL_PATH_LIKE_RE.match(normalized):
        return True
    return False


class PrecheckSelectedIntentsService:
    def __init__(self, *, context: WorkbenchContext) -> None:
        self._context = context

    def execute(self, payload: Any) -> dict[str, Any]:
        runtime = self._context.runtime
        project = _normalized_text(getattr(payload, "project", "")) or context.default_project
        page_raw = _normalized_text(getattr(payload, "page", ""))
        page = runtime.normalize_page_slug(page_raw) if page_raw else ""
        if not page:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page must not be empty",
            )

        raw_candidates = [item for item in list(getattr(payload, "selected_candidates", []) or []) if isinstance(item, dict)]
        selected_intent_ids = [
            _normalized_text(item)
            for item in list(getattr(payload, "selected_intent_ids", []) or [])
            if _normalized_text(item)
        ]
        resolved_candidates = preview_store.resolve_selected_candidates(
            preview_id=_normalized_text(getattr(payload, "preview_id", "")),
            selected_intent_ids=selected_intent_ids,
            fallback_candidates=raw_candidates,
        )
        normalized_candidates = self._context.candidate_normalizer.normalize_candidates(
            resolved_candidates
        )
        if len(normalized_candidates) > 20:
            raise runtime.HTTPException(
                status_code=runtime.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="selected_candidates exceeds max size 20",
            )

        page_object_error: dict[str, Any] | None = None
        try:
            page_object = resolve_page_object(project, page)
        except ExecutionCompilerError as exc:
            page_object = {}
            page_object_error = exc.to_detail()
        items: list[dict[str, Any]] = []
        status_counts = {"ok": 0, "warn": 0, "block": 0}
        for index, candidate in enumerate(normalized_candidates, start=1):
            intent_id = _normalized_text(candidate.get("intent_id")) or f"candidate-{index:02d}"
            title = _normalized_text(candidate.get("title")) or intent_id
            involved_elements = [
                _normalized_text(item)
                for item in (candidate.get("involved_elements") if isinstance(candidate.get("involved_elements"), list) else [])
                if _normalized_text(item)
            ]
            mappable_involved_elements = [
                item for item in involved_elements if not _is_non_dom_involved_element(item)
            ]
            involved_element_codes, unknown_elements = resolve_involved_element_codes(
                mappable_involved_elements,
                page_object if isinstance(page_object, dict) else {},
            )
            has_steps = bool(candidate.get("steps")) and isinstance(candidate.get("steps"), list)
            expected_result = _normalized_text(
                candidate.get("expected_result")
                or candidate.get("expected")
                or candidate.get("expect_result")
            )

            reasons: list[str] = []
            status = "ok"
            if not _normalized_text(candidate.get("intent_id")):
                reasons.append("缺少 intent_id")
                status = "block"
            if not involved_elements:
                reasons.append("缺少 involved_elements")
                if status != "block":
                    status = "warn"
            if unknown_elements:
                reasons.append(f"元素未在 Page Object 注册: {', '.join(unknown_elements)}")
                status = "block"
            if not has_steps:
                reasons.append("缺少结构化 steps")
                if status == "ok":
                    status = "warn"
            if not expected_result:
                reasons.append("缺少 expected_result")
                if status == "ok":
                    status = "warn"
            if page_object_error is not None:
                page_object_reason = _normalized_text(page_object_error.get("reason")) or _normalized_text(page_object_error.get("message"))
                reasons.append(
                    f"页面对象不可用: {page_object_reason or '无法解析页面元素映射'}"
                )
                status = "block"

            status_counts[status] = status_counts.get(status, 0) + 1
            items.append(
                {
                    "intent_id": intent_id,
                    "title": title,
                    "status": status,
                    "reasons": reasons,
                    "unknown_elements": unknown_elements,
                    "involved_elements": involved_elements,
                    "involved_element_codes": involved_element_codes,
                    "can_generate": status != "block",
                }
            )

        return {
            "items": items,
            "summary": {
                "total": len(items),
                "status_counts": status_counts,
                "block_count": int(status_counts.get("block", 0) or 0),
                "warn_count": int(status_counts.get("warn", 0) or 0),
                "ok_count": int(status_counts.get("ok", 0) or 0),
                "project": project,
                "page": page,
                "page_object_error": page_object_error,
            },
        }
