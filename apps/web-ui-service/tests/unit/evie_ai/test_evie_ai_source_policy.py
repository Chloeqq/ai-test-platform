from __future__ import annotations

import pytest
from app.constants.evie_ai import TestAssetOperationType as OperationType
from app.policies.evie_ai.source_policy import (
    ManualSourceIdentity,
    RequirementSourceIdentity,
    build_manual_source_identity_hash,
    build_requirement_source_identity_hash,
)


def test_requirement_source_identity_matches_frozen_vector() -> None:
    identity = RequirementSourceIdentity(
        requirement_id="req_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        requirement_version_id="reqv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    assert build_requirement_source_identity_hash(identity) == (
        "267837638a82f16f56afec5771d1c6e1c65ec34caa7ecc52f3b7896ae48b13b2"
    )


def test_manual_source_identity_changes_with_real_source_semantics() -> None:
    base = ManualSourceIdentity(
        project_code="demo",
        actor_or_client_id="user:usr_0123456789abcdef0123456789abcdef",
        operation_type=OperationType.CREATE_ASSET,
        idempotency_key="request-1",
        request_fingerprint="a" * 64,
    )
    changed = ManualSourceIdentity(
        project_code="demo",
        actor_or_client_id=base.actor_or_client_id,
        operation_type=base.operation_type,
        idempotency_key="request-2",
        request_fingerprint=base.request_fingerprint,
    )

    assert build_manual_source_identity_hash(base) == (
        "7b51aeacee59b218686bb05eb3fea1a947c8ea259ca14c64061ae1368309420c"
    )
    assert build_manual_source_identity_hash(base) != build_manual_source_identity_hash(
        changed
    )


def test_source_identity_rejects_malformed_authoritative_inputs() -> None:
    with pytest.raises(ValueError, match="requirement_id"):
        build_requirement_source_identity_hash(
            RequirementSourceIdentity(
                requirement_id="not-a-requirement",
                requirement_version_id="reqv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            )
        )

    with pytest.raises(ValueError, match="actor_or_client_id"):
        build_manual_source_identity_hash(
            ManualSourceIdentity(
                project_code="demo",
                actor_or_client_id="user:admin",
                operation_type=OperationType.CREATE_ASSET,
                idempotency_key="request-1",
                request_fingerprint="a" * 64,
            )
        )
