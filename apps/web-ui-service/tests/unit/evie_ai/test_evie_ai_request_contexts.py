from __future__ import annotations

import pytest

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.models.user import User
from app.services.evie_ai.request_actor_context import RequestActorContext
from app.services.evie_ai.request_channel_context import RequestChannelContext
from app.services.evie_ai.request_trace_context import RequestTraceContext
from app.services.evie_ai.user_public_identity_service import TrustedUserPrincipal

USER_PUBLIC_ID = "usr_0123456789abcdef0123456789abcdef"


def test_request_actor_context_builds_stable_actor_from_trusted_principal() -> None:
    context = RequestActorContext()
    principal = TrustedUserPrincipal(
        user_public_id=USER_PUBLIC_ID,
        role="developer",
        is_active=True,
    )

    assert context.execute(principal) == f"user:{USER_PUBLIC_ID}"


def test_request_actor_context_rejects_orm_user_input() -> None:
    context = RequestActorContext()
    user = User(
        id=42,
        user_public_id=USER_PUBLIC_ID,
        username="tester",
        hashed_password="hashed",
        role="developer",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        context.execute(user)  # type: ignore[arg-type]

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.IDENTITY


@pytest.mark.parametrize("invalid_user_public_id", ["", "bad-id", "usr_" + "g" * 32])
def test_request_actor_context_fails_closed_for_invalid_public_identity(
    invalid_user_public_id: str,
) -> None:
    context = RequestActorContext()
    principal = TrustedUserPrincipal(
        user_public_id=invalid_user_public_id,
        role="developer",
        is_active=True,
    )

    with pytest.raises(EvieAiDomainError) as exc_info:
        context.execute(principal)

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.IDENTITY
    assert exc_info.value.retryable is False


def test_request_channel_context_always_returns_trusted_api_channel() -> None:
    context = RequestChannelContext()

    assert context.execute() == "api"


def test_request_channel_context_exposes_no_client_controlled_input() -> None:
    assert RequestChannelContext.execute.__code__.co_argcount == 1


def test_request_trace_context_uses_existing_request_id_and_internal_correlation_id() -> None:
    context = RequestTraceContext.from_request_id("request-123")

    assert context.request_id == "request-123"
    assert context.correlation_id
    assert context.correlation_id != context.request_id


@pytest.mark.parametrize("request_id", [None, "", "   "])
def test_request_trace_context_fails_closed_for_invalid_internal_request_id(
    request_id: str | None,
) -> None:
    with pytest.raises(EvieAiDomainError) as exc_info:
        RequestTraceContext.from_request_id(request_id)  # type: ignore[arg-type]

    assert exc_info.value.code is EvieAiErrorCode.DATA_INTEGRITY_ERROR
    assert exc_info.value.stage is EvieAiErrorStage.REQUEST_VALIDATION


def test_request_trace_context_has_no_client_controlled_correlation_parameter() -> None:
    assert RequestTraceContext.from_request_id.__func__.__code__.co_argcount == 2
