from __future__ import annotations

import fnmatch
import ipaddress
import logging
import os
import socket
from collections.abc import Callable
from typing import Any
from urllib import parse as url_parse

from app.core import page_analysis_rules
from app.core.page_analysis_pipeline import (
    normalize_page_surface_model,
    normalize_test_point_plan_model,
)
from shared_backend.type_utils import dict_value as _dict_value
from shared_backend.type_utils import list_value as _list_value

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

from shared_backend.type_utils import dedup_keep_order as _dedup_keep_order


def _clamp_confidence(value: Any) -> float:
    return page_analysis_rules.clamp_confidence(value)


# ---------------------------------------------------------------------------
# Page URL helpers
# ---------------------------------------------------------------------------

def extract_page_from_url(
    raw_url: str,
    *,
    normalize_page_slug_fn: Any,
    http_exception_cls: Any,
    bad_request_status: int,
) -> tuple[str, str]:
    value = str(raw_url).strip()
    if not value:
        raise http_exception_cls(status_code=bad_request_status, detail="page_urls contains empty value")

    parsed = url_parse.urlparse(value)
    path = parsed.fragment.split("?", 1)[0] if parsed.fragment else parsed.path
    segments = [item for item in path.split("/") if item]
    candidate = segments[-1] if segments else value
    page = normalize_page_slug_fn(candidate)
    return value, page


def resolve_page_url(
    raw_url: str,
    page: str,
    *,
    canonical_hash_routes: dict[str, str] | None = None,
) -> str:
    parsed = url_parse.urlparse(str(raw_url).strip())
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or "localhost:5174"
    base = f"{scheme}://{netloc}"
    canonical = (canonical_hash_routes or {}).get(page)
    if canonical:
        return f"{base}/#{canonical}"
    if parsed.fragment:
        fragment = parsed.fragment
        if not fragment.startswith("/"):
            fragment = "/" + fragment
        return f"{base}/#{fragment}"
    path = parsed.path or "/"
    return f"{base}{path}"


def route_signature(raw_url: str) -> str:
    parsed = url_parse.urlparse(str(raw_url or "").strip())
    fragment = str(parsed.fragment or "").split("?", 1)[0].strip()
    if fragment:
        return fragment if fragment.startswith("/") else f"/{fragment}"
    path = str(parsed.path or "").strip()
    return path if path.startswith("/") else f"/{path}" if path else ""


def is_allowed_host_pattern(hostname: str, *, patterns: list[str] | None = None) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return False
    configured_patterns = [str(item).strip().lower() for item in (patterns or []) if str(item).strip()]
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in configured_patterns)


def is_private_or_local_hostname(hostname: str, port: int | None) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return True
    try:
        ip_obj = ipaddress.ip_address(normalized)
        return bool(
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        )
    except ValueError:
        pass

    if normalized in {"localhost", "localhost.localdomain"}:
        return True

    try:
        candidates = socket.getaddrinfo(normalized, port or 80, proto=socket.IPPROTO_TCP)
    except OSError:
        return True
    for candidate in candidates:
        try:
            resolved_ip = ipaddress.ip_address(candidate[4][0])
        except Exception:
            return True
        if (
            resolved_ip.is_private
            or resolved_ip.is_loopback
            or resolved_ip.is_link_local
            or resolved_ip.is_reserved
            or resolved_ip.is_multicast
        ):
            return True
    return False


def validate_page_surface_url(
    raw_url: str,
    *,
    allow_private_hosts: bool = False,
    allowed_host_patterns: list[str] | None = None,
    http_exception_cls: Callable[..., Exception] = Exception,
    bad_request_status: int = 400,
    unprocessable_entity_status: int = 422,
) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise http_exception_cls(status_code=bad_request_status, detail="page url must not be empty")

    parsed = url_parse.urlparse(value)
    scheme = str(parsed.scheme or "http").strip().lower()
    if scheme not in {"http", "https"}:
        raise http_exception_cls(status_code=unprocessable_entity_status, detail="page url must use http or https")
    if parsed.username or parsed.password:
        raise http_exception_cls(status_code=unprocessable_entity_status, detail="page url must not contain credentials")

    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        raise http_exception_cls(status_code=unprocessable_entity_status, detail="page url hostname is required")

    if allow_private_hosts:
        return value

    if is_private_or_local_hostname(hostname, parsed.port) and not is_allowed_host_pattern(
        hostname,
        patterns=allowed_host_patterns,
    ):
        raise http_exception_cls(
            status_code=unprocessable_entity_status,
            detail=f"page url host is blocked by SSRF policy: {hostname}",
        )
    return value


