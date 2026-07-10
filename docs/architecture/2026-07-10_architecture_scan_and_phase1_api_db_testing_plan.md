# ATP 架构扫描报告 + API Contract Driven Test MVP 建设计划

**日期**：2026-07-10（初版）/ 更新于同日（根据委员会决议调整范围）
**扫描范围**：全项目 `shared_backend/`、`apps/web-ui-service/`、`runners/`、`apps/ai-orchestrator/`
**目标**：扫描现有基础设施，评估 API + DB 测试能力缺口，设计 API Contract Driven Test MVP

> **⚠️ 范围已更新**：本文档的初始版本包含 ApiAsset 模型、BusinessAssertion→SqlGenerator、
> 10 个 Intent 等设计。经过反方审计和委员会决议后，Phase 1 范围已大幅缩小。
> **当前有效范围见第四章，被删除组件的回归策略见 `2026-07-10_mvp_redesign_committee_decision.md` 第 3.1 节。**

**相关文档**：
- `2026-07-10_ai_generated_test_case_quality_audit.md` — 审计报告
- `2026-07-10_api_db_testing_first_strategy.md` — API+DB 优先策略论证
- `2026-07-10_target_architecture_review_and_gap_analysis.md` — 目标架构评审
- `2026-07-10_adversarial_architecture_audit.md` — 反方架构审计
- `2026-07-10_mvp_redesign_committee_decision.md` — **委员会决议（最终范围）**

---

## 〇、产品定位重新定义

```text
之前定位: "AI 自动生成测试用例平台"
    问题: 容易被质疑"AI 生成的用例能跑吗？"

重新定位: "AI 驱动的智能测试编排平台"
    核心能力:
    1. AI 理解需求 → 输出 Test Intent
    2. 自动选择测试层级（API 80% / UI 20%）
    3. 基于测试资产（ApiAsset + PageObject + DataPool）生成可执行测试
    4. 多 Runner 执行（API / DB / UI）
    5. 自动判断失败归因（平台 Bug vs 被测系统 Bug）
    6. 反馈优化生成策略
```

---

## 一、当前架构全景

