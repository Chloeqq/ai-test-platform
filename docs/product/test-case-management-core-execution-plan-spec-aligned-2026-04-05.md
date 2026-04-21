# 测试用例管理层执行计划（规范版）

> 文档版本：v1.9  
> 制定日期：2026-04-05  
> 最近更新：2026-04-06  
> 规范依据：`docs/refactoring/case-management-codex-guide.md`  
> 适用范围：测试用例管理层（不含 runner 执行内核改造）

---

## 📋 一、任务概述

### 1.1 当前问题

| 问题 | 现状 | 影响 |
|------|------|------|
| 数据模型分散 | 管理层、共享层、文件层存在重复语义 | 同一用例跨系统不一致 |
| 项目维度缺失 | 用例主表缺 project 字段，项目隔离不可用 | 多项目治理混乱，无法做项目级统计与权限 |
| 生命周期薄弱 | 仅有基础状态字段 | 审批与发布不可追溯 |
| 追踪关系缺失 | Requirement/Bug/CodeChange 关系不完整 | 难以回答影响范围问题 |
| 自动化映射弱 | 仅脚本路径字段，缺强绑定 | 管理层与执行层脱节 |
| 审计能力不足 | 用例域审计不完整 | 合规风险高 |

### 1.2 本期目标

本期按流程图实现中台最小闭环：

1. 打通 `PRD/Swagger/Git Diff -> Case` 的结构化追踪链路
2. 建立项目级隔离：支持创建项目、项目切换、项目维度筛选与统计
3. 建立 `Draft -> Review -> Approved -> Active -> Deprecated` 生命周期与审批
4. 建立 `Case ID ↔ Script ID` 强映射
5. 支持三条必答查询：
   - 一个需求覆盖哪些用例
   - 一个 Bug 影响哪些用例
   - 一个代码改动触发哪些测试

### 1.3 关键断点诊断（新增）

结论：`AI 自动生成用例模块` 与 `测试用例管理模块` 当前已从“半打通”提升到**主链打通（治理未闭环）**状态。

| 诊断项 | 当前表现 | 代码证据 | 判定 |
|------|------|------|------|
| 生成入口 | AI 生成走 `/api/workbench/generate`，产出 YAML + state | `apps/web-ui-service/app/routers/workbench_generation.py`、`apps/web-ui-service/app/services/workbench_generation_service.py` | 已有 |
| 管理入口 | 用例列表走 `/api/test-cases`，读写 `test_cases` 表 | `apps/web-ui-service/app/routers/test_cases.py`、`apps/web-ui-service/app/services/test_case_service.py`、`apps/web-ui-service/app/models/test_case.py` | 已有 |
| 数据贯通 | `/api/workbench/generate`、`/api/workbench/auto-run` 生成后会 upsert 到 `test_cases` | `apps/web-ui-service/app/routers/workbench_generation.py`（`test_case_service.upsert_test_case_from_workbench`） | 主链已打通 |
| ID 体系 | 管理页主显示标准 `case_id`，保留 DB `id` 仅内部使用 | `apps/web-ui-service/app/templates/cases.html`、`apps/web-ui-service/app/static/cases_presenter.js` | 已统一 |
| UI 提示 | AI 生成入口收口到 `/ai-generation`，生成后可回到用例中心继续审核/治理 | `apps/web-ui-service/app/templates/cases.html`、`apps/web-ui-service/app/templates/workbench_generate.html` | 已打通 |

补充说明：

- 你提到的“最重要问题”判断是正确的：核心问题不在页面样式，而在“生成链路与管理链路的一致性治理”。
- 当前该问题已完成“主链打通”，下一阶段重点转向生命周期审批、关系追踪、自动化绑定与审计闭环。

### 1.4 项目维度现状补充（新增）

| 维度 | 当前现状 | 判定 |
|------|------|------|
| 管理主表 | `test_cases` 已有 `project_code` 字段 | 已具备基础能力 |
| 管理 API | `/api/test-cases` 支持 `project_code` 查询条件 | 已支持项目隔离查询 |
| AI 生成 UI | 项目选择已接入项目主数据，支持项目管理弹层（新增/编辑/删除） | 已可用 |
| AI 资产层 | workbench 资产支持按 `project` 存储路径 | 部分具备 |
| 项目字典 | 已落地 `test_projects` 注册表与 CRUD API | 已具备基础能力 |

