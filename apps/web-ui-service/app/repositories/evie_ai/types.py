"""EvieAi Repository 层内部返回类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RepositoryPage(Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