```text
┌──────────────────────────────────────────────────────────────────┐
│                         当前 ATP 架构（扫描结果）                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Router 层 (24 routers)                                     │  │
│  │  workbench_generation / workbench_assets / test_cases /    │  │
│  │  page_objects / quality_dashboard / quality_eval ...       │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                              │                                     │
│  ┌──────────────────────────▼─────────────────────────────────┐  │
│  │  Facade 层 (facade.py + facade_*.py)                        │  │
│  │  编排：generate_cases / run_case / review / gate / report   │  │
│  └──────┬───────────────────────┬──────────────────────────────┘  │
│         │                       │                                   │
│  ┌──────▼──────────┐  ┌─────────▼──────────────────────────────┐  │
│  │  Service 层      │  │  Store 层 (线程安全 + DB/文件双模)       │  │
│  │  38 个 service   │  │  app.api.workbench.store              │  │
│  │                  │  │  → workbench_state_store               │  │
│  │  generation_     │  └──────────────────────────────────────┘  │
│  │  compiler (9个)  │                                              │
│  │  quality_gate    │                                              │
│  │  (17条规则)       │                                              │
│  │  workbench_      │                                              │
│  │  analysis/asset/ │                                              │
│  │  gate/review/    │                                              │
│  │  runtime         │                                              │
│  └──────┬───────────┘                                              │
│         │                                                          │
│  ┌──────▼──────────────────────────────────────────────────────┐  │
│  │  Repository 层 (12 repos)                                    │  │
│  │  TestCase / PageObject / Recorder / TestPoint /             │  │
│  │  TestPointAsset / TestDataPool / TestProject / User /       │  │
│  │  QualityEval / WorkbenchState / ...                         │  │
│  └──────┬──────────────────────────────────────────────────────┘  │
│         │                                                          │
│  ┌──────▼──────────────────────────────────────────────────────┐  │
│  │  Model 层 (11 models)                                        │  │
│  │  TestCase ★ / PageObject ★ / PageElement ★ / TestDataPool ★│  │
│  │  TestCaseExecution / TestCaseStep / TestCaseVersion /       │  │
│  │  WorkbenchState / QualityEval / TestProject / User          │  │
│  │  ★ = 已为 API/DB 测试预留字段但未使用                         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  shared_backend (19 modules)                                 │  │
│  │  execution_compiler ★ / data_pool_resolver /                │  │
│  │  element_binding / ir_schema_validator /                    │  │
│  │  quality_gate (engine + registry + rule_interface) /        │  │
│  │  schemas (models + contracts + validator)                   │  │
│  │  ★ = 只支持 UI action (input/click/goto/wait/login)          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Runner 层 (runners/web-playwright-python)                   │  │
│  │  actions/: 10 个 action (assert_* x6, click, fill, goto,   │  │
│  │            login, wait_for, network_condition)              │  │
│  │  executor/: base_executor (框架) + api_executor (骨架)       │  │
│  │            + ui_executor                                    │  │
│  │  runner/: action_registry, data_expander, locator_resolver  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  AI Orchestrator 层 (apps/ai-orchestrator)                   │  │
│  │  8 Agent + FastAPI (2026-05 从 Flask 迁移)                   │  │
│  │  仅支持 UI 测试用例生成,  无 API/DB 测试生成能力               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、关键发现：已有基础设施远超预期

### ✅ 已存在且可直接复用

| 组件 | 位置 | 当前状态 | 复用价值 |
|------|------|---------|---------|
| **TestCase.test_type** | `models/test_case.py:43` | `default="ui"`，可扩展到 `"api"` | 一条用例同时支持 UI/API/DB 三种执行模式 |
| **TestCase.setup_sql** | `models/test_case.py:49` | `Text, default=""`，完全未使用 | DB 前置数据准备（后续改为 Business Assertion） |
| **TestCase.assert_sql** | `models/test_case.py:56` | `Text, default=""`，完全未使用 | DB 断言（后续改为 Business Assertion） |
| **TestCase.sut_service** | `models/test_case.py:41` | `String(120)`，完全未使用 | 被测服务名 → API Runner 路由到正确的 base URL |
| **PageElement.role** | `models/page_object.py:95` | `String(60), default=""` | Element Role 注册，已存在字段 |
| **TestDataPool + Item** | `models/test_data_pool.py` | 完整模型 + Repository + Service | 测试数据管理 |
| **data_pool_resolver** | `shared_backend/data_pool_resolver.py` | 统一的池解析 | 数据引用解析 |
| **BaseTestExecutor** | `runners/.../executor/base_executor.py` | 抽象基类 + ExecutionConfig/Result | 扩展 ExecutionResult |
| **Quality Gate 17 条规则** | `services/quality_gate/rules/` | RULE_001~017 | 后续扩展 API/DB 规则 |
| **Decision.REPAIR** | `shared_backend/quality_gate/models.py:38` | 已定义 | 反馈闭环数据模型 |
| **PRECONDITION_TYPES** | `shared_backend/quality_gate/models.py:71` | 已预留 `api_call`, `sql` | 前置条件可执行化类型系统 |

---

## 三、目标架构：Test Knowledge Layer

### 3.1 核心问题

大厂不会让 AI 直接生成 API DSL。中间必须有 **Test Knowledge Layer（测试知识层）**：

```text
错误模型（当前 ATP）:
  需求 → AI 猜测试点 → AI 猜断言 → 执行
  问题: 猜测链过长，失败无法归因

正确模型（目标架构）:
  需求 → AI 分析测试意图 → 匹配已有测试资产 → 选择测试层级 → 生成 DSL → 执行
```

### 3.2 目标架构图

```text
                  用户输入
                     |
        PRD / Swagger / Git Diff
                     |
                     ↓
             Requirement Agent
                     |
                     ↓
              Test Intent IR
              (测试意图层)
例如:
  {
   intent: "login",
   type: "negative",
   condition: "wrong_password",
   expected: "authentication_failed"
  }
                     |
                     ↓
          Test Strategy Selector
          判断这个测试应该在哪层？
          ┌───────────────┐
          │               │
          ↓               ↓
       API Test       UI Test
       80%             20%
          │               │
          ↓               ↓
 API Contract        Page Object
 ApiAsset            Element Role
          │               │
          ↓               ↓
       Test DSL
          │
          ↓
       Compiler
          │
          ↓
     Execution Engine
          │
    ┌─────┼─────┐
    ↓     ↓     ↓
 API Runner │ UI Runner
       DB Runner
          │
          ↓
       Evidence
          │
          ↓
    Failure Attribution
          │
          ↓
       AI Feedback
