# 2026-04-02 orchestrator 多源闭环剩余任务清单

## 2026-04-02 完成状态

当前这份 backlog 已完成主任务收口，状态应更新为：

- `最小闭环`：已完成
- `治理级闭环`：已完成第一版

本轮已落地：

- `source_inputs / source_ids / reference_ids` 统一
- `change_impact` 结构增强
- OpenAPI / Git Diff / defect 工具抽取深度增强
- `requirement -> test points -> case` 追溯矩阵打通
- parser / fallback explainability 增强
- 多源摘要已接入 preview、execution record、task summary、governance overview 消费面
- 回归结果已提升到：`190 passed, 1 skipped`

当前剩余内容不再属于“闭环未完成”，而属于后续迭代优化项，例如：

- 更复杂的冲突裁决策略
- 更细粒度的 change impact 解释
- manager 视角更强的趋势分析和排序模型

## 当前判断

当前 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 已经具备“最小多源闭环”：

- 空 schema/tool 文件已补齐
- `openapi_spec / git_diff / defect_ticket` 已接入 fallback 主链
- `RequirementSpecV1` 已能输出：
  - `source_inputs`
  - `parameter_constraints`
  - `business_rules`
  - `change_impact`
  - `coverage_matrix.traceability_status`
- 已有基础回归：
  - [test_requirement_parser_multisource.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_requirement_parser_multisource.py)
  - [test_multisource_fallback_tools.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_multisource_fallback_tools.py)

但当前还没有达到“平台治理级闭环”。主要缺口集中在：

- 多源抽取深度仍偏启发式
- `requirement -> test points -> case/yaml` 的追溯约束还不够强
- `change_impact / traceability / business_rules` 的消费面还不够统一
- 多源链路的异常、降级、冲突覆盖还不够完整

## 优先级总览

1. `P0` 先补“结构化一致性”和“回归护栏”
2. `P1` 再补“多源抽取深度”和“治理消费面”
3. `P2` 最后做“解释增强”和“平台级分析联动”

---

## P0：结构化一致性与护栏（已完成）

### 1. 统一 `source_inputs` / `reference_ids` / `source_ids` 约束（已完成）

目标：

- 让 requirement、test intents、test points、coverage matrix 使用一致的 source id 语义
- 避免当前“有输入来源，但点位和覆盖矩阵无法稳定追溯”的情况

改动点：

- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
- [test-point.schema.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/schemas/test-point.schema.py)

执行项：

- 为 `source_inputs` 生成稳定 `source_id`
- 强制 `test_intents.source_ids` 与 `coverage_matrix.source_ids` 对齐
- 在 test point plan 里补 `metadata.traceability`
- 对缺失 `source_ids` 的情况输出 warning，而不是静默丢失

验收标准：

- 多源 parse 后，每个 `test_intent` 至少可追到一个 `source_id`
- `coverage_matrix` 中 gap/covered 行均能追到 `source_id`
- `TestPointPlanV1` 中可稳定回放追溯链

### 2. 强化 `change_impact` 结构（已完成）

目标：

- 不只给 `impact_score`，还要让“为什么变高”可计算、可展示

改动点：

- [git-diff.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/git-diff.tool.py)
- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)

执行项：

- 补 `changed_areas` 的确定性规则
- 增加 `risk_signals`
- 增加 `impacted_source_ids`
- 增加 `impacted_test_intent_ids`

验收标准：

- `change_impact` 不只包含 `impact_score`
- 可稳定输出：
  - `changed_files`
  - `changed_modules`
  - `changed_areas`
  - `affected_intent_ids`
  - `risk_signals`

### 3. 补多源冲突与降级回归（已完成第一版）

目标：

- 把当前“能跑通”变成“冲突输入也不乱”

改动点：

- [test_multisource_fallback_tools.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_multisource_fallback_tools.py)
- [test_requirement_parser_multisource.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_requirement_parser_multisource.py)

执行项：

- 新增以下场景回归：
  - OpenAPI 与 Git Diff page candidate 冲突
  - defect ticket 缺 severity
  - Git diff 只有 path hint 没有 diff body
  - OpenAPI 只有路径无 summary
  - 多源全部存在但 requirement 为空

验收标准：

- 上述场景均有测试
- 冲突场景下输出 `parser_runtime.llm_trace.reason_code` 或 equivalent fallback reason

---

## P1：多源抽取深度与治理消费面（已完成第一版）

