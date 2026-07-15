from __future__ import annotations

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_idempotency_retention_defaults_to_seven_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EVIE_AI_IDEMPOTENCY_RETENTION_DAYS", raising=False)

    assert Settings().evie_ai_idempotency_retention_days == 7


def test_idempotency_retention_accepts_positive_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVIE_AI_IDEMPOTENCY_RETENTION_DAYS", "14")

    assert Settings().evie_ai_idempotency_retention_days == 14


@pytest.mark.parametrize("raw_value", ["0", "-1", "not-an-integer"])
def test_idempotency_retention_rejects_invalid_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
) -> None:
    monkeypatch.setenv("EVIE_AI_IDEMPOTENCY_RETENTION_DAYS", raw_value)

    with pytest.raises((ValueError, ValidationError)):
        Settings()
