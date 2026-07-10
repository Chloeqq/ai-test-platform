# ATP 反方架构审计报告

**审计角色**：反方架构审计专家（不优化，只攻击）
**审计日期**：2026-07-10
**原则**：不鼓励，只找问题

---

## 1. 商业价值审计

### 1.1 这个问题是否真实存在？

**部分真实，但被过度放大了。**

> "AI 生成的 UI 测试用例 40% 虚假通过"

这个数据来自 ATP 自己对 login 模块的审计。但你需要区分两个问题：

- **问题是 ATP 自身的设计缺陷？** — 零断言、断言目标错误、element role 缺失——这些不是"AI 自动化测试"这个领域的固有问题，而是 ATP 的设计不完善。
- **还是行业通用问题？** — Postman 不需要 element role，RestAssured 不需要找 toast。你把 UI 测试最难的部分作为切入点，然后说"AI 自动化测试不行"，这是**把切入点问题当成领域问题**。

**真正的痛点是什么？**

| 用户 | 真正痛点 | ATP 解决了吗 |
|------|---------|-------------|
| 10 人 QA 团队 | 需求理解困难，测试设计耗时 | ✅ 方向正确 |
| 50 人 QA 团队 | 多项目质量统一治理 | ⚠️ 有框架但缺多租户 |
| 200 人 QA 组织 | 执行环境管理、数据治理 | ❌ 完全没有 |
| QA 负责人 | 测试资产复用、人员交接 | ❌ 没有协作能力 |

**你花最多精力解决的问题（AI 生成 UI 断言准确性），不一定是最痛的问题。**

### 1.2 是否比传统框架有明显价值？

**对于 API 测试：不明显。**

```text
你设计的:
  ApiAsset → Test Intent → DSL → Compiler → Runner → Evidence

Postman 用户做的事:
  Collection → Request → Assertion → Run → Report

区别在哪？
  - Postman 不用写 YAML，用 GUI
  - Postman 不需要 Compiler
  - Postman 的 business_intents 叫 "Test Script"
  - Postman 已有 2000 万用户
```

**ATP 相对于 Postman/Newman 的增量价值是什么？如果你不能一句话说清楚，这个设计就有问题。**

可能的差异化：
1. **跨 API + DB + UI 三层断言**（Postman 不做 DB 断言）→ 这是真差异
2. **AI 从需求生成 Test Intent**（Postman 没有）→ 这是真差异，但有风险
3. **质量治理闭环**（Postman 只执行不管治理）→ 这是真差异

**但当前 Phase 1 没有 2 和 3。Phase 1 就是一个"需要手写 YAML 的 Postman"。**

### 1.3 如果去掉 AI，这个平台是否仍然成立？

**如果你诚实地回答这个问题，会很痛苦。**

```text
去掉 AI 后:
  ├── Test Asset Center (PageObject, DataPool) → 有价值，但很多工具都有
  ├── DSL Compiler → Playwright 本身就支持 YAML？
  ├── Quality Gate → 有价值，但依赖前两层
  ├── API/DB Runner → 有价值，但和 Postman + Database Plugin 竞争
  └── Execution Result + 故障归因 → 这是真差异化

结论: 去掉 AI 后，只有"故障归因"和"质量治理"是真差异化。
       其他都是已有的开源/商业能力。
```

---

## 2. 技术可行性审计

### 2.1 当前设计是否过度架构？

**是的。Phase 1 设计中有三个明显的过度架构：**

**过度架构 1：BusinessAssertion → SqlGenerator**

```text
当前设计:
  db_assertions:
    - entity: session
      condition:
        user_id: "{{user_id}}"
        exists: true
        within_seconds: 60
  ↓ SqlGenerator 翻译
  SELECT 1 FROM sessions WHERE ... (需要知道表结构元数据)

问题:
  1. SqlGenerator 需要知道表名、字段名、SQL 方言
  2. 这些信息从哪里来？另一个 ApiAsset？
  3. 对于 Phase 1 MVP，这是不必要的复杂度
  4. 你只需要验证 3 个 SQL 查询，写 3 行 SQL 就够了
```

**建议**：Phase 1 直接用 `assert_sql`。BusinessAssertion 是 Phase 2 的事。

**过度架构 2：Test Strategy Selector**

