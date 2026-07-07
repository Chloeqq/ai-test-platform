from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.services import workbench_state_store


PREVIEW_ROOT = workbench_state_store.WEB_UI_STATE_ROOT / "preview-test-points"
_PREVIEW_ID_RE = re.compile(r"^preview-[a-f0-9]{16}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _preview_path(preview_id: str) -> Path:
    normalized = _text(preview_id)
    if not _PREVIEW_ID_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "preview_not_found", "message": "preview snapshot not found"},
        )
    return PREVIEW_ROOT / f"{normalized}.json"


def _requirement_spec(snapshot: dict[str, Any]) -> dict[str, Any]:
    preview_payload = _dict(snapshot.get("preview_payload"))
    item = _dict(preview_payload.get("item"))
    return _dict(item.get("requirement_spec"))


def _quality_gate(requirement_spec: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return _dict(item.get("quality_gate")) or _dict(requirement_spec.get("quality_gate"))


def _steps_summary(intent: dict[str, Any]) -> str:
    steps = [_text(item) for item in _list(intent.get("steps")) if _text(item)]
    if steps:
        return "，".join(steps[:2])[:160]
    hints = [_text(item) for item in _list(intent.get("steps_hint")) if _text(item)]
    if hints:
        return "，".join(hints[:2])[:160]
    return (_text(intent.get("summary")) or _text(intent.get("precondition")) or _text(intent.get("title")))[:160]


def _public_intent(intent: dict[str, Any], *, index: int, preview_id: str) -> dict[str, Any]:
    intent_id = _text(intent.get("intent_id")) or f"intent-{index:02d}"
    title = _text(intent.get("title")) or _text(intent.get("summary")) or f"测试点 {index}"
    return {
        "intent_id": intent_id,
        "title": title,
        "intent_type": _text(intent.get("intent_type")) or "functional",
        "priority": _text(intent.get("priority")) or "P1",
        "steps_summary": _steps_summary(intent),
        "expected_result": _text(intent.get("expected_result") or intent.get("expected")),
        "detail_url": f"/api/workbench/preview-test-points/{preview_id}/test-intents/{intent_id}",
    }


def _public_quality_gate(gate: dict[str, Any]) -> dict[str, Any]:
    blockers = [item for item in _list(gate.get("blockers")) if isinstance(item, dict)]
    return {
        "decision": _text(gate.get("decision")) or "unknown",
        "stage": _text(gate.get("stage")),
        "blocker_count": len(blockers),
        "blockers": [
            {
                "code": _text(item.get("code")),
                "message": _text(item.get("message") or item.get("reason")),
            }
            for item in blockers[:10]
        ],
    }


def _sanitize_parser_runtime(value: dict[str, Any]) -> dict[str, Any]:
    runtime = deepcopy(value)
    runtime.pop("llm_trace", None)
    runtime.pop("prompt_fingerprint", None)
    for key in ("overlay_keys", "overlay_key_count"):
        runtime.pop(key, None)
    return runtime


def _sanitize_requirement_spec_for_diagnostics(requirement_spec: dict[str, Any]) -> dict[str, Any]:
    spec = deepcopy(requirement_spec)
    parser_runtime = _dict(spec.get("parser_runtime"))
    if parser_runtime:
        spec["parser_runtime"] = _sanitize_parser_runtime(parser_runtime)
    return spec


def save_preview_snapshot(
    *,
    project: str,
    page: str,
    source: str,
    effective_requirement: str,
    preview_payload: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    preview_id = f"preview-{uuid.uuid4().hex[:16]}"
    snapshot = {
        "preview_id": preview_id,
        "project": _text(project) or "mall",
        "page": _text(page),
        "source": _text(source) or "manual",
        "effective_requirement": _text(effective_requirement),
        "trace_id": _text(trace_id),
        "created_at": workbench_state_store.now_iso(),
        "preview_payload": preview_payload if isinstance(preview_payload, dict) else {},
    }
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    with workbench_state_store.FILE_LOCK:
        _preview_path(preview_id).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return snapshot


def load_preview_snapshot(preview_id: str) -> dict[str, Any]:
    path = _preview_path(preview_id)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "preview_not_found", "message": "preview snapshot not found"},
        )
    with workbench_state_store.FILE_LOCK:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "preview_snapshot_corrupted", "message": "preview snapshot is corrupted"},
            ) from exc
    return payload if isinstance(payload, dict) else {}


