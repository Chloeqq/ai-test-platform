# Quality Gate MVP 模型审查

日期：2026-07-07

## 背景

Requirement → Intent → TestPointAsset → Structurer → Quality Gate → Review 闭环完成。审查当前 Quality Gate 评分/决策逻辑是否合理。

## 当前模型

```python
# _build_quality_report (workbench_asset_views.py)
if zero_assert_count > 0:
    decision = "REJECT"
    score = max(0, 100 - zero_assert_count * 10)
elif assertion_warnings:
    decision = "REVIEW"
    score = 75
elif requires_review:
    decision = "REVIEW"
    score = 80
else:
    decision = "PASS"
    score = 90
```

## 问题分析（基于 26-point 资产实测数据）

### 问题 1：`candidate_step` 被当作普通零断言惩罚

**intent-25 数据：**
```
point_type: functional
actions: ['candidate_step']           ← structurer 根本没处理
warnings: ['仍需人工结构化：打开登录页', 'assertion_missing']
```
这个 point 从未经过 structurer，没有断言是**预期行为**。当前模型把它计入 `zero_assert_count`，拉低 score。不公平。

**结论：** 未处理（unprocessed）≠ 零断言（zero_assert）。需区分。

### 问题 2：`candidate_step` + 断言共存的 point 被忽略

**intent-02 数据：**
```
actions: ['candidate_step', 'assert_visible']  ← 已有断言但含占位步骤
warnings: ['仍需人工结构化：直接访问工作台首页']
```
它有断言（不应计入 zero_assert），但 `candidate_step` 风险未被追踪。执行时占位步骤可能生成空操作。

**结论：** `candidate_step` 需单独追踪，即使当前有断言。

### 问题 3：不同 point_type 零断言权重应不同

| point_type | 零断言严重度 | 理由 |
|-----------|------------|------|
| functional | **高** | 正向功能无法验证 → 用例无效 |
| security | **高** | 安全拦截无法验证 → 安全风险 |
| negative | **高** | 异常场景无法验证 → 覆盖缺失 |
| boundary | **高** | 边界条件无法验证 → 覆盖缺失 |
| format | 低 | 格式校验通常有隐式断言 |
| interaction_exception | 低 | 交互异常有时只需观察行为 |

当前所有类型一律 -10 分。functional 和 interaction_exception 等同处理不合理。

### 问题 4：数据类 warning 不应影响 score

```
"用户名输入框 的空格输入需要后续由 DSL 数据引用执行"
"用户名输入框 输入步骤缺少明确测试数据"
```

这些是数据补全提示（告诉人工需要补充测试数据），不是结构性质量问题。当前它们混入 `other_warnings` 触发 REVIEW，但数据补充是人工常态操作。

### 问题 5：`candidate_step` 进入执行链路风险

intent-25 只有 `candidate_step` 一个 action。如果未被拦截直接进入执行引擎，会生成一个空步骤的测试脚本——不报错但也不做任何验证。当前模型只在 `per_point` 标记了 `has_candidate_step`，不影响全局 decision。

## 推荐方案

### 保留
- per_point 逐点质量数据（`has_assertion`, `has_candidate_step`, `warning_count`）
- by_point_type 分组统计
- score + decision 双输出
- assertion_warnings / other_warnings 分类

### 调整

| # | 当前 | 改为 | 理由 |
|---|------|------|------|
| 1 | `zero_assert_count` 不区分 `candidate_step` | 包含 `candidate_step` 且无断言的 point 不计入 `zero_assert_count`，输出为 `unprocessed_count` | 未处理 ≠ 零断言 |
| 2 | `candidate_step` 只在 `per_point` 标记 | 新增 `candidate_step_count` 顶层指标，进入 decision | 有执行风险，需单独追踪 |
| 3 | 所有 point_type 零断言惩罚相同 | critical 类型（functional/security/negative/boundary）权重 ×2，轻量类型（interaction_exception/format）×0.5 | 不同场景断言重要度不同 |
| 4 | 数据类 warning 影响 decision | 新增 `data_warnings`：含"空格输入"/"缺少明确测试数据"/"无法无损表达"的 warning 不参与 decision | 数据补充是人工常态 |
| 5 | REJECT 门槛为任意零断言 | 仅 critical 类型零断言 + candidate_step_count > 0 同时成立才 REJECT；其余 REVIEW | 单点问题不应阻断全局 |

### 删除
- `requires_review` 字段参与 score/decision（保留在 API 输出但不影响评分——它是上游输入）

### 不新增
- 不新增数据库字段
- 不新增状态机
- 不新增 Agent
- 不新增 API endpoint

## 调整后模型

```
score = 100
for each zero_assertion point:
    if pt in {functional, security, negative, boundary}:  score -= 20
    elif pt in {format, interaction_exception}:  score -= 5
    else:  score -= 10
score = max(0, score)

decision:
    if zero_assert(CRITICAL types) > 0 AND candidate_step_count > 0:
        → REJECT (有未处理的点 + 关键类型零断言)
    elif zero_assert_count > 0:
        → REVIEW (需要人工确认缺失的断言)
    elif candidate_step_count > 0:
        → REVIEW (有占位步骤需人工结构化)
    elif assertion_warnings:
        → REVIEW
    else:
        → PASS

输出新增:
    candidate_step_count: int
    unprocessed_count: int
    data_warnings: [str]
```

## 对当前 26-point 资产的影响预测

| 指标 | 当前模型 | 调整后 |
|------|---------|--------|
| zero_assert | 2 (intent-24, intent-25) | 1 (仅 intent-24；intent-25 为 unprocessed) |
| candidate_step | 未追踪 | 3 (intent-02, intent-03, intent-25) |
| unprocessed | 未追踪 | 1 (intent-25) |
| data_warnings | 混入 other_warnings | 2 (空格输入) |
| score | 80 | 80 (1 critical 零断言 ×20) |
| decision | REJECT | REVIEW (1 critical零断言，candidate_step=3 但不同点) |

## 决定

- [ ] 实施调整
- [ ] 仅调整部分
- [ ] 不实施
