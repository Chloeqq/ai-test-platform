from __future__ import annotations

import json
from typing import Any


def model_dump_json(model: Any) -> str:
    if hasattr(model, "model_dump"):
        payload = model.model_dump()
    elif hasattr(model, "dict"):
        payload = model.dict()
    else:
        payload = model
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
