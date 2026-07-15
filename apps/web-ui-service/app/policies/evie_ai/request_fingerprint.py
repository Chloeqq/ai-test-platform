"""Frozen v1 request-fingerprint policies for lifecycle write operations."""

from __future__ import annotations

from dataclasses import dataclass

from app.constants.evie_ai import (
    TestAssetOperationType,
    TestAssetReviewAction,
    TestAssetSourceType,
)
from app.policies.evie_ai.content_fingerprint import (
    TestAssetContent,
    content_payload,
    normalize_text_field,
    sha256_hex,
)

REQUEST_FINGERPRINT_VERSION = "v1"


@dataclass(frozen=True)
class CreateAssetFingerprintInput:
    source_type: TestAssetSourceType
    content: TestAssetContent
    requirement_id: str | None = None
    requirement_version_id: str | None = None


@dataclass(frozen=True)
class CreateVersionFingerprintInput:
    test_asset_id: str
    expected_row_version: int
    content: TestAssetContent
    reason: str | None


@dataclass(frozen=True)
class RestoreHistoricalVersionFingerprintInput:
    test_asset_id: str
    test_asset_version_id: str
    expected_row_version: int
    reason: str


@dataclass(frozen=True)
class ReviewAssetFingerprintInput:
    test_asset_id: str
    test_asset_version_id: str
    expected_row_version: int
    decision: TestAssetReviewAction
    comment: str | None
    reason: str | None


@dataclass(frozen=True)
class DeleteAssetFingerprintInput:
    test_asset_id: str
    expected_row_version: int
    reason: str


@dataclass(frozen=True)
class RestoreAssetFingerprintInput:
    test_asset_id: str
    expected_row_version: int
    reason: str


def _request_payload(
    operation_type: TestAssetOperationType,
    fields: dict[str, object],
) -> dict[str, object]:
    return {
        "fingerprint_version": REQUEST_FINGERPRINT_VERSION,
        "operation_type": operation_type.value,
        **fields,
    }


def _normalized_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_text_field(value)


def _require_positive_row_version(row_version: int) -> None:
    if row_version < 1:
        raise ValueError("expected_row_version must be positive")


def build_create_asset_request_fingerprint(
    command: CreateAssetFingerprintInput,
) -> str:
    fields: dict[str, object] = {
        "source_type": command.source_type.value,
        "content": content_payload(command.content),
    }
    if command.source_type is TestAssetSourceType.REQUIREMENT:
        if not command.requirement_id or not command.requirement_version_id:
            raise ValueError("Requirement source identity is required")
        fields["requirement_id"] = command.requirement_id
        fields["requirement_version_id"] = command.requirement_version_id
    elif command.requirement_id is not None or command.requirement_version_id is not None:
        raise ValueError("Manual source cannot contain Requirement identity")
    return sha256_hex(
        _request_payload(TestAssetOperationType.CREATE_ASSET, fields)
    )


def build_create_version_request_fingerprint(
    command: CreateVersionFingerprintInput,
) -> str:
    _require_positive_row_version(command.expected_row_version)
    return sha256_hex(
        _request_payload(
            TestAssetOperationType.CREATE_VERSION,
            {
                "test_asset_id": command.test_asset_id,
                "expected_row_version": command.expected_row_version,
                "content": content_payload(command.content),
                "reason": _normalized_optional_text(command.reason),
            },
        )
    )


def build_restore_historical_version_request_fingerprint(
    command: RestoreHistoricalVersionFingerprintInput,
) -> str:
    _require_positive_row_version(command.expected_row_version)
    return sha256_hex(
        _request_payload(
            TestAssetOperationType.RESTORE_HISTORICAL_VERSION,
            {
                "test_asset_id": command.test_asset_id,
                "test_asset_version_id": command.test_asset_version_id,
                "expected_row_version": command.expected_row_version,
                "reason": normalize_text_field(command.reason),
            },
        )
    )


def build_review_asset_request_fingerprint(
    command: ReviewAssetFingerprintInput,
) -> str:
    _require_positive_row_version(command.expected_row_version)
    return sha256_hex(
        _request_payload(
            TestAssetOperationType.REVIEW_ASSET,
            {
                "test_asset_id": command.test_asset_id,
                "test_asset_version_id": command.test_asset_version_id,
                "expected_row_version": command.expected_row_version,
                "decision": command.decision.value,
                "comment": _normalized_optional_text(command.comment),
                "reason": _normalized_optional_text(command.reason),
            },
        )
    )


def build_delete_asset_request_fingerprint(
    command: DeleteAssetFingerprintInput,
) -> str:
    _require_positive_row_version(command.expected_row_version)
    return sha256_hex(
        _request_payload(
            TestAssetOperationType.DELETE_ASSET,
            {
                "test_asset_id": command.test_asset_id,
                "expected_row_version": command.expected_row_version,
                "reason": normalize_text_field(command.reason),
            },
        )
    )


def build_restore_asset_request_fingerprint(
    command: RestoreAssetFingerprintInput,
) -> str:
    _require_positive_row_version(command.expected_row_version)
    return sha256_hex(
        _request_payload(
            TestAssetOperationType.RESTORE_ASSET,
            {
                "test_asset_id": command.test_asset_id,
                "expected_row_version": command.expected_row_version,
                "reason": normalize_text_field(command.reason),
            },
        )
    )
