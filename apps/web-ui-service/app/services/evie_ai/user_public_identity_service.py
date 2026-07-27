"""EvieAi 服务使用的可信用户 principal 基元。"""

from __future__ import annotations

from dataclasses import dataclass

from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)
from app.models.user import User
from app.policies.evie_ai.user_identity_policy import is_valid_user_public_id


@dataclass(frozen=True)
class TrustedUserPrincipal:
    # 下游 EvieAi 安全组件只能使用稳定的公共身份。
    user_public_id: str
    role: str
    is_active: bool


class UserPublicIdentityService:
    def execute(self, user: User) -> TrustedUserPrincipal:
        # 认证可返回有效 ORM User，但其公共身份字段仍可能已损坏。
        user_public_id = user.user_public_id
        if not isinstance(user_public_id, str) or not is_valid_user_public_id(
            user_public_id
        ):
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.IDENTITY,
                message="A valid stable user public identity is required.",
                retryable=False,
            )

        return TrustedUserPrincipal(
            user_public_id=user_public_id,
            role=user.role,
            is_active=user.is_active,
        )
