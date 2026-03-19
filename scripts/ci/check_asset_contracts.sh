#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

changed_files=""

if [ "$#" -gt 0 ]; then
  changed_files="$(printf '%s\n' "$@")"
else
  changed_files="$(git diff --cached --name-only --diff-filter=ACMR --relative="$REPO_ROOT" || true)"
fi

if ! printf '%s\n' "$changed_files" | grep -Eq '(^|/)assets/(test-cases|page-objects)/'; then
  echo "No staged asset changes detected, skipping asset contract checks."
  exit 0
fi

PYTHONPATH=runners/web-playwright-python .venv/bin/python -m pytest -m contract runners/web-playwright-python/tests/test_asset_contracts.py
