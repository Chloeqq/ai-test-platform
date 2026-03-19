from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from ..schema import DataGenerationRequest
except ImportError:  # pragma: no cover
    from schema import DataGenerationRequest  # type: ignore


def load_generation_request(payload: dict[str, Any] | str | Path) -> DataGenerationRequest:
    if isinstance(payload, DataGenerationRequest):
        return payload
    if isinstance(payload, Path):
        raw = json.loads(payload.read_text(encoding="utf-8"))
        return DataGenerationRequest.model_validate(raw)
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            raise ValueError("payload is empty")
        if text.startswith("{"):
            return DataGenerationRequest.model_validate(json.loads(text))
        return load_generation_request(Path(text))
    if isinstance(payload, dict):
        return DataGenerationRequest.model_validate(payload)
    raise TypeError(f"Unsupported payload type: {type(payload)!r}")
