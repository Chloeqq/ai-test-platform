# 2026-04-02 下一阶段剩余任务清单

## 当前基线

截至 2026-04-02，项目当前基线为：

- `web-ui-service` 主链稳定
- `legacy_workbench` 已进入 `compat facade + infra bridge` 稳态
- 平台治理入口第一版已落地
- orchestrator 多源闭环第一版已完成
- 全仓回归结果为 `202 passed`

这意味着后续任务的重点，已经从“补主链断层”和“清理超大 router”切换为：

1. 平台治理能力深化
2. 多源解释与追溯增强
3. 平台级分析能力补强
4. 架构边界固化

---

## 优先级总览

1. `P0` 优先把“治理入口”升级成“治理闭环”
2. `P1` 补齐多源第二阶段解释与追溯
3. `P1` 提升运行态严格性与回归护栏
4. `P2` 再做平台级分析与长期架构治理

---

## P0：治理闭环深化

### 1. 治理卡片跳转带筛选上下文

状态：已完成（2026-04-02）

目标：

- 让 dashboard 跳转不只是进入页面，而是带着筛选条件落到对应问题集合

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/dashboard.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/dashboard.js)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/dashboard.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/dashboard.html)
- `/executions` / `/quality/clusters` / `/quality/trends` 对应前端与接口

执行项：

- 为高风险任务卡片追加 `risk_level / traceability_gap / source_type` 查询参数
- 为 quality gate 卡片追加 `alert_code / date_range / blocked_only` 查询参数
- 为 cluster 卡片追加 `cluster_id / severity / manual_review` 查询参数
- 为 trends 卡片追加默认时间范围 `7d / 14d`

验收标准：

- 点击 dashboard 卡片后，落地页已自动带筛选结果
- 用户无需二次筛选即可直接看到目标问题集合

完成情况：

- 已由治理接口直接返回标准化 `links`，不再依赖前端硬编码跳转参数
- 已覆盖：
  - `high_risk_tasks`
  - `no_manifest_tasks`
  - `failure_clusters`
  - `manual_review_clusters`
  - `trend_summary_7d.links`
- dashboard 已改为消费接口返回的筛选链接

### 2. 统一治理指标口径

状态：已完成（2026-04-02）

目标：

- 避免 dashboard、tasks、reporting、history 之间对同一指标口径不一致

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)
- `/api/dashboard/governance`、`/api/workbench/tasks`、report 接口

执行项：

- 统一 `high_risk_task_count` 定义
- 统一 `traceability_gap_task_count` 定义
- 统一 `multisource_task_count` 定义
- 统一 `quality_gate block_rate` 时间窗口与分母口径
- 补指标说明字典

验收标准：

- dashboard 与 tasks summary 对同一指标值一致
- 文档中存在明确的指标定义与时间窗口说明

完成情况：

- `block_rate_24h`、`multisource_task_count`、`traceability_gap_task_count`、`no_manifest_task_count`、`top_alert_code` 已补入口径说明
- `metric_definitions` 已成为 dashboard 治理指标的统一字典出口
- 相关集成测试已补齐并锁定这些字段

### 3. 增加 manager 视角治理摘要

状态：已完成（2026-04-02）

目标：

- 让当前 dashboard 不只是工程视角，而是能支持周会/复盘的管理摘要

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/dashboard.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/dashboard.js)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/dashboard.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/dashboard.html)

执行项：

- 增加 `本周治理压力摘要`
- 增加 `高风险任务变化`
- 增加 `traceability 完整度趋势`
- 增加 `多源任务占比趋势`
- 增加 `建议本周优先处理主题`

验收标准：

- dashboard 中存在可直接用于周报/复盘的摘要区块
- 摘要内容可由接口直接返回，不依赖前端拼接推断

完成情况：

- `manager_summary` 已新增 `top_theme`
- dashboard 现已展示“本周主题”并将其与 headline 一起渲染
- manager 摘要已经覆盖：
  - 发布准备度
  - 追溯状态
  - 多源状态
  - 本周焦点
  - 亮点摘要列表

