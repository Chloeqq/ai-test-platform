#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
ENV_FILE="${ROOT_DIR}/.env"

ORCH_LOG="/tmp/ai-orchestrator.log"
WEB_LOG="/tmp/web-ui-service.log"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  echo "[start-all] loaded env file: ${ENV_FILE}"
else
  echo "[start-all] env file not found, continue with current shell environment."
fi

# Ensure root-level shared modules (e.g. datetime_compat.py) are importable.
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

if lsof -iTCP:8000 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "[start-all] port 8000 is already in use, skip orchestrator start."
else
  nohup "${PYTHON_BIN}" -m uvicorn app:app \
    --app-dir "${ROOT_DIR}/apps/ai-orchestrator/src" \
    --host 127.0.0.1 \
    --port 8000 >"${ORCH_LOG}" 2>&1 &
  echo "[start-all] orchestrator started (pid=$!)."
fi

if lsof -iTCP:8013 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "[start-all] port 8013 is already in use, skip web-ui-service start."
else
  nohup "${PYTHON_BIN}" -m uvicorn app.main:app \
    --app-dir "${ROOT_DIR}/apps/web-ui-service" \
    --host 127.0.0.1 \
    --port 8013 >"${WEB_LOG}" 2>&1 &
  echo "[start-all] web-ui-service started (pid=$!)."
fi

echo "[start-all] API docs:"
echo "  - http://127.0.0.1:8000/docs"
echo "  - http://127.0.0.1:8013/docs"
