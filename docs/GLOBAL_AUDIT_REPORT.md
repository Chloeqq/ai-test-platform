# AI Test Platform — 全局代码审查报告

> 版本：v1.0 ｜ 审查日期：2026-04-15 ｜ 审查范围：全仓库

---

## 一、问题总览统计

### 1.1 按严重级别

| 级别 | 数量 | 占比 | 说明 |
|------|------|------|------|
| **P0 — 严重** | 3 | 5.4% | 认证缺失、权限提升、服务裸奔 |
| **P1 — 高** | 22 | 39.3% | 安全暴露、功能缺失、CI 缺口、架构债务 |
| **P2 — 中** | 21 | 37.5% | 死代码、命名混乱、依赖不一致、产物追踪 |
| **P3 — 低** | 10 | 17.9% | 文档过时、TODO 残留、空目录、命名美化 |
| **合计** | **56** | 100% | |

### 1.2 按问题维度

| 维度 | P0 | P1 | P2 | P3 | 合计 | 占比 |
|------|----|----|----|----|------|------|
| 安全与认证 | 3 | 5 | 3 | 0 | **11** | 19.6% |
| 功能重叠/冲突 | 0 | 4 | 3 | 1 | **8** | 14.3% |
| 目录结构 | 0 | 2 | 3 | 3 | **8** | 14.3% |
| 依赖与构建 | 0 | 4 | 3 | 0 | **7** | 12.5% |
| CI/CD | 0 | 4 | 1 | 1 | **6** | 10.7% |
| 死代码/冗余 | 0 | 0 | 6 | 2 | **8** | 14.3% |
| 代码质量 | 0 | 3 | 2 | 3 | **8** | 14.3% |
| **合计** | **3** | **22** | **21** | **10** | **56** | 100% |

### 1.3 按处理状态

| 状态 | 数量 | 占比 |
|------|------|------|
| 待修复 | 56 | 100% |
| 已修复（上一轮管线整改） | 13 | （不计入本轮） |

---

## 二、完整问题清单

### 2.1 安全与认证（11 项）

| 编号 | 级别 | 问题 | 文件 | 行号 |
|------|------|------|------|------|
| SEC-01 | P0 | 大部分 API 端点无 JWT 认证，`get_current_user` 仅用于 `/api/auth/me` | `apps/web-ui-service/app/routers/test_cases.py`, `workbench_*.py` 等全部 router | — |
| SEC-02 | P0 | 注册接口允许客户端指定任意角色（可提权为 admin） | `apps/web-ui-service/app/routers/auth.py` | 24–35 |
| SEC-03 | P0 | Orchestrator 全部端点无认证，`/orchestrate`、资产变更等敏感 POST 完全开放 | `apps/ai-orchestrator/src/app.py` | 154–186 |
| SEC-04 | P1 | 基础设施端口全暴露：PostgreSQL 5432、Redis 6379、ES 19200、Kibana 15601 | `docker-compose.yml` | 32–144 |
| SEC-05 | P1 | Elasticsearch 关闭安全 `xpack.security.enabled: "false"` | `docker-compose.yml` | 121–124 |
| SEC-06 | P1 | 全量代码 bind-mount 到容器（`.:/app`），容器逃逸可读写整棵代码树 | `docker-compose.yml` | 34, 67 |
| SEC-07 | P1 | Allure 报告静态目录 `/allure` 无认证保护 | `apps/web-ui-service/app/main.py` | 56–62 |
| SEC-08 | P1 | Flask 500 返回异常明文 `str(exc)`，泄露内部路径和堆栈 | `apps/ai-orchestrator/src/app.py` | 79–83 |
| SEC-09 | P2 | 多处硬编码弱密码 `macro123`、`admin123` | `.env.example:5`, `workbench_analysis_service.py:713`, `agent.py:129`, `check_web_ui_pages.py:27` | — |
| SEC-10 | P2 | `.env.docker` 未加入 `.gitignore`，可能被意外提交 | `.gitignore` | 13–14 |
| SEC-11 | P2 | `setup_sql`/`assert_sql` 字段为用户可控，存储后若未来执行存在 SQL 注入风险 | `apps/web-ui-service/app/models/test_case.py` | 35, 42 |

