# ATP MVP 重设计：架构评审委员会决议

**委员会成员**：字节测试平台负责人 / AI 产品负责人 / 创业公司 CTO
**日期**：2026-07-10
**输入**：反方架构审计报告 (`2026-07-10_adversarial_architecture_audit.md`)
**目标**：设计一个"既能在 2 周内完成，又具备 AI 测试平台差异化价值"的 MVP

---

## 1. 反方意见裁决

### 1.1 必须接受的意见

| 反方意见 | 裁决 | 理由 |
|---------|------|------|
| BusinessAssertion → SqlGenerator 过度架构 | ✅ **接受，删除** | Phase 1 只有 3 个场景、2 条 SQL。写 SQL 比写翻译层更快 |
| Test Strategy Selector 不属于 Phase 1 | ✅ **接受，删除** | Phase 1 只有 API 测试。没有"选择"的必要 |
| SelftestRunner 独立模块过度 | ✅ **接受，合并** | 10 行自检代码，合并到 ApiStepRunner 内部 |
| 10 个 Intent 太多 | ✅ **接受，缩小** | 3 个场景足够演示闭环 |
| AI Feedback Loop 数据不足 | ✅ **接受，延期** | Phase 1 没有足够的执行数据 |
| 冷启动问题真实存在 | ✅ **接受，设计应对** | 不能假设用户有 Swagger/OpenAPI |

### 1.2 不能删除的意见（尽管正确）

| 反方意见 | 裁决 | 理由 |
|---------|------|------|
| "这就像一个 YAML 版 Postman" | ❌ **不能删除，必须正面回答** | 如果连这个都回答不了，产品不成立 |
| "去掉 AI 后没有差异化" | ❌ **不能回避，AI 必须有用但不是全部** | AI 的定位必须精准：不是"生成测试"，是"理解需求意图" |
| "首次使用体验比 Postman 差" | ❌ **必须设计解决方案** | 30 秒 vs 10 分钟的差距必须缩小 |
| "和 CI/CD 不集成" | ❌ **Phase 1 不解决但必须留有接口** | CLI 模式 + JSON 输出 = 可以接入任何 CI/CD |

---

## 2. MVP 重设计

### 2.1 核心叙事

```text
ATP 的定位（一句话）:

"Postman 告诉你测试通过或失败。
 ATP 告诉你为什么会失败，以及该找谁修。"

差异化三角:
  ┌─────────────────┐
  │                 │
  │   AI 理解需求    │
  │   输出测试意图    │
  │                 │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │                 │
  │  API + DB 断言   │  ← Postman 做不到
  │  (业务真相验证)   │
  │                 │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │                 │
  │  故障归因        │  ← 所有工具都做不到
  │  (谁的问题？)     │
  │                 │
  └─────────────────┘
```

### 2.2 MVP 架构图