```text
当前设计目标:
  AI 自动判断这个场景应该测 API 还是 UI
  ← 这是大厂 200 人团队、500+ 接口、3 年积累后的优化目标
  ← 不是 Phase 1 应该考虑的

Phase 1 的现实:
  - 只有 login 一个模块
  - 全部 10 个 Intent 都在 API 层
  - Selector 永远返回 "API"
  - 这个组件 100% 是浪费
```

**建议**：Test Strategy Selector 是 Phase 3+ 的事。

**过度架构 3：OpenAPI → ApiAsset 自动化导入**

```text
当前假设: 被测系统有 OpenAPI spec，ATP 可以自动导入
mall 现实: Swagger 运行时生成，没有静态 JSON 文件

你需要:
  1. 人工创建 ApiAsset（手工填字段）
  2. 或者写一个 Swagger JSON 抓取器
  3. 或者让被测系统导出 OpenAPI JSON

Phase 1 就是手工录入一个 POST /admin/login 的 ApiAsset。
OpenAPI 自动导入是 Phase 2+ 的事。
```

### 2.2 Phase 1 MVP 是否真的能在 3-5 天完成？

**估算过于乐观。实际需要 7-10 天。**

让我逐项拆解隐藏复杂度：

| 任务 | 估算 | 隐藏复杂度 |
|------|------|-----------|
| ApiAsset 模型 | 0.5 天 | 简单 |
| Compiler 扩展 | 1 天 | 需要理解 1030 行的 compiler 全貌，新增 action 不能破坏现有逻辑 |
| ApiStepRunner | 2 天 | HTTP 请求简单，但：JSON path 解析（点号/数组索引/通配符）、错误处理（超时/SSL/DNS/Connection Refused）、响应 body 可能不是 JSON、变量替换 `{{username}}` 需要实现 |
| SelftestRunner | 0.5 天 | 简单 |
| ExecutionResult 扩展 | 0.5 天 | 需要同步改 facade_test_point_assets.py 的 run_case 流程 |
| facade 分流 | 1 天 | 当前 run_case 函数 150+ 行，耦合了 pytest subprocess、Allure、evidence manifest。加入 API 分流需要理解整个函数的所有分支 |
| 单元测试 | 1.5 天 | mock HTTP、mock DB、mock 环境变量，15+ cases |
| 端到端验证 | 1 天 | 需要启动 mall 系统、准备测试数据、调试各种环境问题 |

**合计：7.5-10 天。不是 3-5 天。**

### 2.3 哪些模块存在隐藏复杂度？

**隐藏复杂度 1：变量替换系统**

```yaml
body:
  username: "{{username}}"       # 从哪来？
  password: "{{password}}"       # 从哪来？

# 可能的来源:
# 1. setup db_query 的 extract 结果
# 2. 上一个 api_request 的 response JSON path 提取
# 3. 环境变量
# 4. TestDataPool
# 5. 硬编码 inlined
```

**你需要在 ApiStepRunner 中实现一个 mini 变量作用域系统。这是 10 行代码的事吗？不是。** 现有的 `data_pool_resolver` 只处理 `pool_name + key` 引用，不处理 `{{...}}` 模板语法。

**隐藏复杂度 2：被测系统的 base URL 管理**

```text
sut_service: mall-admin
  → 映射到 base URL

可能的配置来源:
  1. 环境变量 ATP_SUT_MALL_ADMIN_URL
  2. 配置文件
  3. 服务发现（Consul/Nacos）
  4. 硬编码 localhost:8080

Phase 1 可以用环境变量，但你需要:
  - 文档约定命名规则
  - 缺失时的错误提示
  - 多环境切换（dev/staging/prod）
```

**隐藏复杂度 3：DB 连接管理**

```text
selftest_runner DB 自检用 ATP 自己的数据库（已有连接）
但业务 DB 断言是查被测系统的数据库！

    ATP DB（自己的） ≠ 被测系统 DB（mall 的）

当前设计中，DB 断言查的是被测系统的 DB。
但 ATP 如何连接到被测系统的 DB？
  - 环境变量 ATP_SUT_MALL_DB_URL
  - 需要同时管理自己的 DB 连接 + 被测系统的 DB 连接
  - 两个连接池、两个 session factory
```

这是 Phase 1 最大的隐藏复杂度。**DB 断言需要独立的 DB 连接管理。**

### 2.4 哪些设计在真实企业环境会失败？

**失败点 1：硬编码账号密码**

```yaml
body:
  username: admin
  password: macro123
```

