from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException, status
from shared_backend.case_ids import normalize_client_code
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.page_object import PageObjectRecorderSession
from app.schemas.page_object import PageElementCreate, PageObjectCreate, PageObjectRefCreate
from app.schemas.page_object_recorder import (
    RecorderSessionCreateCasePayload,
    RecorderSessionCreate,
    RecorderSessionHeartbeatPayload,
    RecorderSessionStopPayload,
)
from app.schemas.test_case import TestCaseCreate
from app.services import page_object_service, test_case_service, test_project_service

SESSION_STATUS_VALUES = {"active", "stopped", "failed"}
_PROCESS_REGISTRY: dict[int, subprocess.Popen[bytes]] = {}
_RECORDER_ROOT = Path(__file__).resolve().parents[4] / "artifacts" / "page-recorder"
_IDENTIFIER_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")
_AUTH_ROUTE_PATTERN = re.compile(r"(login|signin|sign-in|auth|oauth|sso|passport|登录|认证)", re.IGNORECASE)
_DYNAMIC_TEXT_FULL_PATTERN = re.compile(
    r"^[¥$€]?\s*[+-]?\d[\d,]*(?:\.\d+)?(?:%|万|亿|w|W|k|K)?$"
)
_DATE_TEXT_PATTERN = re.compile(
    r"^(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?|\d{1,2}:\d{2}(?::\d{2})?)$"
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


def _normalize_project_code(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "").strip()).lower()
    if len(normalized) < 2 or len(normalized) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_code must be 2-20 letters or digits",
        )
    return normalized


def _normalize_page_code(value: str) -> str:
    normalized = _IDENTIFIER_PATTERN.sub("-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < 2 or len(normalized) > 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_code must be 2-40 chars and use letters/digits/_/-",
        )
    return normalized


def _normalize_session_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id cannot be empty")
    return normalized


def _normalize_element_code(value: str) -> str:
    normalized = _IDENTIFIER_PATTERN.sub("-", str(value or "").strip()).strip("-").lower()
    if len(normalized) < 2:
        normalized = f"element-{uuid.uuid4().hex[:8]}"
    return normalized[:80]


def _serialize_session(item: PageObjectRecorderSession) -> dict[str, object]:
    recorded_steps = _load_recorded_steps(Path(item.script_path))
    if not recorded_steps:
        recorded_steps = _serialize_recorded_steps(_parse_codegen_steps(Path(item.script_path)))
    return {
        "id": item.id,
        "session_id": item.session_id,
        "project_code": item.project_code,
        "client": item.client,
        "page_code": item.page_code,
        "page_name": item.page_name,
        "url": item.url,
        "status": item.status,
        "process_pid": item.process_pid,
        "script_path": item.script_path,
        "started_by": item.started_by,
        "error_message": item.error_message,
        "started_at": item.started_at,
        "heartbeat_at": item.heartbeat_at,
        "stopped_at": item.stopped_at,
        "recorded_step_count": len(recorded_steps),
        "recorded_steps": recorded_steps,
    }


def _get_session_or_404(db: Session, session_id: str) -> PageObjectRecorderSession:
    normalized_session_id = _normalize_session_id(session_id)
    item = db.execute(
        select(PageObjectRecorderSession).where(PageObjectRecorderSession.session_id == normalized_session_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"recorder session not found: {session_id}")
    return item


def _resolve_playwright_command() -> list[str]:
    if importlib.util.find_spec("playwright") is not None:
        return [sys.executable, "-m", "playwright"]
    playwright_bin = shutil.which("playwright")
    if playwright_bin:
        return [playwright_bin]
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "playwright runtime not available in current web-ui-service environment; "
            f"install it with '{sys.executable} -m pip install -r requirements-dev.txt' "
            f"and '{sys.executable} -m playwright install'"
        ),
    )


