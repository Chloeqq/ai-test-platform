"""选择器自愈：主 selector 失败时按序探测 fallback 列表。"""
from __future__ import annotations

from typing import Callable


class SelectorResolutionError(RuntimeError):
    """主 selector 与所有 fallback 均无法匹配 DOM 时抛出。"""


def resolve_selector_with_fallback(
    *,
    selector: str,
    fallback_selectors: list[str] | None,
    selector_probe: Callable[[str], bool],
) -> tuple[str, bool]:
    """按序探测 selector，返回 (命中的 selector, 是否使用了 fallback)。"""
    candidates = [selector, *(fallback_selectors or [])]
    visited: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if not normalized or normalized in visited:
            continue
        visited.add(normalized)
        if selector_probe(normalized):
            return normalized, normalized != selector
    raise SelectorResolutionError("no available selector from primary and fallback candidates")

