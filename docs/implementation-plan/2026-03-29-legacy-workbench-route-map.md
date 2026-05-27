# 2026-03-29 legacy_workbench 路由拆层映射表

## 1. 目的

这份清单用于回答三个问题：

1. `legacy_workbench.py` 当前到底暴露了哪些接口
2. 每个接口更适合归属到哪个 service / router
3. 下一轮拆层应该按什么顺序做，才能在不改 URL 的前提下降低风险

适用文件：

- [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py)

## 2. 当前路由总表

当前实际路由共 `35` 个：

### 2.1 项目与任务视图

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `GET` | `/api/workbench/projects` | `list_projects` | `workbench_state_store` + 新 `workbench_project_router` | P2 |
| `GET` | `/api/workbench/tasks` | `list_execution_tasks` | `workbench_runtime_service` + 新 `workbench_task_router` | P1 |
| `GET` | `/api/workbench/tasks/{task_id}` | `get_execution_task` | `workbench_runtime_service` + 新 `workbench_task_router` | P1 |
| `GET` | `/api/workbench/execution-gate/config` | `get_execution_gate_config` | `workbench_gate_service` + 新 `workbench_gate_router` | P1 |

### 2.2 用例与测试点资产

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `GET` | `/api/workbench/cases` | `list_cases` | `workbench_asset_service` + 新 `workbench_case_router` | P1 |
| `GET` | `/api/workbench/cases/{case_id}` | `get_case` | `workbench_asset_service` + 新 `workbench_case_router` | P1 |
| `PUT` | `/api/workbench/cases/{case_id}` | `save_case` | `workbench_asset_service` + 新 `workbench_case_router` | P0 |
| `GET` | `/api/workbench/test-point-assets` | `list_test_point_assets` | `workbench_asset_service` | P0 |
| `GET` | `/api/workbench/test-point-assets/coverage-summary` | `get_test_point_asset_coverage_summary` | `workbench_asset_service` | P1 |
| `GET` | `/api/workbench/test-point-assets/{asset_id}` | `get_test_point_asset` | `workbench_asset_service` | P0 |

### 2.3 生成与预览

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `POST` | `/api/workbench/generate` | `generate_case` | 新 `workbench_generate_router` + `workbench_asset_service` + `workbench_analysis_service` | P0 |
| `POST` | `/api/workbench/preview-test-points` | `preview_test_points` | 新 `workbench_generate_router` + `workbench_analysis_service` | P0 |
| `POST` | `/api/workbench/auto-run` | `auto_run` | 新 `workbench_generate_router` + `workbench_runtime_service` | P1 |

### 2.4 Review 与门禁

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `POST` | `/api/workbench/reviews` | `save_review` | `workbench_review_service` + 新 `workbench_review_router` | P0 |
| `POST` | `/api/workbench/execution-gate/decisions` | `save_execution_gate_decision` | `workbench_gate_service` + 新 `workbench_gate_router` | P0 |
| `POST` | `/api/workbench/execution-gate/decisions/approve` | `approve_execution_gate_decision` | `workbench_gate_service` + 新 `workbench_gate_router` | P0 |
| `POST` | `/api/workbench/execution-gate/decisions/revoke` | `revoke_execution_gate_decision` | `workbench_gate_service` + 新 `workbench_gate_router` | P0 |

### 2.5 Run 与自愈

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `POST` | `/api/workbench/run` | `run_case` | `workbench_runtime_service` + 新 `workbench_run_router` | P0 |
| `GET` | `/api/workbench/runs` | `list_runs` | `workbench_runtime_service` + 新 `workbench_run_router` | P0 |
| `GET` | `/api/workbench/runs/{run_id}` | `get_run` | `workbench_runtime_service` + 新 `workbench_run_router` | P0 |
| `GET` | `/api/workbench/runs/{run_id}/events` | `stream_run_events` | `workbench_runtime_service` + 新 `workbench_run_router` | P1 |
| `GET` | `/api/workbench/runs/{run_id}/analysis` | `get_run_analysis` | `workbench_runtime_service` + `workbench_analysis_service` | P1 |
| `POST` | `/api/workbench/runs/{run_id}/heal` | `heal_run` | `workbench_runtime_service` | P1 |
| `POST` | `/api/workbench/runs/{run_id}/rerun` | `rerun_case` | `workbench_runtime_service` | P0 |
| `POST` | `/api/workbench/runs/{run_id}/heal-and-rerun` | `heal_and_rerun_case` | `workbench_runtime_service` | P1 |

### 2.6 缺陷关联

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `GET` | `/api/defects` | `list_defects` | 新 `workbench_defect_router` + `workbench_state_store` | P2 |
| `POST` | `/api/defects` | `add_defect` | 新 `workbench_defect_router` + `workbench_state_store` | P2 |

