"""EvieAi 请求正文的最小日志保护。"""

from __future__ import annotations

from app.services.evie_ai import is_evie_ai_api_path


class NaturalLanguageLoggingGuard:
    """对 EvieAi API 完全抑制请求正文预览。"""

    def execute(self, *, path: str, payload_preview: str) -> str:
        if is_evie_ai_api_path(path):
            return "[EvieAi request body suppressed]"
        return payload_preview
