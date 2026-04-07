# 测试用例管理中台差距跟踪记录（2026-04-05）

## 0. 文档目标

本文件用于跟踪“测试用例管理层（Test Case Management Core）”与目标企业标准之间的差距，作为后续迭代的唯一跟踪台账。

关联执行计划：

- [test-case-management-core-execution-plan-2026-04-05.md](./test-case-management-core-execution-plan-2026-04-05.md)
- [test-case-management-core-execution-plan-spec-aligned-2026-04-05.md](./test-case-management-core-execution-plan-spec-aligned-2026-04-05.md)（推荐主计划）
- [test-case-list-enterprise-upgrade-plan-2026-04-05.md](./test-case-list-enterprise-upgrade-plan-2026-04-05.md)
- [test-case-case-id-unification-priority-plan-2026-04-05.md](./test-case-case-id-unification-priority-plan-2026-04-05.md)（编号统一专项）
- [test-case-field-persistence-plan-2026-04-05.md](./test-case-field-persistence-plan-2026-04-05.md)（字段落库方案）
- [test-case-excel-export-implementation-plan-2026-04-05.md](./test-case-excel-export-implementation-plan-2026-04-05.md)（Excel 导出方案）

范围包含：

- 用例资产管理（Case Asset）
- 用例建模与结构化（Case Modeling）
- 生命周期管理（Lifecycle）
- 用例关系与追踪（Traceability）
- 用例与自动化映射（Automation Binding）
- 用例选择与编排（Selection & Suite）
- 用例质量治理（Quality Governance）
- AI 增强接口层（AI Bridge）

---

## 1. 本次基线结论（2026-04-05）

总体判定：`基础能力已具备，企业级中台能力未闭环`。

- 已具备：用例、执行、缺陷、版本等基础数据结构和接口
- 部分具备：AI 解析 PRD/OpenAPI/Git Diff 并输出覆盖矩阵/追踪摘要
- 主要缺口：审批状态机、跨域追踪关系、Case↔Script 强映射、合规审计闭环
- 关键断点状态更新：AI 自动生成用例与管理主表已完成主链打通（生成后可 upsert 到 `test_cases`）
- 项目维度状态更新：`project_code` + 项目注册表 CRUD 已落地，下一步聚焦权限、成员与统计闭环
- 自动化验证更新：项目维度与编号链路相关回归 `23 passed`（含项目 API、WorkBench 项目聚合、Excel 导出、来源筛选、删除约束边界）
- 前端交互自动化更新：项目管理弹层 Playwright 冒烟已补齐（新增/编辑/删除链路 `1 passed`）

### 1.1 最新进度快照（2026-04-06）

总体进度（按执行计划 Phase 加权）：**约 43%（进行中）**

| Phase | 进度估算 | 进展摘要 |
|---|---:|---|
| Phase 1 输入源与编排统一 | 65% | AI 生成到管理主表主链已打通 |
| Phase 2 数据模型与迁移 | 48% | `case_id`/`project_code`/`test_projects` 主数据基础已落地 |
| Phase 3 服务层实现 | 40% | 项目 CRUD、删除保护、幂等保存与弹窗闭环已上线 |
| Phase 4 API 与 CI 联动 | 35% | 项目 API、来源筛选、Playwright 项目弹层冒烟与 API 边界测试已可用，CI 触发链待补 |
| Phase 5 治理闭环验收 | 0% | 未开始 |

---

## 2. 八大能力域对照清单

