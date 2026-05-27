# AI测试平台实施计划

## 项目概述

本项目旨在将现有的AI测试平台从原型阶段推向生产就绪状态，重点完善用例管理层、执行调度器和整体架构。

## 实施计划总览

### 阶段概览

| 阶段 | 名称 | 优先级 | 预计工期 | 状态 |
|------|------|--------|----------|------|
| P0 | 核心架构完善 | 🔴 高 | 1-2周 | 进行中 |
| P1 | 用例编辑器独立化 | 🟠 中 | 2-3周 | 待开始 |
| P2 | 高级功能 | 🟡 低 | 3-4周 | 待开始 |

### 详细任务分解

#### P0 阶段：核心架构完善（第1-2周）

**任务1: 用例数据模型扩展**
- 扩展TestCase数据模型，支持不同类型测试用例
- 添加test_type、pytest_path、markers等字段
- 创建数据库迁移脚本

**任务2: 执行调度器实现** 
- 创建统一执行调度器
- 按用例类型分发执行
- 实现API和UI执行器

#### P1 阶段：用例编辑器独立化（第3-5周）

**任务3: 独立用例编辑器前端组件**
- 创建可视化用例编辑器
- 支持基本信息、测试步骤、数据驱动配置

**任务4: 数据驱动配置UI**
- 实现数据驱动测试配置界面
- 支持参数化测试数据管理

#### P2 阶段：高级功能（第6-9周）

**任务5: 用例健康度分析**
- 实现用例健康度评分系统
- 包含稳定性、维护成本、执行时间等维度

**任务6: pytest深度集成**
- 实现pytest与平台的深度集成
- 自动同步执行结果到平台

## 当前状态

- **项目启动日期**: 2026年3月27日
- **当前阶段**: P0 - 核心架构完善
- **当前任务**: 任务1 - 用例数据模型扩展
- **预计完成**: 2026年4月10日

## 执行日志

### 2026-03-29（平台核查与主链路稳定性修复）

- 已完成：定位并修复 `pytest` 全量失败的主因，包含测试导入冲突、orchestrator 端点测试端口依赖、requirement parser 子进程环境缺失、资产契约不一致。
- 已完成：恢复全量测试通过，当前结果为 `182 passed, 1 skipped`。
- 已完成：补充平台核查与治理推进方案文档 [2026-03-29-platform-verification-and-governance-plan.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-03-29-platform-verification-and-governance-plan.md)。
- 已完成：补充 `legacy_workbench.py` 路由拆层映射文档 [2026-03-29-legacy-workbench-route-map.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-03-29-legacy-workbench-route-map.md)。
- 已确认：当前主风险已从“主链路不可运行”转向“router 过重、schema/tool 治理不闭环、平台级分析深度不足”。

### 2026-03-31（legacy_workbench 剩余职责盘点）

- 已完成：对 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 当前剩余职责做结构化盘点。
- 已完成：新增盘点文档 [2026-03-31-legacy-workbench-responsibility-inventory.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-03-31-legacy-workbench-responsibility-inventory.md)。
- 已明确：后续不再以“尽量删除 compat 壳”为主要目标，而是优先收 `tasks/runtime view`、`run governance snapshot` 等仍然偏厚的真实逻辑。
- 已明确：`save_case/save_review/heal_run/rerun_case/heal_and_rerun_case` 等公共兼容入口当前更适合作为稳定兼容层保留。

### 2026-04-01（legacy_workbench 第二阶段持续收口）

- 已完成：`legacy_workbench.py` 文件规模继续从盘点时的 `4490` 行收缩到当前 `2731` 行。
- 已完成：`tasks/runtime view` 相关 route 与主视图逻辑迁出，新增 [workbench_tasks.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/workbench_tasks.py) 与 [workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py)。
- 已完成：`run governance snapshot`、failure analysis 归一、reporting/allure helper 继续下沉到 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)。
- 已完成：`page analysis / surface extraction` 主链大幅迁到 [workbench_analysis_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_analysis_service.py)，包括 `page surface`、`page object` 增强、`requirement steps` 生成等。
- 已完成：`orchestrator / risk / gate` 相关核心 helper 继续下沉，`quality gate` 提取、`requirement spec for risk`、`execution plan for risk`、`execution gate`、`risk report` 编排已分别收口到 generation / gate / analysis service。
- 已完成：通用 orchestrator HTTP 客户端从 legacy 中抽出，新增 [workbench_orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_orchestrator_service.py)。
- 已完成：runtime 工具链继续收口，`build_run_command`、`extract_json_from_text`、`get_python_bin` 已迁到 [workbench_runtime_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_runtime_service.py)。
- 已完成：多个基础重复 helper 已统一委托，包括 `safe_case_id`、`normalize_page_slug`、`normalize_history_text_list`、`now_iso`、`parse_optional_bool_query`。
- 已完成：`failure/runtime records` 主聚合链继续迁出，`collect_failure_entries_with_meta`、`collect_failure_entries`、`normalize_failure_evidence_meta`、`normalize_execution_meta` 已进入 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)。
- 已完成：`review / run review state` 主组装链继续迁出，`build_run_review_state_from_decisions` 与 `build_item_review_state` 已进入 [workbench_review_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_review_service.py)。
- 已完成：`workbench_tasks.py` 已进一步减少对 legacy 基础 helper 的依赖，开始直接消费 task/reporting service 中的通用函数。
- 已验证：当前全量测试保持稳定，结果为 `182 passed, 1 skipped`。

