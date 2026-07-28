#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
BASE_REF="${BASE_REF:-origin/dev}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[evie-ai-quality] Missing Python interpreter: ${PYTHON_BIN}" >&2
  echo "[evie-ai-quality] Run 'make install-dev' first." >&2
  exit 2
fi

"${PYTHON_BIN}" scripts/ci/evie_ai_quality_gate.py \
  --base-ref "${BASE_REF}" \
  "$@"

"${PYTHON_BIN}" -m pytest \
  tests/unit/test_evie_ai_code_quality_gate.py \
  -q

PYTHONPATH=apps/web-ui-service \
  "${PYTHON_BIN}" -m pytest \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py \
  -q
