"""为 EvieAi API 请求构造可信的 channel 上下文。"""

from __future__ import annotations


class RequestChannelContext:
    def execute(self) -> str:
        return "api"
