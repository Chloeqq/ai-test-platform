#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
ALEMBIC_BIN="${ROOT_DIR}/.venv/bin/alembic"
WEB_UI_SERVICE_DIR="${ROOT_DIR}/apps/web-ui-service"
SQLITE_VERIFY_DB="${WEB_UI_SERVICE_DIR}/alembic-acceptance.db"

EXPECTED_REVISION="20260323_221200"
POSTGRES_DSN_DEFAULT="postgresql+psycopg2://aitest:aitest@127.0.0.1:5432/ai_test_platform"
POSTGRES_DSN="${POSTGRES_DSN:-${POSTGRES_DSN_DEFAULT}}"
SKIP_POSTGRES=0

PASS_COUNT=0
FAIL_COUNT=0

FAILED_STEPS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/qa/accept-enterprise-upgrade.sh [--skip-postgres] [--postgres-dsn DSN]

Options:
  --skip-postgres      Skip PostgreSQL migration and verification steps.
  --postgres-dsn DSN   Override PostgreSQL DSN used by Alembic and validation.
  -h, --help           Show this help.

Environment:
  POSTGRES_DSN         Same as --postgres-dsn, if provided.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-postgres)
      SKIP_POSTGRES=1
      shift
      ;;
    --postgres-dsn)
      POSTGRES_DSN="${2:-}"
      if [[ -z "${POSTGRES_DSN}" ]]; then
        echo "[ERROR] --postgres-dsn requires a value"
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

require_binary() {
  local path="$1"
  local name="$2"
  if [[ ! -x "${path}" ]]; then
    echo "[ERROR] Missing executable: ${name} (${path})"
    exit 2
  fi
}

run_step() {
  local title="$1"
  local cmd="$2"
  echo
  echo "==> ${title}"
  set +e
  eval "${cmd}"
  local code=$?
  set -e
  if [[ ${code} -eq 0 ]]; then
    echo "[PASS] ${title}"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "[FAIL] ${title} (exit=${code})"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_STEPS+=("${title}")
  fi
}

print_summary() {
  echo
  echo "================ Acceptance Summary ================"
  echo "PASS: ${PASS_COUNT}"
  echo "FAIL: ${FAIL_COUNT}"
  if [[ ${FAIL_COUNT} -gt 0 ]]; then
    echo "Failed Steps:"
    for step in "${FAILED_STEPS[@]}"; do
      echo "  - ${step}"
    done
    echo "===================================================="
    return 1
  fi
  echo "All checks passed."
  echo "===================================================="
  return 0
}

require_binary "${PYTHON_BIN}" "python"
require_binary "${ALEMBIC_BIN}" "alembic"

set -e

run_step "Required files exist" "
  test -f '${WEB_UI_SERVICE_DIR}/migrations/versions/20260323_170800_add_workbench_reporting_tables.py' &&
  test -f '${WEB_UI_SERVICE_DIR}/scripts/bootstrap_database.py' &&
  test -f '${WEB_UI_SERVICE_DIR}/tests/unit/test_workbench_services.py' &&
  test -f '${WEB_UI_SERVICE_DIR}/tests/integration/test_workbench_multisource_endpoints.py'
"

run_step "Unit tests (web-ui-service/tests/unit)" "
  '${PYTHON_BIN}' -m pytest '${WEB_UI_SERVICE_DIR}/tests/unit' -q
"

run_step "Integration tests (workbench multisource)" "
  '${PYTHON_BIN}' -m pytest '${WEB_UI_SERVICE_DIR}/tests/integration/test_workbench_multisource_endpoints.py' -q
"

run_step "SQLite Alembic upgrade to head" "
  rm -f '${SQLITE_VERIFY_DB}' &&
  cd '${WEB_UI_SERVICE_DIR}' &&
  DATABASE_URL='sqlite:////${SQLITE_VERIFY_DB}' '${ALEMBIC_BIN}' -c alembic.ini upgrade head
"

run_step "SQLite revision equals ${EXPECTED_REVISION}" "
  '${PYTHON_BIN}' - <<'PY'
import sqlite3
db = r'${SQLITE_VERIFY_DB}'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('select version_num from alembic_version')
rows = cur.fetchall()
conn.close()
print('sqlite alembic_version =', rows)
assert rows == [('${EXPECTED_REVISION}',)], rows
PY
"

if [[ ${SKIP_POSTGRES} -eq 0 ]]; then
  run_step "PostgreSQL Alembic upgrade to head" "
    cd '${WEB_UI_SERVICE_DIR}' &&
    DATABASE_URL='${POSTGRES_DSN}' '${ALEMBIC_BIN}' -c alembic.ini upgrade head
  "

  run_step "PostgreSQL revision + table existence validation" "
    '${PYTHON_BIN}' - <<'PY'
import psycopg2
dsn = '${POSTGRES_DSN}'.replace('+psycopg2', '')
conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute('select version_num from alembic_version')
version_rows = cur.fetchall()
print('postgres alembic_version =', version_rows)
assert version_rows == [('${EXPECTED_REVISION}',)], version_rows
cur.execute(\"select to_regclass('public.workbench_defect_links'), to_regclass('public.workbench_failure_source_calibrations')\")
table_rows = cur.fetchall()
print('postgres tables =', table_rows)
assert table_rows == [('workbench_defect_links', 'workbench_failure_source_calibrations')], table_rows
conn.close()
PY
  "
else
  echo
  echo "[SKIP] PostgreSQL checks skipped by --skip-postgres"
fi

if print_summary; then
  exit 0
fi
exit 1
