# 质量闭环 MVP 优化报告

> **日期:** 2026-07-07 | **状态:** ✅ P0-5~P0-8 已实施 (c802738)
> **审查范围:** TestPointAssetEditPage + save_service 编辑→重新编译闭环

---

## 1. 当前闭环完整度评分: **35/100**

| 阶段 | 状态 | 得分 |
|------|------|------|
| Gate 发现问题 | ✅ quality_report 已实施 | 10/10 |
| 人工看到问题 | ⚠️ API 有数据但前端未展示 | 5/10 |
| 人工编辑 | ❌ 编辑后全部变成 candidate_step | 5/30 |
| 重新编译 | ❌ upsert 路径不经过 structurer | 0/30 |
| 重新 Gate | ❌ 无重新编译则无新 Gate 结果 | 0/10 |
| 批准 | ✅ approve API 存在 | 10/10 |

---

## 2. 当前编辑能力矩阵

| 能力 | 已支持 | 缺口 | 严重等级 |
|------|--------|------|---------|
| 修改 steps 文本 | ✅ textarea 可编辑 | 保存后全部变成 candidate_step | 🔴 P0 |
| 修改 expected | ✅ text field | 修改后不经过编译器重新生成断言 | 🔴 P0 |
| 修改 test_data | ❌ 无入口 | 无法修复 value=null | 🟡 P1 |
| 修复 candidate_step | ❌ 无法 | 编辑器发送时也变成 candidate_step | 🔴 P0 |
| 保存后重新编译 | ❌ 不经过 | 直接替换 points，绕过 structurer | 🔴 P0 |
| 修改 assertion | ❌ 无入口 | 只能通过改 expected 间接影响 | 🟡 P1 |

---

## 3. 核心 Bug: `payloadPoint()` 破坏闭环

**`TestPointAssetEditPage.tsx`: 行 ~330**

```typescript
const steps = splitLines(candidate.stepsText).map((step) => ({
    action: "candidate_step",  // ← 🔴 永远 candidate_step!
    target: "",
    value: step,
    raw_text: step,
}));
```

**连锁反应:**

```
用户编辑 stepsText → 保存 → payloadPoint() → 全部 candidate_step
  → PUT /api/test-point-assets/{id}
    → upsert_test_point_asset()
      → if incoming_points: points = incoming_points ← 🔴 直接替换,不经过编译器!
        → 写文件 + 写 DB
          → quality_report 显示零断言 (因为全是 candidate_step)
```

**闭环断裂点:** 编辑→保存路径绕过了 `structured_steps_from_candidate` → `_build_expected_assertions`。

---

## 4. Gate 问题驱动的修复能力 — 逐项模拟

### Q-001: negative assert_url 弱断言

| 问题 | 答案 |
|------|------|
| 人工知道哪里错? | ❌ 前端未展示 quality_report |
| 人工知道为什么错? | ❌ 原因不在编辑页中 |
| 人工知道怎么修改? | ❌ 编辑页无引导 |
| 修改入口? | ⚠️ 只能改 expected 文本, 保存后全变 candidate_step |

### Q-002: functional 零断言

同上 — 修改后断言反而消失 (变 candidate_step)

### Q-004: candidate_step 占位符

编辑后仍然是 candidate_step — 无法修复

### Q-007: boundary value=null

编辑页无 test_data 入口 — 无法修复

---

## 5. 硬编码审计

### ❌ 发现 3 处硬编码 (前端)

| # | 文件:行号 | 硬编码 | 违反约束 |
|---|----------|--------|---------|
| 1 | `TestPointAssetEditPage.tsx`: `LOGIN_INVOLVED_ELEMENT_ALIASES` | 12 个 login 页元素映射 | 约束 1 (业务场景硬编码) |
| 2 | `TestPointAssetEditPage.tsx`: `page !== "login"` | 页面名判断 | 约束 1 (业务场景硬编码) |
| 3 | `TestPointAssetEditPage.tsx`: `"用户名输入框": "username_input"` | 映射到旧 element_code | 约束 1 (错误映射) |
| 4 | `TestPointAssetEditPage.tsx`: `payloadPoint()` | `action: "candidate_step"` 硬编码 | 约束 1 (破坏编译器) |

### 后端无新增硬编码 ✅

---

## 6. 阻塞执行的问题 (P0 — ✅ 已实施)

| # | 问题 | 方案 | 改动 | 状态 |
|---|------|------|------|------|
| P0-5 | `payloadPoint()` 总生成 candidate_step | 前端传 raw text, 后端 build_point() 编译 | `TestPointAssetEditPage.tsx` | ✅ |
| P0-6 | `upsert` 直接替换 points 不编译 | 后端 `_steps_from_candidate` → `structured_steps_from_candidate` | `facade_helpers.py` | ✅ |
| P0-7 | `LOGIN_INVOLVED_ELEMENT_ALIASES` | 全部删除, 后端 ElementResolver 解析 | `TestPointAssetEditPage.tsx` | ✅ |
| P0-8 | `page !== "login"` 硬编码 | 删除分支, 统一走 API | `TestPointAssetEditPage.tsx` | ✅ |

> commit: `c802738` — 2 文件, +34/-69 行. 验证: 4/4 cases passed.

## 7. 可以延后 (P1)

| # | 问题 | 修复方案 |
|---|------|---------|
| P1-1 | ✅ quality_report 展示 | 已实施 (b753b60) |
| P1-2 | ✅ Gate 保护 — 零断言不可批准 | 已实施 (d98b606) |
| P1-3 | 无 Gate 引导修复 | ⬜ 延后 |

## 8. 明确不要做 (P2)

- DSL 步骤结构化编辑器
- Repair Agent
- 自动修复
- 新状态字段
- 新数据库表

---

## 9. 进入代码阶段允许修改的文件

| 文件 | 改动 | P0 |
|------|------|-----|
| `TestPointAssetEditPage.tsx` | 修复 payloadPoint, 删除硬编码映射 | P0-5/7/8 |
| `facade_test_point_assets.py` | upsert 时重新编译 points | P0-6 |

**仅 2 个文件, ~40 行改动。**

---

## 10. 结论

```
═══════════════════════════════════════════════
闭环评分: 35/100。存在 P0 断裂: 编辑→保存不经过编译器。
═══════════════════════════════════════════════
```

**必须修复 P0-5→P0-8 才能形成有效闭环。** 否则任何编辑操作都会把 DSL 步骤降级为 candidate_step，让质量审计和 Gate 修正全部失效。
