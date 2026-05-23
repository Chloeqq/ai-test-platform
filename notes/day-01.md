# D1 项目全景与架构理解

日期：2026-05-23

## 今日目标

30 分钟内能讲清：

1. 这个平台解决什么问题。
2. 主链路怎么走。
3. 代码分成哪几块。
4. `POST /orchestrate` 在哪里。

## 今日已跑命令

```bash
pwd
rg --files | head -120
rg -n "def orchestrate|POST /orchestrate|test_post_orchestrate_returns_201" apps docs README.md
```

关键定位结果：

```text
apps/ai-orchestrator/src/app.py
  Flask HTTP 入口，包含 POST /orchestrate 路由。

apps/ai-orchestrator/src/orchestrator_service.py
  真实编排服务，包含 OrchestratorService.orchestrate。

apps/ai-orchestrator/src/services/orchestration_flow_support.py
  编排流程支撑，包含 orchestrate 流程方法。

apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py
  /orchestrate 集成测试，包含 FakeService 和基础接口断言。

apps/ai-orchestrator/README.md
  orchestrator 服务接口说明。

docs/bugfixes/2026-05-22_case_center_script_code_execution_chain_fix.md
  script_code 到 runner 执行链路的 bugfix 记录，是面试时讲工程问题的好材料。
```

## 今日必读文件

### 1. README.md

重点：

- 平台不是单点测试脚本，而是企业级 AI 自动化测试平台。
- 核心能力包括：
  - 确定性自动化测试底座
  - AI 测试点生成
  - AI 脚本生成
  - AI 失败归因
  - 智能回归推荐
  - 质量分析与发布门禁

我自己的理解：

```text
TODO: 用自己的话写 4 句话，说明这个平台解决什么痛点。
```

### 2. pytest.ini

重点：

- `testpaths` 决定默认 pytest 会收集哪些测试。
- `markers` 定义测试分层：
  - `contract`
  - `integration`
  - `e2e`
  - `smoke`
  - `generated`

我自己的理解：

```text
TODO: 写清 integration 和 e2e 的区别。
```

### 3. Makefile

重点：

- `make test` 当前等价于 `make test-contracts`。
- `make test-orchestrator` 跑 ai-orchestrator 的 integration 测试。
- `make test-runner-assets` 跑 runner 资产契约测试。
- `make static-baseline-fast` 跑 ruff、JS 静态检查和 scoped mypy，不跑 pytest。
- `make static-baseline` 在 fast 基础上增加稳定 pytest 和架构检查。

我自己的理解：

```text
TODO: 写一张命令表：命令 / 作用 / 面试时怎么解释。
```

### 4. bugfix 文档

文件：

```text
docs/bugfixes/2026-05-22_case_center_script_code_execution_chain_fix.md
```

重点：

- 这份文档说明项目不是玩具代码，已经出现过真实链路问题。
- 核心问题是 `script_code -> test_steps -> 页面展示 -> runner 执行` 链路不一致。
- 重要概念：唯一事实源。

5 个根因：

```text
1. 唯一事实源倒挂
2. 脚本更新不刷新展示投影
3. 详情 mapper 优先读取旧文件
4. runtime YAML 被 runner 白名单拒绝
5. runner schema 与当前 YAML 脱节
```

我自己的理解：

```text
TODO: 每个根因用 2 句话解释。
```

## 今日架构图草稿

先用文本版，后面可以手画或用 Mermaid。

```text
需求 / PRD / OpenAPI / Git Diff / 缺陷单
  -> AI Orchestrator
  -> Test Design Agent
  -> 测试点 / YAML 用例 / script_code
  -> shared_backend execution compiler
  -> Playwright Runner
  -> screenshot / log / trace / Allure / report
  -> 失败分析 / 质量门禁 / 回归建议
```

核心目录：

```text
apps/web-ui-service
  FastAPI 主服务 + React 前端，负责平台控制台、测试资产、任务和报告展示。

apps/ai-orchestrator
  Flask 编排服务，负责需求解析、用例生成、runner 调度和报告聚合。

agents
  AI Agent 目录，例如 test-design、script-generation、failure-analysis。

runners/web-playwright-python
  Playwright 执行器，负责把 YAML 用例真正跑起来。

shared_backend
  共享契约、case_id、执行编译、状态机、观测性等基础能力。

assets
  测试资产，包括 page objects 和 test cases。

docs
  架构设计、bugfix 留档、验收文档。

code_explanations
  源码讲解，用来辅助接管 AI 辅助生成的代码。
```

## POST /orchestrate 初步定位

今天只做定位，不要求完全读懂。

```text
HTTP 路由入口：
apps/ai-orchestrator/src/app.py -> def orchestrate()

真实业务入口：
apps/ai-orchestrator/src/orchestrator_service.py -> OrchestratorService.orchestrate()

流程支撑：
apps/ai-orchestrator/src/services/orchestration_flow_support.py -> orchestrate()

集成测试：
apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py
```

第一层代码观察：

```text
1. app.py 的 def orchestrate() 是 HTTP 路由入口。
2. 它先读取 JSON payload。
3. 然后解析 mode 和 execute。
4. 再把 requirement、page、source、runner、input_sources 等字段组装成 orchestrate_kwargs。
5. 真正业务逻辑交给 orchestrator_service.orchestrate(**orchestrate_kwargs)。
6. 返回前通过 orchestrator_service.serialize_result(result) 转成 JSON 响应。
```

这说明：

```text
路由层很薄，主要负责 HTTP 入参、默认值、错误映射和响应。
业务编排放在 OrchestratorService 和 orchestration_flow_support。
测试里用 FakeService 替代真实 service，目的是稳定验证 HTTP contract。
```

我的问题：

```text
TODO: 写下现在还不懂的 3 个问题。
1.
2.
3.
```

## 今日面试表达草稿

先背这个版本，后面每天迭代：

> 这个项目是一个 AI 自动化测试平台，目标是打通从需求输入到测试执行和质量报告的链路。平台底层用 pytest 和 Playwright 做确定性执行，上层用 AI 辅助生成测试点、测试用例和失败分析。`ai-orchestrator` 负责编排 AI Agent 和 runner，`web-ui-service` 负责控制台、资产和任务管理，`shared_backend` 负责共享契约与执行编译。我的接管路径是先跑通测试，再从 `/orchestrate` 主链路开始读代码，逐步补测试和做小功能。

## D1 自测题

完成今天学习后闭卷回答：

1. 这个平台解决什么痛点？
2. 「确定性底座 + AI 增强」分别指什么？
3. `apps/web-ui-service` 和 `apps/ai-orchestrator` 分别负责什么？
4. `shared_backend` 为什么存在？
5. `runner` 是什么？
6. `assets` 目录存什么？
7. `pytest.ini` 里的 marker 有哪些？
8. `make test-orchestrator` 跑什么？
9. `POST /orchestrate` 的入口文件在哪？
10. bugfix 文档里的「唯一事实源」是什么意思？

## 今日完成标准

- [ ] 读完 `README.md` 架构和测试入口部分。
- [ ] 读完 `pytest.ini`。
- [ ] 读完 `Makefile` 前 120 行。
- [ ] 读完 bugfix 文档前 120 行。
- [ ] 能画出主链路。
- [ ] 能口述 3 分钟项目介绍。
- [ ] 写下 3 个还不懂的问题。
