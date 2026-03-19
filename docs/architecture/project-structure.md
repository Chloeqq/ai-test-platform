# 项目目录分层（前后端）

## 前端

- `apps/web-console/`
  - 静态前端控制台（`index.html` / `app.js` / `styles.css`）
  - 当前由 `ai-orchestrator` 托管

## 后端

- `apps/ai-orchestrator/`
  - AI 编排服务 API
- `apps/web-ui-service/`
  - Web UI 后端服务（FastAPI）
  - `app/main.py` 为应用入口
  - `app/models/` 为数据库模型
  - `app/routers/` 为 API 路由
  - `app/schemas/` 为 Pydantic 模型
  - `app/core/` 为配置和安全模块

## 兼容层

- `web-ui/`
  - 历史路径兼容入口（转发到 `apps/web-ui-service`）
  - 新增后端代码不要再放在这里

## 其他核心目录

- `runners/` 自动化执行引擎
- `assets/` 测试资产（YAML、Page Object、模板）
- `docs/` 架构与产品文档
