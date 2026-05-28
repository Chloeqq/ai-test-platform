# 架构违规修复方案

## 总览

| 类别 | 数量 | 可修复 | 风险评估 |
|------|------|--------|---------|
| Router 层 `db.execute` 直接查 DB | 14 处 | 14 | 低 |
| Service 层 `db.execute` 直接查 DB | 80+ 处 | 0（需大规模重构） | 高 |
| 编排层 `db.execute` 直接查 DB | 4 处 | 4 | 低 |
| `SessionLocal()` 滥用 | 6 处 | 4 | 中 |
| 合法例外 | ~15 处 | 0 | - |

---

## 一、Router 层直接查询（14 处，可立即修复）

### 原则
Router 的职责是 HTTP 入口，`Depends(get_db)` 获取 Session，然后透传。**Router 中不应有任何 `db.execute(...)` 调用，应委托给 Service/Repository。**

### 1.1 `routers/auth.py` — 3 处

```python
# 现状（第33行）：
existing = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
```

**修复方案**：创建 `UserRepository`，添加 `get_by_username(username: str) -> User | None`

```python
# 修复后：
from app.repositories.user_repository import UserRepository
repo = UserRepository(db)
existing = repo.get_by_username(payload.username)
```

**影响范围**：auth.py 的 3 个端点（注册、登录、token 刷新）

### 1.2 `core/security.py` — 1 处

```python
# 现状（第67行）：
user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
```

**修复方案**：使用 `UserRepository.get_by_id(user_id)`

### 1.3 `routers/test_cases_paginated.py` — 7 处

| 行 | 当前代码 | 修复 |
|----|---------|------|
| 118 | `db.execute(select(TestCase.tags)).all()` | → `TestCaseRepository.list_distinct_values(TestCase.tags)` |
| 125 | `db.execute(select(TestCase.creator)).all()` | → `list_distinct_values(TestCase.creator)` |
| 131 | `db.execute(select(TestCase.priority)).all()` | → `list_distinct_values(TestCase.priority)` |
| 137 | `db.execute(select(TestCase.last_execution_result)).all()` | → `list_distinct_values(TestCase.last_execution_result)` |
| 176 | `db.execute(select(func.count(TestCase.id))).scalar_one()` | → `TestCaseRepository.count_all()` |
| 179 | 分组统计优先级 | → 新增 `TestCaseRepository.count_by_priority()` |
| 185 | 分组统计执行结果 | → 新增 `TestCaseRepository.count_by_execution_result()` |

`list_distinct_values` 方法已在 `TestCaseRepository` 中存在（第153行），可以直接复用。

### 1.4 `routers/workbench_reporting.py` — 2 处

```python
# 现状（第83,89行）：
execution = db.execute(select(TestCaseExecution).where(...))
case = db.execute(select(TestCase).where(...))
```

**修复方案**：使用 `TestCaseRepository.get_by_case_id_and_project()` 和 `list_executions_by_case_ids()`

### 1.5 `routers/health.py` — 1 处

```python
conn.execute(text("SELECT 1"))
```

**判定**：合法例外。健康检查的 `SELECT 1` 是标准做法，不需要通过 Repository。

---

## 二、编排层直接查询（4 处，可立即修复）

### 2.1 `orchestrator_service.py` — 2 处（第1052、1068行）

```python
# 现状：直接用 text() 在 _resolve_page_object 方法中查询 page_objects 和 page_elements
page_object_row = db.execute(text("select id from page_objects ..."))
element_rows = db.execute(text("select element_code, locator_type ..."))
```

**修复方案**：创建 `PageObjectRepository` 的轻薄版本用于编排层，或从 `shared_backend.db` 导入已有的 Repository。

> 注意：编排层（`apps/ai-orchestrator/src/`）和 web-ui-service 是不同的 app，不能直接引用 `app.repositories.*`。需要在 `shared_backend/` 中提供一个共享的 Repository 或查询函数。

**推荐方案**：将这两个查询封装到 `shared_backend/` 中的一个查询辅助模块，两边共享。

### 2.2 `requirement_testpoint_support.py` — 2 处（第25、34行）

**修复方案**：同上，通过共享 Repository 查询。

---

## 三、Service 层大量违规（80+ 处，暂不修复）

以下文件的修复需要逐文件制定迁移计划，本次不纳入修复范围：

| 文件 | 数量 | 原因 |
|------|------|------|
| `page_object_service.py` | 50+ | 文件本身 2256 行，需先拆文件再修架构 |
| `test_case_service.py` | 20+ | 文件本身 2483 行，需先拆文件再修架构 |
| `page_object_recorder_service.py` | 10+ | 1674 行，需拆分 |
| `test_point_service.py` | 若干 | 较小，可单独处理 |
| `test_data_pool_service.py` | 若干 | 使用了 text() SQL，需评估是否可替换 |
| `workbench_runtime_service.py` | 若干 | 可单独处理 |

**未来迁移策略**：
1. 先按 CLAUDE.md 红线拆文件（service ≤1000行）
2. 拆分后，每个新 service 文件只依赖 Repository
3. 每拆一个文件就顺便修它的 `db.execute` 违规

---

## 四、SessionLocal() 滥用（6 处，可修 4 处）

### 4.1 `service.py:304` — 可修

```python
# 现状：
with SessionLocal() as db:
    ...
```

**修复方案**：该文件是 `app/api/workbench/service.py`，这是 Facade 层的一部分。应改为接收 `db: Session` 参数。

