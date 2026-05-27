from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .registry import mark_registry_entry_cleaned
except ImportError:  # pragma: no cover
    from registry import mark_registry_entry_cleaned  # type: ignore


def mark_cleaned(*, registry_path: str | Path, request_id: str) -> dict[str, Any] | None:
    return mark_registry_entry_cleaned(Path(registry_path), request_id=request_id)
