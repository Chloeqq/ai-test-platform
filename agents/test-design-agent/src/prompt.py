from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """
你是 test-design-agent。
你的职责是根据输入需求输出“可解析的 JSON 对象”。

硬性要求：
1. 只输出一个 JSON 对象，不要输出 Markdown 代码块，不要解释文本。
2. 只基于用户输入和页面元素上下文生成，不要使用本地规则假设。
3. 必须保证字段结构完整、类型可解析。
4. 如果上一次输出有结构错误，必须按错误信息修复后再输出。

生成规则（必须严格遵守）：
1. 一个用例只对应一个测试意图，不合并多个场景。
2. 步骤必须是真实可执行操作：fill / click / wait_for / assert_visible / assert_text，禁止出现连续重复 login。
3. 每个用例只包含一个核心验证点，禁止把登录成功、为空提示、错误提示、长度超限写在同一个用例里。
4. execution.steps 必须是真实流程，不生成无意义的 intent-01～intent-99。
5. 输出结构必须严格遵循给定 JSON 结构，不扩展、不脑补、不乱加字段。
6. 只根据当前传入的“单一测试意图”生成对应一条用例，不主动扩展其他场景。
""".strip()


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_generate_prompt(*, requirement: str, page: str, page_elements: list[str]) -> str:
    return f"""
请根据以下信息生成测试用例 JSON（不是 YAML）：

[Input]
page: {page}
requirement:
{requirement}

page_elements:
{_json_block(page_elements)}

[Output Contract]
必须输出一个 JSON 对象，且包含这些顶层字段：
- version (string)
- id (string, non-empty)
- title (string, non-empty)
- module (string, non-empty)
- priority (string, non-empty)
- tags (string array)
- owner (string)
- status (string)
- description (string)
- requirement (string array)
- data (object，值必须是 array；如无需测试数据请输出 {{}})
- execution (object)

execution 必须包含：
- runner (string)
- page (string, non-empty)
- variables (object)
- steps (array, at least 1)

steps 每项必须包含：
- action (string, non-empty)
可选：
- target
- value

额外约束：
- 一个用例只做一件事，只覆盖一个测试意图。
- action 仅允许：fill / click / wait_for / assert_visible / assert_text。
- 禁止连续重复 login。
- 禁止把“正常登录、空值、错误密码、长度限制”等不同场景合并到一个用例。
- execution.steps 必须是可执行真实流程，禁止输出 intent-01～intent-99 这类占位步骤。
- 可使用 version v4 风格字段（如 page_code/module_code/case_type/source），但不得新增无意义字段。

参考示例（仅用于约束结构与粒度，禁止照抄）：
{{
  "version": "v4",
  "id": "atp-web-login-auth-ex-ai-0002",
  "title": "登录页-登录认证-异常场景-登录超时提示",
  "module": "login",
  "priority": "P2",
  "tags": ["ai-generated", "exception", "login"],
  "owner": "qa-team",
  "status": "automated",
  "description": "验证弱网/服务超时情况下登录超时提示正常弹出",
  "requirement": [
    "测试意图：登录超时提示",
    "前置条件：登录页面已打开，模拟网络超时环境",
    "操作步骤：1.输入用户名 test001 2.输入密码 123456 3.点击登录按钮 4.等待接口超时",
    "预期结果：出现登录超时提示，按钮恢复可点击"
  ],
  "data": {{}},
  "execution": {{
    "runner": "playwright",
    "page": "login",
    "variables": {{}},
    "steps": [
      {{"action": "fill", "target": "username_input", "value": "test001"}},
      {{"action": "fill", "target": "password_input", "value": "123456"}},
      {{"action": "click", "target": "login_button"}},
      {{"action": "wait_for", "target": "timeout_toast"}},
      {{"action": "assert_visible", "target": "timeout_toast"}},
      {{"action": "assert_text", "target": "timeout_toast", "value": "登录超时，请稍后重试"}}
    ]
  }},
  "page_code": "login",
  "module_code": "auth",
  "case_type": "ex",
  "source": "ai"
}}

仅返回 JSON 对象。
""".strip()


def build_generate_repair_prompt(
    *,
    requirement: str,
    page: str,
    page_elements: list[str],
    previous_output: str,
    validation_error: str,
) -> str:
    return f"""
你上一次输出不符合结构要求，请修复并重新输出 JSON 对象。

[Original Input]
page: {page}
requirement:
{requirement}
page_elements:
{_json_block(page_elements)}

[Previous Output]
{previous_output}

[Validation Error]
{validation_error}

请严格修复上述错误，只返回修复后的 JSON 对象。
""".strip()


def build_bundle_prompt(
    *,
    requirement: str,
    page: str,
    requirement_spec: dict[str, Any],
    case: dict[str, Any] | None,
    page_elements: list[str],
) -> str:
    return f"""
请生成 TestDesignBundle JSON 对象。

[Input]
page: {page}
requirement:
{requirement}
page_elements:
{_json_block(page_elements)}
requirement_spec:
{_json_block(requirement_spec)}
existing_case:
{_json_block(case or {})}

[Output Contract]
必须输出一个 JSON 对象，且至少包含以下顶层 key：
- version (string)
- page (string)
- requirement (string array)
- requirement_spec (object)
- case (object, 使用 generate contract)
- test_points (object)
- traceability (object)
- review_summary (object)

可选：
- confidence (number)
- warnings (string array)
- requires_review (boolean)
- metadata (object)

只返回 JSON 对象。
""".strip()


def build_bundle_repair_prompt(
    *,
    requirement: str,
    page: str,
    requirement_spec: dict[str, Any],
    case: dict[str, Any] | None,
    page_elements: list[str],
    previous_output: str,
    validation_error: str,
) -> str:
    return f"""
你上一次输出的 design_bundle 不满足结构要求，请修复后重新输出 JSON 对象。

[Original Input]
page: {page}
requirement:
{requirement}
page_elements:
{_json_block(page_elements)}
requirement_spec:
{_json_block(requirement_spec)}
existing_case:
{_json_block(case or {})}

[Previous Output]
{previous_output}

[Validation Error]
{validation_error}

请仅返回修复后的 JSON 对象。
""".strip()
