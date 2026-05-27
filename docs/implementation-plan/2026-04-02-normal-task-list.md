# 2026-04-02 正常任务清单

## 当前基线

- 全仓回归：`195 passed`
- `web-ui-service`：`137 passed`
- `legacy_workbench` 已进入 `compat facade + infra bridge` 稳态
- 平台治理闭环第一版已完成
- orchestrator 多源闭环第一版已完成

---

## 正常任务顺序

### T1. 拆分 `orchestrator_service.py` 的多源处理主块

目标：

- 把多源 fallback、source 归一、page 冲突裁决、change impact、traceability 相关逻辑抽离出主服务文件

执行项：

- 新增独立 support 模块
- `OrchestratorService` 保持兼容入口，内部改为委托
- 跑多源相关回归

完成状态：

- 已完成
- 新增模块：
  - [multisource_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/multisource_support.py)
- `orchestrator_service.py` 行数已从 `4270` 行下降到 `3695` 行
- 定点回归结果：`15 passed, 1 skipped`

### T2. 拆分 `orchestrator_service.py` 的 execution/report 相关主块

目标：

- 继续缩小 orchestrator 主文件，优先抽出执行记录、报告拼装、artifact 汇总

执行项：

- 新增 execution/report support 模块
- `OrchestratorService` 保持兼容方法名，内部改为委托
- 跑 execution/report 相关定点回归与全仓回归

完成状态：

- 已完成
- 新增模块：
  - [execution_report_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/execution_report_support.py)
- 已迁出逻辑：
  - `execution_record` manifest 解析与 metadata merge
  - `execution_record` metadata / payload 构建
  - report summary 预览读取
  - report payload 组装
  - report json / markdown 渲染
- `orchestrator_service.py` 行数已从 `3695` 行继续下降到 `3210` 行
- 定点回归结果：`50 passed, 1 skipped`
- 全仓回归结果：`193 passed, 1 skipped`

### T3. 推进 strict-mode 准备

目标：

- 让 `manifest-first` 的 readiness 指标与 orchestrator 执行记录生成链进一步收口

执行项：

- 补 compat builder 命中统计
- 补 strict-mode 专项回归
- 进一步减少 compat-only 路径

完成状态：

- 已完成
- `execution_record_meta` 已新增：
  - `manifest_record_path`
  - `manifest_status`
  - `resolution_reason`
- strict-mode 用例已从环境依赖 skip 改为可直接执行的明确回归
- 已新增 compat builder 命中回归，验证 fallback 场景下的 resolution meta
- OpenAPI 契约已同步扩展 `ExecutionRecordResolutionMetaV1`
- 定点回归结果：`21 passed`

### T4. 为 orchestrator 增加模块边界护栏

目标：

- 避免后续新增复杂逻辑再次回流到单个超大文件

执行项：

- 增加简单边界检查
- 在 README 中明确后续新增逻辑入口

完成状态：

- 已完成
- 新增边界检查脚本：
  - [check_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_orchestrator_service_boundary.py)
- 新增自动测试：
  - [test_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/unit/test_orchestrator_service_boundary.py)
- 当前护栏约束：
  - `orchestrator_service.py` 行数不得超过 `3300`
  - 必须保留 `MultisourceSupport` / `ExecutionReportSupport` 依赖
  - 禁止 `report_summary` 逻辑直接回流主文件
- 定点回归结果：`22 passed`

### T5. 持续同步实施文档

目标：

- 让重构进度、当前真实状态和后续顺序保持一致

完成状态：

- 已完成
- 当前文档已同步 `T1 ~ T4` 结果与最新回归状态
- 正常任务清单本轮已全部执行完成

---

## 当前建议

当前已完成：

1. `T1` 多源主块拆分
2. `T2` execution/report 主块拆分
3. `T3` strict-mode 准备
4. `T4` orchestrator 边界护栏
5. `T5` 文档同步

收口结果：

