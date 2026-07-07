"""页面级 Hook 子模块。

提供可插拔的页面特殊逻辑处理，避免通用步骤结构化引擎中
出现页面专属硬编码（如登录页的密码可见性切换）。

新增页面 Hook 只需:
  1. 继承 PageHook 实现子类
  2. 注册到 PAGE_HOOK_REGISTRY
"""

from .base import PageHook
from .login_password_visibility import LoginPasswordVisibilityHook

# 页面 Hook 注册表: page_code → Hook 类
# 新增页面时只需在此注册，无需修改 save_service
PAGE_HOOK_REGISTRY: dict[str, type[PageHook]] = {
    LoginPasswordVisibilityHook().page_code: LoginPasswordVisibilityHook,
}


def get_page_hook(page: str) -> PageHook | None:
    """根据 page code 返回对应的 PageHook 实例，无匹配返回 None。"""
    hook_cls = PAGE_HOOK_REGISTRY.get(page)
    return hook_cls() if hook_cls is not None else None


__all__ = ["PageHook", "LoginPasswordVisibilityHook", "PAGE_HOOK_REGISTRY", "get_page_hook"]