### 2026-04-02（test-point asset governance 主摘要链收口）

- 已完成：`legacy_workbench.py` 文件规模继续从上一阶段的 `2731` 行收缩到当前 `2509` 行。
- 已完成：`test-point asset governance` 主摘要链整体迁出，以下 helper 已进入 [workbench_asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py)：
  - `_build_test_point_asset_selection_summary`
  - `_build_test_point_asset_gate_context`
  - `_build_test_point_asset_summary`
  - `_build_test_point_asset_coverage_summary`
  - `_build_test_point_asset_traceability_summary`
- 已明确：assets 主题当前已从“高优先级主收口区”转入“稳态维护 + 少量 compat glue 清理”阶段。
- 已验证：`web-ui-service` 全量回归继续稳定，结果为 `130 passed, 6 warnings`。

### 2026-04-02（legacy_workbench 第三阶段收尾）

- 已完成：`legacy_workbench.py` 文件规模继续从 `2509` 行收缩到当前 `2186` 行。
- 已完成：assets 主题基础计算与运行态桥继续迁出，以下 helper 已进入 [workbench_asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_asset_service.py)：
  - `_count_test_point_types`
  - `_build_test_point_asset_semantic_summary`
  - `_build_test_point_asset_technique_summary`
  - `_merge_reference_items`
  - `_latest_run_snapshot_for_case`
- 已完成：failure/runtime records 相关读取桥继续迁出，以下 helper 已进入 [workbench_runtime_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_runtime_service.py)：
  - `_resolve_manifest_entries`
  - `_load_execution_record_payload`
  - `_load_runtime_execution_record_from_artifacts`
- 已完成：failure source calibration 相关 helper 已进入 [workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py)：
  - `_normalize_failure_source_value`
  - `_sanitize_failure_source_feedback`
  - `_record_failure_source_calibration_sample`
- 已完成：review 侧查询桥 `_review_decisions_for_run` 已进入 [workbench_review_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_review_service.py)。
- 已完成：analysis 小型 helper `_extract_page_from_url` 与 `_load_latest_self_healing_result` 已进入 [workbench_analysis_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_analysis_service.py)。
- 已判断：当前 [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py) 已基本进入 `compat facade + infra bridge` 稳态，不再适合继续做机械式 helper 搬运。

### 2026-04-02（平台治理能力第一刀落地）

- 已完成：新增平台治理总览接口 [dashboard.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/dashboard.py) 中的 `GET /api/dashboard/governance`。
- 已完成：新增治理聚合 service [workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py)，统一汇总：
  - quality gate 24h 趋势与阻断摘要
  - execution task governance risk 摘要
  - failure clusters 热点聚合
  - 管理视角 action items / top governance risks
- 已完成：dashboard 页面新增治理视图区块：
  - 高风险治理任务
  - 缺失 Manifest 任务
  - 失败聚类数
  - 需人工复核聚类
  - 治理行动建议
  - Top 治理风险任务
- 已完成：新增治理能力回归测试，覆盖 dashboard 页面骨架、治理聚合接口和降级路径。
- 已验证：当前 `web-ui-service` 回归结果为 `133 passed, 6 warnings`；全仓结果为 `185 passed, 1 skipped, 7 warnings`。
- 已明确：后续平台推进重心已从“继续拆 legacy”转向“治理指标统一、趋势洞察深化、schema/tool 闭环补齐”。

### 2026-04-02（平台治理能力第二刀：趋势治理看板）

- 已完成：治理总览接口继续扩展，`GET /api/dashboard/governance` 现在输出：
  - `trend_14d`
  - `trend_summary_7d`
- 已完成：治理聚合 service [workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py) 新增 14 天治理趋势聚合，统一汇总：
  - quality gate 日阻断
  - run 级 risk gate block
  - review required
  - self-healing attention
  - 日治理压力分
- 已完成：dashboard 页面新增治理趋势图与 7 天治理摘要：
  - 7d 门禁阻断
  - 7d 风险阻断
  - 7d 需复核
  - 趋势方向
- 已完成：补齐 dashboard 趋势相关回归测试与 builder 级聚合测试。
- 已验证：当前 `web-ui-service` 回归结果为 `134 passed, 6 warnings`；全仓结果为 `185 passed, 1 skipped, 7 warnings`。
- 已明确：dashboard 现在已经从“执行概览页”升级为“执行 + 治理”双视角入口。