| 能力域 | 目标状态 | 当前状态 | 判定 | 关键证据 |
|---|---|---|---|---|
| 1. 用例资产管理 | 可管理 Case/Version/Run/Bug 资产 | 已有 `test_cases`/`test_case_versions`/`test_case_executions`/`test_case_defects` | 部分具备 | `apps/web-ui-service/app/models/test_case.py` |
| 2. 用例建模与结构化 | Case 拥有 Preconditions/Steps/Expected/Assertions | 当前偏执行字段（`script_code`/`pytest_path`），缺结构化步骤模型 | 缺关键能力 | `apps/web-ui-service/app/models/test_case.py` |
| 3. 生命周期管理 | `Draft → Review → Approved → Active → Deprecated` | 仅允许 `active/inactive/deprecated` | 缺关键能力 | `apps/web-ui-service/app/services/test_case_data_service.py` |
| 4. 用例关系与追踪 | Requirement↔Case↔Run↔Bug↔CodeChange 可追溯 | 仅有部分 Case-Defect 链接；缺统一关系层 | 缺关键能力 | `apps/web-ui-service/app/models/test_case.py` `apps/web-ui-service/app/models/workbench_state.py` |
| 5. 用例与自动化映射 | `Case ID ↔ Script ID` 强映射、手动/自动、1:N 覆盖 | 仅 `pytest_path` 文本字段，无绑定表 | 缺关键能力 | `apps/web-ui-service/app/models/test_case.py` |
| 6. 用例选择与编排 | Suite/回归策略/变更触发编排 | 目前主要是 batch CRUD/导出，无 Suite 实体 | 部分具备 | `apps/web-ui-service/app/routers/test_cases.py` |
| 7. 用例质量治理 | 审核队列、质量规则、审计看板闭环 | 页面有治理入口，但仍是占位与后续接入说明 | 部分具备 | `apps/web-ui-service/app/routers/ui_assets_pages.py` |
| 8. AI 增强接口层 | 多输入源解析并反哺中台实体 | 解析能力较强，回写到中台关系层不足 | 部分具备 | `apps/ai-orchestrator/src/services/requirement_parse_support.py` `apps/ai-orchestrator/src/services/multisource_support.py` |

---

## 3. 必须做到（三条）现状判定

| 必须项 | 目标 | 现状 | 判定 |
|---|---|---|---|
| 一个需求覆盖哪些用例 | Requirement -> Case 可查询 | 缺 Requirement↔Case 关系模型与查询接口 | 未达标 |
| 一个 Bug 影响哪些用例 | Bug -> Case 可查询 | 有缺陷关联，但仍分散且不统一 | 部分达标 |
| 一个代码改动触发哪些测试 | Git Diff -> Suite/Case 可触发 | 有 Git Diff 解析，未形成稳定触发编排 | 未达标 |

---

## 4. 三项重点缺口（你指定）

### 4.1 审批流（PRD→Case）

当前缺口：

- 缺 PRD 实体与 PRD↔Case 关系
- 缺审批状态机与审批动作落库
- 缺审批角色（提审/审核/驳回/发布）与权限矩阵

### 4.2 版本对比（谁改了什么）

当前现状：

- 已有版本表和版本对比能力（`test_case_versions` + compare）
- 但对“结构化字段级差异”（步骤变更、断言变更）支持不足

### 4.3 审计日志（合规）

当前现状：

- Workbench 侧存在历史事件模型
- 用例管理核心域缺统一审计模型（审批、状态流转、字段变更、关联变更）

---

## 5. 分阶段落地计划（建议）

### P0（1-2 周）：先打中台底座

1. 生命周期状态机升级  
目标：支持 `Draft/Review/Approved/Active/Deprecated` 与合法流转校验。

2. 审批流最小可用  
目标：`PRD -> Case Draft -> Review -> Approved`，动作全量落审计。

3. 用例域审计日志表  
目标：记录 `谁在何时改了什么`，并可按 Case/PRD/Run 回查。

验收标准：

- 任意状态变更可追溯到操作者、时间、前后状态
- UI 可查看审批轨迹与驳回原因

### P1（2-4 周）：补齐追踪关系与自动化绑定

1. 关系层建模  
目标：新增 Requirement↔Case、Case↔Run、Run↔Bug、Change↔Case 关系。

2. 自动化强映射  
目标：新增 Case↔Script 绑定表，支持 1:N 覆盖、手动/自动状态、绑定健康度。

3. 变更影响触发  
目标：Git Diff 入库后可推导“建议执行 Case/Suite”。

验收标准：

- 输入 requirement_id 可返回覆盖 case 列表
- 输入 bug_id 可返回受影响 case 列表
- 输入 commit/diff 可生成触发测试清单

### P2（4-6 周）：治理闭环与 AI 反哺

1. Suite 编排中心  
目标：支持基线回归、风险回归、热区回归。

2. 用例质量评分  
目标：覆盖率、波动率、失效率、陈旧度形成治理分。

3. AI 反哺策略  
目标：根据执行结果自动建议优化/弃用/补充用例，并走审批流。

验收标准：

- 每周可输出“低质量用例清单 + 处理建议”
- AI 推荐变更不直接生效，必须经过审核

---

## 6. 跟踪台账（持续更新）

