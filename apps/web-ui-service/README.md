# Web UI Service (FastAPI)

当前后端已切换为 FastAPI 项目骨架，目录如下：

```text
apps/web-ui-service/
├── app/
│   ├── main.py
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   └── core/
└── requirements.txt
```

## 本地运行

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
./.venv/bin/pip install -r apps/web-ui-service/requirements.txt
./.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8014 --reload
```

## 前端（TypeScript + React）

仓库已新增 `apps/web-ui-service/frontend`（Vite + React + TypeScript）作为统一前端主工程，前端页面按模块逐步迁移到该主工程。

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make frontend-install
make frontend-dev
```

构建到 FastAPI 静态目录：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make frontend-build
```

构建后入口：

- `http://127.0.0.1:8013/react`
- `http://127.0.0.1:8013/execution/runs`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/react/execution/runs`
- `http://127.0.0.1:8013/execution/results`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/react/execution/results`
- `http://127.0.0.1:8013/ai-generation`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/react/ai-generation`
- `http://127.0.0.1:8013/ai-generation/history`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/ai-generation/prompts`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/execution/plans`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/dashboard`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/quality/flaky`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/quality/failure-clusters`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/quality/trends`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/quality/gates`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/defects`（主入口，307 到 React 页面）
- `http://127.0.0.1:8013/settings/scheduler`（主入口，307 到 React 页面）

## 默认开发数据库

- SQLite（默认）：`sqlite:////Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/dev.db`（运行时按本机绝对路径生成）
- 可通过环境变量覆盖：`DATABASE_URL`
- 开发环境默认允许自动建表：`DATABASE_AUTO_CREATE_TABLES=true`
- 非开发环境不会再默认启用自动建表或默认管理员初始化，缺少安全配置会在启动时直接失败
- Docker / PostgreSQL 环境建议通过 Alembic 迁移建表，并显式设置：`DATABASE_AUTO_CREATE_TABLES=false`

## 数据库迁移

已受管数据库可通过下面命令执行增量迁移：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make db-upgrade
```

新建空数据库必须通过确定性 bootstrap 初始化：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make db-bootstrap
```

这个命令会：

1. 空库时创建冻结在 `20260713_121000` 的静态 schema；
2. 结构 fingerprint 校验成功后才 `stamp 20260713_121000`，再执行后续增量迁移；
3. 已有合法 Alembic 版本的数据库执行 `upgrade head`；
4. 有用户表但没有版本、版本不存在于仓库、或版本与关键 schema 不一致时明确失败，等待人工接管。

不要用裸命令初始化空库：

```bash
alembic upgrade head
```

该命令默认会被拒绝，以避免触发历史动态 metadata migration。仅在明确的 legacy 维护操作中，才允许临时设置默认关闭的：

```bash
ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE=1
```

Docker 和共享环境不得默认设置该变量。

新增迁移版本：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make db-revision MSG="add new table"
```

当前迁移入口位于：

- [alembic.ini](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/alembic.ini)
- [migrations/env.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/migrations/env.py)

## JWT 认证

- 登录接口：`POST /api/auth/login`
- 获取当前用户：`GET /api/auth/me`（`Authorization: Bearer <token>`）
- 开发环境下会使用默认管理员种子账号；生产或其他非开发环境必须显式配置：
  - `JWT_SECRET_KEY`
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `ADMIN_ROLE`
