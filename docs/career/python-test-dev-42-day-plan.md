# Python 测试开发 42 天项目接管与面试冲刺计划

适用对象：已有自动化测试经验或测试基础，但存在约一年半空窗期；当前需要用 `ai-test-platform` 项目重新建立技术可信度，并以测试开发工程师 / Python 自动化测试工程师 / SDET 为主要求职方向。

计划开始日期可自行填写。建议每天投入 6-8 小时，至少保证 4 小时高质量学习与编码。

## 1. 总纲

### 1.1 求职定位

主定位：测试开发工程师。

辅助投递方向：

- Python 自动化测试工程师
- SDET
- QA Automation Engineer
- 测试平台开发工程师
- 测试效能工程师

不建议当前主投：

- 纯 Python 后端开发
- 算法工程师
- 高级架构师
- 纯 AI Agent 工程师

原因：当前项目的最大优势不是单点脚本能力，而是「测试资产 + AI 编排 + Runner 执行 + 报告证据 + 质量分析」的测试平台能力。测试开发岗位最能承接这个叙事。

### 1.2 面试核心叙事

建议统一使用以下表达：

> 这个项目的初版我使用 AI 作为结对编程工具完成，但我负责需求拆解、架构设计、模块验收、测试补齐和问题修复。现在我通过阅读源码、跑通测试、补充测试、追踪主链路和整理文档逐步接管项目。核心链路我能解释、能调试、能修改。

不要说：

- 代码都是 AI 写的，我还没怎么看
- 我只是让 AI 生成了一个项目
- 我还不确定里面怎么跑

要强调：

- 我能跑通
- 我能解释
- 我能定位
- 我能补测试
- 我能做小功能迭代

### 1.3 项目卖点

面试时优先讲 5 个点：

1. 平台不是单脚本，而是测试平台：需求、测试资产、执行、证据、报告、失败分析闭环。
2. AI 不是替代自动化，而是增强测试设计和失败归因。
3. 执行层保持确定性：pytest、Playwright、YAML 用例、Page Object、Allure。
4. 平台有工程化入口：Makefile、CI、静态检查、契约测试、集成测试。
5. 自己正在逐模块接管：从 orchestrator、runner、shared_backend、web-ui-service 逐步深入。

### 1.4 42 天目标

42 天后必须达到：

- 能 5 分钟讲清项目整体架构。
- 能 10 分钟讲清 `POST /orchestrate` 主链路。
- 能现场定位一个接口测试或 runner 测试。
- 能独立写 pytest fixture、参数化测试、异常路径测试。
- 能解释 Flask orchestrator 和 FastAPI web-ui-service 的职责边界。
- 能解释 YAML 用例如何进入 Playwright runner。
- 能解释 Allure / report / evidence 的作用。
- 能说清 AI 辅助代码如何被你接管。
- 至少完成 1 个小功能或 1 个可展示改进。
- 准备好 8-10 个项目深挖问答。

### 1.5 每日固定节奏

每天按这个格式执行和记录：

```text
1. 今日目标
2. 阅读文件
3. 跑通命令
4. 亲手编码或补测试
5. 面试口述沉淀
6. 今日卡点
```

建议每天新建：

```text
notes/day-XX.md
```

如果当天有代码练习：

```text
notes/dayXX_exercises.py
notes/test_dayXX_exercises.py
```

### 1.6 评价标准

每天结束前问自己：

- 我今天是否跑过命令？
- 我今天是否读过真实源码？
- 我今天是否亲手写过代码或测试？
- 我今天是否能产出一段面试表达？
- 我今天是否更能证明项目是我接管的？

如果 5 个问题里少于 4 个是「是」，当天任务不算完成。

## 2. 项目地图

重点目录：

```text
apps/ai-orchestrator/          Flask 编排服务，负责 AI Agent、Runner、报告链路
apps/web-ui-service/           FastAPI 主服务和 React 前端，负责平台控制台与业务数据
agents/                        测试设计、脚本生成、失败分析等 Agent
runners/web-playwright-python/ YAML 驱动的 Playwright 执行器
shared_backend/                共享契约、case_id、执行编译、观测性等底层能力
assets/                        测试资产：page objects、test cases
docs/                          架构、bugfix、验收、治理文档
code_explanations/             源码讲解，用于读不懂源码时辅助理解
```

主链路：

```text
需求 / PRD / OpenAPI / Git Diff
  -> ai-orchestrator
  -> test-design-agent
  -> 测试点 / YAML 用例
  -> shared_backend execution compiler
  -> web-playwright-python runner
  -> screenshot / log / trace / Allure / report
  -> 失败分析 / 质量门禁 / 回归建议
```

优先掌握的核心文件：

