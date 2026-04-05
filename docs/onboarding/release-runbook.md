# Release Runbook

本文档用于把当前仓库的 CI/CD 流程快速跑通，覆盖镜像构建、staging 部署、健康检查与回滚。

## 1. 工作流概览

当前 GitHub Actions 工作流：

- [tests.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/tests.yml)
  - 质量门与 E2E 手动触发
- [build-image.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/build-image.yml)
  - 构建并推送 `ghcr.io/<owner>/ai-test-platform-web`
- [deploy-staging.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/deploy-staging.yml)
  - 在 staging 主机拉取镜像并重启容器
  - 自动输出部署摘要（image/container/healthcheck）到 GitHub Step Summary
  - 失败时自动抓取远端 `docker ps` 与 `docker logs` 诊断信息

## 2. GitHub Secrets / Variables

### 2.1 必需 Secrets

`tests.yml`（E2E 手动执行）：

- `BASE_URL`
- `TEST_USERNAME`
- `TEST_PASSWORD`

`deploy-staging.yml`（staging 部署）：

- `STAGING_SSH_HOST`
- `STAGING_SSH_USER`
- `STAGING_SSH_KEY`
- `STAGING_GHCR_USERNAME`
- `STAGING_GHCR_TOKEN`

### 2.2 可选 Secrets

- `STAGING_SSH_PORT`（默认 `22`）

### 2.3 可选 Repository Variables

- `STAGING_CONTAINER_NAME`（默认 `ai-test-platform-web-staging`）
- `STAGING_HOST_PORT`（默认 `8013`）
- `STAGING_ENV_FILE`（例如 `/etc/ai-test-platform/staging.env`）
- `STAGING_EXTRA_DOCKER_ARGS`（例如 `--network host`）
- `STAGING_HEALTHCHECK_URL`（默认自动拼为 `http://<host>:<port>/health/ready`）

## 3. 首次跑通顺序

1. 推送 `dev`，确认 [tests.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/tests.yml) 的 `static-baseline` 通过。
2. 手动触发 `tests.yml` 的 `e2e-smoke`，验证 E2E 凭据有效。
3. 触发 [build-image.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/build-image.yml)（可 push 触发，也可手动触发）。
4. 等 `Build Image` 成功后，触发 [deploy-staging.yml](/Users/bettyhuang/PycharmProjects/ai-test-platform/.github/workflows/deploy-staging.yml)：
   - 可自动由 `workflow_run` 触发；
   - 也可 `workflow_dispatch` 手动指定 `image_ref`。
5. 检查 `Deploy Staging` 最后一步健康检查成功。

## 4. 手工部署（不经 Actions）

可在 staging 主机手工执行：

```bash
export IMAGE_REF="ghcr.io/<owner>/ai-test-platform-web:sha-<commit>"
export GHCR_USERNAME="<ghcr-user>"
export GHCR_TOKEN="<ghcr-token>"
export CONTAINER_NAME="ai-test-platform-web-staging"
export HOST_PORT="8013"
export ENV_FILE="/etc/ai-test-platform/staging.env"

bash scripts/deploy/deploy_staging.sh
```

部署后做健康检查：

```bash
HEALTHCHECK_URL="http://<staging-host>:8013/health/ready" \
scripts/deploy/healthcheck.sh
```

部署脚本会在远端写入最近一次部署元数据（默认路径）：

```bash
/tmp/ai-test-platform-staging-deploy.last
```

## 5. 回滚策略

`deploy_staging.sh` 内置“单步失败回滚”：

- 如果新镜像启动失败，会自动回退到部署前容器镜像。

如果需要人工回滚到指定版本：

1. 在 `deploy-staging.yml` 的 `workflow_dispatch` 输入 `image_ref`（指定旧 tag）。
2. 重新执行一次部署。

## 6. 常见故障排查

### 6.1 `docker login ghcr.io` 失败

- 检查 `STAGING_GHCR_USERNAME` / `STAGING_GHCR_TOKEN`。
- 确保 token 对目标镜像有 pull 权限。

### 6.2 SSH 连接失败

- 检查 `STAGING_SSH_HOST` / `STAGING_SSH_PORT` / `STAGING_SSH_USER`。
- 确认 `STAGING_SSH_KEY` 对应公钥已在主机授权。

### 6.3 部署成功但健康检查失败

- 检查 `STAGING_ENV_FILE` 是否存在、内容是否完整。
- 登录主机执行 `docker logs <container_name>` 查看启动错误。
- 检查 `STAGING_HEALTHCHECK_URL` 是否匹配真实对外地址。
- 查看 `Deploy Staging` workflow 的失败诊断步骤输出（已自动包含远端 `docker ps` 与日志 tail）。
