from __future__ import annotations

import re
import uuid
from collections.abc import Callable

import pytest
from app.core import id_gen
from app.core.id_gen import (
    REQUIREMENT_ID_PATTERN,
    REQUIREMENT_VERSION_ID_PATTERN,
    TEST_ASSET_AUDIT_EVENT_ID_PATTERN,
    TEST_ASSET_ID_PATTERN,
    TEST_ASSET_REVIEW_ID_PATTERN,
    TEST_ASSET_SOURCE_ID_PATTERN,
    TEST_ASSET_VERSION_ID_PATTERN,
    USER_PUBLIC_ID_PATTERN,
    generate_requirement_id,
    generate_requirement_version_id,
    generate_test_asset_audit_event_id,
    generate_test_asset_id,
    generate_test_asset_review_id,
    generate_test_asset_source_id,
    generate_test_asset_version_id,
    generate_user_public_id,
)

ID_CASES: tuple[tuple[Callable[[], str], str, str], ...] = (
    (generate_requirement_id, "req", REQUIREMENT_ID_PATTERN),
    (
        generate_requirement_version_id,
        "reqv",
        REQUIREMENT_VERSION_ID_PATTERN,
    ),
    (generate_test_asset_id, "ta", TEST_ASSET_ID_PATTERN),
    (
        generate_test_asset_version_id,
        "tav",
        TEST_ASSET_VERSION_ID_PATTERN,
    ),
    (generate_test_asset_source_id, "tas", TEST_ASSET_SOURCE_ID_PATTERN),
    (generate_user_public_id, "usr", USER_PUBLIC_ID_PATTERN),
    (generate_test_asset_review_id, "tar", TEST_ASSET_REVIEW_ID_PATTERN),
    (
        generate_test_asset_audit_event_id,
        "tae",
        TEST_ASSET_AUDIT_EVENT_ID_PATTERN,
    ),
)


@pytest.mark.parametrize(("generator", "prefix", "pattern"), ID_CASES)
def test_evie_ai_public_ids_have_expected_format(
    generator: Callable[[], str],
    prefix: str,
    pattern: str,
) -> None:
    value = generator()

    assert re.fullmatch(pattern, value)
    assert len(value) == len(prefix) + 1 + 32


@pytest.mark.parametrize(("generator", "_prefix", "_pattern"), ID_CASES)
def test_evie_ai_public_ids_are_unique(
    generator: Callable[[], str],
    _prefix: str,
    _pattern: str,
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
