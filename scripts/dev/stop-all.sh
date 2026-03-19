#!/usr/bin/env bash
set -euo pipefail

stop_port() {
  local port="$1"
  local name="$2"
  local pids
  pids="$(lsof -t -iTCP:${port} -sTCP:LISTEN || true)"
  if [[ -z "${pids}" ]]; then
    echo "[stop-all] ${name} not running on port ${port}."
    return
  fi
  kill ${pids} || true
  echo "[stop-all] ${name} stopped by port ${port} (pid=${pids})."
}

stop_port 8000 "orchestrator"
stop_port 8013 "web-ui-service"
