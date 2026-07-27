"""EvieAi 请求的可信内部 trace 上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.errors.evie_ai import (
    EvieAiDomainError,
    EvieAiErrorCode,
    EvieAiErrorStage,
)


@dataclass(frozen=True)
class RequestTraceContext:
    """保存现有 request_id 和仅供服务端使用的 correlation_id。"""

    request_id: str
    correlation_id: str

    @classmethod
    def from_request_id(cls, request_id: str) -> "RequestTraceContext":
        if not isinstance(request_id, str) or not request_id.strip():
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.REQUEST_VALIDATION,
                message="A trusted request identifier is required.",
                retryable=False,
            )

        correlation_id = uuid4().hex
        if not correlation_id:
            raise EvieAiDomainError(
                EvieAiErrorCode.DATA_INTEGRITY_ERROR,
                stage=EvieAiErrorStage.REQUEST_VALIDATION,
                message="A trusted correlation identifier is required.",
                retryable=False,
            )

        return cls(
            request_id=request_id.strip(),
            correlation_id=correlation_id,
        )
