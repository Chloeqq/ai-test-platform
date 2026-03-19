# Web Playwright Python Stable Baseline

本文档用于固化当前 `web-playwright-python` 与 `ai-orchestrator` 的阶段性稳定基线。

目标：

- 先稳定，再增强
- 不大改当前已跑通版本
- AI 生成 YAML 必须严格复用当前稳定 smoke YAML 和 page-object 命名
- target 只能来自现有 page-object
- `login` 步骤不能带 `target/value`
- 每次只完成一个阶段，不一次性重构全部项目

## 阶段1：固化当前稳定版本

当前稳定基线：

- smoke 执行入口只运行 `assets/test-cases/smoke`
- 稳定 smoke YAML 文件集合固定为：
  - `login-smoke.yaml`
  - `order-smoke.yaml`
  - `permission-smoke.yaml`
  - `product-smoke.yaml`
- `login` 第一步必须是裸 `login`
  - 不能带 `target`
  - 不能带 `value`
- 稳定 smoke 相关 page-object target 命名被冻结，不允许 AI 自行发明新 target

对应校验：

- [test_asset_contracts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_asset_contracts.py)
- [test_yaml_smoke.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_yaml_smoke.py)

## 阶段2：固化 AI 生成规则

当前规则：

- AI 生成必须复用稳定 smoke 的步骤风格
- `product/order/permission` 页前两步固定为：
  - `login`
  - `click <稳定菜单 target>`
- `login` 页固定为：
  - `login`
  - `assert_visible home_menu`
- `target` 只能来自现有 page-object

对应校验：

- [agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/test-design-agent/src/agent.py)
- [test_stable_generation_rules.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/test-design-agent/tests/test_stable_generation_rules.py)

## 阶段3：打通 AI 用例单独执行链路

当前规则：

- AI 用例执行链路只运行 `assets/test-cases/ai-generated`
- 不加载 smoke 用例
- `tests/test_yaml_ai_generated.py` 只走 AI 专用 loader
- `RUN_MODE=ai` 时不允许把 `TEST_CASE_PATH` 指到 `smoke` 目录

对应校验：

- [test_case_loader.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/test_case_loader.py)
- [test_yaml_ai_generated.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_yaml_ai_generated.py)
- [test_ai_generated_loader.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_ai_generated_loader.py)

## 阶段4：补齐失败留痕能力

当前失败产物：

- `failed.png`
- `page.html`
- `meta.txt`
- `analysis.txt`
- 视频目录由 `PLAYWRIGHT_VIDEO_DIR` 配置

当前约束：

- 不改现有 E2E 执行主干
- 失败产物目录支持配置，但默认目录不变
- `meta.txt` 至少包含：
  - URL
  - Title
  - 截图路径
  - HTML 路径

对应实现：

- [conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)
- [PROJECT_DOCS.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/PROJECT_DOCS.md)

## 阶段5：接入 AI 失败分析

当前规则：

- pytest 失败后自动调用 `failure-analysis-agent`
- 输入包括：
  - 错误信息
  - 页面 HTML
  - 当前 URL
  - 页面标题
  - 失败证据路径
- 输出 `analysis.txt`
- orchestrator 报告中包含：
  - `failure_reason`
  - `failure_analysis`
  - `analysis_files`

对应实现：

- [analyze.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/failure-analysis-agent/analyze.py)
- [orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)

## 阶段6：预留自动修复入口

当前规则：

- 只输出建议，不自动修改 YAML
- 只输出建议，不自动修改 page-object
- 报告中包含：
  - `self_healing_advice`
- HTTP 预览接口：
  - `POST /healing/preview`

当前建议能力来源：

- [agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/src/agent.py)

对应契约：

- [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

## 阶段8：Self-Healing Advisor

当前规则：

- 新增 `self-healing-advisor-agent`
- pytest 失败后生成 `suggestion.json`
- Allure 中展示修复建议
- 安全校验：
  - `target` 必须来自现有 page-object
  - `confidence < 0.5` 时不输出建议
- 严格禁止自动修改 YAML

阶段8专项清单：

- [stage8-self-healing-advisor-checklist.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/conventions/stage8-self-healing-advisor-checklist.md)

## 当前推荐操作顺序

如果后续继续增强，必须遵守以下顺序：

1. 先补测试和契约
2. 再加小范围能力
3. 不重写当前 smoke 规则
4. 不让 AI 绕过 page-object 命名体系
5. 不让自动修复直接改文件

## 当前稳定入口

Runner：

- smoke 执行：
  - [test_yaml_smoke.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_yaml_smoke.py)
- AI 用例执行：
  - [test_yaml_ai_generated.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_yaml_ai_generated.py)

Orchestrator：

- 生成与执行：
  - `POST /orchestrate`
- 报告查询：
  - `GET /reports/latest`
  - `GET /reports/{case_id}`
- 自动修复建议预览：
  - `POST /healing/preview`
