from __future__ import annotations

from app.policies.evie_ai.content_fingerprint import (
    TestAssetContent as AssetContent,
)
from app.policies.evie_ai.content_fingerprint import (
    build_content_fingerprint,
    canonical_json_bytes,
    normalize_test_asset_content,
)

CONTENT = AssetContent(
    title="  Cafe\u0301  ",
    precondition=" ready \r\nnext  \r",
    natural_steps=(" first  \r\n  second  ", " keep  internal "),
    expected_result=" result  ",
    priority=" P1 ",
    tags=(" smoke ", "", "回归", "smoke", "  回归 "),
)


def test_content_normalization_preserves_meaning_and_stabilizes_tags() -> None:
    normalized = normalize_test_asset_content(CONTENT)

    assert normalized == AssetContent(
        title="Café",
        precondition="ready\nnext",
        natural_steps=("first\n  second", "keep  internal"),
        expected_result="result",
        priority="P1",
        tags=("smoke", "回归"),
    )


def test_content_fingerprint_matches_frozen_vector() -> None:
    assert build_content_fingerprint(CONTENT) == (
        "4d9c36eda49d4b99c63a4ef88b7f28ce1e008df972346621c37ea808fc0aaebb"
    )


def test_canonical_json_is_independent_of_mapping_order() -> None:
    first = {"b": "值", "a": [2, 1]}
    second = {"a": [2, 1], "b": "值"}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_bytes(first) == b'{"a":[2,1],"b":"\xe5\x80\xbc"}'


def test_incomplete_natural_language_content_remains_fingerprintable() -> None:
    incomplete = AssetContent(
        title="",
        precondition=None,
        natural_steps=(),
        expected_result="",
        priority=None,
        tags=(),
    )

    assert len(build_content_fingerprint(incomplete)) == 64
