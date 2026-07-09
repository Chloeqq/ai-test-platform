# AI Quality Assurance Platform：Pytest 详解

本文档描述本仓库中 **pytest 的配置、约定、分层策略与实现细节**，面向需要在本地或 CI 中调试、扩展测试的同学。

**相关文件索引（建议收藏路径）：**

| 资源 | 路径 |
|------|------|
| 根配置 | [pytest.ini](../../pytest.ini) |
| Runner 子配置 | [runners/web-playwright-python/pytest.ini](../../runners/web-playwright-python/pytest.ini) |
| 开发依赖（含 pytest 及插件） | [requirements-dev.txt](../../requirements-dev.txt) |
| 根 Makefile 测试目标 | [Makefile](../../Makefile) |
| 静态基线（含 pytest 段） | [scripts/qa/run-static-baseline.sh](../../scripts/qa/run-static-baseline.sh)、[scripts/qa/run-static-baseline-fast.sh](../../scripts/qa/run-static-baseline-fast.sh) |
| CI 工作流 | [.github/workflows/tests.yml](../../.github/workflows/tests.yml) |
| Web UI 集成测试 fixture | [apps/web-ui-service/tests/conftest.py](../../apps/web-ui-service/tests/conftest.py) |
| Playwright Runner 钩子与 fixture | [runners/web-playwright-python/conftest.py](../../runners/web-playwright-python/conftest.py) |

**补充速查：** [cookbook.md](./cookbook.md)（常用命令一览）

---

## 目录

