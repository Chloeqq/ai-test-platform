# AI Test Platform

企业级 AI 自动化测试平台。

本项目用于构建一个面向企业研发测试场景的 **AI 自动化测试平台**，目标是实现：

- 确定性自动化测试底座
- AI 测试点生成
- AI 脚本生成
- AI 失败归因
- 智能回归推荐
- 质量分析与发布门禁

---

## 1. 项目目标

AI Test Platform 不是一个单点测试工具，而是一个完整的平台型项目。  
它面向以下核心场景：

- 根据 PRD / 原型图 / OpenAPI 自动生成测试点
- 基于测试点生成 Playwright / API / Appium 脚本草稿
- 自动执行 Web / API / Mobile 测试
- 采集 trace / screenshot / video / logs 等证据
- 对失败进行聚类、归因与风险分析
- 为回归范围选择和发布决策提供支持

---

## 2. 平台定位

本平台采用：

**确定性自动化底座 + AI 增强能力 + 质量数据闭环 + 发布治理**

其中：

- **确定性底座**：Playwright / API / Appium 等自动化执行能力
- **AI 增强**：需求解析、测试设计、脚本生成、失败归因、风险评估
- **数据闭环**：证据采集、质量分析、趋势与稳定性指标
- **发布治理**：PR 门禁、冒烟门禁、回归门禁、风险放行建议

---

## 3. 当前阶段

当前项目处于 **0-1 初始化阶段**，已经完成：

- 项目目录结构初始化
- 平台模块分层设计
- AI Agent 分工设计
- Runner / Asset / Evidence / Analytics 基础目录规划

当前优先事项：

1. 完善项目 README 与基础文档
2. 搭建 Web 自动化底座（Playwright）
3. 搭建 AI Orchestrator 基础骨架
4. 建立首批测试资产模板
5. 跑通第一条 smoke 用例

---

## 4. 总体架构

```text
输入源层
PRD / Swagger / Git Diff / 缺陷单 / 线上日志

↓
测试资产中心
用例库 / 页面对象 / API契约 / 数据模板 / 标签体系

↓
AI 编排层
需求解析Agent / 测试设计Agent / 脚本生成Agent / 失败归因Agent / 风险评估Agent

↓
自动化执行层
Web / API / Mobile

↓
执行与调度中心
CI/CD / 并发调度 / 环境分配 / 重试策略

↓
证据采集层
Trace / Screenshot / Video / Console / Network / Logs

↓
质量分析与洞察层
Flaky分析 / 失败聚类 / 趋势分析 / 风险评分

↓
发布决策与治理层
PR门禁 / 冒烟门禁 / 回归门禁 / 风险放行建议

↓
基础设施层
Docker / K8s / 配置 / 存储 / 队列 / 监控
```

## 5. 当前可用测试入口

先在根目录初始化 Python 开发环境：

```bash
make install-dev
```

如果希望在提交前自动校验测试资产，再执行：

```bash
make install-hooks
```

然后执行统一测试入口：

```bash
make test
```

如果要在提交前执行当前稳定的静态质量门（`ruff + mypy + pytest` 组合），执行：

```bash
make static-baseline
```

如果只需要快速跑静态检查（不跑 `pytest`），执行：

```bash
make static-baseline-fast
```

也可以直接在根目录执行：

```bash
.venv/bin/python -m pytest
```

按标记筛选时可使用：

```bash
.venv/bin/python -m pytest -m "contract or integration"
.venv/bin/python -m pytest -m e2e runners/web-playwright-python/tests
.venv/bin/python -m pytest -m "e2e and smoke" runners/web-playwright-python/tests
.venv/bin/python -m pytest -m "e2e and generated" runners/web-playwright-python/tests
```

或按类型分别执行：

```bash
make test-orchestrator
make test-runner-assets
make check-console
make static-baseline-fast
make static-baseline
make test-e2e-generated-allure
make allure-info
make allure-summary
make allure-generate
make allure-open
```

说明：

- `make test-orchestrator` 会跑 `apps/ai-orchestrator` 的 `POST /orchestrate` pytest 集成测试
- `make test-runner-assets` 会跑 `web-playwright-python` 的 page object / test case 资产契约测试
- `make check-console` 会对 `apps/web-console/static/app.js` 做 Node 语法检查
- `make static-baseline-fast` 会执行静态基线脚本 [scripts/qa/run-static-baseline-fast.sh](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/qa/run-static-baseline-fast.sh)
- `make static-baseline` 会执行跨模块静态基线脚本 [scripts/qa/run-static-baseline.sh](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/qa/run-static-baseline.sh)
  - 当前质量门范围：`ruff check apps agents runners` + scoped `mypy`（agents 稳定子集 + runners 工具链 `manage_allure/check_base_url`）+ `pytest -q agents` + `runners` 工具链稳定测试集 + `ai-orchestrator` OpenAPI 合约测试
