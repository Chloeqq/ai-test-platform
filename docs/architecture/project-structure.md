# 项目目录分层

本文档描述当前项目的真实目录重心，帮助新同学先建立地图，再进入具体代码。

核心原则：

- 先理解主链目录，不把所有目录看成同等重要。
- 新功能优先进入主链目录，避免继续堆到历史兼容层。
- 运行态产物和长期业务事实分开看。

---

## 1. 当前主链目录

当前最重要的主链是：

```text
apps/web-ui-service
  -> apps/ai-orchestrator
  -> shared_backend
  -> runners/web-playwright-python
  -> assets / reports / web-ui/state
```

### `apps/web-ui-service/`

当前 Web UI 主服务。

职责：

- 承载用户入口、Workbench、用例中心、资产中心、报告、认证、Dashboard、质量治理页面和 API。
- 通过配置中的 `ORCHESTRATOR_URL` 调用 `apps/ai-orchestrator`。
- 管理业务库表，如用户、项目、页面对象、测试点、测试用例、执行记录、审核决策等。
- 提供 React 前端主工程，并将构建产物托管到 FastAPI 静态资源。

关键入口：

- `app/main.py`：FastAPI app 与 router 注册。
- `app/routers/`：HTTP API 和页面入口。
- `app/api/workbench/facade.py`：Workbench 聚合门面。
- `app/services/workbench_generation_api/`：AI 生成、预览、保存、预检等主链服务。
- `app/models/`：SQLAlchemy 业务模型。
- `app/schemas/`：Web UI 层 Pydantic schema。
- `app/core/`：配置、数据库、认证、Redis、分页、页面分析等基础能力。
- `frontend/`：Vite + React + TypeScript 前端主工程。
- `migrations/`：Alembic 数据库迁移。

常见改动放置：

- 新 Web API：优先放到 `app/routers/`，业务逻辑放到 `app/services/`。
- Workbench 主链逻辑：优先看 `app/api/workbench/` 和 `app/services/workbench_generation_api/`。
- 数据库表结构：改 `app/models/` 并补 Alembic migration。
- React 页面：改 `frontend/src/`，构建后进入 `app/static/react`。

### `apps/ai-orchestrator/`

当前 AI 编排 API 服务。HTTP 层基于 Flask，并通过 `create_server()` 兼容 CLI 和集成测试。

职责：

- 暴露 `/orchestrate`、`/requirements/parse`、`/risk/evaluate`、`/failures/triage`、`/healing/preview` 等编排接口。
- 编排需求解析、测试点生成、测试用例生成、契约校验、runner 执行、报告生成和失败分析。
- 调用 `agents/` 和 `runners/web-playwright-python/`，同时复用 `shared_backend/` 的契约和编译规则。

关键入口：

- `src/app.py`：HTTP 路由入口，`POST /orchestrate` 在这里。
- `src/orchestrator_service.py`：编排服务门面。
- `src/services/orchestration_flow_support.py`：`orchestrate` 主流程。
- `src/services/requirement_parse_support.py`：需求解析支持。
- `src/services/requirement_testpoint_support.py`：测试点相关支持。
- `src/services/execution_report_support.py`：报告构建支持。
- `src/services/failure_healing_support.py`：失败分析和自愈建议支持。
- `src/services/runner_registry_support.py`：runner 能力注册。
- `openapi/orchestrator-openapi.yaml`：Orchestrator API 契约。
- `tests/integration/`：`POST /orchestrate` 等集成测试主入口。

常见改动放置：

- 新 HTTP 编排接口：从 `src/app.py` 接入，核心逻辑放到 service/support 模块。
- `/orchestrate` 主链变更：优先改 `orchestrator_service.py` 或 `services/orchestration_flow_support.py`。
- 响应契约变更：同步 `openapi/orchestrator-openapi.yaml` 和集成测试。

### `shared_backend/`

仓库根目录下的共享契约与规则层，不在 `apps/` 下面。

职责：

- 定义跨 Web UI、Orchestrator、Runner 共享的数据模型、契约和校验规则。
- 提供测试点到执行步骤的编译能力。
- 承载 page object、case id、element binding、intent mapping、自愈建议、观测日志等共享逻辑。