**在真实企业环境中**：
- 不同环境（dev/staging/prod）有不同的测试账号
- 密码不能明文存在 YAML 中
- 账号可能过期、被禁用、被删除
- 同一个账号被多个测试用例复用可能导致状态冲突

**Postman 怎么解决的**：Environment Variables + Vault
**ATP 的对策**：需要 TestDataPool 集成，但 Phase 1 没做

**失败点 2：被测系统不可控**

```text
Phase 1 假设: mall 系统可启动、可连接、数据可预期

真实企业:
  - 被测系统可能部署在内网，ATP 需要 VPN/代理
  - 被测系统可能有 API 限流
  - 被测系统的测试数据可能被其他人修改
  - 多个用例并发执行可能导致数据冲突
```

**失败点 3：DB 连接权限**

```text
真实企业:
  - QA 环境通常没有生产 DB 的读权限
  - DB 连接需要审批
  - DB 密码存在 Vault 中，不是环境变量
  - 不同环境的 DB schema 可能不同（迁移未同步）
```

---

## 3. 数据来源审计 — 攻击 Test Knowledge Layer

### 3.1 ApiAsset 的 business_intents 从哪里产生？

**这是整个设计中最薄弱的环节。**

```text
你的设计:
  ApiAsset.business_intents = [
    {intent: "login_success", assertions: [...]},
    {intent: "login_failed", assertions: [...]},
  ]

谁写这些数据？
  选项 A: 人工录入 → 每个 API 端点 3-5 个 intent × 50 个端点 = 200 条
            维护成本和工作量不可接受
  
  选项 B: AI 生成 → 回到"AI 推测"的老问题
            AI 不知道真实错误码
            AI 不知道真实业务规则
  
  选项 C: 从 Swagger 自动提取 → Swagger 只描述 API Schema
            不描述"这个 API 可以证明什么业务行为"
            不描述"什么情况下返回 401 vs 403 vs 500"
  
  选项 D: 从已有测试用例中学习 → 需要已有测试用例
            冷启动时没有
  
  选项 E: 从执行结果中学习 → 需要先执行
            第一次执行时没有 business_intents → 无法生成断言
            → 死循环
```

**结论：business_intents 的来源是一个未解决的冷启动问题。**

### 3.2 谁维护 BusinessAssertion？

```text
业务断言: "登录成功后 sessions 表应有记录"

谁定义 sessions 表的结构？
  谁定义表名 = "sessions"（不是 "user_sessions" 或 "auth_session"）？
  谁定义字段名 = "user_id"（不是 "uid" 或 "account_id"）？
  谁定义时间字段名 = "created_at"（不是 "create_time" 或 "ts"）？

答案: 需要 DB Schema 元数据。
      但 DB Schema 元数据从哪里来？
      - 手动录入 → 不可维护
      - 自动扫描 DB → 可能但需要额外开发
      - Swagger 不描述 DB → 不可用
```

### 3.3 冷启动问题

```text
Day 0: ATP 部署
  ├── ApiAsset 为空
  ├── BusinessAssertion 为空
  ├── 没有任何测试资产
  └── 没有任何历史执行数据

用户想测的第一个接口: POST /admin/login
  ├── 需要创建 ApiAsset（手工）
  ├── 需要定义 business_intents（手工）
  ├── 需要定义 assertions（手工）
  ├── 需要配置 DB 连接（手工）
  ├── 需要准备测试数据（手工）
  └── 最后才能写 DSL 并执行

对比 Postman:
  ├── 输入 URL + body → Send → 看到 response
  └── 30 秒内完成第一次请求

ATP 的首次使用体验比 Postman 差了 10 倍。
```

---

## 4. AI 能力边界审计

### 4.1 Requirement Agent — AI 是否真的需要？

```text
Requirement Agent 的输入:  PRD / Swagger / Git Diff / 用户故事
Requirement Agent 的输出: Test Intent IR

问题: 这个"理解需求并生成结构化意图"的工作，多少是需要 LLM 的？

拆解:
  1. 从 PRD 提取"要测什么" → LLM 擅长（NLP 理解）
  2. 判断测试类型（positive/negative/boundary）→ 规则可以做到
     条件: "错误" "失败" "异常" → negative
     条件: "边界" "超过" "小于" → boundary
     这完全可以用关键词匹配 + 少量 LLM 兜底
  
  3. 匹配已有 ApiAsset → 规则完全胜任
     输入: 需求提到 "登录"
     匹配: ApiAsset 中所有 intent_name 包含 "login" 的条目
     不需要 LLM
  
  4. 选择断言类型 → 规则完全胜任
     intent = "login_failed" → 查 ApiAsset.business_intents → 得到 assertions
     不需要 LLM

结论: Requirement Agent 中，只有步骤 1（从 PRD 提取需求意图）需要 LLM。
      步骤 2-4 应该由规则引擎完成。
      把整个流程包装为一个 Agent 是过度设计。
```