```text
README.md
Makefile
pytest.ini
apps/ai-orchestrator/src/app.py
apps/ai-orchestrator/src/orchestrator_service.py
apps/ai-orchestrator/src/services/agent_execution_support.py
apps/ai-orchestrator/src/services/runner_registry_support.py
apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py
shared_backend/case_ids.py
shared_backend/execution_compiler.py
shared_backend/observability/logging.py
apps/web-ui-service/app/main.py
apps/web-ui-service/tests/conftest.py
runners/web-playwright-python/conftest.py
```

## 3. 每周目标

### Week 1：项目跑通 + 主链路理解

目标：能讲清项目是什么、怎么跑、核心 API 怎么走。

验收：

- `make test-orchestrator` 可跑通或能解释失败原因。
- 完成架构图。
- 完成 `POST /orchestrate` 一页纸。
- 录制 5 分钟项目介绍。

### Week 2：Python + pytest 接管

目标：补齐 Python 和 pytest 基础，并能给项目补小测试。

验收：

- 手写不少于 10 个 Python 小函数。
- 为练习函数写 pytest。
- 给项目补 1-2 个真实测试。
- 能解释 fixture、marker、FakeService、异常映射。

### Week 3：Web UI Service + FastAPI + 数据模型

目标：理解平台业务服务层、路由、数据库、状态管理。

验收：

- 能讲清 FastAPI 服务如何组织。
- 能讲清 TestClient 测试怎么写。
- 能解释 models、schemas、services、routers 的分层。
- 能读懂一个 workbench API 的完整调用链。

### Week 4：Runner + Playwright + YAML 执行链

目标：理解自动化执行底座。

验收：

- 能讲清 YAML 用例、Page Object、Playwright runner 的关系。
- 能运行至少一个 runner 相关 contract test。
- 能解释 evidence、Allure、report summary 的作用。
- 能说明 e2e 为什么不默认进 PR CI。

### Week 5：完成一个可展示功能

目标：做一个小但完整的平台功能，作为面试展示证据。

推荐功能：

- `SkillRegistrySupport`：展示平台可用能力目录。
- `/skills` 接口：返回 browser、spreadsheet、pdf、docx 等能力目录。
- 为 `/skills` 补 integration test。
- README 增加 skill/capability 设计说明。

验收：

- 有代码变更。
- 有测试。
- 有文档。
- 能 demo。

### Week 6：简历、项目问答、模拟面试

目标：把技术能力转化成面试表达。

验收：

- 完成项目简历描述。
- 完成 10 个项目深挖问答。
- 完成 2 次录音或视频模拟面试。
- 准备好空窗期解释。
- 每天开始投递。

## 4. 每日任务

## D1：项目全景与架构理解

目标：30 分钟内能讲清这个平台做什么、主链路怎么走、代码分哪几块。

阅读：

- `README.md`
- `pytest.ini`
- `Makefile`
- `docs/bugfixes/2026-05-22_case_center_script_code_execution_chain_fix.md`
- `apps/ai-orchestrator/src/app.py` 中的 `def orchestrate`

命令：

```bash
pwd
rg --files | head -120
rg -n "def orchestrate|POST /orchestrate|test_post_orchestrate_returns_201" apps docs
```

产出：

- `notes/day-01.md`
- 手画一张架构图。
- 写 4 句话回答：这个平台解决什么痛点？

面试表达：

> 这个项目是一个 AI 自动化测试平台，核心是把需求输入转成测试点和 YAML 用例，再通过 Playwright runner 执行，并采集报告和失败证据。它不是单纯脚本，而是测试资产、执行编排、报告分析和质量门禁的闭环。

## D2：环境跑通与测试入口

目标：能跑通基础命令，并理解每个命令做什么。

阅读：

- `Makefile`
- `scripts/qa/run-static-baseline-fast.sh`
- `scripts/qa/run-static-baseline.sh`
- `.github/workflows/tests.yml`
- `requirements-dev.txt`

命令：

```bash
make install-dev
make static-baseline-fast
make test-orchestrator
make test-contracts
```

如果失败，记录：

- Python 版本
- 失败命令
- traceback
- 失败是环境问题、依赖问题、还是测试断言问题

产出：

- 命令执行表：命令、作用、是否通过、耗时、失败原因。
- 截图或复制关键输出到 `notes/day-02.md`。

面试表达：

> 项目有分层测试入口。`static-baseline-fast` 主要跑 ruff、JS 静态检查和 scoped mypy；`static-baseline` 会增加稳定 pytest；`test-orchestrator` 聚焦编排服务集成测试；E2E 不默认跑，因为需要真实浏览器和业务环境。

## D3：Python 基础回补：函数、类型、Path、dict

目标：结合项目源码补回 Python 常用语法。

阅读：