### 2026-04-02（orchestrator schema/tool 最小闭环 + warning 清理）

- 已完成：`web-ui-service` 侧弃用 warning 清理：
  - [main.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/main.py) 已从 `on_event("startup")` 迁到 FastAPI lifespan
  - [workbench_generation.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/workbench_generation.py) 已移除弃用的 `HTTP_422_UNPROCESSABLE_ENTITY`
- 已完成：`web-ui-service` 测试 warning 降到 `0`，当前结果为 `134 passed`
- 已完成：补齐 ai-orchestrator 空 schema/tool 文件并接入主链 fallback：
  - [test-point.schema.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/schemas/test-point.schema.py)
  - [openapi-parser.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/openapi-parser.tool.py)
  - [git-diff.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/git-diff.tool.py)
  - [jira-reader.tool.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/tools/jira-reader.tool.py)
- 已完成：这些 tool/schema 已接入 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 的 requirement fallback 与 test-point normalization fallback，不再只是占位文件。
- 已完成：新增 orchestrator 侧回归测试 [test_multisource_fallback_tools.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_multisource_fallback_tools.py)。
- 已验证：当前全仓结果为 `189 passed, 1 skipped`。
- 已完成：ai-orchestrator 已新增自有 ASGI 适配层 [wsgi_asgi.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/wsgi_asgi.py)，原 `WSGIMiddleware` 弃用 warning 已清零。

### 2026-04-02（治理入口可操作化 + 人工验收清单）

- 已完成：治理 KPI 卡片与治理趋势摘要卡片升级为可点击入口，可直接跳转至 `/executions`、`/report/performance`、`/quality/clusters`、`/quality/trends`。
- 已完成：新增人工验收文档 [2026-04-02-governance-acceptance-checklist.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-governance-acceptance-checklist.md)。
- 已完成：新增自有 ASGI 适配层 [wsgi_asgi.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/wsgi_asgi.py)，替换已弃用的 `WSGIMiddleware` 依赖。
- 已验证：当前 `web-ui-service` 回归结果为 `134 passed`；全仓结果为 `189 passed, 1 skipped`。

### 2026-04-02（orchestrator 多源闭环剩余任务清单）

- 已完成：补充多源闭环剩余任务清单文档 [2026-04-02-orchestrator-multisource-closure-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-orchestrator-multisource-closure-backlog.md)。
- 已明确：当前 orchestrator 多源能力状态应定义为“最小闭环已完成，治理级闭环未完成”。
- 已明确：下一阶段优先级应按以下顺序推进：
  - `source_inputs / source_ids / reference_ids` 统一
  - `change_impact` 结构增强
  - 多源冲突与降级回归补齐
  - OpenAPI / Git Diff / defect 抽取深度增强
  - requirement -> test points -> case 追溯矩阵打通

### 2026-04-02（orchestrator 多源闭环第一版治理级收口完成）

- 已完成：`source_inputs / source_ids / reference_ids` 统一，`RequirementSpecV1`、test points、case steps、report 之间已形成稳定追溯链。
- 已完成：`change_impact` 结构增强，当前稳定输出 `changed_files / changed_modules / changed_areas / affected_intent_ids / impacted_source_ids / risk_signals / explanation`。
- 已完成：OpenAPI / Git Diff / defect tool 抽取深度增强，新增 endpoint / operation / request-body / response-body / permission / selector / business-rule 等结构化信号。
- 已完成：preview 消费面已展示 `source_count / source_types / change_impact` 摘要，前端预览文本也已反映 source ids 与 traceability status。
- 已完成：execution record 已写入多源摘要 metadata，tasks / governance 聚合链已可消费 `source_count / source_types / traceability_completeness / changed_areas`。
- 已完成：治理总览接口与 dashboard 已开始显示多源治理信号，Top governance risks 现在包含多源来源与追溯完整度。
- 已完成：相关回归补齐，定点回归结果为 `110 passed, 1 skipped`，全仓结果提升到 `190 passed, 1 skipped`。
- 已判断：当前 orchestrator 多源能力状态应更新为“最小闭环已完成，治理级闭环第一版已完成”，后续工作转入迭代增强而非补基础断层。

### 2026-04-02（下一阶段剩余任务清单）

- 已完成：整理下一阶段剩余任务清单文档 [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md)。
- 已明确：后续任务重点已从“修主链断层”切换为：
  - 治理闭环深化
  - 多源第二阶段解释与追溯增强
  - 运行态严格性与平台级回归护栏
  - 平台级分析与架构边界固化
- 已明确：推荐执行顺序应优先推进：
  - dashboard 跳转带筛选上下文
  - 治理指标口径统一
  - manager 视角治理摘要
  - 多源冲突裁决与 traceability completeness 增强
  - strict-mode readiness 与 regression pack

