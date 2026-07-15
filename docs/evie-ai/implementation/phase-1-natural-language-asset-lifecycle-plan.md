# EvieAi Phase 1 自然语言测试资产生命周期实施计划

日期：2026-07-15
状态：Approved（文档 PR 合并前不授权启动 Slice 1）
规格合同：`phase-1-natural-language-asset-lifecycle-specification.md`
决策记录：`../decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`

## 1. 实施目标

建设 Phase 1 Asset Lifecycle Core：统一 Intake、Manual/Requirement 来源、幂等、精确重复、
版本、审核、软删除恢复、审计和查询 API。

本计划不包含 AI 生成、Candidate 迁移、语义重复、Asset-to-Case、Compiler、Runner、
TestCase 或完整前端资产中心。

2026-07-15 可实施性评审的 5 项表达缺口已从已批准规格同步到各实施切片和测试矩阵；
本计划不因此重新选择或扩大架构方案。

2026-07-15 最终审查的 P-01～P-06 实施级约束以及 API project scope 传输规则已纳入本计划。
它们不新增 ADR 或合同签字项，只固定分支交付、幂等并发、事务重试和审计生成的可执行语义。

## 2. 实施前置条件

- `dev` 必须包含 PR #4，C-01 已合并并复验。
- 实施前只读确认 branch、HEAD、工作区、Alembic heads/history/current。
- 本地/测试数据库在需要时按受管路径升级；禁止 stamp。
- 不恢复或混入旧链修复和本地私人文件。
- 不新增第三方依赖，除非另行批准。

## 2.1 合同签字状态

| 编号 | 修订项 | 状态 | 阻塞切片 |
|---|---|---|---|
| A-01 | asset_code 服务端生成策略 | 已批准 | — |
| A-02 | project scope / actor / channel 权威合同 | 已批准 | — |
| A-03 | 编辑时 content claim 原子替换 | 已批准 | — |
| A-04 | 来源主表/子表跨表一致性 | 已批准 | — |
| A-05 | 完整 downgrade 数据保护 | 已批准 | — |
| A-06 | 存量 Content Claim 回填冲突处理 | 已批准 | — |
| A-07 | source_identity_hash 算法与跨项目归属 | 已批准 | — |
| A-08 | 审核 row_version 与重复转换语义 | 已批准 | — |
| A-09 | API 状态码、deleted 错误与 keyword 语义 | 已批准 | — |
| A-10 | TestAssetVersion 版本化字段集合 | 已批准 | — |

A-01～A-10 合同门禁已经解除。必须先完成本组权威文档的提交、审查和合并，再从最新
`dev` 创建 Slice 1 功能分支；不得在当前文档分支直接实施代码。

## 2.2 实施级约束状态

| 编号 | 实施级约束 | 状态 |
|---|---|---|
| P-01 | Slice 2 与 Slice 3 原子数据库交付 | 已纳入 |
| P-02 | 幂等 operation、唯一作用域与 CAS 并发算法 | 已纳入 |
| P-03 | 不可变幂等操作结果摘要 | 已纳入 |
| P-04 | Intake 单次竞态回退协调器 | 已纳入 |
| P-05 | Phase 0 持久化不变量 | 已纳入 |
| P-06 | 审计事件生成矩阵 | 已纳入 |

架构待签字项和合同待签字项均为 0。本计划获得 Approved 不代表当前文档分支
可开始业务代码；Slice 1 仍必须等待文档 PR 合并。

## 3. 目标目录

```text
apps/web-ui-service/app/
├── constants/evie_ai.py
├── core/id_gen.py
├── models/evie_ai/
├── schemas/evie_ai/
├── repositories/evie_ai/
├── services/evie_ai/
├── policies/evie_ai/
├── errors/evie_ai.py
└── routers/evie_ai/

apps/web-ui-service/tests/
├── unit/evie_ai/
└── integration/evie_ai/
```

不得建立平行 ID 系统、超大单文件或旧 Workbench facade 代理。

## 4. 切片顺序

### Slice 0：权威规格与追踪

目标：合入本规格、ADR、实施计划、阶段矩阵和任务档案。

文件：仅 `docs/evie-ai/**`。
Migration：无。
验收：链接、命名、阶段边界和决策一致。
Commit：`docs(evie-ai): approve phase1 asset lifecycle contract`

### Slice 1：常量、ID、错误和纯 Policy

目标：建立来源、operation、review transition、audit event、错误码、内容规范化和指纹规则。

