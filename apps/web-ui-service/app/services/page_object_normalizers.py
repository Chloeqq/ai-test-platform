import re

from fastapi import HTTPException, status

from app.models.page_object import PageElement
from app.services.page_element_code_policy import require_valid_element_code
from shared_backend.type_utils import (
    normalize_project_code_strict as _normalize_project_code_strict,
)

PAGE_OBJECT_STATUS_VALUES = {"draft", "review", "published", "retired"}
PAGE_ELEMENT_STATUS_VALUES = {"active", "inactive", "deprecated"}
LOCATOR_TYPE_VALUES = {"id", "name", "css", "xpath", "text", "placeholder", "role", "data-testid", "data-qa"}
REFERENCE_TYPE_VALUES = {"test_case", "script", "test_point", "plan", "suite"}
GOVERNANCE_STATUS_VALUES = {"draft", "active", "governing", "retired"}
ELEMENT_REVIEW_STATUS_VALUES = {"approved", "pending", "rejected"}
ELEMENT_STABILITY_LEVEL_VALUES = {"high", "medium", "low"}
ELEMENT_MATCH_STRATEGY_VALUES = {"exact", "alias", "derived", "composite", "template"}
ELEMENT_LOCATOR_SOURCE_VALUES = {"", "testid", "qa", "role_name", "placeholder", "id", "name", "css", "xpath", "manual"}
CANDIDATE_PROMOTION_STATUS_VALUES = {"pending", "partially_promoted", "promoted", "rejected"}
CANDIDATE_STATUS_VALUES = {"pending", "reviewed", "promoted", "rejected", "merged"}
BUSINESS_TYPE_VALUES = {
    "input",
    "button",
    "link",
    "menu",
    "tab",
    "switch",
    "checkbox",
    "radio",
    "dialog",
    "table",
    "container",
    "metric_label",
    "metric_value",
    "password_toggle",
}
BUSINESS_DOMAIN_VALUES = {"", "auth", "navigation", "dashboard", "search", "table", "form", "detail", "common"}


def _normalize_project_code(value: str) -> str:
    try:
        return _normalize_project_code_strict(value, max_len=20)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _normalize_identifier(value: str, *, field_name: str, min_length: int = 2, max_length: int = 80) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < min_length or len(normalized) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be {min_length}-{max_length} chars and use letters/digits/_/-",
        )
    return normalized


def _normalize_page_object_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_OBJECT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page object status must be one of: {', '.join(sorted(PAGE_OBJECT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_page_element_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in PAGE_ELEMENT_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page element status must be one of: {', '.join(sorted(PAGE_ELEMENT_STATUS_VALUES))}",
        )
    return normalized


def _normalize_governance_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in GOVERNANCE_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"governance_status must be one of: {', '.join(sorted(GOVERNANCE_STATUS_VALUES))}",
        )
    return normalized


def _normalize_review_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_REVIEW_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"review_status must be one of: {', '.join(sorted(ELEMENT_REVIEW_STATUS_VALUES))}",
        )
    return normalized


def _normalize_stability_level(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_STABILITY_LEVEL_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"stability_level must be one of: {', '.join(sorted(ELEMENT_STABILITY_LEVEL_VALUES))}",
        )
    return normalized


def _normalize_match_strategy(value: str) -> str:
    normalized = str(value or "").strip().lower() or "exact"
    if normalized not in ELEMENT_MATCH_STRATEGY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"match_strategy must be one of: {', '.join(sorted(ELEMENT_MATCH_STRATEGY_VALUES))}",
        )
    return normalized


def _normalize_locator_source(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ELEMENT_LOCATOR_SOURCE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"locator_source must be one of: {', '.join(sorted(ELEMENT_LOCATOR_SOURCE_VALUES - {''}))}",
        )
    return normalized


def _normalize_locator_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in LOCATOR_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"locator_type must be one of: {', '.join(sorted(LOCATOR_TYPE_VALUES))}",
        )
    return normalized


