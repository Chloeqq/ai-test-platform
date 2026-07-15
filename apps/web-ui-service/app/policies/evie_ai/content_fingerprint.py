"""Deterministic normalization and fingerprinting for natural-language assets."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TestAssetContent:
    title: str
    precondition: str | None
    natural_steps: tuple[str, ...]
    expected_result: str
    priority: str | None
    tags: tuple[str, ...]


def normalize_text_field(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    without_trailing_space = "\n".join(
        line.rstrip() for line in normalized.split("\n")
    )
    return without_trailing_space.strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_text_field(value)


def normalize_test_asset_content(content: TestAssetContent) -> TestAssetContent:
    normalized_tags = tuple(
        sorted(
            {
                normalized_tag
                for tag in content.tags
                if (normalized_tag := normalize_text_field(tag))
            }
        )
    )
    return TestAssetContent(
        title=normalize_text_field(content.title),
        precondition=_normalize_optional_text(content.precondition),
        natural_steps=tuple(
            normalize_text_field(step) for step in content.natural_steps
        ),
        expected_result=normalize_text_field(content.expected_result),
        priority=_normalize_optional_text(content.priority),
        tags=normalized_tags,
    )


def content_payload(content: TestAssetContent) -> dict[str, object]:
    normalized = normalize_test_asset_content(content)
    return {
        "title": normalized.title,
        "precondition": normalized.precondition,
        "natural_steps": list(normalized.natural_steps),
        "expected_result": normalized.expected_result,
        "priority": normalized.priority,
        "tags": list(normalized.tags),
    }


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_content_fingerprint(content: TestAssetContent) -> str:
    return sha256_hex(content_payload(content))
