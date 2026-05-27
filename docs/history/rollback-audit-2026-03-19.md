# 回退巡检报告（2026-03-19）

## 已恢复

1. `apps/ai-orchestrator/src/app.py`
   - 恢复 ASGI 入口：`flask_app = create_app()` + `app = WSGIMiddleware(flask_app)`。
   - 结果：`uvicorn app:app` 可启动，`http://127.0.0.1:8000/health` 可用。

2. `apps/web-ui-service/app/routers/legacy_workbench.py`
   - 恢复 `POST /api/workbench/runs/{run_id}/heal-and-rerun`。
   - 补齐 `_find_run_item` / `_wait_run_terminal`，支持“修复+重跑+等待终态”。

3. `apps/web-ui-service/app/static/workbench.js`
   - 恢复工作台按钮调用 `heal-and-rerun`，不是旧的单独 `/heal`。

4. `apps/web-ui-service/app/templates/workbench.html`
   - 按钮文案恢复为：`一键修复+重跑`。

5. `apps/web-ui-service/app/core/config.py`
   - 恢复 `orchestrator_url` 配置项（默认 `http://127.0.0.1:8000`）。

## 已确认仍有效（未回退）

1. `apps/web-ui-service/app/main.py`
   - `/allure-snapshots` 静态挂载存在。
   - Allure 响应防缓存中间件存在。

2. `apps/web-ui-service/app/routers/legacy_workbench.py`
   - 运行命令含 `--alluredir`。
   - `POST /api/report/allure/refresh` 存在。
   - Allure 快照索引路径 `"/allure-snapshots/{version}/index.html"` 存在。

3. `apps/web-ui-service/app/templates/report_allure.html` + `app/static/report_allure.js`
   - 强制刷新按钮、版本化加载逻辑存在。

## 仍需关注（疑似“能力回退”而非单点 bug）

1. `apps/ai-orchestrator/src/asset_service.py`
   - 当前只保留基础资产读写能力，未见 URL 级 Page Object 生成链路的 SSRF 防护函数与线程封装逻辑。
   - 如果目标仍是“从页面 URL 自动抽取元素并生成 Page Object”，需补回对应实现与安全校验。

2. 技术栈一致性
   - 当前 `ai-orchestrator` 仍是 Flask 内核 + ASGI 包装，并非原计划的原生 FastAPI 服务。
   - 若目标是“两个服务都原生 FastAPI”，需单独排期迁移。

## 验证快照

- `http://127.0.0.1:8000/health`：`{"status":"ok"}`
- `http://127.0.0.1:8013/openapi.json`：包含
  - `/api/workbench/runs/{run_id}/heal-and-rerun`
  - `/api/report/allure/refresh`
