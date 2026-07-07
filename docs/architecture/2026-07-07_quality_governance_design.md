# AI 测试资产质量治理方案

> **日期:** 2026-07-07 | **状态:** V2 反方评审已通过 (见 `quality_governance_v2_review.md`)
> **触发审计:** Q-001 ~ Q-008（质量审计报告）
> **范围:** 生成 → Gate → 审核 → 执行的完整质量闭环
>
> **V2 评审决策:**
> - ✅ 保留: 编译后 Gate, 断言强度评分, RULE_008=FATAL, Gate 结果展示
> - ❌ 删除: Repair Agent (编译器修复即可), quality_status 独立字段, Final Gate 独立阶段
> - 🔧 修改: RULE_003 按 intent_type 区分, 强制规则 4→2
> - **MVP: 4 项** (structurer.py 修复 30 行 + 重新保存资产 + 前端展示 Gate + RULE_003 分级)

---

## 1. 当前问题

| ID | 问题 | 根因 | 当前是否有 Gate 规则覆盖? |
|----|------|------|------------------------|
| Q-001 | 23/27 点 assert_url 弱断言 | 编译器让 `assert_text` 降级为 `assert_url` | ✅ RULE_003 可检测，但审核绕过 |
| Q-002 | happy path 零断言 | 编译器未给成功场景生成 assertion | ✅ RULE_008 可检测，但审核绕过 |
| Q-003 | 登录态保持零断言 | 同上 | ✅ RULE_008 可检测 |
| Q-004 | candidate_step 占位符 | AI 无法映射到页面元素 | ⚠️ RULE_016 部分覆盖 |

**根因不是 Gate 规则不够，而是:**
1. 编译阶段产生了错误步骤（assert_text → assert_url 降级）
2. Gate 执行后人工审核可以无视 Gate 结果直接批准
3. `Decision.REPAIR` 已定义但无实现

---

## 2. 目标架构 (V2 精简版)

> ⚠️ V2 评审已删除 Repair Agent 和 Final Gate。修复编译器 (structurer.py) 从源头消除问题。

```
AI 生成
  │  candidate test points (自然语言步骤)
  ▼
编译 → DSL 步骤 (structurer.py)           ← 【P0 修复: assert_url→assert_text】
  │                                          【P0 修复: 零断言兜底】
  ▼
┌─────────────┐
│ Quality Gate │ ← 17 条规则 (已有)
│  FATAL → REJECT
│  ERROR → REVIEW (强制展示 Gate 报告)      ← 【P0 强化】
│  WARNING → REVIEW
│  INFO → PASS
└──────┬──────┘
       │
       ├── PASS ──→ 可执行
       │
       ├── REVIEW ──→ 人工审核               ← 【P0 强化】
       │              │  Gate 结果必须展示
       │              │  gate_score < 60 → 不可批准
       │
       └── REJECT ──→ 记录驳回原因           ← 【已有】
```

### V2 vs V1 决策

| 组件 | V1 方案 | V2 决策 | 理由 |
|------|--------|---------|------|
| Repair Agent | 新增 | ❌ 删除 | 编译器修复后不需要 |
| Final Gate | 新增 | ❌ 删除 | 合并到现有 Gate(assertion=0→REJECT) |
| quality_status | 新增字段 | ❌ 删除 | 状态爆炸, Decision 枚举已足够 |
| structurer.py 修复 | 低优先级 | 🔼 P0 | 根因修复, MVP |
| Gate 强制 | 低优先级 | 🔼 P0 | 审核不能无视 Gate |
| RULE_003 | FATAL 统一 | 🔧 分级 | 按 intent_type 区分 (V2 review) |

---

## 3. 状态模型设计

### 当前

```
generated ──→ [Gate] ──→ pending_review ──→ approved/rejected
                              ↑
                         人工可跳过 Gate
```

### 目标