- `shared_backend/case_ids.py`
- `code_explanations/shared_backend/case_ids.py_explanation.md`
- `shared_backend/datetime_compat.py`
- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`

练习：

创建：

```text
notes/day03_exercises.py
notes/test_day03_exercises.py
```

实现并测试：

- `normalize_page_name(name: str) -> str`
- `build_case_id(project: str, page: str, seq: int) -> str`
- `merge_payload(base: dict, override: dict) -> dict`
- `safe_get(d: dict, *keys, default=None)`
- `read_yaml_steps(path: Path) -> list[str]`

命令：

```bash
.venv/bin/python -m pytest notes/test_day03_exercises.py -v
```

产出：

- 5 个函数。
- 对应 pytest。
- 笔记：`Path`、类型注解、`dict.get`、异常处理。

面试表达：

> 我不是孤立学习 Python，而是直接对照项目里的 case_id、Path、payload 合并和 YAML 读取来练习，这样能快速把语法迁移到项目维护里。

## D4：Python 进阶：异常、日志、request_id

目标：能读懂项目里的 logging、异常链和请求追踪。

阅读：

- `shared_backend/observability/logging.py`
- `code_explanations/shared_backend/observability/logging.py_explanation.md`
- `shared_backend/observability/ai_trace.py`
- `code_explanations/shared_backend/observability/ai_trace.py_explanation.md`
- `apps/web-ui-service/app/main.py`

命令：

```bash
.venv/bin/python -m pytest apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py::test_post_orchestrate_returns_201_and_payload -v -s
```

产出：

- 解释 `request_id` 用途。
- 解释为什么敏感字段要脱敏。
- 解释 `raise NewError(...) from exc` 的作用。

面试表达：

> 平台里 request_id 用于串联一次请求的日志、执行记录和异常定位。线上排查时，可以根据 request_id 从接口日志追到 runner 执行和报告生成。

## D5：pytest 入门与测试分层

目标：理解 contract、integration、e2e 的分层，能读懂 fixture 和 marker。

阅读：

- `pytest.ini`
- `apps/web-ui-service/tests/conftest.py`
- `runners/web-playwright-python/conftest.py`
- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`

命令：

```bash
.venv/bin/python -m pytest -m integration -q
.venv/bin/python -m pytest -m contract -q
.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_generation_api.py --setup-show -q
.venv/bin/python -m pytest -m e2e runners/web-playwright-python/tests --collect-only
```

产出：

- pytest 分层图。
- 写 5 句话解释为什么 PR CI 不默认跑 e2e。
- 写清 `yield fixture` 和 `return fixture` 区别。

面试表达：

> integration 测试验证模块协作，但通常用 Fake 或 Mock 隔离外部服务；e2e 测试验证真实用户链路，但依赖环境，所以不适合作为每次 PR 的默认阻塞项。

## D6：精读 orchestrate 请求响应

目标：闭卷说出 `POST /orchestrate` 的入参、出参、主流程。

阅读：

- `apps/ai-orchestrator/src/app.py`
- `apps/ai-orchestrator/src/orchestrator_service.py`
- `apps/ai-orchestrator/src/services/agent_execution_support.py`
- `apps/ai-orchestrator/src/services/runner_registry_support.py`
- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`

命令：

```bash
rg -n "def orchestrate|class FakeService|test_post_orchestrate_returns_201|generate_only|generate_and_run|RunnerExecutionError" apps/ai-orchestrator
```

产出：

- `POST /orchestrate` 一页纸。
- 写清 `execute=true` 和 `execute=false` 的差异。
- 写清 `mode=generate_only` 和 `mode=generate_and_run` 的差异。
- 写清 FakeService 为什么存在。

面试表达：

> `/orchestrate` 是编排入口。它接收需求、页面、执行模式和 runner 信息，先生成测试用例，再按 execute/mode 决定是否触发 runner，最后返回 case、execution_record、report 和报告路径。

## D7：第 1 周复盘与 5 分钟口述

目标：把阅读成果转成面试可表达内容。

任务：

- 不看笔记重画架构图。
- 录制 5 分钟项目介绍。
- 重跑 `make test-orchestrator`。
- 读 bugfix 文档里的根因分析。
- 预习 `shared_backend/execution_compiler.py`。

命令：

```bash
make test-orchestrator
```

产出：

- 架构图第 2 版。
- 5 分钟口述稿。
- `AI 代码接管证据清单`：
  - 我能解释的模块
  - 我能跑通的测试
  - 我亲手写过的测试
  - 我发现的问题
  - 我能现场改的小功能

面试表达：

> 我现在不是停留在读代码，而是通过跑测试、画链路、读 bugfix、补练习测试来接管项目。第一周我重点掌握了 orchestrator 的核心接口和测试分层。

## D8：Python 面向对象与服务类

目标：理解项目中 service class 的组织方式。

阅读：

- `apps/ai-orchestrator/src/orchestrator_service.py`
- `apps/ai-orchestrator/src/services/runner_registry_support.py`
- `apps/ai-orchestrator/src/services/agent_execution_support.py`

练习：

- 手写一个 `SimpleSkillRegistry` 类。
- 支持 `list_skills()` 和 `resolve_skill(name)`。
- 为它写 pytest。

命令：

```bash
.venv/bin/python -m pytest notes/test_day08_skill_registry.py -v
```

产出：

- 类、初始化参数、私有属性、异常处理笔记。

面试表达：

> 项目里的 service class 主要承担业务编排和能力封装，路由层只做参数解析和错误映射，复杂逻辑放到 service 层，方便测试。

## D9：pytest 参数化与边界用例

目标：掌握参数化测试和边界条件。

阅读：

- `shared_backend/tests/test_case_rules.py`
- `shared_backend/tests/test_contract_validator.py`
- `apps/ai-orchestrator/tests/integration/test_case_id_guardrails.py`

练习：

- 给 D8 的 `SimpleSkillRegistry` 增加参数化测试。
- 测试空字符串、大小写、未知 skill、默认 skill。

命令：

```bash
.venv/bin/python -m pytest notes/test_day08_skill_registry.py -v
```

产出：

- 参数化测试模板。
- 边界用例清单。

面试表达：

> 我写测试时会优先覆盖正常路径、边界输入和异常路径。参数化可以减少重复代码，同时让规则更清楚。

## D10：Mock / Fake / Stub 的区别

目标：理解为什么 orchestrator 测试用 FakeService。

阅读：

- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`
- `apps/ai-orchestrator/tests/integration/test_agent_execution_support_import.py`
- `apps/ai-orchestrator/tests/unit/test_requirement_parse_support.py`

