from __future__ import annotations

from typing import Any

from .element_binding import resolve_element_code


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_key(value: Any) -> str:
    text = _normalized_text(value).lower()
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_action(value: Any) -> str:
    action = _normalized_key(value)
    if action in {"goto", "open", "navigate"}:
        return "goto"
    if action in {"click", "tap", "press"}:
        return "click"
    if action in {"input", "fill", "type"}:
        return "input"
    if action in {"assert", "assertvisible", "visible"}:
        return "assert_visible"
    if action in {"asserttext", "text"}:
        return "assert_text"
    if action in {"asserturl", "url"}:
        return "assert_url"
    if action in {"assertmetric", "assertnumber", "metric", "number", "numeric"}:
        return "assert_metric"
    if action in {"wait", "waitfor"}:
        return "wait_for"
    if action in {"login"}:
        return "login"
    return ""


def _split_payload(text: str) -> tuple[str, str]:
    payload = _normalized_text(text)
    if not payload:
        return "", ""
    for separator in ("=", "::", "=>", "|"):
        if separator in payload:
            left, right = payload.split(separator, 1)
            return _normalized_text(left), _normalized_text(right)
    return payload, ""


def _resolve_target_code(target: Any, alias_map: dict[str, str] | None) -> str:
    normalized_target = _normalized_text(target)
    if not normalized_target:
        return ""
    if not isinstance(alias_map, dict) or not alias_map:
        return ""
    resolved = resolve_element_code(normalized_target, alias_map)
    return resolved or ""


def resolve_explicit_step(
    *,
    steps_hint: Any,
    page: str,
    target: Any = None,
    value: Any = None,
    page_element_alias_map: dict[str, str] | None = None,
) -> tuple[str, str | None, Any]:
    hints = steps_hint if isinstance(steps_hint, list) else ([] if steps_hint is None else [steps_hint])
    if not hints:
        raise ValueError("missing explicit steps_hint")

    hint = hints[0]
    hint_action = ""
    hint_target = ""
    hint_value: Any = None

    if isinstance(hint, dict):
        hint_action = _normalize_action(hint.get("action"))
        hint_target = _normalized_text(hint.get("target"))
        hint_value = hint.get("value")
    else:
        hint_text = _normalized_text(hint)
        if not hint_text:
            raise ValueError("empty steps_hint entry")
        if ":" in hint_text:
            action_raw, payload = hint_text.split(":", 1)
            hint_action = _normalize_action(action_raw)
            if hint_action in {"goto", "login"}:
                hint_value = _normalized_text(payload)
            elif hint_action == "assert_metric":
                payload_text = _normalized_text(payload)
                comparator_split = None
                for operator in (">=", "<=", "==", "!=", ">", "<"):
                    if operator in payload_text:
                        left, right = payload_text.split(operator, 1)
                        comparator_split = (_normalized_text(left), f"{operator}{_normalized_text(right)}")
                        break
                if comparator_split is not None:
                    hint_target, hint_value = comparator_split
                else:
                    hint_target, hint_value = _split_payload(payload_text)
            elif hint_action in {"click", "wait_for", "assert_visible", "assert_text", "assert_url", "assert_metric"}:
                hint_target, hint_value = _split_payload(payload)
            elif hint_action == "input":
                hint_target, hint_value = _split_payload(payload)
            else:
                hint_target = _normalized_text(payload)
        else:
            hint_action = _normalize_action(hint_text)

    if not hint_action:
        raise ValueError(f"unsupported explicit step hint: {hint!r}")

    explicit_target = _normalized_text(target) or hint_target
    explicit_value = value if value is not None else hint_value

    if hint_action == "goto":
        route = _normalized_text(explicit_value) or _normalized_text(hint_target)
        if not route:
            raise ValueError("goto step requires explicit route")
        if not route.startswith(("http://", "https://", "/", "#/")):
            route = f"/{route.lstrip('/')}"
        return "goto", None, route

    if hint_action == "login":
        return "login", None, None

    if hint_action in {"click", "wait_for", "assert_visible", "assert_text"}:
        resolved_target = _resolve_target_code(explicit_target, page_element_alias_map)
        if not resolved_target:
            raise ValueError(f"{hint_action} step requires explicit target")
        return hint_action, resolved_target, None

    if hint_action == "assert_metric":
        resolved_target = _resolve_target_code(explicit_target, page_element_alias_map)
        if not resolved_target:
            raise ValueError("assert_metric step requires explicit target")
        rule = explicit_value
        if rule is None or str(rule).strip() == "":
            rule = "number"
        return "assert_metric", resolved_target, rule

    if hint_action == "assert_url":
        route = _normalized_text(explicit_value) or _normalized_text(hint_target)
        if not route:
            raise ValueError("assert_url step requires explicit url")
        return "assert_url", None, route

    if hint_action == "input":
        resolved_target = _resolve_target_code(explicit_target, page_element_alias_map)
        if not resolved_target:
            raise ValueError("input step requires explicit target")
        if explicit_value is None:
            raise ValueError("input step requires explicit value")
        return "input", resolved_target, explicit_value

    raise ValueError(f"unsupported explicit step action: {hint_action}")