def build_public_preview_response(snapshot: dict[str, Any]) -> dict[str, Any]:
    preview_id = _text(snapshot.get("preview_id"))
    preview_payload = _dict(snapshot.get("preview_payload"))
    item = _dict(preview_payload.get("item"))
    requirement_spec = _requirement_spec(snapshot)
    intents = [item for item in _list(requirement_spec.get("test_intents")) if isinstance(item, dict)]
    gate = _quality_gate(requirement_spec, item)
    public_intents = [
        _public_intent(intent, index=index, preview_id=preview_id)
        for index, intent in enumerate(intents, start=1)
    ]
    distribution: dict[str, int] = {}
    for intent in public_intents:
        intent_type = _text(intent.get("intent_type")) or "unknown"
        distribution[intent_type] = distribution.get(intent_type, 0) + 1
    return {
        "item": {
            "preview_id": preview_id,
            "page": _text(requirement_spec.get("page")) or _text(snapshot.get("page")),
            "priority": _text(requirement_spec.get("priority")) or "P1",
            "parse_confidence": requirement_spec.get("parse_confidence", item.get("parse_confidence", 0)),
            "intent_count": len(public_intents),
            "intent_type_distribution": distribution,
            "quality_gate": _public_quality_gate(gate),
            "test_intents": public_intents,
            "diagnostics_url": f"/api/workbench/preview-test-points/{preview_id}/diagnostics",
            "output_contract": {
                "machine_schema": "TestPointPreviewPublicV1",
                "detail_schema": "RequirementSpecV1",
                "rendered_by": "web-ui-service",
            },
        }
    }


def build_preview_diagnostics(preview_id: str) -> dict[str, Any]:
    snapshot = load_preview_snapshot(preview_id)
    requirement_spec = _sanitize_requirement_spec_for_diagnostics(_requirement_spec(snapshot))
    gate = _dict(requirement_spec.get("quality_gate"))
    return {
        "item": {
            "preview_id": _text(snapshot.get("preview_id")),
            "project": _text(snapshot.get("project")),
            "page": _text(snapshot.get("page")),
            "created_at": _text(snapshot.get("created_at")),
            "quality_gate": {
                "decision": _text(gate.get("decision")) or "unknown",
                "metrics": _dict(gate.get("metrics")),
                "thresholds": _dict(gate.get("thresholds")),
                "blockers": _list(gate.get("blockers")),
            },
            "ambiguities": _list(requirement_spec.get("ambiguities")),
            "dependency_graph": _list(requirement_spec.get("dependency_graph")),
            "coverage_matrix": _list(requirement_spec.get("coverage_matrix")),
            "parser_runtime": _dict(requirement_spec.get("parser_runtime")),
            "requirement_analysis_markdown": _text(
                _dict(_dict(snapshot.get("preview_payload")).get("item")).get("requirement_analysis_markdown")
            ),
        }
    }


def get_preview_intents(preview_id: str, selected_intent_ids: list[str] | None = None) -> list[dict[str, Any]]:
    snapshot = load_preview_snapshot(preview_id)
    requirement_spec = _requirement_spec(snapshot)
    intents = [item for item in _list(requirement_spec.get("test_intents")) if isinstance(item, dict)]
    selected = [_text(item) for item in (selected_intent_ids or []) if _text(item)]
    if not selected:
        return [dict(item) for item in intents]
    selected_set = set(selected)
    return [dict(item) for item in intents if _text(item.get("intent_id")) in selected_set]


def resolve_selected_candidates(
    *,
    preview_id: str,
    selected_intent_ids: list[str] | None = None,
    fallback_candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    fallback = [dict(item) for item in (fallback_candidates or []) if isinstance(item, dict)]
    normalized_preview_id = _text(preview_id)
    if not normalized_preview_id:
        return fallback
    ordered_ids = [_text(item) for item in (selected_intent_ids or []) if _text(item)]
    if not ordered_ids:
        ordered_ids = [
            _text(item.get("intent_id"))
            for item in fallback
            if _text(item.get("intent_id"))
        ]
    if not ordered_ids:
        return fallback
    intents = get_preview_intents(normalized_preview_id, ordered_ids)
    by_id = {_text(item.get("intent_id")): item for item in intents if _text(item.get("intent_id"))}
    resolved = [dict(by_id[item]) for item in ordered_ids if item in by_id]
    return resolved or fallback


def build_preview_intent_detail(preview_id: str, intent_id: str) -> dict[str, Any]:
    normalized_intent_id = _text(intent_id)
    for intent in get_preview_intents(preview_id, [normalized_intent_id]):
        if _text(intent.get("intent_id")) == normalized_intent_id:
            return {
                "item": {
                    "preview_id": _text(preview_id),
                    "intent": intent,
                }
            }
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "test_intent_not_found", "message": "test intent not found"},
    )
