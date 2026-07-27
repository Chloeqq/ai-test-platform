"""EvieAi 项目范围 API 的仅管理员授权门。"""

from __future__ import annotations

from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.services.evie_ai.user_public_identity_service import (
    TrustedUserPrincipal,
)


class ProjectAccessAuthorizer:
    def execute(self, principal: TrustedUserPrincipal) -> bool:
        if not isinstance(principal, TrustedUserPrincipal):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.IDENTITY,
                message="A trusted user principal is required.",
                retryable=False,
            )

        if principal.role != "admin" or principal.is_active is not True:
            raise EvieAiDomainError(
                EvieAiErrorCode.PROJECT_SCOPE_FORBIDDEN,
                stage=EvieAiErrorStage.AUTHORIZATION,
                message="EvieAi project scope requires an active admin principal.",
                retryable=False,
            )

        return True