```text
┌─────────────────────────────────────────────────────────────┐
│                    ATP Phase 1 MVP                           │
│                  "需求 → 意图 → 验证 → 归因"                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: 用户输入需求（自然语言）                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  "验证登录功能：正确密码能登录，错误密码提示错误，          │ │
│  │   空用户名不能登录"                                      │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                    │
│  Step 2: AI 解析 → Test Intent（唯一用到 AI 的地方）          │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │  RequirementParser (LLM)                                │ │
│  │                                                         │ │
│  │  输入: "正确密码能登录"                                   │ │
│  │  输出: {                                                │ │
│  │    intent: "login_success",                             │ │
│  │    scenario: "positive",                                │ │
│  │    what_to_verify: "认证成功 + token 返回"                │ │
│  │  }                                                      │ │
│  │                                                         │ │
│  │  输入: "错误密码提示错误"                                  │ │
│  │  输出: {                                                │ │
│  │    intent: "login_failed",                              │ │
│  │    scenario: "negative",                                │ │
│  │    what_to_verify: "认证失败 + 错误提示"                   │ │
│  │  }                                                      │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                    │
│  Step 3: 用户确认（人工 Gate）                                 │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │  "AI 分析出以下测试意图，请确认或修改:"                    │ │
│  │                                                         │ │
│  │  [✓] 正向: 正确密码登录成功                               │ │
│  │  [✓] 负向: 错误密码被拒绝                                 │ │
│  │  [✓] 负向: 空用户名被拒绝                                 │ │
│  │                                                         │ │
│  │  请补充:                                                 │ │
│  │  API Base URL: [http://localhost:8080]                  │ │
│  │  登录接口路径: [/admin/login]                             │ │
│  │  测试账号: [admin]  密码: [macro123]                     │ │
│  │  DB连接(可选): [postgresql://...]                        │ │
│  │                                                         │ │
│  │  [开始测试]                                              │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                    │
│  Step 4: 自动执行 + 故障归因                                   │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │                                                         │ │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────────────┐   │ │
│  │  │ API Test │   │ DB Test  │   │ Fault Attribution│   │ │
│  │  │          │   │          │   │                  │   │ │
│  │  │ POST     │   │ SELECT   │   │ Layer 0: 平台自检 │   │ │
│  │  │ /login   │   │ FROM     │   │ Layer 1: 连通性   │   │ │
│  │  │          │   │ sessions │   │ Layer 2: 协议     │   │ │
│  │  │ assert   │   │ WHERE    │   │ Layer 3: 契约     │   │ │
│  │  │ status   │   │ ...      │   │                  │   │ │
│  │  │ assert   │   │          │   │ 结果:            │   │ │
│  │  │ JSON     │   │ assert   │   │ ✅ SUT 符合预期   │   │ │
│  │  │          │   │ exists   │   │ ❌ SUT 不符合标准 │   │ │
│  │  └──────────┘   └──────────┘   │ ⚠️ 平台自身问题   │   │ │
│  │                                 └──────────────────┘   │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                    │
│  Step 5: 报告                                              │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │                                                         │ │
│  │  📊 测试报告: mall 登录功能                               │ │
│  │                                                         │ │
│  │  ✅ 正确密码登录: PASS                                   │ │
│  │     API 返回 200, token 有效, DB sessions 有记录          │ │
│  │                                                         │ │
│  │  ✅ 错误密码登录: 预期失败 (expected_failure)              │ │
│  │     API 返回 code=500, message="用户名或密码错误"          │ │
│  │     ⚠️ 治理建议: 认证失败应返回 HTTP 401 而非 200          │ │
│  │                                                         │ │
│  │  ✅ 空用户名登录: 预期失败                                │ │
│  │     API 返回 code=404, 校验生效                           │ │
│  │                                                         │ │
│  │  归因置信度: Level A (平台自检通过, 连通性正常)             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 核心数据模型（极简版）

```text
Phase 1 只需要 3 个数据结构:

1. TestIntent (AI 输出 + 人工确认的结果)
   {
     "intents": [
       {
         "name": "login_success",
         "scenario": "positive",
         "api": {
           "method": "POST",
           "path": "/admin/login",
           "body": {"username": "admin", "password": "macro123"}
         },
         "assertions": [
           {"type": "status", "expected": 200},
           {"type": "json", "path": "code", "expected": 200},
           {"type": "json", "path": "data.token", "match": "not_empty"}
         ],
         "db_assertions": [
           {"sql": "SELECT 1 FROM sessions WHERE ...", "expected": "exists"}
         ]
       },
       {
         "name": "login_failed_wrong_password",
         "scenario": "negative",
         "expected_behavior": "failed",
         ...
       }
     ],
     "config": {
       "base_url": "http://localhost:8080",
       "db_url": "postgresql://..."
     }
   }

2. ExecutionResult (执行结果 + 故障归因)
   {
     "intent": "login_success",
     "status": "passed",
     "assertions": [
       {"type": "status", "expected": 200, "actual": 200, "passed": true}
     ],
     "failure_layer": null,
     "platform_healthy": true,
     "governance_findings": [],
     "evidence": {"request": {...}, "response": {...}}
   }

3. TestReport (面向用户的报告)
   {
     "summary": "3/3 scenarios passed",
     "findings": [
       {"severity": "warning", "message": "认证失败应返回 HTTP 401"}
     ],
     "attribution_confidence": "Level A"
   }
```

### 2.4 用户使用流程

```text
用户使用 ATP 的完整流程（10 分钟内完成首次测试）:

Step 1: 写需求（1 分钟）
  在 Web UI 文本框输入:
  "验证 mall 系统登录功能：正确密码登录成功，错误密码提示错误，
   空用户名拒绝登录"

Step 2: AI 分析（10 秒）
  系统返回 3 个 Test Intent（AI 生成 + 可编辑）

Step 3: 补充配置（2 分钟）
  填写:
  - API Base URL: http://localhost:8080
  - 登录接口: /admin/login
  - 测试账号: admin / macro123
  - DB 连接(可选): postgresql://mall_user@localhost:5432/mall

Step 4: 执行（30 秒）
  系统自动:
  - 发送 3 个 API 请求
  - 执行 DB 查询
  - 执行故障归因