| 日期 | 事项 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|
| 2026-04-05 | 中台差距基线评估完成 | 已完成 | 平台团队 | 首版结论，作为后续迭代基线 |
| 2026-04-05 | 生命周期状态机升级方案评审 | 待开始 | 待定 | P0 首任务 |
| 2026-04-05 | 审批流数据模型设计 | 待开始 | 待定 | PRD↔Case↔审批动作 |
| 2026-04-05 | 追踪关系层 ER 设计 | 待开始 | 待定 | Requirement/Case/Run/Bug/Change |
| 2026-04-05 | 执行计划留档（8 周里程碑） | 已完成 | 平台团队 | 见执行计划文档 v1.0 |
| 2026-04-05 | 规范版执行计划留档 | 已完成 | 平台团队 | 按 refactoring 规范重制 Phase 计划 |
| 2026-04-05 | 增补列表页企业化专项与 AI/Case 打通整改 | 已完成 | 平台团队 | 执行计划升级到 v1.1 |
| 2026-04-05 | 固化 `case_id` 统一决议与优先级 | 已完成 | 平台团队 | 单独留档为编号统一专项，后续按该基线执行 |
| 2026-04-05 | 字段落库方案与 Excel 导出方案留档 | 已完成 | 平台团队 | 后续开发按这两份设计文档落地 |
| 2026-04-06 | AI 生成 -> 用例主表同步（upsert）主链打通 | 已完成 | 平台团队 | `/api/workbench/generate`、`/api/workbench/auto-run` 均回写 `test_cases` |
| 2026-04-06 | 项目主数据 CRUD 落地（新增/编辑/删除） | 已完成 | 平台团队 | `/api/test-projects` 支持 `GET/POST/PUT/DELETE` |
| 2026-04-06 | 用例中心与 AI 生成页项目管理弹层上线 | 已完成 | 平台团队 | 支持项目管理与跨页复用，含幂等保存提示 |
| 2026-04-06 | 规范版执行计划进度更新到 v1.2 | 已完成 | 平台团队 | 里程碑状态与 Phase 进度已同步 |
| 2026-04-06 | 项目管理保存交互修正 | 已完成 | 平台团队 | 幂等保存提示“项目已存在”，保存成功自动关闭弹窗 |
| 2026-04-06 | 规范版执行计划进度更新到 v1.3 | 已完成 | 平台团队 | 更新总体进度到 35%，并补充自动化验证证据 |
| 2026-04-06 | 回归验证补录 | 已完成 | 平台团队 | `test_case_id_flow` + 项目集成测试 + 导出测试共 `19 passed` |
| 2026-04-06 | 用例列表 P0 改版落地 | 已完成 | 平台团队 | 状态/结果分列、优先级色标、AI 快捷筛选全部完成 |
| 2026-04-06 | 来源筛选契约落地（API+服务+搜索语法） | 已完成 | 平台团队 | 支持 `source` 参数与 `来源:AI` 语法，管理层与 UI 快捷筛选一致 |
| 2026-04-06 | 规范版执行计划进度更新到 v1.4 | 已完成 | 平台团队 | 总体进度更新到 39%，补齐 pytest/ruff/mypy 证据 |
| 2026-04-06 | Web UI Service mypy 分批纳管 | 已完成 | 平台团队 | `run-static-baseline-fast.sh` 新增 `apps/web-ui-service/app` 分批目标并通过 |
| 2026-04-06 | 项目管理弹层 Playwright 冒烟补齐 | 已完成 | 平台团队 | 新增 `test_project_manager_smoke.py`，新增/编辑/删除链路通过 |
| 2026-04-06 | 删除约束 API 边界测试补齐 | 已完成 | 平台团队 | 新增 inactive 删除、空更新 payload、状态非法值用例 |
| 2026-04-06 | 规范版执行计划进度更新到 v1.5 | 已完成 | 平台团队 | 总体进度更新到 43%，补齐三项缺失与验证证据 |
| 2026-04-06 | 用例入口一致性收口与历史清理 | 已完成 | 平台团队 | 新增 case center 统一过滤服务，接入 history/failures/runs/tasks/assets/reviews/gate，新增 `/api/workbench/case-consistency/cleanup`，清理遗留 `SMOKE-*`/`TC-*` 报告与资产 |

---

## 7. 下次复盘检查点

建议在以下任一条件触发时更新本文件：

- P0 任一任务落地合并
- 新增或调整中台核心表结构
- 审批流或追踪关系 API 首次上线
- CI/CD 增加“变更影响触发测试”能力

更新方式建议：

- 仅追加，不覆盖历史记录
- 每次更新附带“变更文件 + 接口 + 验收结果”
