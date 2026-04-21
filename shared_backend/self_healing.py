from __future__ import annotations

from typing import Callable


class SelectorResolutionError(RuntimeError):
    pass


def resolve_selector_with_fallback(
    *,
    selector: str,
    fallback_selectors: list[str] | None,
    selector_probe: Callable[[str], bool],
) -> tuple[str, bool]:
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