```

### 3.3 Test Knowledge Layer 核心组件

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Test Knowledge Layer                          │
│                    （测试知识层）                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ApiAsset — 不只是存 API Schema，而是"这个 API 能证明什么业务行为"  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ {                                                          │  │
│  │   service_name: "mall-admin",                              │  │
│  │   endpoint: "POST /admin/login",                           │  │
│  │   auth_required: false,                                     │  │
│  │                                                             │  │
│  │   business_intents: [                                       │  │
│  │     {                                                       │  │
│  │       "intent": "login_success",                            │  │
│  │       "expected_http_status": 200,                           │  │
│  │       "assertions": [                                       │  │
│  │         {"field": "code", "expected": 200},                  │  │
│  │         {"field": "data.token", "not_empty": true}           │  │
│  │       ]                                                     │  │
│  │     },                                                      │  │
│  │     {                                                       │  │
│  │       "intent": "login_failed_wrong_password",              │  │
│  │       "expected_http_status": 200,  // mall 不返回 401       │  │
│  │       "assertions": [                                       │  │
│  │         {"field": "code", "expected": 500},                  │  │
│  │         {"field": "message", "contains": "用户名或密码错误"}   │  │
│  │       ]                                                     │  │
│  │     }                                                       │  │
│  │   ]                                                         │  │
│  │ }                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  BusinessAssertion — 不直接写 SQL，而是表达业务验证意图             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ {                                                          │  │
│  │   "entity": "session",                                     │  │
│  │   "condition": {                                           │  │
│  │     "user_id": "{{user_id}}",                               │  │
│  │     "exists": true,                                        │  │
│  │     "within_seconds": 60                                    │  │
│  │   }                                                        │  │
│  │ }                                                          │  │
│  │ ↓ SqlGenerator 翻译为:                                      │  │
│  │ SELECT 1 FROM sessions WHERE user_id = ?                    │  │
│  │   AND created_at > NOW() - INTERVAL '60 seconds'            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ExpectedBehavior — 分离"业务预期"和"测试执行"两个维度              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ # 不再用 expected_failure: true (容易混淆)                  │  │
│  │                                                             │  │
│  │ expected_behavior:                                          │  │
│  │   status: failed           # 业务预期结果：失败              │  │
│  │                                                              │  │
│  │ # 执行结果判定:                                              │  │
│  │ #   业务预期失败 + 断言通过 → expected_behavior_matched ✅    │  │
│  │ #   业务预期失败 + 断言失败 → assertion_failed ❌ (被测Bug)   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、Phase 1: API Contract Driven Test MVP

> **此章节已根据委员会决议 `2026-07-10_mvp_redesign_committee_decision.md` 更新。**
> 原设计（ApiAsset 模型、BusinessAssertion→SqlGenerator、10 Intent、Selftest 独立模块）
> 已被委员会缩减。以下为最终有效范围。

### 4.1 原则

1. **最大复用** — 不改已有 UI 测试链路，新增 API 测试为独立链路
2. **最小改动** — 新增 5 个文件 + 修改 2 个文件，~700 行
3. **AI 克制使用** — 只用于需求→意图提取，不做测试生成
4. **3 个 Intent** — 1 正向 + 2 负向，足够演示闭环
5. **不建资产中心** — TestIntent 直接包含 API 信息，不经过 ApiAsset 层
6. **2 周可演示** — Week 1 核心引擎，Week 2 UI + AI 集成

### 4.2 范围定义

```text
Phase 1 范围 (2 周 MVP):
  ✅ 用户输入需求文本 → AI 提取 Test Intent → 用户确认 → 执行 → 报告
  ✅ 3 个 mall login 场景（1 正向 + 2 负向）
  ✅ 故障归因四层诊断
  ✅ 简单 Web UI + CLI JSON 输出

Phase 1 明确不做:
  ❌ ApiAsset 模型 — TestIntent 直接包含 API 信息，Phase 2 根据真实使用数据设计
  ❌ BusinessAssertion → SqlGenerator — 直接用 assert_sql 写 SQL
  ❌ SelftestRunner 独立模块 — 合并到 ApiStepRunner 内部
  ❌ facade run_case 分流 — 走独立 API endpoint
  ❌ 变量模板 {{...}} 系统 — Phase 1 硬编码值
  ❌ AI Feedback Loop — Phase 1 没有足够执行数据
  ❌ Quality Gate API/DB 规则
