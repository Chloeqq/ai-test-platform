# CLAUDE.md — AI Test Platform 项目规则

## 架构硬约束

### 分层（不可违反）
```
Router → Facade → Service → Repository → DB
  │        │         │
  │        │         └── 纯业务逻辑，不创建 Session
  │        └── 编排流程，透传 db 参数
  └── HTTP 入口，Depends(get_db) 获取 Session
```

- **Router** 层：`Depends(get_db)` 获取 Session，请求结束自动 commit/close
- **Facade** 层：接收 `db: Session`，透传给 Service 和 Store，**决不自己 `SessionLocal()`**
- **Service** 层：接收 `db: Session`，通过 Repository 访问 DB
- **Repository** 层：唯一允许写 `db.execute(select(...))` 的地方（在方法内部）
- **子进程/后台线程**：可 `get_db_session()` 或 `SessionLocal()` 独立 Session

### 事实源层次
```
第 1 层: test_cases.script_code (DB)     ← 唯一可执行格式，不可绕过
第 2 层: assets/test-cases/*.yaml        ← 从 script_code 派生
第 3 层: web-ui/state/                   ← 可重建缓存（见 state/README.md）
第 4 层: 运行记录 (history/runs/reporting)
```

### DB 访问规则
- **强制使用 Repository**：不允许在 Service/Facade 中直接写 `db.execute(select(Model)...)`
- 6 个 Repository：`TestCaseRepository`, `PageObjectRepository`, `RecorderRepository`, `TestProjectRepository`, `TestDataPoolRepository`（WorkbenchState 通过 `state_store`）
- 共享工具在 `shared_backend/type_utils.py`（`dict_value`, `list_value`, `int_value` 等）

### 异常处理
- `json.loads` → 捕获 `(json.JSONDecodeError, ValueError)`
- `yaml.safe_load` → 捕获 `yaml.YAMLError`
- `except Exception` 仅用于：编排降级、DB 回滚、子进程容错
- 不要新增空的 `except:` 或裸 `except Exception:`

## 核心文件
- `README.md` — 完整架构 + 6 条业务链路 + 数据模型 + 工程约束
- `docs/architecture/2026-05-27_重构执行记录.md` — 全部 6 轮改动记录
- `apps/web-ui-service/app/api/workbench/facade.py` — Workbench 主门面
- `apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py` — 生成管线（6 步骤函数）
- `apps/ai-orchestrator/src/orchestrator_service.py` — AI 编排服务
- `shared_backend/execution_compiler.py` — DSL 编译器（V1.1 铁律）
- `web-ui/state/README.md` — 运行态缓存说明

## 测试
- 运行：`make test-unit`（分两批以隔离 monkeypatch 状态污染）
- 预期：276 passed
- 或分两批运行：batch1(facade+precheck=44) + batch2(其余=232)

## Store 关系
- `app.api.workbench.store` — 线程安全包装层，业务代码用这个
- `app.services.workbench_state_store` — 底层 DB/文件双模读写，被上面包装

## 生成链路关键点
- 两条路径汇聚到 `run_generate_pipeline()`
- Path A（AI 驱动）：`selected_candidate=None` → LLM 路径 → 校验在 orchestrator
- Path B（手动/治理）：`selected_candidate` 非空 → 直接编译 → V1.1 严格校验
- DSL V1.1 6 条铁律都在编译器里 `raise ExecutionCompilerError`，不是软检查

## 修改代码前检查
1. 改 DB 查询 → 用 Repository 方法，不要写 `db.execute(select(...))`
2. 改异常处理 → 用具体类型，不要加 `except Exception`
3. 改工具函数 → 先看 `shared_backend/type_utils.py` 是否已有
4. 改生成逻辑 → 确认两条路径都有校验覆盖
5. 改完运行 `pytest apps/web-ui-service/tests/unit/ apps/ai-orchestrator/tests/unit/ -q`

## 已知问题（接手时注意）

### WorkbenchState 表无 Alembic 迁移 ✅ 已处理
`make db-upgrade` 和 `make db-bootstrap` 现在会在 alembic 之后自动调用 `Base.metadata.create_all()` 创建 6 张 workbench_state 表。正式迁移待补。

### 启动后页面为空 ✅ 已处理
`make dev` 现在自动运行 `db-bootstrap` 创建 seed 数据。如果仍为空，检查 `.env` 中 `DATABASE_URL` 是否正确指向 Docker PostgreSQL。

### 前端本地开发需手动 build ✅ 已处理
`make install-dev` 和 `make dev` 现在自动 `npm install && npm run build`。`frontend-build` 也内置了 `npm install` 检查。

### `app.py` 和 `app/` 包冲突
orchestrator 的 `apps/ai-orchestrator/src/app.py` 和 web-ui 的 `apps/web-ui-service/app/` 包在同一个 PYTHONPATH 中会冲突（`.py` 先于 package/）。`verify_core_chain.py` 已 workaround。CI 和本地开发应通过 `docker compose` 隔离两个服务，不要混在同一个 PYTHONPATH。

### ORM 无 relationship 定义
所有模型只有 `mapped_column`，没有 `relationship()`。TestCase 和 TestCaseExecution 之间的关联只能通过 Repository 方法手动查询。不要尝试用 `case.executions` 等 ORM 懒加载——不存在。

### test ordering 失败
`test_workbench_facade.py` 和 `test_precheck_selected_intents_service.py` 的 monkeypatch 与其他测试存在状态污染。`make test-unit` 已分两批运行（44 + 232 = 276 passed）隔离。单独跑 `pytest apps/web-ui-service/tests/unit/ -q` 会有 15 个假失败。根因待排查。
