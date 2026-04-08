# 企业级 AI 测试平台缺口补齐工作包台账（2026-04-06）

文档版本：v1.10  
文档类型：执行台账（Execution Backlog）  
目标：把架构缺口拆解成可交付、可验收、可回滚的工程任务包  
关联文档：`enterprise-ai-test-platform-full-architecture-and-gap-closure-2026-04-06.md`

---

## 0. 使用说明

本台账用于日常推进和周会同步，所有工作包遵循同一口径：

1. 每个工作包必须声明依赖、代码目录、验收标准、回滚边界。
2. 所有状态更新只改本文件，避免多文档口径分叉。
3. 未通过验收的工作包不得标记为完成。

状态字典：

- `未开始`
- `进行中`
- `阻塞`
- `已完成`

---

## 1. 全局进度看板（持续更新）

更新时间：2026-04-07 23:54 (Asia/Shanghai)

| 维度 | 完成度估算 | 当前状态 | 说明 |
|---|---:|---|---|
| 输入源层 | 55% | 进行中 | 多源解析已接入，结构化入库与追踪仍缺失 |
| 测试资产中心 | 69% | 进行中 | WP-01 已落迁移闭环；WP-02 已完成录制会话 API + 前端录制页 + 页面对象管理页联动 + 项目治理约束前后端一致，并补齐用例详情页、Workbench、生成历史、执行任务入口的一致性 |
| AI 编排层 | 62% | 进行中 | 主链可用，adapter/tool 空壳待补 |
| 自动化执行层 | 58% | 进行中 | Web 主链稳定，Mobile 未落地 |
| 执行与调度中心 | 35% | 进行中 | 汇总视图已具备，真实调度内核不足 |
| 证据采集层 | 64% | 进行中 | manifest-first 已启用，兼容回退待清零 |
| 质量分析与洞察层 | 50% | 进行中 | 摘要有，趋势/聚类/评分产品化不足 |
| 发布决策与治理层 | 61% | 进行中 | 门禁/审批可用，策略治理深度不足 |
| 基础设施层 | 47% | 进行中 | docker-compose 完整，K8s/MQ/对象存储待工程化 |

总体完成度（加权）：**58%（进行中）**

---

## 2. 工作包总览（按优先级）

| 编号 | 工作包 | 层级 | 优先级 | 状态 | 依赖 |
|---|---|---|---|---|---|
| WP-01 | 页面对象中心化数据模型落库 | 测试资产中心 | P0 | 进行中 | 无 |
| WP-02 | 页面对象录制主链（会话/捕获/确认） | 测试资产中心 | P0 | 进行中 | WP-01 |
| WP-03 | 执行层改造：步骤引用 element_code | 资产中心 + 执行层 | P0 | 未开始 | WP-01, WP-02 |
| WP-04 | 页面对象健康巡检与告警 | 资产中心 + 质量层 | P0 | 未开始 | WP-01 |
| WP-05 | API 契约中心（持久化 + 版本差异） | 测试资产中心 | P1 | 未开始 | WP-01 |
| WP-06 | 数据模板中心（模板/版本/引用） | 测试资产中心 | P1 | 未开始 | WP-01 |
| WP-07 | 统一资产写入口（case 写服务收口） | 应用编排层 | P1 | 未开始 | WP-01, WP-05, WP-06 |
| WP-08 | AI adapter/tool 空壳补齐 | AI 编排层 | P1 | 未开始 | 无 |
| WP-09 | 调度中心队列化（非只读汇总） | 执行与调度中心 | P1 | 未开始 | WP-03 |
| WP-10 | manifest-first 治理清零 compat fallback | 证据采集层 | P1 | 未开始 | WP-03, WP-09 |
| WP-11 | 质量分析产品化（Flaky/趋势/评分） | 质量分析层 | P2 | 未开始 | WP-10 |
| WP-12 | 门禁策略模板化与豁免治理 | 发布治理层 | P2 | 未开始 | WP-11 |
| WP-13 | 基础设施升级（MQ/对象存储/K8s） | 基础设施层 | P2 | 未开始 | WP-09, WP-10 |

---

## 3. 工作包明细（可执行）

## WP-01 页面对象中心化数据模型落库（P0）

目标：
建立页面对象的数据库主模型，结束“仅 YAML 资产”的治理短板。

改动目录：

- `apps/web-ui-service/app/models/`
- `apps/web-ui-service/app/schemas/`
- `apps/web-ui-service/app/services/`
- `apps/web-ui-service/app/routers/`
- `apps/web-ui-service/alembic/versions/`

新增对象（建议）：

- `page_objects`
- `page_elements`
- `page_element_versions`
- `page_object_refs`
- `page_element_health_checks`

验收标准：

