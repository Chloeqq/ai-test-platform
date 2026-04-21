from __future__ import annotations

import hashlib
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_ai_trace_context(
    *,
    page: str = "",
    prompt_version: str = "",
    model: str = "",
    source: str = "",
    instructions_version: str = "",
) -> dict[str, Any]:
    normalized_page = _text(page) or "common"
    normalized_prompt_version = _text(prompt_version) or "unknown"
    normalized_model = _text(model) or "rule-engine"
    normalized_source = _text(source) or "manual"
    normalized_instructions = _text(instructions_version) or "unknown"
    digest = hashlib.sha1(
        "|".join(
            [
                normalized_page,
                normalized_prompt_version,
                normalized_model,
                normalized_source,
                normalized_instructions,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "trace_id": f"ai-trace-{digest}",
        "prompt_version": normalized_prompt_version,
        "model": normalized_model,
        "source": normalized_source,
        "instructions_version": normalized_instructions,
    }


def attach_ai_trace_context(payload: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
    raw = dict(payload if isinstance(payload, dict) else {})
    trace_value = raw.get("ai_trace")
    trace_payload = trace_value if isinstance(trace_value, dict) else {}
    raw["ai_trace"] = {
        **(context if isinstance(context, dict) else {}),
        **trace_payload,
    }
    return raw