1. [pytest 在本仓库中的定位](#1-pytest-在本仓库中的定位)
2. [运行前环境](#2-运行前环境)
3. [根目录 `pytest.ini` 逐项说明](#3-根目录-pytestini-逐项说明)
4. [Runner 子项目的 `pytest.ini`](#4-runner-子项目的-pytestini)
5. [测试发现与「默认会跑哪些用例」](#5-测试发现与默认会跑哪些用例)
6. [Markers：注册、语义与代码中的真实用法](#6-markers注册语义与代码中的真实用法)
7. [模块级 `pytestmark`](#7-模块级-pytestmark)
8. [Fixtures](#8-fixtures)
9. [pytest 钩子（Hooks）与失败产物](#9-pytest-钩子hooks与失败产物)
10. [参数化、`tmp_path`、`raises`](#10-参数化tmp_pathraises)
11. [Monkeypatch 与环境变量开关](#11-monkeypatch-与环境变量开关)
12. [插件：pytest-playwright、allure-pytest](#12-插件pytest-playwrightallure-pytest)
13. [Makefile 与 pytest 命令对照](#13-makefile-与-pytest-命令对照)
14. [静态基线 `static-baseline` 的分步行为](#14-静态基线-static-baseline-的分步行为)
15. [GitHub Actions 中的 pytest](#15-github-actions-中的-pytest)
16. [与其他目录中 pytest 的关系](#16-与其他目录中-pytest-的关系)
17. [排障与注意事项](#17-排障与注意事项)

---

## 1. pytest 在本仓库中的定位

pytest 承担几类互补职责：

| 层次 | 典型内容 | 依赖 |
|------|------------|------|
| **契约 / 不变量** | `shared_backend` 里 Schema 规范化、管线契约 | 通常无外部服务 |
| **服务集成** | FastAPI `TestClient` + 内存 SQLite、Orchestrator Flask test client | 无真实浏览器业务环境 |
| **Runner 契约** | YAML 资产、加载器、纯 Python 工具 | 无浏览器 |
| **浏览器 E2E** | Playwright、`BASE_URL`、账号 | 需可访问前端或演示环境 |

这与 Makefile 中的 `test-contracts`、`static-baseline`、`test-e2e*` 分层一致：**越往上越慢、越依赖环境**。

---

## 2. 运行前环境

1. **Python 虚拟环境**（仓库惯例）：项目根执行 `make install-dev`，得到 `.venv/`。
2. **解释器**：CI 使用 Python **3.13**（见 `.github/workflows/tests.yml`）；本地建议对齐主版本。
3. **`PYTHONPATH`**：根 `pytest.ini` 已注入多处路径；部分 Makefile 目标会**额外**设置 `PYTHONPATH`（例如 Runner），用于覆盖默认收集目录下的导入场景。
4. **Playwright 浏览器**：E2E 前需 `.venv/bin/playwright install chromium`（CI 中亦有安装步骤）。

---

## 3. 根目录 `pytest.ini` 逐项说明

对应文件：[pytest.ini](../../pytest.ini)。

### 3.1 `pythonpath`

多行路径会加入 **sys.path**（pytest 6+ 行为），等价于在运行测试前把下列目录当作「一等公民」包根：

- `.`（仓库根）
- `shared_backend`
- `apps/web-ui-service`
- `apps/ai-orchestrator/src`
- `runners/web-playwright-python` 及其 `tools`
- 多个 `agents/*` 源码根

**作用**：测试代码里可直接 `from app....`、`from shared_backend....`、`from orchestrator_service....` 等，避免在每个测试文件手写 `sys.path.insert`。

**注意**：若你在子目录单独运行 pytest 且未加载根配置，可能出现导入差异；优先从**仓库根**执行 `.venv/bin/python -m pytest`。

### 3.2 `testpaths`

仅当**命令行未显式传入路径**时，pytest 只在下列目录收集测试：

- `shared_backend/tests`
- `apps/ai-orchestrator/tests/integration`
- `apps/web-ui-service/tests/integration`
- `runners/web-playwright-python/tests/test_asset_contracts.py`
- `runners/web-playwright-python/tests/test_asset_toolkit.py`

**作用**：缩小默认范围；例如 **`apps/web-ui-service/tests/unit/` 不在默认 testpaths 中**，裸跑 `pytest` 不会收集单元测试，需要显式指定路径（见 [§5](#5-测试发现与默认会跑哪些用例)）。

### 3.3 `python_files` / `python_classes` / `python_functions`

- 文件：`test_*.py`
- 类：`Test*`
- 函数：`test_*`

与 pytest 默认约定一致，便于工具链与文档统一。

### 3.4 `markers`（须在配置中声明）

声明以下自定义标记（避免 UnknownMark 警告，并文档化语义）：

| Marker | 含义 |
|--------|------|
| `contract` | 契约、Schema、静态不变量 |
| `integration` | 跨模块集成，不要求真实业务环境 |
| `e2e` | 端到端；浏览器或可运行目标 |
| `smoke` | 人工筛选的冒烟 |
| `generated` | AI 生成的 YAML 驱动用例 |

这些标记与 **`-m`** 过滤配合使用；并非每个测试文件都挂了 marker（尤其是默认 testpaths 下的 integration 测试），因此 **`-m integration` 只会选中显式打了该标记的用例**。

### 3.5 `norecursedirs`

收集时跳过 `.git`、`.venv`、`node_modules`、`__pycache__` 以及 runner 内嵌虚拟环境等目录，减少无关遍历与误收集。

### 3.6 `addopts = -ra`

`-r` 输出简短摘要信息（a = 所有额外信息），包含 **skipped、xfailed** 等的原因行，便于 CI 日志审查。

---

## 4. Runner 子项目的 `pytest.ini`

路径：[runners/web-playwright-python/pytest.ini](../../runners/web-playwright-python/pytest.ini)。

与根配置差异要点：

| 项 | Runner 子配置 | 说明 |
|----|----------------|------|
| `testpaths` | `tests` | 相对于该目录，默认收集 `runners/web-playwright-python/tests/` |
| `pythonpath` | `. tools` | 强调 Runner 包内与 tools |
| `addopts` | `-v --output=test-results` | 详细输出并指定输出目录（插件相关） |
| `markers` | `e2e` / `smoke` / `generated` | 子集，用于浏览器测试分层 |

当你从**仓库根**用根 `pytest.ini` 跑 Runner 测试时，通常通过 **`PYTHONPATH=runners/web-playwright-python`** + 显式路径或 `-m e2e`，根配置的 `pythonpath` 与子目录习惯叠加使用。

---

## 5. 测试发现与「默认会跑哪些用例」

### 5.1 从仓库根不加路径

```bash
.venv/bin/python -m pytest
```

行为：使用根 `pytest.ini` 的 **`testpaths`**（见 §3.2）。  
**不会**自动包含：

- `apps/web-ui-service/tests/unit/`
- `apps/web-ui-service/tests/` 下非 integration 子目录中的部分文件
- `agents/*/tests/`（除非显式路径）

### 5.2 显式路径（覆盖 testpaths）

示例：

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/unit/
.venv/bin/python -m pytest agents/requirement-parser-agent/tests/
```

### 5.3 `static-baseline` 中的 `pytest -q agents`

脚本 [run-static-baseline.sh](../../scripts/qa/run-static-baseline.sh) 会执行：

```bash
.venv/bin/python -m pytest -q agents
```

这是对 **`agents` 目录的显式收集**，与默认 `testpaths` 无关；用于跑各 Agent 包下的单元/契约测试。

---

## 6. Markers：注册、语义与代码中的真实用法

### 6.1 为何需要注册？

pytest 建议在 `pytest.ini` 中列出自定义 marker，否则新版本可能对 **未知标记** 发出告警或在未来改为错误。

### 6.2 Makefile 中的组合筛选

根 `Makefile` 定义：

```makefile
PYTEST_CONTRACT := $(PYTEST) -m "contract or integration"
```

**语义**：只运行**至少打了 `contract` 或 `integration` 标记**的测试。  
若某集成测试**未打** `integration` marker，则不会被该变量选中——这是阅读 CI/本地脚本时容易忽略的一点。

### 6.3 仓库中 marker 的实际出现位置（示例）

以下便于「按文件理解」本项目如何使用 marker（非穷举）：

| 位置 | 标记方式 | 说明 |
|------|-----------|------|
| [runners/web-playwright-python/tests/test_login_smoke.py](../../runners/web-playwright-python/tests/test_login_smoke.py) | `pytestmark = [pytest.mark.e2e, pytest.mark.smoke]` | 模块级作用于全部用例 |
| [runners/web-playwright-python/tests/test_yaml_ai_generated.py](../../runners/web-playwright-python/tests/test_yaml_ai_generated.py) | `e2e` + `generated` | AI YAML 驱动 + 浏览器 |
| [runners/web-playwright-python/tests/test_asset_contracts.py](../../runners/web-playwright-python/tests/test_asset_contracts.py) | `contract` | 资产契约 |
| [runners/web-playwright-python/tests/test_ai_generated_loader.py](../../runners/web-playwright-python/tests/test_ai_generated_loader.py) | `contract` | 加载器逻辑（仍属稳定契约） |
| [runners/web-playwright-python/tests/test_base_url_check.py](../../runners/web-playwright-python/tests/test_base_url_check.py) | `@pytest.mark.contract` | 单函数标记 |
| [apps/ai-orchestrator/tests/integration/test_orchestrate_execute_true_e2e_smoke.py](../../apps/ai-orchestrator/tests/integration/test_orchestrate_execute_true_e2e_smoke.py) | `@pytest.mark.integration` + `@pytest.mark.e2e` | 编排真实执行链冒烟 |

**结论**：Runner 侧习惯用 **`pytestmark`** 批量打标；Orchestrator 个别文件用 **装饰器**；Web UI 大量 integration 测试可能**仅依赖路径被收集**，而无 `integration` marker——是否纳入 `PYTEST_CONTRACT` 取决于是否打了标。

---

## 7. 模块级 `pytestmark`

示例（Runner）：

```python
pytestmark = [pytest.mark.e2e, pytest.mark.smoke]
```

**作用**：将该模块内所有测试函数默认挂上所列标记，避免每个 `def test_*` 重复写装饰器。

---

## 8. Fixtures

### 8.1 Web UI：`workbench_generation_client`

定义位置：[apps/web-ui-service/tests/conftest.py](../../apps/web-ui-service/tests/conftest.py)。

机制摘要：

- 使用 **SQLite 内存库**（`sqlite://`）+ `StaticPool`，单线程共享连接。
- `Base.metadata.create_all` 创建 ORM 表。
- 构造最小 **FastAPI** 应用，仅 `include_router(workbench_generation_router)`。
- 使用 `app.dependency_overrides[get_db]` 注入测试 `Session`。
- `yield client, session` 后关闭 `TestClient` 与 session。

**知识点对应**：pytest **fixture 生命周期**、`yield` 清理、FastAPI **依赖覆盖**、`starlette.testclient.TestClient`（依赖 **httpx**，需在环境中安装）。

### 8.2 各集成测试文件内的局部 fixture

例如 `test_workbench_projects_api.py`、`test_page_objects_api.py` 等自建 **完整 app** 或替换路由——用于覆盖不同路由组合，而不放大全局 `conftest` 的职责。

### 8.3 Runner：`page`、`base_url`、`test_username` 等

定义于 [runners/web-playwright-python/conftest.py](../../runners/web-playwright-python/conftest.py)（篇幅较长）。典型测试签名：

```python
def test_login_smoke(page, base_url, test_username, test_password):
```

**作用**：封装 Playwright **同步 API**、从环境变量读取基地址与账号、失败时截图与证据落盘等。

### 8.4 `autouse=True`

用于「每个测试自动执行前后逻辑」，例如清空认证状态、占位 **capture_failure_artifacts**（见 Runner 测试中空的 autouse fixture，可与钩子联动扩展）。

---

## 9. pytest 钩子（Hooks）与失败产物

Runner 的 [conftest.py](../../runners/web-playwright-python/conftest.py) 注册了：

| 钩子 | 作用 |
|------|------|
| `pytest_runtest_makereport`（hookwrapper） | 在 fixture 内通过 `request.node.rep_call` 等读取 **setup/call/teardown** 各阶段报告 |
| `pytest_runtest_teardown` | 在 teardown 阶段汇总状态，写入 **ExecutionRecord**、**EvidenceManifest** 等 |

这与纯「单元测试断言」不同：属于 **pytest 插件机制**，用于把测试结果映射到平台的 **证据契约**（`shared_backend` 规范化）。

---

## 10. 参数化、`tmp_path`、`raises`

- **`@pytest.mark.parametrize`**：表驱动多种输入（见 Web UI unit 测试及部分 Runner 测试）。
- **`tmp_path`**：pytest 内置 fixture，提供隔离临时目录（如 `test_ai_generated_loader_accepts_case_path_inside_ai_generated`）。
- **`pytest.raises`**：断言期望异常类型与文案（加载器路径校验等）。

---

## 11. Monkeypatch 与环境变量开关

集成测试中常见三类：

1. **替换客户端**：如 Orchestrator 解析改为 stub。
2. **替换文件系统根**：`tmp_path` 指向案例资产目录。
3. **环境变量**：例如 Makefile 中的  
   - `EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false`（Web UI manifest 严格模式）  
   - `EXECUTION_RECORD_COMPAT_BUILDER_ENABLED=false`（Orchestrator execution_record 严格模式）  
   - `TEST_DESIGN_MODE=deterministic`（编排 E2E 冒烟确定性）

这些常在 **`make test-webui-manifest-strict`**、**`test-orchestrator-manifest-strict`**、**`test-orchestrate-e2e-smoke`** 中与 **`pytest -k strict_mode`** 组合使用。

---

## 12. 插件：pytest-playwright、allure-pytest

| 插件 | 作用 |
|------|------|
| **pytest-playwright** | 提供 `page` 等 fixture，与 Playwright 同步 API 集成 |
| **allure-pytest** | 支持 `--alluredir`，与 [manage_allure.py](../../runners/web-playwright-python/tools/manage_allure.py) 生成 HTML 报告 |

安装见 [requirements-dev.txt](../../requirements-dev.txt)。

---

## 13. Makefile 与 pytest 命令对照

下表便于从「我要跑什么」反查命令（完整见 [Makefile](../../Makefile)）。

| Make 目标 | pytest 相关行为 |
|-----------|------------------|
| `test-pipeline-contracts` | 显式文件列表：`shared_backend/tests/test_execution_compiler_contract.py` 等 |
| `test-orchestrator` | `-m integration apps/ai-orchestrator/tests/integration` |
| `test-openapi` | 单文件 `test_openapi_contract.py` |
| `test-runner-assets` | `PYTHONPATH=runners/web-playwright-python` + `-m contract` + 指定文件 |
| `test-webui-manifest-strict` | 环境变量 + `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py -k strict_mode` |
| `test-orchestrator-manifest-strict` | 环境变量 + `test_orchestrator_service_asset_flow.py -k strict_mode` |
| `test-orchestrate-e2e-smoke` | `TEST_DESIGN_MODE=deterministic` + `test_orchestrate_execute_true_e2e_smoke.py` |
| `test-e2e` | `-m e2e runners/web-playwright-python/tests` |
| `test-e2e-smoke` | `-m "e2e and smoke"` + 显式若干 smoke 文件 |
| `test-e2e-generated` | `-m "e2e and generated"` |

---

## 14. 静态基线 `static-baseline` 的分步行为

`make static-baseline` 会先执行 **`run-static-baseline-fast.sh`**（**不含 pytest**：ruff、Web UI 静态 JS、mypy），再执行 **`run-static-baseline.sh`**：

| 步骤 | 说明 |
|------|------|
| pytest `-q agents` | Agent 目录下测试 |
| pytest Runner 工具测试 | `test_manage_allure.py`、`test_report_summary.py`、`test_base_url_check.py` |
| pytest Orchestrator OpenAPI | `test_openapi_contract.py` |
| `check_workbench_architecture.py` | **非 pytest**：架构与导入守卫 |

因此 **「静态基线」≠ 仅 pytest**，而是 **静态分析 + 选定 pytest + 架构脚本** 的组合。

---

## 15. GitHub Actions 中的 pytest

工作流 [.github/workflows/tests.yml](../../.github/workflows/tests.yml) 中与 pytest 相关的要点：

| Job | 说明 |
|-----|------|
| **static-baseline**（ubuntu） | `make test-contracts`、`make static-baseline`；随后安装 Playwright Chromium，执行 **`make test-orchestrate-e2e-smoke`**（编排真实链冒烟） |
| **e2e-smoke / e2e-generated**（self-hosted） | 需 `BASE_URL`、`TEST_USERNAME`、`TEST_PASSWORD`；分别 `make test-e2e-smoke`、`make test-e2e-generated` |

PR 推送默认跑 **static-baseline job**；完整 E2E 常为 **workflow_dispatch** 触发。

---

## 16. 与其他目录中 pytest 的关系

若仓库中存在 **第三方或 vendored 子项目**（例如独立的 API 工程），其目录内可能另有 **`pytest.ini`** 与 **`tests/`** 布局。运行方式以该子项目为准；**不要假设**根目录 `testpaths` 会收集它们。

---

## 17. 排障与注意事项

1. **`ModuleNotFoundError`**：确认从仓库根运行，且根 `pytest.ini` 生效；或按 Makefile 设置 `PYTHONPATH`。
2. **`TestClient` / httpx**：Starlette TestClient 需要 **httpx**；缺失会报错。
3. **默认不跑 unit**：依赖 `apps/web-ui-service/tests/unit/` 时需显式路径。
4. **`-m integration` 与集成测试目录**：目录名是 `integration` 并不等于函数带有 `integration` marker；筛选时注意差异。
5. **E2E 红**：先检查 `BASE_URL`、账号、浏览器安装与网络；Runner `check_base_url.py` 在部分目标前执行。

---

*维护提示：变更根 `pytest.ini`、`Makefile` 静态基线脚本或 CI 工作流时，请同步更新本文档与 [cookbook.md](./cookbook.md)。*
