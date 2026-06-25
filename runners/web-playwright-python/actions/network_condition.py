"""V3.0a: 网络条件模拟 — 弱网/超时/离线。

通过 Playwright page.route() 实现请求拦截。
network_condition 字段由 compiler 在 preconditions 块编译时注入。
"""

import time


def _slow_handler(route):
    """模拟弱网：延迟 200ms 后继续请求。"""
    time.sleep(0.2)
    route.continue_()


def _timeout_handler(route):
    route.abort("timedout")


def _offline_handler(route):
    route.abort()


_HANDLERS = {
    "timeout": _timeout_handler,
    "slow": _slow_handler,
    "offline": _offline_handler,
}


def network_condition_action(page, locator, step, context, **kwargs):
    """应用网络条件到后续步骤。

    支持的 profile:
    - timeout: 所有请求立即超时 (abort="timedout")
    - slow: 所有请求延迟 200ms (模拟弱网)
    - offline: 所有请求中断 (abort)
    """
    profile = str(step.get("network_condition", "")).strip()
    if not profile:
        return

    handler = _HANDLERS.get(profile)
    if handler is None:
        return

    page.route("**/*", handler)
    # Note: Playwright route handlers persist until page close.
    # page fixture is function-scoped → each test gets a fresh page.
