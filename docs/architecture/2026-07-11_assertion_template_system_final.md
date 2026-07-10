# ATP 断言模板系统 — 最终方案 v2.0

**日期**：2026-07-11
**版本**：v2.0（补充 execution_layer / behavior_version / audit_log / context_filter）
**原则**：AI 负责意图分类，系统负责行为映射，断言来自配置而非推测

---

## 一、核心架构

```text
                 Requirement (自然语言)

                        │
                        ▼
              AI Intent Parser

              输出: intent_type + scenario
              例: {intent_type: "AUTH_LOGIN", scenario: "negative"}

                        │
                        ▼
              Behavior Resolver (确定性规则)

              intent + scenario + page + context_filter
              → behavior_code + capability list

                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   Page Behavior   Domain Behavior  (No Config → WARNING)

                        │
                        ▼
              Assertion Template Registry

              behavior_code + version + execution_layer
              → assertions[] (含变量模板)

                        │
                        ▼
              Variable Resolver

              {{home_url}} → env | {{test_user.id}} → DataPool

                        │
                        ▼
              Assertion Compiler

              template + context → 可执行 DSL

                        │
                        ▼
              Test Runner

                        │
                        ▼
              Assertion Result + Audit Log
```

---

## 二、AI 边界

```text
AI 做的事:
  ✅ 理解自然语言 → 分类 intent_type + scenario
     "正确密码登录成功" → {intent_type: "AUTH_LOGIN", scenario: "positive"}
     "错误密码提示错误" → {intent_type: "AUTH_LOGIN", scenario: "negative"}
     "管理员登录后台"   → {intent_type: "AUTH_LOGIN", scenario: "positive", context: {role: "admin"}}

AI 不做的事:
  ❌ 输出 behavior_code 枚举值
  ❌ 输出具体断言
  ❌ 输出测试数据

IntentType 粒度控制:
  正确: AUTH_LOGIN, AUTH_LOGOUT, INPUT_VALIDATION, PASSWORD_VISIBILITY, RATE_LIMIT
  错误: AUTH_LOGIN_WRONG_PASSWORD, AUTH_LOGIN_USERNAME_EMPTY (太细, 变成硬编码)
  
  区分方式: intent_type 只表达"什么业务动作", scenario 表达"正/负/边界",
           condition 表达具体条件(如 credential_invalid, field_empty)
```

---

## 三、Behavior Capability — 可组合断言

```text
behavior 不是单一断言集合，而是 capability 组合：

  AUTH_LOGIN_SUCCESS:
    capabilities: [SESSION_CREATED, PAGE_REDIRECTED, TOKEN_STORED]

  AUTH_LOGIN_FAILED:
    capabilities: [ERROR_DISPLAYED, SESSION_NOT_CREATED]

  USER_REGISTER_SUCCESS:
    capabilities: [USER_CREATED, SESSION_CREATED, PAGE_REDIRECTED]
    ↑ SESSION_CREATED 可复用

每个 capability 对应一组 assertion_template:
  SESSION_CREATED → [{layer: "database", action: "db_exists", entity: "session"}]
  PAGE_REDIRECTED → [{layer: "ui", action: "assert_url", value: "{{home_url}}"}]
  ERROR_DISPLAYED → [{layer: "ui", action: "assert_text", target: "error-toast", operator: "not_empty"}]
```

---

## 四、Behavior Registry — 三级查找

```text
┌─────────────────────────────────────────────────────────────┐
│                     Behavior Registry                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  查找优先级（context_filter 参与匹配）:                        │
│                                                              │
│  Level 1: Page-level Assertion Template                      │
│    scope=page, page_code=login                               │
│    最高优先级，针对特定页面 + 特定 context 定制                 │
│                                                              │
│  Level 2: Domain-level Assertion Template                    │
│    scope=domain, domain=auth                                 │
│    跨页面通用默认断言                                         │
│                                                              │
│  Level 3: No Assertion Configuration                         │
│    status: WARNING                                           │
│    reason: "AUTH_LOGIN_SUCCESS has no assertion template"     │
│    不生成断言，不猜测，提示配置缺失                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、Context Filter（Resolver 组合匹配）

```text
匹配优先级:
  page + context 完全匹配 → 最高
  page 匹配, context 无 → 次高
  domain + context 匹配 → 第三
  domain 匹配, context 无 → 第四
  无匹配 → Level 3 (WARNING)

示例:
  intent: AUTH_LOGIN, scenario: positive, context: {role: "admin"}
  
  查找:
    1. login page + role=admin → 无
    2. login page + 无context → 命中 → AUTH_LOGIN_SUCCESS
    3. 使用 page-level 默认模板
