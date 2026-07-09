# Docker Compose 部署流程 Runbook

## 目标

本文档记录 AI 质量保障平台在本地或单机服务器上通过 `docker compose` 部署的标准流程，覆盖构建、启动、健康检查、访问入口、常用运维命令和排障记录。

适用范围：

- `web-ui-service` 平台主站与执行桌面
- `ai-orchestrator` 编排服务
- `postgres`、`redis`
- `nginx` 网关
- `elasticsearch`、`kibana`、`logstash` 日志链路

## 当前部署结果

最近一次部署时间：2026-05-16

部署命令使用：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build web
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build
```

验证结果：

- `postgres`：healthy
- `redis`：healthy
- `orchestrator`：healthy
- `web`：healthy
- `nginx`：running
- `elasticsearch`：healthy
- `kibana`：healthy
- `logstash`：healthy
- `http://127.0.0.1:8013/health/ready`：HTTP 200
- `http://127.0.0.1:8000/health`：HTTP 200
- `http://127.0.0.1:6080/vnc.html`：HTTP 200

最终复核结果：

- 复核时间：2026-05-16
- `docker compose --env-file .env.docker ps`：核心服务与 ELK 服务均已启动，除 `nginx` 无 healthcheck 外，其余服务均为 `healthy`。
- 平台 readiness：`status=ok`，`database.ok=true`，`redis.ok=true`，`orchestrator.ok=true`。
- Elasticsearch 集群：HTTP 200，单节点状态为 `yellow`，原因是副本分片在单节点环境无法分配；这不影响本地单机部署可用性。

## 前置条件

1. 本机已安装 Docker Desktop 或 Docker Engine。

2. Docker Compose 可用：

```bash
docker compose version
```

3. 仓库根目录存在 `.env.docker`。

4. 确认 `.env.docker` 中的敏感配置已经按目标环境替换，不要在生产环境使用示例密码。

关键配置：

```env
DATABASE_URL=postgresql+psycopg2://...
POSTGRES_DB=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
JWT_SECRET_KEY=...
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
BASE_URL=http://localhost:8013/login#/login
TEST_USERNAME=...
TEST_PASSWORD=...
ORCHESTRATOR_API_KEY=...
DOCKER_OPENAI_API_KEY=...
DOCKER_OPENAI_BASE_URL=...
DOCKER_OPENAI_MODEL=...
```

被测系统 URL 映射配置：

```env
RUNNER_LOOPBACK_HOST=
RUNNER_URL_REWRITE_MAP=http://localhost:5174=http://host.docker.internal:5174;http://127.0.0.1:5174=http://host.docker.internal:5174
```

说明：

- 默认不改写绝对被测 URL，避免把 `http://localhost:5174/#/login` 误替换成平台自身。
- 如果 Docker 容器需要访问宿主机上的被测前端，应显式配置 `RUNNER_URL_REWRITE_MAP`，例如 `http://localhost:5174=http://host.docker.internal:5174`。
- 配置映射前必须先确认容器内能访问目标地址。
- 当前本地 Docker 部署已配置 `localhost:5174` 与 `127.0.0.1:5174` 到 `host.docker.internal:5174` 的映射，确保容器内 Playwright 能访问宿主机上的 mall-admin-web。

## 标准部署流程

### 1. 进入仓库根目录

```bash
cd /Users/bettyhuang/PycharmProjects/ai-quality-platform
```

### 2. 校验 Compose 配置

```bash
docker compose --env-file .env.docker config --quiet
```

如果本机 Docker Buildx 写入 `~/.docker/buildx/activity` 报权限错误，使用可写的临时 Buildx 配置目录：

```bash
mkdir -p /private/tmp/ai-quality-platform-buildx
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker config --quiet
```

### 3. 构建业务镜像

推荐先单独构建业务镜像，再启动服务：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build orchestrator web
```

说明：

- 首次构建 `web` 镜像会安装 Playwright Chromium、FFmpeg 和 Headless Shell。
- 首次下载浏览器资源可能需要 10 到 20 分钟。
- 如果构建中断，可以重新执行同一条 build 命令，Docker 会复用已完成的缓存层。

### 4. 启动服务

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build
```