任务：

- 总结 FakeService 提供了哪些方法。
- 解释它和真实 OrchestratorService 的关系。
- 写一个小 Fake 类练习。

命令：

```bash
rg -n "class FakeService|service\\.calls|error =" apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py
```

产出：

- Fake / Mock / Stub 对比表。

面试表达：

> FakeService 用来稳定接口层测试，避免每次测试依赖真实 LLM、真实 runner 或文件系统副作用。这样可以把 HTTP contract 和后端业务执行分开验证。

## D11：异常路径与 HTTP 错误映射

目标：掌握接口如何把内部异常映射成 HTTP 响应。

阅读：

- `apps/ai-orchestrator/src/app.py`
- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`
- `docs/core/error_response_rules.md`

任务：

- 找到 400、404、415、422、502 的测试。
- 为一个小练习接口写异常映射测试。

命令：

```bash
rg -n "400|404|415|422|502|ValidationError|RunnerExecutionError" apps/ai-orchestrator/src apps/ai-orchestrator/tests
```

产出：

- HTTP 错误码对照表。

面试表达：

> 接口层不能把内部异常原样抛给用户，需要稳定的错误格式。比如 runner 执行失败可以映射为 502，参数校验失败映射为 400 或 422。

## D12：shared_backend 契约与执行编译

目标：理解平台为什么需要共享契约层。

阅读：

- `shared_backend/execution_compiler.py`
- `code_explanations/shared_backend/execution_compiler.py_explanation.md`
- `shared_backend/schemas/contracts.py`
- `shared_backend/tests/test_execution_compiler_contract.py`
- `shared_backend/tests/test_pipeline_contract.py`

命令：

```bash
.venv/bin/python -m pytest shared_backend/tests/test_execution_compiler_contract.py shared_backend/tests/test_pipeline_contract.py -v
```

产出：

- 解释 execution compiler 的作用。
- 写清「唯一事实源」为什么重要。

面试表达：

> shared_backend 是平台的契约层，避免 web-ui、orchestrator、runner 各自理解一套数据结构。执行编译器的价值是把测试资产稳定转换成 runner 可执行的数据。

## D13：补一个真实项目测试

目标：从学习进入接管，给项目补一个小测试。

候选任务：

- 给 `RunnerRegistrySupport.resolve_runner_profile` 补未知 runner 测试。
- 给 `RunnerRegistrySupport.list_runners` 补返回副本测试。
- 给 `AgentExecutionSupport._allocate_case_id` 补边界测试。

命令：

```bash
.venv/bin/python -m pytest apps/ai-orchestrator/tests -q
```

产出：

- 至少 1 个项目内真实测试。
- 记录测试覆盖了什么风险。

面试表达：

> 我接管项目时会先从低风险、边界清晰的测试补起，例如 registry、case_id、异常路径，这样能快速建立对模块行为的信心。

## D14：第 2 周复盘

目标：巩固 Python + pytest + orchestrator。

任务：

- 重跑 Week 2 相关测试。
- 整理 10 个 pytest 面试问答。
- 录制 5 分钟：如何测试 `/orchestrate`。

命令：

```bash
make test-orchestrator
.venv/bin/python -m pytest shared_backend/tests -q
```

产出：

- Python 知识清单。
- pytest 知识清单。
- 接管证据第 2 版。

## D15：FastAPI 服务入口

目标：理解 web-ui-service 为什么用 FastAPI。

阅读：

- `apps/web-ui-service/app/main.py`
- `apps/web-ui-service/app/routers/health.py`
- `apps/web-ui-service/tests/conftest.py`
- `code_explanations/apps/web-ui-service/app/core/config.py_explanation.md`

命令：

```bash
rg -n "FastAPI\\(|include_router|@app.middleware|Depends|get_current_user" apps/web-ui-service/app
```

产出：

- FastAPI app 启动流程图。
- middleware、router、dependency 说明。

面试表达：

> web-ui-service 是平台主服务，负责控制台、项目、用例、任务和报告等业务 API。FastAPI 适合做结构化 API，TestClient 也方便写接口测试。

## D16：SQLAlchemy models 与 Alembic

目标：理解数据表和迁移。

阅读：

- `apps/web-ui-service/app/core/database.py`
- `apps/web-ui-service/app/models/test_case.py`
- `apps/web-ui-service/app/models/test_project.py`
- `apps/web-ui-service/migrations/versions/*.py`

命令：

```bash
rg -n "class .*\\(Base\\)|Column|relationship|ForeignKey|alembic" apps/web-ui-service/app apps/web-ui-service/migrations
```

产出：

- models 与 migrations 对照表。
- 解释 Alembic 的作用。

面试表达：

> 测试平台不是只跑脚本，还要管理测试资产和执行状态，所以需要数据库模型和迁移管理。Alembic 保证表结构演进可追踪。

## D17：Router / Schema / Service 分层

目标：能追踪一个 FastAPI 接口从 router 到 service。

阅读：

- `apps/web-ui-service/app/routers/test_cases.py`
- `apps/web-ui-service/app/schemas/test_case.py`
- `apps/web-ui-service/app/services/test_case_service.py`
- `apps/web-ui-service/tests/integration/test_test_case_tree_api.py`

命令：

```bash
rg -n "router\\.|def .*test_case|TestCase" apps/web-ui-service/app/routers apps/web-ui-service/app/services apps/web-ui-service/app/schemas
```

产出：

- 画出 test case API 调用链。
- 写清 schema 和 model 的区别。

面试表达：

> router 负责 HTTP 入参出参，schema 负责 API 数据结构，model 负责数据库映射，service 负责业务逻辑。这样的分层利于测试和维护。

## D18：Workbench 生成链路

目标：理解前端工作台如何触发生成。

阅读：

- `apps/web-ui-service/app/routers/workbench_generation.py`
- `apps/web-ui-service/app/services/workbench_generation_service.py`
- `apps/web-ui-service/app/services/workbench_orchestrator_service.py`
- `apps/web-ui-service/tests/integration/test_workbench_generation_api.py`

命令：

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_generation_api.py -v
```

产出：

- workbench generation 链路图。
- 解释 web-ui-service 与 ai-orchestrator 如何协作。

## D19：任务状态与执行记录

目标：理解平台如何表示任务状态。

阅读：

- `apps/web-ui-service/app/services/workbench_task_service.py`
- `apps/web-ui-service/app/models/orchestration_task.py`
- `apps/web-ui-service/tests/integration/test_workbench_tasks_api.py`
- `shared_backend/state_machines.py`

命令：

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_tasks_api.py -v
```

产出：

- 任务状态流转图。
- 解释为什么测试平台需要状态机。

## D20：报告与质量门禁

目标：理解报告和 gate。

阅读：

- `apps/web-ui-service/app/services/workbench_reporting_service.py`
- `apps/web-ui-service/app/services/workbench_gate_service.py`
- `apps/web-ui-service/app/routers/workbench_reporting.py`
- `apps/web-ui-service/app/routers/workbench_gate.py`
- `docs/core/quality_gate_rules.md`

命令：

```bash
rg -n "gate|quality|report|allure|summary" apps/web-ui-service/app docs/core
```

产出：

- 质量门禁规则笔记。
- 面试回答：什么情况下不允许发布？

## D21：第 3 周复盘

目标：能讲清 web-ui-service。

任务：

- 录制 8 分钟：FastAPI 服务架构。
- 整理 models / schemas / routers / services 对比表。
- 跑 web-ui-service 重点测试。

命令：

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_generation_api.py apps/web-ui-service/tests/integration/test_workbench_tasks_api.py -v
```

产出：

- Web UI Service 一页纸。
- FastAPI 面试问答 10 个。

## D22：Playwright runner 总览

目标：理解 runner 是确定性执行底座。

阅读：

- `runners/web-playwright-python/README.md` 如果存在
- `runners/web-playwright-python/conftest.py`
- `runners/web-playwright-python/tests/test_asset_contracts.py`
- `runners/web-playwright-python/pages/login_page.py`
- `assets/page-objects/web/login.page-object.yaml`

命令：

```bash
make test-runner-assets
```

产出：

- Page Object 与 YAML 资产关系图。

面试表达：

> AI 生成的是测试设计和用例草稿，真正执行依赖 Playwright runner。这样既能利用 AI 提效，又能保证执行层稳定和可回归。

## D23：YAML 测试用例结构

目标：能手写一个 YAML 测试用例并解释字段。

阅读：

- `assets/test-cases/ai-generated/*.yaml`
- `shared_backend/schemas/contracts.py`
- `runners/web-playwright-python/tests/test_asset_contracts.py`

任务：

- 选择一个 YAML 用例逐字段解释。
- 手写一个登录失败提示用例草稿。

命令：

```bash
rg -n "steps:|expected|page|case_id|script_code" assets shared_backend runners
```

产出：

- YAML 字段说明表。

## D24：Page Object 与定位器治理

目标：理解页面对象治理。

阅读：

- `docs/page-object-governance/README.md`
- `assets/page-objects/web/login.page-object.yaml`
- `shared_backend/page_object_assets.py`
- `apps/web-ui-service/app/services/page_object_service.py`

命令：

```bash
rg -n "page_object|selector|data-testid|locator|element" docs assets shared_backend apps/web-ui-service/app/services
```

产出：

- 定位器稳定性原则。
- 面试回答：如何降低 UI 自动化 flaky？

## D25：Evidence / Allure / report summary

目标：理解执行证据如何支持失败分析。

阅读：

- `runners/web-playwright-python/tools/manage_allure.py`
- `runners/web-playwright-python/tools/check_base_url.py`
- `runners/web-playwright-python/tests/test_manage_allure.py`
- `runners/web-playwright-python/tests/test_report_summary.py`
- `apps/ai-orchestrator/src/services/execution_report_support.py`

命令：

```bash
.venv/bin/python -m pytest runners/web-playwright-python/tests/test_manage_allure.py runners/web-playwright-python/tests/test_report_summary.py -v
make allure-info
```

产出：

- 证据类型清单：截图、日志、trace、video、analysis、Allure。

## D26：失败分析与自愈建议

目标：理解失败归因模块。

阅读：

- `apps/ai-orchestrator/src/services/failure_healing_support.py`
- `agents/failure-analysis-agent/analyze.py`
- `agents/failure-analysis-agent/test_analyze.py`
- `shared_backend/self_healing.py`

命令：

```bash
rg -n "failure|healing|triage|self_healing|suggestion" apps agents shared_backend
```

产出：

- 失败类型分类表。
- 自愈建议的边界：建议可以给，但不应盲目自动修改。

## D27：真实 E2E 与环境依赖

目标：知道如何跑真实浏览器测试，以及为什么它容易受环境影响。

阅读：

- `Makefile` 中 `test-e2e*` 目标。
- `runners/web-playwright-python/tools/check_base_url.py`
- `runners/web-playwright-python/tools/run_login_e2e_demo.py`

命令：

```bash
make test-e2e-login-demo
```

如果失败，记录是否缺 Playwright browser：

```bash
.venv/bin/python -m playwright install
```

产出：

- E2E 环境依赖清单。
- 面试回答：如何处理 flaky 和环境不稳定？

## D28：第 4 周复盘

目标：能讲清 runner 执行链路。

任务：

- 录制 8 分钟：YAML 到 Playwright 执行。
- 重跑 runner asset 测试。
- 整理 E2E / integration / contract 区别。

命令：

```bash
make test-runner-assets
make test-orchestrator
```

产出：

- Runner 一页纸。
- Playwright 面试问答 10 个。

## D29：可展示功能设计：Skill Registry

目标：设计一个小功能，把 Codex skill 思路转成平台 capability 目录。

设计：

```text
GET /skills
返回平台可用能力：
- browser_ui_test
- spreadsheet_report
- pdf_validate
- docx_validate
- pptx_validate
- openai_api_test_design
```

阅读：

- `apps/ai-orchestrator/src/services/runner_registry_support.py`
- `apps/ai-orchestrator/src/app.py`
- `apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py`

产出：

- `docs/core/skill_registry_design.md` 草稿。
- 接口响应 JSON 示例。

## D30：实现 SkillRegistrySupport

目标：完成服务类。

任务：

- 新增 `apps/ai-orchestrator/src/services/skill_registry_support.py`
- 实现 `list_skills()`
- 实现 `resolve_skill_profile(skill)`
- 不接真实执行，只做 catalog。

测试：

- 新增 unit 或 integration test。
- 测试返回副本。
- 测试未知 skill 抛错。

命令：

```bash
.venv/bin/python -m pytest apps/ai-orchestrator/tests -q
```

产出：

- 代码 + 测试。

## D31：新增 `/skills` API

目标：把 SkillRegistry 接入 orchestrator HTTP 层。

任务：

- 在 `app.py` 增加 `GET /skills`
- 返回 `items` 和 `default_skill`
- 错误格式沿用项目现有风格。

测试：

- 在 `test_orchestrate_endpoint.py` 或新测试文件里补 `test_get_skill_catalog_returns_200`。

命令：

```bash
.venv/bin/python -m pytest apps/ai-orchestrator/tests/integration -q
```

产出：

- 可展示接口。

## D32：文档和 README 更新

目标：让功能可以被面试官快速理解。

任务：

- 更新 `apps/ai-orchestrator/README.md`
- 增加 `/skills` 说明。
- 增加 skill/capability 设计说明。

命令：

```bash
make test-orchestrator
```

产出：

- 文档变更。
- 接口示例。

## D33：代码质量检查与修复

目标：保证新增功能通过质量门。

命令：

```bash
make static-baseline-fast
make test-orchestrator
```

任务：

- 修 ruff。
- 修 mypy 可控问题。
- 修测试失败。
- 记录未解决问题。

产出：

- 功能验收表。

## D34：功能 Demo 准备

目标：把小功能变成面试展示。

任务：

- 写 3 分钟 demo 讲稿。
- 准备 curl 示例。
- 准备“为什么做 skill registry”的回答。

示例讲法：

> 我把 Codex skill 的概念抽象成平台 capability catalog。这样平台不依赖某个 AI 工具运行时，而是把 browser、pdf、spreadsheet 等能力作为可注册、可展示、可编排的测试能力。

产出：

- Demo 讲稿。
- curl 示例。

## D35：第 5 周复盘

目标：完成一个可展示、可测试、可解释的小功能。

任务：

- 重跑相关测试。
- 录屏或录音 demo。
- 总结这次改动的设计、实现、测试、风险。

命令：

```bash
make static-baseline-fast
make test-orchestrator
```

产出：

- 项目接管证据第 3 版。

## D36：简历项目描述

目标：把项目写进简历。

任务：

写 3 个版本：

1. 2 行短版。
2. 5 行标准版。
3. 面试展开版。

推荐标准版：

```text
AI 自动化测试平台 | Python / Pytest / Playwright / Flask / FastAPI
- 设计并接管 AI 测试编排链路，支持从自然语言需求生成测试点与 YAML 用例。
- 基于 pytest + Playwright runner 执行 Web 自动化测试，采集截图、日志、Allure 报告等证据。
- 建立测试资产中心，管理 page object、test case、执行记录和报告摘要。
- 补充 orchestrator、runner、shared_backend 等模块的 contract/integration 测试，提升链路稳定性。
```

产出：

- 简历项目经历。
- 技术关键词表。

## D37：空窗期解释与 AI 代码解释

目标：处理面试敏感问题。

准备答案：

问题 1：空窗期一年半在做什么？

建议：

> 这段时间我主要在调整职业方向和补测试开发能力。最近我用这个 AI 自动化测试平台作为主项目，系统性补 Python、pytest、Playwright、FastAPI 和测试平台架构，并把 AI 辅助生成的初版代码逐步接管，形成可运行、可测试、可展示的项目。

问题 2：代码是不是 AI 写的？

建议：

> 初版确实大量使用 AI 辅助，但我不把它当成最终交付。我做了源码阅读、测试跑通、架构梳理、补测试和小功能迭代。面试时我可以现场解释核心链路，也可以现场改一个小功能或补一个测试。

产出：

- 敏感问题回答稿。
- 录音 2 遍。

## D38：Python 面试专项

目标：补常见 Python 面试题。

主题：

- list / tuple / dict / set
- 深拷贝 / 浅拷贝
- 生成器
- 装饰器
- 上下文管理器
- 异常链
- dataclass
- typing
- pathlib
- subprocess

任务：

- 每个主题写一个项目中的例子。
- 每个主题写一句面试回答。

产出：

- Python 面试问答 20 个。

## D39：pytest / 自动化测试专项

目标：准备测试开发高频问题。

主题：

- fixture
- marker
- parametrize
- mock / fake
- contract / integration / e2e
- flaky test
- Page Object
- 测试数据管理
- CI 中测试分层
- Allure 报告

任务：

- 每个主题都关联项目中的一个文件。

产出：

- pytest / 自动化测试面试问答 20 个。

## D40：平台设计专项

目标：准备项目深挖。

准备 10 个问题：

1. 为什么要做 ai-orchestrator？
2. 为什么 web-ui-service 和 ai-orchestrator 分开？
3. 为什么用 YAML 作为测试用例资产？
4. 为什么 runner 要保持确定性？
5. 如何降低 UI 自动化 flaky？
6. 如何设计测试资产中心？
7. 如何做失败归因？
8. 如何做质量门禁？
9. 如果并发执行 1000 条用例，怎么改？
10. 如果让你重构这个项目，你先改哪里？

产出：

- 项目深挖问答 10 个。
- 每个问题回答 1-2 分钟。

## D41：模拟面试 1

目标：模拟一轮技术面。

流程：

1. 3 分钟自我介绍。
2. 5 分钟项目介绍。
3. 10 分钟 orchestrate 链路。
4. 10 分钟 pytest / Playwright。
5. 10 分钟 Python 基础。
6. 5 分钟空窗期解释。

任务：

- 录音。
- 标记卡顿问题。
- 当天补齐 3 个薄弱点。

产出：

- 模拟面试复盘。

## D42：模拟面试 2 + 投递准备

目标：正式进入投递状态。

任务：

- 再做一次模拟面试。
- 准备 GitHub/本地 demo 路径。
- 准备项目截图或录屏。
- 整理简历最终版。
- 建立投递表。

投递表字段：

```text
公司
岗位
JD 关键词
投递日期
状态
面试时间
被问问题
复盘
```

产出：

- 简历最终版。
- 项目 demo 讲稿。
- 投递表。
- 下一阶段计划。

## 5. 面试速记

### 5.1 30 秒项目介绍

> 我做的是一个 AI 自动化测试平台，目标是把需求、PRD、OpenAPI 等输入转成测试点和可执行测试资产。平台由 Flask 编排服务、FastAPI 控制台服务、pytest/Playwright runner、shared_backend 契约层和测试资产目录组成。AI 负责提升测试设计和失败分析效率，执行层保持确定性，最终产出报告、证据和质量门禁结果。

### 5.2 1 分钟项目介绍

> 这个项目解决的是企业测试中需求到自动化执行链路割裂的问题。用户输入需求后，ai-orchestrator 会调用测试设计能力生成测试点和 YAML 用例，然后通过 shared_backend 的契约和执行编译层，把用例交给 Playwright runner 执行。执行过程中会收集 screenshot、日志、Allure 报告和失败分析结果。web-ui-service 负责平台控制台、测试资产、任务状态和报告展示。我的重点是接管这条主链路，补测试、跑 CI、理解异常路径，并做能力目录扩展。

### 5.3 空窗期回答

> 空窗期里我重新调整了职业方向，把重点放到 Python 测试开发和测试平台能力上。最近我集中用这个 AI 自动化测试平台作为主项目，补齐 pytest、Playwright、FastAPI、Flask、CI 和测试资产管理能力。这个项目初版有 AI 辅助，但我通过阅读源码、跑通测试、补充测试、整理架构图和实现小功能逐步接管，现在核心链路我可以独立讲解和修改。

### 5.4 AI 辅助代码回答

> 我把 AI 当成结对编程和脚手架生成工具，而不是替代工程判断。真正进入面试和工作场景时，关键是能不能解释、测试、调试和维护。我现在做的事情就是把 AI 辅助生成的代码转化成自己真正理解和能负责的代码。

## 6. 每周验收清单

Week 1：

- [ ] 架构图
- [ ] `POST /orchestrate` 一页纸
- [ ] `make test-orchestrator` 结果
- [ ] 5 分钟项目介绍录音

Week 2：

- [ ] Python 练习函数
- [ ] 练习 pytest
- [ ] 至少 1 个项目真实测试
- [ ] pytest 面试问答

Week 3：

- [ ] FastAPI 服务架构图
- [ ] web-ui-service 一页纸
- [ ] models/schemas/routers/services 对比表

Week 4：

- [ ] Runner 执行链路图
- [ ] YAML 字段说明
- [ ] Playwright 面试问答

Week 5：

- [ ] Skill Registry 或同等小功能
- [ ] 对应测试
- [ ] README / docs 更新
- [ ] demo 讲稿

Week 6：

- [ ] 简历项目描述
- [ ] 空窗期回答
- [ ] AI 辅助代码回答
- [ ] 项目深挖问答
- [ ] 两次模拟面试
- [ ] 投递表

## 7. 下一阶段

42 天后，如果已经开始面试，继续按面试反馈补短板。

如果还没有面试机会，优先做三件事：

1. 增强项目展示：README、截图、接口 demo、架构图。
2. 增强真实改动：每周至少 2 个小 PR 或提交。
3. 扩大投递范围：测试开发、Python 自动化、SDET、测试平台、质量效能同时投。

最终目标不是证明这个项目从第一行代码都是你手写的，而是证明你已经拥有它：能解释、能运行、能测试、能修复、能迭代。