幂等 `operation_type` 必须使用集中 Enum/常量，固定为：

```text
create_asset
create_version
restore_historical_version
review_asset
delete_asset
restore_asset
```

不得使用 Router 路径、函数名或自由文本作为 `operation_type`。

修改/新增：

- `app/constants/evie_ai.py`
- `app/core/id_gen.py`（增加 `tar_`、`tae_`，复用现有 UUID helper）
- `app/core/config.py`（解析和校验幂等保留期）
- `app/errors/evie_ai.py`
- `app/policies/evie_ai/source_policy.py`
- `app/policies/evie_ai/content_fingerprint.py`
- `app/policies/evie_ai/review_policy.py`
- `app/policies/evie_ai/asset_code_policy.py`（执行 `asset_code=test_asset_id`，不重写存量）
- `tests/unit/evie_ai/test_evie_ai_config.py`

Policy 不直接读取环境变量。Settings 解析并校验配置，Service 通过依赖或配置对象取得
retention_days。Policy 不读数据库或调用旧链。

测试：ID 格式/碰撞、Unicode/NFC/换行/tags 规范化、canonical JSON 稳定字节流与
SHA-256、合法/非法审核转换、`conversion_status` 合法集不包含 `failed`、稳定错误码。

Commit：`feat(evie-ai): add phase1 lifecycle policies and identifiers`

### Slice 2：ORM 和 Schema

目标：实现已批准的数据结构，不生成 Migration。

模型：

- 通用 `TestAssetSource`
- `TestAssetRequirementSource`
- `TestAssetIdempotencyRecord`
- `TestAssetContentClaim`
- `TestAssetReviewRecord`
- `TestAssetAuditEvent`

`TestAssetIdempotencyRecord` 至少持久化：完整幂等 scope、`request_fingerprint`、
`expires_at`、单调 `generation`、`result_http_status`、`result_type`、`test_asset_id`、
`test_asset_version_id`、`test_asset_review_record_id`、`created`、`reused_existing`、`changed`、
`row_version`、`deleted` 和 `completed_at`。不保存自然语言正文或完整响应。

幂等唯一约束固定为：

```text
UNIQUE(project_code, operation_type, actor_or_client_id, idempotency_key)
```

显式约束名为 `uq_test_asset_idempotency_scope_key`。Content Claim 的
`UNIQUE(project_code, content_fingerprint)` 显式约束名为
`uq_test_asset_content_claims_project_fingerprint`。两个名称都必须纳入 63 字节守卫。

Schema：Manual/Requirement source union、Intake、Version、Historical Version Restore、Review、
Delete/Restore、列表/详情/历史响应和结构化错误。

测试：字段、PK/FK/Unique/Check/Index、不可变时间字段、机器字段拒绝、内部 PK 不暴露、
`UNIQUE(test_asset_pk, source_identity_hash)`、严格非版本领域事实字段集、AST 边界。

#### P-01：Slice 2/3 交付边界

Slice 2 和 Slice 3 可以保留为两个独立 Commit，但必须位于同一功能分支和同一 PR，
并作为一个原子数据库交付单元合并。不得将已依赖 Phase 1 表结构的 ORM 映射
单独合并到尚未包含对应 Migration 的 `dev`。

Slice 2 Commit 后只允许执行纯模型、Schema、metadata 和静态边界测试；完整数据库测试
必须在 Slice 3 Commit 完成后执行。该 PR 合并时必须同时具备最终 ORM、对应线性
Migration、SQLite/PostgreSQL upgrade 测试和 121000 到新 head 的受管升级证据。

#### P-05：Phase 0 持久化不变量

- `TestAsset.current_version_pk` 继续 nullable；
- Phase 1 不为 `current_version_pk` 新增数据库 ForeignKey；
- current version 必须属于对应 TestAsset，由 Repository/Service 在事务中校验；
- 内部数据库 FK 使用 `*_pk` 命名并指向 Integer PK；
- 公共 ID 使用独立字符串列，不作为内部关系 FK；
- `TestAssetVersion`、`TestAssetReviewRecord` 和 `TestAssetAuditEvent` 保持不可变；
- 不修改 Phase 0 已发布公共 ID 前缀和现有数据；
- 不使用 `Base.metadata.create_all()` 补偿 Migration。

负向模型测试必须明确断言 `current_version_pk` 不存在数据库 ForeignKey。

Commit：`feat(evie-ai): add phase1 asset lifecycle models and schemas`

