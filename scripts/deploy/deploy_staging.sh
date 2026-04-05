#!/usr/bin/env bash
set -euo pipefail

require_env() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "[deploy-staging] Missing required env: ${key}" >&2
    exit 1
  fi
}

require_env "IMAGE_REF"
require_env "GHCR_USERNAME"
require_env "GHCR_TOKEN"

CONTAINER_NAME="${CONTAINER_NAME:-ai-test-platform-web-staging}"
HOST_PORT="${HOST_PORT:-8013}"
ENV_FILE="${ENV_FILE:-}"
EXTRA_DOCKER_ARGS="${EXTRA_DOCKER_ARGS:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[deploy-staging] docker is required on remote host." >&2
  exit 1
fi

echo "[deploy-staging] Logging into GHCR..."
echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin >/dev/null

echo "[deploy-staging] Pulling image ${IMAGE_REF}..."
docker pull "${IMAGE_REF}"

previous_image=""
if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  previous_image="$(docker inspect --format '{{.Config.Image}}' "${CONTAINER_NAME}" || true)"
  echo "[deploy-staging] Stopping existing container ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null || true
fi

run_new_container() {
  local image_ref="$1"
  local -a cmd
  cmd=(docker run -d --name "${CONTAINER_NAME}" --restart unless-stopped -p "${HOST_PORT}:8013")
  if [[ -n "${ENV_FILE}" ]]; then
    cmd+=(--env-file "${ENV_FILE}")
  fi
  if [[ -n "${EXTRA_DOCKER_ARGS}" ]]; then
    # shellcheck disable=SC2206
    local extra_parts=(${EXTRA_DOCKER_ARGS})
    cmd+=("${extra_parts[@]}")
  fi
  cmd+=("${image_ref}")
  "${cmd[@]}"
}

echo "[deploy-staging] Starting new container ${CONTAINER_NAME}..."
if ! run_new_container "${IMAGE_REF}" >/dev/null; then
  echo "[deploy-staging] Failed to start new container from ${IMAGE_REF}." >&2
  if [[ -n "${previous_image}" ]]; then
    echo "[deploy-staging] Rolling back to previous image: ${previous_image}"
    docker rm -f "${CONTAINER_NAME}" >/dev/null || true
    run_new_container "${previous_image}" >/dev/null
    echo "[deploy-staging] Rollback succeeded."
  fi
  exit 1
fi

echo "[deploy-staging] Deployment succeeded."
