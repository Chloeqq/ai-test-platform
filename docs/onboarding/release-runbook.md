# Release Runbook (CI/CD v1)

## 1. Workflows

- CI quality gate: [`Tests`](../../.github/workflows/tests.yml)
  - default on `pull_request/push`: `make static-baseline`
- Image build: [`Build Image`](../../.github/workflows/build-image.yml)
  - on `main/master` push and manual trigger
- Staging deploy: [`Deploy Staging`](../../.github/workflows/deploy-staging.yml)
  - auto after successful image build on `main/master`
  - manual trigger supports `image_ref`

## 2. Required GitHub Secrets

For staging deployment:

- `STAGING_HOST`: staging server hostname or IP
- `STAGING_USER`: SSH user on staging host
- `STAGING_SSH_PRIVATE_KEY`: private key content (PEM/OpenSSH)
- `STAGING_SSH_PORT` (optional): defaults to `22`
- `STAGING_APP_DIR` (optional): defaults to `/opt/ai-test-platform`
- `STAGING_CONTAINER_NAME` (optional): defaults to `ai-test-platform-staging`
- `STAGING_HOST_PORT` (optional): defaults to `8013`
- `STAGING_CONTAINER_PORT` (optional): defaults to `8013`
- `STAGING_ENV_FILE` (optional): env file path on remote host
- `STAGING_HEALTHCHECK_URL` (optional): defaults to `http://$STAGING_HOST:$STAGING_HOST_PORT/health`
- `GHCR_DEPLOY_USERNAME` (optional): required when package is private
- `GHCR_DEPLOY_TOKEN` (optional): required when package is private (`read:packages`)

## 3. Normal Release Flow

1. Open PR and wait for `Tests` workflow (`static-baseline`) to pass.
2. Merge into `main`.
3. `Build Image` pushes `ghcr.io/<owner>/<repo>:sha-<commit>`.
4. `Deploy Staging` pulls that image and restarts staging container.
5. Post-deploy healthcheck calls `/health`.

## 4. Manual Staging Deploy

Use `Deploy Staging` -> `Run workflow`:

- Leave `image_ref` empty to deploy current commit SHA image.
- Set `image_ref` to roll forward/backward to a specific tag.
- Keep `run_healthcheck=true` unless debugging.

## 5. Rollback

Run `Deploy Staging` manually with a previous immutable image tag, for example:

- `ghcr.io/<owner>/<repo>:sha-<older-commit-sha>`

This redeploys the previous container image and re-runs healthcheck.