def _start_codegen_process(url: str, script_path: Path) -> int:
    playwright_command = _resolve_playwright_command()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(  # noqa: S603
        [
            *playwright_command,
            "codegen",
            str(url),
            "--target",
            "python",
            "--output",
            str(script_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _PROCESS_REGISTRY[int(process.pid)] = process
    return int(process.pid)


def _stop_codegen_process(process_pid: int | None) -> None:
    if process_pid is None or process_pid <= 0:
        return
    process = _PROCESS_REGISTRY.pop(process_pid, None)
    if process is not None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        return
    try:
        os.kill(process_pid, signal.SIGTERM)
    except OSError:
        return


def _recorded_steps_path(script_path: Path) -> Path:
    return script_path.with_suffix(".steps.json")


def _locator_key(locator_type: str, locator_value: str, role: str = "") -> tuple[str, str, str]:
    return (str(locator_type or "").strip(), str(locator_value or "").strip(), str(role or "").strip())


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
    has_wording = bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))
    if digit_count >= 3 and not has_wording:
        return True
    if digit_count >= 2 and re.search(r"(同比|环比|本月|本周|今日|昨日|订单|销售|金额|总额|总数|kpi)", text, re.IGNORECASE):
        return True
    if digit_count >= 2 and len(text) >= 12:
        return True
    return False


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


def _parse_locator_from_codegen_line(stripped: str) -> _ParsedLocator | None:
    locator_type = ""
    locator_value = ""
    role = ""
    match = re.search(r'get_by_role\("([^"]+)"\s*,\s*name="([^"]+)"\)', stripped)
    if match:
        locator_type = "role"
        role = str(match.group(1)).strip()
        locator_value = str(match.group(2)).strip()
    if not locator_type:
        match = re.search(r'get_by_test_id\("([^"]+)"\)', stripped)
        if match:
            locator_type = "data-testid"
            locator_value = str(match.group(1)).strip()
    if not locator_type:
        match = re.search(r'get_by_placeholder\("([^"]+)"\)', stripped)
        if match:
            locator_type = "placeholder"
            locator_value = str(match.group(1)).strip()
    if not locator_type:
        match = re.search(r'get_by_text\("([^"]+)"\)', stripped)
        if match:
            locator_type = "text"
            locator_value = str(match.group(1)).strip()
    if not locator_type:
        match = re.search(r'locator\("([^"]+)"\)', stripped)
        if match:
            raw_locator = str(match.group(1)).strip()
            if raw_locator.startswith("xpath="):
                locator_type = "xpath"
                locator_value = raw_locator.removeprefix("xpath=").strip()
            else:
                locator_type = "css"
                locator_value = raw_locator
                if raw_locator.startswith("#"):
                    locator_type = "id"
                    locator_value = raw_locator.removeprefix("#").strip()
    if not locator_type or not locator_value:
        return None
    return _ParsedLocator(locator_type=locator_type, locator_value=locator_value, role=role)


def _parse_action_from_codegen_line(stripped: str) -> tuple[str, str]:
    if match := re.search(r'\.goto\("(.*?)"\)', stripped):
        return ("navigate", str(match.group(1)).strip())
    if ".dblclick()" in stripped:
        return ("dblclick", "")
    if ".uncheck()" in stripped:
        return ("uncheck", "")
    if ".check()" in stripped:
        return ("check", "")
    if ".click()" in stripped:
        return ("click", "")
    if ".hover()" in stripped:
        return ("hover", "")
    if match := re.search(r'\.fill\("(.*?)"\)', stripped):
        return ("fill", str(match.group(1)))
    if match := re.search(r'\.press\("(.*?)"\)', stripped):
        return ("press", str(match.group(1)))
    if match := re.search(r'\.select_option\("(.*?)"\)', stripped):
        return ("select_option", str(match.group(1)))
    return ("", "")


def _parse_codegen_script(script_path: Path, *, include_dynamic_text: bool = False) -> list[_ParsedLocator]:
    if not script_path.exists():
        return []
    content = script_path.read_text(encoding="utf-8", errors="ignore")
    parsed: list[_ParsedLocator] = []
    seen: set[tuple[str, str, str]] = set()
    for line in content.splitlines():
        stripped = line.strip()
        locator = _parse_locator_from_codegen_line(stripped)
        if locator is None:
            continue
        if not include_dynamic_text and locator.locator_type == "text" and _looks_dynamic_text_locator(locator.locator_value):
            continue
        key = _locator_key(locator.locator_type, locator.locator_value, locator.role)
        if key in seen:
            continue
        seen.add(key)
        parsed.append(locator)
    return parsed


def _parse_codegen_steps(script_path: Path) -> list[_ParsedStep]:
    if not script_path.exists():
        return []
    content = script_path.read_text(encoding="utf-8", errors="ignore")
    steps: list[_ParsedStep] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        action, value = _parse_action_from_codegen_line(stripped)
        if not action:
            continue
        if action == "press" and str(value).strip().lower() in {"capslock", "numlock", "scrolllock"}:
            continue
        locator = _parse_locator_from_codegen_line(stripped)
        if action == "navigate":
            steps.append(
                _ParsedStep(
                    action=action,
                    locator_type="url",
                    locator_value=value,
                    role="",
                    value=value,
                    raw_line=stripped,
                )
            )
            continue
        if locator is None:
            continue
        steps.append(
            _ParsedStep(
                action=action,
                locator_type=locator.locator_type,
                locator_value=locator.locator_value,
                role=locator.role,
                value=value,
                raw_line=stripped,
            )
        )
    return _dedupe_recorded_steps(steps)


def _dedupe_recorded_steps(steps: list[_ParsedStep]) -> list[_ParsedStep]:
    if not steps:
        return []
    normalized: list[_ParsedStep] = []
    for step in steps:
        if normalized:
            previous = normalized[-1]
            if (
                step.action == "click"
                and previous.action == "click"
                and _locator_key(step.locator_type, step.locator_value, step.role)
                == _locator_key(previous.locator_type, previous.locator_value, previous.role)
            ):
                continue
        normalized.append(step)
    return normalized


def _serialize_recorded_steps(
    steps: list[_ParsedStep],
    *,
    element_code_by_key: dict[tuple[str, str, str], str] | None = None,
) -> list[dict[str, object]]:
    element_code_by_key = element_code_by_key or {}
    items: list[dict[str, object]] = []
    for index, step in enumerate(steps, start=1):
        items.append(
            {
                "index": index,
                "action": step.action,
                "locator_type": step.locator_type,
                "locator_value": step.locator_value,
                "role": step.role,
                "value": step.value,
                "element_code": element_code_by_key.get(
                    _locator_key(step.locator_type, step.locator_value, step.role),
                    "",
                ),
                "raw_line": step.raw_line,
            }
        )
    return items


def _save_recorded_steps(script_path: Path, steps: list[dict[str, object]]) -> None:
    artifact_path = _recorded_steps_path(script_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(steps, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_recorded_steps(script_path: Path) -> list[dict[str, object]]:
    artifact_path = _recorded_steps_path(script_path)
    if not artifact_path.exists():
        return []
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    items: list[dict[str, object]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "index": int(item.get("index") or index),
                "action": str(item.get("action") or "").strip(),
                "locator_type": str(item.get("locator_type") or "").strip(),
                "locator_value": str(item.get("locator_value") or "").strip(),
                "role": str(item.get("role") or "").strip(),
                "value": str(item.get("value") or "").strip(),
                "element_code": str(item.get("element_code") or "").strip(),
                "raw_line": str(item.get("raw_line") or "").strip(),
            }
        )
    return items


def _ensure_page_object(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
    page_name: str,
    entry_url: str,
    started_by: str,
) -> tuple[dict[str, object], str]:
    try:
        item = page_object_service.get_page_object(
            db,
            page_code=page_code,
            project_code=project_code,
            client=client,
        )
        return item, "existing"
    except HTTPException as exc:
        if int(exc.status_code) != status.HTTP_404_NOT_FOUND:
            raise
        item = page_object_service.create_page_object(
            db,
            PageObjectCreate(
                project_code=project_code,
                client=client,
                page_code=page_code,
                page_name=page_name,
                page_url=_derive_page_url(entry_url, page_code=page_code, page_name=page_name),
                precondition_state=_derive_precondition_state(entry_url, page_code=page_code, page_name=page_name),
                status="draft",
                created_by=started_by,
            ),
        )
        return item, "created"


def _load_page_object_snapshot(
    db: Session,
    *,
    project_code: str,
    client: str,
    page_code: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        page_item = page_object_service.get_page_object(
            db,
            page_code=page_code,
            project_code=project_code,
            client=client,
        )
    except HTTPException as exc:
        if int(exc.status_code) == status.HTTP_404_NOT_FOUND:
            return {}, []
        raise
    elements = page_object_service.list_page_elements(
        db,
        page_code=page_code,
        project_code=project_code,
        client=client,
    )
    return page_item, list(elements)


def create_recorder_session(db: Session, payload: RecorderSessionCreate) -> dict[str, object]:
    project_code = _normalize_project_code(payload.project_code)
    test_project_service.ensure_project_active_for_write(db, project_code)
    client = normalize_client_code(payload.client)
    page_code = _normalize_page_code(payload.page_code)
    page_name = str(payload.page_name or "").strip()
    started_by = str(payload.started_by or "").strip() or "system"
    if not page_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page_name cannot be empty")
    session_id = f"rec_{uuid.uuid4().hex[:16]}"
    script_path = (_RECORDER_ROOT / f"{session_id}.codegen.py").resolve()
    process_pid = _start_codegen_process(str(payload.url), script_path)
    item = PageObjectRecorderSession(
        session_id=session_id,
        project_code=project_code,
        client=client,
        page_code=page_code,
        page_name=page_name,
        url=str(payload.url).strip(),
        status="active",
        process_pid=process_pid,
        script_path=str(script_path),
        started_by=started_by,
        heartbeat_at=datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


def heartbeat_recorder_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionHeartbeatPayload,
) -> dict[str, object]:
    item = _get_session_or_404(db, session_id)
    if item.status != "active":
        return _serialize_session(item)
    item.heartbeat_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


def get_recorder_session(db: Session, *, session_id: str) -> dict[str, object]:
    item = _get_session_or_404(db, session_id)
    return _serialize_session(item)


def cleanup_orphan_recorder_artifacts(db: Session) -> dict[str, object]:
    _RECORDER_ROOT.mkdir(parents=True, exist_ok=True)
    active_session_ids = {
        str(value or "").strip()
        for value in db.execute(select(PageObjectRecorderSession.session_id)).scalars().all()
        if str(value or "").strip()
    }
    orphan_files: list[str] = []
    cleaned_files: list[str] = []
    scanned_files = 0

    for artifact_path in sorted(_RECORDER_ROOT.glob("rec_*.codegen.py")):
        scanned_files += 1
        session_id = str(artifact_path.name).removesuffix(".codegen.py")
        if not session_id:
            continue
        if session_id in active_session_ids:
            continue
        orphan_files.append(str(artifact_path))
        steps_path = _recorded_steps_path(artifact_path)
        if artifact_path.exists():
            artifact_path.unlink()
            cleaned_files.append(str(artifact_path))
        if steps_path.exists():
            steps_path.unlink()
            cleaned_files.append(str(steps_path))

    for steps_path in sorted(_RECORDER_ROOT.glob("rec_*.codegen.steps.json")):
        scanned_files += 1
        session_id = str(steps_path.name).removesuffix(".codegen.steps.json")
        if not session_id:
            continue
        if session_id in active_session_ids:
            continue
        if str(steps_path) not in orphan_files:
            orphan_files.append(str(steps_path))
        if steps_path.exists():
            steps_path.unlink()
            cleaned_files.append(str(steps_path))

    return {
        "scanned_file_count": scanned_files,
        "orphan_file_count": len(orphan_files),
        "cleaned_file_count": len(cleaned_files),
        "cleaned_files": cleaned_files,
    }


def _normalize_step_value(value: object) -> str:
    return str(value or "").strip()


def _build_case_steps_from_recorded_steps(recorded_steps: list[dict[str, object]]) -> list[dict[str, object]]:
    case_steps: list[dict[str, object]] = []
    for index, step in enumerate(recorded_steps, start=1):
        action = _normalize_step_value(step.get("action"))
        locator_type = _normalize_step_value(step.get("locator_type"))
        locator_value = _normalize_step_value(step.get("locator_value"))
        role = _normalize_step_value(step.get("role"))
        element_code = _normalize_step_value(step.get("element_code"))
        value = _normalize_step_value(step.get("value"))
        if not action:
            continue
        if element_code:
            target = f"element:{element_code}"
        elif locator_type and locator_value:
            target = f"{locator_type}:{locator_value}"
        elif locator_value:
            target = locator_value
        else:
            target = f"step-{index}"
        locator_hint = locator_type
        if role:
            locator_hint = f"{locator_type}({role})" if locator_type else role
        description = f"录制步骤{index} {action} {target}"
        if locator_hint and locator_value:
            description += f" [{locator_hint}={locator_value}]"
        case_steps.append(
            {
                "action": action,
                "target": target,
                "value": value,
                "description": description,
            }
        )
    return case_steps


def _build_case_script_from_recorded_steps(
    session: PageObjectRecorderSession,
    recorded_steps: list[dict[str, object]],
) -> str:
    fn_name = re.sub(r"[^a-zA-Z0-9_]+", "_", f"test_{session.page_code}_{session.session_id}").strip("_").lower()
    if not fn_name:
        fn_name = f"test_recorder_{uuid.uuid4().hex[:8]}"
    lines = [
        f"def {fn_name}(page):",
        f"    # Generated from recorder session {session.session_id}",
    ]
    normalized_url = str(session.url or "").strip()
    if normalized_url:
        lines.append(f"    page.goto({json.dumps(normalized_url, ensure_ascii=False)})")
    for index, step in enumerate(recorded_steps, start=1):
        raw_line = _normalize_step_value(step.get("raw_line"))
        if raw_line:
            lines.append(f"    # Step {index}: {raw_line}")
    lines.append("    assert True")
    return "\n".join(lines) + "\n"


def _dedupe_text_items(values: list[str]) -> list[str]:
    output: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in output:
            output.append(value)
    return output


def _link_case_refs_for_recorded_elements(
    db: Session,
    *,
    session: PageObjectRecorderSession,
    case_id: str,
    recorded_steps: list[dict[str, object]],
    created_by: str,
) -> dict[str, int]:
    element_codes = _dedupe_text_items([
        _normalize_step_value(step.get("element_code"))
        for step in recorded_steps
    ])
    linked_count = 0
    skipped_count = 0
    for element_code in element_codes:
        try:
            page_object_service.create_page_object_ref(
                db,
                page_code=session.page_code,
                element_code=element_code,
                project_code=session.project_code,
                client=session.client,
                payload=PageObjectRefCreate(
                    reference_type="test_case",
                    reference_key=case_id,
                    source="recorder",
                    created_by=created_by,
                ),
            )
            linked_count += 1
        except HTTPException as exc:
            if int(exc.status_code) in {status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}:
                skipped_count += 1
                continue
            raise
    return {
        "linked_ref_count": linked_count,
        "skipped_ref_count": skipped_count,
    }


def create_test_case_draft_from_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionCreateCasePayload,
) -> dict[str, object]:
    session_item = _get_session_or_404(db, session_id)
    if str(session_item.status or "").strip().lower() == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="session is active; stop recorder session before generating test case draft",
        )
    script_path = Path(session_item.script_path)
    recorded_steps = _load_recorded_steps(script_path)
    if not recorded_steps:
        parsed_steps = _parse_codegen_steps(script_path)
        recorded_steps = _serialize_recorded_steps(parsed_steps)
    if not recorded_steps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no recorded steps found for this recorder session",
        )

    page_object_item, page_object_action = _ensure_page_object(
        db,
        project_code=session_item.project_code,
        client=session_item.client,
        page_code=session_item.page_code,
        page_name=session_item.page_name,
        entry_url=session_item.url,
        started_by=str(payload.creator or "").strip() or session_item.started_by or "system",
    )
    case_steps = _build_case_steps_from_recorded_steps(recorded_steps)
    if not case_steps:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="recorded steps cannot be converted to test case steps",
        )
    creator = str(payload.creator or "").strip() or session_item.started_by or "system"
    page_name = str(page_object_item.get("page_name") or session_item.page_name or session_item.page_code).strip()
    case_name = str(payload.name or "").strip() or f"{page_name} 录制回放草稿"
    product_line = str(payload.product_line or "").strip() or page_name or session_item.page_code
    module = str(payload.module or "").strip() or "录制回放"
    tags = _dedupe_text_items(
        [*list(payload.tags or []), "recorder", f"page:{session_item.page_code}", f"session:{session_item.session_id}"]
    )
    case = test_case_service.create_test_case(
        db,
        TestCaseCreate(
            mode="manual",
            project_code=session_item.project_code,
            client=session_item.client,
            page_code=session_item.page_code,
            name=case_name,
            product_line=product_line,
            module=module,
            priority=str(payload.priority or "").strip() or "P1",
            test_type="ui",
            precondition_state=str(page_object_item.get("precondition_state") or "").strip(),
            test_steps=case_steps,
            tags=tags,
            creator=creator,
            assignee=str(payload.assignee or "").strip(),
            status=str(payload.status or "").strip() or "active",
            source_ref=f"recorder:{session_item.session_id}",
            script_code=_build_case_script_from_recorded_steps(session_item, recorded_steps),
            expected_result="关键步骤可稳定回放，页面对象元素可被可靠引用。",
        ),
    )
    ref_result = {"linked_ref_count": 0, "skipped_ref_count": 0}
    if bool(payload.link_page_refs):
        ref_result = _link_case_refs_for_recorded_elements(
            db,
            session=session_item,
            case_id=str(case.case_id or ""),
            recorded_steps=recorded_steps,
            created_by=creator,
        )
    return {
        "id": int(case.id),
        "case_id": str(case.case_id or ""),
        "name": str(case.name or ""),
        "project_code": str(case.project_code or ""),
        "client": str(case.client or ""),
        "page_code": str(case.page_code or ""),
        "page_object_action": page_object_action,
        "recorded_step_count": len(recorded_steps),
        "case_step_count": len(case_steps),
        **ref_result,
    }