1. 支持页面、元素 CRUD。
2. 支持元素版本快照。
3. 支持查询元素被哪些 case 引用。
4. migration 在 PostgreSQL 与 SQLite 均可执行。

回滚边界：

- 回滚本工作包新增 migration 与新表路由，不影响旧 YAML 执行主链。

当前进度（2026-04-06）：

- 已完成：`PageObject/PageElement/PageElementVersion/PageObjectRef/PageElementHealthCheck` 模型落库定义。
- 已完成：`page_object` schema 与 service（页面/元素 CRUD、版本快照、引用关系）。
- 已完成：`/api/page-objects` 路由主链与 `main.py` 挂载。
- 已完成：集成测试覆盖 CRUD、版本、引用、删除约束（`test_page_objects_api.py`）。
- 已完成：runner 侧 schema 同步（`page_object.schema.json`、`yaml_testcase.schema.json` 增强兼容字段）。
- 已完成：`page/element` 字段补齐（`page_url/module_id/element_count/health_status`、`backup_locator/health_status/version`）并回写页面聚合指标。
- 已完成：Alembic 最小骨架补齐（`alembic.ini`、`migrations/env.py`、`migrations/script.py.mako`、WP-01 revision、`scripts/bootstrap_database.py`）。
- 已完成：历史 `pyc` 迁移版本恢复为源码 revision，形成连续演进链（`20260323_143500` -> `20260327_181500` -> `20260406_181500_wp01...`）。
- 待完成：与录制器 WP-02 的会话写入接口衔接。

## WP-02 当前进度（2026-04-07）

- 已完成：录制会话模型 `page_object_recorder_sessions` 与迁移补齐。
- 已完成：录制会话 API：
  - `POST /api/page-objects/recorder/sessions`
  - `GET /api/page-objects/recorder/sessions/{session_id}`
  - `POST /api/page-objects/recorder/sessions/{session_id}/heartbeat`
  - `POST /api/page-objects/recorder/sessions/{session_id}/stop`
- 已完成：后端 `playwright codegen` 进程拉起/停止 + 录制脚本解析 + `page + element` 入库。
- 已完成：集成测试覆盖录制会话生命周期与入库幂等。
- 已完成：前端录制页面入口与会话状态展示（`/assets/page-objects/recorder`）。
- 已完成：页面对象管理页接入真实后端 API（`/assets/page-objects`，含 page/element 基础 CRUD）。
- 已完成：项目管理能力在用例列表 / 生成用例 / 页面对象 / 页面录制四个入口统一（共享 `project_selector_support.js` + 统一项目弹层回调）。
- 已完成：项目删除规则与测试口径对齐（默认仅校验数据库引用；显式传入 `state_root` 时才校验文件状态目录）。
- 已完成：Playwright 项目管理冒烟增强（`test_project_manager_smoke.py`）覆盖跨页面同步：`/cases`、`/ai-generation`、`/execution/workbench`、`/assets/page-objects`、`/assets/page-objects/recorder`，并校验 Workbench 在 inactive 项目下进入只读态。
- 已完成：`check_web_ui_pages.py` 巡检范围扩展到页面对象与录制页面，纳入匿名/登录双场景巡检。
- 已完成：inactive 项目写入约束落地（页面对象创建/更新/元素写入/录制会话创建统一校验 `project.status=active`），并补齐集成测试。
- 已完成：inactive 项目前端治理补齐（`cases` 新建草稿弹窗、`ai-generation`、`page-object-recorder` 均禁用 inactive 项目写入；仅保留列表筛选场景可见）。
- 已完成：用例服务写入口 active 校验补齐（`create_test_case`、`update_test_case`、`upsert_test_case_from_workbench`、`create/update_module_tree_node`、`update_script`、`batch_update_test_case_tags`、`batch_update_test_case_status`、`add_test_case_defect`），并补齐单测/集成测试。
- 已完成：服务层剩余高频写入口回归补齐（批量标签、脚本更新、模块树更新等），当前删除/清理类操作暂保留为治理例外，用于 inactive 项目存量清理。
- 已完成：`cases` 列表页前端治理提示与按钮收口：当筛选到单个 inactive 项目时，前端主动禁用新增、审核、改标签、废弃、树节点新增/编辑；运行、导出、删除保留。
- 已完成：用例列表 payload 下发 `project_status`，`cases` 页支持“全部项目”视图下按行/按选中集精确治理 inactive 项目用例，不再只依赖当前筛选项目粗粒度判断。
- 已完成：用例详情 payload 下发真实 `project_status`，详情页前端已与服务层治理规则对齐；inactive 项目下仅保留浏览、版本对比、执行历史查看，禁用资产属性、数据驱动、脚本和缺陷写入。
- 已完成：详情页治理回归补齐（service/API/detail template 占位），避免再次回落为 mapper 默认 `active`。
- 已完成：Workbench 项目列表改为结构化项目项（`project_code/project_name/status/source`），调试页接入统一项目管理弹层与治理提示。
- 已完成：Workbench YAML 保存链路补齐 inactive 项目写保护；前端在 inactive 项目下切换为只读浏览态，并允许基于已保存版本继续执行。
- 已完成：Workbench 项目 API / 保存 API / 页面模板回归补齐，确保调试入口与用例中心项目治理口径一致。
- 已完成：`/ai-generation/history` 与 `/execution/runs` 接入统一项目选择器、项目管理弹层、`project_code/project_status` 透传与 inactive 项目提示，历史/执行侧链入口与用例中心项目治理口径一致。
- 已完成：`/api/workbench/history`、`/api/workbench/tasks` 支持按 `project_code` 筛选，并补齐 `project_status` 返回；新增集成测试覆盖项目过滤与 inactive 项目状态透传。
- 已完成：`check-web-ui-static.sh` 纳入 `workbench_history*`、`execution_runs*` 脚本静态检查，避免新页面遗漏基线校验。
- 已完成：验证基线补齐并通过：`run-static-baseline-fast.sh`、页面巡检、集成测试（项目管理/页面对象/录制链路）、Playwright 项目管理冒烟。
- 待完成：捕获候选定位器实时回传（当前为 stop 后批量解析）。

