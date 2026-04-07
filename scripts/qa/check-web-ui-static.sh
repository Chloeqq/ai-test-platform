#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v node >/dev/null 2>&1; then
  echo "[check-web-ui-static] Missing node executable." >&2
  exit 1
fi

FILES=(
  "apps/web-ui-service/app/static/cases.js"
  "apps/web-ui-service/app/static/cases_dialog.js"
  "apps/web-ui-service/app/static/projects_api.js"
  "apps/web-ui-service/app/static/project_manager_dialog.js"
  "apps/web-ui-service/app/static/workbench_generate_shared.js"
  "apps/web-ui-service/app/static/workbench_generate.js"
  "apps/web-ui-service/app/static/workbench_cases.js"
  "apps/web-ui-service/app/static/workbench.js"
  "apps/web-ui-service/app/static/execution_runs_presenter.js"
)

for file in "${FILES[@]}"; do
  echo "[check-web-ui-static] node --check ${file}"
  node --check "${file}"
done

echo "[check-web-ui-static] Completed."
