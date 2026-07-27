"""EvieAi Slice 5 API 安全前置组件的公共边界。"""

from __future__ import annotations


EVIE_AI_API_PREFIX = "/api/evie-ai/"


def is_evie_ai_api_path(path: str) -> bool:
    """判断路径是否属于需要 Slice 5 适配的 EvieAi API 命名空间。"""

    return isinstance(path, str) and path.startswith(EVIE_AI_API_PREFIX)