### 2.2 功能重叠与冲突（8 项）

| 编号 | 级别 | 问题 | 文件 |
|------|------|------|------|
| OVL-01 | P1 | 两套 Case API 并存：`/api/workbench/cases*`（YAML/资产）vs `/api/test-cases*`（DB 树） | `workbench_assets.py` vs `test_cases.py` |
| OVL-02 | P1 | 前端调用 3 个不存在的后端端点：`/events`、`/analysis`、`/heal-and-rerun` | `static/workbench_runs.js` → `workbench_runs.py` |
| OVL-03 | P1 | 历史兼容 router 曾定义真实路由但未挂载 — 死 HTTP 表面（已清理） | `app/api/workbench/router.py` |
| OVL-04 | P1 | 多层 import 别名链导致同一 symbol 多路径可达（已收口） | `app/api/workbench/` 下 `facade.py`、`store.py`、`schemas.py` |
| OVL-05 | P2 | State Store 多级委托导致语义分散（已收口） | `state_store.py` / `api/workbench/store.py` |
| OVL-06 | P2 | 双重 Health 端点：`GET /health`（router）vs `GET /health/ready`（main.py 直定义），文档未区分 | `routers/health.py` + `main.py` |
| OVL-07 | P2 | `/api/auth/register` 无前端调用（`login.js` 只用 login） | `routers/auth.py` |
| OVL-08 | P3 | `workbench_generation_service.py` 与 `workbench_generation_api/` 边界模糊，`context.py` 同时依赖两者 | `services/` 下两个 generation 模块 |

### 2.3 目录结构（8 项）

| 编号 | 级别 | 问题 | 路径 |
|------|------|------|------|
| DIR-01 | P1 | 三个 "web-ui" 目录：`apps/web-ui-service/`、`apps/web-ui/`、`web-ui/` | 仓库根 + apps/ |
| DIR-02 | P1 | 文档路径错误：`project-structure.md` 写 `apps/shared_backend/`，实际在 `shared_backend/` | `docs/architecture/project-structure.md` |
| DIR-03 | P2 | Orchestrator 10+ 空目录：`adapters/`、`controllers/`、`workflows/` 等，无 `__init__.py` | `apps/ai-orchestrator/src/` |
| DIR-04 | P2 | 根目录散落 `datetime_compat.py`，应归入 `shared_backend/` | 仓库根 |
| DIR-05 | P2 | 已追踪的生成产物：`dev.db`、`reports/telemetry/*.jsonl` 需 `git rm --cached` | `apps/web-ui-service/dev.db`, `reports/telemetry/` |
| DIR-06 | P3 | `artifacts/` 目录为空占位 | 仓库根 |
| DIR-07 | P3 | `apps/web-ui/` 与 `web-ui/` 重复（均只有 `state/`） | 两个 state 目录 |
| DIR-08 | P3 | Agent 目录用连字符（`test-design-agent`），Python 导入用下划线 — 需 `sys.path` 黑魔法衔接 | `agents/*/` |

### 2.4 依赖与构建（7 项）

| 编号 | 级别 | 问题 | 文件 |
|------|------|------|------|
| DEP-01 | P1 | `ruff`/`mypy` 被 static-baseline 依赖但未出现在任何 `requirements*.txt` | 所有 `requirements*.txt` |
| DEP-02 | P1 | `make install-dev` 只装 `requirements-dev.txt`，不装 web-ui/orchestrator 应用依赖 | `Makefile:47-48` |
| DEP-03 | P1 | Orchestrator Dockerfile 用 `python:3.13-slim` + Playwright 但无 `--with-deps`，构建脆弱 | `apps/ai-orchestrator/Dockerfile` |
| DEP-04 | P1 | Postgres healthcheck 硬编码 `pg_isready -U aitest`，不跟随 `POSTGRES_USER` 环境变量 | `docker-compose.yml` |
| DEP-05 | P2 | PyYAML 版本策略不一致：dev 精确钉 `==6.0.2`，web-ui 范围钉 `>=6.0,<7.0` | 5 个 requirements 文件 |
| DEP-06 | P2 | Docker Compose Kibana / Logstash 无 healthcheck | `docker-compose.yml` |
| DEP-07 | P2 | Root Dockerfile 合并安装 dev + web-ui 依赖，镜像臃肿且隐藏缺失 | `Dockerfile` |