# ---------------------------------------------------------------------------
# Surface element candidates / confidence
# ---------------------------------------------------------------------------

def build_surface_element_candidate(
    *,
    key: str,
    label: str,
    locator_type: str,
    locator_value: str,
    confidence: float,
    source: str,
    role: str = "",
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return page_analysis_rules.build_surface_element_candidate(
        key=key,
        label=label,
        locator_type=locator_type,
        locator_value=locator_value,
        confidence=confidence,
        source=source,
        role=role,
        warnings=warnings,
        metadata=metadata,
    )


def build_surface_element_candidates(page: str, surface: dict[str, Any]) -> list[dict[str, Any]]:
    return page_analysis_rules.build_surface_element_candidates(page, surface)


def surface_confidence_summary(surface: dict[str, Any]) -> dict[str, Any]:
    return page_analysis_rules.surface_confidence_summary(surface)


def surface_inferred_elements(page: str, surface: dict[str, Any]) -> dict[str, dict[str, str]]:
    return page_analysis_rules.surface_inferred_elements(page, surface)


def build_surface_result_from_snapshot(
    *,
    page_url: str,
    payload: dict[str, Any],
    frame_surface: dict[str, Any],
    login_url: str,
    login_attempted: bool,
    login_succeeded: bool,
    redirected_to_login: bool,
    login_network_idle_reached: bool,
    target_network_idle_reached: bool,
    marker_selector: str,
    selector_wait_status: str,
    requested_route: str,
    final_route: str,
    route_mismatch: bool,
    stability: dict[str, Any],
) -> dict[str, Any]:
    return page_analysis_rules.build_surface_result_from_snapshot(
        page_url=page_url,
        payload=payload,
        frame_surface=frame_surface,
        login_url=login_url,
        login_attempted=login_attempted,
        login_succeeded=login_succeeded,
        redirected_to_login=redirected_to_login,
        login_network_idle_reached=login_network_idle_reached,
        target_network_idle_reached=target_network_idle_reached,
        marker_selector=marker_selector,
        selector_wait_status=selector_wait_status,
        requested_route=requested_route,
        final_route=final_route,
        route_mismatch=route_mismatch,
        stability=stability,
    )


def normalize_page_surface(
    payload: dict[str, Any] | None,
    *,
    page: str = "",
    requested_url: str = "",
) -> dict[str, Any]:
    return normalize_page_surface_model(payload, page=page, requested_url=requested_url)


# ---------------------------------------------------------------------------
# Surface stability
# ---------------------------------------------------------------------------

def compute_surface_stability(samples: list[dict[str, int]]) -> dict[str, Any]:
    normalized: list[dict[str, int]] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        normalized.append(
            {
                "field_count": int(sample.get("field_count", 0) or 0),
                "button_count": int(sample.get("button_count", 0) or 0),
                "title_count": int(sample.get("title_count", 0) or 0),
                "loading_mask_count": int(sample.get("loading_mask_count", 0) or 0),
            }
        )
    if not normalized:
        return {"status": "unknown", "stable": False, "sample_count": 0}

    last = normalized[-1]
    previous = normalized[-2] if len(normalized) >= 2 else None
    stable = bool(previous) and previous == last and int(last.get("loading_mask_count", 0)) == 0
    status = "stable" if stable else "settling"
    if int(last.get("loading_mask_count", 0)) > 0:
        status = "loading"
    return {
        "status": status,
        "stable": stable,
        "sample_count": len(normalized),
        "latest": last,
        "previous": previous or {},
    }


def wait_for_surface_stable(
    page: Any,
    *,
    attempts: int = 4,
    interval_ms: int = 400,
) -> dict[str, Any]:
    samples: list[dict[str, int]] = []
    for _ in range(max(1, attempts)):
        try:
            snapshot = page.evaluate(
                """() => ({
                    field_count: document.querySelectorAll('input,textarea,select').length,
                    button_count: document.querySelectorAll('button,[role="button"],.el-button').length,
                    title_count: document.querySelectorAll('h1,h2,h3,.el-breadcrumb__inner,.el-card__header,.el-page-header__title,.el-tabs__item').length,
                    loading_mask_count: document.querySelectorAll('.el-loading-mask, .loading, [aria-busy="true"]').length,
                })"""
            )
        except Exception:
            break
        if isinstance(snapshot, dict):
            samples.append(snapshot)
        stability = compute_surface_stability(samples)
        if bool(stability.get("stable")):
            return stability
        try:
            page.wait_for_timeout(interval_ms)
        except Exception:
            break
    return compute_surface_stability(samples)


def collect_frame_surface(page: Any) -> dict[str, Any]:
    frames = getattr(page, "frames", None)
    if not callable(frames):
        return {"frames": [], "accessible_count": 0, "blocked_count": 0}

    items: list[dict[str, Any]] = []
    blocked_count = 0
    for frame in frames()[1:]:
        try:
            frame_url = str(frame.url or "").strip()
            snapshot = frame.evaluate(
                """() => ({
                    title: document.title || '',
                    field_placeholders: [...document.querySelectorAll('input,textarea,select')]
                        .map((el) => (el.getAttribute('placeholder') || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    button_texts: [...document.querySelectorAll('button,[role="button"],.el-button')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    title_candidates: [...document.querySelectorAll('h1,h2,h3,.el-dialog__title,.el-card__header')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    has_table: !!document.querySelector('.el-table'),
                    has_form: !!document.querySelector('.el-form, form'),
                })"""
            )
            if not isinstance(snapshot, dict):
                continue
            items.append(
                {
                    "url": frame_url,
                    "title": str(snapshot.get("title", "")).strip(),
                    "field_placeholders": [str(item).strip() for item in snapshot.get("field_placeholders", []) if str(item).strip()],
                    "button_texts": [str(item).strip() for item in snapshot.get("button_texts", []) if str(item).strip()],
                    "title_candidates": [str(item).strip() for item in snapshot.get("title_candidates", []) if str(item).strip()],
                    "has_table": bool(snapshot.get("has_table", False)),
                    "has_form": bool(snapshot.get("has_form", False)),
                }
            )
        except Exception:
            blocked_count += 1
            continue
    return {
        "frames": items,
        "accessible_count": len(items),
        "blocked_count": blocked_count,
    }


# ---------------------------------------------------------------------------
# Full page surface extraction
# ---------------------------------------------------------------------------

def extract_page_surface(
    page_url: str,
    *,
    settings: Any,
    validate_page_surface_url_fn: Any,
    wait_for_surface_stable_fn: Any,
    collect_frame_surface_fn: Any,
    route_signature_fn: Any,
    build_surface_result_from_snapshot_fn: Any,
    build_surface_element_candidates_fn: Any,
    surface_confidence_summary_fn: Any,
    normalize_page_surface_fn: Any,
    extract_page_from_url_fn: Any,
    dedup_keep_order_fn: Any,
) -> dict[str, Any]:
    validate_page_surface_url_fn(page_url)
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}

    login_url = str(getattr(settings, "page_surface_login_url", "")).strip() or os.getenv("BASE_URL", "http://localhost:5174/#/login")
    validate_page_surface_url_fn(login_url)
    username = os.getenv("TEST_USERNAME", "")
    password = os.getenv("TEST_PASSWORD", "")
    if not username or not password:
        LOGGER.warning("TEST_USERNAME / TEST_PASSWORD not set; skipping page surface analysis")
        return {}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(6000)
            login_network_idle_reached = False
            target_network_idle_reached = False
            login_attempted = False
            login_succeeded = False
            marker_selector = ""
            selector_wait_status = "not_started"
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            username_filled = False
            for locator in ["请输入用户名", "用户名", "账号", "请输入账号"]:
                try:
                    page.get_by_placeholder(locator).first.fill(username)
                    username_filled = True
                    break
                except Exception:
                    continue
            if not username_filled:
                page.locator("input").first.fill(username)

            password_filled = False
            for locator in ["请输入密码", "密码"]:
                try:
                    page.get_by_placeholder(locator).first.fill(password)
                    password_filled = True
                    break
                except Exception:
                    continue
            if not password_filled:
                page.locator("input[type='password']").first.fill(password)

            try:
                login_attempted = True
                page.get_by_role("button", name="登录").first.click()
            except Exception:
                login_attempted = True
                page.locator("button, .el-button").first.click()
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
                login_network_idle_reached = True
            except Exception:
                login_network_idle_reached = False
            page.wait_for_timeout(1200)
            current_after_login = str(page.url or "").strip()
            login_succeeded = bool(current_after_login) and "#/login" not in current_after_login and "/login" not in current_after_login

            try:
                page.goto(page_url, wait_until="commit", timeout=20000)
            except PlaywrightTimeoutError:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
                target_network_idle_reached = True
            except Exception:
                target_network_idle_reached = False
            stability = wait_for_surface_stable_fn(page, attempts=4, interval_ms=400)
            for selector in [".el-table", ".el-form", ".el-card", ".el-dialog__wrapper", "main", "[role='main']"]:
                try:
                    page.wait_for_selector(selector, state="attached", timeout=2500)
                    marker_selector = selector
                    selector_wait_status = "matched"
                    break
                except Exception:
                    continue
            if not marker_selector:
                selector_wait_status = "timeout"
            page.wait_for_timeout(1200)
            payload = page.evaluate(
                """() => {
                    const fields = [...document.querySelectorAll('input,textarea,select')].map((el) => ({
                        placeholder: el.getAttribute('placeholder') || '',
                        name: el.getAttribute('name') || '',
                        cls: el.className || '',
                    }));
                    const buttons = [...document.querySelectorAll('button,[role="button"],.el-button')].map((el) => ({
                        text: (el.innerText || '').trim(),
                        cls: el.className || '',
                    })).filter((item) => item.text);
                    const menuItems = [...document.querySelectorAll('[role="menuitem"],.el-menu-item')].map((el) => ({
                        text: (el.innerText || '').trim(),
                        cls: el.className || '',
                    })).filter((item) => item.text);
                    const titleCandidates = [...document.querySelectorAll('h1,h2,h3,.el-breadcrumb__inner,.el-card__header,.el-page-header__title,.el-tabs__item')]
                        .map((el) => (el.innerText || '').trim())
                        .filter(Boolean);
                    return {
                        url: location.href,
                        title: document.title,
                        fields,
                        buttons,
                        menuItems,
                        titleCandidates,
                        hasTable: !!document.querySelector('.el-table'),
                        hasForm: !!document.querySelector('.el-form, form'),
                        hasDialog: !!document.querySelector('.el-dialog, .el-dialog__wrapper, [role="dialog"]'),
                        dialogTitles: [...document.querySelectorAll('.el-dialog__title, [role="dialog"] [aria-label], [role="dialog"] h1, [role="dialog"] h2, [role="dialog"] h3')]
                            .map((el) => (el.innerText || el.getAttribute('aria-label') || '').trim())
                            .filter(Boolean)
                            .slice(0, 10),
                        iframeCount: document.querySelectorAll('iframe').length,
                        loadingMaskCount: document.querySelectorAll('.el-loading-mask, .loading, [aria-busy="true"]').length,
                        bodyTextLength: (document.body?.innerText || '').trim().length,
                    };
                }"""
            )
            frame_surface = collect_frame_surface_fn(page)
            browser.close()
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}
    if not isinstance(frame_surface, dict):
        frame_surface = {"frames": [], "accessible_count": 0, "blocked_count": 0}

    final_url = str(payload.get("url", "")).strip()
    redirected_to_login = bool(final_url) and ("#/login" in final_url or "/login" in final_url)
    requested_route = route_signature_fn(page_url)
    final_route = route_signature_fn(final_url)
    route_mismatch = bool(requested_route and final_route and requested_route != final_route)
    surface_result = build_surface_result_from_snapshot_fn(
        page_url=page_url,
        payload=payload,
        frame_surface=frame_surface,
        login_url=login_url,
        login_attempted=login_attempted,
        login_succeeded=login_succeeded,
        redirected_to_login=redirected_to_login,
        login_network_idle_reached=login_network_idle_reached,
        target_network_idle_reached=target_network_idle_reached,
        marker_selector=marker_selector,
        selector_wait_status=selector_wait_status,
        requested_route=requested_route,
        final_route=final_route,
        route_mismatch=route_mismatch,
        stability=stability,
    )
    page_name = extract_page_from_url_fn(page_url)[1]
    element_candidates = build_surface_element_candidates_fn(page_name, surface_result)
    surface_result["element_candidates"] = element_candidates
    surface_result["confidence_summary"] = surface_confidence_summary_fn(
        {
            **surface_result,
            "element_candidates": element_candidates,
        }
    )
    surface_result["confidence"] = surface_result["confidence_summary"]["confidence"]
    surface_result["requires_review"] = surface_result["confidence_summary"]["requires_review"]
    surface_result["warnings"] = dedup_keep_order_fn(surface_result["warnings"] + surface_result["confidence_summary"]["warnings"])

    return normalize_page_surface_fn(
        surface_result,
        page=page_name,
        requested_url=page_url,
    )


