# web-ui (Legacy Compatibility Layer)

`web-ui/` 目录已降级为兼容层，保留历史入口，避免旧脚本失效。

当前真实后端实现已迁移到：

- [apps/web-ui-service](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service)

## 兼容入口

- [app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/app.py)
- [worker.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/worker.py)

说明：

- `app.py` 会转发到 `apps/web-ui-service/app/main.py` 的 FastAPI 应用
- `worker.py` 仅保留停用提示，旧 worker 入口已下线

## 推荐启动方式

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
./.venv/bin/python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013
```