### Slice 3：增量 Migration

目标：从实施时唯一 head 创建 Phase 1 schema，并无损演进 Requirement 来源。

实施前必须执行：

```text
alembic heads
alembic history
alembic current
```

当前预期：`down_revision = "20260713_121000"`；不得只按文档假设。

Slice 3 与 Slice 2 必须按 P-01 在同一功能分支和同一 PR 中原子交付。Migration 必须
同时守住 P-05 的 Phase 0 持久化不变量，不得为 `current_version_pk` 增加 FK，也不得用
`Base.metadata.create_all()` 补齐结构。

Upgrade 顺序：

1. 在任何业务结构变更前预检存量有效资产的 fingerprint、current version 归属和重复组；
   存在冲突时 fail-closed，且不得泄露自然语言正文。
2. 创建新表、显式约束和索引。
3. 创建 Requirement 来源子表。
4. 从现有 `test_asset_sources` 回填 Requirement 关联。
5. 校验总行数、唯一性、父子归属和 FK。
6. SQLite batch rebuild / PostgreSQL 显式 alter，移除主表专用字段。
7. 建立数据库可表达的 FK/Unique 约束，并通过迁移验证、Service 不变量和一致性测试
   保证来源跨表完整性；不使用普通 CHECK 冒充跨表约束，不引入 trigger。
   Phase 1 不在 Requirement 子表复制 `source_type`，因此不使用
   `(test_asset_source_pk, source_type) -> test_asset_sources(id, source_type)` 组合 FK。
   `requirement` 主表记录缺少子记录或 `manual` 主表记录存在子记录时，Repository
   必须 fail-closed；Service 必须在同一事务维护主/子记录；Migration 必须显式校验。
8. Content Claim 回填使用该 revision 内的冻结指纹实现或不可变
   migration-local helper；禁止导入当前 ORM、Service、Policy、Settings 或可演进业务模块。
   固定测试向量必须证明冻结实现与发布时应用 Policy 产生相同结果。
9. 自动扫描所有 Alembic revisions、SQLAlchemy metadata 和显式 schema identifiers，按
   `len(identifier.encode("utf-8")) <= 63` 校验。
10. 运行 bootstrap 回归。

Downgrade 必须执行完整业务数据保护：非 Requirement 来源、Review、Audit、未知来源或
来源不一致任一存在时 fail-closed。Idempotency/ContentClaim 仅在业务检查通过后作为
可重建技术状态删除。

测试：存量重复/缺失 current version/父子归属错误预检 fail-closed 且结构不变、
来源主/子异常状态直接构造后 Repository 和 Migration fail-closed、冻结指纹实现无应用模块导入、
固定测试向量与发布时 Policy 一致、空库
baseline→新 head、121000→新 head、空业务数据 downgrade 成功、不可逆业务数据 downgrade
被拒绝且数据库不变、upgrade/downgrade/upgrade、SQLite FK ON、真实 PostgreSQL、记录数
不变、所有 schema identifier ≤63 字节。

Commit：`feat(evie-ai): add phase1 asset lifecycle database schema`

### Slice 4：Repository 和查询基础

目标：为新表提供 add、flush、query 和并发访问，不控制事务。

内容：

- Source 主/子表持久化与重复来源查询；
- Idempotency scope claim、结果读取、过期清理和并发安全重新占用；
- ContentClaim 按 fingerprint 查询、新建插入、原子更新和删除；
- Review/Audit append-only；
- 列表过滤、详情、版本和审核历史分页；
- 显式 include_deleted 查询。

测试：Repository 无 commit/rollback、唯一冲突、FK、软删除过滤、分页稳定性、N+1 防护。

#### P-02：幂等并发状态算法

1. 按 `project_code + operation_type + actor_or_client_id + idempotency_key` 查询记录。
2. 记录存在且未过期：请求指纹相同时返回已保存操作结果；不同时返回
   `EVIE_IDEMPOTENCY_CONFLICT`。
3. 记录存在但已过期：通过行锁或带旧 `generation`/过期条件的 CAS 更新原记录，
   清除旧结果字段，写入新 request fingerprint、`expires_at` 并递增 `generation`。CAS 失败
   必须重新读取，不得无条件覆盖。
4. 记录不存在：插入新记录；命中 `uq_test_asset_idempotency_scope_key` 时当前事务
   回滚，并在干净事务中重新执行幂等检查。
