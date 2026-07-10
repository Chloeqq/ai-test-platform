# ATP v3.3 修正版 — 基于终审反馈

**版本**：v3.3（v3.2 + 定位修正 + Risk Classifier + Sprint 2.5）
**日期**：2026-07-10
**触发**：反方终审报告 `2026-07-10_adversarial_audit_v3_2_final.md`
**原则**：不推翻 v3.2，只增量修正三个致命问题

---

## 一、定位修正

```text
v3.2 定位：
  "通过业务 Oracle 验证 AI 生成测试可信度的平台"

问题：
  → "验证"暗示 ATP 能做"判断"
  → 反方攻击准确：100% requires_human = 没有判断能力

v3.3 定位：
  "通过多源测试证据发现 AI 生成 UI 测试的可信风险，
   并提供可追溯证据链的平台"

区别：
  - 不是"判断是否正确"，而是"发现风险"
  - 不是"给出结论"，而是"提供证据链"
  - 类比：Datadog — 告诉你异常在哪、证据是什么，最终工程师判断
```

---

## 二、三大修正

### 修正 1：自动 Risk Rules（解决 100% requires_human）

```text
当前（v3.2）：
  所有 divergence → requires_human: True
  自动化判定率 = 0%

修正后（v3.3）：
  新增 ReliabilityClassifier — 自动判定规则引擎

  自动规则示例：

  Rule: zero_assertion
    条件: UI assertions 为空
    → risk=HIGH, confidence=1.0, auto=true
    → 不需要人工

  Rule: button_as_error_target
    条件: assertion_type=text AND target ends_with "-btn" AND expected 含 error 语义
    → risk=HIGH, confidence=0.92, auto=true
    → 不需要人工

  Rule: api_ui_message_mismatch
    条件: API response.message ≠ UI assertion.expected AND both are error messages
    → risk=HIGH, confidence=0.85, auto=true
    → 不需要人工

  Rule: backend_failure_ui_pass
    条件: API status=failed AND UI status=passed AND UI assertions 为空
    → risk=CRITICAL, confidence=0.95, auto=true
    → 不需要人工

  Rule: multi_source_inconsistency
    条件: API PASS + DB NOT_EXISTS
    → risk=HIGH, confidence=0.88, auto=true
    → 标记为 api_db_divergence（不是 UI 问题）

  目标：自动判定率 > 40%（不是现在的 0%）
```

### 修正 2：多源 Evidence Graph（解决 Oracle 悖论）

```text
当前（v3.2）：
  Spec → API → UI 线性对比
  任何一个源错误都检测不到

修正后（v3.3）：
           Spec (需求/契约)
             |
     ┌───────┼───────┐
     │       │       │
    API     DB       UI
     │       │       │
     └───────┼───────┘
             ▼
      Evidence Graph
    (多源交叉验证)

  交叉验证规则：
    - API 返回 token + DB session 未创建 → api_db_divergence
    - API 返回 error + DB 有 session → data_consistency_error
    - API+DB 一致 + UI 不一致 → high_confidence_ui_issue
    - API+DB+UI 三者一致 → aligned（高可信）

  不再依赖单一 Oracle。两个独立源交叉验证。
```

### 修正 3：UIEvidence 扩展字段（解决证据不足）

```text
当前（v3.2）：
  UIEvidence: case_id, status, assertions[type, target, expected, actual]

修正后（v3.3）：
  UIEvidence 新增（全部 optional，不强制）：
    - screenshot_url: str   — 失败截图
    - dom_snapshot: str     — 失败时 DOM 快照
    - trace_url: str        — Playwright trace
    - network_logs: list    — API 调用日志
    - console_logs: list    — 浏览器控制台日志

  注意：ATP 不产生这些数据。ATP 只接入已有数据。
       这些字段为空不影响核心功能，但有它们时 Risk Classifier
       可以做更准确的判断。
```

---

## 三、新增组件：Risk Classifier

```text
runners/api_python/risk_classifier.py (~150行)

class RiskClassified:
    intent_name: str
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
    reasons: list[str]           # 判定理由
    evidence: list[str]           # 证据引用（API/DB/UI）
    auto: bool                    # true=自动判定, false=需人工
    confidence: float             # 0.0 ~ 1.0

class ReliabilityClassifier:
    rules: list[RiskRule]  # 可扩展的规则列表

    def classify(layer_comparison, api_result, ui_evidence) → RiskClassified:
        逐条规则匹配 → 第一个命中的返回
        无规则命中 → requires_human=True, risk=MEDIUM

RiskRule 接口:
    name: str
    condition: (comparison, api_result, ui_evidence) → bool
    risk_level: str
    confidence: float
    auto: bool
    reasons: list[str]
```

---

## 四、Sprint 2.5 验收指标

```text
目标：证明 ATP 能自动发现历史 24 条 UI 用例中的主要风险

| 指标                        | 目标    |
| --------------------------- | ------- |
| 发现 zero assertion         | 100%    |
| 发现 weak assertion         | 90%+    |
| 发现 wrong target           | 80%+    |
| 发现 API/UI message mismatch | 80%+    |
| 自动判定率（非人工）         | > 30%   |
| 人工判断比例                 | < 70%   |

Demo 叙事修正：
  不是展示 "API PASS + UI FAIL = 差异报告"（太像报告工具）
  而是展示 "发现 FALSE_PASS_HIGH 风险 + 证据链"
```

---

## 五、v3.2 → v3.3 改动清单

```text
新增文件 (2个):
  runners/api_python/risk_classifier.py       Risk Rules + Classifier
  runners/api_python/tests/test_risk_classifier.py   ~15 tests

修改文件 (3个):
  runners/api_python/layer_comparator.py      +evidence_graph 交叉验证
  runners/api_python/report_builder.py        +risk_level 展示
  services/atp_bridge.py                      +classifier 集成

不改文件:
  ✅ executor/api_step_runner.py
  ✅ gate/test_reliability_gate.py
  ✅ requirement_parser.py
  ✅ ui_evidence_adapter.py
  ✅ routers/atp_api.py
  ✅ main.py

代码量: ~300 行新增 + 测试
```

---

## 六、最终裁定

```text
反方审计结论：接受（三个致命问题成立）
停止建议：不接受（MVP 阶段不应追求生产级完备）

修正后的进入标准：
  ✅ v3.2 引擎代码质量合格（116/116 tests）
  ✅ 定位从"判定器"修正为"风险分析器"
  ✅ 自动判定率 > 30%（不再是 0%）
  ✅ 多源交叉验证（不再依赖单一 Oracle）
  → 可以进入真实系统接入阶段

产品判断：
  ATP 不是 AI 版 Allure 报告器。
  ATP 是 AI 测试可信风险分析平台。
  不判断对错，只发现风险 + 提供证据链。
```
