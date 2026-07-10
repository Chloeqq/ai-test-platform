# ATP MVP v3.1 开发冻结版

**版本**：v3.2 Frozen — Sprint 1 + Sprint 2 全部完成
**日期**：2026-07-10
**状态**：✅ 已冻结，104 tests passed，Demo 全链路跑通
**代码位置**：runners/api_python/
**相关文档**：
- `2026-07-10_mvp_redesign_committee_decision.md` — 委员会决议
- `2026-07-10_adversarial_architecture_audit.md` — 反方审计

---

## 一句话定位

ATP 是一个通过业务 Oracle 验证 AI 生成测试可信度的测试质量平台。它通过 LLM 理解业务需求生成 Test Intent，经人工确认后执行确定性 API/DB 验证作为业务真相源，接入已有 UI 测试结果进行断言校准，识别假通过与弱断言，并通过故障归因区分平台问题与被测系统问题。

---

## 一、MVP 核心闭环

```text
用户需求
   │
   ▼
Requirement Parser (LLM)
   │
   ▼
TestIntent
   │
   ▼
Human Review
   │
   ├──────────────────────────────┐
   ▼                              ▼
Execution Engine              UIEvidence
   │                         (外部 UI 测试结果接入)
   ├── API 验证                  │
   │   (被测系统实际行为)          │
   ├── SQL 验证                  │
   │                             │
   ▼                             ▼
API/SQL Result              UI Result
   │                             │
   └──────────┬──────────────────┘
              ▼
     Layer Comparator
 (以 Business Intent 为基准)
    ├── 意图 vs API: 后端是否正确实现了业务意图？
    └── 意图 vs UI:  前端是否正确展示了业务意图？
              │
              ▼
         Test Report
   (intent_aligned /
    intent_api_divergence /
    intent_ui_divergence)
```

---

## 二、明确 AI 边界

### AI 做

输入示例：

```
验证登录：
正确密码可以登录
错误密码拒绝
空用户名失败
```

输出示例：

```json
{
  "intents": [
    {
      "name": "login_success",
      "scenario": "positive"
    },
    {
      "name": "login_failed",
      "scenario": "negative"
    }
  ]
}
```

### AI 不做

```
❌ 猜接口地址
❌ 猜 HTTP 状态码
❌ 猜数据库字段
❌ 猜业务规则
❌ 自动生成 SQL
```

**原因：这些属于确定性知识。**

---

## 三、核心数据模型冻结

### 1. TestIntent

```python
class TestIntent(BaseModel):
    name: str
    scenario: Literal["positive", "negative", "boundary"]
    api_request: ApiRequest
    assertions: list[Assertion]
    db_assertions: list[SQLAssertion] = []
```

### 2. ExecutionResult

```python
class ExecutionResult(BaseModel):
    intent_name: str
    status: Literal["passed", "failed"]
    assertions: list
    failure_layer: Optional[str]
    evidence: dict
```

### 3. TestReport

```python
class TestReport(BaseModel):
    summary: str
    results: list[ExecutionResult]
    calibrations: list[CalibrationFinding] = []
    findings: list
    confidence_level: str
```

### 4. UIEvidence（输入 DTO，非核心 Model）

> ATP 不负责执行 UI 测试。
> ATP 负责接入已有 UI 自动化结果，判断其是否可信。

```python
class UIEvidence(BaseModel):
    """外部 UI 测试结果接入合约。Phase 1 支持 Playwright JSON 输出。"""
    case_id: str
    intent_name: str            # 与 API TestIntent.name 对齐
    status: str                 # "passed" | "failed"
    assertions: list[UIAssertion]

class UIAssertion(BaseModel):
    type: str                   # "assert_text" | "assert_visible" | "assert_url"
    target: str                 # element code
    expected: str               # AI 推测的期望值
    actual: str = ""            # 实际值（如果 Runner 能提供）
```

---

## 四、执行引擎设计冻结

### API Runner

只支持：POST、headers、body。断言：`status`、`json_path`。

```yaml
api_request:
  method: POST
  path: /admin/login
  body:
    username: admin
    password: xxx

assertions:
  - type: status
    expected: 200
  - type: json
    path: data.token
    operator: exists
```

### SQL Runner

只支持：直接 SQL + exists / value 断言。

```yaml
db_assertion:
  sql: "select count(*) from sessions where user_id=1"
  expected:
    value: 1
```