### 2026-04-03（docs/rule/ui 最高优先级对齐）

- 已完成：扫描并对齐 [docs/rule/ui](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui) 下的 UI 规范文档，新增盘点文档 [2026-04-03-ui-rule-compliance-audit.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-03-ui-rule-compliance-audit.md)。
- 已完成：重构平台左侧导航的信息架构，当前统一为：
  - 用例中心
  - AI生成
  - 执行中心
  - 质量分析
  - 资产与配置
  - 系统管理
- 已完成：将 `/quality/flaky`、`/assets/test-points`、`/defects`、`/quality/trends`、`/settings/scheduler`、`/gate` 等页面从“占位骨架”升级为具备统一 Hero、筛选条、批量选择栏、分页页脚和刷新入口的首版可用页面。
- 已完成：统一新增共享列表交互能力，已沉淀到 [platform_format.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js) 与 [governance_pages.css](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/governance_pages.css)，包含：
  - 最近刷新时间展示
  - 客户端分页
  - 批量勾选与复制
  - 表格页脚
  - 筛选摘要
- 已完成：关键治理列表页新增高级筛选折叠，并支持筛选条件保留：
  - 刷新页面后保留当前筛选
  - URL 查询参数与会话态同步
  - 重置时同时清理筛选状态
- 已完成：失败聚类页继续增强，新增跨页面 Hero 操作入口，并补齐 cluster table 分页页脚。
- 已完成：页面级集成回归，结果为 `105 passed`，覆盖：
  - 新导航结构
  - 关键页面共享工具栏
  - 选择栏
  - 分页页脚
  - 质量分析页面快速跳转
  - 高级筛选折叠入口
- 已完成：`web-ui-service` 全量回归继续稳定，结果为 `144 passed`。
- 已判断：`docs/rule/ui` 当前最高价值部分已经完成第一版落地，后续不再优先补“骨架页”，而是进入组件复用、图表深化和交互细节打磨阶段。

### 2026-04-02（Agent 模块待完善清单补充）

- 已完成：基于 `docs/architecture/agents-analysis.md` 中仍然有参考价值的部分，新增 Agent 模块补充清单文档 [2026-04-02-agent-improvement-supplement.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-agent-improvement-supplement.md)。
- 已明确：当前适合纳入待完善项的 Agent 主题包括：
  - `requirement-parser-agent` 内部职责拆分
  - `test-design-agent` 内部职责拆分
  - Agent 配置 / fallback / 日志 / 错误契约统一
  - Agent 层单元测试与黄金样本回归增强
  - `data-generation-agent` 企业级能力增强
- 已明确：以下旧判断不再建议直接纳入当前待完善清单：
  - “失败聚类分析缺失”
  - “测试点中间层缺失”
  - “必须立即引入统一 Agent 基类”
  - “self-healing-advisor-agent 是超大核心单体”

### 2026-04-02（docs/rule 规则对齐与平台强校验起步）

- 已完成：扫描 `docs/rule` 目录下的规则文档，并新增当前对齐盘点文档 [2026-04-02-rule-compliance-audit.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-rule-compliance-audit.md)。
- 已完成：新增共享规则校验模块 [apps/shared_backend/case_rules.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_rules.py)，用于承接 `case_id` 结构校验、标题基础质量校验、枚举字段校验和结构化元数据补齐。
- 已完成：规则已接入 YAML 资产保存链路与 workbench 手工保存链路，防止新增 `case` 再继续污染命名和结构。
- 已完成：新增共享规则测试 [apps/shared_backend/tests/test_case_rules.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/tests/test_case_rules.py)，并将资产合同测试纳入规则校验。

### 2026-04-03（docs/rule 规则对齐继续推进：字典源 / 状态机 / AI 观测）

- 已完成：新增共享规则字典数据源：
  - [apps/shared_backend/data/case_dictionaries.json](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/data/case_dictionaries.json)
  - [apps/shared_backend/case_dictionary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/case_dictionary.py)
- 已完成：新增共享状态机模块 [apps/shared_backend/state_machines.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/state_machines.py)，开始统一 `case_status / run_status / ai_status / migration_status`。
- 已完成：新增共享 AI 观测入口 [apps/shared_backend/observability/ai_trace.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/observability/ai_trace.py)，并接入 requirement parser fallback、orchestrator requirement spec、execution record metadata 与 telemetry。
- 已完成：`case_rules.py` 已升级为字典命中校验 + AI 状态校验 + 标题 4~5 段语义校验。
- 已完成：`asset_toolkit.py` 已切换为 AI 资产优先使用平台生成 ID，并配合 [scripts/normalize_case_texts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/normalize_case_texts.py) 再次清洗历史 YAML 标题文案。
- 已完成：新增 `GET /api/workbench/case-dictionaries`，前端和后续治理页面可直接消费平台字典源。
- 已验证：本轮聚焦回归结果为 `134 passed`。

