# Pytest 命令速查（Cookbook）

仓库根目录、已执行 `make install-dev` 为前提，解释器使用 `.venv/bin/python`。

---

## 1. 默认收集（与根 `testpaths` 一致）

```bash
.venv/bin/python -m pytest
```

---

## 2. 显式跑 Web UI 单元测试（默认 testpaths 不包含）

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/unit/ -v
```

---

## 3. 契约 + 带 `integration`/`contract` marker 的用例（Makefile 等价思路）

```bash
.venv/bin/python -m pytest -m "contract or integration"
```

注意：未打上述 marker 的「集成风格」测试**不会**被选中。

---

## 4. 仅 AI Orchestrator 集成目录

```bash
.venv/bin/python -m pytest -m integration apps/ai-orchestrator/tests/integration
```

---

## 5. 稳定契约三件套（与 `make test-pipeline-contracts` 同族）

```bash
.venv/bin/python -m pytest shared_backend/tests/test_execution_compiler_contract.py \
  shared_backend/tests/test_pipeline_contract.py \
  shared_backend/tests/test_contract_validator.py -v
```

---

## 6. Runner：资产契约（与 `make test-runner-assets` 同族）

```bash
PYTHONPATH=runners/web-playwright-python \
  .venv/bin/python -m pytest -m contract \
  runners/web-playwright-python/tests/test_asset_contracts.py \
  runners/web-playwright-python/tests/test_asset_toolkit.py
```

---

## 7. Runner：浏览器 E2E（需可访问 `BASE_URL`）

```bash
make test-e2e-smoke
# 或
make test-e2e-generated
```

底层近似：

```bash
PYTHONPATH=runners/web-playwright-python \
  .venv/bin/python -m pytest -m "e2e and smoke" \
  runners/web-playwright-python/tests/test_login_smoke.py
```

---

## 8. Agents 目录（与 `static-baseline` 中一段相同）

```bash
.venv/bin/python -m pytest -q agents
```

---

## 9. OpenAPI 契约单文件

```bash
PYTHONPATH=apps/ai-orchestrator/src \
  .venv/bin/python -m pytest apps/ai-orchestrator/tests/integration/test_openapi_contract.py -v
```

---

## 10. Allure 结果目录（示例）

```bash
PYTHONPATH=runners/web-playwright-python \
  .venv/bin/python -m pytest -m "e2e and smoke" \
  runners/web-playwright-python/tests/test_login_smoke.py \
  --alluredir runners/web-playwright-python/allure-results
```

然后可用 `make allure-generate` / `make allure-open`（见根 Makefile）。

---

## 11. 名称子集 `-k`

```bash
.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py -k strict_mode -v
```

常与 `EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false` 等环境变量配合（见 `Makefile` 中 `test-webui-manifest-strict`）。

---

更多说明见 [README.md](./README.md)。