如果明确需要边构建边启动，也可以使用：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --build
```

## 后端重启与镜像刷新

更新时间：2026-05-18

适用场景：

- 仅需重启后端进程。
- 本地代码或前端静态包已经变更，需要让 Docker 中的 `web` 服务加载新镜像。
- 修改了 `apps/web-ui-service` 后端、React 前端、静态资源或执行桌面相关脚本。

### 1. 查看当前服务状态

```bash
docker compose --env-file .env.docker ps
```

### 2. 仅重启后端容器

如果只是环境变量已在容器内生效、数据库短暂异常恢复、或需要重启后端进程，可以执行：

```bash
docker compose --env-file .env.docker restart web
```

注意：

- 当前 `docker-compose.yml` 没有把后端源码目录挂载进 `web` 容器。
- 因此本地代码变更后，只执行 `restart web` 不会让代码改动生效。
- 代码变更必须执行“重新构建 web 镜像并重建容器”。

### 3. 重新构建 web 镜像

本机 Docker Buildx 如果遇到 `~/.docker/buildx/activity` 权限问题，统一使用可写临时目录：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build web
```

### 4. 用新镜像重建后端并刷新 nginx

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build web nginx
docker compose --env-file .env.docker restart nginx
```

说明：

- `up -d --no-build web nginx` 会使用刚构建好的 `ai-quality-platform-web-ui` 镜像重建 `web` 容器。
- `restart nginx` 用于刷新反向代理连接，避免旧 upstream 连接残留。
- `postgres`、`redis`、`orchestrator` 不会被重建，只会作为依赖保持运行。

### 5. 健康检查

检查 Compose 服务：

```bash
docker compose --env-file .env.docker ps web nginx postgres redis orchestrator
```

检查平台入口：

```bash
curl -sS -o /tmp/ai-platform-ready.json -w '%{http_code}' http://127.0.0.1:8013/health/ready
cat /tmp/ai-platform-ready.json
```

检查后端直连端口：

```bash
curl -sS -o /tmp/ai-platform-web-ready.json -w '%{http_code}' http://127.0.0.1:8015/health/ready
cat /tmp/ai-platform-web-ready.json
```

期望结果：

```text
HTTP 200
status=ok
database.ok=true
redis.ok=true
orchestrator.ok=true
```

### 6. 本次执行记录

执行时间：2026-05-18

实际执行命令：

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker restart web
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build web
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build web nginx
docker compose --env-file .env.docker restart nginx
docker compose --env-file .env.docker ps web nginx postgres redis orchestrator
curl -sS -o /tmp/ai-platform-ready.json -w '%{http_code}' http://127.0.0.1:8013/health/ready
curl -sS -o /tmp/ai-platform-web-ready.json -w '%{http_code}' http://127.0.0.1:8015/health/ready
```

本次验证结果：

- `web`：healthy
- `nginx`：running
- `postgres`：healthy
- `redis`：healthy
- `orchestrator`：healthy
- `http://127.0.0.1:8013/health/ready`：HTTP 200
- `http://127.0.0.1:8015/health/ready`：HTTP 200

### 5. 查看容器状态

```bash
docker compose --env-file .env.docker ps
```

期望状态：

- `postgres`、`redis`、`orchestrator`、`web`、`elasticsearch`、`kibana`、`logstash` 最终为 `healthy`。
- `nginx` 没有 healthcheck，状态为 `running` 即可。

## 访问入口

| 能力 | 地址 |
|---|---|
| 平台主入口 | `http://127.0.0.1:8013` |
| Web 服务直连 | `http://127.0.0.1:8015` |
| 健康检查 | `http://127.0.0.1:8013/health/ready` |
| Orchestrator 健康检查 | `http://127.0.0.1:8000/health` |
| noVNC 执行桌面 | `http://127.0.0.1:6080/vnc.html` |
| Elasticsearch | `http://127.0.0.1:19200` |
| Kibana | `http://127.0.0.1:15601` |

## 验收命令

### 平台健康检查

```bash
curl -fsS http://127.0.0.1:8013/health/ready
```

期望返回：

```json
{
  "status": "ok",
  "database": {"ok": true},
  "redis": {"ok": true},
  "orchestrator": {"ok": true}
}
```