---

## P1：多源第二阶段增强

### 4. 强化多源冲突裁决策略

状态：已完成（2026-04-02）

目标：

- 当前已有 fallback 与 explainability，但冲突裁决仍偏轻量

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
- 多源相关测试文件

执行项：

- 引入 page candidate 打分
- 明确 source type 优先级规则
- 输出 conflict candidates 列表
- 输出 chosen vs rejected reasons
- 补典型冲突场景回归

验收标准：

- 冲突输入下 page 选择结果可解释
- `parser_runtime` 中能回放裁决原因

### 5. 强化 traceability completeness 计算

状态：已完成（2026-04-02）

目标：

- 让 traceability 不只是 point 数量统计，而是更接近真实治理信号

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py)

执行项：

- 区分 `intent coverage` 与 `source coverage`
- 区分 `covered / partial / gap / orphan`
- 增加 `orphan case steps` 检测
- 增加 `unmapped changed areas` 检测

验收标准：

- `traceability_summary` 中可区分 partial 与 orphan
- governance 可直接消费更细粒度的追溯状态

### 6. 增强 change impact explainability

状态：已完成（2026-04-02）

目标：

- 让 `impact_score` 不只用于排序，还能解释“为什么高”

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/git-diff.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/git-diff.tool.py)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)

执行项：

- 增加 factor 列表与权重
- 增加 top_factor
- 增加 `recommended_regression_scope`
- 增加 `why_blocked` / `why_manual_review`

验收标准：

- report 与 governance 中可展示 top impact factor
- impact score 可拆解回具体信号

---

## P1：运行态严格性与护栏

### 7. 推进 execution record strict-mode 准备

状态：已完成（2026-04-02，第二版治理消费已接入）

目标：

- 逐步减少 compat builder 依赖，最终让 manifest-first 成为默认稳定路径

改动点：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
- runner 相关 schema / artifact 代码
- workbench task/reporting runtime 读取链

执行项：

- 统计 compat builder 命中率
- 增加 strict-mode readiness 指标
- 给缺失 manifest 的任务打更明确标记
- 补 strict-mode 场景回归

验收标准：

- 能回答“是否可以在更严格环境里关闭 compat builder”
- dashboard / tasks 中可看到 strict-mode readiness

### 8. 补平台级 regression pack

状态：已完成（2026-04-02）

目标：

- 给治理、多源、runtime 聚合这些高价值链路更稳的回归保护

改动点：

- `apps/web-ui-service/tests/integration/`
- `apps/ai-orchestrator/tests/integration/`

执行项：

- 增加治理页 contract snapshot
- 增加 multisource governance 消费回归
- 增加 conflict resolution 回归
- 增加 execution_record metadata 回归

验收标准：

- 关键治理与多源字段变更会被测试第一时间发现

---

## P2：平台级分析能力

### 9. 深化 failure cluster / flaky / trend 分析

状态：已完成（2026-04-02，第二版增强）

目标：

- 从“能看聚类数”升级到“能指导治理优先级”

改动点：

- reporting / governance / dashboard 相关 service

执行项：

- 增加 cluster 变化趋势
- 增加 cluster 稳定性与修复收益估计
- 增加 flaky 任务与 multisource/change impact 关联分析

验收标准：

- 可回答“当前最值得处理的 cluster 是什么、为什么”

### 10. 回归包与质量门自动化联动

状态：已完成（2026-04-02）

目标：

- 让 change impact 和治理风险真正影响执行策略

改动点：

- orchestrator / execution plan / governance service

执行项：

- 为 change impact 生成推荐 regression pack
- 为高风险 change 强制更高治理门槛
- 为低风险 change 提供精简回归建议

验收标准：

- 同一变更输入下，可稳定产出推荐执行范围与门禁建议

---

## P2：架构边界固化

### 11. 冻结 `legacy_workbench` 边界