### 2.7 报告与历史

| Method | Path | Function | 推荐归属 | 优先级 |
|---|---|---|---|---|
| `GET` | `/api/report/overview` | `report_overview` | 新 `workbench_report_router` + `workbench_history_service` | P1 |
| `GET` | `/api/report/failures` | `report_failures` | 新 `workbench_report_router` + `workbench_history_service` | P1 |
| `GET` | `/api/report/context` | `report_context` | 新 `workbench_report_router` | P2 |
| `GET` | `/api/report/performance` | `report_performance` | 新 `workbench_report_router` + `workbench_history_service` | P2 |
| `GET` | `/api/report/allure` | `report_allure` | 新 `workbench_report_router` | P2 |
| `POST` | `/api/report/allure/refresh` | `report_allure_refresh` | 新 `workbench_report_router` | P2 |
| `GET` | `/api/workbench/history` | `workbench_history` | `workbench_history_service` + 新 `workbench_history_router` | P1 |
| `GET` | `/api/workbench/quality-gates/summary` | `workbench_quality_gate_summary` | `workbench_history_service` + `workbench_gate_service` | P1 |
| `GET` | `/api/workbench/download-log/{run_id}` | `download_log` | `workbench_runtime_service` | P2 |

## 3. 当前状态判断

## 3.1 已经有 service 但 router 仍过重

这几类能力在代码里已经抽出了 service，但 `legacy_workbench.py` 仍在做过多组装工作：

- Review
- Execution gate
- Runtime run
- Test point asset
- History
- Analysis

这说明当前最合理的动作不是“重写逻辑”，而是“继续把 router 壳削薄”。

## 3.2 最值得先拆的 4 组接口

建议优先拆下面四组，因为收益最大、风险最低：

### 第一组：Review / Gate

- `/api/workbench/reviews`
- `/api/workbench/execution-gate/decisions*`

原因：

- service 已存在
- 输入输出边界清晰
- 与运行态和报告态耦合相对较小

### 第二组：Run

- `/api/workbench/run`
- `/api/workbench/runs*`

原因：

- 当前是用户主链路的一部分
- runtime service 已具备核心能力
- 迁完后能显著减少 router 中的流程控制代码

### 第三组：Generate / Preview

- `/api/workbench/generate`
- `/api/workbench/preview-test-points`
- `/api/workbench/auto-run`

原因：

- 这是主工作台的核心入口
- 目前与 analysis / asset / runtime 多处耦合
- 拆完后最能提升可维护性

### 第四组：Test Point Assets

- `/api/workbench/test-point-assets*`

原因：

- 当前平台治理最重要的数据面之一
- 已经有较强的 state/summary 逻辑
- 非常适合独立成 router + service 查询面

## 4. 推荐 router 目标结构

建议最终收敛为以下结构：

- `app/routers/workbench_generate.py`
- `app/routers/workbench_runs.py`
- `app/routers/workbench_reviews.py`
- `app/routers/workbench_gate.py`
- `app/routers/workbench_assets.py`
- `app/routers/workbench_reports.py`
- `app/routers/workbench_history.py`
- `app/routers/workbench_defects.py`
- `app/routers/legacy_workbench.py`

其中：

- 新 router 承担真实实现
- `legacy_workbench.py` 只保留兼容导出和少量过渡封装

## 5. 第一轮拆层建议

建议第一轮只做低风险搬迁，不改 URL，不改返回结构：

### Step 1

- 新建 `workbench_reviews.py`
- 迁移 `save_review`
- 迁移 review 相关请求校验与响应组装

### Step 2

- 新建 `workbench_gate.py`
- 迁移三个 execution gate 接口
- 保持 service 调用不变

### Step 3

- 新建 `workbench_runs.py`
- 迁移 `run_case / list_runs / get_run / rerun_case`
- 暂时保留 `heal* / events / analysis`

### Step 4

- 新建 `workbench_assets.py`
- 迁移 case 与 test-point-assets 查询读接口

## 6. 验收标准

每完成一轮拆层，需要满足：

- 全量 `pytest` 通过
- URL 与响应结构不变化
- `legacy_workbench.py` 行数明显下降
- 新 router 文件具备最少集成测试覆盖
- 新增逻辑只进入新 router，不再进入 `legacy_workbench.py`

## 7. 当前建议的直接下一步

最适合作为下一次代码改造的切入点：

1. 先拆 `save_review`
2. 再拆 `execution-gate` 三个接口
3. 最后拆 `run_case/list_runs/get_run/rerun_case`

这样可以在最短路径内，把最核心的治理和运行入口从超大文件中剥离出来。
