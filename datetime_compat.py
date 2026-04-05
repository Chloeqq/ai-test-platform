"""Compatibility helpers for datetime timezone constants."""

from datetime import timezone

try:
    from datetime import UTC as UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python < 3.11
    UTC = timezone.utc

