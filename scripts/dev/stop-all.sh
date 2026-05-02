#!/usr/bin/env bash
set -euo pipefail

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
    echo "[stop-all] ${name} not running on port ${port}."
    return
  fi
  kill ${pids} || true
  echo "[stop-all] ${name} stopped by port ${port} (pid=${pids})."
}

stop_port 8000 "orchestrator"
stop_port 8013 "frontend" "node"
stop_port 8014 "web-ui-service" "Python"
stop_port 8015 "stale-web-ui-service" "Python"
