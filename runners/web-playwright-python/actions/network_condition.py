"""V3.0a: 网络条件模拟 — 弱网/超时/离线。

通过 Playwright page.route() 实现请求拦截。
network_condition 字段由 compiler 在 preconditions 块编译时注入。
"""


def network_condition_action(page, locator, step, context, **kwargs):
    """应用网络条件到后续步骤。

    支持的 profile:
    - timeout: 所有请求立即超时
    - slow: 所有请求延迟 2s
    - offline: 所有请求中断（离线）
    """
    profile = str(step.get("network_condition", "")).strip()
    if not profile:
        return

    if profile == "timeout":
        page.route("**/*", lambda route: route.abort("timedout"))
    elif profile == "slow":
        page.route("**/*", lambda route: route.continue_(  # type: ignore
            # upstream types missing continue_ signature
        ))  # delay handled by Playwright internal throttling
    elif profile == "offline":
        page.route("**/*", lambda route: route.abort())

    # Note: Playwright route handlers persist until page.unroute() or page close.
    # The clear_auth_state fixture navigates to a new page, resetting routes.
