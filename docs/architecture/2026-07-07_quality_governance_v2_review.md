# 质量治理 V2 反方评审报告

> **日期:** 2026-07-07
> **角色:** 反方审查者
> **审查对象:** `quality_governance_design.md` (质量治理 V1 方案)

---

## 1. 保留的方案

### ✅ Gate 分层架构 (方案 B)

```
AI生成 → 编译 → Quality Gate → 人工审核 → Final Gate → 执行
```

**理由:** V1 的方案 A(生成后立即 Gate)不合理 — 生成的是自然语言，Gate 规则需要 DSL 步骤才能执行。方案 B 在编译后 Gate 是正确的。

**但 Gate 不是"两层"，是同一 Gate 跑两次:**
- 编译后: 全量 17 条规则
- 执行前: 仅 4 条断言完整性检查 (强制,不可跳过)

### ✅ 断言强度评分

functional ≥ assert_visible, negative/boundary ≥ assert_text 的规则设计合理。

**补充:** 需要增加 `security` 类型的特殊处理 — `assert_url` 对 security 场景是有效的(验证跳转回登录页)，不应判为弱断言。

---

## 2. 删除的方案

### ❌ Repair Agent (当前阶段)

**删除理由:**
1. Q-001 的根因是 `structurer.py` 编译 bug (assert_text → assert_url 降级)，修复编译器即可从源头消除问题
2. Auto-fix assert_url → assert_text 有风险: 自动生成的错误文案可能不匹配实际 UI
3. 增加复杂度: 新模块 + 新失败模式 + 新调试场景
4. 修复 Agent 的正确引入时机: 当 Gate 发现有 3 种以上不同的可自动修复模式时

**替代方案:** 直接修复 `structurer.py:_build_expected_assertions` 的编译逻辑

### ❌ quality_status 状态模型 (当前阶段)

**删除理由:**
1. 状态爆炸风险: asset.status + review.status + quality.status + execution.status = 4 套状态体系，用户困惑
2. `Decision` 枚举已足够: PASS/REPAIR/REVIEW/REJECT 已经表达了质量决策
3. Gate 结果是瞬时的(几百 ms)，不需要持久化中间状态

**替代方案:** 
- Gate 结果附加到 `review_summary` 而非独立状态
- `gate_score < 60 → requires_review = True, review_blocked = True` (强制审核)

### ❌ Final Gate 作为独立阶段

**删除理由:**
- 断言完整性检查可以在现有 Gate 中作为 "断言分项评分" 完成
- 新增独立 Final Gate 增加管线复杂度

**替代方案:** 在现有 Gate 评估中，如果 `assertion` 维度得分为 0，无论其他维度分数如何，最终 Decision 强制为 REJECT

---

## 3. 修改的方案

### 🔧 RULE_003 Severity: FATAL → 依赖 intent_type

**原方案:** RULE_003 (assert_url 弱断言) 统一 FATAL

**问题:** 
- `security` 场景 (intent-03: 未登录访问被拦截) 的 `assert_url:#/login` 是**正确的** — 验证用户被重定向回登录页
- `functional` 场景的 `assert_url` 可能合理 (如 "已登录刷新页面，确认仍在首页")

**修正:**

| intent_type | 最后一个断言是 assert_url | Severity |
|-------------|------------------------|----------|
| `negative` | assert_url | **FATAL** — 必须有 assert_text 验证错误文案 |
| `boundary` | assert_url | **FATAL** — 同上 |
| `format` | assert_url | **FATAL** — 同上 |
| `security` | assert_url only | **WARNING** — 合理但建议加 assert_visible |
| `functional` | assert_url | **WARNING** — 需人工确认 |
| `interaction_exception` | assert_url | **WARNING** — 需人工确认 |

### 🔧 RULE_008 Severity: FATAL → FATAL (但需要 context)

**原方案:** RULE_008 (零断言) 统一 FATAL — **保留正确**