### 2.5 CI/CD（6 项）

| 编号 | 级别 | 问题 | 文件 |
|------|------|------|------|
| CI-01 | P1 | PR/push 只跑 `test-pipeline-contracts` + `static-baseline`，漏掉 `test-orchestrator`、`test-runner-assets`、`test-*-manifest-strict` | `.github/workflows/tests.yml` |
| CI-02 | P1 | 架构守卫重复执行：独立步骤跑一次，`static-baseline.sh` 内部又跑一次 | `tests.yml` + `run-static-baseline.sh` |
| CI-03 | P1 | Self-hosted E2E runner 无 `actions/setup-python`，Python 版本不受控 | `tests.yml` e2e-smoke/generated jobs |
| CI-04 | P1 | `build-image.yml` 只构建 web 镜像，不构建 orchestrator 镜像 | `.github/workflows/build-image.yml` |
| CI-05 | P2 | Pre-commit 与 CI 不对齐：hooks 只有 asset-contracts 和 architecture-guard，无 ruff/mypy/pytest | `.pre-commit-config.yaml` |
| CI-06 | P3 | `asset-tool-help` 未加入 Makefile `.PHONY` | `Makefile:1` |

### 2.6 死代码与冗余（8 项）

| 编号 | 级别 | 问题 | 文件 |
|------|------|------|------|
| DEAD-01 | P2 | `normalize_ai_status` 从未被调用 | `shared_backend/state_machines.py:49` |
| DEAD-02 | P2 | `validate_state_transition` 从未被调用 | `shared_backend/state_machines.py` |
| DEAD-03 | P2 | `execution_pipeline.py` 整模块无人引用（`run_ir_with_mapping` 完全断链） | `shared_backend/execution_pipeline.py` |
| DEAD-04 | P2 | `compile_playwright_python` 无外部调用者 | `shared_backend/execution_compiler.py` |
| DEAD-05 | P2 | `runtime/persistence.py` 的 `persist_case_and_state` 无人导入 | `workbench_generation_compiler/runtime/persistence.py` |
| DEAD-06 | P2 | `ir/`、`normalization/`、`mapping/` 子包无外部消费者，属孤立子树 | `workbench_generation_compiler/` |
| DEAD-07 | P3 | `__all__` 导出 10+ 无外部消费的符号（`IRSchemaValidator`、`PageObjectRegistry` 等） | `shared_backend/__init__.py` |
| DEAD-08 | P3 | `attach_ai_trace_context` 导出但无外部调用 | `shared_backend/observability/` |

### 2.7 代码质量（8 项）

| 编号 | 级别 | 问题 | 文件 |
|------|------|------|------|
| QUAL-01 | P1 | 20+ 处 `sys.path.insert` 操纵 | orchestrator、agents、runner、scripts 等 |
| QUAL-02 | P1 | `importlib.util.spec_from_file_location` 动态加载模块 | `orchestrator_service.py` |
| QUAL-03 | P1 | 存在 `from x import *` 通配符导入 | `workbench/facade.py`, `workbench/schemas.py`, `execution_compiler.py` |
| QUAL-04 | P2 | `ExecutionCompilerError` vs `ExecutionCompileError` 命名差一词易混淆 | `shared_backend/execution_compiler.py:1070` |
| QUAL-05 | P2 | 多处 `except Exception` 吞异常不记日志 | `generate_pipeline.py:73`, `execution_compiler.py:1061`, `contracts.py:80` 等 |
| QUAL-06 | P3 | 产品代码残留 TODO 注释 | `test_case_data_service.py:224,269` |
| QUAL-07 | P3 | 关键 pipeline 入口使用 `Callable[..., ...]` 弱类型标注 | `generate_pipeline.py:18-25` |
| QUAL-08 | P3 | `get_dictionary_items` 被使用但不在 `__all__` 中，API 不一致 | `shared_backend/__init__.py` |