5. 业务失败时，整条幂等记录随业务事务回滚。
6. 业务成功时，结果摘要与领域数据在同一事务提交。

SQLite 必须通过唯一约束和条件更新提供与 PostgreSQL 行锁等价的 CAS 语义，不得使用
进程内锁作为数据库一致性保护。

#### P-03：幂等重放结果摘要

- 幂等重放返回已保存的不可变操作结果语义，不使用资产当前状态覆盖原操作结果；
- 写接口响应使用操作结果 Envelope；需要最新完整资产时调用详情接口；
- 资源后续被编辑或删除，不改变历史幂等结果中的 `created`、`reused_existing`、
  `changed`、`test_asset_version_id` 或完成时 `row_version`；
- 幂等表不保存 title、precondition、natural_steps、expected_result 或完整响应正文。

Commit：`feat(evie-ai): add phase1 lifecycle repositories`

### Slice 5：API 安全前置修复

目标：在自然语言写 API 上线前解决预检 C-02、C-03、C-05。

- 显式 project scope 验证，禁止自动创建固定默认项目；
- 自然语言请求 body 日志关闭或脱敏；
- EvieAi 结构化领域异常和 FastAPI 映射；
- request_id/correlation_id/channel 统一上下文。

明确组件：

- `ProjectScopeService`：只读校验项目存在、状态和访问权限；
- `ProjectAccessAuthorizer`：项目授权事实源 Adapter；
- `RequestActorContext`：从认证 principal 生成 user/client 稳定身份；
- `RequestChannelContext`：首版由受信任 API Adapter 固定设置为 `api`，不读取请求正文中的 channel。

首版按 A-02 使用认证上下文中的全局 `User.role=admin`，并要求现有项目状态为 active；
列表、详情、版本历史、审核历史和所有写接口均执行这一权限规则。非 admin、项目
不存在或项目非 active 均拒绝。禁止自动创建默认项目。后续如引入项目级
membership/permission，必须独立设计和迁移，不得静默改变首版权限语义。

不得在此切片实现旧 Workbench 修复或全平台大重构。

测试：跨项目拒绝、缺少项目失败、日志不含正文、错误码/HTTP status、敏感信息不泄露；
同时回归既有 API 错误响应、非 EvieAi 路由日志、请求 body 下游可重复读取，以及流式、
multipart、非 JSON 请求不被破坏。不得借此一次性改造所有旧 API 错误格式。

Commit：`fix(evie-ai): enforce lifecycle API safety boundaries`

### Slice 6：Intake Service

目标：实现 Manual/Requirement 创建、幂等和精确重复复用的单事务主链。

事务公共前置顺序固定为请求规范化、request fingerprint、幂等 claim、content fingerprint、
查询 content claim。已有 claim 时进入精确重复复用路径，只读取已有资产、按需新增真实来源
并写复用审计，不创建新的 Asset 或 Version。

未查询到 claim 时，新建路径先创建 Asset 并 flush 内部 PK，再创建首 Version/Source，
插入指向新 Asset 的 claim，设置 current pointer，写 Audit/幂等结果后提交。若 claim 插入触发
并发唯一冲突，当前新建事务整体回滚，不保留任何聚合、claim、审计或幂等结果。
应用层必须在新的干净事务中，从 project scope、请求规范化、request fingerprint 和
幂等检查开始重新执行完整 Intake。已存在同 scope/key 的完成结果时直接重放；否则重读
Content Claim 后进入复用路径。不得继续使用失败 Session，也不得绕过幂等 claim。

Requirement 来源必须验证公共 ID、project scope 和版本归属。

#### P-04：Intake 竞态协调器

`TestAssetIntakeService` 仍是唯一公开资产创建入口。它持有一个事务外层的轻量
`IntakeTransactionRunner`（或等价私有协调方法），由该 runner 为每次尝试创建新 Session 和事务。
这不是第二个业务保存服务，Adapter 仍只调用 `TestAssetIntakeService`。

单次事务内编排不得在失败事务内自行再次调用 `session.begin()`。只有命中以下显式命名约束时
才允许进入竞态回退：

- `uq_test_asset_content_claims_project_fingerprint`；
- `uq_test_asset_idempotency_scope_key`。

不得将任意 `IntegrityError` 解释为精确重复或幂等竞态。Content Claim 唯一冲突后最多执行
一次完整的干净事务重入；重入后仍无法读取获胜 claim 或再次发生非预期冲突时必须
fail-closed，不得无限循环。失败 Session 必须 rollback、close 并废弃；新尝试使用新 Session。

