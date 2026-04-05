#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[static-baseline-fast] Missing Python interpreter: ${PYTHON_BIN}" >&2
  echo "[static-baseline-fast] Run 'make install-dev' first." >&2
  exit 1
fi

has_python_sources() {
  local target="$1"
  find "${target}" -type f \( -name "*.py" -o -name "*.pyi" \) -print -quit | grep -q .
}

echo "[static-baseline-fast] Running Ruff..."
"${PYTHON_BIN}" -m ruff check apps agents runners

echo "[static-baseline-fast] Building mypy target list..."
MYPY_TARGETS=()

# Incremental typed scope: keep CI green while we pay down typing debt.
for target in \
  "agents/execution-planner-agent/src" \
  "agents/failure-triage-agent/src" \
  "agents/requirement-parser-agent/src" \
  "agents/risk-evaluation-agent/src" \
  "agents/script-generation-agent/src" \
  "agents/self-healing-advisor-agent/src" \
  "agents/test-design-agent/src"; do
  if [[ -d "${target}" ]] && has_python_sources "${target}"; then
    MYPY_TARGETS+=("${target}")
  fi
done

if [[ ${#MYPY_TARGETS[@]} -eq 0 ]]; then
  echo "[static-baseline-fast] No mypy targets found; skipping mypy."
  exit 0
fi

echo "[static-baseline-fast] Running mypy on ${#MYPY_TARGETS[@]} targets..."
MYPY_FAILED=0
for target in "${MYPY_TARGETS[@]}"; do
  echo "[static-baseline-fast] mypy ${target}"
  if ! "${PYTHON_BIN}" -m mypy --exclude "(^|/)tools/index\\.py$" "${target}"; then
    MYPY_FAILED=1
  fi
done

if [[ "${MYPY_FAILED}" -ne 0 ]]; then
  echo "[static-baseline-fast] mypy reported errors." >&2
  exit 2
fi

echo "[static-baseline-fast] Completed."