```

### 4.3 改动清单

```text
新增文件 (5个):
├── apps/web-ui-service/app/services/api_step_runner.py   (~200行)
│   ApiStepRunner: HTTP 请求 + JSON path 断言 + SQL 断言 + 归因 + 自检
│
├── apps/web-ui-service/app/services/requirement_parser.py (~80行)
│   RequirementParser: LLM prompt + response 解析 → TestIntent
│
├── apps/web-ui-service/app/models/api_test_intent.py     (~50行)
│   TestIntent Pydantic model (Phase 1 极简版)
│
├── apps/web-ui-service/app/routers/api_test.py           (~60行)
│   独立 API endpoint: POST /api/atp/run-api-test
│
└── apps/web-ui-service/tests/unit/test_api_step_runner.py (~120行)
   8 个 test cases: 正向/负向/边界/DB断言/故障归因/自检失败/治理建议

修改文件 (2个):
├── shared_backend/execution_compiler.py                   (~60行)
│   新增 DSL action: api_request, assert_response_status,
│                    assert_response_json, db_query
│
└── runners/web-playwright-python/executor/base_executor.py (~20行)
   ExecutionResult 新增: expected_behavior_matched,
   scenario_type, failure_layer, platform_error,
   connectivity_report, governance_findings

总代码量: ~700 行 (业务 ~530 + 测试 ~120 + 前端 ~50/可选)
```

### 4.4 数据模型（极简版）

> **决策**：Phase 1 不建 Asset Center。TestIntent 直接包含 API 信息和断言。
> ApiAsset 模型延至 Phase 2，基于真实使用数据设计，避免真空过度架构。
> 详见 `2026-07-10_mvp_redesign_committee_decision.md` 第 3.1 节。

```python
# apps/web-ui-service/app/models/api_test_intent.py

class TestIntent(BaseModel):
    """Phase 1 极简 TestIntent — API 信息直接内联，不经过 Asset Center"""
    name: str                    # "login_success"
    scenario: str                # "positive" | "negative"
    api_method: str              # "POST"
    api_path: str                # "/admin/login"
    api_body: dict               # {"username": "admin", "password": "macro123"}
    assertions: list[Assertion]  # 断言列表
    db_assertions: list[DbAssertion] = []  # 可选，直接用 SQL
    expected_behavior: str = "success"     # "success" | "failed"

class Assertion(BaseModel):
    type: str   # "status" | "json"
    path: str | None = None     # JSON path, 如 "code" | "data.token"
    expected: Any | None = None # 期望值
    match: str = "exact"        # "exact" | "contains" | "not_empty"

class DbAssertion(BaseModel):
    sql: str                    # Phase 1 直接写 SQL，不做 SqlGenerator
    expected: str               # "exists" | "not_exists"
```

### 4.5 DSL（极简版）

> Phase 1 只有 3 个场景，不引入 `expected_behavior` 复杂模型。
> 直接在 YAML 中声明 scenario_type 和断言。

```yaml
# 场景 1: 正向 — 登录成功
scenario_type: positive
api:
  method: POST
  path: /admin/login
  body:
    username: admin
    password: macro123

assertions:
  - type: status
    expected: 200
  - type: json
    path: code
    expected: 200
  - type: json
    path: data.token
    match: not_empty

# DB 断言（可选，直接用 SQL）
db_assertions:
  - sql: "SELECT 1 FROM ums_admin WHERE username='admin' AND status=1"
    expected: exists

---
# 场景 2: 负向 — 错误密码
scenario_type: negative
api:
  method: POST
  path: /admin/login
  body:
    username: admin
    password: wrong_password

assertions:
  - type: json
    path: code
    expected: 500
  - type: json
    path: message
    contains: "用户名或密码错误"

---
# 场景 3: 负向 — 空用户名
scenario_type: negative
api:
  method: POST
  path: /admin/login
  body:
    username: ""
    password: macro123

assertions:
  - type: json
    path: code
    expected: 404
