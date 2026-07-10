# ATP 断言模板系统设计方案

**日期**：2026-07-11
**目标**：消除硬编码 token 匹配，用 PageObject 断言目录替代自然语言推测，达到大厂标准
**原则**：从自然语言推测 → 基于测试资产的确定性映射

---

## 一、当前问题

```text
现状：
  expected_result (自然语言)
    → token 匹配 ("成功登录", "跳转到首页", ...)
      → 匹配到了 → 生成断言
      → 没匹配到 → 零断言

问题：
  1. token 是硬编码常量，不可扩展不可维护
  2. "跳转至工作台首页" vs "跳转到首页" — 一字之差就不匹配
  3. 正向场景 token 只有 4 个，覆盖率极低
  4. 每个被测系统的预期表达方式不同，无法通用
```

## 二、目标架构：三层断言生成

```text
第 1 层: AI 输出结构化 TestIntent
  {
    scenario: "positive",
    expected_behavior: "authenticated_and_redirected"
  }
  ↑ AI 只输出行为语义，不输出具体断言值

第 2 层: PageObject 断言模板目录
  login 页面:
    authenticated_and_redirected → [
      {action: assert_url, value: "/home"},
      {action: assert_visible, target: "dashboard"},
      {action: db_exists, entity: "session", condition: {user_id: "{{user_id}}"}}
    ]
    auth_rejected → [
      {action: assert_text, target: "error-toast", contains: ""},
      {action: db_not_exists, entity: "session"}
    ]
    input_validation_triggered → [
      {action: assert_text, target: "error-toast"},
      {action: assert_visible, target: "login-page"}
    ]
  ↑ 由平台管理员/QA 维护，是确定性知识

第 3 层: 断言编译器（确定性映射）
  expected_behavior → 查 PageObject → 返回断言模板 → 编译器填充变量 → DSL
  ↑ 不推测，不匹配文本，只做确定性查找
```

## 三、核心数据模型

### 3.1 AssertionTemplate — 页面断言模板

```python
# 存储在 PageObject 的 assertion_templates 字段中 (JSON)

class AssertionTemplate:
    """一条断言模板：确定的 action + target + value"""
    action: str               # "assert_url" | "assert_visible" | "assert_text" | "db_exists" | "db_not_exists"
    target: str = ""          # element_code, 如 "error-toast" | "dashboard"
    value: str = ""           # 期望值, 如 "#/home"
    operator: str = "eq"      # "eq" | "contains" | "not_empty" | "exists"
    description: str = ""     # 人类可读说明, 如 "验证跳转到首页"

class BehaviorAssertionSet:
    """某个 expected_behavior 对应的断言集"""
    expected_behavior: str    # "authenticated_and_redirected"
    label: str                # 人类可读标签, 如 "认证成功并跳转"
    assertions: list[AssertionTemplate]

class PageAssertionConfig:
    """PageObject 的完整断言配置"""
    page_code: str            # "login"
    page_url: str             # "http://...#/login"
    behaviors: list[BehaviorAssertionSet]
```

### 3.2 存储方式

```text
方案 A (推荐): PageObject 新增 assertion_templates JSON 字段
  优点: 配置和页面在一起，维护方便
  缺点: 需要前端新增"断言模板管理"页面

方案 B: 独立断言模板表
  优点: 独立管理
  缺点: 多一层关联

选方案 A — 断言模板是页面的一部分。
```

### 3.3 数据示例