### Orchestrator 健康检查

```bash
curl -fsS http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok"}
```

### noVNC 检查

```bash
curl -fsS -o /tmp/novnc.html -w '%{http_code}\n' http://127.0.0.1:6080/vnc.html
```

期望返回 `200`。

### ELK 检查

```bash
curl -fsS http://127.0.0.1:19200
curl -fsS http://127.0.0.1:15601/api/status
```

查看 Elasticsearch 集群状态：

```bash
curl -sS --max-time 20 -w '\nhttp=%{http_code}\n' 'http://127.0.0.1:19200/_cluster/health?pretty'
```

本地单节点部署允许出现：

```json
{
  "status": "yellow",
  "number_of_nodes": 1,
  "number_of_data_nodes": 1,
  "timed_out": false
}
```

说明：

- `yellow` 表示主分片可用，但副本分片未分配。
- 单节点 Elasticsearch 没有第二个节点承载副本，因此这是本地开发部署的常见状态。
- 如果 `timed_out=false` 且 HTTP 状态为 `200`，日志检索链路可继续使用。

## 常用运维命令

### 查看日志

```bash
docker compose --env-file .env.docker logs -f web
docker compose --env-file .env.docker logs -f orchestrator
docker compose --env-file .env.docker logs -f postgres
```

### 重启单个服务

```bash
docker compose --env-file .env.docker restart web nginx
```

### 重新构建并替换 Web 服务

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build web
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build web nginx
```

### 停止服务但保留数据卷

```bash
docker compose --env-file .env.docker down
```

### 清理服务和数据卷

高风险操作，会删除数据库、Redis、Elasticsearch 等持久化数据：

```bash
docker compose --env-file .env.docker down -v
```

执行前必须确认已经备份。

## 数据与持久化

Compose 中的持久化位置：

- `postgres_data`：PostgreSQL 数据
- `redis_data`：Redis 数据
- `elasticsearch_data`：Elasticsearch 数据
- `platform_logs`：平台日志
- `./web-ui/state:/app/web-ui/state`：平台运行状态、执行产物索引
- `./assets/test-cases:/app/assets/test-cases`：测试用例资产

建议备份：

```bash
docker compose --env-file .env.docker exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/ai_quality_platform_backup.sql
tar -czf /tmp/ai-quality-platform-state.tgz web-ui/state assets/test-cases
```

## 常见问题

### 1. `failed to update builder last activity time`

现象：

```text
failed to update builder last activity time: open ~/.docker/buildx/activity/...: operation not permitted
```

处理：

```bash
mkdir -p /private/tmp/ai-quality-platform-buildx
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build web
```

不要把 `DOCKER_CONFIG` 整体切到临时目录，否则可能导致 Docker 找不到 Compose 插件。

### 2. 首次构建 Web 镜像很慢

原因：

- `python -m playwright install --with-deps chromium` 会下载 Chromium、FFmpeg、Headless Shell。
- 资源总量较大，首次构建可能超过 15 分钟。

处理：

- 使用更长的命令超时时间。
- 构建中断后重新执行 build，Docker 会复用已完成缓存层。

### 3. `kibana` 或 `logstash` 长时间 `starting`

说明：

- ELK 链路启动比核心业务服务慢。
- 先确认 `elasticsearch` healthy。

排查：

```bash
docker compose --env-file .env.docker logs --tail 200 kibana
docker compose --env-file .env.docker logs --tail 200 logstash
docker compose --env-file .env.docker ps
```

### 4. `elasticsearch` 启动期反复 `starting`

现象：

- `docker compose ps` 中 `elasticsearch` 短时间显示 `health: starting`。
- 健康检查偶发超时。
- 日志中出现 JVM 慢启动、线程调度延迟或 `clock went backwards`。

说明：

- Elasticsearch 对本机内存和磁盘 IO 较敏感。
- 首次启动或资源紧张时，可能需要数分钟才能稳定。
- 如果最终恢复为 `healthy`，并且 `_cluster/health` 返回 HTTP 200，可以继续使用。

排查：

```bash
docker inspect ai-quality-platform-elasticsearch-1 --format 'restart_count={{.RestartCount}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}'
docker compose --env-file .env.docker logs --tail 200 elasticsearch
```

处理建议：

- 优先给 Docker Desktop 分配更多内存，建议至少 6GB，ELK 全量链路建议 8GB 以上。
- 如果当前只验证平台核心功能，可以先关注 `web/nginx/postgres/redis/orchestrator` 的健康状态。
- 如果生产或准生产使用，应增加 Elasticsearch 节点或关闭副本分片告警的误判逻辑。

### 5. PostgreSQL 启动期提示 `database system is in recovery mode`

现象：

```text
psycopg2.OperationalError: connection to server at "postgres", port 5432 failed:
FATAL: the database system is in recovery mode
```

说明：

- 这是 PostgreSQL 容器启动或恢复 WAL 期间的暂态错误。
- 如果 `postgres` 最终变为 `healthy`，平台 readiness 后续返回 `database.ok=true`，通常无需人工处理。

排查：

```bash
docker compose --env-file .env.docker ps postgres
docker compose --env-file .env.docker logs --tail 200 postgres
curl -fsS http://127.0.0.1:8013/health/ready
```

处理建议：

- 等待 PostgreSQL 恢复完成后再访问平台或执行用例。
- 如果持续失败，先保留数据卷，不要直接 `down -v`，应先导出日志并确认是否需要备份恢复。

### 6. 用例执行访问错被测平台

原则：

- 绝对被测 URL 默认必须原样保留。
- 不允许静默把 `http://localhost:5174/#/login` 改成 `http://localhost:8013/...`。
- AI YAML 用例执行时，runner preflight 应优先读取用例脚本中的 `execution.page_url` 或首个 `goto` 步骤，而不是平台自身 `BASE_URL`。