### 4.2 Test Strategy Selector — 规则还是 AI？

```text
Test Strategy Selector 的目标: 判断这个场景应该测 API 还是 UI

判断逻辑:
  1. 有对应的 ApiAsset？→ API 可测
  2. 需要验证 UI 行为（视觉反馈、交互逻辑）？→ UI 可测
  3. 只验证业务逻辑（认证/数据变更）？→ API 优先

这不就是 3 条 if-else 规则吗？
为什么需要一个 Agent？

答案: 不需要 Agent。这是一个规则引擎。
      最多是带有 3-5 条规则的 classifier。
```

### 4.3 AI Feedback Loop — 需要吗？

```text
AI Feedback Loop 的目标: 从失败的执行结果中学习，优化生成策略

问题: 当前 Phase 1 根本没有足够的数据来"学习"。

Phase 1 有 10 个 Intent。
"学习"需要: 至少 100+ 个执行样本，包含 success 和 failure 的混合。

建议: AI Feedback Loop 至少延迟到 Phase 3。
      Phase 2 可以做一个简单的规则-based 反馈:
      "这个断言连续失败 3 次 → 标记为需要人工确认"
      不需要 LLM。
```

### 4.4 AI 能力边界总结

| 组件 | 是否需要 LLM | 替代方案 |
|------|------------|---------|
| Requirement Agent（需求理解） | ✅ 需要 | 不可替代，这是核心 NLP 能力 |
| Requirement Agent（意图→资产匹配） | ❌ 不需要 | 关键词匹配 + 规则 |
| Test Strategy Selector | ❌ 不需要 | 3 条 if-else 规则 |
| AI Feedback Loop | ❌ 不需要（当前阶段） | 规则-based 标记 |
| 断言生成（错误文案推测） | ❌ 不需要 | 从 ApiAsset 精确取值 |

**结论：ATP 当前设计中，只有 1 个地方真正需要 LLM（从 PRD 提取需求意图），其他 4 个地方可以用规则替代。把所有东西都叫"Agent"是一种命名泡沫。**

---

## 5. MVP 范围审计

### 5.1 是否应该缩小？

**是的。当前 Phase 1 仍然太大。**

```text
当前 Phase 1:
  ApiAsset + Compiler + ApiStepRunner + SelftestRunner +
  BusinessAssertion + SqlGenerator + ExecutionResult +
  facade 分流 + 10 个 Intent + 15+ 单元测试

应该缩小为:
  1 个 YAML → Compiler → ApiStepRunner → ExecutionResult
  （BusinessAssertion 和 SqlGenerator 删除）
  （Selftest 合并到 ApiStepRunner 内部）
  （facade 分流暂时不做，直接调 ApiStepRunner 验证）
```

### 5.2 最小可证明价值(MVP)是什么？

```text
最小 MVP: 一行 curl 能做到的事，ATP 能否做到？

  curl -X POST http://localhost:8080/admin/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"wrong"}'

  → 返回 {"code":500,"message":"用户名或密码错误"}

ATP 最小 MVP:
  1. 从 YAML 读取 api_request
  2. 发送 HTTP 请求
  3. 断言 response JSON path
  4. 返回 passed/failed + evidence

这就够了。这就是一个可演示的 MVP。
API Asset、BusinessIntent、Selftest、DB Assertion — 全部可以在下一个 Sprint 加。
```

### 5.3 哪些功能应该延期？

```text
应该延期到 Phase 2:
  ❌ BusinessAssertion → SqlGenerator（直接用 assert_sql）
  ❌ SelftestRunner 独立模块（合并到 ApiStepRunner 内部，10 行代码）
  ❌ facade 分流到 run_case（先直接调 ApiStepRunner 验证）
  ❌ 10 个 Intent（先做 3 个：正向登录、错误密码、空用户名）

应该延期到 Phase 3:
  ❌ Test Strategy Selector
  ❌ AI Feedback Loop
  ❌ OpenAPI 自动导入
  ❌ DB 连接池管理（直接用单个连接）
```

