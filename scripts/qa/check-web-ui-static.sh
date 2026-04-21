#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

TEMPLATES_DIR="apps/web-ui-service/app/templates"
STATIC_DIR="apps/web-ui-service/app/static"
REACT_TEMPLATE="${TEMPLATES_DIR}/react_app.html"

if [[ ! -f "${REACT_TEMPLATE}" ]]; then
  echo "[check-web-ui-static] Missing React shell template: ${REACT_TEMPLATE}" >&2
  exit 1
fi

legacy_templates=$(find "${TEMPLATES_DIR}" -maxdepth 1 -type f ! -name "react_app.html" | sort || true)
if [[ -n "${legacy_templates}" ]]; then
  echo "[check-web-ui-static] Legacy templates must be removed; found:" >&2
  echo "${legacy_templates}" >&2
  exit 1
fi

legacy_static=$(find "${STATIC_DIR}" -maxdepth 1 -type f | sort || true)
if [[ -n "${legacy_static}" ]]; then
  echo "[check-web-ui-static] Legacy static root files must be removed; found:" >&2
  echo "${legacy_static}" >&2
  exit 1
fi

if ! rg -n "/static/react/assets/main.css" "${REACT_TEMPLATE}" >/dev/null 2>&1; then
  echo "[check-web-ui-static] React shell is missing /static/react/assets/main.css reference." >&2
  exit 1
fi

if ! rg -n "/static/react/assets/main.js" "${REACT_TEMPLATE}" >/dev/null 2>&1; then
  echo "[check-web-ui-static] React shell is missing /static/react/assets/main.js reference." >&2
  exit 1
fi

echo "[check-web-ui-static] React-only static policy passed."