### 1.5 当前总体进度快照（2026-04-06）

总体进度（按 Phase 加权）：**约 53%（进行中）**

| Phase | 当前状态 | 进度估算 | 进展摘要 |
|---|---|---:|---|
| Phase 1 输入源与编排统一 | 进行中 | 65% | 多输入源契约可用，AI 生成与管理主表同步链路已接通 |
| Phase 2 数据模型与迁移 | 进行中 | 48% | `case_id`/`project_code`/项目注册表已落地，关系模型与迁移治理待完成 |
| Phase 3 服务层实现 | 进行中 | 44% | AI upsert、项目 CRUD/删除保护/幂等保存、模块树节点 CRUD（新增/编辑/删除）已落地；生命周期/审批/追踪/绑定待完成 |
| Phase 4 API 与 CI 联动 | 进行中 | 42% | 项目管理 API、来源筛选、模块树治理 API、Playwright 项目弹层冒烟与 API 边界测试已补齐，`/api/v1` 与 CI 触发链待完成 |
| Phase 5 治理闭环验收 | 未开始 | 0% | 待前置 Phase 完成后进入 |

本轮进度校验（2026-04-06）：

- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/test_case_id_flow.py apps/web-ui-service/tests/integration/test_test_projects_api.py apps/web-ui-service/tests/integration/test_workbench_projects_api.py`：`17 passed`
- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/test_case_export_service.py`：`2 passed`

增量校验（2026-04-06）：

- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/test_case_id_flow.py apps/web-ui-service/tests/integration/test_test_projects_api.py apps/web-ui-service/tests/integration/test_workbench_projects_api.py apps/web-ui-service/tests/test_case_export_service.py`：`20 passed`
- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m ruff check apps/web-ui-service/app/routers/test_cases.py apps/web-ui-service/app/services/test_case_search_service.py apps/web-ui-service/app/services/test_case_service.py apps/web-ui-service/tests/test_case_id_flow.py`：`All checks passed`
- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m mypy apps/web-ui-service/app/routers/test_cases.py apps/web-ui-service/app/services/test_case_search_service.py apps/web-ui-service/app/services/test_case_service.py apps/web-ui-service/tests/test_case_id_flow.py`：`Success`

工程补齐验证（2026-04-06）：

- `scripts/qa/run-static-baseline-fast.sh`：`Completed`（新增 Web UI Service 分批 mypy 目标）
- `PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/integration/test_test_projects_api.py apps/web-ui-service/tests/integration/test_workbench_projects_api.py apps/web-ui-service/tests/test_case_id_flow.py apps/web-ui-service/tests/test_case_export_service.py`：`23 passed`
- `BASE_URL=http://127.0.0.1:8013 TEST_USERNAME=admin TEST_PASSWORD=admin123 PYTHONPATH=runners/web-playwright-python .venv/bin/python -m pytest -q -m "e2e and smoke" runners/web-playwright-python/tests/test_project_manager_smoke.py`：`1 passed`

列表企业化增量验证（2026-04-06）：

- `.venv/bin/ruff check apps/web-ui-service/app/services/test_case_search_service.py apps/web-ui-service/app/services/test_case_service.py apps/web-ui-service/app/services/test_case_mapper.py apps/web-ui-service/app/routers/test_cases.py apps/web-ui-service/tests/test_case_id_flow.py`：`All checks passed`
- `PYTHONPATH=apps/web-ui-service .venv/bin/mypy apps/web-ui-service/app/services/test_case_search_service.py apps/web-ui-service/app/services/test_case_service.py apps/web-ui-service/app/services/test_case_mapper.py apps/web-ui-service/app/routers/test_cases.py apps/web-ui-service/tests/test_case_id_flow.py`：`Success`
- `PYTHONPATH=apps/web-ui-service .venv/bin/pytest -q apps/web-ui-service/tests/test_case_id_flow.py apps/web-ui-service/tests/test_case_export_service.py`：`18 passed`
- `PYTHONPATH=apps/web-ui-service .venv/bin/pytest -q apps/web-ui-service/tests/integration/test_test_projects_api.py apps/web-ui-service/tests/integration/test_workbench_projects_api.py`：`7 passed`
- `BASE_URL=http://127.0.0.1:8013 TEST_USERNAME=admin TEST_PASSWORD=admin123 PYTHONPATH=.:apps/web-ui-service:runners/web-playwright-python .venv/bin/pytest -q -m "e2e and smoke" runners/web-playwright-python/tests/test_project_manager_smoke.py`：`1 passed`