---

## WP-02 页面对象录制主链（P0）

目标：
实现“录制优先”的页面对象入库流程。

改动目录：

- `apps/web-ui-service/app/routers/page_objects_recorder.py`（新）
- `apps/web-ui-service/app/services/page_object_recorder_service.py`（新）
- `apps/web-ui-service/app/services/page_object_locator_strategy_service.py`（新）
- `apps/web-ui-service/app/templates/page_object_recorder.html`（新）
- `apps/web-ui-service/app/static/page_object_recorder*.js`（新）

关键能力：

1. `session create/heartbeat/stop`
2. `capture candidates`
3. `locator scoring`
4. `confirm -> elements + versions`

验收标准：

1. 同一元素连续录制推荐定位器一致率 >= 90%（基线页面）。
2. 无法绕过策略直接提交自由 locator（普通角色）。
3. 录制数据可在页面对象列表查看。

回滚边界：

- 保留旧页面对象 YAML 可读，录制入口可下线但不影响线上执行。

---

## WP-03 执行层 element_code 引用改造（P0）

目标：
用例步骤不再直接依赖自由 locator，统一通过 `element_code` 解析。

改动目录：

- `runners/web-playwright-python/runner/`
- `apps/web-ui-service/app/services/test_case_service.py`
- `apps/web-ui-service/app/schemas/`

验收标准：

1. 新增用例步骤保存 `element_code`。
2. 执行时可解析到有效 locator。
3. 元素变更后无需改所有 case 脚本。

回滚边界：

- 保留旧 locator 兼容读取开关，问题时回切旧解析逻辑。

---

## WP-04 页面对象健康巡检与告警（P0）

目标：
建立元素失效自动发现机制。

改动目录：

- `apps/web-ui-service/app/services/`
- `apps/web-ui-service/app/routers/`
- `apps/ai-orchestrator/src/jobs/`（或 web-ui 定时任务）

验收标准：

1. 支持按计划巡检页面对象。
2. 失效元素写入 health check 记录。
3. 失败归因可引用最新健康状态。

---

## WP-05 API 契约中心（P1）

目标：
OpenAPI 不再是临时解析结果，形成契约资产中心。

改动目录：

- `apps/web-ui-service/app/models/`
- `apps/web-ui-service/app/routers/`
- `apps/web-ui-service/app/services/`
- `apps/ai-orchestrator/src/tools/openapi-parser.tool.py`（复用）

验收标准：

1. 契约导入与版本化存储可用。
2. 契约 diff 可查看 changed_areas。
3. 契约可关联到 case 与回归建议。

---

## WP-06 数据模板中心（P1）

目标：
把 `data_config` 从“单用例字段”升级为平台模板资产。

改动目录：

- `apps/web-ui-service/app/models/`
- `apps/web-ui-service/app/routers/`
- `apps/web-ui-service/app/services/`

验收标准：

1. 模板可新增/编辑/版本化。
2. case 可引用模板而非复制数据。
3. 支持查询模板被哪些 case 使用。

---

## WP-07 统一资产写入口（P1）

目标：
所有入口（AI 生成、Workbench、用例中心）统一走同一资产写服务。

改动目录：

- `apps/web-ui-service/app/services/`
- `apps/web-ui-service/app/routers/`

验收标准：

1. 不再出现同一资产在 DB/JSON/YAML 三处写法分叉。
2. 新增字段只需改一处 mapper/contract。
3. 审计日志链路一致。

---

## WP-08 AI adapter/tool 空壳补齐（P1）

