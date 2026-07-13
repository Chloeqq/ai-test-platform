from __future__ import annotations

import re
import uuid
from collections.abc import Callable

import pytest

from app.core import id_gen
from app.core.id_gen import (
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
)


ID_CASES: tuple[tuple[Callable[[], str], str], ...] = (
    (generate_requirement_id, "req"),
    (generate_requirement_version_id, "reqv"),
    (generate_test_asset_id, "ta"),
    (generate_test_asset_version_id, "tav"),
    (generate_test_asset_source_id, "tas"),
)


@pytest.mark.parametrize(("generator", "prefix"), ID_CASES)
def test_evie_ai_public_ids_have_expected_format(
    generator: Callable[[], str],
    prefix: str,
) -> None:
    value = generator()

    assert re.fullmatch(rf"{prefix}_[0-9a-f]{{32}}", value)
    assert len(value) == len(prefix) + 1 + 32


@pytest.mark.parametrize(("generator", "_prefix"), ID_CASES)
def test_evie_ai_public_ids_are_unique(
    generator: Callable[[], str],
    _prefix: str,
) -> None:
    values = {generator() for _ in range(1_000)}

    assert len(values) == 1_000


def test_requirement_id_uses_full_uuid4_hex(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_uuid = uuid.UUID("01234567-89ab-cdef-0123-456789abcdef")
    monkeypatch.setattr(uuid, "uuid4", lambda: fixed_uuid)

    assert (
        id_gen.generate_requirement_id()
        == "req_0123456789abcdef0123456789abcdef"
    )
