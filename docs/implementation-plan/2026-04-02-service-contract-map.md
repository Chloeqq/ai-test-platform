# 2026-04-02 Service Contract 与分层说明

## 目标

为当前已经形成的 `router -> service -> state/infra -> compat facade` 结构补齐职责说明，降低后续维护和交接成本。

---

## 分层原则

1. `router`
- 只负责 HTTP 入参、鉴权、响应格式和页面模板接线。
- 不承载复杂业务编排。

2. `service`
- 负责业务聚合、规则判断、治理摘要、contract 组装。
- 是新增平台能力的默认落点。

3. `state / runtime / infra`
- 负责文件读写、artifact 解析、runtime 补充、兼容数据桥接。

4. `legacy_workbench`
- 只允许保留 `compat facade + infra bridge`。
- 不再新增大型业务函数或新的 route decorator。

---

## 核心 Service 职责

### `workbench_governance_service`

职责：
- 聚合 `quality gate / task governance risk / failure clusters / flaky / trend`
- 输出 dashboard 管理视角、治理趋势、执行策略

关键 payload：
- `risk`
- `summary`
- `failure_clusters.analysis`
- `flaky_analysis`
- `execution_strategy`
- `manager_summary`

### `workbench_task_service`

职责：
- execution task 列表、过滤、summary、governance risk 评分
- multisource/task 视角消费 `traceability` 与 `change_impact`

关键 payload：
- `multisource_summary`
- `governance_risk_top_items`
- `recommended_regression_scope_counts`
- `gate_recommendation_counts`
- `recommended_regression_pack`

### `workbench_reporting_service`

职责：
- report overview / failures / context / performance / allure
- failure entries 聚合
- execution meta 与 strict-mode readiness 规范化

关键 payload：
- `strict_mode_readiness`
- `failure source calibration`
- `run governance snapshot`

### `workbench_generation_service`

职责：
- preview / generate / auto-run 业务编排
- 多源 requirement 归一
- requirement markdown / execution plan / auto-run item 组装

关键 payload：
- `requirement_spec`
- `change_impact`
- `recommended_regression_scope`
- `traceability_summary`

### `workbench_analysis_service`

职责：
- page URL 解析
- page surface / semantic / page object 增强
- requirement steps 生成
- risk 评估编排辅助

关键 payload：
- `PageSurfaceV1`
- `PageSemanticModelV1`
- `PageObjectDraftV1`

### `workbench_asset_service`

职责：
- case / test-point asset 读写
- governance summary / coverage summary / traceability summary

关键 payload：
- `TestPointPlanV1`
- `selection_summary`
- `gate_context`
- `traceability_summary`

### `workbench_review_service`

职责：
- review decision 聚合
- run review state / item review state
- audit timeline 与 review sanitation

### `workbench_gate_service`

职责：
- execution gate 纯计算与 policy baseline
- gate decision 审计快照
- gate 相关基础 helper

### `workbench_runtime_service`

职责：
- run command 构建
- runtime execution record / manifest artifact 解析
- runtime view 兼容桥接

### `workbench_orchestrator_service`

职责：
- 通用 JSON POST 封装
- orchestrator HTTP 交互错误映射

---

## 关键 Contract 入口

1. Orchestrator 多源 contract
- `source_inputs`
- `source_id`
- `reference_ids`
- `change_impact`
- `traceability_summary`

2. 执行记录 contract
- `ExecutionRecordV1`
- `metadata.multisource`
- `metadata.strict_mode_readiness`

3. 治理 contract
- `risk`
- `manager_summary`
- `execution_strategy`
- `failure_clusters.analysis`

4. 资产 contract
- `TestPointPlanV1`
- `PageSurfaceV1`
- `PageObjectDraftV1`

---

## 后续开发入口约束

1. 新增 workbench 页面或接口：优先进入对应 `router + service`
2. 新增治理聚合：优先进入 `workbench_governance_service`
3. 新增 runtime/artifact 解析：优先进入 `workbench_runtime_service`
4. 新增 traceability/change impact 消费：优先进入 `workbench_task_service / workbench_governance_service`
5. 非兼容需求，不再新增到 `legacy_workbench.py`