测试点提取专项修复验证（2026-04-06）：

- `PYTHONPATH=apps/ai-orchestrator/src .venv/bin/pytest -q apps/ai-orchestrator/tests/integration/test_orchestrator_service_asset_flow.py -k "structured_requirement_without_collapsing_title"`：`1 passed`
- `PYTHONPATH=apps/ai-orchestrator/src .venv/bin/pytest -q apps/ai-orchestrator/tests/integration/test_orchestrator_service_asset_flow.py`：`13 passed`
- `.venv/bin/ruff check agents/requirement-parser-agent/src/agent.py agents/requirement-parser-agent/src/tools/document_fetcher.py agents/requirement-parser-agent/src/tools/local_file_reader.py agents/requirement-parser-agent/src/tools/user_story_parser.py apps/ai-orchestrator/tests/integration/test_orchestrator_service_asset_flow.py`：`All checks passed`
- `PYTHONPATH=. .venv/bin/mypy agents/requirement-parser-agent/src/tools/document_fetcher.py agents/requirement-parser-agent/src/tools/local_file_reader.py agents/requirement-parser-agent/src/tools/user_story_parser.py`：`Success`

入口一致性收口增量（2026-04-06）：

- 新增 `workbench_case_consistency_service`，统一按 `test_cases.case_id` 过滤所有 case 相关入口数据。
- 已接入过滤入口：`/api/workbench/history`、`/api/report/failures`、`/api/report/overview`、`/api/report/context`、`/api/report/performance`、`/api/defects`、`/api/workbench/runs*`、`/api/workbench/tasks*`、`/api/workbench/cases*`、`/api/workbench/test-point-assets*`、`/api/workbench/reviews`、`/api/workbench/execution-gate/*`。
- 新增清理接口：`POST /api/workbench/case-consistency/cleanup`，清理 `history/runtime-runs/defect-links/review-decisions/execution-gate-decisions/failure-source-calibrations` 与 `reports/executions` 中非 case center 的历史记录。
- 本地历史脏数据清理：已删除 `reports/executions` 下遗留 `SMOKE-*` / `TC-*` 报告，以及 `assets/test-cases/ai-generated` 下遗留 `SMOKE-*` 资产文件。
- 生成回退命名已收口：不再生成 `SMOKE-*` 风格 ID 与标题。

模块树治理增量（2026-04-06）：

- 已新增模块树节点治理 API：`POST /api/test-cases/tree/nodes`、`PUT /api/test-cases/tree/nodes`、`DELETE /api/test-cases/tree/nodes`，支持新增/编辑/删除。
- `GET /api/test-cases/tree` 已支持返回“无用例但已建树节点”的模块（`count=0`），用于列表页模块树与治理操作一致。
- 列表页已接入模块树治理入口（新增节点 / 编辑节点 / 删除节点），并在操作后刷新树与列表筛选上下文。
- 已修复树节点编辑的条件匹配写法，避免条件表达式导致误匹配风险。
- 新增集成测试覆盖模块树 CRUD 与删除约束：
  `PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/integration/test_test_case_tree_api.py`：`3 passed`。

---

## 🚫 二、执行约束（必须遵守）

1. 不直接修改/删除旧接口，新增能力优先放在 `/api/v1/`。
2. 不使用 `DROP TABLE` / 直接 `ALTER TABLE` 破坏性操作，统一通过迁移脚本。
3. 不改动 `runners/web-playwright-python/` 执行层目录（本期聚焦管理层）。
4. 不硬编码环境配置，新增配置同步更新 `.env.example`。
5. 每个新服务必须补对应单测，禁止“只写功能不验收”。
6. 分阶段提交，按 Phase 留档，不做一次性大提交。

---

## 📅 三、实施计划（按流程图拆解）

计划窗口：`2026-04-06` ~ `2026-05-31`（8 周）

### Phase 1：输入源与编排统一（第 1 周）