### 4. 增强 OpenAPI 抽取深度（已完成）

目标：

- 从“路径关键词推 page”升级到“端点能力 -> 测试意图 -> 参数约束”

改动点：

- [openapi-parser.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/openapi-parser.tool.py)

执行项：

- 支持 requestBody / response schema 基本解析
- 抽取枚举、必填项、分页字段、状态字段
- 区分查询类、写操作类、审批类、批量类端点
- 形成更稳定的 `parameter_constraints` 和 `design_input_fragments`

验收标准：

- OpenAPI 输入可稳定产出字段级约束
- 测试点 technique summary 能反映字段/约束数量

### 5. 增强 defect / JIRA 抽取深度（已完成）

目标：

- 让 defect 不只是“风险提示”，而是能参与 intent 和回归优先级判断

改动点：

- [jira-reader.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/jira-reader.tool.py)

执行项：

- 识别 ticket key、severity、component、labels、复现步骤关键词
- 输出更稳定的 `business_rule_hints`
- 增加 `regression_priority_boost`

验收标准：

- defect 输入能显著影响：
  - `business_rules`
  - `test_intents`
  - `change_impact`

### 6. 增强 Git Diff 抽取深度（已完成）

目标：

- 从“文件变了”提升到“变更影响了什么类型的测试”

改动点：

- [git-diff.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/git-diff.tool.py)

执行项：

- 识别：
  - API contract 变更
  - permission/auth 变更
  - selector/ui 文本变更
  - assertion/business rule 变更
- 产出 `changed_areas` 与 `design_input_fragments`

验收标准：

- 权限类 diff 能提升权限/回归类 intent
- UI/selectors 类 diff 能提升页面交互类 intent

### 7. 打通 requirement -> test points -> case 的追溯矩阵（已完成）

目标：

- 让 orchestrator 输出不再只是“生成结果”，而是“可治理结果”

改动点：

- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
- [test-point.schema.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/schemas/test-point.schema.py)

执行项：

- 为生成的 test points 附上 `intent_ids/source_ids`
- 为 case steps 附上 point 来源映射
- report 里补 `traceability_summary`

验收标准：

- 从 report 可反推：
  - 来自哪个 source
  - 覆盖了哪个 intent
  - 哪些 intent 仍有 gap

---

## P2：解释增强与平台级联动（第一版已完成）

### 8. 补 parser / fallback explainability（已完成）

目标：

- 让多源决策过程能被 UI 和治理页消费

改动点：

- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)

执行项：

- 统一输出：
  - 为什么最终选中当前 page
  - 为什么提升了某类 intent
  - 为什么提高了 change impact
  - 为什么 quality gate block / allow / manual_review

验收标准：

- `parser_runtime` / `quality_gate` 中有稳定 explanation 字段
- dashboard/workbench 可直接消费解释文本

### 9. 让多源结果进入治理视图（已完成第一版）

目标：

- 让 dashboard 和执行记录页看到“治理信号来自哪里”

改动点：

- web-ui 的 reporting / governance / task service

执行项：

- 在任务详情与治理总览中暴露：
  - source composition
  - traceability completeness
  - change impact factors

验收标准：

- 执行记录和治理页能看到多源来源摘要与追溯完整度

### 10. 补平台级 regression pack（已完成第一版）

目标：

- 把多源链路从“功能通过”升级为“回归可守”

执行项：

- 增加以下测试集：
  - tool-level unit tests
  - fallback contract tests
  - orchestrate E2E multisource tests
  - web-ui multisource governance rendering tests

验收标准：

- 多源链路的关键场景都能通过单测或集成测试稳定覆盖

---

## 建议执行顺序

### 第一阶段

1. 统一 `source_inputs/source_ids/reference_ids`
2. 强化 `change_impact`
3. 补多源冲突与降级回归

### 第二阶段

4. 增强 OpenAPI 抽取
5. 增强 Git Diff 抽取
6. 增强 defect/JIRA 抽取
7. 打通 requirement -> test points -> case 追溯矩阵

### 第三阶段

8. 补 explainability
9. 接入治理页与执行页消费面
10. 补平台级 regression pack

---

## 结论

“继续增强 orchestrator 多源闭环”这件事：

- `最小闭环`：已完成
- `治理级闭环`：未完成

当前最值得先做的，不是继续扩更多来源，而是先把已有 `OpenAPI / Git Diff / defect ticket` 的：

- 追溯一致性
- change impact 结构
- 回归护栏

补扎实。
