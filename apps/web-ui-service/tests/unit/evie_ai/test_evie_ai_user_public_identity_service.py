from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.models.user import User
from app.services.evie_ai.user_public_identity_service import (
    TrustedUserPrincipal,
    UserPublicIdentityService,
)

USER_PUBLIC_ID = "usr_0123456789abcdef0123456789abcdef"


def test_trusted_user_principal_is_immutable_and_exposes_approved_fields() -> None:
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role="viewer",
        is_active=True,
    )

    assert principal.user_public_id == USER_PUBLIC_ID
    assert principal.role == "viewer"
    assert principal.is_active is True
    assert not hasattr(principal, "id")

    with pytest.raises(FrozenInstanceError):
        principal.role = "admin"


def test_user_public_identity_service_builds_trusted_principal_from_authenticated_user() -> None:
    service = UserPublicIdentityService()
    user = User(
        id=42,
        user_public_id=USER_PUBLIC_ID,
        username="tester",
        hashed_password="hashed",
        role="developer",
        is_active=True,
    )

    principal = service.execute(user)

    assert principal == TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role="developer",
        is_active=True,
    )
    assert not hasattr(principal, "id")


@pytest.mark.parametrize(
    "invalid_user_public_id",
    [
        None,
        "",
        "   ",
        "user_0123456789abcdef0123456789abcdef",
        "usr_0123456789abcdef0123456789abcde",
        "usr_0123456789abcdef0123456789abcdef!",
    ],
)
def test_user_public_identity_service_fails_closed_for_invalid_public_identity(
    invalid_user_public_id: str | None,
) -> None:
    # 服务必须在 actor 或其他下游上下文建立前阻止非法 principal。
    service = UserPublicIdentityService()
    user = User(
        id=42,
        user_public_id=invalid_user_public_id,  # type: ignore[arg-type]
        username="tester",
        hashed_password="hashed",
        role="developer",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        service.execute(user)

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.IDENTITY
    assert exc_info.value.retryable is False
