#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/apps/web-ui-service/frontend"
ENV_FILE="${ROOT_DIR}/.env"
LOG_FILE="/tmp/web-ui-frontend.log"
FRONTEND_PORT="${FRONTEND_PORT:-8014}"
API_TARGET="${VITE_API_TARGET:-http://127.0.0.1:8014}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  echo "[restart-frontend] loaded env file: ${ENV_FILE}"
else
  echo "[restart-frontend] env file not found, continue with current shell environment."
fi

stop_port() {
  local port="$1"
  local name="$2"
  local command_name="${3:-}"
  local pids
  if [[ -n "${command_name}" ]]; then
    pids="$(lsof -t -iTCP:${port} -sTCP:LISTEN -a -c "${command_name}" || true)"
  else
    pids="$(lsof -t -iTCP:${port} -sTCP:LISTEN || true)"
  fi
  if [[ -z "${pids}" ]]; then
    echo "[restart-frontend] ${name} not running on port ${port}."
    return 0
  fi
  echo "[restart-frontend] stopping ${name} pid(s): ${pids}"
  kill ${pids} 2>/dev/null || true
  sleep 2
  local retry=0
  while lsof -t -iTCP:${port} -sTCP:LISTEN >/dev/null 2>&1 && [[ ${retry} -lt 10 ]]; do
    retry=$((retry + 1))
    sleep 1
  done
  if lsof -t -iTCP:${port} -sTCP:LISTEN >/dev/null 2>&1; then
    kill -9 ${pids} 2>/dev/null || true
    sleep 1
  fi
  echo "[restart-frontend] ${name} stopped by port ${port} (pid=${pids})."
}

stop_port "${FRONTEND_PORT}" "frontend" "node"

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "[restart-frontend] frontend directory missing: ${FRONTEND_DIR}" >&2
  exit 1
fi

if [[ ! -f "${FRONTEND_DIR}/package.json" ]]; then
  echo "[restart-frontend] package.json missing under frontend directory" >&2
  exit 1
fi

cd "${FRONTEND_DIR}"
export VITE_API_TARGET="${API_TARGET}"
nohup npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}" >"${LOG_FILE}" 2>&1 &
frontend_pid=$!
echo "[restart-frontend] frontend started (pid=$!)."
echo "[restart-frontend] log: ${LOG_FILE}"
echo "[restart-frontend] url: http://127.0.0.1:${FRONTEND_PORT}"

sleep 2
if ! curl -fsS "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
  echo "[restart-frontend] frontend health check failed, showing log tail:" >&2
  tail -n 40 "${LOG_FILE}" >&2
  exit 1
fi
echo "[restart-frontend] frontend is ready."