# ---------------------------------------------------------------------------
# Surface candidate confidence index
# ---------------------------------------------------------------------------

def _surface_candidate_confidence_index(surface: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidate_index: dict[str, dict[str, Any]] = {}
    if not isinstance(surface, dict):
        return candidate_index
    candidates = _list_value(surface.get("element_candidates"))
    for item in candidates:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        candidate_index[key] = {
            "confidence": _clamp_confidence(item.get("confidence", 0)),
            "requires_review": bool(item.get("requires_review")),
            "warnings": [str(entry).strip() for entry in item.get("warnings", []) if str(entry).strip()]
            if isinstance(item.get("warnings"), list)
            else [],
            "label": str(item.get("label", "")).strip() or key,
        }
    confidence_summary = _dict_value(surface.get("confidence_summary"))
    low_confidence_items = _list_value(confidence_summary.get("low_confidence_items"))
    for item in low_confidence_items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not key or key in candidate_index:
            continue
        candidate_index[key] = {
            "confidence": _clamp_confidence(item.get("confidence", 0)),
            "requires_review": True,
            "warnings": [str(entry).strip() for entry in item.get("warnings", []) if str(entry).strip()]
            if isinstance(item.get("warnings"), list)
            else [],
            "label": str(item.get("label", "")).strip() or key,
        }
    return candidate_index


def surface_candidate_confidence_index(surface: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _surface_candidate_confidence_index(surface)


def inherit_test_point_confidence_from_surface(*, plan: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    candidate_index = _surface_candidate_confidence_index(surface)
    points = _list_value(plan.get("points"))
    if not points:
        return normalize_test_point_plan_model(plan, strict=False)

    for point in points:
        if not isinstance(point, dict):
            continue
        deps = [str(item).strip() for item in _list_value(point.get("involved_elements")) if str(item).strip()]
        if not deps:
            continue
        base_confidence = _clamp_confidence(point.get("confidence", 0))
        dependency_scores: list[float] = []
        dependency_warnings: list[str] = []
        missing_dependencies: list[str] = []
        low_confidence_dependencies: list[dict[str, Any]] = []
        matched_elements: list[str] = []

        for dep in _dedup_keep_order(deps):
            candidate = candidate_index.get(dep)
            if not isinstance(candidate, dict):
                missing_dependencies.append(dep)
                dependency_scores.append(0.55)
                continue
            matched_elements.append(dep)
            dep_confidence = _clamp_confidence(candidate.get("confidence", 0))
            dependency_scores.append(dep_confidence)
            if dep_confidence < 0.75 or bool(candidate.get("requires_review")):
                low_confidence_dependencies.append(
                    {
                        "key": dep,
                        "label": str(candidate.get("label", "")).strip() or dep,
                        "confidence": dep_confidence,
                        "warnings": [str(item).strip() for item in candidate.get("warnings", []) if str(item).strip()]
                        if isinstance(candidate.get("warnings"), list)
                        else [],
                    }
                )
            dependency_warnings.extend(
                [str(item).strip() for item in candidate.get("warnings", []) if str(item).strip()]
                if isinstance(candidate.get("warnings"), list)
                else []
            )

        if not dependency_scores:
            continue

        inherited_confidence = _clamp_confidence(min(dependency_scores))
        merged_confidence = _clamp_confidence(min(base_confidence, inherited_confidence))
        point["confidence"] = merged_confidence
        point["confidence_factors"] = {
            **(point.get("confidence_factors", {}) if isinstance(point.get("confidence_factors"), dict) else {}),
            "base_confidence": base_confidence,
            "dependency_confidence_min": inherited_confidence,
            "dependency_count": len(_dedup_keep_order(deps)),
            "missing_dependency_count": len(missing_dependencies),
        }
        dependency_evidence: list[str] = []
        if matched_elements:
            dependency_evidence.append(f"已匹配依赖元素：{', '.join(_dedup_keep_order(matched_elements))}")
        if low_confidence_dependencies:
            dependency_evidence.append(
                "低置信度依赖元素："
                + ", ".join(
                    f"{str(item.get('label', '')).strip() or str(item.get('key', '')).strip()}({int(_clamp_confidence(item.get('confidence', 0)) * 100)}%)"
                    for item in low_confidence_dependencies
                    if isinstance(item, dict)
                )
            )
        if missing_dependencies:
            dependency_evidence.append(f"页面分析未识别依赖元素：{', '.join(missing_dependencies)}")
        warning_rows = [str(item).strip() for item in point.get("warnings", []) if str(item).strip()] if isinstance(point.get("warnings"), list) else []
        if low_confidence_dependencies:
            warning_rows.append(
                "依赖元素置信度偏低："
                + ", ".join(
                    f"{str(item.get('label', '')).strip() or str(item.get('key', '')).strip()}({int(_clamp_confidence(item.get('confidence', 0)) * 100)}%)"
                    for item in low_confidence_dependencies
                    if isinstance(item, dict)
                )
            )
        if missing_dependencies:
            warning_rows.append(f"依赖元素未在页面分析模型中识别：{', '.join(missing_dependencies)}")
        warning_rows.extend(dependency_warnings)
        point["warnings"] = _dedup_keep_order(warning_rows)
        point["requires_review"] = bool(point.get("requires_review")) or merged_confidence < 0.75 or bool(point["warnings"])
        point["dependency_review"] = {
            "mode": "rule_first_surface",
            "propagated": True,
            "involved_elements": _dedup_keep_order(deps),
            "matched_elements": _dedup_keep_order(matched_elements),
            "low_confidence_dependencies": low_confidence_dependencies,
            "low_confidence_dependency_count": len(low_confidence_dependencies),
            "missing_dependencies": _dedup_keep_order(missing_dependencies),
            "missing_dependency_count": len(_dedup_keep_order(missing_dependencies)),
            "base_confidence": base_confidence,
            "inherited_confidence": inherited_confidence,
            "requires_review": bool(low_confidence_dependencies or missing_dependencies) or merged_confidence < 0.75,
            "evidence": dependency_evidence,
        }

    return normalize_test_point_plan_model(plan, strict=False)
