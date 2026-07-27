from __future__ import annotations

import pytest
from unittest.mock import Mock

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.models.user import User
from app.repositories.test_project_repository import TestProjectRepository
from app.services.evie_ai.project_access_authorizer import (
    ProjectAccessAuthorizer,
)
from app.services.evie_ai.user_public_identity_service import TrustedUserPrincipal

USER_PUBLIC_ID = "usr_0123456789abcdef0123456789abcdef"


def test_project_access_authorizer_allows_active_admin_principal() -> None:
    authorizer = ProjectAccessAuthorizer()
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role="admin",
        is_active=True,
    )

    assert authorizer.execute(principal) is True


@pytest.mark.parametrize(
    ("role", "is_active"),
    [
        ("developer", True),
        ("viewer", True),
        ("admin", False),
    ],
)
def test_project_access_authorizer_denies_non_admin_or_inactive_principal(
    role: str,
    is_active: bool,
) -> None:
    authorizer = ProjectAccessAuthorizer()
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role=role,
        is_active=is_active,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        authorizer.execute(principal)

    assert exc_info.value.code is EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN
    assert exc_info.value.stage is EvieAiErrorStage.AUTHORIZATION
    assert exc_info.value.retryable is False


def test_project_access_authorizer_rejects_orm_user_input() -> None:
    authorizer = ProjectAccessAuthorizer()
    user = User(
        id=42,
        user_public_id=USER_PUBLIC_ID,
        username="tester",
        hashed_password="hashed",
        role="admin",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        authorizer.execute(user)  # type: ignore[arg-type]

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.IDENTITY


@pytest.mark.parametrize(
    ("role", "is_active"),
    [
        ("developer", True),
        ("viewer", True),
        ("admin", False),
        ("Admin", True),
        (42, True),
        ("admin", "true"),
    ],
)
def test_project_access_authorizer_rejects_noncanonical_role_or_active_flag(
    role: object,
    is_active: object,
) -> None:
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role=role,  # type: ignore[arg-type]
        is_active=is_active,  # type: ignore[arg-type]
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        ProjectAccessAuthorizer().execute(principal)

    assert exc_info.value.code is EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN


def test_non_admin_denial_happens_before_any_project_repository_query() -> None:
    repository = Mock(spec=TestProjectRepository)
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role="viewer",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        ProjectAccessAuthorizer().execute(principal)

    assert exc_info.value.code is EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN
    repository.get_by_code.assert_not_called()
