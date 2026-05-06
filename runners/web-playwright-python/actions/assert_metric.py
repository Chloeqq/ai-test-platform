from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from runner.variable_resolver import resolve_variables


_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_COMPARATOR_RE = re.compile(r"^\s*(>=|<=|>|<|==|!=)\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*$")
_CURRENCY_HINT_RE = re.compile(r"[¥￥$€£]|人民币|元")


@dataclass
class _MetricSample:
    number_text: str
    numeric_value: float
    raw_text: str


def _single_locator(locator):
    if locator is None:
        return None
    try:
        if locator.count() > 1:
            return locator.first
    except Exception:
        return locator
    return locator


def _safe_text_content(locator) -> str:
    if locator is None:
        return ""
    for method_name in ("text_content", "inner_text"):
        method = getattr(locator, method_name, None)
        if not callable(method):
            continue
        try:
            value = method()
        except Exception:
            continue
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _collect_candidate_texts(locator, *, max_depth: int = 3) -> list[str]:
    current = _single_locator(locator)
    results: list[str] = []
    for _ in range(max_depth + 1):
        if current is None:
            break
        text = _safe_text_content(current)
        if text:
            results.append(text)
        try:
            current = current.locator("xpath=..")
        except Exception:
            break
    # Keep order and deduplicate
    deduped: list[str] = []
    seen: set[str] = set()
    for item in results:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _parse_float(number_text: str) -> float:
    return float(str(number_text).replace(",", "").strip())


def _extract_number_from_text(
    *,
    text: str,
    metric_label: str,
    extract_regex: str,
) -> str:
    if extract_regex:
        matched = re.search(extract_regex, text)
        if matched:
            candidate = matched.group(1) if matched.lastindex else matched.group(0)
            number_match = _NUMBER_RE.search(str(candidate))
            if number_match:
                return number_match.group(0)

    if metric_label:
        pattern = re.compile(rf"{re.escape(metric_label)}\s*[:：]?\s*({_NUMBER_RE.pattern})")
        matched = pattern.search(text)
        if matched:
            return matched.group(1)
        pos = text.find(metric_label)
        if pos >= 0:
            suffix = text[pos + len(metric_label) :]
            fallback = _NUMBER_RE.search(suffix)
            if fallback:
                return fallback.group(0)

    default_match = _NUMBER_RE.search(text)
    if default_match:
        return default_match.group(0)
    return ""


def _resolve_rule(step: dict[str, Any], context: dict[str, Any]) -> str:
    for source in (step.get("metric_rule"), step.get("rule"), step.get("value")):
        if source is None or source == "":
            continue
        if isinstance(source, str):
            return str(resolve_variables(source, context)).strip()
        return str(source).strip()
    raise ValueError("assert_metric action requires metric_rule/rule/value")


def _resolve_metric_label(step: dict[str, Any], context: dict[str, Any]) -> str:
    for source in (step.get("metric_label"), step.get("label"), step.get("selector")):
        if source is None or source == "":
            continue
        value = str(resolve_variables(source, context)) if isinstance(source, str) else str(source)
        value = value.strip()
        if value:
            return value
    return ""


def _resolve_extract_regex(step: dict[str, Any], context: dict[str, Any]) -> str:
    for source in (step.get("extract_regex"), step.get("pattern"), step.get("regex")):
        if source is None or source == "":
            continue
        value = str(resolve_variables(source, context)) if isinstance(source, str) else str(source)
        value = value.strip()
        if value:
            return value
    return ""


def _extract_metric_sample(locator, *, metric_label: str, extract_regex: str) -> _MetricSample:
    texts = _collect_candidate_texts(locator)
    if not texts:
        raise AssertionError("assert_metric could not read any text from locator or ancestors")
    for text in texts:
        number_text = _extract_number_from_text(
            text=text,
            metric_label=metric_label,
            extract_regex=extract_regex,
        )
        if not number_text:
            continue
        return _MetricSample(
            number_text=number_text,
            numeric_value=_parse_float(number_text),
            raw_text=text,
        )
    raise AssertionError(f"assert_metric could not extract numeric value from texts: {texts}")


def _assert_metric_rule(sample: _MetricSample, *, rule: str) -> None:
    normalized_rule = str(rule or "").strip()
    lowered = normalized_rule.lower()

    if lowered in {"number", "numeric"}:
        return
    if lowered == "integer":
        if "." in sample.number_text:
            raise AssertionError(f"assert_metric expected integer, got `{sample.number_text}`")
        return
    if lowered == "non_negative":
        if sample.numeric_value < 0:
            raise AssertionError(f"assert_metric expected non_negative, got {sample.numeric_value}")
        return
    if lowered == "positive":
        if sample.numeric_value <= 0:
            raise AssertionError(f"assert_metric expected positive, got {sample.numeric_value}")
        return
    if lowered == "currency":
        if not _CURRENCY_HINT_RE.search(sample.raw_text):
            raise AssertionError(f"assert_metric expected currency-like text, got `{sample.raw_text}`")
        return

    if lowered.startswith("matches:") or lowered.startswith("regex:"):
        _, pattern = normalized_rule.split(":", 1)
        pattern = pattern.strip()
        if not pattern:
            raise ValueError("assert_metric regex rule cannot be empty")
        if not re.search(pattern, sample.number_text):
            raise AssertionError(
                f"assert_metric regex `{pattern}` does not match extracted value `{sample.number_text}`"
            )
        return

    comparator = _COMPARATOR_RE.match(normalized_rule)
    if comparator:
        operator = comparator.group(1)
        expected = _parse_float(comparator.group(2))
        actual = sample.numeric_value
        checks = {
            ">=": actual >= expected,
            ">": actual > expected,
            "<=": actual <= expected,
            "<": actual < expected,
            "==": abs(actual - expected) < 1e-9,
            "!=": abs(actual - expected) >= 1e-9,
        }
        if not checks[operator]:
            raise AssertionError(
                f"assert_metric failed: actual {actual} {operator} expected {expected} is false"
            )
        return

    if _NUMBER_RE.fullmatch(normalized_rule):
        expected_number = _parse_float(normalized_rule)
        if abs(sample.numeric_value - expected_number) >= 1e-9:
            raise AssertionError(
                f"assert_metric failed: actual {sample.numeric_value} != expected {expected_number}"
            )
        return

    raise ValueError(f"unsupported assert_metric rule: {normalized_rule}")


def assert_metric_action(page, locator, step, context, **kwargs):
    _ = page, kwargs
    if locator is None:
        raise ValueError("assert_metric action requires a resolved locator")
    runtime_context = context if isinstance(context, dict) else {}
    rule = _resolve_rule(step if isinstance(step, dict) else {}, runtime_context)
    metric_label = _resolve_metric_label(step if isinstance(step, dict) else {}, runtime_context)
    extract_regex = _resolve_extract_regex(step if isinstance(step, dict) else {}, runtime_context)
    sample = _extract_metric_sample(locator, metric_label=metric_label, extract_regex=extract_regex)
    _assert_metric_rule(sample, rule=rule)