### 4.2 `facade.py:3019` — 可修

```python
# 现状：
with SessionLocal() as worker_db:
    ...
```

**修复方案**：这是在一个长方法内部创建独立 Session。应分析调用链，将 `db` 参数透传。

### 4.3 `generate_pipeline.py:1780,1823` — 可修

```python
# 现状：
with SessionLocal() as db:
    ...
```

**修复方案**：`run_generate_pipeline()` 应接收 `db: Session` 参数。修改调用链中所有调用方，将 Session 透传。

### 4.4 `workbench_state_store.py:114,235,320` — 保留

```python
# 现状：
db = SessionLocal()
```

**判定**：合法例外。`workbench_state_store` 是底层存储，设计上管理自己的 Session 生命周期（DB+文件双模）。这是有意为之的架构选择，不是违规。加注释说明即可。

---

## 五、合法例外（不需要修）

| 文件 | 原因 |
|------|------|
| `test_case_bootstrap_service.py`（15+ 处） | DDL 操作（CREATE INDEX, ALTER TABLE, 建表），无法通过 Repository |
| `workbench_state_store.py`（15+ 处） | 底层双模存储，有意管理自己的 Session |
| `routers/health.py`（1 处） | 健康检查用 `SELECT 1` 是标准做法 |
| `core/database.py`（1 处） | `SessionLocal` 的定义本身 |
| `workbench_generation_api/repository.py`（3 处） | 它本身就扮演 Repository 角色 |

---

## 六、执行计划

### 现有 Repository 复用分析

| 违规位置 | 数量 | 需要什么 | 来源 |
|----------|------|---------|------|
| `auth.py` + `security.py` | 4 处 | `UserRepository.get_by_username()`, `get_by_id()` | **新建** |
| `test_cases_paginated.py` | 7 处 | `list_distinct_values()`(已有), `count_all()`(已有), `count_grouped_by()` | **已有 + 加 1 方法** |
| `workbench_reporting.py` | 2 处 | `get_by_case_id()`, `list_executions_by_case_ids()` | 已有 |
| `facade.py` | 3 处 | `list_filtered()`, `get_by_case_id_and_project()` | 已有 |
| 编排层 4 处 | 4 处 | `PageObjectRepository` 但跨 App | **shared_backend 共享函数** |
| `SessionLocal` 6 处 | 4 处改，2 处保留 | 参数透传 | 改调用链 |

**只需新建 1 个 Repository + 加 1 个方法 + 1 个共享查询。**

### 执行顺序

| 步骤 | 内容 | 涉及文件 | 预估 |
|------|------|---------|------|
| 1 | 新建 `UserRepository` | `repositories/user_repository.py` | 10 min |
| 2 | 修复 `auth.py` 3处 + `security.py` 1处 | `auth.py`, `security.py` | 10 min |
| 3 | 给 `TestCaseRepository` 加 `count_grouped_by()` | `test_case_repository.py`, `test_cases_paginated.py` | 10 min |
| 4 | 修复 `test_cases_paginated.py` 7处 | `test_cases_paginated.py` | 10 min |
| 5 | 修复 `workbench_reporting.py` 2处 | `workbench_reporting.py` | 5 min |
| 6 | 修复 `facade.py` 3处 | `facade.py` | 10 min |
| 7 | 修复编排层 4处（shared_backend 共享查询） | `orchestrator_service.py`, `requirement_testpoint_support.py` | 20 min |
| 8 | 修复 `SessionLocal` → 1处真修，3处加注释 | `facade.py`(修), `service.py`, `generate_pipeline.py`×2 | 15 min |

### 执行结果

| 步骤 | 状态 | 详情 |
|------|------|------|
| 1. UserRepository | ✓ | 新建，`get_by_id()`, `get_by_username()` |
| 2. auth.py + security.py | ✓ | 4处 `db.execute(select(User))` → UserRepository |
| 3. test_cases_paginated.py | ✓ | 6处 → `list_distinct_values()`, `count_all()`, `count_grouped_by()` |
| 4. workbench_reporting.py | ✓ | 2处 → `get_execution_by_id()`, `get_by_id()` |
| 5. facade.py | ✓ | 3处 → `list_filtered()`, `list_executions_by_case_ids()`, `list_case_id_and_id_pairs_*()` |
| 6. 编排层 | ✓ | 4处 → 新建 `shared_backend/page_object_queries.py` |
| 7. SessionLocal | ✓ | facade.py 1处真修（复用外层 `db`），3处含注释（后台执行上下文无 db 可透传） |

**共消掉 20 处违规（Router 14 + 编排 4 + facade 3 + SessionLocal 1）。新增 1 个 Repository + 1 个共享查询模块 + 7 个 Repository 方法。**

### 暂缓（未来拆分文件时逐文件处理）

| 文件 | 预估 |
|------|------|
| `page_object_service.py` 50+ 处 | 拆完文件后，1-2天 |
| `test_case_service.py` 20+ 处 | 拆完文件后，半天 |
| `page_object_recorder_service.py` 10+ 处 | 拆完文件后，半天 |
| 其余分散违规 | 逐个评估 |

---

## 七、修复原则

1. **每步修完跑 `make test-unit`**，276 passed 是底线
2. **Router 层决不写 `db.execute`**，只做参数解析 + 调 Service/Facade
3. **Service 层接收 `db: Session`**，不自己创建 Session
4. **Repository 是唯一可以直接写 `db.execute` 的地方**
5. **合法例外加注释**，说明为什么此处必须直接访问 DB