- [ ] 统一输入契约：PRD/Swagger/Git Diff/Manual
- [ ] 统一 `requirement_spec` 字段定义与版本号
- [ ] 规范化覆盖矩阵与 traceability 输出结构
- [ ] 设计 AI 生成资产到 `test_cases` 的同步契约（字段映射 + 冲突策略）
- [ ] 设计项目模型契约（Project Registry + 项目编码规则 + 默认项目策略）

出口标准：

- 输入源具备统一 DTO 与校验
- 解析结果可稳定落到管理层关系服务
- 输出 AI->Case 同步映射文档并评审通过
- 输出项目维度治理方案并评审通过

### Phase 2：数据模型与迁移（第 2-3 周）

- [ ] 落地核心关系模型（Requirement-Case / Change-Case / Case-Script）
- [ ] 落地审批与审计模型（任务、动作、事件）
- [ ] 增加必要索引与唯一约束
- [ ] 编写迁移脚本与干跑校验
- [x] 增加标准 `case_id` 字段与唯一索引，保留旧 `id` 兼容读
- [ ] 增加 `source`、`assignee`、`is_automated`、`review_status` 等列表治理必需字段
- [x] 在用例核心表增加 `project_code` 字段并用于项目隔离查询（组合唯一仍待专项评估）
- [x] 新增 `projects` 注册表（`test_projects`，支持基础治理字段）

出口标准：

- 新模型可在不破坏旧链路情况下并行运行
- 迁移脚本可重复执行且结果一致
- 管理页列表可返回标准 `case_id` 与来源字段
- 项目数据可隔离查询，且旧数据默认归档到 `default/atp`

### Phase 3：服务层实现（第 4-5 周）

- [ ] 生命周期状态机服务（流转校验）
- [ ] 审批服务（提审/通过/驳回/重提）
- [ ] Trace 关系服务（Requirement/Bug/Change 查询）
- [ ] 自动化绑定服务（Case↔Script 1:N）
- [x] AI 生成落库同步服务（WorkBench Asset -> Test Case Core）
- [x] 去重策略（同 case_id upsert，不重复插入）
- [x] 项目管理服务（创建/编辑状态/删除 + 引用保护 + 幂等更新）
- [ ] 项目成员/负责人治理能力（RBAC 与成员关系）
- [ ] 所有 case 查询默认必须带项目上下文（显式或默认）

出口标准：

- 核心服务完成并带单测
- 三条必答查询在服务层可用
- AI 生成后 30 秒内可在 `/api/test-cases` 查询到对应用例
- 通过 `project` 可独立查询项目内用例，不串数据

### Phase 4：API 层与 CI 联动（第 6-7 周）

- [ ] 新增 `/api/v1/` 查询与操作接口
- [ ] 增加变更影响触发接口（commit/diff -> case/suite）
- [ ] CI 调用选案接口并执行建议集
- [ ] 执行结果回写 Case 质量字段与追踪关系
- [ ] 列表接口升级：结构化筛选、多选标签（包含/排除）、时间范围、来源筛选
- [ ] 统计接口升级：总数/自动化率/通过率/待评审/失败用例
- [x] 项目管理 API：创建/列表/编辑/删除（详情与成员治理待补）
- [ ] 列表 API 支持 `project` 必填或会话默认项目

出口标准：

- API 合约稳定并通过集成测试
- CI 可基于代码变更输出建议执行集并触发执行
- 列表页所需的统计与筛选 API 能覆盖企业级操作路径
- 不同项目的 CI 触发与报告互不干扰

### Phase 5：治理闭环与发布验收（第 8 周）

- [ ] 接入治理看板基础指标（覆盖率/失败率/波动率）
- [ ] AI 建议单（优化/删除/补充）接入审批门禁
- [ ] 输出周报模板与运维手册
- [ ] 完成上线前回归与发布评审
- [ ] 用例列表企业化改版（列自定义、快捷筛选、批量操作、保存视图）

出口标准：

- AI 反哺默认“审批后生效”
- 形成可运营的治理闭环
- 用例列表页满足治理角色（QA 经理/测试工程师/开发）高频场景

---

## 3.1 列表页企业化专项（并行主线）

本专项并行推进，用于吸收当前页面诊断中提出的 23 项问题，按价值分层落地。

### P0（立即落地，1 天）

