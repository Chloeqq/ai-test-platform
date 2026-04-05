#!/usr/bin/env bash
set -euo pipefail

HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-20}"
HEALTHCHECK_INTERVAL_SECONDS="${HEALTHCHECK_INTERVAL_SECONDS:-5}"
HEALTHCHECK_TIMEOUT_SECONDS="${HEALTHCHECK_TIMEOUT_SECONDS:-3}"

if [[ -z "${HEALTHCHECK_URL}" ]]; then
  echo "[healthcheck] Missing HEALTHCHECK_URL" >&2
  exit 1
fi

echo "[healthcheck] Checking ${HEALTHCHECK_URL}"

attempt=1
while [[ "${attempt}" -le "${HEALTHCHECK_RETRIES}" ]]; do
  status_code="$(
    curl -sS -o /dev/null -w "%{http_code}" \
      --max-time "${HEALTHCHECK_TIMEOUT_SECONDS}" \
      "${HEALTHCHECK_URL}" || true
  )"

  if [[ "${status_code}" =~ ^2[0-9][0-9]$ ]]; then
    echo "[healthcheck] Success on attempt ${attempt} (HTTP ${status_code})"
    exit 0
  fi

  echo "[healthcheck] Attempt ${attempt}/${HEALTHCHECK_RETRIES} failed (HTTP ${status_code:-n/a})"
  if [[ "${attempt}" -lt "${HEALTHCHECK_RETRIES}" ]]; then
    sleep "${HEALTHCHECK_INTERVAL_SECONDS}"
  fi
  attempt=$((attempt + 1))
done

echo "[healthcheck] Service did not become healthy in time." >&2
exit 1