状态：已完成（2026-04-02）

目标：

- 避免后续新逻辑再次回流到 legacy

改动点：

- 代码评审约束
- 文档与简单检查脚本

执行项：

- 在文档中明确 `legacy_workbench` 只允许 compat / bridge
- 新增简单检查，避免新增大型业务函数进入 legacy
- 在 README 中明确后续开发入口

验收标准：

- 后续新增 workbench 功能默认进入 router/service/state 新结构

### 12. 补服务契约文档

状态：已完成（2026-04-02）

目标：

- 让当前已经形成的 service 分层更易维护与交接

改动点：

- `docs/implementation-plan/`

执行项：

- 为 governance / generation / reporting / runtime / review / gate / asset service 补职责说明
- 为关键 payload 补 contract 说明

验收标准：

- 新成员能快速知道功能应该改在哪一层、看哪份 contract

---

## 推荐执行顺序

1. `P0-1` 治理卡片跳转带筛选上下文
2. `P0-2` 统一治理指标口径
3. `P0-3` 增加 manager 视角治理摘要
4. `P1-4` 强化多源冲突裁决策略
5. `P1-5` 强化 traceability completeness 计算
6. `P1-7` execution record strict-mode 准备
7. `P1-8` 平台级 regression pack
8. `P2-9` 深化 failure/flaky/trend 分析
9. `P2-10` 回归包与质量门自动化联动
10. `P2-11/12` 架构边界固化与契约文档补齐

---

## 2026-04-02 完成状态更新

### `P1-4` 强化多源冲突裁决策略

已完成：

- page candidate 裁决已补齐 `source_priority_score / source_priority_rules / confidence`。
- `page_resolution_summary` 已稳定输出：
  - `chosen_candidate`
  - `conflict_candidate_details`
  - `resolution_strategy`
  - `chosen_reason / rejected_reasons`
- parser fallback 冲突场景回归已补齐，可回放 chosen vs rejected 原因。

### `P1-5` 强化 traceability completeness 计算

已完成：

- `traceability_summary` 已区分：
  - `intent_coverage_status`
  - `source_coverage_status`
  - `covered / partial / gap / orphan`
- 已新增：
  - `orphan_step_count / orphan_step_keys`
  - `partial_source_ids / uncovered_source_ids`
  - `coverage_breakdown / source_breakdown`
  - `unmapped_changed_area_count`
- governance / task summary 已可直接消费这些更细粒度信号。

### `P1-6` 增强 change impact explainability

已完成：

- `change_impact` 已稳定输出：
  - `top_factor`
  - `recommended_regression_scope`
  - `why_manual_review`
  - `why_blocked`
- preview / task / governance 消费面已展示 explainability，不再只剩 `impact_score`。

### `P1-7` 推进 execution record strict-mode 准备

已完成（第一版）：

- `strict_mode_readiness` 已补齐：
  - `can_disable_compat_builder`
  - `blocking_reasons`
  - `improvement_actions`
  - `signals`
- task summary 已新增：
  - `strict_mode_status_counts`
  - `strict_mode_ready_task_count`
  - `strict_mode_caution_task_count`
  - `strict_mode_blocked_task_count`
  - `strict_mode_can_disable_compat_builder`
- governance 总览与 manager summary 已开始直接消费 strict-mode readiness。
- `/api/workbench/tasks` 已支持 `strict_mode_status` 过滤。

### `P1-8` 补平台级 regression pack

已完成（第一版）：

- 已补 governance / tasks / strict-mode 定点回归。
- 已补多源冲突裁决与 explainability 回归。
- 已补 execution_record metadata 与 strict-mode 消费回归。
- 关键治理和多源字段变更已能被测试第一时间捕获。

### `P2-9` 深化 failure cluster / flaky / trend 分析

已完成：

- `GET /api/dashboard/governance` 已新增：
  - `failure_clusters.analysis`
  - `flaky_analysis`
