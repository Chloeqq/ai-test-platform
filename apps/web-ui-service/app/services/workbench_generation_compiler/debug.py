from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

_TRUTHY = {"1", "true", "yes", "on"}
_SNAPSHOT_LOCK = threading.Lock()
_SNAPSHOTS: dict[tuple[str, str], Any] = {}


def debug_enabled() -> bool:
    raw = os.getenv("WORKBENCH_GENERATION_DEBUG")
    return str(raw or "").strip().lower() in _TRUTHY


def _to_stable_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(value)


def build_trace_id(*, stage: str, payload: Any) -> str:
    raw = f"{stage}:{_to_stable_json(payload)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"wbgen-{digest[:16]}"


def digest_payload(payload: Any) -> str:
    raw = _to_stable_json(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _json_clone(value: Any) -> Any:
    try:
        return json.loads(_to_stable_json(value))
    except Exception:
        return deepcopy(value)


def _layer_from_event(event: str) -> str:
    token = str(event or "").strip().split(".", 1)[0]
    return token or "unknown"


def _diff_summary(left: Any, right: Any) -> dict[str, Any]:
    if isinstance(left, dict) and isinstance(right, dict):
        left_keys = set(left.keys())
        right_keys = set(right.keys())
        added = sorted(str(key) for key in right_keys - left_keys)[:20]
        removed = sorted(str(key) for key in left_keys - right_keys)[:20]
        changed: list[str] = []
        for key in sorted(left_keys & right_keys, key=lambda item: str(item)):
            if left.get(key) != right.get(key):
                changed.append(str(key))
                if len(changed) >= 20:
                    break
        return {
            "mode": "dict",
            "added_keys": added,
            "removed_keys": removed,
            "changed_keys": changed,
            "changed_count": len(changed),
        }
    if isinstance(left, list) and isinstance(right, list):
        return {
            "mode": "list",
            "left_length": len(left),
            "right_length": len(right),
            "length_delta": len(right) - len(left),
            "changed": left != right,
        }
    return {
        "mode": "scalar",
        "changed": left != right,
        "left_type": type(left).__name__,
        "right_type": type(right).__name__,
    }


def _debug_output_file() -> Path:
    raw = str(os.getenv("WORKBENCH_GENERATION_DEBUG_FILE", "") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path("/tmp/workbench_generation_debug.jsonl")


def _append_debug_file_line(line: str) -> None:
    path = _debug_output_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return


def summarize_payload(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": type(payload).__name__,
        "digest": digest_payload(payload),
    }
    if isinstance(payload, dict):
        keys = [str(key) for key in payload.keys()]
        summary["keys"] = keys[:20]
        summary["key_count"] = len(keys)
    elif isinstance(payload, list):
        summary["length"] = len(payload)
    else:
        summary["repr"] = str(payload)[:200]
    return summary


def log_debug_event(
    *,
    logger: logging.Logger,
    event: str,
    trace_id: str,
    payload: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    if not debug_enabled():
        return
    compare_with_event = ""
    if isinstance(extra, dict):
        compare_with_event = str(extra.get("compare_with_event", "")).strip()
    payload_snapshot = _json_clone(payload)
    compare_snapshot: Any = None
    with _SNAPSHOT_LOCK:
        _SNAPSHOTS[(trace_id, event)] = payload_snapshot
        if compare_with_event:
            compare_snapshot = _SNAPSHOTS.get((trace_id, compare_with_event))
    event_payload: dict[str, Any] = {
        "event": event,
        "layer": _layer_from_event(event),
        "trace_id": trace_id,
        "summary": summarize_payload(payload),
    }
    if compare_with_event:
        event_payload["compare_with_event"] = compare_with_event
        event_payload["compare_found"] = compare_snapshot is not None
        if compare_snapshot is not None:
            event_payload["compare_summary"] = summarize_payload(compare_snapshot)
            event_payload["diff_summary"] = _diff_summary(compare_snapshot, payload_snapshot)
    if isinstance(extra, dict) and extra:
        event_payload["extra"] = {k: v for k, v in extra.items() if str(k) != "compare_with_event"}
    serialized = _to_stable_json(event_payload)
    logger.info("workbench_generation_debug %s", serialized)
    _append_debug_file_line(serialized)