### 2026-04-02（治理闭环 P0 收口）

- 已完成：dashboard 治理卡片与治理趋势卡片的跳转改为消费 `/api/dashboard/governance` 返回的标准化 `links`，不再依赖前端硬编码参数。
- 已完成：治理总览接口补齐并统一 `metric_definitions`，新增 `block_rate_24h`、`multisource_task_count`、`no_manifest_task_count`、`top_alert_code` 等口径说明。
- 已完成：`manager_summary` 新增 `top_theme`，dashboard 管理者摘要已能直接呈现本周治理主题。
- 已完成：治理相关集成回归补齐，当前定点结果为 `7 passed`，全仓结果为 `195 passed`。

### 2026-04-02（历史方案文档更新为当前状态版）

- 已完成：以下历史方案文档已补充“当前状态说明”，明确标注 `已完成 / 部分完成 / 未完成 / 不再建议按原方案继续`：
  - [detailed-refactoring-plan.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/detailed-refactoring-plan.md)
  - [test-point-layer-design.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/test-point-layer-design.md)
  - [failure-clustering-design.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/failure-clustering-design.md)
- 已完成：三份文档均补充“当前建议下一步”，并与 [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md) 对齐。

### 2026-04-02（orchestrator 拆分继续推进：failure / triage / self-healing）

- 已完成：新增 [failure_healing_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/failure_healing_support.py)，承接 failure / triage / self-healing 相关支持逻辑。
- 已完成：以下能力已从 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 迁出并改为兼容委托：
  - `evaluate_risk_report`
  - `triage_failure`
  - `enrich_failure_triage_with_history`
  - `analyze_failure`
  - `build_self_healing_advice`
  - `load_self_healing_suggestion_preview`
  - `load_self_healing_execution_preview`
  - `preview_self_healing_advice`
- 已验证：当前 `orchestrator_service.py` 行数已从 `2865` 行继续下降到 `2602` 行。
- 已验证：orchestrator 定点回归结果为 `61 passed`；全仓回归结果维持 `195 passed`。
- 已明确：主文件当前已经形成 `multisource + execution/report + analytics/query + failure/healing` 四块 support 委托结构，后续拆分将更聚焦剩余编排桥和边界固化。

### 2026-04-02（orchestrator 拆分继续推进：requirement quality / test-point generation）

- 已完成：新增 [requirement_testpoint_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/requirement_testpoint_support.py)，承接 requirement quality gate、test-point generation 与 requirement markdown 渲染相关逻辑。
- 已完成：以下能力已从 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 迁出并改为兼容委托：
  - `build_requirement_quality_gate`
  - `attach_requirement_quality_gate`
  - `build_requirement_quality_blocker`
  - `merge_case_requirements`
  - `build_test_points_preview`
  - `build_test_points_from_execution_steps`
  - `build_test_points_from_requirement_spec`
  - `apply_constraint_summary_to_test_points`
  - `build_constraint_technique_summary`
  - `map_intent_type_to_point_type`
  - `safe_int / safe_float`
  - `map_intent_to_step`
  - `render_requirement_spec_markdown`
- 已验证：当前 `orchestrator_service.py` 行数已从 `2602` 行继续下降到 `2107` 行。
- 已验证：requirement/test-point 定点回归结果为 `59 passed`；全仓回归结果维持 `195 passed`。
- 已明确：主文件当前已经形成 `multisource + execution/report + analytics/query + failure/healing + requirement/test-point` 五块 support 委托结构，后续拆分可以继续聚焦 `parse/orchestrate` 主编排桥。

### 2026-04-02（orchestrator 拆分继续推进：requirement parse subprocess / fallback）

- 已完成：新增 [requirement_parse_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/requirement_parse_support.py)，承接 requirement parser subprocess 与 fallback requirement spec 生成逻辑。
- 已完成：以下能力已从 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 迁出并改为兼容委托：
  - `_parse_requirement_spec`
  - `_infer_page_from_text`
  - `_build_requirement_parser_runtime_fallback`
- 已验证：当前 `orchestrator_service.py` 行数已从 `2107` 行继续下降到 `1895` 行。
- 已验证：requirement parse 定点回归结果为 `63 passed`；全仓回归结果维持 `195 passed`。
- 已明确：主文件当前已经形成 `multisource + execution/report + analytics/query + failure/healing + requirement/test-point + requirement/parse` 六块 support 委托结构，后续可以更集中地评估 `orchestrate` 主编排桥是否还需要继续收口。

### 2026-04-02（orchestrator 拆分收尾：agent execution + orchestration flow）

