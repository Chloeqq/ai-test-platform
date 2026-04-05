# Testing Guide

本文档说明当前仓库的测试分层、依赖准备、本地运行方式，以及与 CI 的对应关系。

## 1. 测试分层

当前项目把测试分成 4 类：

- `contract`
  - 契约/结构/静态一致性校验
  - 不依赖真实业务系统
- `integration`
  - 跨模块集成校验
  - 不依赖真实业务页面环境
- `e2e + smoke`
  - 人工维护的浏览器端到端测试
  - 依赖可访问的业务系统和有效账号
- `e2e + generated`
  - AI 生成的 YAML 浏览器端到端测试
  - 同样依赖真实业务环境

当前 marker 注册在：

- [pytest.ini](/Users/bettyhuang/PycharmProjects/ai-test-platform/pytest.ini)

## 2. 依赖准备

先在仓库根目录创建并安装开发依赖：

```bash
make install-dev
```

这会：

- 创建根目录 `.venv`
- 安装 [requirements-dev.txt](/Users/bettyhuang/PycharmProjects/ai-test-platform/requirements-dev.txt)

如果要运行浏览器 E2E 测试，还需要安装 Playwright 浏览器：

```bash
.venv/bin/playwright install
```

如果希望在 `git commit` 前自动校验测试资产，执行：

```bash
make install-hooks
```

## 3. 最常用命令

### 非 E2E 稳定测试

```bash
make test
```

### 统一静态基线（ruff + mypy + pytest）

```bash
make static-baseline
```

该入口会调用 [scripts/qa/run-static-baseline.sh](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/qa/run-static-baseline.sh)，执行当前 monorepo 下稳定可复用的 scoped `mypy` 命令组合（覆盖 `apps`、`runners`，并自动发现 `agents/*/src` 全量目录），避免重复模块命名冲突导致的误报。

### 快速静态基线（ruff + mypy，不跑 pytest）

```bash
make static-baseline-fast
```

该入口会调用 [scripts/qa/run-static-baseline-fast.sh](/Users/bettyhuang/PycharmProjects/ai-test-platform/scripts/qa/run-static-baseline-fast.sh)，适合本地高频迭代时快速验证静态质量门。

等价于：

```bash
.venv/bin/python -m pytest
```

这会跑：

- `apps/ai-orchestrator` 的 `integration` 测试
- `web-playwright-python` 的 `contract` 测试

### 只跑 orchestrator 集成测试

```bash
make test-orchestrator
```

### 只跑 runner 资产契约测试

```bash
make test-runner-assets
```

这会同时覆盖：

- 静态资产契约测试
- YAML / page object 工具链测试

## 4. 运行 E2E 测试

### 跑所有 E2E

```bash
make test-e2e
```

### 跑人工维护的 smoke 用例

```bash
make test-e2e-smoke
```

### 跑 AI 生成用例

```bash
make test-e2e-generated
```

也可以直接用 marker：

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python -m pytest -m "e2e and smoke" runners/web-playwright-python/tests
PYTHONPATH=runners/web-playwright-python .venv/bin/python -m pytest -m "e2e and generated" runners/web-playwright-python/tests
```

## 5. E2E 运行前提

运行浏览器测试前，需要准备好这些环境变量：

- `BASE_URL`
- `TEST_USERNAME`
- `TEST_PASSWORD`

来源：

- 本地默认从根目录 [`.env`](/Users/bettyhuang/PycharmProjects/ai-test-platform/.env) 读取
- 模板见 [`.env.example`](/Users/bettyhuang/PycharmProjects/ai-test-platform/.env.example)

## 6. 当前默认行为

根级 `pytest` 默认只收集稳定的非 E2E 测试：

- [apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py)
- [runners/web-playwright-python/tests/test_asset_contracts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tests/test_asset_contracts.py)

这样做的目的，是避免开发者在没有业务环境和浏览器依赖时，直接误跑页面测试。

## 7. CI 对应关系

当前 GitHub Actions 配置见：

- [tests.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/tests.yml)

执行策略：

- `pull_request` / `push`
  - 默认跑 `make static-baseline`（`ruff + scoped mypy + pytest`）
- `workflow_dispatch`
  - 可手动选择：
    - `static-baseline`
    - `e2e-smoke`
    - `e2e-generated`
    - `all`

## 8. 常见问题

### `No module named pytest`

说明根目录 `.venv` 还没安装依赖，先执行：

```bash
make install-dev
```

### 提交时 pre-commit 提示 `.venv/bin/python` 不存在

说明根目录开发环境还没准备好，先执行：

```bash
make install-dev
make install-hooks
```

### `PytestUnknownMarkWarning`

通常是从错误目录启动 pytest，或子目录 `pytest.ini` 和根级 marker 没对齐。当前仓库已经同步了根级和 runner 子目录的 marker 定义；优先从仓库根目录运行命令。

### E2E 用例启动后打不开页面

优先检查：

- `BASE_URL` 是否正确
- 目标系统是否已启动
- `TEST_USERNAME` / `TEST_PASSWORD` 是否有效
- 是否已执行 `.venv/bin/playwright install`

## 9. 推荐工作流

日常开发建议：

1. `make install-dev`
2. `make test`
3. 改动涉及多模块质量门（类型检查、格式、回归）时，跑 `make static-baseline`
  如果仅需快速静态检查，可先跑 `make static-baseline-fast`
4. 改动涉及真实页面交互时，再额外跑 `make test-e2e-smoke`
5. 需要验证 AI 生成链路时，跑 `make test-e2e-generated`
