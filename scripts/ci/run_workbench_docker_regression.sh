#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
WEB_SERVICE="${WORKBENCH_WEB_SERVICE:-web}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "[workbench-docker-regression] docker compose is required." >&2
  exit 1
fi

compose_exec() {
  "${COMPOSE[@]}" -f "${COMPOSE_FILE}" exec -T -w /app "${WEB_SERVICE}" "$@"
}

ensure_web_running() {
  if "${COMPOSE[@]}" -f "${COMPOSE_FILE}" ps --status running --services | grep -Fxq "${WEB_SERVICE}"; then
    return 0
  fi

  echo "[workbench-docker-regression] starting web stack..." >&2
  "${COMPOSE[@]}" -f "${COMPOSE_FILE}" up -d "${WEB_SERVICE}" postgres redis orchestrator >/dev/null
}

run_architecture_guard() {
  echo "[workbench-docker-regression] architecture guard"
  compose_exec python3 scripts/ci/check_workbench_architecture.py
}

run_py_compile() {
  echo "[workbench-docker-regression] py_compile"
  compose_exec python3 - <<'PY'
from pathlib import Path
import py_compile

bases = [
    Path("shared_backend"),
    Path("apps/web-ui-service/app"),
    Path("scripts/ci"),
]

paths: list[Path] = []
for base in bases:
    if base.exists():
        paths.extend(sorted(p for p in base.rglob("*.py") if p.is_file()))

for path in paths:
    py_compile.compile(str(path), doraise=True)

print(f"compiled {len(paths)} python files")
PY
}

run_pytest_if_available() {
  echo "[workbench-docker-regression] pytest"
  if ! compose_exec python3 -m pytest --version >/dev/null 2>&1; then
    echo "[workbench-docker-regression] pytest is not available in the web container; skipping tests." >&2
    return 0
  fi

  local tests=(
    "apps/web-ui-service/tests/test_workbench_generation_service.py"
    "apps/web-ui-service/tests/integration/test_workbench_generation_api.py"
  )

  if [[ -n "${WORKBENCH_DOCKER_EXTRA_TESTS:-}" ]]; then
    # shellcheck disable=SC2206
    tests+=( ${WORKBENCH_DOCKER_EXTRA_TESTS} )
  fi

  compose_exec python3 -m pytest -q "${tests[@]}"
}

main() {
  cd "${ROOT_DIR}"
  ensure_web_running
  run_architecture_guard
  run_py_compile
  run_pytest_if_available
  echo "[workbench-docker-regression] done"
}

main "$@"