def _locator_source_from_type(locator_type: str) -> str:
    normalized = str(locator_type or "").strip().lower()
    if normalized == "data-testid":
        return "testid"
    if normalized == "data-qa":
        return "qa"
    if normalized == "role":
        return "role_name"
    if normalized in {"placeholder", "id", "name", "css", "xpath"}:
        return normalized
    return "manual"


def _stability_from_locator_source(locator_source: str, *, review_status: str = "approved") -> str:
    normalized = str(locator_source or "").strip().lower()
    if review_status == "approved" and normalized in {"testid", "qa"}:
        return "high"
    if normalized in {"role_name", "placeholder", "id", "name"}:
        return "medium"
    return "low"


def _validate_formal_element_governance_qualification(element: PageElement) -> None:
    """Keep approved high/medium elements aligned with the governance mapping contract."""
    review_status = str(element.review_status or "").strip().lower()
    stability_level = str(element.stability_level or "").strip().lower()
    locator_source = str(element.locator_source or "").strip().lower()
    locator_type = str(element.locator_type or "").strip().lower()
    testid_value = str(element.testid_value or "").strip()
    qa_value = str(element.qa_value or "").strip()

    if review_status != "approved":
        return

    if bool(element.is_key_element) and not testid_value and not qa_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="approved key element requires testid_value or qa_value",
        )

    if stability_level == "high":
        if locator_source not in {"testid", "qa"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high stability element requires locator_source testid or qa",
            )
        if locator_source == "testid" and (locator_type != "data-testid" or not testid_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high testid element requires locator_type data-testid and testid_value",
            )
        if locator_source == "qa" and (locator_type != "data-qa" or not qa_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved high qa element requires locator_type data-qa and qa_value",
            )
        return

    if stability_level == "medium":
        expected_locator_type_by_source = {
            "role_name": "role",
            "placeholder": "placeholder",
            "id": "id",
            "name": "name",
        }
        expected_locator_type = expected_locator_type_by_source.get(locator_source)
        if expected_locator_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approved medium stability element requires locator_source role_name, placeholder, id, or name",
            )
        if locator_type != expected_locator_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"approved medium {locator_source} element requires locator_type {expected_locator_type}",
            )


def _normalize_business_type(value: str, fallback: str = "") -> str:
    normalized = str(value or fallback or "").strip().lower()
    if normalized and normalized not in BUSINESS_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"business_type must be one of: {', '.join(sorted(BUSINESS_TYPE_VALUES))}",
        )
    return normalized


def _normalize_business_domain(value: str, fallback: str = "") -> str:
    normalized = str(value or fallback or "").strip().lower()
    if normalized not in BUSINESS_DOMAIN_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"business_domain must be one of: {', '.join(sorted(item for item in BUSINESS_DOMAIN_VALUES if item))}",
        )
    return normalized


def _normalize_formal_element_code(
    value: str,
    *,
    page_code: str = "",
    business_type: str = "",
    locator_source: str = "",
    locator_type: str = "",
    testid_value: str = "",
) -> str:
    return require_valid_element_code(
        value,
        page_code=page_code,
        business_type=business_type,
        locator_source=locator_source,
        locator_type=locator_type,
        testid_value=testid_value,
    )


def _locator_identity_key(locator_type: str, locator_value: str, role: str) -> tuple[str, str, str]:
    return (
        str(locator_type or "").strip().lower(),
        str(locator_value or "").strip(),
        str(role or "").strip().lower(),
    )


def _locator_relaxed_key(locator_type: str, locator_value: str) -> tuple[str, str]:
    return (
        str(locator_type or "").strip().lower(),
        str(locator_value or "").strip(),
    )


def _normalize_reference_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in REFERENCE_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reference_type must be one of: {', '.join(sorted(REFERENCE_TYPE_VALUES))}",
        )
    return normalized


def _normalize_binary_health_status(value: int) -> int:
    normalized = int(value)
    if normalized not in {0, 1}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="health_status must be 0 or 1",
        )
    return normalized
