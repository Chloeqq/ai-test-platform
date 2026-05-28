# 代码审查问题清单 — 2026-05-28

## 已修复

- [x] **`orchestrator_service.py:1013`** — `except (yaml.YAMLError, OSError)` 漏了 `UnicodeDecodeError`，已加 `ValueError`
- [x] **`execution_compiler.py`** — 删除重复的 `_dedup_keep_order`/`_dict_value`/`_list_value`，改用 `type_utils` 导入
- [x] **`orchestrator_service.py`** — 裸 `except Exception` 改为具体类型（`_env_float`, `_env_int`, YAML解析, `_load_available_targets`）

---

## 待修复

### 第 1 批：重复函数定义（低风险，每个 5 分钟）

- [x] ~~**`page_object_assets.py:20`**~~ — `_dedupe_keep_order` **保留**：本地版会 strip 每个值再去重，`type_utils.dedup_keep_order` 不 strip，语义不同
- [x] ~~**`test_case_mapper.py:37`**~~ — `_list_value` **保留**：本地版返回 `list[str]` 且过滤空字符串，`type_utils.list_value` 返回 `list[Any]` 不过滤，语义不同
- [x] **`element_binding.py:7`** — `_normalized_text` → `from type_utils import str_value as _normalized_text`
- [x] **`intent_mapping.py:9`** — `_normalized_text` → `from type_utils import str_value as _normalized_text`
- [x] **`page_object_assets.py:12`** — `_normalized_text` → `from type_utils import str_value as _normalized_text`
- [x] **`element_binding.py + intent_mapping.py`** — `_normalized_key` → 提取到 `type_utils.normalized_key`，两个文件改为 import
- [x] **`test_case_mapper.py:51`** — `_text` → `from type_utils import str_value as _text`

### 第 2 批：私有函数被外部导入（边界明确，每个 10 分钟）

- [x] `execution_compiler.py` 中 6 个 `_` 前缀函数 → 移除 `_` 前缀正式公开：
  `_normalize_page_slug` → `normalize_page_slug`
  `_has_multisource_inputs` → `has_multisource_inputs`
  `_build_system_requirement` → `build_system_requirement`
  `_extract_quality_gate` → `extract_quality_gate`
  `_is_quality_gate_blocked` → `is_quality_gate_blocked`
  `_render_requirement_spec_markdown` → `render_requirement_spec_markdown`
- 同步更新了 `orchestrator_client_factory.py` 和 `preview_test_points_usecase.py` 的导入
- `orchestrator_client.py` 中的 `self._xxx` 是实例变量，无需改动
- `workbench_gate_service.py`/`review_service.py`/`service.py` 中的 `_normalize_page_slug` 是本地实现，不是导入，无需改动

### 第 3 批：废弃代码清理（低风险，每个 5 分钟）

- [x] `PreviewTestPointsCompiler` 类 — 从 `execution_compiler.py` 和 `__init__.py` 导出中删除
- [x] `preview_test_points_infra.py` — 整个文件删除（无调用方）
- [x] `ExecutionCompileError` 别名 — 删除，内部引用改为 `ExecutionCompilerError`
- `execution_compiler.py`: 1184 → 1032 行(-152)

### 第 4 批：`import *` 清理（低风险）

- [x] `page_object_service.py:39` — `from app.services.page_object_normalizers import *` → 只用了 `CANDIDATE_PROMOTION_STATUS_VALUES` 和 `CANDIDATE_STATUS_VALUES`
- [x] `page_object_recorder_service.py:36` — `from app.services.page_object_locator_scoring import *` → 替换为 20 个显式导入
- [x] `workbench_generation_compiler/execution_compiler.py` — 整个文件删除（无调用方的 re-export shim）

### 第 5 批：`import sqlite3` 清理

- [x] `test_requirement_testpoint_resolution.py:3` — **无需修改**。测试文件创建内存 SQLite 测试库，属合法使用。CI 第 206 行已排除 `/tests/` 路径。
- [x] `test_cases_browser_interactions.py:6` — **无需修改**。E2E 测试直接写 DB 做断言，CI 已排除。
- [x] `scripts/normalize_case_ids.py:5` — **无需修改**。工具脚本不属 CI 扫描范围（仅扫描 `apps/web-ui-service/app` 和 `apps/ai-orchestrator/src`）。

结论：3 处均为合法使用，CI 正确跳过，无需改动。

---

## 仅记录、暂不修复（需要大规模重构）

### 文件大小超标

| 文件 | 当前 | 上限 | 超出 |
|------|------|------|------|
| `facade.py` | 3,792 | 2,500 | +1,292 |
| `generate_pipeline.py` | 2,636 | 1,000 | +1,636 |
| `test_case_service.py` | 2,483 | 1,000 | +1,483 |
| `page_object_service.py` | 2,256 | 1,000 | +1,256 |
| `orchestrator_service.py` | 1,839 | 1,000 | +839 |
| `workbench_asset_service.py` | 1,805 | 1,000 | +805 |
| `page_object_recorder_service.py` | 1,674 | 1,000 | +674 |
| `workbench_analysis_service.py` | 1,422 | 1,000 | +422 |
| `workbench_governance_service.py` | 1,403 | 1,000 | +403 |
| `workbench_reporting_service.py` | 1,321 | 1,000 | +321 |
| `workbench_runtime_service.py` | 1,158 | 1,000 | +158 |
| `routers/page_objects.py` | 540 | 200 | +340 |
| `routers/workbench_assets.py` | 311 | 200 | +111 |
| `routers/test_cases.py` | 274 | 200 | +74 |
| `routers/test_cases_paginated.py` | 202 | 200 | +2 |

### 单函数超标

| 函数 | 文件 | 行数 |
|------|------|------|
| `build_governance_overview` | `workbench_governance_service.py` | 370 |
| `update_test_case` | `test_case_service.py` | 266 |
| `runtime_view_from_entry` | `workbench_runtime_service.py` | 255 |

### 架构违规：`db.execute(select(...))` 在非 Repository 层

大量存在于 `orchestrator_service.py`, `facade.py`, `routers/test_cases_paginated.py`, `page_object_recorder_service.py`, `page_object_service.py`, `security.py` 等。需逐文件迁移到 Repository。

### 架构违规：`SessionLocal()` 在 Service/Facade 层

- `facade.py:3019`
- `service.py:304`
- `generate_pipeline.py:1780,1823`
- `workbench_state_store.py:114,235,320`

### 高优先级但工作量大

- **~800 处** `str(value or "").strip()` 未使用 `type_utils.str_value`
- **11 个文件**各自定义本地的 `_text`/`_normalized_text` 函数，与 `type_utils.str_value` 功能相同

---

## 修复原则

1. 每次修一批，修完跑 `make test-unit` 确认 276 passed
2. 每批用一个独立 commit
3. 第 1-5 批全部修完后，再做大规模重构（文件拆分）