def stop_recorder_session(
    db: Session,
    *,
    session_id: str,
    payload: RecorderSessionStopPayload,
) -> dict[str, object]:
    item = _get_session_or_404(db, session_id)
    script_path = Path(item.script_path)
    parsed_steps = _parse_codegen_steps(script_path)
    parsed_locators_all = _parse_codegen_script(script_path, include_dynamic_text=True)
    parsed_locators = [locator for locator in parsed_locators_all if not _is_locator_blocked_for_ingest(locator)[0]]
    step_hit_count_by_key: dict[tuple[str, str, str], int] = {}
    for step in parsed_steps:
        if step.locator_type == "url":
            continue
        key = _locator_key(step.locator_type, step.locator_value, step.role)
        step_hit_count_by_key[key] = int(step_hit_count_by_key.get(key, 0)) + 1
    probe_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    probe_status = "not_requested"
    if bool(payload.verify_locators):
        probe_by_key, probe_status = _probe_availability(
            item.url,
            parsed_locators_all,
            timeout_ms=int(payload.verify_timeout_ms or 4000),
        )

    if item.status in {"stopped", "failed"}:
        session_payload = _serialize_session(item)
        page_object_item, current_elements = _load_page_object_snapshot(
            db,
            project_code=item.project_code,
            client=item.client,
            page_code=item.page_code,
        )
        element_candidates = _build_element_candidates(
            parsed_locators_all,
            step_hit_count_by_key=step_hit_count_by_key,
            element_code_by_key={},
            ingested_keys=set(),
            probe_by_key=probe_by_key,
            probe_status=probe_status,
        )
        return {
            "session": session_payload,
            "ingested_count": 0,
            "elements": [],
            "steps": list(session_payload.get("recorded_steps") or []),
            "element_candidates": element_candidates,
            "verification": {"requested": bool(payload.verify_locators), "status": probe_status},
            "page_object_action": "already_stopped",
            "page_object": page_object_item,
            "page_element_total_count": len(current_elements),
            "first_element_code": str(current_elements[0].get("element_code") or "") if current_elements else "",
        }

    _stop_codegen_process(item.process_pid)
    ingested: list[dict[str, object]] = []
    element_code_by_key: dict[tuple[str, str, str], str] = {}
    ingested_keys: set[tuple[str, str, str]] = set()
    page_object_action = "not_ingested"
    page_object_item: dict[str, object] = {}

    if payload.ingest_to_page_object:
        page_object_item, page_object_action = _ensure_page_object(
            db,
            project_code=item.project_code,
            client=item.client,
            page_code=item.page_code,
            page_name=item.page_name,
            entry_url=item.url,
            started_by=item.started_by,
        )
        existing_elements = page_object_service.list_page_elements(
            db,
            page_code=item.page_code,
            project_code=item.project_code,
            client=item.client,
        )
        for existing in existing_elements:
            element_code_by_key[
                _locator_key(
                    str(existing.get("locator_type") or ""),
                    str(existing.get("locator_value") or ""),
                    str(existing.get("role") or ""),
                )
            ] = str(existing.get("element_code") or "")
        for index, locator in enumerate(parsed_locators, start=1):
            locator_key = _locator_key(locator.locator_type, locator.locator_value, locator.role)
            element_code = _normalize_element_code(
                f"{item.page_code}-{locator.locator_type}-{locator.locator_value[:24]}-{index}"
            )
            element_name = f"录制元素{index}"
            try:
                element = page_object_service.create_page_element(
                    db,
                    page_code=item.page_code,
                    project_code=item.project_code,
                    client=item.client,
                    payload=PageElementCreate(
                        element_code=element_code,
                        element_name=element_name,
                        locator_type=locator.locator_type,
                        locator_value=locator.locator_value,
                        role=locator.role,
                        status="active",
                        is_primary=True,
                        owner=item.started_by,
                        changed_by=payload.changed_by,
                        change_summary=f"recorder session {item.session_id}",
                    ),
                )
                ingested.append(element)
                element_code_by_key[locator_key] = str(element.get("element_code") or "")
                ingested_keys.add(locator_key)
            except HTTPException as exc:
                if int(exc.status_code) != status.HTTP_409_CONFLICT:
                    raise
                existing = page_object_service.get_page_element(
                    db,
                    page_code=item.page_code,
                    element_code=element_code,
                    project_code=item.project_code,
                    client=item.client,
                )
                element_code_by_key[locator_key] = str(existing.get("element_code") or "")

    serialized_steps = _serialize_recorded_steps(parsed_steps, element_code_by_key=element_code_by_key)
    _save_recorded_steps(script_path, serialized_steps)
    element_candidates = _build_element_candidates(
        parsed_locators_all,
        step_hit_count_by_key=step_hit_count_by_key,
        element_code_by_key=element_code_by_key,
        ingested_keys=ingested_keys,
        probe_by_key=probe_by_key,
        probe_status=probe_status,
    )

    item.status = "stopped"
    item.stopped_at = datetime.now(UTC)
    item.process_pid = None
    db.add(item)
    db.commit()
    db.refresh(item)
    snapshot_page_object, snapshot_elements = _load_page_object_snapshot(
        db,
        project_code=item.project_code,
        client=item.client,
        page_code=item.page_code,
    )
    if snapshot_page_object:
        page_object_item = snapshot_page_object
    first_element_code = str(ingested[0].get("element_code") or "") if ingested else ""
    if not first_element_code and snapshot_elements:
        first_element_code = str(snapshot_elements[0].get("element_code") or "")

    return {
        "session": _serialize_session(item),
        "ingested_count": len(ingested),
        "elements": ingested,
        "steps": serialized_steps,
        "element_candidates": element_candidates,
        "verification": {"requested": bool(payload.verify_locators), "status": probe_status},
        "page_object_action": page_object_action,
        "page_object": page_object_item,
        "page_element_total_count": len(snapshot_elements),
        "first_element_code": first_element_code,
    }