关键文件：

- `schemas/contracts.py`：`PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1 / ExecutionRecordV1 / EvidenceManifestV1` 等契约。
- `schemas/models.py`：共享 Pydantic 模型。
- `schemas/validator.py`：`ContractValidator`。
- `execution_compiler.py`：测试点编译为可执行步骤的核心。
- `page_object_assets.py`：页面对象资产读取与解析。
- `case_ids.py`、`case_rules.py`：用例 ID 和用例规则。
- `observability/`：日志、request id、AI trace、subprocess 观测能力。
- `tests/`：共享契约和规则的单元/契约测试。

使用原则：

- 如果规则被两个以上模块依赖，应优先考虑放入 `shared_backend`。
- 不要在 Web UI、Orchestrator、Runner 里各自复制一套契约模型。
- 修改共享契约时，应同步跑 `shared_backend/tests` 和相关集成测试。

### `runners/web-playwright-python/`

当前成熟的 Web 自动化执行器。

职责：

- 读取 YAML 测试用例和 page object。
- 用 pytest + Playwright 执行 Web 自动化测试。
- 产出 Allure、截图、视频、trace、HTML、analysis 等证据。
- 提供 asset toolkit、schema 校验、YAML executor、运行工具链。

关键目录：

- `runner/`：YAML 加载、执行器、运行时逻辑。
- `pages/`：Page Object 相关 Python 封装。
- `actions/`：执行动作封装。
- `schemas/`：runner 侧 YAML schema。
- `tests/`：runner 契约、工具链、E2E 测试。
- `tools/`：Allure、URL 检查、资产 CLI 等工具。
- `artifacts/`：运行证据。
- `allure-results/`、`allure-report/`：Allure 原始结果和 HTML 报告。
- `fixtures/login-demo/`：本地登录 E2E demo。

使用原则：

- runner 负责执行，不负责重新设计测试点。
- runner schema 变更要考虑 `shared_backend.execution_compiler` 和用例中心 `script_code`。
- E2E 相关测试默认不应混入普通非 E2E 质量门。

### `assets/`

当前测试资产目录。

当前实际落地：

- `assets/page-objects/`：页面对象和元素资产。
- `assets/test-cases/`：测试用例资产。
  - `ai-generated/`：AI 生成用例。
  - `manual/`：人工维护用例。

说明：

- README 和规划文档里提到的 API 契约、业务流程、风险规则、测试数据模板等属于平台方向，不代表当前都已经有同等成熟的目录落地。
- 长期可复用资产应进入 `assets/` 或数据库，而不是散落在运行态目录。

---

## 2. 支撑目录

### `agents/`

AI Agent 子项目集合。

当前目录包括：

- `requirement-parser-agent`
- `test-design-agent`
- `script-generation-agent`
- `data-generation-agent`
- `execution-planner-agent`
- `failure-analysis-agent`
- `failure-triage-agent`
- `risk-evaluation-agent`
- `self-healing-advisor-agent`

说明：

- 目录名使用连字符，内部 Python 包通常使用下划线。
- Orchestrator 通过 Python path、subprocess 或服务封装调用这些能力。
- 不要把 Agent 目录误认为主 Web 服务入口。

### `reports/`

编排和执行报告目录。

当前重点：

- `reports/executions/`：Orchestrator 生成的 JSON / Markdown 执行报告。
- `reports/executions/generated-scripts/`：生成脚本相关报告产物。
- `reports/telemetry/`：遥测数据。

说明：

- `reports/` 是运行结果和分析结果，不是测试用例长期事实源。
- 报告展示通常由 Web UI 聚合读取。

### `web-ui/state/`

运行态状态与缓存目录。

当前包含：

- `preview-test-points/`
- `generated-cases/`
- `runs/`
- `reporting/`
- `test-points/`
- `default/`

说明：

- 这是运行态产物和兼容状态层。
- 新功能不应默认把长期业务真相写到这里。
- 如果数据需要审计、查询、关联和治理，优先进入数据库、`assets/` 或共享契约。