- 已完成：新增 [agent_execution_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/agent_execution_support.py)，承接 script generation、execution planner、test-design case/fallback 与 case-step 渲染逻辑。
- 已完成：新增 [orchestration_flow_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/orchestration_flow_support.py)，承接 `orchestrate(...)` 主编排桥。
- 已完成：以下能力已从 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 迁出并改为兼容委托：
  - `_generate_script_bundle`
  - `_build_execution_plan`
  - `_generate_case`
  - `_build_design_fallback_case`
  - `_build_design_generation`
  - `_render_case_steps_from_test_points`
  - `orchestrate`
- 已验证：当前 `orchestrator_service.py` 行数已从 `1895` 行继续下降到 `1585` 行。
- 已验证：定点回归结果为 `64 passed`；全仓回归结果维持 `195 passed`。
- 已完成：边界护栏同步收紧，当前 [check_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_orchestrator_service_boundary.py) 已将主文件上限调整为 `2000` 行，并要求保留全部核心 support 依赖。
- 已判断：本轮 orchestrator 正常任务清单已经完成，主文件当前已经稳定为 orchestrator facade + support bridge。

### 2026-04-02（正常任务清单 T1-T2 推进）

- 已完成：新增正常任务清单文档 [2026-04-02-normal-task-list.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-normal-task-list.md)，把后续工作收敛为 `T1~T5` 的连续执行序列。
- 已完成：`T1` 多源主块拆分，新增 [multisource_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/multisource_support.py)，`orchestrator_service.py` 已从 `4270` 行降到 `3695` 行。
- 已完成：`T2` execution/report 主块拆分，新增 [execution_report_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/execution_report_support.py)，`orchestrator_service.py` 已进一步降到 `3210` 行。
- 已完成：`OrchestratorService` 当前已将以下 execution/report 逻辑改为兼容委托：
  - report summary path / preview
  - execution record manifest 解析
  - execution record metadata merge / payload 构建
  - report payload 组装
  - report json / markdown 渲染
- 已验证：orchestrator 定点回归结果为 `50 passed, 1 skipped`；全仓结果保持 `193 passed, 1 skipped`。
- 已明确：正常任务清单下一步将进入 `T3 strict-mode 准备` 与 `T4 orchestrator 边界护栏`。

### 2026-04-02（正常任务清单 T3-T5 收口）

