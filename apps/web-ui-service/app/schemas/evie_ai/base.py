"""EvieAi Phase 0 Schema 公共配置和稳定 ID 格式。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"


class EvieAiSchema(BaseModel):
    """拒绝未声明字段，避免机器执行字段渗入资产契约。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvieAiReadSchema(EvieAiSchema):
    """允许从 ORM 或显式投影读取的响应契约。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        from_attributes=True,
    )
