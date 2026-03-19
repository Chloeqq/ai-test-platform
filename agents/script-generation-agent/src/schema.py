from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class GeneratedScript:
    version: str
    framework: str
    language: str
    case_id: str
    page: str
    filename: str
    entrypoint: str
    script_code: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