- 已完成：`T3 strict-mode 准备`，`execution_record_meta` 已新增 `manifest_record_path / manifest_status / resolution_reason`，compat builder 命中原因现在可观测、可消费、可回归。
- 已完成：strict-mode 用例已从环境依赖 skip 改为可直接执行的明确回归；同时新增 compat builder 命中回归，验证 fallback 场景下的 resolution meta。
- 已完成：OpenAPI 契约已同步扩展 `ExecutionRecordResolutionMetaV1`，与最新 execution record resolution 元数据保持一致。
- 已完成：`T4 orchestrator 边界护栏`，新增 [check_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_orchestrator_service_boundary.py) 与 [test_orchestrator_service_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/unit/test_orchestrator_service_boundary.py)。
- 已完成：当前 orchestrator 边界护栏约束包括：
  - [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 行数不得超过 `3300`
  - 必须保留 `MultisourceSupport` / `ExecutionReportSupport`
  - 禁止 `report_summary` 逻辑直接回流主文件
- 已完成：`T5` 文档同步，正常任务清单 [2026-04-02-normal-task-list.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-normal-task-list.md) 已更新为全部完成状态。
- 已验证：orchestrator 定点回归结果为 `22 passed`；全仓结果提升到 `195 passed`。

### 2026-04-02（继续推进：analytics/query 主块拆分）

- 已完成：继续将 [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py) 中与主编排解耦的分析/查询逻辑迁出，新增 [analytics_query_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/analytics_query_support.py)。
- 已完成：以下逻辑已改为兼容委托：
  - requirement parse telemetry summary / telemetry event read-write
  - latest report / named report query
  - failure cluster list / cluster detail query
- 已完成：新 support 已按实时路径取值，兼容测试中对 `report_root / runner_root / requirement_parse_telemetry_log` 的动态覆写行为。
- 已验证：本轮定点回归结果为 `64 passed`；全仓结果保持 `195 passed`。
- 已完成：`orchestrator_service.py` 文件规模继续从 `3213` 行收缩到 `2865` 行。

### 2026-04-02（平台级分析与架构边界固化收口）

- 已完成：治理总览继续深化，新增：
  - `failure_clusters.analysis`
  - `flaky_analysis`
  - `execution_strategy`
- 已完成：dashboard 新增“治理执行策略”“聚类与 Flaky 洞察”区块，已可直接展示推荐回归包、门禁建议、首要 cluster 和 flaky/change-impact 关联。
- 已完成：`workbench_task_service` 新增平台级执行策略汇总：
  - `recommended_regression_scope_counts`
  - `gate_recommendation_counts`
  - `recommended_regression_pack`
- 已完成：新增 `legacy_workbench` 边界检查脚本 [check_legacy_workbench_boundary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/check_legacy_workbench_boundary.py)，并补齐自动测试防止 route/business logic 回流。
- 已完成：新增 service 契约文档 [2026-04-02-service-contract-map.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-service-contract-map.md)，明确 governance / generation / reporting / runtime / review / gate / asset 分层职责与关键 payload。
- 已判断：`2026-04-02-platform-next-backlog.md` 中的 `P2-9 ~ P2-12` 已完成第一版收口，后续进入迭代增强而非基础补齐阶段。
- 已验证：当前 `web-ui-service` 回归结果为 `137 passed`；全仓结果为 `193 passed, 1 skipped`。

### 2026-04-02（正常任务清单 + orchestrator 第一刀拆分）

- 已完成：新增正常任务清单文档 [2026-04-02-normal-task-list.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-normal-task-list.md)。
- 已完成：`orchestrator_service.py` 的多源处理主块已抽离到 [multisource_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/multisource_support.py)。
- 已完成：`OrchestratorService` 保留兼容方法入口，内部已改为委托 support 模块，不破坏现有测试锚点。
- 已完成：`orchestrator_service.py` 文件规模已从 `4270` 行下降到当前 `3695` 行。
- 已验证：orchestrator 多源定点回归结果为 `15 passed, 1 skipped`；全仓结果保持 `193 passed, 1 skipped`。

### 2026-04-02（多源第二阶段增强 + strict-mode readiness 第一版）

- 已完成：多源冲突裁决 explainability 增强，[multisource_support.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/services/multisource_support.py) 现已稳定输出 `source_priority_rules / chosen_candidate / conflict_candidate_details / resolution_strategy`。
- 已完成：traceability completeness 计算增强，现已区分 `intent_coverage_status / source_coverage_status / covered / partial / gap / orphan`，并补齐 `orphan_step_keys / partial_source_ids / uncovered_source_ids / unmapped_changed_area_count`。
- 已完成：change impact explainability 已进入 preview / task / governance 消费面，现可稳定展示 `top_factor / recommended_regression_scope / why_manual_review / why_blocked`。
- 已完成：`strict_mode_readiness` 第一版增强，[workbench_reporting_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_reporting_service.py) 现已输出 `can_disable_compat_builder / blocking_reasons / improvement_actions / signals`。
- 已完成：任务汇总与治理总览现已直接消费 strict-mode 信号，[workbench_task_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_task_service.py) 与 [workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py) 已新增：
  - `strict_mode_status_counts`
  - `strict_mode_ready_task_count`
  - `strict_mode_caution_task_count`
  - `strict_mode_blocked_task_count`
  - `strict_mode_can_disable_compat_builder`
- 已完成：`/api/workbench/tasks` 已支持 `strict_mode_status` 过滤，执行页筛选上下文已可承接 strict-mode 治理动作。
- 已完成：平台级 regression pack 第一版补齐，已新增 governance / tasks / strict-mode / 多源 explainability 相关回归保护。
- 已验证：本轮定点回归结果为 `9 passed, 90 deselected`；全仓结果为 `196 passed`。

### 2026-04-02（剩余能力收口：CoverageMatrix / scheduler / runner-aware orchestration）

- 已完成：`CoverageMatrix / traceability completeness` 更产品化：
  - 新增资产级接口 `GET /api/workbench/test-point-assets/{asset_id}/coverage-matrix`
  - `coverage_matrix` 现已稳定输出 `row_id / traceability_status / source_ids / intent_ids / point_keys / missing_point_keys / changed_areas / explanation`
  - 已新增 matrix summary：`covered / partial / gap / orphan / latest_run_status / latest_run_missing_count`
- 已完成：统一调度中心第一版：
  - 新增 [workbench_scheduler_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_scheduler_service.py)
  - 新增接口：
    - `GET /api/workbench/scheduler/summary`
    - `GET /api/workbench/scheduler/dispatch-plan`
  - 已可输出 queue pressure、environment pools、resource profiles、runner distribution、dispatch lanes、recommended concurrency
- 已完成：failure cluster / flaky / risk scoring 第二版增强：
  - governance 总览已新增 `risk.score_breakdown`
  - `top_governance_risks[*]` 已新增 `risk_score_breakdown`
  - failure cluster analysis 已新增 `trend_pressure / risk_overlap_count / flaky_overlap_count`
  - flaky analysis 已新增 `risk_overlap_ratio / stability_score`
- 已完成：strict manifest-first 继续收紧：
  - governance summary 已新增 `strict_manifest_policy`
  - strict-mode 信号现已进入 task summary、manager summary、scheduler recommendations
  - 当前已可直接回答“是否适合关闭 compat builder，以及下一步动作”
- 已完成：API / Mobile runner 第一版：
  - ai-orchestrator 新增 `GET /runners/catalog`
  - `POST /orchestrate` 已支持 `runner=playwright/api/mobile`
  - 已支持 generate-only 的 runner-aware orchestration：
    - `playwright -> framework=playwright`
    - `api -> framework=requests`
    - `mobile -> framework=appium`
  - `api/mobile` 当前会明确阻止 `execute=true`
  - execution record / report request context 已写入 runner profile
  - YAML schema 已允许 `playwright/api/mobile`
- 已验证：定点回归结果为 `16 passed, 145 deselected`；全仓结果提升到 `202 passed`。

### 当前总体结论（2026-04-02 最新基线）

1. `legacy_workbench.py` 已完成主收口，当前按稳定兼容层与 infra 桥接层维护，不再作为重点重构对象。
2. `orchestrator_service.py` 已完成本轮大块拆分，当前重点从“继续拆单体”转向“平台能力增强与边界护栏保持稳定”。
3. 平台治理入口、治理趋势、多源闭环、strict manifest-first 治理消费、统一调度中心第一版、API / Mobile runner 第一版都已落地。
4. 当前实施日志与 backlog 应以：
   - [2026-04-02-platform-next-backlog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-platform-next-backlog.md)
   - [2026-04-02-normal-task-list.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-normal-task-list.md)
   为准。

### 2026-03-27（P1-任务4：数据驱动配置UI）

- 已完成：在 `cases` 页面新增“数据驱动配置”面板（启用开关、参数输入、数据行增删改）。
- 已完成：创建用例请求支持 `data_config`，并在后端标准化处理。
- 已完成：`test_cases` 模型新增 `data_config(JSON)` 字段，新增迁移脚本 `20260327_181500_add_test_cases_data_config.py`。
- 已完成：用例列表新增“数据驱动”状态列，便于快速识别是否启用数据驱动。
- 已完成：当启用数据驱动时，后端会将配置注入脚本（空脚本时生成可运行的参数化模板）。

### 验收建议

1. 打开 `用例库` 页面，新建用例时启用数据驱动并填写参数、数据行，确认可提交成功。
2. 创建后返回列表，确认“数据驱动”列显示“已启用”。
3. 调用 `GET /api/test-cases/{id}`，确认响应中存在 `data_config` 字段。
4. 若本地数据库使用 Alembic，执行迁移后确认 `test_cases.data_config` 列存在。

### 2026-03-28（P1-任务4补齐）

- 已完成：新增 `PUT /api/test-cases/{case_id}`，支持更新 `data_config` 并回写脚本。
- 已完成：用例详情页新增数据驱动配置区，可视化查看与编辑参数/数据行。
- 已完成：新增集成测试 `test_test_cases_data_config.py`，覆盖创建、读取、更新三条主路径。
- 已完成：前端静态资源版本号更新，避免浏览器缓存旧页面。
- 已完成：`batch/export` 现在也会携带 `data_config`，保证导出结果与平台回显一致。

### 2026-03-28（P0收尾：资产属性补齐）

- 已完成：`test_cases` 新增 `test_type`、`markers`、`pytest_path`、`status` 四个资产属性。
- 已完成：用例列表页展示测试类型、标记和状态。
- 已完成：用例详情页支持编辑并保存资产属性。
- 已完成：相关接口测试已补齐并通过。

### 当前结论（历史任务归档说明）

- 2026-03-27 ~ 2026-03-28 的用例编辑器、数据驱动配置、资产属性补齐任务均已完成，可视为历史归档记录。
- 当前项目主线已不再停留在早期 `P0/P1` 任务，而是进入“治理能力深化 + 多源解释与追溯增强 + 平台级分析与调度”的阶段。
- 若继续推进，请直接参考最新 backlog，而不是以本段旧阶段描述判断当前状态。

### 2026-04-03（UI IA 第二阶段：导航归属 + AI 向导 + 管理页骨架）

- 已完成：新版导航信息架构继续落地，补齐高优先级入口：`待审核用例 / 用例版本 / Prompt 管理 / 测试计划 / 权限与角色`。
- 已完成：旧 `/ai-orchestration` 入口已重定向到 `/workbench/generate`，避免重复入口继续扩散。
- 已完成：`AI生成` 主入口改为分步式向导，生成页现在明确分成“输入来源 / 生成配置 / 预览与提交”三步。
- 已完成：`调试工作台` 继续保留为调试职责，不再承载默认生成入口。
- 已完成：`用例中心` 主列表页改为“左列表 + 右详情”结构，统一展示脚本、执行、版本、缺陷上下文。
- 已完成：共享管理页骨架落地，`待审核用例 / 用例版本 / Prompt 管理 / 测试计划 / 权限与角色` 已统一到同一布局语言。
- 已完成：超阈值页面脚本拆分：
  - `workbench_generate.js` -> `workbench_generate_shared.js + workbench_generate_wizard.js + workbench_generate.js`
  - `cases.js` -> `cases_api.js + cases_dialog.js + cases.js`
- 已验证：
  - `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py`: `107 passed`
  - `apps/web-ui-service/tests`: `146 passed`
  - 全仓：`209 passed`
