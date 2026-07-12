# EvieAi Phase 0 领域模型实施计划

日期：2026-07-12

本文记录 EvieAi Phase 0 的最终实施计划。本文已合并 2026-07-12 人工确认结论，作为后续代码落地的权威计划。

## 0. 与完整目标架构的关系

EvieAi Phase 0 是完整目标架构的最小领域模型切片。

完整目标能力参考：

- `docs/evie-ai/architecture/target-capability-map.md`
- EvieAi 架构图：`docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
- Excel 完整设计参考：`docs/evie-ai/reference/ATP_V2_架构分层功能清单_完整实施版.xlsx`

上述资料用于保证长期方向一致，但不自动扩大 Phase 0 范围。

Phase 0 仅实施本文明确列出的模型、字段、约束和测试。

发生冲突时，以用户确认决策、`AGENTS.md` 和本文为准。

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

## 1. 当前未提交改动隔离方案

当前分支与基线：

```text
branch: dev
HEAD: 85e876b docs: document generation architecture migration
```

当前工作区存在旧链修复、文档清理、调试产物和依赖文件改动。EvieAi Phase 0 不应混入旧链修复。

| 改动 | 判断 | 建议 |
|---|---|---|
| `apps/web-ui-service/app/api/workbench/facade_helpers.py` | 旧链修复，和 EvieAi Phase 0 无关 | 单独提交或 stash |
| `apps/web-ui-service/app/api/workbench/facade_test_point_assets.py` | 旧链修复，和 EvieAi Phase 0 无关 | 单独提交或 stash |
| `apps/web-ui-service/tests/unit/test_workbench_facade.py` | 旧链修复测试 | 跟旧链修复一起提交 |
| `package.json` / `package-lock.json` | 依赖变更，和 EvieAi Phase 0 无关 | 单独确认，不混入 EvieAi |
| `.playwright-mcp/*` | 本地调试产物 | 不提交 |
| `docs/evie-ai/**`、`AGENTS.md`、文档索引 | EvieAi 权威文档与清理改动 | 可作为独立 `docs(evie-ai)` 提交 |
| `docs/archive/*` | 旧链历史归档 | 可随文档清理提交，或单独提交 |

建议顺序：

1. 先处理或 stash 旧链代码修复。
2. 单独提交 EvieAi 文档和归档清理。
3. 从干净工作区开始 EvieAi Phase 0 代码落地。

## 2. Phase 0 文件清单

### 文档

```text
AGENTS.md

docs/evie-ai/
├── README.md
├── architecture/
│   ├── natural-language-test-assets.md
│   └── evie-ai-overview.md
├── implementation/
│   └── phase-0-domain-model.md
├── migration/
│   ├── legacy-chain-freeze-list.md
│   └── docs-cleanup-plan.md
└── reference/
    ├── README.md
    ├── ATP_V2_架构分层功能清单_完整实施版.xlsx
    └── 2026-07-12_evie-ai-architecture-flow.mmd
```

不允许同时保留旧产品命名目录作为权威路径。

### 后端模型

```text
apps/web-ui-service/app/models/evie_ai/
├── __init__.py
├── requirement.py
└── test_asset.py
```

主要类：

- `Requirement`
- `RequirementVersion`
- `TestAsset`
- `TestAssetVersion`
- `TestAssetSource`

职责：

- 定义 EvieAi 自然语言资产最小持久化模型。
- 复用现有 `TestProject.project_code` 作为项目作用域，不新增平行 Project 表，不新增 `project_id / project_uuid`。
- 只保存自然语言资产、版本、来源关系。

不允许承担：

- 不保存 `action / target / value`
- 不保存 `structured_steps`
- 不保存 `selector / locator`
- 不保存 `script_code`
- 不调用 AI、Compiler、Runner、QualityGate

### Schema

```text
apps/web-ui-service/app/schemas/evie_ai/
├── __init__.py
├── requirement.py
└── test_asset.py
```

职责：

- 定义 Phase 0 的自然语言字段契约。
- 明确禁止机器字段进入 TestAsset schema。

不允许承担：

- 不做 AI 生成。
- 不做语义去重。
- 不做 Asset-to-Case。
- 不做 Compiler 输入转换。

### Repository

```text
apps/web-ui-service/app/repositories/evie_ai/
├── __init__.py
├── requirement_repository.py
└── test_asset_repository.py
```

职责：

- EvieAi 表的最小 DB 读写。
- 维护 `current_version_id` 一致性。
- 使用现有 `Session` 和 `BaseRepository`。

不允许承担：

- 不调用旧 `TestPointAssetRepository`
- 不调用 `structurer`
- 不调用 `execution_compiler`
- 不调用 `ContractValidator`
- 不调用 `resolve_explicit_step`

### ID 模块

修改：

```text
apps/web-ui-service/app/core/id_gen.py
```

新增函数：

```python
generate_requirement_id()
generate_requirement_version_id()
generate_test_asset_id()
generate_test_asset_version_id()
generate_test_asset_source_id()
```

不新增独立于现有体系的 ID 服务。

### Migration

新增：

```text
apps/web-ui-service/migrations/versions/<actual_revision>_evie_ai_phase0_assets.py
```

`<actual_revision>` 必须实施前读取 Alembic 当前 heads/history 后确定，不按日期猜。

### 测试

```text
apps/web-ui-service/tests/unit/evie_ai/
├── test_evie_ai_ids.py
├── test_evie_ai_models.py
├── test_evie_ai_schemas.py
├── test_evie_ai_repositories.py
└── test_evie_ai_architecture_boundaries.py
```

## 3. 数据模型

### requirements

职责：需求聚合根，只保存稳定身份和聚合状态，不保存正文。

核心字段：

```text
id
project_code
requirement_code
external_requirement_key
review_status
current_version_id nullable
created_at
updated_at
deleted_at
created_by
updated_by
```

不允许放：

```text
title
content
description
natural_steps
structured_steps
script_code
```

### requirement_versions

职责：保存需求正文版本。

核心字段：

```text
id
requirement_id
version_no
title
content
content_checksum
version_status
created_at
updated_at
created_by
updated_by
```

### test_assets

职责：自然语言测试资产聚合根，表达“测什么”。

核心字段：

```text
id
project_code
asset_code
review_status
conversion_status
current_version_id nullable
created_at
updated_at
deleted_at
created_by
updated_by
```

Phase 0 不包含：

```text
duplicate_status
intent_id
status=deleted
structured_steps
action
target
value
locator
compiler_ir
dsl
script_code
```

软删除只使用 `deleted_at`。

### test_asset_versions

职责：保存自然语言测试资产内容版本。

核心字段：

```text
id
test_asset_id
version_no
title
precondition
natural_steps
expected_result
priority
tags
content_checksum
created_at
updated_at
created_by
updated_by
```

### test_asset_sources

职责：Phase 0 只支持 Requirement 来源绑定。

核心字段：

```text
id
test_asset_id
requirement_id
requirement_version_id
source_identity_hash
created_at
created_by
```

不预建：

```text
document_id
document_version_id
section_id
page_id
generation_context_id
batch_id
```

## 4. 约束和索引

### requirements

```text
UNIQUE(project_code, requirement_code)
INDEX(project_code)
INDEX(project_code, external_requirement_key)
INDEX(review_status)
INDEX(deleted_at)
```

`external_requirement_key` 只建普通组合索引，不建唯一约束。

`current_version_id` Phase 0 允许为空，初始 Migration 不建数据库 FK。

### requirement_versions

```text
FK(requirement_id) -> requirements(id)
UNIQUE(requirement_id, version_no)
INDEX(requirement_id)
INDEX(content_checksum)
INDEX(version_status)
```

`content_checksum` 只建普通索引，不建唯一约束，允许恢复历史正文。

### test_assets

```text
UNIQUE(project_code, asset_code)
INDEX(project_code)
INDEX(review_status)
INDEX(conversion_status)
INDEX(deleted_at)
```

`current_version_id` Phase 0 允许为空，初始 Migration 不建数据库 FK。

### test_asset_versions

```text
FK(test_asset_id) -> test_assets(id)
UNIQUE(test_asset_id, version_no)
INDEX(test_asset_id)
INDEX(content_checksum)
```

`content_checksum` 只建普通索引，不建 `UNIQUE(test_asset_id, content_checksum)`，因为必须允许资产恢复到历史内容。

### test_asset_sources

```text
FK(test_asset_id) -> test_assets(id)
FK(requirement_id) -> requirements(id)
FK(requirement_version_id) -> requirement_versions(id)
UNIQUE(test_asset_id, source_identity_hash)
INDEX(requirement_id)
INDEX(requirement_version_id)
INDEX(source_identity_hash)
```

## 5. ID 方案

继续扩展现有：

```text
apps/web-ui-service/app/core/id_gen.py
```

新增函数建议：

```python
generate_requirement_id()          # req_<uuid4hex32>
generate_requirement_version_id()  # reqv_<uuid4hex32>
generate_test_asset_id()           # ta_<uuid4hex32>
generate_test_asset_version_id()   # tav_<uuid4hex32>
generate_test_asset_source_id()    # tas_<uuid4hex32>
```

规则：

- 不得使用 8 位短 hex 作为核心业务 ID。
- 核心业务 ID 统一使用 UUID4 hex32。
- ID 由后端生成。
- AI 不生成权威数据库 ID。
- Phase 0 不新增 `intent_id`。

## 6. current_version 事务规则

### Requirement

创建需求时：

```text
1. 创建 Requirement
2. 创建 RequirementVersion(version_no=1)
3. Repository 在同一事务内设置 Requirement.current_version_id
4. 验证 current_version.requirement_id == requirement.id
```

新增版本时：

```text
1. 创建 RequirementVersion(version_no + 1)
2. 更新 Requirement.current_version_id
3. 同事务提交
```

### TestAsset

创建资产时：

```text
1. 创建 TestAsset
2. 创建 TestAssetVersion(version_no=1)
3. 创建 TestAssetSource
4. Repository 在同一事务内设置 TestAsset.current_version_id
5. 验证 current_version.test_asset_id == test_asset.id
```

新增版本时：

```text
1. 如果 TestAsset.conversion_status = processing，禁止直接编辑，必须先结束或取消当前 ConversionAttempt
2. 创建 TestAssetVersion(version_no + 1)
3. 更新 TestAsset.current_version_id
4. 将 TestAsset.review_status 重置为 pending
5. 按原 conversion_status 计算新 conversion_status：
   - 原状态为 succeeded 或 stale 时，新状态为 stale
   - 原状态为 not_started 或 blocked 时，新状态为 not_started
6. 同事务提交
```

Phase 0 不用数据库 FK 强约束 `current_version_id`，避免建表时循环依赖；一致性由 Repository 和测试保证。

## 7. Migration 顺序

实施前必须执行只读确认：

```text
alembic heads
alembic history
```

Migration 文件：

```text
apps/web-ui-service/migrations/versions/<actual_revision>_evie_ai_phase0_assets.py
```

upgrade 顺序：

```text
1. create requirements
2. create requirement_versions
3. create test_assets
4. create test_asset_versions
5. create test_asset_sources
6. create indexes
7. create unique constraints
```

downgrade 顺序：

```text
1. drop test_asset_sources
2. drop test_asset_versions
3. drop test_assets
4. drop requirement_versions
5. drop requirements
```

## 8. 架构守卫测试设计

测试目录：

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py
```

采用三类检查。

### AST import 检查

EvieAi 资产模块禁止依赖：

```text
structurer
execution_compiler
ContractValidator
resolve_explicit_step
TestPointAsset
Candidate
selected_candidates
Runner
QualityGate
```

检查范围：

```text
apps/web-ui-service/app/models/evie_ai/**
apps/web-ui-service/app/schemas/evie_ai/**
apps/web-ui-service/app/repositories/evie_ai/**
```

### Pydantic 字段集合检查

TestAsset Schema 不允许出现机器执行字段：

```text
structured_steps
steps_hint
action
target
value
locator
compiler_ir
dsl
script_code
runner_steps
```

### SQLAlchemy 表字段检查

表字段不允许出现：

```text
structured_steps
action
target
value
locator
script_code
duplicate_status
intent_id
status
```

允许：

```text
review_status
conversion_status
deleted_at
```

文本搜索只作为辅助，不作为主判断。

## 9. 测试计划

### ID 测试

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_ids.py
```

覆盖：

- ID 前缀正确。
- ID 长度和字符集足够安全。
- 批量生成无碰撞。
- 不使用 8 位短 hex。

### 模型测试

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_models.py
```

覆盖：

- 表名正确。
- 字段集合不包含机器执行字段。
- `current_version_id` 可为空。
- 软删除使用 `deleted_at`。
- 项目作用域字段使用 `project_code`。
- `external_requirement_key` 不是唯一约束。
- `content_checksum` 不是唯一约束。

### Schema 测试

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_schemas.py
```

覆盖：

- TestAsset Schema 只接收自然语言资产字段。
- 禁止机器字段。

### Repository 测试

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py
```

覆盖：

- 创建 Requirement + RequirementVersion。
- 创建 TestAsset + TestAssetVersion + TestAssetSource。
- `current_version_id` 指向属于自身聚合的版本。
- 同一资产同一来源重复时触发唯一约束或返回已有记录。
- 创建 TestAsset 新版本时，`review_status` 重置为 `pending`。
- 创建 TestAsset 新版本时，`conversion_status` 按人工确认规则迁移。
- `processing` 期间不允许直接编辑。

### 架构依赖测试

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py
```

覆盖：

- EvieAi 资产模块不能依赖 `structurer`。
- EvieAi 资产模块不能依赖 `execution_compiler`。
- EvieAi 资产模块不能依赖 `ContractValidator`。
- EvieAi 资产模块不能依赖 `resolve_explicit_step`。
- EvieAi 资产模块不能导入旧 `TestPointAsset`。

## 10. Commit 拆分

建议提交顺序：

```text
docs(evie-ai): establish natural language asset authority
```

范围：

```text
AGENTS.md
docs/evie-ai/**
移除或移动未提交的旧产品命名文档目录
```

```text
feat(evie-ai): add collision-safe domain id generators
```

范围：

```text
apps/web-ui-service/app/core/id_gen.py
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_ids.py
```

```text
feat(evie-ai): add requirement and natural language asset models
```

范围：

```text
apps/web-ui-service/app/models/evie_ai/**
apps/web-ui-service/app/models/__init__.py
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_models.py
```

```text
feat(evie-ai): add phase0 natural language asset database schema
```

范围：

```text
apps/web-ui-service/migrations/versions/<actual_revision>_evie_ai_phase0_assets.py
```

```text
feat(evie-ai): add requirement and test asset repositories
```

范围：

```text
apps/web-ui-service/app/repositories/evie_ai/**
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py
```

```text
test(evie-ai): guard natural language asset boundaries
```

范围：

```text
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py
apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_schemas.py
```

## 11. 人工确认结论

1. 项目作用域继续复用现有 `TestProject.project_code`。Phase 0 不新增 Project 表，不增加 `project_id / project_uuid`。
2. TestAsset 创建新版本时：
   - `review_status` 统一重置为 `pending`
   - 原 `conversion_status = succeeded` 或 `stale` 时，新状态为 `stale`
   - 原 `conversion_status = not_started` 或 `blocked` 时，新状态为 `not_started`
   - `processing` 期间不允许直接编辑，必须先结束或取消当前 ConversionAttempt
3. `Requirement.external_requirement_key` Phase 0 只建普通组合索引，不建唯一约束。
4. `RequirementVersion.content_checksum` 只建普通索引，不建唯一约束，允许恢复历史正文。
5. 核心业务 ID 统一使用：
   - `req_<uuid4hex32>`
   - `reqv_<uuid4hex32>`
   - `ta_<uuid4hex32>`
   - `tav_<uuid4hex32>`
   - `tas_<uuid4hex32>`
6. Phase 0 的 `TestAssetSource` 只支持 Requirement 来源，不创建 Document、Section、Page、GenerationContext 和 GenerationBatch 占位字段。
7. 所有未提交的旧产品命名文档内容移动到 `docs/evie-ai`，两套目录不得并存。
