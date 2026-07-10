from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from app.services.page_element_code_policy import suggest_business_element_code
from app.services.page_object_source_semantics import SourceSemanticCatalog

logger = logging.getLogger(__name__)

__all__ = [
    "_ParsedLocator",
    "_ParsedStep",
    "_ParsedStepEncoder",
    "_AUTH_ROUTE_PATTERN",
    "_DYNAMIC_TEXT_FULL_PATTERN",
    "_DATE_TEXT_PATTERN",
    "_METRIC_LABEL_HINT_PATTERN",
    "_METRIC_TEXT_WITH_TRAILING_NUMBER_PATTERN",
    "_short_hash",
    "_role_name_suffix",
    "_derive_recorder_element_name",
    "_locator_key",
    "_looks_dynamic_text_locator",
    "_normalize_metric_text_locator",
    "_normalize_page_route",
    "_looks_auth_like",
    "_derive_page_url",
    "_derive_precondition_state",
    "_is_visual_only_locator",
    "_is_locator_blocked_for_ingest",
    "_locator_base_score",
    "_infer_locator_category",
    "_probe_availability",
    "_risk_adjusted_locator_quality",
    "_score_to_tier",
    "_recommended_action",
    "_build_element_candidates",
    "_locator_source",
    "_candidate_key_for_locator",
    "_group_key_for_locator",
    "_normalize_business_element_code",
    "_candidate_code_seed",
    "_business_type_guess",
    "_business_domain_guess",
    "_source_enhanced_candidate_semantics",
]

_AUTH_ROUTE_PATTERN = re.compile(r"(login|signin|sign-in|auth|oauth|sso|passport|登录|认证)", re.IGNORECASE)
_DYNAMIC_TEXT_FULL_PATTERN = re.compile(
    r"^[¥$€]?\s*[+-]?\d[\d,]*(?:\.\d+)?(?:%|万|亿|w|W|k|K)?$"
)
_DATE_TEXT_PATTERN = re.compile(
    r"^(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?|\d{1,2}:\d{2}(?::\d{2})?)$"
)
_METRIC_LABEL_HINT_PATTERN = re.compile(
    r"(本周|本月|今日|昨日|总额|总数|销量|销售|订单|会员|新增|统计|库存|金额|待处理|已完成|完成)",
    re.IGNORECASE,
)
_METRIC_TEXT_WITH_TRAILING_NUMBER_PATTERN = re.compile(
    r"^(?P<label>[A-Za-z一-鿿][A-Za-z0-9一-鿿()（）·\-/]{1,40}?)[：:\s]*"
    r"[¥$€]?\s*[+-]?\d[\d,]*(?:\.\d+)?(?:%|万|亿|w|W|k|K)?$"
)


@dataclass(frozen=True)
class _ParsedLocator:
    locator_type: str
    locator_value: str
    role: str


@dataclass(frozen=True)
class _ParsedStep:
    action: str
    locator_type: str
    locator_value: str
    role: str
    value: str
    raw_line: str


class _ParsedStepEncoder:
    """Minimal encoder to avoid json/serialization import in recorder_service."""
    pass


