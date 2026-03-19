from __future__ import annotations

from typing import Any

try:
    from ..agent import DataGenerationAgent
except ImportError:  # pragma: no cover
    from agent import DataGenerationAgent  # type: ignore


def run_generation(payload: dict[str, Any]) -> dict[str, Any]:
    return DataGenerationAgent().generate(payload)
