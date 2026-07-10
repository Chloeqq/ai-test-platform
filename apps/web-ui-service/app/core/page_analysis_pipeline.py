from __future__ import annotations

import logging
from typing import Any

from app.core.page_analysis_rules import build_page_semantic_model
from shared_backend.schemas import (
    normalize_page_analysis_bundle_v1,
    normalize_page_object_draft_v1,
    normalize_page_semantic_model_v1,
    normalize_page_surface_v1,
    normalize_test_point_plan_v1,
)
from shared_backend.type_utils import dict_value as _dict_value
from shared_backend.type_utils import list_value as _list_value

LOGGER = logging.getLogger(__name__)


from shared_backend.type_utils import dedup_keep_order as _dedup_keep_order


def _surface_summary(surface: dict[str, Any]) -> dict[str, Any]:
    summary = surface.get("confidence_summary")
    if isinstance(summary, dict):
        return summary
    return {
        "confidence": float(surface.get("confidence", 0.0) or 0.0),
        "warnings": [str(item).strip() for item in surface.get("warnings", []) if str(item).strip()] if isinstance(surface.get("warnings"), list) else [],
        "low_confidence_items": [],
        "low_confidence_count": 0,
        "requires_review": bool(surface.get("requires_review", False)),
    }


def normalize_page_surface_model(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    requested_url: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    try:
        normalized, contract_warnings = normalize_page_surface_v1(raw, page=page, requested_url=requested_url, strict=strict)
        normalized["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(normalized.get("warnings")) if str(item).strip()]
            + [str(item).strip() for item in contract_warnings if str(item).strip()]
        )
        confidence_summary = _dict_value(normalized.get("confidence_summary"))
        confidence_summary["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(confidence_summary.get("warnings")) if str(item).strip()]
        )
        normalized["confidence_summary"] = confidence_summary
        return normalized
    except Exception as exc:
        LOGGER.warning("page_surface normalization failed, keep raw payload: %s", exc)
        return raw


def normalize_page_object_model(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    path: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    try:
        normalized, contract_warnings = normalize_page_object_draft_v1(raw, page=page, path=path, strict=strict)
        normalized["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(normalized.get("warnings")) if str(item).strip()]
            + [str(item).strip() for item in contract_warnings if str(item).strip()]
        )
        summary = _dict_value(normalized.get("summary"))
        summary["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(summary.get("warnings")) if str(item).strip()]
        )
        normalized["summary"] = summary
        coverage = _dict_value(normalized.get("coverage"))
        coverage["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(coverage.get("warnings")) if str(item).strip()]
        )
        normalized["coverage"] = coverage
        return normalized
    except Exception as exc:
        LOGGER.warning("page_object normalization failed, keep raw payload: %s", exc)
        return raw


def normalize_page_semantic_model(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    requested_url: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    try:
        normalized, contract_warnings = normalize_page_semantic_model_v1(raw, page=page, requested_url=requested_url, strict=strict)
        normalized["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(normalized.get("warnings")) if str(item).strip()]
            + [str(item).strip() for item in contract_warnings if str(item).strip()]
        )
        summary = _dict_value(normalized.get("summary"))
        summary["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(summary.get("warnings")) if str(item).strip()]
        )
        normalized["summary"] = summary
        return normalized
    except Exception as exc:
        LOGGER.warning("page_semantic normalization failed, keep raw payload: %s", exc)
        return raw


def normalize_test_point_plan_model(
    payload: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    try:
        normalized, contract_warnings = normalize_test_point_plan_v1(raw, strict=strict)
        normalized["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(normalized.get("warnings")) if str(item).strip()]
            + [str(item).strip() for item in contract_warnings if str(item).strip()]
        )
        coverage = _dict_value(normalized.get("coverage"))
        coverage["warnings"] = _dedup_keep_order(
            [str(item).strip() for item in _list_value(coverage.get("warnings")) if str(item).strip()]
        )
        normalized["coverage"] = coverage
        review_summary = _dict_value(normalized.get("review_summary"))
        if "involved_element_count" not in review_summary:
            review_summary["involved_element_count"] = len(
                [item for item in _list_value(normalized.get("involved_elements")) if str(item).strip()]
            )
        normalized["review_summary"] = review_summary
        return normalized
    except Exception as exc:
        LOGGER.warning("test_point_plan normalization failed, keep raw payload: %s", exc)
        return raw


def consume_page_analysis_bundle(
    *,
    page: str,
    project: str = "default",
    case_id: str = "",
    page_url: str = "",
    page_surface: dict[str, Any] | None = None,
    page_semantic: dict[str, Any] | None = None,
    page_object: dict[str, Any] | None = None,
    test_points: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_page = str(page or "").strip()
    normalized_surface = normalize_page_surface_model(page_surface, page=normalized_page, requested_url=page_url)
    semantic_payload = (
        page_semantic
        if isinstance(page_semantic, dict) and page_semantic
        else build_page_semantic_model(
            page=normalized_page,
            surface=normalized_surface,
            page_object=page_object if isinstance(page_object, dict) else {},
            requested_url=page_url,
        )
    )
    normalized_page_semantic = normalize_page_semantic_model(semantic_payload, page=normalized_page, requested_url=page_url)
    normalized_page_object = normalize_page_object_model(page_object, page=normalized_page)
    normalized_test_points = normalize_test_point_plan_model(test_points)
    raw_bundle = {
        "version": "PageAnalysisBundleV1",
        "page": normalized_page,
        "project": str(project or "mall").strip() or "mall",
        "case_id": str(case_id or "").strip(),
        "page_url": str(page_url or "").strip(),
        "page_surface": normalized_surface,
        "page_semantic": normalized_page_semantic,
        "page_object": normalized_page_object,
        "test_points": normalized_test_points,
    }

    if callable(normalize_page_analysis_bundle_v1):
        normalized_bundle, bundle_warnings = normalize_page_analysis_bundle_v1(raw_bundle, strict=False)
        normalized_bundle["warnings"] = [
            str(item).strip()
            for item in normalized_bundle.get("warnings", [])
            if str(item).strip()
        ] + [str(item).strip() for item in bundle_warnings if str(item).strip()]
        normalized_bundle["warnings"] = list(dict.fromkeys(normalized_bundle["warnings"]))
    else:
        normalized_bundle = {
            "version": "PageAnalysisBundleV1",
            "schema_version": "page-analysis-bundle.v1",
            "page": normalized_page,
            "project": str(project or "mall").strip() or "mall",
            "case_id": str(case_id or "").strip(),
            "page_url": str(page_url or "").strip(),
            "page_surface": normalized_surface,
            "page_surface_summary": _surface_summary(normalized_surface),
            "page_semantic": normalized_page_semantic,
            "page_semantic_summary": normalized_page_semantic.get("summary", {}) if isinstance(normalized_page_semantic.get("summary"), dict) else {},
            "page_object": normalized_page_object,
            "page_object_summary": normalized_page_object.get("summary", {}) if isinstance(normalized_page_object.get("summary"), dict) else {},
            "test_points": normalized_test_points,
            "test_point_summary": normalized_test_points.get("review_summary", {}) if isinstance(normalized_test_points.get("review_summary"), dict) else {},
            "model_versions": {
                "page_surface": str(normalized_surface.get("version", "")).strip(),
                "page_semantic": str(normalized_page_semantic.get("version", "")).strip(),
                "page_object": str(normalized_page_object.get("version", "")).strip(),
                "test_points": str(normalized_test_points.get("version", "")).strip(),
            },
            "consumed_models": {
                "page_surface": str(normalized_surface.get("version", "")).strip(),
                "page_semantic": str(normalized_page_semantic.get("version", "")).strip(),
                "page_object": str(normalized_page_object.get("version", "")).strip(),
                "test_points": str(normalized_test_points.get("version", "")).strip(),
            },
            "confidence": 0.0,
            "warnings": [],
            "requires_review": False,
            "metadata": {},
        }

    model_versions = normalized_bundle.get("model_versions") if isinstance(normalized_bundle.get("model_versions"), dict) else {}
    consumed_models = normalized_bundle.get("consumed_models") if isinstance(normalized_bundle.get("consumed_models"), dict) else {}

    return {
        "analysis_bundle": normalized_bundle,
        "page_surface": normalized_bundle.get("page_surface", {}) if isinstance(normalized_bundle.get("page_surface"), dict) else {},
        "page_surface_summary": normalized_bundle.get("page_surface_summary", {}) if isinstance(normalized_bundle.get("page_surface_summary"), dict) else _surface_summary(normalized_bundle.get("page_surface", {}) if isinstance(normalized_bundle.get("page_surface"), dict) else {}),
        "page_semantic": normalized_bundle.get("page_semantic", {}) if isinstance(normalized_bundle.get("page_semantic"), dict) else {},
        "page_semantic_summary": normalized_bundle.get("page_semantic_summary", {}) if isinstance(normalized_bundle.get("page_semantic_summary"), dict) else {},
        "page_object": normalized_bundle.get("page_object", {}) if isinstance(normalized_bundle.get("page_object"), dict) else {},
        "page_object_summary": normalized_bundle.get("page_object_summary", {}) if isinstance(normalized_bundle.get("page_object_summary"), dict) else {},
        "test_points": normalized_bundle.get("test_points", {}) if isinstance(normalized_bundle.get("test_points"), dict) else {},
        "test_point_summary": normalized_bundle.get("test_point_summary", {}) if isinstance(normalized_bundle.get("test_point_summary"), dict) else {},
        "model_versions": model_versions,
        "consumed_models": consumed_models,
        "confidence": float(normalized_bundle.get("confidence", 0.0) or 0.0),
        "warnings": [str(item).strip() for item in normalized_bundle.get("warnings", []) if str(item).strip()] if isinstance(normalized_bundle.get("warnings"), list) else [],
        "requires_review": bool(normalized_bundle.get("requires_review", False)),
    }
