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
- 运行：`make test-unit`（分两进程以隔离 monkeypatch 状态污染）
- 预期：274 passed, 3 failed（3 个旧有 facade mock DB 问题）
- 分两批：batch1(facade+precheck=44, 3 fail) + batch2(其余=233, 0 fail)

## Store 关系
- `app.api.workbench.store` — 线程安全包装层，业务代码用这个
- `app.services.workbench_state_store` — 底层 DB/文件双模读写，被上面包装

## 生成链路关键点
- 两条路径汇聚到 `run_generate_pipeline()`
- Path A（AI 驱动）：`selected_candidate=None` → LLM 路径 → 校验在 orchestrator
- Path B（手动/治理）：`selected_candidate` 非空 → 直接编译 → V1.1 严格校验
- DSL V1.1 6 条铁律都在编译器里 `raise ExecutionCompilerError`，不是软检查

## 铁律

### 🚫 永远不要 `git add -A`
磁盘上存在大量未被跟踪的历史遗留文件（旧测试、生成产物、缓存）。`git add -A` 会把它们全部提交，污染仓库。**只 `git add <具体文件>` 或用 `git add -u`（只添加已跟踪文件的修改）。**

### 🚫 永远不要删除 Postgres 数据卷
`docker compose down postgres -v` 中的 `-v` 会**永久删除数据库**，导致所有用户、用例、页面对象、执行记录丢失。**严禁**在任何情况下使用 `-v` 标志。如果必须重建数据库，用 `docker compose down postgres`（不带 `-v`），然后 `docker compose up -d postgres`。

## 修改代码前检查
1. 改 DB 查询 → 用 Repository 方法，不要写 `db.execute(select(...))`
2. 改异常处理 → 用具体类型，不要加 `except Exception`
3. 改工具函数 → 先看 `shared_backend/type_utils.py` 是否已有
4. 改生成逻辑 → 确认两条路径都有校验覆盖
5. 改完运行 `pytest apps/web-ui-service/tests/unit/ apps/ai-orchestrator/tests/unit/ -q`

## 文件大小红线（CI 自动拦截）
| 层级 | 上限 |
|------|------|
| facade | 2,500 行 |
| service | 1,000 行 |
| repository | 400 行 |
| router | 200 行 |
| 单个函数 | 370 行（超 100 行警告） |
超过必须在 commit message 中说明原因，并计划拆分。

## 已知陷阱

### N+1 查询风险
项目已定义 `TestCase.executions`、`PageObject.elements` 等 ORM relationship（`lazy="select"`）。
直接访问 `case.executions` 或 `page_object.elements` 会触发隐式查询——在循环中会导致 N+1。
**批量场景必须走 Repository 方法**（`repo.list_executions_by_case_ids(case_ids)` 等），不要依赖 ORM 懒加载。

### pytest -q 直接跑会失败
`pytest apps/web-ui-service/tests/unit/ apps/ai-orchestrator/tests/unit/ -q` 会有 15 个假失败。
这是 monkeypatch 状态污染（非代码 bug）。用 `make test` 或 `make test-unit`（已分两批）。

## AI 代码生成模板

### 新建 service 函数
```python
from app.repositories.xxx_repository import XxxRepository
from shared_backend.type_utils import dict_value, list_value  # 按需

def new_business_function(db: Session, *, param1: str, param2: int) -> dict[str, Any]:
    """做什么事情。返回 {key: value}。"""
    repo = XxxRepository(db)
    items = repo.list_filtered(status=param1)
    return {"items": items, "total": len(items)}
```
要求: 参数 type hint 必写、返回 dict 必写 shape 注释、DB 访问必须通过 repo、必须写测试。

### 新建工具函数
1. 先查 `shared_backend/type_utils.py` 是否有同功能函数
2. 如果有 → `from shared_backend.type_utils import xxx as _xxx`
3. 如果通用 → 加到 `type_utils.py`
4. 如果仅本文件使用 → 在文件顶部定义 `def _xxx(...)`

### 新建 Repository 方法
```python
def list_by_xxx(self, project_code: str) -> list[Model]:
    return list(self.db.execute(
        select(Model).where(Model.project_code == project_code)
    ).scalars().all())
```
Repository 是唯一可以写 `db.execute(select(...))` 的地方。

## CI 护栏（scripts/ci/check_architecture.py）
每次 PR 自动检查:
- 文件/函数大小是否超限
- 非 repository 层是否写了 `db.execute(select(...))`
- service 层是否 `SessionLocal()`
- 是否重复定义 `type_utils` 已有函数
- 是否 `import sqlite3`
- 是否 `import *`

## 已知问题（接手时注意）

### WorkbenchState 表无 Alembic 迁移 ✅ 已处理
`make db-upgrade` 和 `make db-bootstrap` 现在会在 alembic 之后自动调用 `Base.metadata.create_all()` 创建 6 张 workbench_state 表。正式迁移待补。

### 启动后页面为空 ✅ 已处理
`make dev` 现在自动运行 `db-bootstrap` 创建 seed 数据。如果仍为空，检查 `.env` 中 `DATABASE_URL` 是否正确指向 Docker PostgreSQL。

### 前端本地开发需手动 build ✅ 已处理
`make install-dev` 和 `make dev` 现在自动 `npm install && npm run build`。`frontend-build` 也内置了 `npm install` 检查。

### `app.py` 和 `app/` 包冲突 ✅ 已处理
orchestrator: `app.py` → `main.py`。两个服务不再有 PYTHONPATH 冲突。

### ORM 无 relationship 定义 ✅ 已处理
TestCase ↔ Execution/Step/Version/Defect 和 PageObject ↔ PageElement 已添加 `relationship(back_populates=..., lazy="select")`。可直接 `case.executions` 导航。注意 N+1 风险——批量查询仍应走 Repository。

### test ordering 失败 ✅ 已诊断
根因：多个测试文件的 monkeypatch.setattr 累积效应，非单一污染源。
排除了"单个文件导致"的可能——是 monkeypatch 撤销顺序的复杂交互。
根治需将 44 个测试的 monkeypatch 改为 `unittest.mock.patch` 上下文管理器。
当前 workaround: `make test-unit` 分两批（44+232=276）。