```
generated ──→ quality_checking ──→ quality_failed (REJECT)
              │                    quality_pending_repair (REPAIR)
              │                    quality_warning (REVIEW)
              │                    quality_passed (PASS)
              │
              ├── quality_passed ──→ executable
              │
              ├── quality_warning ──→ human_review
              │                         │
              │                     approved → executable
              │                     rejected → rejected
              │
              └── quality_pending_repair ──→ [Auto-fix] ──→ quality_checking (retry)
```

### 状态定义

| 状态 | 含义 | 可否生成用例? | 可否执行? |
|------|------|------------|---------|
| `generated` | AI 生成完成, 未跑 Gate | ❌ | ❌ |
| `quality_checking` | Gate 执行中 | ❌ | ❌ |
| `quality_passed` | Gate PASS, 无需审核 | ✅ | ✅ |
| `quality_warning` | Gate 有 WARNING | ❌ | ❌ 需审核 |
| `quality_pending_repair` | Gate 有 ERROR, 可自动修复 | ❌ | ❌ |
| `quality_failed` | Gate FATAL, 不可修复 | ❌ | ❌ |
| `human_review` | 等待人工审核 | ❌ | ❌ |
| `approved` | 人工通过 | ✅ | ✅ |
| `rejected` | 驳回 | ❌ | ❌ |
| `executable` | 可执行 | ✅ | ✅ |

### 状态流转规则

```
generated → quality_checking (自动)
quality_checking → quality_passed | quality_warning | quality_pending_repair | quality_failed (Gate 决定)
quality_pending_repair → quality_checking (修复 Agent 成功后)
quality_warning → approved | rejected (人工)
approved → executable
quality_passed → executable
```

---

## 4. Gate 策略: 规则分级 + 决策矩阵

### 规则 Severity → Decision 映射

| Severity | 含义 | Decision | 动作 |
|----------|------|----------|------|
| FATAL | 用例完全无效 | REJECT | 记录原因, 不进执行 |
| ERROR | 可自动修复的缺陷 | REPAIR | 触发修复 Agent |
| WARNING | 需人工确认 | REVIEW | 展示 Gate 报告给审核者 |
| INFO | 提示 | PASS | 直接通过 |

### Q-001 ~ Q-004 分级

| ID | Severity | 原因 |
|----|----------|------|
| Q-001 (assert_url 弱断言) | **FATAL** | 23 个 negative/boundary 点只检查 URL, 全部会假通过 |
| Q-002 (happy path 零断言) | **FATAL** | 核心功能无验证, 执行无意义 |
| Q-003 (登录态零断言) | **FATAL** | 同上 |
| Q-004 (candidate_step) | **ERROR** | 可修复: 人工替换为可执行步骤 |

### 规则分类 → 决策表

| 规则 | 类别 | Severity | → Decision |
|------|------|----------|-----------|
| RULE_001 | data | ERROR | REPAIR |
| RULE_002 | data | ERROR | REPAIR |
| RULE_003 | assertion | FATAL | REJECT |
| RULE_004 | dependency | WARNING | REVIEW |
| RULE_005 | dependency | ERROR | REPAIR |
| RULE_006 | page_object | ERROR | REPAIR |
| RULE_007 | data | INFO | PASS |
| RULE_008 | assertion | FATAL | REJECT |
| RULE_009 | assertion | ERROR | REPAIR |
| RULE_010 | data | ERROR | REPAIR |
| RULE_011 | semantic | WARNING | REVIEW |
| RULE_012 | semantic | WARNING | REVIEW |
| RULE_013 | dependency | WARNING | REVIEW |
| RULE_014 | page_object | ERROR | REPAIR |
| RULE_015 | semantic | ERROR | REPAIR |
| RULE_016 | semantic | FATAL | REJECT |
| RULE_017 | semantic | WARNING | REVIEW |

### 强制 Gate: 断言完整性最终检查

无论 Gate 决策是什么，以下检查在执行前**强制执行**且不可被人工覆盖:

1. **所有 functional 点必须有 `assert_visible` 或 `assert_text`**（不能只有 assert_url）
2. **所有 negative/boundary/security 点必须有 `assert_text`**（必须有错误文案验证）
3. **所有点必须至少有一个 assertion**
4. **不允许 `candidate_step` 进入执行**（必须全部分解为可执行步骤）