```

### 4.6 验证方案（缩小后）

```text
Phase 1 通过标准: 3 个场景全部通过 + 故障归因正确

验证步骤:
  Step 1: 单元测试（不需要被测系统）
    pytest apps/web-ui-service/tests/unit/test_api_step_runner.py -v
    预期: 8 passed

  Step 2: 集成测试（需要 mall 系统）
    3 个 login 场景执行，验证:
    - 正向: status=passed
    - 负向: status=expected_behavior_matched
    - 治理建议: "认证失败应返回 HTTP 401 而非 200"

  Step 3: 审计对比
    UI 测试虚假通过率 40%（审计结果）
    → API+DB 测试虚假通过率 < 5%（目标）

对比原设计:
  原: 10 个 Intent + ApiAsset 模型 + BusinessAssertion + 15+ 单元测试
  现: 3 个场景 + 极简 TestIntent + 直接 SQL + 8 个单元测试
  时间: 10 天 → 2 周，复杂度降低 60%
```

---

## 五、故障归因模型

### 5.1 分层自诊断

```text
┌──────────────────────────────────────────────────────────────┐
│                     ATP 执行分层诊断模型                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Layer 0: 平台自检 (ATP Self-Check)                           │
│   问题: ATP 自身的 Runner 是否正常工作？                        │
│   基准: 内置 selftest 用例（ATP 测自己）                       │
│   ├── selftest_001: GET httpbin.org/get → assert 200          │
│   ├── selftest_002: POST postman-echo.com → assert JSON path  │
│   └── selftest_003: DB SELECT 1 → assert result               │
│   任何 FAIL → platform_error=true，立即终止                    │
│                                                               │
│  Layer 1: 连通性诊断 (Connectivity)                            │
│   问题: ATP 能否到达被测系统？                                  │
│   诊断: DNS 解析 + TCP 连接 + TLS 握手                         │
│   归因: 连接失败 + selftest 通过 → SUT 不可达                  │
│                                                               │
│  Layer 2: 协议诊断 (Protocol)                                  │
│   问题: SUT 是否返回合法的 HTTP 响应？                          │
│   诊断: HTTP 响应 / Content-Type / JSON 可解析性               │
│   归因: 502/503/504 → 网关问题 / 非 JSON → 路由错误             │
│                                                               │
│  Layer 3: 契约诊断 (Contract)  ← SUT 问题区域                  │
│   问题: SUT 的响应是否符合 ATP 定义的质量标准？                 │
│   每个断言失败携带: expected / actual / evidence                │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 结果可信度分级

```text
Level A — 结果可信（被测系统的真实表现）
  条件: Layer 0 + 1 + 2 全部通过
  行动: 按被测系统 Bug 流程处理

Level B — 结果存疑（可能是平台问题）
  条件: Layer 0 通过，Layer 1 或 2 异常
  行动: 人工确认 connectivity_report 后判定

Level C — 结果不可信（平台自身问题）
  条件: Layer 0 自检失败
  行动: 修复 ATP 平台后重新执行
```

---

## 六、总结

> **本文档范围已根据委员会决议 `2026-07-10_mvp_redesign_committee_decision.md` 更新。**

```text
1. ATP 定位: "AI 驱动的智能测试编排平台"
   差异化: 故障归因 + 跨层断言(API+DB)，不是 AI 生成测试

2. Phase 1 MVP 缩小后范围:
   - 3 个 login 场景（1 正 + 2 负）
   - 不建 ApiAsset、BusinessIntent Center、SqlGenerator
   - AI 只用于需求→意图提取，不做测试生成
   - ~700 行代码，2 周可演示

3. 被删除组件的回归策略（详见委员会决议 3.1 节）:
   第一类(早晚要加): ApiAsset → Phase 2，基于真实使用数据设计
   第二类(可能不需要): BusinessIntent Center、Strategy Selector → 待验证
   第三类(工具非架构): OpenAPI Import → 独立CLI
   不应加回来: Agent多角色包装 → 命名泡沫

4. 对比反方审计前:
   原 Phase 1: 860 行 + ApiAsset 模型 + 10 Intent + 15+ 测试 → 7-10 天
   现 Phase 1: 700 行 + 极简 TestIntent + 3 场景 + 8 测试 → 2 周
   复杂度降低 60%，差异化更清晰
```