---

## 三、统计图表

### 3.1 按维度分布

```
安全与认证  ████████████████████  11 (19.6%)
功能重叠    ██████████████        8 (14.3%)
目录结构    ██████████████        8 (14.3%)
依赖构建    ████████████          7 (12.5%)
CI/CD       ██████████            6 (10.7%)
死代码      ██████████████        8 (14.3%)
代码质量    ██████████████        8 (14.3%)
```

### 3.2 按严重级别分布

```
P0 严重  ██████                 3 ( 5.4%)  ← 必须立即处理
P1 高    ████████████████████  22 (39.3%)  ← 短期处理
P2 中    ██████████████████    21 (37.5%)  ← 中期处理
P3 低    ██████████            10 (17.9%)  ← 排期处理
```

### 3.3 修复工作量估算

| 阶段 | 级别 | 数量 | 估计人天 | 说明 |
|------|------|------|----------|------|
| Phase A：紧急止血 | P0 | 3 | 2–3 天 | 认证保护、角色白名单、Orchestrator API Key |
| Phase B：短期加固 | P1 | 22 | 5–8 天 | 端口收敛、CI 补齐、缺失端点、依赖声明、sys.path 治理 |
| Phase C：中期清理 | P2 | 21 | 5–7 天 | 死代码删除、目录合并、版本统一、异常处理 |
| Phase D：打磨收尾 | P3 | 10 | 2–3 天 | 文档更新、TODO 清理、空目录删除、命名美化 |
| **合计** | | **56** | **14–21 天** | |

---

## 四、推荐修复优先序

### Phase A — 紧急（1–3 天）

```
SEC-01  给所有写操作 API 加 JWT 依赖
SEC-02  /api/auth/register 增加角色白名单 (允许 viewer / tester, 禁止 admin)
SEC-03  Orchestrator 增加 API Key / Token 认证中间件
```

### Phase B — 短期（1–2 周）

```
安全:    SEC-04~08  端口收敛 + ES 安全 + 异常脱敏
功能:    OVL-01~03  合并双 Case API + 补齐 3 个缺失端点 + 清理 legacy router
CI:      CI-01~04   补齐 test-contracts 全集 + 去重守卫 + Python 版本钉 + orchestrator 镜像构建
依赖:    DEP-01~04  requirements 补齐 ruff/mypy + install-dev 完善 + Dockerfile 修复
质量:    QUAL-01~03 sys.path 治理 + importlib 替代 + star-import 消除
```

### Phase C — 中期（2–3 周）

```
目录:    DIR-01~05  三合一 web-ui + 文档修正 + 空目录清理 + git rm 产物
死代码:  DEAD-01~06 删除无引用函数/模块/子包
依赖:    DEP-05~07  统一版本策略 + healthcheck 补齐
功能:    OVL-04~07  import 链扁平化 + state store 层级精简
质量:    QUAL-04~05 命名统一 + 异常日志补齐
```

### Phase D — 收尾（排期处理）

```
DIR-06~08  清理空目录 + 统一命名约定
DEAD-07~08 __all__ 瘦身
QUAL-06~08 TODO 清理 + 类型标注 + API 一致性
CI-05~06   Pre-commit 对齐 + Makefile .PHONY
OVL-08     Generation 服务边界文档化
```

---

## 五、与上一轮整改的关系

上一轮管线整改（13 项，已全部完成）聚焦于 **测试用例生成管线的 5 大根因**（字段不一致、双源冲突、降级控制等）。

本轮全局审查发现的 56 项问题覆盖更广：
- **无交集项**：安全认证（SEC）、CI 缺口（CI）、死代码（DEAD）、依赖管理（DEP）均为新发现
- **有关联项**：目录结构（DIR）、功能重叠（OVL）在上轮扫描中有提及但未纳入整改范围
- **互补关系**：上轮修复了 **管线数据流** 问题，本轮发现的是 **基础设施和工程治理** 问题

---

*审查完成。共发现 56 项问题，按 P0(3)/P1(22)/P2(21)/P3(10) 分级。建议按 Phase A→D 顺序处理。*