但 V1 方案对 functional 的 "至少一个 assert_visible" 要求过于强硬:
- intent-02 (已登录刷新页面): 步骤是"刷新页面"，如果 UI 本身没有加载指示器，无法 assert_visible。此类场景可通过 `assert_url` 验证 URL 仍在首页 — 这是合理的

**修正:** 零断言 = FATAL，但 `assert_url` 对某些 functional 场景可接受 (需人工确认)

### 🔧 强制 Gate 简化: 4 条 → 2 条

**原方案:** 4 条硬规则
1. functional 必须有 assert_visible 或 assert_text
2. negative/boundary/security 必须有 assert_text
3. 所有点至少有一个 assertion
4. 不允许 candidate_step

**修正:** 合并为 2 条
1. **零断言 = FATAL** (任何类型): RULE_008 已覆盖
2. **negative/boundary 用 assert_url 替代 assert_text = FATAL**: RULE_003 加强

去掉第 4 条 (candidate_step 不应在执行前 Gate 拦截 — 应该在编译阶段就拒绝编译，或标记为 "human_required")

---

## 4. MVP 推荐实施顺序

### P0: 必须马上做 (编译层修复, 不改 Gate)

| 优先级 | 改动 | 效果 | 复杂度 |
|--------|------|------|--------|
| P0-1 | 修复 `structurer.py`: negative/boundary 场景生成 `assert_text` 而非 `assert_url` | 消除 23 个弱断言 | 低 (~20行) |
| P0-2 | 修复 `structurer.py`: 所有场景至少生成一个 assertion (没有 token 匹配时至少加 `assert_visible`) | 消除零断言 | 低 (~10行) |
| P0-3 | 重新保存资产 `mall-web-login-auth-fn-ai-0001` | 验证 27 个点全部有正确断言 | 操作 |
| P0-4 | 审核流程: 展示 Gate 评分 (`gate_score`, `grade`, 失败规则列表) | Gate 结果对审核者可见 | 前端改动 |

### P1: 可以延后

| 优先级 | 改动 | 依赖 |
|--------|------|------|
| P1-1 | Gate 评分强制: `gate_score < 60` → `review_blocked = True`, 不可批准 | P0-4 |
| P1-2 | RULE_003 按 intent_type 区分 Severity | P0-1 |
| P1-3 | candidate_step 在编译阶段拒绝: 返回 error 而非降级 | P0-2 |

### P2: 暂不做

| 优先级 | 改动 | 原因 |
|--------|------|------|
| P2-1 | Repair Agent | 修复编译器后不再需要 |
| P2-2 | quality_status 字段 | Gate 结果附加到 review_summary 即可 |
| P2-3 | Final Gate | 断言完整性检查合并到现有 Gate |
| P2-4 | Element Registry | 已有 element_binding + page_elements 表 |

---

## 5. 总结

### 保留 (5)

| 方案 | 理由 |
|------|------|
| 编译后 Gate (方案 B) | 自然语言无法被 Gate 规则检查 |
| 断言强度评分 (强/中/弱/零) | 清晰, 可量化 |
| RULE_008 = FATAL | 零断言不可执行 |
| Gate 结果展示给审核者 | 审核必须有依据 |
| assertion 维度 score=0 → 强制 REJECT | 硬编码保护 |

### 删除 (3)

| 方案 | 理由 |
|------|------|
| Repair Agent | 编译器修复后不再需要; 引入过早 |
| quality_status 独立字段 | 状态爆炸风险; Decision 枚举已足够 |
| Final Gate 独立阶段 | 合并到现有 Gate |

### 修改 (2)

| 方案 | 变更 |
|------|------|
| RULE_003 Severity | FATAL → 按 intent_type 区分 (negative/boundary=FATAL, security/functional=WARNING) |
| 强制 Gate 规则 | 4 条 → 2 条 |

### MVP 只有 4 项

```
P0-1: structurer.py 修复 (20 行)
P0-2: structurer.py 零断言兜底 (10 行)
P0-3: 重新保存资产验证
P0-4: 前端展示 Gate 报告
```

**影响:** 消除 26/27 点的断言质量问题。不新增模块、不新增字段、不新增状态。