- [x] 用例列表显示标准 `case_id`（不再只显示自增 `id`）
- [x] 拆分“状态”和“最新结果”为两列
- [x] 优先级独立列并颜色编码（P0/P1/P2/P3）
- [x] 增加“AI 生成”快捷筛选入口
- [x] 顶部页面说明折叠化（默认收起）
- [x] 分页去重（去掉重复总数和快速跳页确定按钮）
- [x] 状态标签增强（图标 + 文本 + 无障碍友好配色）
- [x] 批量操作补齐（批量运行入口、批量删除、批量导出、批量废弃、批量标签）

### P1（核心体验，2-3 天）

- [x] 顶部统计卡片（总数/自动化率/通过率/失败）
- [x] 快捷筛选 Tab（全部/我的/失败/待评审/P0-P1/AI 生成/导入）
- [ ] 批量操作增强（批量编辑/执行/导出/状态）
- [x] 自动化状态列（Manual/Automated）
- [x] 来源字段筛选（AI/Manual/Coverage/Imported）
- [x] 多优先级筛选（`priority=P0,P1`，后端统一按逗号分隔解析）

### P2（增强体验，3-5 天）

- [ ] 高级筛选器（多选 + 排除 + 时间范围 + 质量维度）
- [ ] 执行趋势迷你图（近 10 次）
- [ ] 保存视图（个人/共享）
- [ ] 列自定义（显示/隐藏/顺序）
- [ ] 快速预览（抽屉或悬停）

### P3（专家效率，1 天）

- [ ] 键盘快捷键（j/k/e/r/d）
- [ ] 订阅与变更提醒（后续接消息中心）

## ✅ 四、验收标准

### 4.1 功能验收

| 功能 | 验收标准 | 验证方法 |
|------|----------|----------|
| 项目创建 | 可创建项目并返回标准项目编码 | API 测试 |
| 项目隔离 | A/B 项目用例列表互不可见 | 集成测试 |
| 生命周期状态机 | 状态只按合法路径流转 | 状态流转测试 |
| 审批流 | 提审/通过/驳回全量留痕 | API + 审计核对 |
| AI 生成落库同步 | AI 生成 case 能自动出现在管理列表 | 端到端联调测试 |
| 需求覆盖查询 | `requirement_id -> case list` 可查询 | 集成测试 |
| 缺陷影响查询 | `bug_id -> case list` 可查询 | 集成测试 |
| 变更触发查询 | `commit/diff -> case/suite` 可查询 | 集成测试 |
| 自动化映射 | Case↔Script 支持 1:N 且状态可见 | API + DB 校验 |
| 列表企业化能力 | 标准 ID、结构化筛选、批量操作、统计卡片可用 | UI 集成测试 |

### 4.2 质量验收

| 指标 | 要求 | 工具 |
|------|------|------|
| 类型检查 | 核心新增模块通过类型检查 | mypy |
| 代码规范 | 新增代码无 ruff 告警 | ruff |
| 单测覆盖 | 新服务覆盖率 ≥ 90% | pytest-cov |
| 审计完整性 | 关键动作 100% 有审计事件 | 抽样审计 |
| 交互可用性 | 关键列表操作 3 步内完成 | 场景走查 |

### 4.3 性能验收

| 场景 | 要求 | 验证方式 |
|------|------|----------|
| 项目切换列表加载 | P95 < 500ms | 压测 |
| 需求覆盖查询 | P95 < 500ms | 压测 |
| 变更触发查询 | P95 < 800ms | 压测 |
| 审批动作写入 | P95 < 200ms | 压测 |
| 列表筛选响应 | P95 < 400ms | 压测 |
| 列表首屏加载 | P95 < 1.2s | 压测 |

---

## 🧾 五、留档与跟踪机制

### 5.1 周期留档规则

- 每周五更新一次本计划执行状态
- 每个 Phase 完成后追加“完成记录”
- 变更必须记录：影响范围、迁移版本、回滚方案

### 5.2 状态定义

- `未开始`
- `进行中`
- `已完成`
- `阻塞`

### 5.3 里程碑跟踪表（持续更新）

