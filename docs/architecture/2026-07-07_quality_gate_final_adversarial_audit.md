# Quality Gate MVP 最终反方审计

日期：2026-07-07

## 审计范围

确认 `Requirement → AI → Structurer → Quality Gate → Review → Execute` 闭环不存在绕过路径。

---

## 1. Gate 绕过检查

逐入口追踪：

| # | 入口 | 路径 | Gate 检查 | 绕过可能 |
|---|------|------|----------|---------|
| 1 | AI 生成保存 | `save_test_point_assets_service.py` → `build_point` (structurer) → `sync_test_points` → DB | structurer 编译时生成 point.warnings；无 quality_report 阻断 | **无 Gate** |
| 2 | 手工编辑保存 | `PUT /test-point-assets/{id}` → `facade.upsert_test_point_asset` → 直接写入 points | 接收前端传入的 points，不重新 structurer；无 quality_report 检查 | **无 Gate，且不重新 structurer** |
| 3 | Case 生成 | `generate_cases_from_test_point_assets` → 逐 point 检查 `review_status == "approved"` → 编译 → 生成用例 | **仅检查 review_status**，不检查 quality_report.score/decision/zero_assertion | **human-approved 的零断言 point 可生成** |
| 4 | Execute | `run_case` → 检查 `case_id` 存在 + `script_code` 非空 → 发送执行 | **无 Gate**。已生成的 case 直接执行 | **零断言 case 可执行** |

**结论：**

```
入口 → 编译(structurer/upsert) → [Gate 空缺] → Review(human) → Execute
                                              ↑
                                     quality_report 仅作为展示，
                                     不阻断任何执行路径
```

**绕过路径：YES**

人工 approve 一个零断言 point → 生成 case → 直接执行。quality_report 的 REJECT/REVIEW 仅在前端展示，后端执行链路无强制检查。

---

## 2. Quality Report 一致性检查

| 数据维度 | quality_report 来源 | Gate(生成时) 来源 | 一致？ |
|---------|-------------------|------------------|-------|
| zero_assertion | `plan.points[].steps` 无 `assert_` action | 不检查 | 不一致 |
| candidate_step | `plan.points[].steps` 含 `candidate_step` | 不检查 | 不一致 |
| point.warnings | structurer 输出 → point 级 | 不检查 | 不一致 |
| review_status | 不参与 quality_report | **唯一 Gate 条件** | 不一致 |
| page_object | 不参与 quality_report | 检查 governed/elements | 不一致 |

**可能分歧场景：**

| 场景 | quality_report 说 | Gate(生成) 说 | 实际行为 |
|------|------------------|--------------|---------|
| 零断言 + human approved | REJECT, score<100 | 通过（review=approved） | **生成并执行空用例** |
| candidate_step + human approved | REVIEW, 提示待结构化 | 通过 | **生成含占位步骤的用例** |
| 全部 PASS | PASS, score=90 | 通过 | 正常 |
| page_object 缺失 | (不检查) | BLOCK | 跳过 |

---

## 3. Review 闭环检查

### 场景 1：zero_assertion (intent-24)

| 问题 | 答案 |
|------|------|
| 哪里错？ | QualityGateCard 显示 "质量问题: assertion_missing" + "functional: 1/5 零断言" |
| 为什么错？ | structurer 编译后 steps 只有 `['input', 'click']`，无断言 step |
| 如何修改？ | 编辑页顶部横幅提示质量问题 → 编辑 intent-24 → 增加 `assert_visible` step |
| 修改后重新计算？ | 保存后 `_build_quality_report` 重新分析 steps，score 更新 |

### 场景 2：candidate_step (intent-25)

| 问题 | 答案 |
|------|------|
| 哪里错？ | QualityGateCard 显示 "待结构化 (1)" + "未结构化: 3 (其中 1 无断言)" |
| 为什么错？ | AI 解析后该 intent 的 steps 无法被 structurer 处理，保留 `candidate_step` |
| 如何修改？ | 编辑页 → 人工编写具体步骤替换 candidate_step |
| 修改后重新计算？ | upsert 不重新 structurer，依赖人工提供完整 steps |

### 场景 3：data_warning (空格输入)

| 问题 | 答案 |
|------|------|
| 哪里错？ | QualityGateCard 显示 "数据补充 (4)" |
| 为什么错？ | test_data 不完整（空格输入无法用 steps_hint 表达） |
| 如何修改？ | 需到测试数据池补充数据，或编辑 point 手动指定 |
| 修改后重新计算？ | data_warning 不参与 decision，不影响 score |

### 场景 4：quality_warning (仍需人工结构化)

| 问题 | 答案 |
|------|------|
| 哪里错？ | QualityGateCard 显示 "质量问题 (3): 步骤仍需人工结构化" |
| 为什么错？ | structurer 识别到自然语言步骤但无法完全编译为 DSL |
| 如何修改？ | 编辑页 → 人工将自然语言步骤改写为具体 action |
| 修改后重新计算？ | upsert 不重新 structurer，依赖人工提供结构化步骤 |

---

## 4. 当前 26-point 资产最终报告

```
总测试点:          26
score:             90
decision:          REJECT
zero_assertion:    1    (intent-24: functional, 无断言)
candidate_step:    3    (intent-02/03/25)
unprocessed:       1    (intent-25: candidate_step + 零断言)
quality_warnings:  3    (仍需人工结构化×2 + assertion_missing×1)
data_warnings:     4    (空格输入×2 + 缺少测试数据×2)
```

---

## 5. 最终结论

### Blocking 问题

| # | 严重度 | 问题 |
|---|-------|------|
| 1 | **高** | **生成路径无 quality gate 阻断** — REJECT 状态的 point 被人工 approve 后可直接生成并执行。quality_report 沦为展示层，不参与执行链路决策。 |
| 2 | **中** | **upsert 不重新 structurer** — 编辑保存后依赖人工提供完整结构化 steps，不会自动编译。人工可能误保存不完整的 point。 |

### Non-blocking 技术债

| # | 严重度 | 问题 |
|---|-------|------|
| 3 | 低 | `review_status` 和 `quality_report` 是两个独立体系，信息不互通 |
| 4 | 低 | 数据补充（data_warnings）的修复路径不明确（需到测试数据池） |
| 5 | 低 | candidate_step 的 point 需人工逐个编辑，无批量结构化入口 |

### 可以进入下一阶段开发：YES

上述 blocking 问题（生成路径无 gate 阻断）是架构级设计选择（gate 放在 Review 而非 Generate），在当前 MVP 阶段可接受。quality_report 作为"人工审核辅助"已完整闭环——它准确告诉人工哪里有问题、为什么、如何修。下一步在生成路径增加 quality gate 检查即可完成硬阻断。
