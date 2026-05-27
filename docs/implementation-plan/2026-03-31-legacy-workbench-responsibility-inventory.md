# legacy_workbench 当前剩余职责盘点

日期：2026-03-31

## 背景

经过前几轮拆层与 service 下沉后，[legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 已经从最初的超大路由文件，收缩成“兼容层 + 状态桥 + 少量未下沉 helper”的混合体。

当前文件规模仍然较大，但已经继续明显收缩：

- 文件行数：`2186`

但需要区分两件事：

1. 文件还大，不等于仍然承担同样多的业务职责
2. 后续不应该再以“尽量清空 legacy”为目标，而应该以“继续收真正值得收的职责”为目标

本文档用于回答两个问题：

1. `legacy_workbench.py` 现在还剩哪些职责
2. 哪些值得继续收，哪些更适合作为兼容层保留

## 当前剩余职责总览

当前职责大致分为 6 类。

### 1. legacy 直接挂载路由现状

本轮收口后，`projects / tasks / execution-gate/config` 也已经迁出 `legacy`。

判断：

- `legacy_workbench.py` 现在的主角色已经不再是 route 容器
- 后续重点不应再放在“搬路由”，而应放在“继续收真实实现”

### 2. public compat 壳

目前保留的 public 兼容入口主要有：

- `save_case(...)`
- `save_review(...)`
- `save_execution_gate_decision(...)`
- `approve_execution_gate_decision(...)`
- `revoke_execution_gate_decision(...)`
- `report_allure_refresh(...)`
- `heal_run(...)`
- `rerun_case(...)`
- `heal_and_rerun_case(...)`

其中前 6 个已经基本是薄壳；后 3 个也是一层转发到 [workbench_runs.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/workbench_runs.py)。

判断：

- 这些入口不再值得以“删除”为目标继续推动
- 它们更适合作为兼容层稳定保留，直到测试和内部调用面明确不再依赖

### 3. 状态存储与文件桥接 helper

这一层主要是：

- `_sync_stage_a_workbench_state`
- `_ensure_dirs`
- `_read_json_list`
- `_write_json_list`
- `_append_history`
- `_append_runtime_run`
- `_update_runtime_run`
- `_update_job`
- `_get_job`
- `_find_run_item`
- `_wait_run_terminal`

判断：

- 这是 legacy 当前最像“基础设施桥”的部分
- 它们被多个 router/service 复用，且 monkeypatch 成本低、兼容价值高
- 继续拆是可以的，但不应优先

### 4. 已显著瘦身但仍留在 legacy 的主题 helper

这类 helper 已经有一部分实现收口到 service，但 legacy 还保留同名入口：

- review
- execution gate
- runtime view
- reporting/allure
- assets
- failure-analysis 归一视图

判断：

- 这部分现在更像“compat facade”
- 后续只值得继续收那些仍有明显重复实现的点
- 不值得为了形式统一，把所有同名 helper 都再做一次机械搬运

### 5. 仍偏厚的编排/分析 helper

当前最值得关注的“还在 legacy 里承担真实业务逻辑”的区域，主要集中在：

- orchestrator / quality gate 编排
  - `_run_orchestrator_generate`
  - `_run_orchestrator_parse`
  - `_run_orchestrator_risk`
- page analysis / surface / page object 增强
  - 少量 glue 仍在 legacy，但核心实现已大幅迁出
- test-point / risk / review 计算
  - `_build_test_point_asset_traceability_summary`
  - `_build_test_point_asset_selection_summary`
  - `_build_item_review_state`
  - `_build_run_review_state_from_decisions`
- runtime / failure / task 聚合视图
  - `_collect_failure_entries_with_meta`
  - `_collect_failure_entries_with_meta`

判断：

- 这些是真正还“值钱”的剩余职责
- 如果还要继续收 legacy，优先级应集中在这一类

### 6. 通用小工具

例如：

- `_normalize_failure_source_value`
- `_parse_iso_datetime`
- `_utc_now`
- `_is_within`
- `_collect_failure_entries_with_meta`

判断：

- 这些工具函数不一定需要全部抽走
- 只在出现明显重复实现或多模块复用阻力时再收

## 已经不建议继续投入的方向

下面这些方向，继续投入的收益已经不高。

### A. 继续删除 public compat 壳

原因：

- 当前 `heal_run` / `rerun_case` / `heal_and_rerun_case` 已经只是薄转发
- `save_case` / `save_review` / `report_allure_refresh` 等也已趋近 compat facade
- 继续删掉它们，收益很小，但会提升测试和兼容风险

建议：

- 保留为兼容层
- 后续仅在确认无测试/内部调用依赖时，再统一处理

### B. 继续机械式搬运零散小工具

原因：

- 对文件体积帮助有限
- 会增加 helper 分散度
- 可能让调试路径更长

建议：

- 仅处理“重复实现明显”或“跨 service 复用阻力大”的工具函数

## 2026-04-01 阶段性进展

本轮已经完成了盘点文档里原先排在前面的多项收口工作。

### 已完成收口

- `tasks/runtime view`
  - route 已迁出到 [workbench_tasks.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/workbench_tasks.py)
  - 核心视图与汇总逻辑已迁到 [workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py)
- `run governance snapshot`
  - 已迁到 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)
