#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
FAST_SCRIPT="scripts/qa/run-static-baseline-fast.sh"

"${FAST_SCRIPT}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[static-baseline] Missing Python interpreter: ${PYTHON_BIN}" >&2
  echo "[static-baseline] Run 'make install-dev' first." >&2
  exit 1
fi

echo "[static-baseline] Running pytest..."
# Incremental stable test scope for CI baseline.
"${PYTHON_BIN}" -m pytest -q agents

echo "[static-baseline] Running stable runner utility tests..."
PYTHONPATH=runners/web-playwright-python \
  "${PYTHON_BIN}" -m pytest -q \
  runners/web-playwright-python/tests/test_manage_allure.py \
  runners/web-playwright-python/tests/test_report_summary.py \
  runners/web-playwright-python/tests/test_base_url_check.py

echo "[static-baseline] Running stable orchestrator API contract tests..."
PYTHONPATH=apps/ai-orchestrator/src \
  "${PYTHON_BIN}" -m pytest -q \
  apps/ai-orchestrator/tests/integration/test_openapi_contract.py

echo "[static-baseline] Running workbench architecture guard..."
"${PYTHON_BIN}" scripts/ci/check_workbench_architecture.py

echo "[static-baseline] Completed."
