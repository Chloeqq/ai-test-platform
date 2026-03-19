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
./.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013 --reload
```

## 默认开发数据库

- SQLite（默认）：`sqlite:////Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/dev.db`（运行时按本机绝对路径生成）
- 可通过环境变量覆盖：`DATABASE_URL`
- 开发环境默认允许自动建表：`DATABASE_AUTO_CREATE_TABLES=true`
- Docker / PostgreSQL 环境建议通过 Alembic 迁移建表，并设置：`DATABASE_AUTO_CREATE_TABLES=false`

## 数据库迁移

项目已补齐 Alembic 最小骨架，Web UI 服务可通过下面命令执行迁移：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make db-upgrade
```

如果数据库里已经存在历史 `create_all` 或旧版表结构，没有 `alembic_version`，先执行：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make db-bootstrap
```

这个命令会：

1. 空库时直接执行 `upgrade head`
2. 已有 Alembic 版本表时执行 `upgrade head`
3. 遇到旧库但没有版本号时，先补齐当前托管表，再 `stamp head`

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
- 启动时会自动初始化默认管理员账号（环境变量可配置）：
  - `ADMIN_USERNAME`（默认 `admin`）
  - `ADMIN_PASSWORD`（默认 `admin123`）
  - `ADMIN_ROLE`（默认 `admin`）