```json
// login PageObject.assertion_templates
{
  "behaviors": [
    {
      "expected_behavior": "authenticated_and_redirected",
      "label": "认证成功并跳转到首页",
      "scenarios": ["positive"],
      "assertions": [
        {"action": "assert_url", "value": "/home", "description": "验证跳转到首页"},
        {"action": "assert_visible", "target": "dashboard", "description": "验证首页元素可见"},
        {"action": "assert_visible", "target": "user-info", "description": "验证用户信息显示"}
      ]
    },
    {
      "expected_behavior": "auth_rejected",
      "label": "认证被拒绝",
      "scenarios": ["negative", "boundary"],
      "assertions": [
        {"action": "assert_text", "target": "error-toast", "operator": "contains", "description": "验证错误提示出现"},
        {"action": "db_not_exists", "entity": "session", "description": "验证未创建会话"}
      ]
    },
    {
      "expected_behavior": "input_validation_triggered",
      "label": "输入校验被触发",
      "scenarios": ["negative"],
      "assertions": [
        {"action": "assert_text", "target": "error-toast", "operator": "not_empty", "description": "验证校验提示出现"},
        {"action": "assert_visible", "target": "login-page", "description": "验证未离开登录页"}
      ]
    },
    {
      "expected_behavior": "account_locked",
      "label": "账号被锁定",
      "scenarios": ["negative"],
      "assertions": [
        {"action": "assert_text", "target": "error-toast", "operator": "contains", "description": "验证锁定提示出现"},
        {"action": "assert_visible", "target": "login-page", "description": "验证未离开登录页"}
      ]
    }
  ]
}
```

## 四、对比：token 匹配 vs 断言模板

| 维度 | token 匹配 (旧) | 断言模板 (新) |
|------|---------------|-------------|
| 断言来源 | 自然语言文本推测 | PageObject 确定性配置 |
| 维护方式 | 改 constants.py 代码 | 前端页面配置 JSON |
| 准确性 | 取决于预期文本写法 | 确定性，不推测 |
| 可扩展性 | 新增 token 需改代码 | 前端新增模板即可 |
| 覆盖率 | 正向场景 4 个 token | 每个 behavior 一组断言 |
| 适用性 | 只适合单一被测系统 | 每个页面独立配置 |

## 五、实施计划

### Phase 1: 数据模型 + 兼容 (0.5 天)

```text
1. PageObject 模型新增 assertion_templates JSON 字段
2. 为 login 页面创建初始断言模板（4 个 behavior）
3. structurer 增加新路径:
   if PageObject.assertion_templates 存在:
     使用模板生成断言
   else:
     使用现有 token 匹配（降级兼容）
```

### Phase 2: 前端管理界面 (1 天)

```text
1. 页面对象详情页新增"断言模板"标签页
2. 列表展示当前页面的所有 behavior + 断言
3. 新增/编辑/删除断言模板
4. 模板预览：展示生成的 DSL 格式
```

### Phase 3: AI 输出 expected_behavior (1 天)

```text
1. Requirement Parser 输出增加 expected_behavior 字段
2. AI prompt 约束: 从页面配置的 behavior 列表中选择，不能随意创造
3. 人审确认环节展示选中的 behavior 和对应断言
```

### Phase 4: 移除硬编码 token (0.5 天)

```text
1. 所有 PageObject 配置完断言模板后
2. 删除 constants.py 中的 ASSERT_*_TOKENS
3. structurer 移除 token 匹配分支
```

## 六、当前 Login 页面的断言模板初始化

```text
需要定义的 behaviors:

  authenticated_and_redirected    ← 替换 token: "成功登录", "跳转到首页"
    断言: assert_url:#/login, assert_visible:首页元素

  input_validation_triggered     ← 替换 token: "提示", "请输入"
    断言: assert_text(error-toast, not_empty), assert_visible(login-page)

  auth_rejected                  ← 替换 token: "错误", "失败"
    断言: assert_text(error-toast, contains), assert_visible(login-page)

  access_redirected              ← 替换 token: "拦截", "登录页面"
    断言: assert_url:#/login
```

## 七、验收标准

```text
✅ token 匹配代码从 structurer 中移除
✅ 20 个 login 测试点全部通过断言模板生成
✅ intent-01 正向用例不再零断言
✅ 新被测系统可通过前端配置断言模板，不需要改代码
✅ 旧数据（无断言模板的页面）降级使用 token 匹配兼容
```