1. [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 已从 `4270` 行降到 `2865` 行
2. 全仓回归提升到 `195 passed`
3. 正常任务清单本轮已全部完成

---

## 完成后的继续推进

### R1. 拆分 telemetry / report query / failure cluster 分析块

完成状态：

- 已完成
- 新增模块：
  - [analytics_query_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/analytics_query_support.py)
- 已迁出逻辑：
  - requirement parse telemetry summary / event iteration / event recording
  - latest report / named report query
  - failure cluster list / cluster detail query
- `orchestrator_service.py` 行数已从 `3213` 行继续下降到 `2865` 行
- 定点回归结果：`64 passed`
- 全仓回归结果：`195 passed`

### R2. 拆分 failure / triage / self-healing support 块

完成状态：

- 已完成
- 新增模块：
  - [failure_healing_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/failure_healing_support.py)
- 已迁出逻辑：
  - risk report fallback evaluation
  - failure triage 与历史聚类增强
  - failure analysis fallback
  - self-healing advice 构建
  - self-healing suggestion / execution preview 读取
  - self-healing preview 请求组装
- `orchestrator_service.py` 行数已从 `2865` 行继续下降到 `2602` 行
- 定点回归结果：`61 passed`
- 全仓回归结果：`195 passed`

### R3. 拆分 requirement quality / test-point generation support 块

完成状态：

- 已完成
- 新增模块：
  - [requirement_testpoint_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/requirement_testpoint_support.py)
- 已迁出逻辑：
  - requirement quality gate 构建 / attach / blocker 生成
  - merge case requirements
  - test-point preview
  - execution-steps / requirement-spec 两条 test-point 构建链
  - constraint technique summary
  - intent-to-step 映射与安全数值工具
  - requirement spec markdown 渲染
- `orchestrator_service.py` 行数已从 `2602` 行继续下降到 `2107` 行
- 定点回归结果：`59 passed`
- 全仓回归结果：`195 passed`

### R4. 拆分 requirement parse subprocess / fallback support 块

完成状态：

- 已完成
- 新增模块：
  - [requirement_parse_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/requirement_parse_support.py)
- 已迁出逻辑：
  - requirement parser subprocess 调用
  - parser `PYTHONPATH` 环境拼装
  - parser 输出 `parser_runtime` fallback
  - orchestrator fallback requirement spec 生成
  - fallback page 推断
- `orchestrator_service.py` 行数已从 `2107` 行继续下降到 `1895` 行
- 定点回归结果：`63 passed`
- 全仓回归结果：`195 passed`

### R5. 拆分 agent execution / design support 块

完成状态：

- 已完成
- 新增模块：
  - [agent_execution_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/agent_execution_support.py)
- 已迁出逻辑：
  - script generation subprocess 调用
  - execution planner subprocess 调用
  - test-design case 生成与 fallback case 构造
  - design generation 摘要
  - test-point -> case steps 渲染
- `orchestrator_service.py` 行数已从 `1895` 行继续下降到 `1585` 行
- 定点回归结果：`64 passed`

### R6. 拆分 orchestrate 主编排桥

完成状态：

- 已完成
- 新增模块：
  - [orchestration_flow_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/orchestration_flow_support.py)
- 已迁出逻辑：
  - request 输入校验
  - source / mode 归一
  - requirement parse -> gate -> telemetry
  - case / script / execution_plan / test_points 主编排
  - execute 模式 evidence / report / runner 失败提升
  - result/report 路径最终组装
- `orchestrator_service.py` 当前稳定在 `1585` 行
- 定点回归结果：`64 passed`

### R7. 收紧 orchestrator 边界护栏

完成状态：

- 已完成
- 边界脚本已更新：
  - [check_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_orchestrator_service_boundary.py)
- 当前护栏约束已从 `3300` 行收紧到 `2000` 行
- 已要求保留以下 support 依赖：
  - `MultisourceSupport`
  - `ExecutionReportSupport`
  - `AnalyticsQuerySupport`
  - `FailureHealingSupport`
  - `RequirementTestPointSupport`
  - `RequirementParseSupport`
  - `AgentExecutionSupport`
  - `OrchestrationFlowSupport`
