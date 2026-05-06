# Dify 工作流提示词规范

这份文档用于把平台规则收敛到 Dify 工作流里，避免每个节点各写各的、各猜各的。

## 1. 开始节点输入规范

### 必填字段

- `project`
- `page`
- `requirement`

### 建议字段

- `source`
- `input_sources`
- `prd_text`
- `user_story`
- `openapi_spec`
- `runtime_logs`
- `page_urls`

### 约束

- `project` 必须是明确项目编码
- `page` 必须是明确页面编码
- `requirement` 必须是完整需求正文
- 不允许用自然语言模糊猜测字段值

### 推荐输入示例

```json
{
  "project": "atp",
  "page": "login",
  "requirement": "业务目标：实现平台用户的身份验证登录功能...",
  "source": "manual"
}
```

## 2. LLM1 测试点规范

### 输入

- `project`
- `page`
- `requirement`
- 知识库检索结果
- 页面对象摘要
- 元素别名表

### 输出要求

- 必须输出结构化 JSON
- 不允许输出散文
- 不允许依赖标题推断步骤
- 找不到元素时直接标记 `block`

### 推荐顶层结构

```json
{
  "version": "RequirementSpecV1",
  "project": "atp",
  "page": "login",
  "source_type": "manual",
  "design_input": "",
  "parse_confidence": 0.0,
  "test_intents": [],
  "ambiguities": [],
  "coverage_matrix": [],
  "warnings": []
}
```

### `test_intents` 推荐字段

```json
{
  "intent_id": "intent-01",
  "title": "首次登录成功",
  "intent_type": "functional",
  "priority": "P0",
  "target": "home_menu",
  "expected_result": "跳转到首页",
  "involved_elements": ["账号输入框", "密码输入框", "登录按钮"],
  "steps_hint": [
    {"action": "input", "target": "账号输入框", "value": "test001"},
    {"action": "input", "target": "密码输入框", "value": "123456"},
    {"action": "click", "target": "登录按钮"}
  ],
  "can_generate": true,
  "reasons": [],
  "unknown_elements": []
}
```

### 硬约束

- `steps_hint` 必须显式存在
- `input` 必须同时带 `target` 和 `value`
- `click`、`assert_visible`、`assert_text` 必须带 `target`
- `assert_url` 必须带明确 URL
- 元素无法映射时，不允许猜测补齐

## 3. LLM2 / LLM3 结构化输出规范

## LLM2: 测试点转 DSL

### 输入

- `LLM1 test_intents`
- 页面对象
- 元素映射

### 输出

```json
{
  "version": "TestDslV1",
  "project": "atp",
  "page": "login",
  "dsl_cases": [
    {
      "intent_id": "intent-01",
      "steps": [
        {"action": "input", "target": "username_input", "value": "test001"},
        {"action": "input", "target": "password_input", "value": "123456"},
        {"action": "click", "target": "login_button"},
        {"action": "assert_visible", "target": "home_menu"}
      ]
    }
  ],
  "warnings": []
}
```

### 约束

- 只允许显式动作
- `input` 必须有 `target` 和 `value`
- `click`、`wait`、`assert_visible`、`assert_text` 必须有 `target`
- 不能输出模糊口语描述
- 不能生成平台不存在的元素名

## LLM3: DSL 转 Playwright 代码

### 输入

- `LLM2 dsl_cases`
- 页面对象
- 代码模板约束

### 输出

```json
{
  "version": "PlaywrightCodeV1",
  "project": "atp",
  "page": "login",
  "artifacts": [
    {
      "file_name": "login.spec.ts",
      "framework": "playwright",
      "language": "typescript",
      "code": "..."
    }
  ],
  "warnings": []
}
```

### 约束

- 只能基于 DSL 生成，不允许重新发明步骤
- 不允许猜 selector
- 不允许补不存在的元素名
- 如果页面对象缺失，返回 `blocked` 或 `needs_review`
- 输出必须可以直接落文件

## 4. 接入原则

- 节点之间只传结构化 JSON
- 任何一步丢失 `target` 都应视为失败
- 不允许通用兜底替代显式映射
- 不允许用自然语言“看起来合理”来绕过规则