---

## 5. Assertion 质量体系: 按 intent_type 最低要求

| intent_type | 最低断言 | 说明 | 反例 |
|-------------|---------|------|------|
| `functional` | `assert_visible` 或 `assert_text` | 验证业务结果可见或文案出现 | intent-01: 只有 input+click,无断言 ❌ |
| `negative` | `assert_text` | 必须验证错误文案,不能只 assert_url | intent-04: assert_url:#/login ❌ |
| `boundary` | `assert_text` | 同上 | intent-08~20: assert_url:#/login ❌ |
| `security` | `assert_visible` + `assert_url` | 验证跳转回登录页 + 确认保护内容不可见 | intent-03: assert_url only ⚠️ |
| `format` | `assert_text` | 验证格式错误提示 | intent-21~23: assert_url only ❌ |
| `interaction_exception` | `assert_attribute` 或 `assert_visible` | 验证交互状态变化 | intent-26: 无断言 ❌ |

### 断言强度评分

| 强度 | 断言类型 | 适用场景 | 分值 |
|------|---------|---------|------|
| 强 | `assert_text` + 具体错误文案 | negative/boundary | 100% |
| 中 | `assert_visible` + 具体元素 | functional/success | 70% |
| 弱 | `assert_url` 仅检查 URL | 仅限辅助验证 | 30% |
| 零 | 无任何断言 | 不可接受 | 0% |

---

## 6. 质量评分模型

### 当前

```
总分 = Σ category_score × (1 - penalty_ratio)
  5 个维度: data(30) + assertion(30) + semantic(20) + dependency(10) + page_object(10) = 100
```

### 建议优化: 断言加权

```
assertion 维度权重从 30 → 40
  - 零断言: assertion 直接归零 → 总分上限 70
  - 弱断言: assertion 扣 50% → 总分上限 85
  - 强断言: assertion 满分

新增 gate_override: 
  如果 assertion_score = 0 → 强制 REJECT (不可被人工覆盖)
```

### 最低可执行分数: 60

```
grade = A/B/C/D/F
  A(90+): 直接入库
  B(75-89): 直接入库
  C(60-74): 人工审核
  D(40-59): 需修复
  F(<40): 驳回
```

---

## 7. 改造优先级 (V2 MVP)

### P0: 编译层修复 (MVP, 预计 30 行代码)

| # | 改动 | 文件 | 效果 |
|---|------|------|------|
| 1 | `_build_expected_assertions`: negative/boundary/format → 生成 `assert_text` 而非 `assert_url` | `structurer.py` | 消除 23 个弱断言 |
| 2 | ✅ 零断言标记 requires_review | `structurer.py` | 已实施 (cea5dd8) |
| 3 | 🔲 重新保存资产 | 操作 | 待手动执行 |
| 4 | 审核页展示 Gate 报告 (`gate_score`, `grade`, 失败规则) | 前端 | Gate 对审核者可见 |

### P1: Gate 强化

| # | 改动 | 依赖 |
|---|------|------|
| 5 | ✅ Gate 保护 — 零断言点不可批准 | 已实施 (d98b606) |
| 6 | RULE_003 按 intent_type 分级 | ⬜ P1 |
| 7 | candidate_step 在编译阶段拒绝而非降级 | P0-2 |

### P2: 暂不做

| # | 原方案 | 删除理由 |
|---|--------|---------|
| - | Repair Agent | 编译器修复后不再需要 |
| - | quality_status 字段 | 状态爆炸; Decision 枚举已足够 |
| - | Final Gate 独立阶段 | 合并到现有 Gate (assertion=0 → REJECT) |
| - | Element Registry | 已有 element_binding + page_elements 表 |

---

## 8. 结论

```
═══════════════════════════════════════════════
Gate 规则体系完整, 问题在编译层 + 审核可绕过
═══════════════════════════════════════════════
```

**不需要新增 Gate 规则, 17 条已足够。**
**需要修复的是: 编译器生成正确步骤 + 审核不能无视 Gate。**
