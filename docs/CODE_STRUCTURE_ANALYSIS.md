| 项目 | 核心模块划分 |
| --- | --- |
| 前端 | `apps/web-ui-service/frontend/src/App.tsx`、`apps/web-ui-service/frontend/src/pages/*`、`apps/web-ui-service/frontend/src/api/*` |
| 后端 | `apps/web-ui-service/app/main.py`、`apps/web-ui-service/app/routers/*`、`apps/web-ui-service/app/services/*`、`apps/web-ui-service/app/models/*` |
| AI逻辑 | `apps/ai-orchestrator/src/app.py`、`apps/ai-orchestrator/src/orchestrator_service.py`、`apps/ai-orchestrator/src/services/*`、`agents/*`、`shared_backend/*` |
| 配置 | `apps/web-ui-service/app/core/config.py`、`docker-compose.yml`、`Dockerfile`、`infra/nginx/default.conf`、`.github/workflows/tests.yml` |
| 数据 | `apps/web-ui-service/migrations/*`、`assets/page-objects/*`、`runners/web-playwright-python/schemas/*`、`reports/*`、`web-ui/state/*` |

| 项目 | 主流程调用链（3个关键文件） |
| --- | --- |
| 需求生成与执行主链 | `apps/web-ui-service/frontend/src/pages/AiGenerationPage.tsx` → `apps/web-ui-service/app/routers/workbench_generation.py` → `apps/ai-orchestrator/src/orchestrator_service.py` |

| 标记 | 文件名 |
| --- | --- |
| 可废弃 | `structure.txt` |
| 可废弃 | `web-ui/state/default/history.json` |
| 可废弃 | `web-ui/state/default/runtime-runs.json` |
| 重复 | `apps/web-ui-service/app/services/workbench_generation_service.py` |
| 重复 | `apps/web-ui-service/app/services/workbench_generation_api/full_chain_service.py` |
| 重复 | `shared_backend/execution_compiler.py` |
| 重复 | `apps/web-ui-service/app/services/workbench_generation_compiler/execution_compiler.py` |
| 未使用 | `apps/web-ui-service/app/services/ui_static_management_page_service.py` |
