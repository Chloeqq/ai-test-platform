"""Deterministic source identity policies for Requirement and Manual sources."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.constants.evie_ai import TestAssetOperationType, TestAssetSourceType
from app.core.id_gen import REQUIREMENT_ID_PATTERN, REQUIREMENT_VERSION_ID_PATTERN
from app.policies.evie_ai.actor_identity_policy import is_valid_user_actor
from app.policies.evie_ai.content_fingerprint import sha256_hex

SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"


@dataclass(frozen=True)
class RequirementSourceIdentity:
    requirement_id: str
    requirement_version_id: str


@dataclass(frozen=True)
class ManualSourceIdentity:
    project_code: str
    actor_or_client_id: str
    operation_type: TestAssetOperationType
    idempotency_key: str
    request_fingerprint: str


def build_requirement_source_identity_hash(
    identity: RequirementSourceIdentity,
) -> str:
    if re.fullmatch(REQUIREMENT_ID_PATTERN, identity.requirement_id) is None:
        raise ValueError("invalid requirement_id")
    if (
        re.fullmatch(
            REQUIREMENT_VERSION_ID_PATTERN,
            identity.requirement_version_id,
        )
        is None
    ):
        raise ValueError("invalid requirement_version_id")
    return sha256_hex(
        {
            "source_type": TestAssetSourceType.REQUIREMENT.value,
            "requirement_id": identity.requirement_id,
            "requirement_version_id": identity.requirement_version_id,
        }
    )


def build_manual_source_identity_hash(identity: ManualSourceIdentity) -> str:
    if not identity.project_code:
        raise ValueError("project_code is required")
    if not is_valid_user_actor(identity.actor_or_client_id):
        raise ValueError("invalid actor_or_client_id")
    if not identity.idempotency_key:
        raise ValueError("idempotency_key is required")
    if re.fullmatch(SHA256_HEX_PATTERN, identity.request_fingerprint) is None:
        raise ValueError("invalid request_fingerprint")
    return sha256_hex(
        {
            "source_type": TestAssetSourceType.MANUAL.value,
            "project_code": identity.project_code,
            "actor_or_client_id": identity.actor_or_client_id,
            "operation_type": identity.operation_type.value,
            "idempotency_key": identity.idempotency_key,
            "request_fingerprint": identity.request_fingerprint,
        }
    )