Step 5: 看报告（1 分钟）
  看到:
  - 3/3 场景通过
  - 1 条治理建议
  - 故障归因: Level A（可信）

总计: 约 5 分钟完成第一次测试

对比 Phase 1 原设计:
  需要手工写 YAML → 手工定义 ApiAsset → 手工配置 DB 连接
  → 至少 30 分钟
```

### 2.5 Demo Story

```text
面试 Demo 场景: "测一个你从没见过的系统"

Demo 流程:

1. 打开 ATP Web UI
2. 输入需求:
   "测试 mall 后台管理系统的用户登录 API:
    正确密码返回 token，
    错误密码提示'用户名或密码错误'，
    空用户名被参数校验拦截"

3. AI 自动分析出 3 个 Test Intent，展示在页面上
   讲解: "AI 只做了一件事——理解需求中的测试意图。
         它不猜测错误码、不猜测接口路径、不猜测测试数据。
         这些都由我在下一步补充。"

4. 手工补充 3 个信息:
   - API 地址: http://localhost:8080
   - 接口路径: /admin/login
   - 测试账号: admin / macro123
   讲解: "这些是确定性信息，不应该让 AI 猜。"

5. 点击执行，3 个场景依次执行:
   场景1: ✅ PASS - 返回 200 + token
   场景2: ✅ 预期失败 - 返回 code=500 + 错误提示
          └── 治理建议: "认证失败应返回 HTTP 401"
   场景3: ✅ 预期失败 - 返回 code=404 + 参数校验生效

6. 展示故障归因:
   "所有结果标注为 Level A 可信——
    因为平台自检(HTTP Client + JSON Assertion)全部通过，
    连通性正常，响应格式正确。如果被测系统返回 502，
    平台会自动标注为 Level B (协议层异常)而非直接报错。"

Demo 时长: 3 分钟
核心信息: "AI 理解需求意图 + 确定性执行 + 故障归因 = ATP"
```

### 2.6 面试讲解版本

```text
面试官: "你的产品和 Postman 有什么区别？"

错误回答:
  "我们的产品用 AI 自动生成测试用例，能测 API 和 DB..."
  → 面试官: "Postman 也能测 API，也有 AI 插件。"

正确回答 (30 秒版):
  "Postman 是一个优秀的 API 调试和执行工具。
   但 ATP 解决的是另一个问题——

   当 50 人的 QA 团队管理 200 个接口的自动化测试时，
   最大的痛点不是'怎么写测试'，而是'失败之后怎么办'。

   Postman 告诉你: 第 47 个断言失败了。
   ATP 告诉你:
   1. 失败原因是被测系统把认证失败返回成 HTTP 200 而非 401
   2. 这个问题已经出现了 15 次，影响 8 个测试用例
   3. 这不是平台的问题（平台自检正常），建议提交缺陷给后端团队
   4. 同时，DB 验证确认 session 未被创建，所以业务逻辑是正确的

   这就是 ATP 的差异化:
   不只是执行测试，而是理解测试结果。"

补充 (如果面试官追问):
   "AI 在 ATP 中的角色很克制。
   我们不要求 AI 生成测试用例——
   因为 AI 不知道你的 API 路径、错误码、测试数据。
   
   AI 只做一件事: 从需求文档中提取测试意图。
   '这段需求在说什么？有哪些需要验证的业务行为？'
   
   至于怎么验证、用什么数据、走 API 还是 UI——
   由测试资产和规则引擎决定，不需要 AI 猜测。
   
   这种'AI + 确定性工程'的结合，比纯 AI 生成更可靠，
   也比纯手工 Postman 更智能。"
