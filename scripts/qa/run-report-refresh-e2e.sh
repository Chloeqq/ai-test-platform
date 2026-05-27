#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

export WEB_UI_REPORT_REFRESH_E2E=1
export WEB_UI_BASE_URL="${WEB_UI_BASE_URL:-http://127.0.0.1:8013}"

echo "[report-refresh-e2e] WEB_UI_BASE_URL=${WEB_UI_BASE_URL}"
"${PYTHON_BIN}" -m pytest \
  "${ROOT_DIR}/runners/web-playwright-python/tests/test_report_refresh_consistency.py" \
  -q