**不要：** BusinessAssertion、SqlGenerator。

---

## 五、故障归因冻结

```text
Failure Attribution:

Layer A: Platform
Layer B: Network
Layer C: API Contract
Layer D: Business Rule
```

示例：

```text
HTTP 200 → API 正常连接 → JSON 结构正常 → 业务断言失败 (body.code=500, expected=200)

归因: Business Rule Failure (被测系统将认证失败返回为 HTTP 200 而非 401)
```

---

## 六、Layer Comparator（分层对比器）

> **v3.2 语义修正**：原名 "Assertion Calibrator"，隐含 "API 是正确答案，用 API 修正 UI" 的假设。
> 但 API 本身也可能返回错误结果（后端 Bug）。因此改为以 **Business Intent（业务意图）为基准**，
> 分别对比 "意图 vs API" 和 "意图 vs UI"，报告偏离，由人判断。

### 核心逻辑

```text
以 Business Intent 为基准的双向对比:

  Business Intent（业务意图 — 基准）
  "错误密码应返回认证失败"
  "应提示错误信息"
       │
  ┌────┴────┐
  ▼         ▼
API 结果   UI 结果
code=200   assert_text PASS
msg="密码   (碰巧匹配)
不正确"

  Layer Comparator 对比:

  意图 vs API (intent_api_divergence):
    "意图要求认证失败，但 API 返回 HTTP 200 而非 401"
    → 后端实现偏离了业务意图
    → 可能原因: 未按 RESTful 规范实现认证失败

  意图 vs UI (intent_ui_divergence):
    "意图要求展示错误信息，UI 断言 target=button 而非 error 元素，
     且 expected='请输入密码' 与 API 实际返回的'密码不正确'不符"
    → 前端展示偏离了业务意图
    → 可能原因: A)UI断言目标错了 B)UI断言期望值错了 C)UI校验未触发
```

### 关键变化

```text
之前（v3.1 Assertion Calibrator）：
  对比的是 API ↔ UI
  隐含: API 是正确答案，UI 错了就按 API 修正

现在（v3.2 Layer Comparator）：
  对比的是 意图 vs API + 意图 vs UI
  基准: Business Intent（需求/业务目标）
  API 和 UI 都可能是错的
  不做修正建议，只报告偏离
```

### 输出格式

```python
class LayerComparison(BaseModel):
    intent_name: str
    divergences: list[LayerDivergence]

class LayerDivergence(BaseModel):
    direction: Literal[
        "intent_api",          # 意图 vs API — 后端是否正确实现了业务意图？
        "intent_ui",           # 意图 vs UI  — 前端是否正确展示了业务意图？
    ]
    intent_expected: Any = None   # 业务意图期望的值
    actual_value: Any = None      # 实际返回/展示的值
    actual_source: str = ""       # "api" | "ui"
    description: str              # 人类可读的偏离描述
    possible_causes: list[str]    # 可能的原因(A/B/C)
    requires_human: bool = True   # 是否需要人工判断
```

---

## 七、Test Reliability Gate（测试可信度门）

命名为"Test Reliability Gate"而非"Quality Gate"——后者容易被理解成 Jenkins 门禁。

```text
执行前:

TestIntent
     │
     ▼
Test Reliability Gate

检查:
  1. 是否存在弱断言 (assert_url only)
  2. 是否缺少业务验证 (assertion_count == 0)
  3. 是否存在 AI 幻觉 (expected_value 为推测值)
  4. 是否可能假通过 (negative 场景错误断言类型)

     │
     ▼
Trusted Execution
```

**已有实验基础**：24 条 login 用例经 Reliability Gate 检查 — 16 条 REJECT（假通过风险）、7 条 PASS（可信）、1 条 REVIEW（需人工确认）。

**没有 Test Reliability Gate，ATP 和普通自动化工具没有区别。**

---

## 八、明确不开发列表

```text
Phase 1 不做：

❌ ApiAsset Center
❌ BusinessIntent Center
❌ OpenAPI Import
❌ UI Runner
❌ Strategy Selector
❌ Multi Agent
❌ Test Data Platform
❌ Knowledge Graph
❌ CI/CD Plugin
```

**写进开发 README。避免 AI 偷加功能。**

---

## 九、Demo Story（必须使用 24 条历史审计数据）