#### P-06：审计事件生成矩阵

| 操作 | 审计事件 |
|---|---|
| 新建资产及首来源 | `asset_created` |
| 重复复用且没有新来源 | `exact_duplicate_reused` |
| 重复复用并新增真实来源 | `source_added` + `exact_duplicate_reused` |
| 创建新版本 | `version_created` |
| 空修改 | 不新增审计事件 |
| 历史版本恢复 | `version_restored` |
| 审核或 reopen | `review_changed` |
| 删除 | `asset_deleted` |
| 恢复 | `asset_restored` |
| 相同幂等键重放 | 不新增审计事件 |
| 新幂等键重复非法状态转换 | 返回 409，不新增审计事件 |

同一事务产生两个事件时，必须共享 `request_id`、`correlation_id`、actor、channel 和
幂等记录引用，但拥有各自独立的 `test_asset_audit_event_id`。

测试：中途失败全回滚、相同 key 重放、payload 冲突、并发 claim 冲突后使用干净事务完整
重进 Intake、同幂等请求不重复来源/审计、重复资产复用并新增来源、
低质量自然语言仍可入库。

Commit：`feat(evie-ai): implement test asset intake service`

### Slice 7：Lifecycle 和 Review Service

目标：实现新版本、历史恢复、审核、删除和恢复。

版本内容 fingerprint 改变时，必须同事务锁定资产及其唯一现有 claim，校验目标指纹未被
其他有效资产占用，再原子更新该 claim，并完成 Version、current pointer、row_version、状态、
审计和幂等结果。任一步失败时整体回滚，原 claim 保持有效；不得临时创建第二条 claim。

合法 `conversion_status` 只包含 `not_started`、`processing`、`blocked`、`succeeded`
和 `stale`，不包含 `failed`。历史版本恢复必须读取指定历史版本内容并创建新版本，
并返回新 `version_id`，不重指 `current_version_pk`。

审核请求必须按最终合同使用 expected_row_version，原子写 ReviewRecord、聚合状态、row_version、
AuditEvent 和幂等结果；重复状态转换不得静默生成新历史。

测试：空修改、version_no 并发、row_version CAS、processing/rejected/deleted 状态、不存在 `failed`
转换状态、历史恢复创建新版本、版本不存在/跨资产 scope 冲突、
审核只针对当前版本、reopen、删除释放 claim、恢复 claim 冲突、幂等重放、不可变审计、
目标指纹冲突保留旧 claim、Version/current pointer 失败整体回滚、并发编辑相同新内容只有
一个成功。

Commit：`feat(evie-ai): implement asset lifecycle and review services`

### Slice 8：Router 和 API 合同

目标：注册 `/api/evie-ai/test-assets` 系列 API，不暴露内部 PK。

Router 仅认证、scope、Schema、Service 调用和响应。所有写接口校验 Idempotency-Key；
版本/审核/删除恢复 Schema 接收 expected_row_version。
历史版本恢复注册
`POST /api/evie-ai/test-assets/{test_asset_id}/versions/{test_asset_version_id}/restore`，其中
`test_asset_version_id` 必须为 `tav_<uuid4hex32>` 公共 ID；成功返回
201 和新创建的版本。所有读写接口均校验全局 admin 与 active project。

`project_code` 传输位置固定为：

| API 类型 | `project_code` 位置 |
|---|---|
| `POST /api/evie-ai/test-assets` | 请求体 |
| `GET /api/evie-ai/test-assets` | 必填 Query 参数 |
| 详情、版本、审核、删除、恢复 | 必填 Query 参数 |

实体接口必须使用 `project_code + public resource ID` 查询，不得先按公共 ID 读取其他项目资源
再在响应阶段隐藏。Requirement 来源必须同时校验：请求 project = TestAsset project =
Requirement project = RequirementVersion project；不匹配返回 `EVIE_SOURCE_SCOPE_MISMATCH`。

测试：201/200/401/403/404/409/422、分页、过滤、deleted 权限、source union、缺少
Idempotency-Key、历史版本恢复、版本不存在/归属错误、项目不存在/非 active、审核版本非当前、
稳定错误结构、OpenAPI。

Commit：`feat(evie-ai): expose natural language asset lifecycle APIs`

### Slice 9：Asset Lifecycle Core 集成验收

目标：完成 SQLite/PostgreSQL、并发、Migration、bootstrap、架构和旧失败基线验收。

