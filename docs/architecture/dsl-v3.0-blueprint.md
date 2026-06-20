# DSL V3.0 目标蓝图

> 2026-06-20 起草。当前 DSL 版本为 V1.1。此文档描述下一个大版本的目标形态，**不作为当前实现参考**。

## 示例用例：密码错误校验

```json
{
  "dsl_version": "3.0",
  "case": {
    "id": "LOGIN_001",
    "name": "账号密码登录-密码错误校验",
    "domain": "user_center",
    "module": "login",
    "sub_module": "password_login",
    "priority": "P0",
    "risk_level": "HIGH",
    "tags": ["login", "security", "validation"]
  },
  "scenario": {
    "intent": "wrong_password_validation",
    "business_goal": "验证密码错误时系统的正确处理逻辑",
    "test_type": ["functional", "security"],
    "risk_points": ["暴力破解", "账号枚举"]
  },
  "actors": {
    "user": { "role": "normal_user" }
  },
  "environment": {
    "env": "test",
    "network_profile": "normal",
    "feature_flags": ["login_v2"]
  },
  "preconditions": [
    {
      "type": "user_exist",
      "user_ref": "user_001",
      "setup_action": "create_user",
      "params": {
        "username": "$test_data.user_001.username",
        "password": "$test_data.user_001.password",
        "status": "active"
      }
    }
  ],
  "test_data": {
    "user_001": {
      "username": "auto_user",
      "password": "CorrectPass123"
    },
    "input": {
      "username": "auto_user",
      "password": "WrongPass123"
    }
  },
  "business_flow": {
    "flow_id": "login_flow",
    "steps": ["input_username", "input_password", "click_login"]
  },
  "execution_plan": [
    {
      "id": "step_1",
      "action": "input",
      "target": {
        "page": "login_page",
        "locator": "username_input"
      },
      "value": "$test_data.input.username"
    },
    {
      "id": "step_2",
      "action": "input",
      "target": {
        "page": "login_page",
        "locator": "password_input"
      },
      "value": "$test_data.input.password"
    },
    {
      "id": "step_3",
      "action": "click",
      "target": {
        "page": "login_page",
        "locator": "login_button"
      }
    },
    {
      "id": "step_4",
      "action": "wait",
      "condition": {
        "type": "element_visible",
        "target": { "page": "login_page", "locator": "error_toast" }
      },
      "timeout_ms": 5000
    },
    {
      "id": "step_5",
      "action": "http_request",
      "method": "GET",
      "url": "/api/user/login-attempts?username=$test_data.input.username",
      "headers": {
        "Authorization": "Bearer $env.api_key"
      },
      "extract": {
        "fail_count": "$response.body.fail_count"
      }
    }
  ],
  "assertions": [
    {
      "id": "assert_http",
      "type": "api",
      "check": "response_code",
      "expected": 401,
      "on_fail": "continue"
    },
    {
      "id": "assert_ui_toast",
      "type": "ui",
      "check": "toast",
      "expected": "用户名或密码错误",
      "on_fail": "continue"
    },
    {
      "id": "assert_db_increment",
      "type": "db",
      "check": "login_fail_count",
      "params": {
        "username": "$test_data.input.username"
      },
      "expected_increment": 1,
      "on_fail": "continue"
    },
    {
      "id": "assert_user_status",
      "type": "business",
      "check": "user_status",
      "expected": "active",
      "on_fail": "abort"
    },
    {
      "id": "assert_no_enum",
      "type": "ai_semantic",
      "prompt": "分析以下提示语是否存在账号枚举风险：{toast_text}",
      "expected": "NO",
      "on_fail": "continue"
    },
    {
      "id": "composite_security",
      "type": "composite",
      "operator": "AND",
      "on_fail": "abort",
      "conditions": [
        {
          "type": "api",
          "check": "response_code",
          "expected": 401
        },
        {
          "type": "ai_semantic",
          "prompt": "响应体是否泄露了用户是否存在的信息",
          "expected": "NO"
        }
      ]
    }
  ],
  "coverage": {
    "requirement_ids": ["REQ_LOGIN_001"],
    "risk_points": ["password_error", "account_security"]
  },
  "observability": {
    "logs": true,
    "trace": true,
    "screenshots": true,
    "video_recording": true
  },
  "rollback": [
    {
      "action": "reset_login_fail_count",
      "params": {
        "username": "$test_data.user_001.username"
      },
      "on": "always"
    },
    {
      "action": "delete_user",
      "params": {
        "username": "$test_data.user_001.username"
      },
      "on": "test_success"
    }
  ]
}
```

## V1.1 → V3.0 新增能力

| 层次 | V1.1 现状 | V3.0 目标 | 新增 |
|------|----------|----------|------|
| 元数据 | project/module/title | + domain/sub_module/risk_level | 领域分类、风险等级 |
| 场景 | intent_id/intent_type | + business_goal/test_type[]/risk_points[] | 业务目标、风控点 |
| 角色 | 无 | actors + role | **完全新能力** |
| 环境 | 硬编码 URL | env/network_profile/feature_flags | 多环境支持 |
| 前置条件 | 纯文本字符串 | 结构化 setup_action + params | **结构性升级** |
| 变量 | `{{var}}` 单层 | `$test_data.xxx.yyy` 两级 | 变量解析引擎 |
| 步骤 | input/click/goto/wait | + http_request + extract + condition | API调用、变量提取 |
| 断言 | assert_visible/text/url (仅UI) | api/ui/db/business/ai_semantic/composite (6种) | **维度升级** |
| 覆盖 | requirement.source_asset_id | requirement_ids[]/risk_points[] | 需求追溯 |
| 可观测 | 隐式(pytest) | 声明式配置 | 声明式 |
| 回滚 | 无 | rollback actions | **完全新能力** |

## 对虚假通过问题的覆盖

当前 24 条 login 用例虚假通过根因分布：

```
67% — 断言弱 (只有 assert_url)        → 质量门 RULE_003 可拦截  ✅
33% — 数据缺失 (data 字段不完整)       → 质量门 RULE_002 可拦截  ✅
~15% — 前置条件不可执行 (纯文本)       → DSL V3.0 preconditions   ← V3.0 可解决
~10% — AI 幻觉/模板残留                → 质量门 RULE_016 (桩)
```

DSL V3.0 主要解决的是前置条件结构化问题（~15%），而非断言和数据完整性问题（83%+）。

## 成本估算

| 模块 | 预计工时 |
|------|---------|
| 元数据/场景/角色/环境 | 2-3 周 |
| 前置条件引擎 (Setup Hook) | 3-4 周 |
| 变量系统升级 | 2-3 周 |
| API/DB 断言 | 3-4 周 |
| AI 语义断言 | 2-3 周 |
| 回滚引擎 | 2-3 周 |
| **合计** | **3-5 月（单人全职）** |

## 决策建议

- V3.0 是**架构升级目标**，不是解决当前 20 条虚假通过问题的工具
- **当前优先**：质量门规则验证 + 补全 → 确认拦截率 → 再决定 DSL 升级范围
- **最值得先从 V3.0 拆出来的模块**：`preconditions` 结构化（直接解决 3 条用例的前置条件不可执行问题）