```

---

## 3. 技术实现：2 周 Sprint 计划

### Week 1: 核心引擎

| 天 | 任务 | 产出 |
|----|------|------|
| Day 1-2 | Compiler 扩展（api_request action） + ApiStepRunner（HTTP + JSON path） | 能执行 1 个 API 请求并断言 |
| Day 3 | DB Assertion（assert_sql 直接执行） | 能验证 DB 状态 |
| Day 4 | ExecutionResult + 故障归因（四层诊断） | 能输出带归因的结果 |
| Day 5 | 单元测试 + 集成验证（3 个 mall login 场景） | 3/3 通过 |

### Week 2: 用户界面 + AI 集成

| 天 | 任务 | 产出 |
|----|------|------|
| Day 6-7 | RequirementParser（LLM → TestIntent） | AI 能从需求文本提取意图 |
| Day 8 | 简单 Web UI（需求输入 → 意图确认 → 执行 → 报告） | 可演示的完整流程 |
| Day 9 | Demo Story 打磨 + 异常场景处理 | 演示不出错 |
| Day 10 | Buffer（修 bug + 补充文档） | |

### 代码量估算

```text
总代码量: ~700 行

  shared_backend/execution_compiler.py  +60 行  (api_request action)
  app/services/api_step_runner.py       +200 行 (HTTP + JSON path + SQL + 归因)
  app/services/requirement_parser.py    +80 行  (LLM prompt + response 解析)
  app/routers/api_test.py               +60 行  (新的 API endpoint)
  app/models/api_test_intent.py         +50 行  (TestIntent Pydantic model)
  frontend/src/pages/ApiTestPage.tsx    +150 行 (简单 UI)
  tests/unit/test_api_step_runner.py    +100 行 (8 个测试)

  不做的:
    ✗ ApiAsset 模型（TestIntent 直接包含 API 信息）
    ✗ BusinessAssertion → SqlGenerator
    ✗ facade run_case 分流（走独立 API endpoint）
    ✗ SelftestRunner 独立模块（合并到 runner 内部）
    ✗ 变量模板 {{...}} 系统（Phase 1 硬编码值）
```

---

### 3.1 被删除组件的回归策略

Phase 1 删除了 5 个组件。以下是每个组件是否需要加回来、何时加、以及现在不加的弊端分析。

```text
┌─────────────────────────────────────────────────────────────────┐
│                    被删除组件分类                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  第一类：早晚要加，但时机影响设计                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ApiAsset — Phase 2 加                                       ││
│  │                                                              ││
│  │ 现在不加的原因:                                               ││
│  │   真空设计会过度架构（path/method/schema/error_codes/        ││
│  │   business_intents/assertions 全加上），维护成本高。           ││
│  │                                                              ││
│  │ 为什么 Phase 2 设计会更好:                                    ││
│  │   Phase 1 有 3 个场景的真实执行数据，知道用户实际需要什么。     ││
│  │   设计出来的 ApiAsset 是"刚好够用"，不是"什么都支持"。          ││
│  │   例如：用户需要 base_url 配置 → 一个字段                     ││
│  │        用户不需要 response_schema → 不设计                    ││
│  │        用户不手动维护 error_codes → 不设计                    ││
│  │                                                              ││
│  │ 加回来的代价:                                                 ││
│  │   - ApiStepRunner 增加 load_api_asset() 调用，约 30 行重构    ││
│  │   - Phase 1 的 3 个 TestIntent 中 API 信息可迁移到 ApiAsset    ││
│  │     (3 条 INSERT，不是数据迁移项目)                            ││
│  │                                                              ││
│  │ 加回来的时机判断:                                              ││
│  │   当同一个 API 端点被 3 个以上测试用例引用时，手工维护          ││
│  │   API 信息（method/path/base_url）开始让人烦的时候。            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  第二类：可能根本不需要                                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ BusinessIntent Center — 不一定需要                           ││
│  │                                                              ││
│  │ 它的核心假设:                                                 ││
│  │   一个 API 端点可以映射到多个 business_intents。               ││
│  │   例如 POST /login → [login_success, login_failed, ...]      ││
│  │                                                              ││
│  │ 为什么不加:                                                   ││
│  │   反方审计指出: 谁维护这个映射？开发连 Swagger 都不写。         ││
│  │   冷启动时没有任何 business_intents，系统不可用。              ││
│  │                                                              ││
│  │ Phase 1 会验证一个关键假设:                                    ││
│  │   "用户是愿意先定义 BusinessIntent 再引用它，                 ││
│  │    还是愿意在每次测试时直接写断言？"                            ││
│  │                                                              ││
│  │   如果验证结果是后者（大概率），BusinessIntent Center 就不需要。 ││
│  │   就像 Postman 用户愿意在 Collection 里写 Test Script，         ││
│  │   而不是先在一个独立的地方定义"这个 API 能验证什么业务行为"。     ││
│  │                                                              ││
│  │ 决策: 等 Phase 1 验证后决定。                                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Strategy Selector — 不需要独立模块                           ││
│  │                                                              ││
│  │ 它的逻辑:                                                     ││
│  │   Rule 1: 用户配置了 API 信息 → API 可测                      ││
│  │   Rule 2: 用户配置了 PageObject → UI 可测                     ││
│  │   Rule 3: 都配置了 → 默认 API（更快更可靠）                     ││
│  │                                                              ││
│  │ 为什么不加:                                                   ││
│  │   这是 3 条 if-else 规则，应该在 ApiStepRunner.execute()       ││
│  │   里用 10 行代码实现，不是独立模块。                            ││
│  │   Phase 1 只有 API 测试，连选择都没有，不需要 Selector。        ││
│  │                                                              ││
│  │ 决策: 不应该加回来。即使 Phase 3 多 Runner 并存，               ││
│  │       也是 3 条规则的配置文件，不是独立服务。                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Agent 多角色包装 — 不应该加回来                               ││
│  │                                                              ││
│  │ 当前 8 个 Agent 的实际需求分析:                                ││
│  │   requirement-parser-agent    → 需要 LLM ✅                  ││
│  │   test-design-agent          → 规则更可靠                    ││
│  │   script-generation-agent    → 规则 + Compiler               ││
│  │   execution-planner-agent    → 不需要，直接执行               ││
│  │   risk-evaluation-agent      → 规则                         ││
│  │   failure-analysis-agent     → 规则（Layer 0→1→2→3 诊断）    ││
│  │   failure-triage-agent       → 规则                         ││
│  │   self-healing-advisor-agent → 规则                         ││
│  │                                                              ││
│  │ 8 个 Agent 中，只有 1 个真正需要 LLM。                         ││
│  │ 其余 7 个是"披着 Agent 外衣的 if-else"。                      ││
│  │                                                              ││
│  │ 决策: 这不是"先删掉、以后加回来"。                              ││
│  │       这是"根本不应该存在"。                                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  第三类：工具而非架构                                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ OpenAPI Import — 独立的 CLI 工具，不影响架构                  ││
│  │                                                              ││
│  │ 为什么不加:                                                   ││
│  │   mall 系统没有静态 OpenAPI JSON 文件（Swagger 运行时生成）。   ││
│  │   冷启动时导入不了任何东西。                                   ││
│  │                                                              ││
│  │ 加回来的形式:                                                 ││
│  │   一个独立的 CLI 脚本或 UI 中的 "Paste Swagger JSON" 按钮。    ││
│  │   输入: OpenAPI JSON 字符串                                   ││
│  │   输出: 自动填充的 TestIntent（接口路径 + method）              ││
│  │   它不影响数据模型、不影响执行链路、不影响产品架构。             ││
│  │                                                              ││
│  │ 决策: Phase 3 花半天写一个 parser，不影响 Phase 1 设计。        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 删除的真正风险不是"要加回来"，而是"加了以后发现设计错了"