---

## 6. 与大厂测试平台对比

### 6.1 Google/Meta 测试平台共同特征

```text
Google (Borg/Blaze/TAP):
  - 测试是 CI/CD pipeline 的一部分，不是独立平台
  - 测试用例和被测代码放在同一个 repo
  - 重执行执行，轻测试生成
  - 没有"AI 生成测试用例"这个环节

Meta (Sapienz/Infer):
  - 重点是 crash detection + regression
  - Sapienz 是用遗传算法生成事件序列，不是 LLM
  - 核心价值观: 能 crash 就是 Bug，不需要复杂断言

共性:
  1. 和 CI/CD 深度集成（不是独立 Web 平台）
  2. 测试资产和代码同仓（不是独立资产管理）
  3. 关注"有没有 Bug"而非"测试设计好不好"
  4. AI/自动化的目标是补充人工测试，不是替代
```

### 6.2 ATP 缺少什么？

| 能力 | Google/Meta | 字节/阿里 | ATP | 
|------|------------|----------|-----|
| CI/CD 集成 | ✅ 核心 | ✅ | ❌ |
| 和代码仓库集成 | ✅ | ✅ | ❌ |
| 多租户/权限 | ✅ | ✅ | ❌ |
| 测试环境管理 | ✅ | ✅ | ❌ |
| 测试数据生命周期 | ✅ | ⚠️ | ⚠️（有 DataPool 但未用） |
| 结果通知/告警 | ✅ | ✅ | ❌ |
| 历史趋势分析 | ✅ | ✅ | ✅（Phase 5.x Dashboard） |
| AI 生成测试 | ⚠️ 实验性 | ⚠️ 部分场景 | ✅（但质量存疑） |

**ATP 最大缺失：不是 AI 能力不够，而是缺少企业级的基础设施（CI/CD 集成、多租户、环境管理、通知）。**

---

## 7. 面试官视角攻击 — 20 个尖锐问题

### 阿里测试专家

1. "你的 ApiAsset 和 Swagger 有什么区别？如果没有实际差别，为什么用户不直接用 Swagger + Newman？"
2. "Postman 有 2000 万用户，你的产品让一个 Postman 用户迁移过来，他 5 分钟内能跑通第一个测试吗？"
3. "你如何保证 AI 生成的测试用例不会污染生产数据？"
4. "你的系统如何和阿里内部的 Aone/TPM 测试平台集成？独立平台在企业内部推广几乎不可能。"
5. "被测系统有 100 个微服务，每个有不同的认证方式（JWT/OAuth2/AK），你的 API Runner 怎么处理？"
6. "谁维护 ApiAsset 的 business_intents？让开发维护——他们连 Swagger 都不愿意写。让 QA 维护——他们为什么要学一个新工具？"

### 字节 AI 产品负责人

7. "你最大的卖点是 AI。但去掉 AI 后，你的产品和 Postman + Jenkins 有什么本质区别？"
8. "你的 AI 幻觉率是多少？用户凭什么信任 AI 生成的断言？"
9. "抖音有 2000+ 接口。你的 ApiAsset 冷启动怎么做？谁录入第 1 个？第 1000 个？"
10. "你说 Test Strategy Selector 能自动判断测 API 还是 UI——但字节的经验是：这个判断最好由人做。因为只有人知道这次上线的风险点在哪。"
11. "字节的测试平台投入了 50+ 工程团队。你一个人做的东西，凭什么能和企业级竞争？"
12. "你的 AI Feedback Loop 需要多少执行数据才能生效？Phase 1 只有 10 个 Intent，根本不够。"
13. "如果你的 AI Agent 生成了一个错误的断言导致测试假通过，线上出了事故，谁来负责？"

### 腾讯质量平台负责人