输出：完整测试结果、未运行测试、已知失败对比、Migration 证据和实施后报告。

Commit：仅在需要测试/文档修正时创建独立提交，不将失败基线改写为通过。

### Slice 10：Requirement 生命周期（独立后续切片）

目标：Requirement 创建、列表、详情、新版本、软删除恢复和资产来源集成。

它属于 Phase 1，但不得与 Asset Lifecycle Core 的大型 PR 混合。完成前不宣告完整 Phase 1。

建议 Commit：`feat(evie-ai): add requirement lifecycle APIs`

### Slice 11：基础前端资产中心（独立产品排期）

可包含列表、Manual 新建、详情、版本、审核和删除恢复。只复用通用组件，不复用旧
Candidate/TestPoint 页面状态或事实源。

## 5. 测试矩阵

| 测试域 | 必须覆盖 |
|---|---|
| ID/Policy | tar/tae ID、指纹、固定 operation_type、review 状态机、错误码 |
| Model/Schema | FK/Unique/Check/Index、不可变、source union、禁止机器字段 |
| Repository | add/flush/query、无 commit/rollback、软删除、分页 |
| Transaction | 任一步骤失败全部回滚，Session 不继续使用，并发 Claim 回退从完整 Intake 重启 |
| Idempotency | 固定 scope、同 key 同请求/不同请求、generation CAS、失败重试、SQLite/PostgreSQL 并发、过期后重用、不可变结果 Envelope |
| Exact duplicate | 创建复用、编辑冲突、删除释放、恢复冲突、并发 claim |
| Claim replacement | 原子更新冲突保留旧 claim、后续失败全回滚、`UNIQUE(test_asset_pk)`、一个有效资产仅一个当前 claim |
| Version | 空修改、历史恢复创建新版本、版本 scope、新版本状态、不包含 failed、version_no/row_version 冲突 |
| Review | 当前版本、row_version、合法/非法转换、reopen、重复状态转换、不可变记录 |
| Audit | P-06 事件矩阵、双事件共享请求上下文但使用独立 ID、脱敏、与 Version/Review 事实源分离 |
| API | 全局 admin 读写、project_code 固定传输位置、project + public ID 作用域查询、状态码、稳定错误码、Idempotency-Key、历史版本恢复、分页和权限 |
| Migration | SQLite/PostgreSQL、冻结指纹测试向量、无应用模块导入、来源异常状态 fail-closed、数据回填、downgrade 保护、identifier limit |
| Bootstrap | frozen exact、合法后代兼容、未知/非谱系 fail-closed |
| Architecture | 禁止 Candidate/structurer/compiler/runner/TestPointAsset 导入 |
| Legacy | 旧失败节点不得增加，不能用 snapshot 批量更新掩盖变化 |

## 6. 完成定义

只有以下条件全部满足，才能宣告 `Phase 1 Asset Lifecycle Core` 完成：

- Slice 1～9 合并并完成合并后复验；
- 所有新写链路经过统一 Service 和事务；
- SQLite 与真实 PostgreSQL Migration/并发测试通过；
- 幂等、重复、版本、审核、删除恢复和审计合同均有失败路径测试；
- API 安全前置项完成；
- 架构守卫通过；
- 相比冻结旧链基线无新增失败；
- 文档、Excel 任务表和实际 Commit/PR 证据同步。

Requirement 生命周期 Slice 10 完成后，才可以宣告完整 Phase 1 完成。

## 7. 当前切片状态

| 切片 | 状态 |
|---|---|
| Slice 0 文档 | 待提交、审查和合并 |
| Slice 1 Policy/ID | 文档合并后允许启动 |
| Slice 2 ORM/Schema | 依赖 Slice 1；必须与 Slice 3 作为同一原子数据库 PR 交付 |
| Slice 3 Migration | 与 Slice 2 同分支、同 PR；不允许单独合并 Slice 2 |
| Slice 4 Repository | 依赖最终模型，合同已确认 |
| Slice 5 API 安全 | admin + active project 临时策略已确认 |
| Slice 6 Intake | 依赖 Slice 1～5，合同已确认 |
| Slice 7 Lifecycle/Review | 依赖 Repository/Service 基础，合同已确认 |
| Slice 8 Router | 依赖 Slice 5～7，合同已确认 |
| Slice 9 验收 | 结构已确认 |
| Slice 10 Requirement | 拆分已确认 |
| Slice 11 前端 | 拆分已确认，等待产品排期 |