### `artifacts/`

跨模块运行产物目录。

当前包含：

- `page-object-imports/`
- `page-recorder/`

说明：

- 用于存放导入、录制、临时处理等过程产物。
- 不应替代业务模型或测试资产目录。

### `docs/`

项目知识库。

当前主要分层：

- `architecture/`：架构与目录说明。
- `core/`：核心规则、平台规则、DSL 方案、质量门、页面对象规则。
- `bugfixes/`：重要问题修复留档。
- `acceptance/`：验收记录。
- `pytest/`：pytest 配置、marker、命令说明。
- `page-object-governance/`：页面对象治理设计和阶段文档。
- `代码流程图/`、`代码评审/`：中文流程图和评审材料。
- `career/`：学习计划。

说明：

- README 负责项目入口。
- 本文档负责目录地图。
- 具体规则优先看 `docs/core/`。

---

## 3. 兼容、历史与基础设施目录

### `web-ui/`

历史兼容与运行态目录。

当前主要价值：

- 承载 `web-ui/state/` 运行态缓存。
- 保留部分历史入口或兼容产物。

原则：

- 不作为当前源码主入口。
- 新功能不建议继续堆在这里。

### `apps/web-console/`

历史 scaffold 控制台资源目录。

说明：

- 这是由 Orchestrator 托管的历史静态控制台资源。
- 不是当前 Workbench 主事实入口。
- 当前主 Web UI 在 `apps/web-ui-service/`。

### `legacy/`

历史代码和待清理目录。

当前包含：

- `deprecated/`
- `duplicate/`
- `unused/`

原则：

- 默认不要在这里新增功能。
- 需要参考历史实现时，只读理解后回到主链目录实现。

### `scripts/`

项目脚本目录。

常见分层：

- `scripts/qa/`：静态检查、页面检查、质量门脚本。
- `scripts/dev/`：本地开发服务启停。
- `scripts/docker/`：Docker 相关脚本。
- `scripts/ci/`：CI 辅助脚本。
- `scripts/tools/`：通用工具脚本。

### `infra/`、`deploy/`

基础设施和部署配置。

当前重点：

- `infra/nginx/`：Nginx 配置。
- `deploy/elk/`：ELK 日志链路配置。
- `docker-compose.yml`：本地/容器化系统拓扑。
- `docker-compose.override.yml`：开发环境 bind mount 和端口暴露。

### `.github/workflows/`

GitHub Actions 工作流。

用于 CI、镜像构建、部署等自动化流程。

### `skills/`

本地 Codex skill 目录。

当前包含：

- `skill-superpowers-implementation-guard/`

说明：

- 这是辅助 Codex 工作流的本地技能，不属于平台运行时代码。

---

## 4. 代码入口速查

### Web UI 主入口

```text
apps/web-ui-service/app/main.py
apps/web-ui-service/app/routers/
apps/web-ui-service/frontend/src/
```

### Workbench / AI 生成入口

```text
apps/web-ui-service/app/routers/workbench_generation.py
apps/web-ui-service/app/services/workbench_generation_api/
apps/web-ui-service/app/services/workbench_generation_api/orchestrator_client_factory.py
```

### Orchestrator `/orchestrate`

```text
apps/ai-orchestrator/src/app.py
apps/ai-orchestrator/src/orchestrator_service.py
apps/ai-orchestrator/src/services/orchestration_flow_support.py
```

### 共享契约与编译

```text
shared_backend/schemas/contracts.py
shared_backend/schemas/models.py
shared_backend/schemas/validator.py
shared_backend/execution_compiler.py
```

### Runner 执行

```text
runners/web-playwright-python/runner/
runners/web-playwright-python/schemas/
runners/web-playwright-python/tests/
```

### 用例中心唯一事实源

```text
apps/web-ui-service/app/models/test_case.py
apps/web-ui-service/app/services/test_case_service.py
apps/web-ui-service/app/services/test_case_mapper.py
runners/web-playwright-python/runner/yaml_loader.py
```

背景文档：