```text
真空设计的典型失败模式:

  设计阶段: "我们需要 ApiAsset 来管理 API 信息。API 有 path、method、
            request_schema、response_schema、error_codes..."
  → 建了 15 个字段的模型

  上线 3 个月后:
    - request_schema 从来没人填过（用户直接写 body template）
    - response_schema 从来没人填过（用户直接写 JSON path 断言）
    - error_codes 维护了 5 个，实际用到的只有 2 个
    - business_intents 全靠 AI 推测，质量很差
    - 15 个字段里，只有 4 个（path、method、base_url、auth_required）被真正使用

  结果: 一个过度设计的模型 → 用户不愿意维护 → 数据质量差 → AI 依赖低质量数据生成
        → 生成的测试更差 → 恶性循环

避免的方式:
  Phase 1 不做 ApiAsset。用户直接在 TestIntent 里写 API 信息。
  执行 3 个场景后，你自然知道用户实际需要什么字段。
  Phase 2 的 ApiAsset 模型是从真实使用中生长出来的，不是从架构图里设计的。
```

---

## 4. 委员会最终决议

```text
字节测试平台负责人:
  "差异化清晰。故障归因是真正的增量价值，其他平台都不做。
   但 2 周内必须演示端到端闭环，否则没有说服力。"

AI 产品负责人:
  "AI 的定位克制是正确的。'AI 理解需求 + 确定性执行' 
   比'AI 全自动生成测试'更有商业说服力。
   Demo Story 中的 3 分钟演示是关键——必须在面试官注意力
   流失之前展示完核心价值。"

创业公司 CTO:
  "同意缩小范围。一个 5 分钟跑通的首次体验，比一个完善
   但需要 30 分钟配置的产品更有竞争力。
   冷启动问题通过在 UI 中引导用户填写 API 信息来解决——
   不做自动发现，不假设用户有 Swagger。
   
   唯一补充: 确保 ExecutionResult 输出纯 JSON，
   这样即使 UI 没做完，CLI 也能演示。"
```

---

**一句话: 2 周 MVP = AI 理解需求意图 + API/DB 确定性执行 + 故障归因。不做测试生成，不做资产中心，不做自动导入。只证明一件事: "ATP 不是另一个 Postman。"**
