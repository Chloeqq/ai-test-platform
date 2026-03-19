from __future__ import annotations

from typing import Any


def summarize_generation_response(response: dict[str, Any]) -> dict[str, Any]:
    generated = response.get("generated") if isinstance(response, dict) else {}
    validations = response.get("validations") if isinstance(response, dict) else []
    total_records = sum(len(items) for items in generated.values()) if isinstance(generated, dict) else 0
    failed = [
        item for item in validations
        if isinstance(item, dict) and not bool(item.get("passed", False))
    ]
    return {
        "total_groups": len(generated) if isinstance(generated, dict) else 0,
        "total_records": total_records,
        "failed_validation_count": len(failed),
        "ok": len(failed) == 0,
    }