- `docs/bugfixes/2026-05-22_case_center_script_code_execution_chain_fix.md`
- `docs/代码流程图/2026-05-22_DSL_V1.1_script_code唯一事实源流程图与代码评审.md`

---

## 5. 新功能应该放哪里

| 需求类型 | 优先位置 |
| --- | --- |
| 新 Web 页面 | `apps/web-ui-service/frontend/src/` |
| 新 Web API | `apps/web-ui-service/app/routers/` + `apps/web-ui-service/app/services/` |
| Workbench 生成链路 | `apps/web-ui-service/app/services/workbench_generation_api/` |
| Orchestrator 编排能力 | `apps/ai-orchestrator/src/services/` |
| `/orchestrate` 主流程 | `apps/ai-orchestrator/src/services/orchestration_flow_support.py` |
| 共享 schema / 契约 | `shared_backend/schemas/` |
| 测试点到执行步骤编译 | `shared_backend/execution_compiler.py` |
| Runner YAML 执行 | `runners/web-playwright-python/runner/` |
| Runner schema | `runners/web-playwright-python/schemas/` |
| 页面对象资产 | `assets/page-objects/` 或 Web UI 页面对象表 |
| YAML 用例资产 | `assets/test-cases/` 或用例中心 DB |
| 运行报告 | `reports/executions/` |
| 临时运行态缓存 | `web-ui/state/` |
| 架构/规则文档 | `docs/architecture/` 或 `docs/core/` |

---

## 6. 不要轻易放到哪里

- 不要把新业务真相写进 `web-ui/state/`。
- 不要在 `legacy/` 里新增功能。
- 不要把当前 Workbench 主链放回 `apps/web-console/`。
- 不要在 Web UI、Orchestrator、Runner 各复制一份共享 schema。
- 不要让 `test_steps`、`source_ref YAML`、页面展示字段反向覆盖 `TestCase.script_code`。
- 不要把运行证据当成可复用测试资产。

---

## 7. 推荐阅读顺序

第一次理解项目：

1. `README.md`
2. `docs/architecture/project-structure.md`
3. `apps/web-ui-service/README.md`
4. `apps/ai-orchestrator/README.md`
5. `docs/pytest/README.md`

理解主链路：

1. `apps/web-ui-service/app/services/workbench_generation_api/orchestrator_client_factory.py`
2. `apps/ai-orchestrator/src/app.py`
3. `apps/ai-orchestrator/src/orchestrator_service.py`
4. `apps/ai-orchestrator/src/services/orchestration_flow_support.py`
5. `shared_backend/execution_compiler.py`
6. `runners/web-playwright-python/runner/`

理解用例中心与唯一事实源：

1. `docs/bugfixes/2026-05-22_case_center_script_code_execution_chain_fix.md`
2. `apps/web-ui-service/app/models/test_case.py`
3. `apps/web-ui-service/app/services/test_case_service.py`
4. `apps/web-ui-service/app/services/test_case_mapper.py`
5. `runners/web-playwright-python/runner/yaml_loader.py`

---

## 8. 当前仍需注意的结构风险

- 主链目录和历史兼容目录仍共存，新同学容易误把 `web-ui/` 或 `apps/web-console/` 当成主入口。
- `apps/web-ui-service` 中仍有聚合门面和部分历史兼容逻辑，改动前要先读调用链。
- `apps/ai-orchestrator` 的 HTTP 层是 Flask，而 `apps/web-ui-service` 是 FastAPI，不能混淆。
- `assets/` 里当前实际落地资产少于平台规划中的资产类型，写文档或代码时要区分“当前已实现”和“未来规划”。
- 运行态目录内容很多，但不代表它们都是长期事实源。

---

## 9. 维护原则

- 目录结构发生主链变化时，同步更新 `README.md` 和本文档。
- 新增跨模块契约时，优先更新 `shared_backend` 并补测试。
- 新增 API 时，补充对应 router/service 测试或集成测试。
- 新增 runner 行为时，同步考虑 YAML schema、执行器、用例中心展示和 `script_code` 唯一事实源。
- 新增文档时，放到最贴近用途的 `docs/` 子目录，避免散落到根目录。
