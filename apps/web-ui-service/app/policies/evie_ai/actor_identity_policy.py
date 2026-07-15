"""Canonical EvieAi actor identity policy."""

from __future__ import annotations

from app.errors.evie_ai import EvieAiDomainError, EvieAiErrorCode, EvieAiErrorStage
from app.policies.evie_ai.user_identity_policy import is_valid_user_public_id


def normalize_user_actor(user_public_id: str | None) -> str:
    if not is_valid_user_public_id(user_public_id):
        raise EvieAiDomainError(
            EvieAiErrorCode.DATA_INTEGRITY_ERROR,
            stage=EvieAiErrorStage.IDENTITY,
            message="A valid stable user public identity is required.",
            retryable=False,
        )
    return f"user:{user_public_id}"


def is_valid_user_actor(actor_or_client_id: str | None) -> bool:
    if actor_or_client_id is None:
        return False
    prefix = "user:"
    return actor_or_client_id.startswith(prefix) and is_valid_user_public_id(
        actor_or_client_id.removeprefix(prefix)
    )