| 里程碑 | 时间窗口 | 状态 | 实际完成日 | 备注 |
|---|---|---|---|---|
| Phase 1 输入与编排统一 | 2026-04-06 ~ 2026-04-12 | 进行中 | - | 输入契约与 AI->Case 主链已落地 |
| Phase 2 数据模型与迁移 | 2026-04-13 ~ 2026-04-26 | 进行中 | - | `case_id`/`project_code`/`test_projects` 已提前落地 |
| Phase 3 服务层实现 | 2026-04-27 ~ 2026-05-10 | 进行中 | - | AI upsert、项目 CRUD、删除保护与幂等保存已提前落地，审批与追踪待补 |
| Phase 4 API 与 CI 联动 | 2026-05-11 ~ 2026-05-24 | 进行中 | - | 项目 API 与列表项目筛选已先行，`/api/v1` 主线待启动 |
| Phase 5 治理闭环验收 | 2026-05-25 ~ 2026-05-31 | 未开始 | - | 待启动 |
| 列表企业化专项 P0 | 2026-04-08 ~ 2026-04-08 | 已完成 | 2026-04-06 | 标准 `case_id`、状态标签增强、批量操作补齐、分页去重、顶部说明折叠已落地 |
| 列表企业化专项 P1-P2 | 2026-04-09 ~ 2026-04-15 | 进行中 | - | 统计卡片、自动化状态列、快捷筛选 Tab、来源筛选与多优先级筛选已落地，高级筛选与保存视图待补 |

---

## 🔗 六、关联文档

- [case-management-codex-guide.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/refactoring/case-management-codex-guide.md)
- [test-case-management-core-gap-tracking-2026-04-05.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/test-case-management-core-gap-tracking-2026-04-05.md)
- [test-case-management-core-execution-plan-2026-04-05.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/test-case-management-core-execution-plan-2026-04-05.md)
- [test-case-list-enterprise-upgrade-plan-2026-04-05.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/test-case-list-enterprise-upgrade-plan-2026-04-05.md)

---

## 📝 七、变更记录

| 日期 | 版本 | 变更内容 | 变更人 |
|------|------|----------|--------|
| 2026-04-05 | v1.0 | 按 refactoring 规范重制执行计划（Phase 化 + 验收表 + 留档机制） | Codex |
| 2026-04-05 | v1.1 | 纳入列表页企业化优化与“AI生成-用例管理半打通”整改主线 | Codex |
| 2026-04-06 | v1.2 | 更新实时进度：AI->Case 主链打通、项目管理 CRUD 落地、里程碑状态从未开始改为进行中 | Codex |
| 2026-04-06 | v1.3 | 同步最新进度与验证结果：项目管理服务/API 勾选更新，新增 19 条自动化测试通过证据 | Codex |
| 2026-04-06 | v1.4 | 列表 P0 缺失项完成（状态/结果分列、优先级色标、AI 快捷筛选），新增来源筛选契约并补齐测试/lint/typecheck 证据 | Codex |
| 2026-04-06 | v1.5 | 工程补齐三项缺失：Web UI mypy 分批纳管、项目管理弹层 Playwright 冒烟、项目删除约束 API 边界测试 | Codex |
| 2026-04-06 | v1.6 | 列表页 P0 企业化交付收口：批量删除/运行入口、状态徽标可读化、分页精简、顶部说明折叠，完成静态检查与回归测试 | Codex |
| 2026-04-06 | v1.7 | 列表页 P1 首批落地：新增统计卡片（总用例/自动化率/通过率/失败）与自动化状态列，补齐后端 stats 契约及测试 | Codex |
| 2026-04-06 | v1.8 | 列表页 P1 第二批落地：快捷筛选 Tab、来源筛选、多优先级筛选（P0/P1）与上下文字段统一，补齐 lint/typecheck/单测/项目 API 与项目弹层冒烟回归证据 | Codex |
| 2026-04-06 | v1.9 | 测试点提取专项修复：补齐 requirement-parser 缺失工具模块，新增结构化模板字段拆段（前置条件/测试步骤/预期结果）并加入回归测试，修复“整段标题污染、测试点提取失真”问题 | Codex |
| 2026-04-06 | v1.10 | 修复“AI 生成用例保存草稿失败且不可找回”链路：放宽 workbench upsert 的自资产 ID 冲突判定、生成阶段避让已存在 case_id、冲突重试取消危险删文件动作，并补齐 3 条回归测试 | Codex |