> ATP 的护城河。不要 Demo "输入需求→生成→执行"这种通用流程。
> 必须展示：有真实数据证明 AI 生成 UI 测试存在可信度问题，ATP 是解决这个问题的系统。

### Step 1：展示历史问题（30 秒）

```text
"在构建 ATP 之前，我先对 AI 生成的 24 条 login UI 测试用例做了全量审计。

 结果:
   - 40% 存在虚假通过风险
   - 25% 无法执行
   - 50% 包含 AI 推测的错误文案

 例如这条 '账号为空点击登录':
   断言: assert_text(target=login-submit-btn, value='请输入账号')
   问题1: 错误文案出现在 toast 元素，不在 button 上
   问题2: '请输入账号' 是 AI 推测的，真实系统返回 'username:不能为空'
   问题3: 即使这个断言碰巧通过，也不能证明被测系统做了空值校验"
```

### Step 2：运行 ATP API Oracle（30 秒）

```text
"ATP 的方案是: AI 不猜测确定性知识。

 输入需求 '验证登录功能' → AI 输出 Test Intent → 人工确认后
 → 执行 API 验证拿到业务真相:

   POST /admin/login {username: "", password: "macro123"}
   → 200 {code: 404, message: "username:不能为空"}

 这就是 Oracle——被测系统的真实行为。"
```

### Step 3：校准历史 UI 用例（1 分钟）

```text
"接入之前审计的 24 条 UI 用例结果，ATP 的 Assertion Calibrator
 逐条对比 API Oracle 和 UI 断言:

   原始 UI 断言:
     assert_text(target=login-submit-btn, value='请输入账号')

   ATP 发现:
     wrong_expected_value: '请输入账号' → 'username:不能为空'
     wrong_assertion_target: button → error/toast 元素
     风险: FALSE_PASS_HIGH

 24 条用例的校准结果:
   - 8 条 business_aligned (API Oracle + UI 一致)
   - 14 条 ui_assertion_risk (UI 断言需要修复)
   - 2 条 valid_business_failure (确实发现了 Bug)"
```

### Step 4：价值总结（30 秒）

```text
"ATP 不是一个 AI 生成测试的工具。

 它是一个通过业务 Oracle 验证 AI 生成测试可信度的平台。

 核心能力:
   1. AI 理解需求意图（不猜测确定性知识）
   2. API/DB 作为业务真相源
   3. 接入已有 UI 测试结果进行可信度校准
   4. 故障归因（平台问题 vs 被测系统问题）

 与 Postman 的区别:
   Postman 告诉你: 第 47 个断言失败了。
   ATP 告诉你: 这个断言不可信，为什么不可信，以及怎么修正。"
```

---

## 十、开发顺序

### Sprint 1：API Engine ✅ 已完成

| 天 | 任务 | 状态 |
|----|------|------|
| Day 1 | ExecutionResult Model + API Runner + JSON Assertion | ✅ 19 tests |
| Day 2 | SQL Assertion + Evidence Collector | ✅ 26 tests |
| Day 3 | Fault Attribution（四层诊断） | ✅ 37 tests |
| Day 4 | Test Reliability Gate | ✅ 55 tests |
| Day 5 | 3 个 Login 场景跑通（真实 mall 系统） | ✅ 3/3 integration |

### Sprint 2：AI + 可信度闭环 ✅ 已完成 (44 tests)

> **v3.2 调整**：Day 8 从 "Assertion Calibrator" 改为 "Layer Comparator"。
> 原因：Calibrator 隐含 "API 是正确答案" 的假设，但 API 本身也可能返回错误结果。
> Layer Comparator 对比 Spec ↔ API ↔ UI 三层，报告不一致，不判断对错。

| 天 | 任务 | 说明 |
|----|------|------|
| Day 6 | Requirement Parser + LLM Prompt | AI 从需求文本提取 Test Intent |
| Day 7 | UIEvidence Adapter | 接入已有 UI 测试结果 JSON |
| Day 8 | **Layer Comparator**（Spec ↔ API ↔ UI 对比） | 三层不一致检测 + 可能原因枚举 + 人工判断标记 |
| Day 9 | Report UI | 展示对比结果 + 不一致报告 + 可信度标注 |
| Day 10 | Demo 打磨 | 用 24 条历史审计数据演示全链路 |