- `page analysis / surface extraction`
  - `_extract_page_surface`
  - `_collect_frame_surface`
  - `_wait_for_surface_stable`
  - `_enhance_page_object_from_surface`
  - `_build_requirement_steps`
  - 已迁到 [workbench_analysis_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_analysis_service.py)
- `orchestrator / risk / gate`
  - `_extract_quality_gate`
  - `_is_quality_gate_blocked`
  - `_build_requirement_spec_for_risk`
  - `_build_execution_plan_for_risk`
  - `_build_execution_gate`
  - `_evaluate_risk_report`
  - 已分别迁到 generation / gate / analysis service
- `failure/runtime records`
  - `_collect_failure_entries_with_meta`
  - `_collect_failure_entries`
  - `_normalize_failure_evidence_meta`
  - `_normalize_execution_meta`
  - 已继续迁到 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)
- `review / run review state`
  - `_build_run_review_state_from_decisions`
  - `_build_item_review_state`
  - 已迁到 [workbench_review_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_review_service.py)
- 通用工具层
  - `_post_json` 已迁到 [workbench_orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_orchestrator_service.py)
  - `_build_run_command`、`_extract_json_from_text`、`_get_python_bin` 已迁到 [workbench_runtime_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_runtime_service.py)
  - `_apply_no_store_headers` 已迁到 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)
  - `_safe_case_id`、`_normalize_page_slug`、`_normalize_history_text_list` 已通过 [workbench_gate_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_gate_service.py) 收口
  - `_now_iso` 已通过 [workbench_state_store.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_state_store.py) 收口
  - `_parse_optional_bool_query`、`_execution_record_time_value` 已迁到 [workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py)

### 当前更准确的判断

- `legacy_workbench.py` 仍然重要，但它现在更明确是：
  - 兼容层
  - 状态桥
  - 少量剩余 glue/helper 聚合点
- 下一阶段不应再以“清空 legacy”为目标
- 更合适的目标是：
  - 继续减少新 router 对 legacy helper 的依赖
  - 只收那些仍有明显重复实现或真实业务重量的点

## 值得继续收的方向

按收益和风险平衡，建议把剩余工作聚焦在 4 个方向。

### 1. `test-point asset governance` 主题

原因：

- `selection / gate context / summary / coverage / traceability` 这一整组主摘要已经完成 service 化
- 当前还可能继续推进的，只剩少量 attach/compat glue
- 这意味着 assets/gate/reporting 之间的治理边界已经明显清晰

建议优先级：`中`

### 2. `failure/runtime records` 剩余聚合主题

包括：

- 少量剩余 runtime/failure 聚合 glue
- 仍保留在 compat 层的状态桥与 realtime/runtime job 协调逻辑

原因：

- 主聚合链、manifest 解析、execution_record 读取与 artifacts 回放已经迁出
- 剩余部分更多是 `_RUN_JOBS/_RUN_LOCK` 驱动的 infra 桥接，不再适合高频拆分

建议优先级：`中`

### 3. `review / run review state` 主题

包括：

- review 与 gate 之间的少量剩余桥接 glue
- 审计/确认点相关的 compat 调用面

原因：

- 主 review state 组装逻辑、review decisions 查询、failure source calibration 已经迁出
- 剩余部分已更接近稳态 compat facade

建议优先级：`中`

## 2026-04-02 阶段性进展

本轮重点完成了 `test-point asset governance` 主摘要链的整体收口。

### 已完成收口

- `test-point asset governance`
  - `_build_test_point_asset_selection_summary`
  - `_build_test_point_asset_gate_context`
  - `_build_test_point_asset_summary`
  - `_build_test_point_asset_coverage_summary`
  - `_build_test_point_asset_traceability_summary`
  - 已迁到 [workbench_asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py)