- 已可回答“当前最值得优先处理的 cluster 是什么、为什么”
- 已可展示 flaky 与 multisource/change impact 的重合关系

### `P2-10` 回归包与质量门自动化联动

已完成：

- execution/task summary 已稳定输出：
  - `recommended_regression_scope_counts`
  - `gate_recommendation_counts`
  - `recommended_regression_pack`
- governance 总览已稳定输出：
  - `execution_strategy.recommended_pack`
  - `execution_strategy.gate_recommendation`
  - `execution_strategy.recommended_scopes`

### `P2-11` 冻结 `legacy_workbench` 边界

已完成：

- 新增边界检查脚本：
  - [check_legacy_workbench_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_legacy_workbench_boundary.py)
- 已新增自动测试，防止 route decorator 或大块业务逻辑回流到 legacy
- 文档已明确：`legacy_workbench` 只允许 `compat facade + infra bridge`

### `P2-12` 补服务契约文档

已完成：

- 新增 service 契约文档：
  - [2026-04-02-service-contract-map.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-service-contract-map.md)
- 已明确 governance / generation / reporting / runtime / review / gate / asset 的职责与关键 payload

## 当前结论

截至 2026-04-02，本清单中的 `P0 ~ P2` 项目已完成第一版收口。后续工作应以迭代增强为主，而不是继续补基础断层。

## 2026-04-02 补充完成状态更新（剩余能力收口）

### `CoverageMatrix / traceability completeness` 更产品化

已完成：

- 新增资产级 CoverageMatrix 产物与接口：
  - `GET /api/workbench/test-point-assets/{asset_id}/coverage-matrix`
- `coverage_matrix` 现在可稳定输出：
  - `row_id`
  - `traceability_status`
  - `source_ids / intent_ids / point_keys`
  - `missing_point_keys`
  - `changed_areas`
  - `summary.covered_count / partial_count / gap_count / orphan_count`
- 已支持优先消费 `plan.metadata.coverage_matrix`，缺失时回退由 test point traceability 推导。

### `failure cluster / flaky / risk scoring` 第二版

已完成：

- governance 总览新增第二版可解释评分：
  - `top_governance_risks[*].risk_score_breakdown`
  - `risk.score_breakdown`
  - `summary.strict_manifest_policy`
- failure cluster 分析新增：
  - `trend_pressure`
  - `risk_overlap_count`
  - `flaky_overlap_count`
- flaky 分析新增：
  - `risk_overlap_ratio`
  - `stability_score`

### `strict manifest-first` 继续收紧

已完成：

- strict-mode readiness 已不再只是单点指标，现已进入：
  - task summary
  - governance summary
  - manager summary
  - scheduler recommendations
- 新增 `strict_manifest_policy`，可直接回答：
  - 当前模式
  - blocked / caution / ready 数量
  - 是否可关闭 compat builder
  - 下一步建议动作

### 统一调度中心

已完成（第一版）：

- 新增调度聚合 service：
  - [workbench_scheduler_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_scheduler_service.py)
- 新增接口：
  - `GET /api/workbench/scheduler/summary`
  - `GET /api/workbench/scheduler/dispatch-plan`
- 当前已可稳定输出：
  - queue pressure
  - environment pool distribution
  - resource profile distribution
  - runner distribution
  - dispatch lanes / recommended concurrency

### API / Mobile runner

已完成（第一版）：

- orchestrator 新增 runner catalog：
  - `GET /runners/catalog`
- `POST /orchestrate` 已支持 `runner=playwright/api/mobile`
- 已支持 generate-only 的 runner-aware orchestration：
  - `playwright -> framework=playwright`
  - `api -> framework=requests`
  - `mobile -> framework=appium`
- `api/mobile` 当前会阻止 `execute=true`，避免假执行路径进入错误成功态。
- execution record / report request context 已写入 runner profile。
- YAML 契约已放宽为允许：
  - `playwright`
  - `api`
  - `mobile`

当前验证结果：

- 全仓：`202 passed`
