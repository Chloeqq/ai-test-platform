# 质量审核闭环审计报告

> **日期:** 2026-07-07
> **审查范围:** Gate 发现问题 → 人工修复 → 重新 Gate → 批准的完整闭环

---

## 1. 当前人工修复能力

### 已存在 ✅

| 能力 | API/页面 | 说明 |
|------|---------|------|
| 编辑测试点 | `PUT /api/workbench/test-point-assets/{id}` + `TestPointAssetEditPage.tsx` | 可修改 steps, expected, priority, precondition 等 |
| 修改 steps | 编辑页 `stepsText` textarea | 编辑为纯文本，保存后编译器重新解析 |
| 修改 expected | 编辑页 `expected` field | 修改后影响断言生成 |
| 保存并重新编译 | `upsert_test_point_asset` → `save_service.execute()` | 重新经过 structurer → assertion builder |
| 审核决策 | `POST /api/workbench/reviews` | approve/reject 操作 |
| quality_report | `build_test_point_asset_detail` 返回 | P0-4 已实施 |

### 缺失 ❌

| 缺口 | 影响 | 严重度 |
|------|------|--------|
| 无结构化断言编辑器 | 修改断言需要编辑 raw text，容易出错 | 🟡 |
| 无 test_data 编辑入口 | boundary 场景 value=null 无法通过编辑修复 | 🟡 |
| 无 Gate 结果驱动的修复引导 | 用户知道"零断言"但不知道应该加什么断言 | 🟡 |
| candidate_step 无法在编辑器中操作 | 占位符步骤需要完全替换 | 🟡 |
| `LOGIN_INVOLVED_ELEMENT_ALIASES` 硬编码 | 前端编辑页硬编码了 login 页的元素映射 | 🔴 违反架构约束 |

---

## 2. 当前闭环流程

```
发现问题 (quality_report.score=70, decision=REJECT)
  ↓
人工看到 (详情页 quality_report section)
  ↓
点击 "编辑" → TestPointAssetEditPage
  ↓  ⚠️ 断点1: 无 Gate 结果引导，用户不知道改什么
人工编辑 stepsText (raw textarea)
  ↓  ⚠️ 断点2: candidate_step 无法直接替换
点击 "保存" → PUT /api/workbench/test-point-assets/{id}
  ↓
编译器重新处理 steps (structurer.py → _build_expected_assertions)
  ↓
新 quality_report 计算 (下次 GET 详情页时)
  ↓
重新 Gate (如果还有问题 → 再次 REJECT)
  ↓
批准 (前端 approve 按钮)
```

### 断点分析

| 断点 | 位置 | 原因 |
|------|------|------|
| 断点1 | 编辑页初始状态 | 无 Gate 引导，用户看到空白 textarea 不知道应该写什么 |
| 断点2 | candidate_step | 无法映射到 element 的步骤，编辑后仍然无法映射 |

---

## 3. MVP 修复方案

### 不引入: 新状态机、新表、新编辑器、新审核流程

### 方案: 利用已有 API 的最小改动

**改动 1: 编辑页预填 Gate 建议 (前端)**

当前: `stepsText` 是空 textarea
建议: 预填编译后的 steps 文本 (已有 `steps_hint` 和 `raw_text`)，让用户看到"当前步骤是什么"

**改动 2: candidate_step 标记为可编辑 (前端)**

当前: candidate_step 显示为纯文本
建议: 显示警告颜色 + 提示 "此步骤无法自动执行，请替换为具体操作"

**改动 3: 前端 LOGIN_INVOLVED_ELEMENT_ALIASES 硬编码修复**

当前: `TestPointAssetEditPage.tsx` 第 ~82 行:
```typescript
const LOGIN_INVOLVED_ELEMENT_ALIASES: Record<string, string> = {
  "用户名输入框": "username_input",
  ...
}
```
这是前端硬编码。修复方向: 从 `page_elements` API 动态加载元素别名映射。

**改动 4: 编辑完成后触发 Gate 重算 (后端已就绪)**

每次 GET 详情页都重新计算 `quality_report`，无需额外改动。

---

## 4. 硬编码审计

### ❌ 发现 1 处硬编码

**`TestPointAssetEditPage.tsx`**: `LOGIN_INVOLVED_ELEMENT_ALIASES` — login 页 12 个元素别名映射硬编码在前端代码中。

```typescript
const LOGIN_INVOLVED_ELEMENT_ALIASES: Record<string, string> = {
  "用户名输入框": "username_input",
  "账号输入框": "username_input",
  ...
  "登录": "login_button",
};
```

新增页面需要在代码中加映射，违反约束 1 (禁止业务场景硬编码)。

---

## 5. 结论

```
═══════════════════════════════════════════════
闭环: 基本完整，有摩擦但可工作
═══════════════════════════════════════════════
```

| 维度 | 状态 |
|------|------|
| 发现 → 编辑 → 重新 Gate → 批准 | ✅ 闭环完整 |
| 编辑入口 | ✅ 存在 (TestPointAssetEditPage) |
| 重新编译 | ✅ 每次 save 经过 structurer |
| quality_report 更新 | ✅ 每次 GET 重新计算 |
| Gate 引导 | ⚠️ 前端未展示 quality_report |
| candidate_step 修复 | ⚠️ 无专用入口 |
| 前端硬编码 | ❌ LOGIN_INVOLVED_ELEMENT_ALIASES |

### 不建议现在做的设计

- 结构化断言编辑器 (DSL step builder UI)
- test_data 独立编辑页面
- Gate-driven repair wizard
- 自动修复 Agent