def _short_hash(*parts: str) -> str:
    payload = "|".join(str(part or "").strip() for part in parts if str(part or "").strip())
    if not payload:
        payload = uuid.uuid4().hex
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def _role_name_suffix(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized == "button":
        return "按钮"
    if normalized in {"textbox", "searchbox", "combobox", "spinbutton"}:
        return "输入框"
    if normalized == "link":
        return "链接"
    if normalized == "menuitem":
        return "菜单项"
    if normalized == "tab":
        return "标签页"
    if normalized == "checkbox":
        return "复选框"
    if normalized == "radio":
        return "单选框"
    if normalized == "switch":
        return "开关"
    return ""


def _derive_recorder_element_name(locator: _ParsedLocator) -> str:
    locator_type = str(locator.locator_type or "").strip().lower()
    locator_value = str(locator.locator_value or "").strip()
    role = str(locator.role or "").strip().lower()
    if locator_type == "role":
        suffix = _role_name_suffix(role)
        if locator_value and suffix:
            if locator_value.endswith(suffix):
                return locator_value[:120]
            return f"{locator_value}{suffix}"[:120]
        if locator_value:
            return locator_value[:120]
        return (suffix or "角色控件")[:120]
    if locator_type == "placeholder":
        if locator_value:
            return (locator_value if locator_value.endswith("输入框") else f"{locator_value}输入框")[:120]
        return "输入框"
    if locator_type == "text":
        return (locator_value or "文本元素")[:120]
    if locator_type == "data-testid":
        return (f"测试标识 {locator_value}" if locator_value else "测试标识")[:120]
    if locator_type == "id":
        return (f"id {locator_value}" if locator_value else "id定位元素")[:120]
    if locator_type == "name":
        return (f"name {locator_value}" if locator_value else "name定位元素")[:120]
    if locator_type == "css":
        return (f"CSS定位元素 {locator_value}" if locator_value else "CSS定位元素")[:120]
    if locator_type == "xpath":
        return (f"XPath定位元素 {locator_value}" if locator_value else "XPath定位元素")[:120]
    return (locator_value or "录制元素")[:120]


def _locator_key(locator_type: str, locator_value: str, role: str = "") -> tuple[str, str, str]:
    return (
        str(locator_type or "").strip().lower(),
        str(locator_value or "").strip(),
        str(role or "").strip().lower(),
    )


def _looks_dynamic_text_locator(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return True
    if _DYNAMIC_TEXT_FULL_PATTERN.fullmatch(text):
        return True
    if _DATE_TEXT_PATTERN.fullmatch(text):
        return True
    digit_count = len(re.findall(r"\d", text))
    if digit_count == 0:
        return False
    has_wording = bool(re.search(r"[A-Za-z一-鿿]", text))
    if digit_count >= 3 and not has_wording:
        return True
    if digit_count >= 2 and re.search(r"(同比|环比|本月|本周|今日|昨日|订单|销售|金额|总额|总数|kpi)", text, re.IGNORECASE):
        return True
    if digit_count >= 2 and len(text) >= 12:
        return True
    return False


def _normalize_metric_text_locator(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    if not re.search(r"\d", text):
        return text
    if not _METRIC_LABEL_HINT_PATTERN.search(text):
        return text
    match = _METRIC_TEXT_WITH_TRAILING_NUMBER_PATTERN.fullmatch(text)
    if not match:
        return text
    label = str(match.group("label") or "").strip("：:- ")
    if len(label) < 2:
        return text
    if not re.search(r"[A-Za-z一-鿿]", label):
        return text
    return label[:120]


def _normalize_page_route(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    path = unquote(str(parsed.path or "").strip())
    fragment = unquote(str(parsed.fragment or "").strip())
    query = str(parsed.query or "").strip()
    route = path
    if fragment:
        if fragment.startswith("/"):
            route = fragment
        elif not route or route == "/":
            route = "/" + fragment
        else:
            route = route + "#" + fragment
    if query:
        route = (route or "") + ("?" + query)
    return route[:256]


def _looks_auth_like(value: str) -> bool:
    return bool(_AUTH_ROUTE_PATTERN.search(str(value or "").strip()))


def _derive_page_url(entry_url: str, *, page_code: str, page_name: str) -> str:
    route = _normalize_page_route(entry_url)
    if not route:
        return ""
    if _looks_auth_like(route) and not _looks_auth_like(page_code) and not _looks_auth_like(page_name):
        return ""
    return route


def _derive_precondition_state(entry_url: str, *, page_code: str, page_name: str) -> str:
    route = _normalize_page_route(entry_url)
    if route and _looks_auth_like(route) and not _looks_auth_like(page_code) and not _looks_auth_like(page_name):
        return "依赖登录页完成认证后进入"
    return ""


def _is_visual_only_locator(locator: _ParsedLocator) -> bool:
    if locator.locator_type not in {"css", "xpath"}:
        return False
    value = str(locator.locator_value or "").strip().lower()
    if not value:
        return True
    return bool(re.search(r"(^|[ >+~])(svg|path|canvas|i)([.#:\[]|$)", value))


def _is_locator_blocked_for_ingest(locator: _ParsedLocator) -> tuple[bool, str]:
    if locator.locator_type == "text" and _looks_dynamic_text_locator(locator.locator_value):
        return True, "dynamic_text"
    if _is_visual_only_locator(locator):
        return True, "visual_node"
    return False, ""


def _locator_base_score(locator: _ParsedLocator) -> float:
    return {
        "data-testid": 0.96,
        "role": 0.90,
        "placeholder": 0.86,
        "id": 0.80,
        "name": 0.75,
        "css": 0.68,
        "text": 0.60,
        "xpath": 0.52,
    }.get(locator.locator_type, 0.50)


def _infer_locator_category(locator: _ParsedLocator) -> str:
    if locator.locator_type == "role":
        role = str(locator.role or "").strip().lower()
        if role in {"textbox", "searchbox", "combobox", "spinbutton"}:
            return "input"
        if role in {"button", "link", "menuitem", "tab", "checkbox", "radio", "switch"}:
            return "action"
    if locator.locator_type == "placeholder":
        return "input"
    if locator.locator_type == "text":
        return "assertion"
    value = str(locator.locator_value or "").strip().lower()
    if re.search(r"(menu|nav|header|footer|panel|container|card|table|grid|chart|sidebar)", value):
        return "container"
    return "action"


def _probe_availability(
    entry_url: str,
    locators: list[_ParsedLocator],
    *,
    timeout_ms: int,
) -> tuple[dict[tuple[str, str, str], dict[str, object]], str]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}, "playwright_unavailable"

    url = str(entry_url or "").strip()
    if not url:
        return {}, "missing_url"

    def _css_id_selector(raw_value: str) -> str:
        value = str(raw_value or "").strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value):
            return "#" + value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'[id="{escaped}"]'

    def _build_locator(page, locator: _ParsedLocator):
        locator_type = str(locator.locator_type or "").strip()
        value = str(locator.locator_value or "").strip()
        role = str(locator.role or "").strip()
        if not locator_type or not value:
            return None
        if locator_type == "data-testid":
            return page.get_by_test_id(value)
        if locator_type == "placeholder":
            return page.get_by_placeholder(value)
        if locator_type == "role":
            if role:
                return page.get_by_role(role, name=value)
            return None
        if locator_type == "text":
            return page.get_by_text(value)
        if locator_type == "css":
            return page.locator(value)
        if locator_type == "id":
            return page.locator(_css_id_selector(value))
        if locator_type == "xpath":
            return page.locator(f"xpath={value}")
        if locator_type == "name":
            safe = value.replace("\\", "\\\\").replace('"', '\\"')
            return page.locator(f'[name="{safe}"]')
        return None

    results: dict[tuple[str, str, str], dict[str, object]] = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(int(timeout_ms))
            try:
                page.goto(url, wait_until="domcontentloaded")
            except (PlaywrightTimeoutError, PlaywrightError):
                context.close()
                browser.close()
                return {}, "goto_failed"

            for locator in locators:
                key = _locator_key(locator.locator_type, locator.locator_value, locator.role)
                output = {
                    "status": "unverified",
                    "match_count": None,
                    "visible": None,
                    "interactable": None,
                }
                pw_locator = _build_locator(page, locator)
                if pw_locator is None:
                    output["status"] = "unsupported_locator"
                    results[key] = output
                    continue
                try:
                    count = int(pw_locator.count())
                except (PlaywrightTimeoutError, PlaywrightError):
                    output["status"] = "probe_error"
                    results[key] = output
                    continue
                output["match_count"] = count
                if count <= 0:
                    output["status"] = "not_found"
                    results[key] = output
                    continue
                if count > 1:
                    output["status"] = "ambiguous"
                    results[key] = output
                    continue
                first = pw_locator.first
                try:
                    output["visible"] = bool(first.is_visible())
                except (PlaywrightTimeoutError, PlaywrightError):
                    output["visible"] = None
                category = _infer_locator_category(locator)
                if category in {"action", "input"}:
                    try:
                        output["interactable"] = bool(first.is_enabled())
                    except (PlaywrightTimeoutError, PlaywrightError):
                        output["interactable"] = None
                output["status"] = "ok"
                results[key] = output

            context.close()
            browser.close()
    except Exception:
        return {}, "probe_error"
    return results, "ok"


def _risk_adjusted_locator_quality(
    locator: _ParsedLocator,
    *,
    step_hit_count: int,
    probe: dict[str, object] | None = None,
) -> tuple[float, list[str]]:
    score = _locator_base_score(locator) + min(0.08, max(0, int(step_hit_count)) * 0.02)
    risks: list[str] = []
    value = str(locator.locator_value or "").strip()
    lowered = value.lower()

    blocked, block_reason = _is_locator_blocked_for_ingest(locator)
    if blocked:
        risks.append(block_reason)
        score = min(score, 0.20)

    if locator.locator_type == "text":
        if len(value) <= 2:
            risks.append("short_text")
            score -= 0.06
        if value in {"首页", "退出", "删除", "保存", "提交", "确定", "取消", "返回"}:
            risks.append("common_text")
            score -= 0.08
        if len(value) >= 18:
            risks.append("long_text")
            score -= 0.10
    if locator.locator_type == "css":
        if "nth-child" in lowered or "nth-of-type" in lowered:
            risks.append("index_selector")
            score -= 0.14
        if re.fullmatch(r"(div|span|p|a|li|ul|i|svg|path|canvas)", lowered):
            risks.append("generic_selector")
            score -= 0.18
    if locator.locator_type == "xpath":
        risks.append("xpath_maintenance")
        score -= 0.14
    if locator.locator_type == "id" and re.search(r"\d{3,}", value):
        risks.append("id_may_be_dynamic")
        score -= 0.10
    if step_hit_count <= 0:
        risks.append("not_used_in_steps")
        score -= 0.08
    probe_status = str((probe or {}).get("status") or "").strip()
    probe_visible = (probe or {}).get("visible")
    probe_interactable = (probe or {}).get("interactable")
    if probe_status == "not_found":
        risks.append("probe_not_found")
        score -= 0.22
    elif probe_status == "ambiguous":
        risks.append("probe_ambiguous")
        score -= 0.18
    elif probe_status == "probe_error":
        risks.append("probe_error")
        score -= 0.06
    elif probe_status == "ok":
        if probe_visible is False:
            risks.append("probe_not_visible")
            score -= 0.10
        if _infer_locator_category(locator) in {"action", "input"} and probe_interactable is False:
            risks.append("probe_not_interactable")
            score -= 0.12
    elif probe_status in {"probe_error", "unsupported_locator", "playwright_unavailable", "goto_failed", "missing_url"}:
        risks.append("probe_unverified")

    score = max(0.05, min(0.99, score))
    dedup_risks = list(dict.fromkeys(risks))
    return score, dedup_risks


def _score_to_tier(score: float) -> tuple[str, str]:
    if score >= 0.85:
        return "A", "high"
    if score >= 0.72:
        return "B", "high"
    if score >= 0.58:
        return "C", "medium"
    return "D", "low"


def _recommended_action(score: float, *, blocked: bool, probe_status: str = "") -> str:
    if blocked:
        return "skip"
    if probe_status in {"not_found", "ambiguous"}:
        return "skip"
    if score >= 0.72:
        return "ingest"
    if score >= 0.58:
        return "review"
    return "skip"


def _build_element_candidates(
    locators: list[_ParsedLocator],
    *,
    step_hit_count_by_key: dict[tuple[str, str, str], int],
    element_code_by_key: dict[tuple[str, str, str], str],
    ingested_keys: set[tuple[str, str, str]],
    probe_by_key: dict[tuple[str, str, str], dict[str, object]] | None = None,
    probe_status: str = "not_requested",
) -> list[dict[str, object]]:
    probe_by_key = probe_by_key or {}
    items: list[dict[str, object]] = []
    for index, locator in enumerate(locators, start=1):
        key = _locator_key(locator.locator_type, locator.locator_value, locator.role)
        step_hit_count = int(step_hit_count_by_key.get(key, 0))
        blocked, block_reason = _is_locator_blocked_for_ingest(locator)
        probe = probe_by_key.get(key, {})
        score, risks = _risk_adjusted_locator_quality(locator, step_hit_count=step_hit_count, probe=probe)
        tier, confidence = _score_to_tier(score)
        action = _recommended_action(score, blocked=blocked, probe_status=str(probe.get("status") or ""))
        element_code = str(element_code_by_key.get(key) or "")
        items.append(
            {
                "index": index,
                "locator_type": locator.locator_type,
                "locator_value": locator.locator_value,
                "role": locator.role,
                "category": _infer_locator_category(locator),
                "step_hit_count": step_hit_count,
                "score": round(score, 2),
                "quality_tier": tier,
                "confidence": confidence,
                "ingestible": not blocked and score >= 0.58,
                "recommended_action": action,
                "ingest_block_reason": block_reason,
                "risk_tags": risks,
                "element_code": element_code,
                "ingested": key in ingested_keys,
                "probe": {
                    "overall_status": probe_status,
                    "status": str(probe.get("status") or ""),
                    "match_count": probe.get("match_count"),
                    "visible": probe.get("visible"),
                    "interactable": probe.get("interactable"),
                },
            }
        )
    return items


def _locator_source(locator_type: str) -> str:
    normalized = str(locator_type or "").strip().lower()
    if normalized == "data-testid":
        return "testid"
    if normalized == "data-qa":
        return "qa"
    if normalized == "role":
        return "role_name"
    if normalized in {"placeholder", "id", "name", "css", "xpath"}:
        return normalized
    return normalized or "manual"


def _candidate_key_for_locator(locator: _ParsedLocator) -> str:
    return f"cand-{_short_hash(locator.locator_type, locator.role, locator.locator_value)}"


def _group_key_for_locator(locator: _ParsedLocator) -> str:
    locator_type = str(locator.locator_type or "").strip().lower()
    locator_value = str(locator.locator_value or "").strip()
    role = str(locator.role or "").strip().lower()
    if locator_type == "data-testid" and locator_value:
        return f"testid:{_short_hash(locator_value)}"
    if locator_type == "data-qa" and locator_value:
        return f"qa:{_short_hash(locator_value)}"
    if locator_type == "role" and role and locator_value:
        return f"role_name:{role}:{_short_hash(locator_value)}"
    if locator_type == "placeholder" and locator_value:
        return f"placeholder:{_short_hash(locator_value)}"
    if locator_type == "id" and locator_value:
        return f"id:{_short_hash(locator_value)}"
    if locator_type == "name" and locator_value:
        return f"name:{_short_hash(locator_value)}"
    return f"stable:{_short_hash(locator_type, role, locator_value)}"


def _normalize_business_element_code(value: str, *, locator: _ParsedLocator) -> str:
    raw = str(value or "").strip()
    semantic_code = suggest_business_element_code(
        raw,
        business_type=_business_type_guess(locator),
    )
    if semantic_code:
        return semantic_code
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", raw.lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    banned_parts = {"css", "xpath", "locator", "path", "nth", "index"}
    parts = [part for part in normalized.split("_") if part and part not in banned_parts]
    normalized = "_".join(parts)
    if len(normalized) < 3:
        return ""
    return normalized[:80].strip("_")


def _candidate_code_seed(locator: _ParsedLocator) -> str:
    locator_type = str(locator.locator_type or "").strip().lower()
    locator_value = str(locator.locator_value or "").strip()
    if locator_type in {"data-testid", "data-qa", "id", "name", "role", "placeholder", "text"}:
        return locator_value
    return ""


def _business_type_guess(locator: _ParsedLocator) -> str:
    locator_type = str(locator.locator_type or "").strip().lower()
    locator_value = str(locator.locator_value or "").strip().lower()
    role = str(locator.role or "").strip().lower()
    if re.search(r"(password|pwd|密码).*(show|hide|visible|toggle|显示|隐藏|明文)|"
                 r"(show|hide|visible|toggle|显示|隐藏|明文).*(password|pwd|密码)", locator_value):
        return "password_toggle"
    if role in {"textbox", "searchbox", "combobox", "spinbutton"} or locator_type == "placeholder":
        return "input"
    if role == "button":
        return "button"
    if role == "link":
        return "link"
    if role == "menuitem":
        return "menu"
    if role == "tab":
        return "tab"
    if role == "checkbox":
        return "checkbox"
    if role == "radio":
        return "radio"
    if role == "switch":
        return "switch"
    if locator_type == "text" and _METRIC_LABEL_HINT_PATTERN.search(locator_value):
        return "metric_label"
    if _infer_locator_category(locator) == "container":
        return "container"
    return "button" if _infer_locator_category(locator) == "action" else "container"


def _business_domain_guess(page_code: str, locator: _ParsedLocator) -> str:
    text = f"{page_code} {locator.locator_value}".lower()
    if re.search(r"(login|signin|auth|password|username|账号|密码|登录)", text):
        return "auth"
    if re.search(r"(menu|nav|sidebar|breadcrumb|导航|菜单)", text):
        return "navigation"
    if re.search(r"(search|query|filter|搜索|查询|筛选)", text):
        return "search"
    if re.search(r"(table|grid|list|表格|列表)", text):
        return "table"
    if re.search(r"(form|input|submit|save|表单|保存|提交)", text):
        return "form"
    if re.search(r"(dashboard|home|chart|metric|首页|统计|看板)", text):
        return "dashboard"
    return "common"


def _source_enhanced_candidate_semantics(
    *,
    locator: _ParsedLocator,
    page_code: str,
    catalog: SourceSemanticCatalog,
) -> tuple[str, str, str, str]:
    hint = catalog.match(
        locator_type=str(locator.locator_type or ""),
        locator_value=str(locator.locator_value or ""),
        role=str(locator.role or ""),
    )
    if hint is None and _is_visual_only_locator(locator):
        value = str(locator.locator_value or "").strip().lower()
        if re.search(r"(password|pwd|show|hide|visible|toggle|eye|suffix|密码|显示|隐藏|明文)", value):
            hint = catalog.find_by_business_type("password_toggle")
    if hint is None:
        business_type = _business_type_guess(locator)
        return (
            _candidate_code_seed(locator),
            _derive_recorder_element_name(locator),
            business_type,
            _business_domain_guess(page_code, locator),
        )
    business_type = str(hint.business_type or "").strip() or _business_type_guess(locator)
    business_domain = str(hint.business_domain or "").strip() or _business_domain_guess(page_code, locator)
    return (
        str(hint.code_seed or "").strip() or _candidate_code_seed(locator),
        str(hint.name or "").strip() or _derive_recorder_element_name(locator),
        business_type,
        business_domain,
    )
