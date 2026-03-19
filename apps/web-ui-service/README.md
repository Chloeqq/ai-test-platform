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

## JWT 认证

- 登录接口：`POST /api/auth/login`
- 获取当前用户：`GET /api/auth/me`（`Authorization: Bearer <token>`）
- 启动时会自动初始化默认管理员账号（环境变量可配置）：
  - `ADMIN_USERNAME`（默认 `admin`）
  - `ADMIN_PASSWORD`（默认 `admin123`）
  - `ADMIN_ROLE`（默认 `admin`）
