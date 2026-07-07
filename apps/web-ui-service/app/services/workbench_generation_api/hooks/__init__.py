"""页面级 Hook 子模块。

提供可插拔的页面特殊逻辑处理，避免通用步骤结构化引擎中
出现页面专属硬编码（如登录页的密码可见性切换）。
"""

from .base import PageHook
from .login_password_visibility import LoginPasswordVisibilityHook

__all__ = ["PageHook", "LoginPasswordVisibilityHook"]