- `test-point asset` 基础计算
  - `_count_test_point_types`
  - `_build_test_point_asset_semantic_summary`
  - `_build_test_point_asset_technique_summary`
  - `_merge_reference_items`
  - `_latest_run_snapshot_for_case`
  - 已迁到 [workbench_asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py)
- `failure/runtime records`
  - `_resolve_manifest_entries`
  - `_load_execution_record_payload`
  - `_load_runtime_execution_record_from_artifacts`
  - 已迁到 [workbench_runtime_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_runtime_service.py)
- `failure source calibration`
  - `_normalize_failure_source_value`
  - `_sanitize_failure_source_feedback`
  - `_record_failure_source_calibration_sample`
  - 已迁到 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)
- `review / run review bridge`
  - `_review_decisions_for_run`
  - 已迁到 [workbench_review_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_review_service.py)
- `analysis` 小型 glue
  - `_extract_page_from_url`
  - `_load_latest_self_healing_result`
  - 已迁到 [workbench_analysis_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_analysis_service.py)

### 当前更准确的判断

- `test-point asset governance` 这一条主治理链已经不再由 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 自己维护真实实现
- `legacy_workbench.py` 在 assets 主题上，当前更像：
  - compat wrapper
  - attach glue
  - 状态桥接层
- `failure/runtime records` 与 `review` 的高价值桥接也已继续迁出
- 当前剩余部分更集中在：
  - compat public 壳
  - `_RUN_JOBS/_RUN_LOCK` 相关 runtime infra 桥
  - 状态文件桥接 helper
- 下一阶段不需要再把 assets 或 review/failure 当作高优先级重区
- 更合适的方向是回到：
  - infra 层稳定化
  - `orchestrator wrappers` 稳态保留
  - 文档与治理视图完善

## 下一步建议（2026-04-02 更新）

1. 将 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 明确视为 `compat + infra bridge`，不再追求机械清空。
2. 后续如继续重构，优先以新 service 直接消费状态层为目标，而不是继续分拆零散 helper。
3. 进入稳态阶段后，重点转向治理能力完善与文档收敛。

### 4. `orchestrator wrappers` 主题

包括：

- `_run_orchestrator_generate`
- `_run_orchestrator_parse`
- `_run_orchestrator_risk`

原因：

- 它们仍然是重要 monkeypatch 锚点
- 不适合贸然删除，但后续可以评估是否引入更明确的 orchestrator client facade
- 这组不是“删除优先项”，而是“稳定后再规划”

建议优先级：`中`

## 建议保留为兼容层的部分

下面这些我建议明确标记为“当前阶段保留”。

### public compat 入口

- `save_case`
- `save_review`
- `save_execution_gate_decision`
- `approve_execution_gate_decision`
- `revoke_execution_gate_decision`
- `report_allure_refresh`
- `heal_run`
- `rerun_case`
- `heal_and_rerun_case`

保留理由：

- 当前已经很薄
- 兼容价值高于继续删除的收益

### state/file bridge

- `_read_json_list`
- `_write_json_list`
- `_append_history`
- `_append_runtime_run`
- `_update_runtime_run`
- `_update_job`
- `_get_job`
- `_find_run_item`
- `_wait_run_terminal`

保留理由：

- 这是 legacy 当前作为“状态桥”的核心
- 多处依赖，短期内保持稳定更重要

### 少量通用工具

- `_apply_no_store_headers`
- `_get_python_bin`
- `_parse_optional_bool_query`
- `_parse_iso_datetime`
- `_utc_now`
- `_is_within`

保留理由：

- 拆分收益不高
- 目前不会显著阻碍主链重构

## 当前建议的后续顺序

如果继续推进 legacy 收口，建议改成下面这个顺序：

1. 先收 `tasks/runtime view`
2. 再收 `run governance snapshot`
3. 之后评估 `page analysis / surface extraction`
4. 最后再碰 `orchestrator / risk / gate` 主编排区

不建议再把“删除 compat 壳”作为主要目标。

## 当前结论

可以把当前 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 的定位明确成一句话：

“它已经不再是主 router，而是一个仍在收缩中的兼容层、状态桥和少量编排 helper 聚合点。”

下一阶段最重要的，不是继续追求“文件更小”，而是：

- 让真正厚的 runtime/task/governance/helper 继续下沉
- 让已经足够薄的 compat 壳稳定保留
- 避免为了形式统一引入额外重构风险
