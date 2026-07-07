"""页面 Hook 基类。

每个页面可以有独立的 PageHook 子类来处理该页面专属逻辑，
如密码可见性切换、特殊前置条件、额外断言等。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PageHook(ABC):
    """页面级钩子基类。

    子类需实现 page_code 返回匹配的页面标识。
    可覆盖以下方法：
      - setup_precondition_steps: 为前置条件补 UI 建立步骤
      - post_click_assertions: 在 click 步骤后补充额外断言
    """

    @property
    @abstractmethod
    def page_code(self) -> str:
        """此 Hook 对应的页面 code（如 'login'）。"""
        ...

    def setup_precondition_steps(self, precondition: str) -> list[dict[str, Any]]:
        """为前置条件生成 UI 建立步骤（默认无）。"""
        _ = precondition
        return []

    def post_click_assertions(
        self, element_code: str, expected: str
    ) -> list[dict[str, Any]]:
        """在 click 步骤后补充的断言步骤（默认无）。"""
        _ = element_code, expected
        return []