- `make test-e2e` 会跑需要真实业务环境的浏览器端到端测试
- `make test-e2e-smoke` 会跑人工维护的 smoke 浏览器测试
- `make test-e2e-generated` 会跑 AI 生成的 YAML 浏览器测试
- `make test-e2e-generated-allure` 会跑 AI 生成的 YAML 浏览器测试并输出 `allure-results`
- `make allure-info` 会显示 Allure CLI 和结果目录/报告目录
- `make allure-summary` 会从 `artifacts/**/analysis.txt` 生成 `report_summary.txt`
- `make allure-generate` 会从 `allure-results` 生成 HTML 报告
- `make allure-open` 会打开 HTML 报告
- 当前命令依赖根目录 `.venv`，依赖清单见 [requirements-dev.txt](/Users/bettyhuang/PycharmProjects/ai-test-platform/requirements-dev.txt)
- 当前这套入口面向非 E2E 校验；真正跑 Playwright 页面测试时仍需要额外执行 `playwright install`
- 根级 [pytest.ini](/Users/bettyhuang/PycharmProjects/ai-test-platform/pytest.ini) 默认只收集当前稳定的非 E2E 测试，不会直接跑业务页面 smoke 用例
- 提交前资产校验配置见 [`.pre-commit-config.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/.pre-commit-config.yaml)

## 6. CI 分阶段策略

当前仓库已启用 GitHub Actions 工作流：

- [tests.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/tests.yml)
- [build-image.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/build-image.yml)
- [deploy-staging.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/deploy-staging.yml)

当前策略：

- `pull_request` / `push`
  - 默认跑 `static-baseline`（`ruff + scoped mypy + pytest`）
- `workflow_dispatch`
  - 可手动选择：
    - `static-baseline`
    - `e2e-smoke`
    - `e2e-generated`
    - `all`

手动跑 E2E 时，CI 需要以下 GitHub Secrets：

- `BASE_URL`
- `TEST_USERNAME`
- `TEST_PASSWORD`

Staging 发布所需 Secrets/Variables、回滚方式、故障排查见：

- [release-runbook.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/release-runbook.md)

## 7. 测试手册

完整测试说明见：

- [docs/onboarding/testing.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/testing.md)
- [CONTRIBUTING.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/CONTRIBUTING.md)

## 8. 稳定基线

当前 `web-playwright-python` 与 `ai-orchestrator` 的阶段1到阶段6稳定基线见：

- [web-playwright-python-stable-baseline.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/conventions/web-playwright-python-stable-baseline.md)
- [stage8-self-healing-advisor-checklist.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/conventions/stage8-self-healing-advisor-checklist.md)

这份文档用于约束后续演进边界，核心原则是：

- 先稳定，再增强
- 不大改当前已跑通版本
- AI 生成 YAML 必须复用稳定 smoke YAML 和 page-object 命名
- 自动修复当前只允许输出建议，不允许自动改文件

## 9. Orchestrator API 契约

`ai-orchestrator` 的 OpenAPI 文档见：

- [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

## 10. Web Console

当前内置控制台位于：

- [apps/web-console/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/README.md)
- [docs/onboarding/console-scaffold-guide.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/console-scaffold-guide.md)
- [docs/product/console-scaffold-prd.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-prd.md)
- [docs/product/console-scaffold-ux-spec.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-ux-spec.md)
- [docs/testing/console-scaffold-test-cases.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/testing/console-scaffold-test-cases.md)
- [docs/api/console-scaffold-api-spec.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/api/console-scaffold-api-spec.md)

说明：

- 它目前是由 `ai-orchestrator` 直接托管的静态页面，不是独立前端工程
- 控制台入口是 [http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)
- 最小静态检查入口是 `make check-console`
- 如果你是第一次使用，优先看 `Console Scaffold Guide`

## 11. Web UI Worklog

今天围绕独立 `web-ui`、测试报告拆分、缺陷关联、报告导航和本地服务稳定性修复的归档见：

- [2026-03-18-web-ui-report-worklog.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/2026-03-18-web-ui-report-worklog.md)
- [2026-03-18-web-ui-report-summary.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/2026-03-18-web-ui-report-summary.md)
- [web-ui-input-sources-guide.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/web-ui-input-sources-guide.md)
- [web-ui/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/README.md)
- [apps/web-ui-service/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/README.md)

说明：

- 当前 Web UI 后端服务入口已经迁入 `apps/web-ui-service/app/`（FastAPI）
- 为保持兼容，`web-ui/` 目录仅保留旧入口转发层；真实实现统一在 `apps/web-ui-service/`

## 12. 平台规划文档

当前平台链路的差距分析与下一阶段排期见：

- [platform-gap-analysis.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/platform-gap-analysis.md)
- [next-phase-roadmap.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/next-phase-roadmap.md)
- [project-structure.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/project-structure.md)