目标：
补齐编排层关键空文件，避免运行时假能力。

当前空壳清单（需补）：

- `apps/ai-orchestrator/src/adapters/llm.adapter.py`
- `apps/ai-orchestrator/src/adapters/notification.adapter.py`
- `apps/ai-orchestrator/src/adapters/queue.adapter.py`
- `apps/ai-orchestrator/src/adapters/storage.adapter.py`
- `apps/ai-orchestrator/src/tools/evidence-reader.tool.py`
- `apps/ai-orchestrator/src/tools/runner-dispatch.tool.py`

验收标准：

1. 适配器有最小可用实现与错误处理。
2. 工具链可被 orchestrator 流程真实调用。
3. 对应单测/集成测试补齐。

---

## WP-09 调度中心队列化（P1）

目标：
从“调度汇总视图”升级为可执行调度能力。

改动目录：

- `apps/web-ui-service/app/services/workbench_scheduler_service.py`
- `apps/web-ui-service/app/services/workbench_task_service.py`
- `apps/web-ui-service/app/models/`（新增 task queue 相关表）

验收标准：

1. 支持任务优先级、并发上限、重试策略落库。
2. 支持队列状态机（queued/running/finished/failed）。
3. 调度执行与任务视图状态一致。

---

## WP-10 manifest-first 清零 compat fallback（P1）

目标：
证据链标准化，尽量消灭兼容回退路径。

改动目录：

- `apps/web-ui-service/app/services/workbench_reporting_service.py`
- `apps/web-ui-service/app/services/workbench_task_service.py`
- runner evidence 输出模块

验收标准：

1. `compat_scan_entry_count` 连续一周为 0（目标环境）。
2. `runtime_fallback_used` 为 false。
3. 证据健康状态达到 `healthy/ready`。

---

## WP-11 质量分析产品化（P2）

目标：
把当前摘要能力升级为可运营指标系统。

验收标准：

1. Flaky 列表与聚类视图可用。
2. 趋势看板支持周/月维度。
3. 风险评分附带可解释因子和建议动作。

---

## WP-12 门禁策略模板化（P2）

目标：
门禁从规则散点配置升级为策略模板中心。

验收标准：

1. 支持按项目/业务线配置门禁模板。
2. 支持豁免申请、审批、过期失效。
3. 产出门禁 KPI（误拦截率/漏拦截率/审批耗时）。

---

## WP-13 基础设施升级（P2）

目标：
为规模化执行和治理提供底座。

验收标准：

1. 引入消息队列用于异步编排。
2. 引入对象存储承载证据资产。
3. K8s 部署清单与最小化灰度流程可用。

---

## 4. 4 周滚动排期建议（默认）

| 周次 | 目标 | 工作包 |
|---|---|---|
| W1 | 资产中心基础模型落地 | WP-01, WP-02 |
| W2 | 执行层与巡检打通 | WP-03, WP-04 |
| W3 | 契约中心/模板中心/统一写入口 | WP-05, WP-06, WP-07 |
| W4 | 编排空壳补齐 + 调度与证据强化起步 | WP-08, WP-09, WP-10 |

> W5+ 进入质量与门禁产品化（WP-11/12）和基础设施升级（WP-13）。

---

## 5. 每日更新模板（复制使用）

```
日期：
负责人：

今日完成：
1.
2.

阻塞项：
1.

明日计划：
1.
2.

工作包状态变更：
- WP-xx: 未开始 -> 进行中
- WP-yy: 进行中 -> 已完成
```

---

## 6. 变更记录

| 日期 | 版本 | 变更内容 | 作者 |
|---|---|---|---|
| 2026-04-06 | v1.0 | 首次创建工作包台账，按全景架构缺口拆解 13 个工作包 | Codex |
| 2026-04-07 | v1.1 | 补记 WP-02 项目治理收口进展：四入口项目管理统一、inactive 项目写入前后端一致、验证链路补齐并通过 | Codex |
| 2026-04-07 | v1.2 | 补记用例服务写入口治理：active 项目校验下沉至 service 层并补齐回归测试 | Codex |
| 2026-04-07 | v1.3 | 扩展用例治理覆盖范围：脚本更新、批量标签/状态、缺陷关联写入口统一纳入 active 项目约束 | Codex |
| 2026-04-07 | v1.4 | 补记治理例外与测试扩围：删除/清理类操作暂保留，新增批量标签/脚本/模块树更新回归覆盖 | Codex |
| 2026-04-07 | v1.5 | 补记用例列表页 UI 治理收口：inactive 项目筛选态下的前端禁用策略与提示文案已落地 | Codex |
| 2026-04-07 | v1.6 | 补记列表 contract 升级：新增 `project_status` 字段，支持全项目视图逐行/逐选择集治理 inactive 项目用例 | Codex |
