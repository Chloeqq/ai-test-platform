"""为 EvieAi API 请求构造稳定的 actor 上下文。"""

from __future__ import annotations

from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.policies.evie_ai.actor_identity_policy import normalize_user_actor
from app.services.evie_ai.user_public_identity_service import (
    TrustedUserPrincipal,
)


class RequestActorContext:
    def execute(self, principal: TrustedUserPrincipal) -> str:
        if not isinstance(principal, TrustedUserPrincipal):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.IDENTITY,
                message="A trusted user principal is required.",
                retryable=False,
            )

        return normalize_user_actor(principal.user_public_id)