14. "腾讯内部 80% 的问题不是'测不到'，而是'测了但没人看结果'。你的平台能和企业微信/飞书/钉钉集成通知吗？"
15. "你们有 SLA 吗？95% 的测试执行成功率？如果被测系统挂了，ATP 能做到自动重试吗？"
16. "多团队共用测试数据时怎么隔离？你的 DataPool 支持多租户吗？"
17. "一个 QA 团队有 20 个人，每个人有自己的测试环境。你的 platform 怎么管理 20 套环境配置？"
18. "你的 DB 断言直接查被测系统数据库——在腾讯，QA 环境不允许直接查 DB。你怎么解决？"
19. "ATP 是独立平台。但腾讯的质量体系是：需求在 TAPD → 开发在工蜂 → 测试在 QTA。ATP 如何和 TAPD/工蜂/QTA 集成？独立平台在腾讯推不动。"
20. "你说你的差异化是'质量治理闭环'——但治理的前提是有大量数据。你一个 login 模块的 10 个 Intent，有什么可治理的？"

---

## 8. 最终结论

### A. 必须保留的设计

| 设计 | 理由 |
|------|------|
| ExecutionResult 四态 + 故障归因 | 这是唯一难以被 Postman 复制的真差异化 |
| Compiler 扩展（api_request action） | 最小的必要改动，且不破坏现有逻辑 |
| ApiStepRunner（in-process 执行） | 正确的执行模式选择 |

### B. 应该删除的设计

| 设计 | 理由 |
|------|------|
| BusinessAssertion → SqlGenerator | Phase 1 直接用 `assert_sql`，不需要翻译层 |
| Test Strategy Selector | Phase 1 只有 API 测试，不需要选择器 |
| SelftestRunner 独立模块 | 10 行代码的事，合并到 ApiStepRunner |
| `expected_behavior` 复杂模型 | 先保留简单的 `scenario_type: negative`，Phase 2 再扩展 |

### C. 应该延期的设计

| 设计 | 延迟到 | 理由 |
|------|--------|------|
| API Asset Center（全量） | Phase 2 | Phase 1 只需 1 个手工 ApiAsset |
| business_intents 完整模型 | Phase 2 | Phase 1 硬编码在 YAML assertions 里 |
| DB 连接池管理 | Phase 2 | Phase 1 单连接 |
| facade run_case 分流 | Phase 2 | Phase 1 直接调 ApiStepRunner |
| AI 接入 | Phase 3 | Phase 1-2 人工构造 Intent 验证闭环 |
| 10 个 Intent | Phase 2 | Phase 1 只需 3 个（1 正 + 2 负） |

### D. 最小可成功 MVP

```text
Phase 1 MVP（缩小到 3-4 天）:

  输入: 1 个 YAML（手工写）
  流程: YAML → Compiler → ApiStepRunner → ExecutionResult
  验证: 3 个 login 场景执行通过

  代码量: ~400 行（不是 860 行）
    - execution_compiler.py 新增 api_request action 映射 (~60行)
    - api_step_runner.py: HTTP 请求 + JSON path + 简单 SQL (~200行)
    - base_executor.py: ExecutionResult 扩展 (~20行)
    - test_api_step_runner.py: 8 个单元测试 (~120行)

  不做的:
    ✗ ApiAsset 模型
    ✗ BusinessAssertion → SqlGenerator
    ✗ SelftestRunner 独立模块
    ✗ facade 分流
    ✗ DB 连接池管理
    ✗ 变量模板 {{...}} 系统（先硬编码）

  通过标准: 1 个正向 + 2 个负向场景全部通过
```

### E. 下一阶段演进路线

```text
Phase 1 (3-4天): 最小可执行闭环
  1 个 YAML → Compiler → ApiStepRunner → Result
  3 个 login 场景
  证明: API 测试能跑通

Phase 2 (1-2周): Test Knowledge Layer
  ApiAsset 模型 + 手工录入 3 个 API 的 business_intents
  DB 断言增强 + 多环境配置
  facade run_case 分流
  10 个 Intent
  证明: 基于资产的测试比 Postman 更可维护

Phase 3 (2-4周): AI 接入
  Requirement Agent（只做需求→Intent 的 NLP 提取）
  规则引擎做资产匹配 + 断言选择
  Quality Gate API/DB 规则
  证明: AI + 测试资产的协作有效

Phase 4+ (长期): 企业级能力
  多租户/权限
  CI/CD 集成
  多 Runner 并发
  DB 连接池管理
  Test Data 生命周期管理
```

---

**最终一句话：当前设计最大的问题不是技术方向错误，而是"想做太多"。把 Phase 1 缩小到 3 个场景、400 行代码、3-4 天完成，比做一个"完善但永远做不完"的 Phase 1 有价值 100 倍。**