```

---

## 六、数据模型

### behavior_registry

```sql
id              SERIAL PRIMARY KEY
behavior_code   VARCHAR(120)    -- "AUTH_LOGIN_SUCCESS"
intent_type     VARCHAR(80)     -- "AUTH_LOGIN"
scenario        VARCHAR(20)     -- "positive" | "negative" | "boundary"
scope           VARCHAR(20)     -- "page" | "domain"
page_code       VARCHAR(40)     -- 仅 scope=page
domain          VARCHAR(40)     -- 仅 scope=domain, 如 "auth"
context_filter  JSONB           -- {"role": "admin"} 或 null
version         INTEGER         -- 1, 2, 3...
status          VARCHAR(20)     -- "active" | "draft" | "deprecated"
priority        INTEGER         -- 1=最高, 3=最低
label           VARCHAR(255)    -- 人类可读标签
capabilities    JSONB           -- ["SESSION_CREATED", "PAGE_REDIRECTED"]
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### assertion_template

```sql
id              SERIAL PRIMARY KEY
behavior_id     INTEGER FK      -- → behavior_registry.id
capability      VARCHAR(80)     -- "SESSION_CREATED" 或 null
execution_layer VARCHAR(20)     -- "ui" | "api" | "database" | "storage"
action          VARCHAR(80)     -- "assert_url" | "assert_visible" | "db_exists" | ...
target          VARCHAR(255)    -- element_code, 如 "error-toast"
operator        VARCHAR(40)     -- "eq" | "contains" | "not_empty" | "exists"
value           TEXT            -- 支持 {{variable}} 模板
variable_schema JSONB           -- {"home_url": "env", "test_user.id": "datapool"}
description     TEXT
created_at      TIMESTAMP
```

### assertion_execution_log（审计追溯）

```sql
id                  SERIAL PRIMARY KEY
test_case_id        VARCHAR(64)
behavior_code       VARCHAR(120)
behavior_version    INTEGER
source              VARCHAR(20)     -- "page_level" | "domain_level" | "not_configured"
compiled_assertions JSONB
execution_result    JSONB
executed_at         TIMESTAMP
```

---

## 七、变量系统

```text
来源 1: Environment Config
  {{home_url}} → 环境变量 ATP_ENV_HOME_URL
  {{api_base}} → 环境变量 ATP_SUT_BASE_URL

来源 2: Test Data
  {{test_user.username}} → DataPool 查询
  {{test_user.id}} → DataPool 查询

来源 3: Runtime Context
  {{response.token}} → API 响应提取
  {{user_id}} → setup 步骤获取

来源 4: Test Case Metadata
  {{case.project}} → 当前测试用例的 project_code
```

---

## 八、Audit Log（Phase 1 必须实现）

```text
每次断言生成时记录：

  输入:
    intent_type: "AUTH_LOGIN"
    scenario: "positive"
    page_code: "login"
    context_filter: null

  解析:
    behavior_code: "AUTH_LOGIN_SUCCESS"
    source: "page_level"
    template_version: 1
    capabilities: ["SESSION_CREATED", "PAGE_REDIRECTED"]

  输出:
    3 assertions generated

  目的:
    - 出现问题可追溯
    - 版本变更可回溯
    - AI 调优需要历史数据
```

---

## 九、实施计划

```text
Phase 0: Behavior Registry 定义（0.5 天）
  - intent_type 枚举: AUTH_LOGIN, INPUT_VALIDATION, PASSWORD_VISIBILITY, ...
  - behavior_code 枚举: AUTH_LOGIN_SUCCESS, AUTH_LOGIN_FAILED, AUTH_INPUT_INVALID, AUTH_ACCESS_BLOCKED
  - intent + scenario → behavior 映射规则
  - 数据模型建表
  - AI 不参与

Phase 1: Resolver + Compiler + Audit Log（1 天）
  - BehaviorResolver: intent+scenario+page+context → behavior_code
  - AssertionCompiler: templates + variables → DSL
  - AuditLog: 记录每次解析过程
  - login 页面初始化 4 个 behavior 模板

Phase 2: 迁移 login（0.5 天）
  - 20 个 case 100% 通过模板生成
  - intent-01 不再零断言
  - 116 个测试全部通过

Phase 3: 前端管理界面（1 天）

Phase 4: AI intent_type 输出（1 天）

Phase 5: 删除 token matcher（0.5 天）

Phase 6: Domain-level fallback（0.5 天）
```

## 十、验收标准

```text
✅ token matcher 代码完全移除
✅ login 20 case 100% 通过模板生成
✅ intent-01 → AUTH_LOGIN_SUCCESS → 3+ assertions
✅ 同一场景不同自然语言写法 → 同一 behavior_code
✅ AI 输出非法 intent_type → 被拒绝
✅ 新页面无需代码修改
✅ behavior 版本可追溯
✅ 断言生成过程有 audit log
✅ 116 tests 全部通过
```