如果容器访问不到宿主机被测服务，应显式配置映射：

```env
RUNNER_URL_REWRITE_MAP=http://localhost:5174=http://host.docker.internal:5174;http://127.0.0.1:5174=http://host.docker.internal:5174
```

配置后在容器内验证：

```bash
docker compose --env-file .env.docker exec web python - <<'PY'
import urllib.request
with urllib.request.urlopen("http://host.docker.internal:5174/#/login", timeout=5) as response:
    print(response.status, response.geturl())
PY
```

如果仍不可达，需要调整被测前端启动方式，例如使用 `--host 0.0.0.0 --port 5174`。

本次修复记录：

- 失败现象：用例还未进入登录步骤，`ensure_e2e_base_url_reachable` 使用 `BASE_URL=http://localhost:8013/login#/login` 做前置检查，导致检查平台自身而非被测系统。
- 修复动作：runner preflight 改为优先读取 YAML 用例的 `execution.page_url=http://localhost:5174/#/login`，并通过 `RUNNER_URL_REWRITE_MAP` 在容器内映射为 `http://host.docker.internal:5174/#/login`。
- 验收结果：平台接口执行 `mall-web-login-auth-fn-ai-0001` 通过，`run_id=da29d370fabe426c8c8d6b039671d0fd`，runner 返回码为 `0`，并生成执行记录、Allure 报告和 WebM 录屏。

## 回滚策略

本地 Compose 部署没有镜像仓库版本标签时，建议回滚方式为：

1. 使用 Git 切回上一个稳定提交。

2. 重新构建业务镜像：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker build orchestrator web
```

3. 重启服务：

```bash
BUILDX_CONFIG=/private/tmp/ai-quality-platform-buildx docker compose --env-file .env.docker up -d --no-build
```

生产环境建议后续引入镜像标签和远端镜像仓库，例如：

```text
ai-quality-platform-web-ui:2026.05.16-<git-sha>
ai-quality-platform-orchestrator:2026.05.16-<git-sha>
```

## 安全注意事项

- 不要把生产密码、JWT 密钥、LLM API Key 写入版本库。
- `RECORDER_VNC_PASSWORD` 在生产环境必须设置强密码。
- `6080` noVNC 不建议直接暴露公网。
- `5432`、`6379`、`19200`、`15601` 如需开放，必须通过内网、VPN 或网关鉴权保护。
- `docker compose down -v` 会删除持久化数据，执行前必须备份。
