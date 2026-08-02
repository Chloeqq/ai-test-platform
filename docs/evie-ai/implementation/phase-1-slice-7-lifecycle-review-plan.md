# EvieAi Phase 1 Slice 7 Lifecycle / Review 实施计划

日期：2026-07-31
计划状态：Approved / Ready for implementation
Phase 1 合同状态：Accepted / Active
Slice 7 合同状态：Accepted / Active
Slice 7 实施状态：Not started
Slice 7 Closeout 状态：Not completed

## 1. 文档定位与状态边界

本计划获得用户批准并合并后，授权按照第 14 节批准文件范围和 S7-T01 至 S7-T07 的顺序实施，
但不授权任何超范围实现。本文件不改变任何已接受的架构、模型、Schema、Migration、API 或前端合同。

- 基线：`origin/dev@91ecd1b43d38d67d4c8a25fac634a1664bfe2208`。
- Slice 6 Closeout：Completed；本计划只复用其可信身份、项目作用域、actor/channel/trace、
  事务、幂等和审计基础，不修改其合同或实现。
- Phase 1 overall status：In Progress。
- Phase 1 closeout status：Not completed。
- Slice 8 status：Not started；本计划不开始 Router 或 API。
- Slice 7 和 Slice 8 完成均不等于 Phase 1 已完成，也不授权 Phase 2。

本计划遵循以下解释顺序：

```text
ADR-0002
-> ARCHITECTURE_BASELINE
-> evie-ai overview
-> target capability map
-> phase traceability
-> Phase 1 Specification and approved Slice contracts
-> approved product decisions
-> current code
```

代码只能说明当前可复用基础，不能覆盖上述合同。任务授权中说明 D1-D10 已获得产品批准；
但该产品原型最终基线文件未出现在干净 `origin/dev` 的可定位文档中。本计划不从缺失文件
推导新的后端规则；它只采用本计划列出的、已由 Phase 1 合同明确的技术边界。

### 1.1 Required Planning Content Index

| 必需主题 | 本文位置 |
|---|---|
| Status / Objective / Contract evidence / Current implementation facts | 第 1--4 节。 |
| In scope / Explicitly out of scope | 第 5--6 节。 |
| Domain commands / Inputs and outputs / command idempotency | 第 7 节。 |
| State transition matrix / Version semantics / Review semantics / Delete-restore semantics | 第 8--9 节。 |
| Transaction boundaries / Concurrency and CAS / Authorization and project scope | 第 10 节。 |
| Execution model: synchronous, async I/O and background processing | 第 11 节。 |
| Error model / Audit and observability | 第 12--13 节。 |
| Repository changes / Service changes / Approved implementation file scope | 第 14 节。 |
| Delivery tasks / Test matrix / Quality gate / Regression baseline | 第 15--17 节。 |
| Review gates / Rollback strategy / Acceptance criteria | 第 18 节。 |
| Risks / Open questions / Deferred decisions | 第 19 节。 |

## 2. Objective

在不创建 HTTP API、前端页面、机器执行工件或新数据模型的前提下，实施两个唯一的后端
编排入口：

- `TestAssetLifecycleService`：创建自然语言资产新版本、从历史版本恢复为新版本、软删除、恢复；
- `TestAssetReviewService`：审核、拒绝和重新打开当前自然语言资产版本。

它们共同解决的单一业务问题是：让已经通过 Slice 6 统一 Intake 创建的 `TestAsset`，能够在
项目作用域和可信身份约束下，安全地演进、审核、删除和恢复，同时保持自然语言资产、版本、
来源、审核、内容声明、幂等结果和审计事实的一致性。

## 3. 权威合同证据

| 证据 | 已接受结论 | 对 Slice 7 的约束 |
|---|---|---|
| [ADR-0002](../decisions/ADR-0002-target-architecture-v2.md) | `TestAsset` 与 `TestCase` 生命周期分离；自然语言资产不承载机器执行语义。 | 不得创建 Candidate、Preview、DSL、`script_code`、TestCase、Compiler 或 Runner 行为。 |
| [ARCHITECTURE_BASELINE](../ARCHITECTURE_BASELINE.md) | 自然语言资产域拥有资产、版本、来源、审核、审计、幂等和生命周期事实；Asset-to-Case 是唯一 NL 到 machine 边界。 | Slice 7 只能处理自然语言资产生命周期，不能提前开始转换。 |
| [Phase 1 Specification](phase-1-natural-language-asset-lifecycle-specification.md) | 规定两个唯一 Service、版本不可变、审核状态机、软删除、内容声明、幂等、审计和 admin-only 项目范围。 | 以该文件的状态、事务、错误和持久化合同为实现依据。 |
| [Phase 1 Overall Plan](phase-1-natural-language-asset-lifecycle-plan.md) | Slice 7 名称为 `Lifecycle 和 Review Service`；Slice 8 才是 Router/API。 | 只实施本计划的 Service/Repository/test 层，不创建 Router、Schema 或前端。 |
| [Phase Traceability](phase-traceability.md) | Slice 7：`Accepted / Active`、`Not started`；Slice 8：`Not started`；Phase 1 仍进行中。 | 计划已批准；Slice 7 implementation status 保持 `Not started`，直到实施代码首次提交。 |
| [Slice 6 Intake Plan](phase-1-slice-6-intake-plan.md) 与 [Slice 6 Closeout](phase-1-slice-6-intake-closeout.md) | 可信 principal、项目作用域、actor/channel/trace、幂等、内容指纹、事务回滚和审计安全基础已交付。 | 必须复用公开基础；不得复制或导入 Intake 私有实现。 |
| [Coding Standards](../engineering/coding-standards.md) 与 [Code Quality Gate](../engineering/code-quality-gate.md) | Service 拥有事务；Repository 不 commit/rollback；使用注入 Clock；zero new violations。 | Slice 7 新增和修改代码必须通过 `evie-ai-code-quality`，不得扩大 baseline。 |

## 4. 当前实现基础与缺口

| 层级 | 已存在且可复用的事实 | Slice 7 缺口或使用方式 |
|---|---|---|
| ORM 模型 | `TestAsset`、不可变 `TestAssetVersion`、`row_version`、`deleted_at`、`TestAssetReviewRecord`、`TestAssetAuditEvent`、`TestAssetIdempotencyRecord`、`TestAssetContentClaim` 均已存在。 | 不修改模型、字段、约束或 Migration。 |
| 常量与错误 | 生命周期 operation、审核 action、审计事件类型、稳定错误码和 `LIFECYCLE` / `REVIEW` stage 已集中定义。 | 不新增状态或错误码，不散落 magic string。 |
| Policy | `review_policy` 已定义 approve、reject、reopen 的合法转换及 reopen reason 规则；request fingerprint 已覆盖生命周期写操作。 | Service 调用既有 Policy 和指纹函数，不重写规则或哈希。 |
| Repository | Asset、Version、Idempotency、Content Claim、Review Record、Audit 的读取/写入基础已存在，且不自行 commit/rollback。 | 需要增加受限的生命周期 CAS 与恢复 claim 操作；不得直接在 Service 做 ORM 更新。 |
| Service | `TestAssetIntakeService` 已是唯一创建入口；Slice 5 的可信 principal、项目授权、项目范围、actor/channel/trace 已存在。 | 尚无 Lifecycle / Review 服务；不得将写操作加回 Intake 或创建平行入口。 |
| 测试基础 | `conftest.py` 提供真实 SQLite/SQLAlchemy 和全部 EvieAi 表；已有 Repository、协调、治理、Policy、Intake 与架构守卫测试。 | 新增生命周期与审核服务真实持久化测试，并最小更新相关 Repository/架构守卫测试。 |
| 冻结旧链 | Candidate/Preview、旧 workbench 生成、直接 Compiler、Runner 等遗留链仍存在于仓库。 | 不得复用为 Slice 7 依赖；架构守卫必须阻止其进入新服务。 |

以下是已识别的最小 Repository 能力缺口，不是新数据模型：

1. 在一次条件更新中推进 current version、审核状态、转换状态和 `row_version`；
2. 在一次条件更新中应用审核状态转换或 `deleted_at` 变更；
3. 读取已删除聚合的 current version，仅用于恢复前的事实校验；
4. 在资产仍处于删除状态时，受限地重新获取其 current content claim，然后才清除 `deleted_at`。

第 4 项必须只服务恢复合同：验证 aggregate、项目和 current content 归属，使用既有唯一约束，
不形成可对任意已删除资产绕过 active-asset 检查的通用入口。

## 5. In Scope

1. `TestAssetLifecycleService` 的版本创建、历史版本恢复、软删除和恢复编排。
2. `TestAssetReviewService` 的 approve、reject、reopen 编排和不可变 `ReviewRecord`。
3. 已有 `TestAsset`、Version、Claim、Idempotency、Review、Audit Repository 的最小受限读写能力。
4. 所有 Slice 7 公开写操作的 project scope、可信 principal、actor/channel/trace、幂等和
   乐观并发语义。
5. 真实 SQLite/SQLAlchemy 事务回滚、并发冲突、重复重放、审计安全和架构边界测试。
6. 对 Slice 7 修改范围运行质量门禁、相关回归和完整 web-ui 对比归因。

## 6. Explicitly Out of Scope

以下内容不在本计划、实现或验证范围内：

- Router、HTTP API、Request/Response Schema、HTTP 状态映射和前端；它们属于 Slice 8 或独立前端工作；
- Slice 6 Intake 行为、Slice 10 Requirement Lifecycle、Slice 11 前端资产中心及相关产品实现、Slice 8、Phase 2 及以后；
- AI 生产者、Candidate、Preview、语义去重、RAG、Embedding；
- Asset-to-Case、Intent IR、Binding、Compiler、TestCase、Runner、报告和执行；
- ORM、Migration、数据回填、旧链删除或 CI-B01/CI-B02 修复；
- AsyncSession 迁移、双 Repository 栈、BackgroundTasks、Celery、RQ、Queue、Worker、Outbox、
  事件总线或任何外部网络副作用；
- 质量门禁逻辑、质量 baseline、工具版本、阈值、exclude、ignore 或 `noqa` 豁免修改；
- 任何默认 `project_code`、项目自动创建、客户端身份覆盖、内部 PK 暴露或全局 Session。

## 7. 服务合同、输入与输出

### 7.1 共同输入上下文

每个公开写操作必须显式接收或由可信调用方传入以下已批准上下文，且不得从请求正文、
username、email、内部 `User.id` 或客户端字段推断：

| 输入 | 事实来源 | 规则 |
|---|---|---|
| `TrustedUserPrincipal` | Slice 5 `UserPublicIdentityService` | 只接受合法、已认证、active 的可信 principal；actor 固定为 `user:<user_public_id>`。 |
| `project_code` | 已验证的请求作用域 | 不能为空，不得默认或回退；先授权再验证 active Project 范围。 |
| actor/channel/trace | Slice 5 context 服务 | 复用 `RequestActorContext`、`RequestChannelContext`、`RequestTraceContext`；客户端不得覆盖。 |
| Idempotency-Key | 调用合同 | 所有公开写操作均必填；作用域为 `project_code + operation + actor + key`。 |
| `expected_row_version` | 调用方基于已读公开事实提供 | 所有 mutation 必填；不匹配返回稳定并发错误，不自动重试。 |
| 注入 UTC Clock | Service 构造依赖 | 生成审核时间、审计发生时间和幂等期限判断；禁止 `datetime.now()` / `utcnow()`。 |

服务只接受现有的显式类型化生命周期、审核和 trace 输入；不使用核心业务 `dict`、`Any` 或
未验证的 ORM `User`。函数签名、参数数量和复杂度必须满足 Quality Gate；复杂编排拆分为
私有的单一职责步骤，但不创建平行业务入口。

### 7.2 `TestAssetLifecycleService`

服务是以下写行为的唯一公开后端入口：

| 操作 | 必要业务输入 | 成功输出 | 不承担的职责 |
|---|---|---|---|
| 创建新版本 | asset public ID、自然语言版本内容、`expected_row_version`、idempotency key、可信上下文 | 现有资产上的新 `TestAssetVersion`、新的 row version、`changed=true`；相同规范化内容返回当前版本和 `changed=false`。 | 不做质量评分、机器化、来源新增或 TestCase 创建。 |
| 历史版本恢复 | asset public ID、目标历史 version public ID、必填 restore reason、`expected_row_version`、idempotency key、可信上下文 | 用历史自然语言内容创建的全新 current version。 | 不把 current pointer 直接指回历史记录，不修改历史版本。 |
| 删除 | asset public ID、必填 delete reason、`expected_row_version`、idempotency key、可信上下文 | 保留 current version/source/review 的已删除资产结果。 | 不删除历史数据，不创建新版本，不取消或修改未来转换工作。 |
| 恢复 | asset public ID、必填 restore reason、`expected_row_version`、idempotency key、可信上下文 | 已恢复的同一聚合，row version 已推进。 | 不创建新版本，不自动合并或替换重复资产。 |

### 7.3 `TestAssetReviewService`

服务是以下审核写行为的唯一公开后端入口：

| 操作 | 必要业务输入 | 成功输出 | 不承担的职责 |
|---|---|---|---|
| approve | asset public ID、current version public ID、`expected_row_version`、idempotency key、可信上下文 | 当前版本审核状态、不可变 Review Record、更新后的 row version。 | 不改变自然语言内容或 conversion status。 |
| reject | 同上，加 comment/reason（按既有 Schema/Policy 的必填规则） | 同上。 | 不删除资产或创建版本。 |
| reopen | 同上，加必填 reopen reason | `approved` 或 `rejected` 回到 `pending` 的事实和 Review Record。 | 不绕过 Policy，不审核历史版本。 |

`TestAssetIntakeService` 继续是唯一新资产创建入口。Lifecycle / Review 服务不得通过任意
辅助函数、Repository 直调、Router 或批处理入口创建新的 `TestAsset`。

### 7.4 逐命令幂等边界

所有下列命令都受 D-04 约束，必须使用 `project_code + operation_type + actor_or_client_id +
idempotency_key` 作用域。相同 scope/key 且 request fingerprint 相同，必须返回已持久化的原
业务结果；不同 fingerprint 必须返回 `EVIE_IDEMPOTENCY_CONFLICT`。completed replay 必须读取
并验证 winner 的公开结果，不能仅因幂等记录存在便返回成功。失败事务不得保留 completed
winner，过期 generation 仅按既有 Idempotency Repository CAS 接管。

| 命令 | Idempotency key | operation type 和指纹受控字段 | Replay 结果与 winner | expected_row_version / CAS | 合同证据 |
|---|---|---|---|---|---|
| create version | 必填 | `create_version`；asset public ID、expected row version、规范化六项自然语言内容、规范化 optional reason。 | 原 Asset/新或 current Version public ID、`changed`、row version；winner result 必须持久化。 | 必填；Asset/Version/Claim CAS，row 冲突不自动重试。 | Specification 5、7、7.1；`request_fingerprint.py` `CreateVersionFingerprintInput`。 |
| restore historical version | 必填 | `restore_historical_version`；asset public ID、历史 Version public ID、expected row version、规范化必填 reason。 | 原 Asset/新 Version public ID、`changed`、row version；winner result 必须持久化。 | 必填；只创建新 Version，不重指历史 Version。 | Specification 5、7；`RestoreHistoricalVersionFingerprintInput`。 |
| approve | 必填 | `review_asset`；asset/version public ID、expected row version、`approve`、规范化 comment/reason。 | 原审核状态、Review Record public ID、row version；winner result 必须持久化。 | 必填；审核状态 CAS；不同 key 的重复最终转换是非法转换。 | Specification 5、8、8.1；`ReviewAssetFingerprintInput`。 |
| reject | 必填 | `review_asset`；asset/version public ID、expected row version、`reject`、规范化 comment/reason。 | 原审核状态、Review Record public ID、row version；winner result 必须持久化。 | 必填；审核状态 CAS。 | Specification 5、8、8.1；`ReviewAssetFingerprintInput`。 |
| reopen | 必填 | `review_asset`；asset/version public ID、expected row version、`reopen`、规范化 comment/reason。 | 原审核状态、Review Record public ID、row version；winner result 必须持久化。 | 必填；Policy 要求 reason，审核状态 CAS。 | Specification 5、8、8.1；`ReviewAssetFingerprintInput`。 |
| delete | 必填 | `delete_asset`；asset public ID、expected row version、规范化必填 reason。 | 原 Asset public ID、`deleted=true`、row version；winner result 必须持久化。 | 必填；删除状态 CAS 与 Claim release 同事务。 | Specification 5、9；`DeleteAssetFingerprintInput`。 |
| restore | 必填 | `restore_asset`；asset public ID、expected row version、规范化必填 reason。 | 原 Asset public ID、`deleted=false`、row version；winner result 必须持久化。 | 必填；先 Claim acquire，再恢复状态 CAS。 | Specification 5、9；`RestoreAssetFingerprintInput`。 |

`approve`、`reject` 和 `reopen` 共享 `review_asset` operation type，但其 action、comment 和
reason 都进入指纹，因此不是以 Slice 6 Intake 的创建机制替代审核合同。

## 8. 状态转换矩阵

### 8.1 Review Status Transition Matrix

审核只改变 `review_status`；它不创建 Version、不改变自然语言正文、不改变 `conversion_status`，
也不执行 delete/restore。下表以既有 `review_policy` 和 Specification D-07/A-08 为唯一依据。

| Current state | Command | Preconditions | Resulting state | row_version behavior | ReviewRecord behavior | Audit behavior | Error on rejection | Contract evidence |
|---|---|---|---|---|---|---|---|---|
| `pending` | approve | Asset active；target 是 current Version；`expected_row_version` 匹配。 | `approved` | CAS 成功后 +1。 | 插入一条 immutable record，action=`approve`。 | 一条 `review_changed`。 | 无；前置失败按对应行。 | Specification 8、8.1；`review_policy.py` transitions。 |
| `pending` | reject | Asset active；target 是 current Version；`expected_row_version` 匹配；reason 非空。 | `rejected` | CAS 成功后 +1。 | 插入一条 immutable record，action=`reject`。 | 一条 `review_changed`。 | 缺 reason 或其他非法转换：`EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8、8.1；`review_policy.py` reason policy。 |
| `approved` | reopen | Asset active；target 是 current Version；`expected_row_version` 匹配；reopen reason 非空。 | `pending` | CAS 成功后 +1。 | 插入一条 immutable record，action=`reopen`。 | 一条 `review_changed`。 | 缺 reason：`EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8、8.1；`review_policy.py` transitions。 |
| `rejected` | reopen | Asset active；target 是 current Version；`expected_row_version` 匹配；reopen reason 非空。 | `pending` | CAS 成功后 +1。 | 插入一条 immutable record，action=`reopen`。 | 一条 `review_changed`。 | 缺 reason：`EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8、8.1；`review_policy.py` transitions。 |
| `pending` | reopen | 无合法 Policy transition。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8；`review_policy.py` transitions。 |
| `approved` | approve | 无合法 Policy transition。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8.1。 |
| `rejected` | reject | 无合法 Policy transition。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8.1。 |
| `approved` | reject | 无合法 Policy transition。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8；`review_policy.py` transitions。 |
| `rejected` | approve | 无合法 Policy transition。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_INVALID_REVIEW_TRANSITION`。 | Specification 8；`review_policy.py` transitions。 |
| 任意 review status，Asset deleted | approve/reject/reopen | A-08 先校验 Asset 未删除。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_ASSET_DELETED`。 | Specification 8.1 step 1；D-08。 |
| 任意 review status，target 非 current Version | approve/reject/reopen | Asset active，但 target 不等于 `current_version_pk`。 | 无变化。 | 不变。 | 不新增。 | 不新增。 | `EVIE_REVIEW_VERSION_NOT_CURRENT`。 | Specification 8、8.1 steps 2--9。 |
| 任意 active review status | create version | 内容变化、Asset active、非 `processing`，Version/Claim CAS 成功。 | 新 current Version 为 `pending`。 | Version/current-pointer mutation 成功后 +1。 | 不创建虚假 ReviewRecord。 | 一条 `version_created`。 | 按第 8.2 节；不适用 review transition。 | Specification 7、8；Specification 8 明确新版本 reset pending。 |
| 任意 active review status | restore historical version | 指定历史 Version 属于同一 Asset；reason、CAS 和 Claim 条件成立。 | 新 current Version 为 `pending`。 | Version/current-pointer mutation 成功后 +1。 | 不创建虚假 ReviewRecord。 | 一条 `version_restored`。 | 按第 8.2 节；不适用 review transition。 | Specification 7、8；Specification 8 明确新版本 reset pending。 |

相同 Idempotency-Key 且相同 fingerprint 的审核命令直接返回其已持久化 winner，不再次执行上表的
状态转换、不插入新的 ReviewRecord 或 Audit。不同 key 对已经完成的同一最终转换，仍按上表返回
`EVIE_INVALID_REVIEW_TRANSITION`。

### 8.2 Version and Conversion Status Rules

| Preconditions and command | Version result | review_status | conversion_status | row_version / Audit | Stable rejection and evidence |
|---|---|---|---|---|---|
| Asset active；create version 内容与 current 规范化 fingerprint 不同；current conversion=`not_started` 或 `blocked`。 | 创建 `version_no + 1` 并切换 current pointer。 | `pending`。 | `not_started`。 | +1；`version_created`。 | Specification 7 D-06。 |
| Asset active；create version 内容不同；current conversion=`succeeded` 或 `stale`。 | 创建 `version_no + 1` 并切换 current pointer。 | `pending`。 | `stale`。 | +1；`version_created`。 | Specification 7 D-06。 |
| Asset active；restore historical version；目标历史 Version 属于同一 Asset；reason、CAS、Claim 条件成立。 | 复制历史自然语言内容为全新 `version_no + 1`；不得重指历史 Version。 | `pending`。 | 按该资产当前 conversion 的上述 D-06 映射。 | +1；`version_restored`。 | Specification 7 D-06、Specification 8。 |
| current conversion=`processing`；create/restore historical version。 | 无 Version 或 pointer 变化。 | 不变。 | 不变。 | 不变；无 Audit。 | `EVIE_ASSET_STATE_CONFLICT`；Specification 7 D-06。 |
| Asset deleted；create/restore historical version。 | 无 Version 或 pointer 变化。 | 不变。 | 不变。 | 不变；无 Audit。 | `EVIE_ASSET_DELETED`；Specification 7 D-06、D-08。 |
| 规范化内容与 current 相同；create version。 | 不创建伪 Version，返回 current。 | 保持。 | 保持。 | 不 bump row；无 Audit。 | Specification 7 D-06。 |

合法 `conversion_status` 仅为 `not_started`、`processing`、`blocked`、`succeeded`、`stale`；
不得引入 `failed`。除 D-06 已明确的 `processing` 和 deleted 限制外，本计划不凭一般经验新增
内容编辑禁令。

### 8.3 Asset Delete / Restore Matrix

删除和恢复只改变 `deleted_at`、Claim 与 `row_version`，不创建内容 Version，也不改变
`review_status`、`conversion_status` 或 current Version 内容。每个输入组合只有以下一个稳定结果：

| Asset state / idempotency input | Command | Result | row_version / Claim | Audit / completed winner | Stable error and evidence |
|---|---|---|---|---|---|
| 任意原命令已成功；相同 scope/key 且相同 fingerprint | delete 或 restore replay | 返回原已持久化 delete/restore 结果。 | 不再改变 row 或 Claim。 | 不新增 Audit；读取同一 completed winner。 | Specification 5 D-04、Specification 9 D-08。 |
| 任意相同 scope/key，但 fingerprint 不同 | delete 或 restore | 无业务执行。 | 不变。 | 不新增 Audit/winner。 | `EVIE_IDEMPOTENCY_CONFLICT`；Specification 5 D-04。 |
| Asset deleted；new key | delete | 无业务执行。 | 不变；不重复 release Claim。 | 不新增 Audit/winner。 | `EVIE_ASSET_STATE_CONFLICT`；Specification 9 D-08 的“不同 key 重复删除返回 409 状态冲突”。 |
| Asset active；new key | restore | 无业务执行。 | 不变；不 acquire Claim。 | 不新增 Audit/winner。 | `EVIE_ASSET_STATE_CONFLICT`；Specification 9 D-08 的“不同 key 重复恢复返回 409 状态冲突”。 |
| Asset deleted；new key | restore | 先获取 current content Claim，再清除 `deleted_at`。 | CAS 成功后 +1；Claim 已恢复。 | 一条 `asset_restored`；同一事务内完成 winner。 | 若 Claim 被其他 active Asset 占用：`EVIE_RESTORE_DUPLICATE_CONFLICT`；Specification 6.3、9。 |
| 已由前次 restore 变为 active；new key | restore | 无业务执行。 | 不变。 | 不新增 Audit/winner。 | `EVIE_ASSET_STATE_CONFLICT`；Specification 9 D-08。 |
| Asset active；new key | delete | 设置 `deleted_at`，保留 current/source/review/version。 | CAS 成功后 +1；同一事务 release current Claim。 | 一条 `asset_deleted`；同一事务内完成 winner。 | 无；前置/CAS 失败按第 10、12 节。 | Specification 6.3、9 D-08。 |

删除后 create-version、restore-historical-version 和所有 review command 由第 8.1/8.2 节拒绝；
恢复不会自动审核、重新转换、复制来源或创建新 Version。

## 9. 版本、审核、删除与恢复的不可变事实

1. `TestAssetVersion` 的自然语言正文只在创建时写入；任何内容变化都创建新版本。
2. `TestAsset.current_version_pk` 只能由受限 Repository 条件更新，且新 Version 必须属于同一
   Asset；不得绕过 Repository 直接赋 ORM 字段。
3. 创建期之外，所有成功 mutation 按 CAS 将 `row_version` 精确推进一次；冲突不自动重试。
4. 新版本必须将审核状态置为 `pending`，并按第 8.2 节映射转换状态。
5. 历史恢复复制历史内容为新版本；不得修改历史记录、复用历史 Version 作为 current 或删除历史。
6. Review Record 是 insert-only：保存 from/to、action、reviewer public identity、时间、
   request/correlation/idempotency 快照以及受控 comment/reason。
7. 删除是唯一以 `TestAsset.deleted_at` 表达的软删除事实；不得硬删除 Aggregate、Version、
   Source、Review、Audit、Idempotency 或 Claim 历史。
8. 删除释放 current fingerprint claim；恢复必须先重新获取完全相同的 current fingerprint claim，
   再恢复 active 状态。删除资产不能作为自动复用或自动合并目标。

## 10. 事务、并发、幂等与权限设计

### 10.1 事务边界

每次首次执行的公开写操作只使用一个 Service 拥有的 `with session.begin()` 事务。该事务的顺序
固定为：

1. 创建或以 generation CAS 重新占用 pending/in-progress Idempotency coordination；
2. 写入或条件更新业务事实；
3. 写入适用的 Version、ReviewRecord 与 Claim；
4. 写入成功 Audit Event；
5. 写入 completed idempotency result 和 winner public result summary；
6. `flush` 后执行所有关系、scope、row-version、Claim、winner 与返回事实校验；
7. 仅在全部校验成功后由同一个 `session.begin()` 统一 commit；Service 仅在 commit 成功后返回。

这里的 pending/in-progress 仅表示现有 `TestAssetIdempotencyRecord.completed_at is None` 的协调
记录，不新增状态字段、任务表或后台执行协议。

因此下列事实必须共同提交或共同回滚：

- Asset 条件更新、Version 创建或 current pointer 更新；
- Claim 替换、释放或恢复前重获；
- Review Record；
- Audit Event；
- pending/in-progress Idempotency coordination、completed result 与 winner public result；
- 操作结果的提交前一致性校验。

`TestAssetIdempotencyRepository.add()` 和 `.complete()` 已在同一同步 Session 内工作，且自身不
commit/rollback；Slice 7 必须沿用这一模型。不得在业务 commit 后启动第二个事务补写 completed
winner。若 `.complete()` 未更新一条期望 generation 记录，或最终 winner 无法读取/验证，必须在
第一个事务内 fail-closed 并 rollback。

Repository 只查询、`add`、`flush` 或执行受限条件更新；不得 `commit`、`rollback`、持有全局
Session、吞掉异常或启动独立事务。任何不可读 winner、丢失 Version、错误项目关系、损坏结果、
非白名单数据库异常或最终校验失败，都必须在提交前抛出稳定领域错误并完整回滚。

### 10.2 并发与 CAS

| 风险 | 机制 | 预期结果 |
|---|---|---|
| 同一 Asset 并发 mutation | asset lock/条件 `row_version` 更新 | 仅一个成功；其他请求为 `EVIE_ROW_VERSION_CONFLICT`，不自动重试。 |
| 同一 Asset 并发新 Version | 资产锁、`version_no` 唯一约束和 CAS | 只创建一个正确下一版本；失败不留下孤儿 Version/Audit/Claim。 |
| 同一 fingerprint 的编辑/恢复 | `TestAssetContentClaim` 唯一约束和原子 replace/acquire | 已被其他 active asset 占用时分别返回 exact duplicate 或 restore duplicate 冲突。 |
| 相同 idempotency key | 既有 Claim/Generation CAS | 同指纹重放原结果；不同指纹为 `EVIE_IDEMPOTENCY_CONFLICT`；过期 generation 仅按既有 CAS 规则接管。 |
| idempotency/claim 竞态 | 复用既有 Repository 的 winner 读取与提交前结果校验 | winner 不可读、跨项目或结果损坏时 fail-closed，不返回局部成功。 |

Slice 7 不把 Intake 的白名单唯一约束重试机制复制为通用 lifecycle 重试。生命周期的
`row_version`、Version 和 Claim 冲突必须按合同返回稳定冲突；只有既有 Idempotency generation
CAS 的受限接管行为可以复用。

### 10.3 认证、授权与 project scope

顺序固定如下，且在每次新事务或允许的 idempotency generation 接管中重新执行：

```text
TrustedUserPrincipal
-> active global-admin authorization
-> explicit project_code validation and active Project scope
-> trusted actor/channel/trace construction
-> idempotency scope and request fingerprint
-> aggregate/version/claim work
```

- 仅 active global admin 可读写 Phase 1 Asset Lifecycle Core 范围；不设计新的 RBAC。
- 所有 Asset、Version、Review、Claim、Idempotency 和 Audit 读取必须受 `project_code` 限制。
- 不允许默认项目、自动创建 Project、根据内部 PK/用户名/email 回退或客户端指定 actor/channel。
- 不暴露内部 ORM PK；审计和结果只使用已批准的 public IDs 与受控状态摘要。

## 11. Execution Model: Synchronous, Async I/O and Background Processing

### 11.1 固定执行结论

**Execution model decision: Synchronous domain execution approved.**

以下 Slice 7 领域命令必须同步执行，并在调用返回前完成唯一的数据库事务：

- create version；
- restore historical version；
- approve；
- reject；
- reopen；
- soft delete；
- restore deleted asset。

每个命令在返回前只能明确给出 success 或稳定领域错误。Audit Event 和 completed idempotency
result 必须在同一事务内持久化、flush 并完成最终校验；Service 只能在统一 commit 成功后返回。

Service 对外领域结果只包含第 7 节已批准的 public `test_asset_id`、适用时的
`test_asset_version_id` 或 `test_asset_review_record_id`、`changed`、最新 `row_version` 和受控的
review/deletion 状态。不得返回内部 ORM PK、完整 Audit payload、IdempotencyRecord、原始 key、
generation 或内部 winner 数据。失败则必须完整 rollback；不得返回 `processing` 后由后台任务修改
这些核心业务事实。

### 11.2 术语边界

| 术语 | 本计划定义 | Slice 7 结论 |
|---|---|---|
| Synchronous domain command | 调用方等待最终领域结果；Service 在返回前完成或回滚单一事务。 | 所有七个 Slice 7 写命令必须采用此模式。 |
| Async I/O | Python/FastAPI 的 `async` / `await` 实现方式；它本身不表示请求提前返回或事务在后台继续。 | 当前不采用；未来 Slice 8 如使用 `async def`，必须单独明确安全适配方式。 |
| Background job | 请求先返回，Worker 在后续执行任务并写事实。 | 不得用于 Slice 7 核心领域事实。 |

不得将 `async def`、非阻塞 I/O、队列排队或任务 Worker 误写为并发控制、事务完成或幂等保证。

### 11.3 当前数据库访问模型与适配边界

当前批准的实现使用 SQLAlchemy synchronous `Session`：

- `app/core/database.py` 以 `create_engine` 和 `sessionmaker` 创建 `SessionLocal`；
- `app/repositories/base.py` 的 Repository 仅接收同步 `Session`；
- `TestAssetIntakeService` 接收 `Callable[[], Session]`，并以 `with session.begin()` 在返回前
  完成事务；
- 现有 `app/services/evie_ai/**` 和 `app/repositories/evie_ai/**` 未使用 `AsyncSession`。

Slice 7 必须沿用这一同步 Session 模型。不得为了“支持异步”全面迁移 Session、同时维护同步/异步
两套 Repository，或在同步事务中跨 `await` 调用外部服务。未来 Slice 8 如选择 `async def`
Router，必须在 Slice 8 合同中定义它如何安全调用既有同步领域事务；不得反向改变 Slice 7
Service、Repository 或事务边界。

### 11.4 并发原则

异步执行不能代替并发控制。每个同步写命令仍必须依赖：

- `expected_row_version`；
- aggregate 条件更新和 CAS；
- 数据库唯一约束；
- 原子 content claim replace/acquire；
- trusted project scope；
- current version 验证；
- commit 前的最终事实校验。

任务排队、串行调用或请求重试不得让基于陈旧事实的第二个业务命令自动成功。row-version、
Version、Review、delete/restore 和 Claim 冲突必须按照第 10 节与第 12 节的稳定领域错误
fail-closed。

### 11.5 禁止后台化的核心事实

以下事实必须在同一个同步事务内持久化，禁止交给 Background job 延迟写入：

- `TestAssetVersion`；
- current-version binding；
- `review_status`；
- `ReviewRecord`；
- `deleted_at`；
- Content Claim；
- `row_version`；
- successful Audit Event；
- idempotency completed result。

### 11.6 Deferred Post-Commit Side Effects

notification、search indexing、analytics、external audit export、webhook 和 data-warehouse event
可在未来作为 post-commit side effect 另行设计，但 Slice 7 不实现它们。核心事务不得调用外部
网络服务，也不得新增 Outbox、Queue、Worker、任务表或事件总线；这些都需要独立批准合同。

### 11.7 超时、取消与失败语义

1. 数据库 timeout、deadlock、lock conflict 或未分类持久化异常必须使 `with session.begin()` 退出并 rollback；不得
   提交部分事实。实现只使用已批准的稳定领域错误，不能为了超时新增自由错误码。
2. `expected_row_version`、唯一 Claim 或状态条件冲突必须由相应 CAS/约束转换为受控领域失败；
   不得用自动业务重试把陈旧命令变成成功。
3. 调用在 commit 前被取消、抛出异常或终止时，Idempotency 不得完成，事务必须 rollback；同 key
   之后可以按既有合同安全重试。
4. commit 成功后若响应中断，调用方必须使用相同 idempotency key 重放以读取已持久化 winner，
   不得再次执行业务命令。
5. 任何 final fact validation 在 commit 前失败时，Version、ReviewRecord、Audit、Claim 和
   Idempotency result 必须共同回滚。
6. 不得自动重试结果未知的完整领域事务；只有既有、受限的 idempotency generation CAS 接管可按
   合同执行，且仍必须在新事务内重新校验 scope 与 winner 事实。
7. HTTP request cancellation、disconnect 行为和 future `async def` Router 对同步 Service 的适配
   明确延期至 Slice 8；Slice 7 不引入异步请求或后台执行语义。

### 11.8 执行模型测试与架构守卫

本计划的测试与架构守卫必须额外证明：

1. concurrent create version 仅一个有效 Version/current-pointer/claim 结果成功；
2. concurrent review transition 仅一个 ReviewRecord 和一次状态推进成功；
3. review versus delete race 与 restore versus create-version race 都返回稳定结果且无部分事实；
4. transaction timeout/锁失败、commit 前异常和 final fact validation 异常均完整 rollback；
5. repeated client submission 仅由同 key replay 返回 winner，不重复写 Version、ReviewRecord 或 Audit；
6. cancelled invocation before commit 不留下 completed idempotency 或其他核心事实；
7. 新 Service 在事务内不执行 external I/O；
8. AST 守卫拒绝 `FastAPI BackgroundTasks`、Celery、RQ、queue producer、worker module、
   `httpx`、`requests`、`aiohttp`、AI service 和 external notification service import；
9. 移除 CAS 条件后的并发测试必须失败，作为 mutation-proof 等价负向证据。

这些测试使用现有真实 SQLite/SQLAlchemy fixture；若无法以当前测试基础设施可靠模拟 timeout 或
取消，则必须在实施前发起计划补正，而不是用 mock 或 skip 代替事务事实证明。

## 12. Error Model

Slice 7 只产生既有结构化领域异常和 stage，不定义 HTTP 映射：

| 场景 | Error code | Stage | 语义 |
|---|---|---|---|
| project_code 缺失或格式非法 | `EVIE_REQUEST_VALIDATION_ERROR` | `REQUEST_VALIDATION` | 复用 `ProjectScopeService`，在任何业务写入前 fail-closed。 |
| Project 不存在或非 active | `EVIE_PROJECT_NOT_FOUND`、`EVIE_PROJECT_INACTIVE` | `REQUEST_VALIDATION` | 复用 `ProjectScopeService`，不创建默认 Project。 |
| 非 active global admin | `EVIE_PROJECT_SCOPE_FORBIDDEN` | `AUTHORIZATION` | 复用 `ProjectAccessAuthorizer`；不执行后续业务写入。 |
| Asset 不存在或项目不匹配 | `EVIE_ASSET_NOT_FOUND` | `LIFECYCLE` / `REVIEW` | 不透露跨项目存在性。 |
| 删除资产尝试编辑/审核 | `EVIE_ASSET_DELETED` | `LIFECYCLE` / `REVIEW` | 不修改任何事实。 |
| `processing` 版本编辑、非法 delete/restore 状态 | `EVIE_ASSET_STATE_CONFLICT` | `LIFECYCLE` | 不创建 Version/Audit。 |
| row version 不匹配 | `EVIE_ROW_VERSION_CONFLICT` | `LIFECYCLE` / `REVIEW` | 不静默覆盖，不自动业务重试。 |
| Version 不存在、非同一 asset 或非 current review target | `EVIE_VERSION_NOT_FOUND`、`EVIE_VERSION_SCOPE_MISMATCH`、`EVIE_REVIEW_VERSION_NOT_CURRENT` | `LIFECYCLE` / `REVIEW` | 不创建 Record/Audit。 |
| 非法审核转换 | `EVIE_INVALID_REVIEW_TRANSITION` | `REVIEW` | 使用 Policy；重复新 key 不产生成功 Audit。 |
| 内容 claim 冲突 | `EVIE_EXACT_DUPLICATE_CONFLICT`、`EVIE_RESTORE_DUPLICATE_CONFLICT` | `LIFECYCLE` | 保留旧 Claim，不产生局部 Version 或恢复。 |
| 缺失 key 或指纹不匹配 | `EVIE_IDEMPOTENCY_KEY_REQUIRED`、`EVIE_IDEMPOTENCY_CONFLICT` | Lifecycle 命令使用 `LIFECYCLE`；review 命令使用 `REVIEW` | 不执行第二次业务副作用。 |
| 不可读 winner、损坏/跨项目结果、关系或 checksum 不一致 | `EVIE_DATA_INTEGRITY_ERROR` | `LIFECYCLE` / `REVIEW` / `PERSISTENCE` | 回滚并给出安全、无敏感数据的错误。 |

不得使用 `HTTPException`、自由文本、`TypeError` 或数据库原始异常替代领域错误；不得把
预期冲突转为 500 或将意外完整性错误伪装为成功。

## 13. Audit and Observability

### 13.1 事件矩阵

| 成功业务结果 | Audit event | 必填受控事实 | 禁止记录 |
|---|---|---|---|
| 新 Version | `version_created` | asset/version public ID、version no、checksum、changed field names、before/after statuses、actor/channel/request/correlation、idempotency snapshot。 | 自然语言正文、Requirement 正文、原始 key、内部 PK、SQL、token、异常/堆栈。 |
| 历史 Version 恢复 | `version_restored` | 新/源 version public ID、restore reason、公开状态摘要、追踪元数据。 | 历史或新正文全文。 |
| approve/reject/reopen | `review_changed` | current version public ID、from/to、action、受控 comment/reason 摘要、review record public ID、追踪元数据。 | 内部 reviewer PK、自由请求体、凭据。 |
| delete | `asset_deleted` | asset public ID、reason、claim release 事实、before/after deletion state、追踪元数据。 | 内容、原始 idempotency key。 |
| restore | `asset_restored` | asset public ID、reason、claim re-acquisition 事实、before/after deletion state、追踪元数据。 | 内容、SQL、Session/异常对象。 |
| 同 key 成功重放、no-op 内容、失败转换 | 无新事件 | 原成功结果或稳定错误。 | 不重复写 Audit。 |

`TestAssetAuditEvent.created_at` 是当前模型中的持久化发生时间字段。Slice 7 Service 必须在
构造 Audit Event 时用注入 UTC Clock 赋值，而不是在业务代码使用本地时钟或依赖不透明默认值。
所有 `before_state_summary` / `after_state_summary` 只允许固定、受控字段；不得把 `dict` 作为
未约束业务协议传递或写入任意请求内容。

### 13.2 日志

日志使用既有结构化日志工具，只记录 `trace_id`、`request_id`、`project_code`、asset/version
public ID、operation、status、duration 和 error code。不得记录自然语言测试步骤、预期结果、
审查全文、原始 idempotency key、Authorization、Cookie、Token 或数据库内部主键。

## 14. 批准实施文件范围

计划实现时只允许下列文件；若发现必须修改本表外文件，必须停止并请求计划补正。

### 14.1 Repository 变更

Repository 只增加第 4 节列出的受限持久化原语：锁定或条件读取、current version 推进、审核
状态 CAS、删除/恢复 CAS，以及恢复专用的 Claim acquire。所有方法必须验证聚合关系和
`project_code`，只执行 query/add/flush/受限条件 update，不包含领域编排、Clock、日志、
`commit` 或 `rollback`。不得把“读取已删除 Asset 的 current Version”暴露成一般查询能力。

### 14.2 Service 变更

两个新增 Service 各自只拥有其领域的公开命令和私有编排辅助步骤：

- Lifecycle：create version、restore historical version、delete、restore；
- Review：approve、reject、reopen。

它们使用明确类型化的既有输入、注入的 Session factory/Clock/retention 配置和已批准的
Repository/Policy/context 服务。它们不共享大而模糊的 util，不导入 Intake 私有函数，也不
承担 Router、Schema、HTTP、AI、Compiler 或 Runner 职责。

| 文件 | 变更类型 | 职责 |
|---|---|---|
| `apps/web-ui-service/app/services/evie_ai/test_asset_lifecycle_service.py` | 新增 | 唯一 Lifecycle 公开编排、事务、幂等、版本/删除/恢复事实校验。 |
| `apps/web-ui-service/app/services/evie_ai/test_asset_review_service.py` | 新增 | 唯一 Review 公开编排、Policy、CAS、Review Record、Audit。 |
| `apps/web-ui-service/app/repositories/evie_ai/test_asset_repository.py` | 修改 | 受限 current-version、版本推进、审核/删除/恢复条件更新和锁定读取。 |
| `apps/web-ui-service/app/repositories/evie_ai/content_claim_repository.py` | 修改 | 原子替换/释放及只用于恢复的受限 claim acquire。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_lifecycle_service.py` | 新增 | 真实 SQLite 生命周期、事务、幂等、Claim、删除/恢复测试。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_review_service.py` | 新增 | 真实 SQLite 审核状态机、Review Record、CAS、Audit 测试。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py` | 修改 | Asset/Version 条件更新、row version 和 deleted current 读取测试。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_coordination_repositories.py` | 修改 | 恢复 claim 的受限路径、唯一冲突和事务语义测试。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py` | 修改 | 生命周期/审核服务只依赖批准层、不得导入冻结旧链的 AST 守卫。 |

不计划修改：`AGENTS.md`、ADR、Baseline、Overview、Capability Map、Phase Traceability、
Slice 6 文件、Model、Schema、Migration、Router、前端、`id_gen.py`、常量、错误码、
Review Policy、Request Fingerprint、质量 baseline、Workflow 或 Ruleset。

## 15. 交付任务与评审门

| 任务 | 目标 | 允许生产文件 | 核心验收 |
|---|---|---|---|
| S7-T01 | 审计既有模型/Repository 并补齐受限 Asset 生命周期 CAS 基础。 | `test_asset_repository.py` | 无 direct ORM update；Version/current/review/conversion/deleted 的条件更新保留 Aggregate 一致性；Repository 无 commit/rollback。 |
| S7-T02 | 补齐 Content Claim 的恢复专用 acquire 操作。 | `content_claim_repository.py` | 仅 deleted aggregate/current fingerprint 可用；唯一约束冲突稳定；不形成通用 bypass。 |
| S7-T03 | 实现 Lifecycle Service 的共同可信上下文、幂等 scope 和提交前结果校验。 | `test_asset_lifecycle_service.py` | 无默认 project、无私有 Intake 复用、Clock 注入、同 key 无副作用重放。 |
| S7-T04 | 实现新版本与历史恢复。 | `test_asset_lifecycle_service.py` | 不可变 Version、no-op、状态映射、原子 claim replace、历史恢复创建新 Version、CAS。 |
| S7-T05 | 实现 Review Service。 | `test_asset_review_service.py` | 仅 current Version、合法 approve/reject/reopen、Review Record insert-only、审核和 conversion 分离。 |
| S7-T06 | 实现 delete/restore。 | `test_asset_lifecycle_service.py` | 删除释放 claim；恢复先拿 claim 后清 deleted；冲突/重放/失败全部 fail-closed。 |
| S7-T07 | 增加真实数据库、同步执行模型、事务、并发、架构与回归测试，并完成门禁和失败归因。 | 计划内测试文件 | 超时/取消/commit 前失败零残留；无后台核心事实；新增违规与新增回归均为 0。 |

每个任务完成后必须先进行局部审查和目标测试；不得将 S7-T01 至 T07 混成不可审查的大型提交。
任何新增模型、Schema、Migration、API、错误码或权限规则需求都是 stop condition，而不是本计划
可自行扩大范围的事项。

## 16. 测试矩阵与验收标准

| 类别 | 必测场景 | 持久化断言 | 计划测试节点 |
|---|---|---|---|
| 新版本 | 内容变化、no-op、`processing` 拒绝、deleted 拒绝、`succeeded/stale` 映射、`not_started/blocked` 映射。 | Version 不可变；current 同 asset；row +1；no-op 无 Version/Audit/row bump。 | `test_evie_ai_lifecycle_service.py` |
| 历史恢复 | 同 asset 历史 Version、缺失 Version、跨 asset Version、必填 reason、重复内容。 | 创建全新 Version，不改历史 pointer；原子 claim 规则正确。 | `test_evie_ai_lifecycle_service.py` |
| 审核 | approve、reject、approved/rejected reopen、缺 reason、非法转换、非 current Version、deleted Asset。 | Review Record insert-only；Audit 一条；审核不改 conversion/content。 | `test_evie_ai_review_service.py` |
| 删除与恢复 | 删除释放 Claim、恢复成功、恢复 fingerprint 冲突、重复 delete/restore、新 key 与相同 key。 | `deleted_at`/row 变化正确；不创建 Version；失败零残留。 | `test_evie_ai_lifecycle_service.py` |
| scope/identity | inactive Project、non-admin、跨项目 Asset/Version/Review/Claim、缺失/非法 principal。 | 业务表无写入；不泄露跨项目事实。 | 两个 Service 测试，复用 Slice 5 fixtures。 |
| 幂等 | 每种写操作的同 key 同指纹 replay、同 key 异指纹 conflict、过期 generation CAS、winner 不可读。 | replay 不新增 Version/Review/Audit/Claim/Source；损坏 winner fail-closed。 | Lifecycle/Review Service 测试。 |
| 并发/事务 | 并发同 row、并发 Version、Claim replace/reacquire、Review CAS。 | 失败后 Asset、Version、Source、Claim、Review、Audit、Idempotency 无局部残留。 | 真实 SQLite/SQLAlchemy 测试及 Repository 测试。 |
| 执行模型 | create-version/review/delete/restore race、数据库 timeout/锁失败、commit 前取消或异常、final fact validation 异常、同 key 重复提交。 | 全部核心事实同步 commit 或 rollback；无 completed winner 或成功 Audit 残留；重放不重复写入。 | `test_evie_ai_lifecycle_service.py`、`test_evie_ai_review_service.py`。 |
| Audit 安全 | 所有事件类型和 replay/no-op。 | 不含正文、原始 key、内部 PK、SQL、token、凭据、Session、异常或堆栈。 | 两个 Service 测试。 |
| 架构边界 | 新 Service 的 imports、自然语言字段、禁止旧链、后台和外部 I/O 依赖。 | AST 不出现 Candidate/Preview/Compiler/Runner/TestCase/Router、BackgroundTasks/Celery/RQ/queue/worker/HTTP client/AI/notification 依赖。 | `test_evie_ai_architecture_boundaries.py` |
| Repository | 受限 CAS、deleted current read、claim restore operation。 | Runtime 返回类型一致；Repository 无 commit/rollback。 | `test_evie_ai_repositories.py`、`test_evie_ai_coordination_repositories.py` |

除 mock 调用验证外，上表所有 aggregate 一致性、重放、冲突和回滚场景必须使用现有真实
SQLite/SQLAlchemy fixture。测试不得通过宽泛 `pytest.raises(Exception)`、skip、降低断言或
修改无关 fixture 制造假阳性。

### 16.1 执行命令

使用已激活且现有的项目虚拟环境执行以下命令；不得为 Slice 7 安装或升级依赖：

```bash
# Slice 7 服务与 Repository 针对性测试
python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_lifecycle_service.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_review_service.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_coordination_repositories.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py

# Slice 1-6 直接兼容回归和完整 EvieAi 回归
python -m pytest -q apps/web-ui-service/tests/unit/evie_ai
python -m pytest -q apps/web-ui-service/tests/unit/evie_ai apps/web-ui-service/tests/integration/evie_ai

# 质量、类型、格式和语法
make evie-ai-quality-gate
scripts/qa/run-evie-ai-quality-gate.sh --staged
python -m pytest -q tests/unit/test_evie_ai_code_quality_gate.py
ruff check apps/web-ui-service/app/services/evie_ai \
  apps/web-ui-service/app/repositories/evie_ai \
  apps/web-ui-service/tests/unit/evie_ai
ruff format --check apps/web-ui-service/app/services/evie_ai \
  apps/web-ui-service/app/repositories/evie_ai \
  apps/web-ui-service/tests/unit/evie_ai
python -m compileall -q apps/web-ui-service/app/services/evie_ai \
  apps/web-ui-service/app/repositories/evie_ai
git diff --check

# 完整 web-ui 单元回归，以及与干净 origin/dev 的同命令对比
python -m pytest -q apps/web-ui-service/tests/unit
```

Mypy 使用 Quality Gate 对受影响 EvieAi 闭包的统一事实源执行；不得以孤立单文件检查替代。
若直接运行 Mypy 用于诊断，必须使用门禁解析的同一受影响模块范围。提交前记录 collected、passed、
failed、errors、skipped、warnings、失败 node ID、首个异常和归一化签名。

完整 web-ui 基线失败必须逐项与干净 `origin/dev` 对比，不得概括为单一 CI 问题。当前已知历史
集合包括 CI-B01 的 8 个 `test_workbench_facade.py` 失败，以及 24 个其他既有失败：
`test_case_id_flow.py` 1 个、`test_step_field_consistency.py` 1 个、
`test_test_point_asset_candidate_sync.py` 1 个、`test_workbench_generation_service.py` 21 个。
CI-B02 是独立的 `apps/ai-orchestrator/src/app.py` 缺失 collection failure。Slice 7 必须证明
新增失败为 0，而非修改或掩盖这些基线问题。

### 16.2 负向证明

新增测试必须证明关键保护确实生效，而不只是测试成功路径：

- 移除或破坏 Version 与 Asset 的同聚合校验时，跨 Asset 历史恢复和非 current 审核测试必须失败；
- 移除 `expected_row_version` 条件时，陈旧 row version 和并发 mutation 测试必须失败；
- 移除恢复前的 Claim acquire 或其唯一冲突处理时，恢复冲突和零残留测试必须失败；
- 移除 idempotency 指纹比较或 replay 返回前校验时，同 key 异内容/损坏 winner 测试必须失败；
- 移除 Audit 敏感字段过滤时，禁止字段矩阵测试必须失败；
- 删除 AST 禁止导入规则时，故意的 Candidate/Compiler/Runner import 样例必须被守卫检出。

这构成 mutation test 的等价负向证明；不要求在本 Slice 引入新的 mutation-testing 第三方依赖。

## 17. 质量门禁与架构守卫

Slice 7 的 merge gate 是 required check `evie-ai-code-quality`。实现分支必须满足：

1. `git diff --check` 通过；
2. changed-files Ruff、Ruff format、受影响模块 Mypy、EQA001--EQA010、分层/依赖 AST 和
   zero-new 比较全部通过；
3. baseline 维持已接受的 50 项，或仅在单独、明确批准的治理工作中按安全收缩规则更新；
   Slice 7 不得新增、替换、重分类或删除 baseline 豁免；
4. 新增/修改 Service 不直接调用 `datetime.now()` / `utcnow()`、不使用核心 `Any`、不使用
   magic status/error string，不扩大函数长度、复杂度、参数数量或嵌套违规；
5. 新架构守卫证明 Lifecycle/Review Service 不导入 Candidate、Preview、TestPointPlan、
   structurer、execution compiler、ContractValidator、Runner、TestCase、Router、BackgroundTasks、
   Celery、RQ、queue producer、worker module、HTTP client、AI service 或 notification service；
6. 工具缺失、解析异常、空/畸形输出、Git 快照异常或 baseline 比较异常都必须 fail-closed；
7. PR 只在 `evie-ai-code-quality` 成功且无新增质量违规后可评审；CI-B01、CI-B02 仅可作为
   已归因历史失败记录，不能被修复、忽略或设为 required。

## 18. 交付、回滚与 Closeout 门

### 18.1 Review Gates

| Gate | 进入条件 | 必须核验 | 不满足时的处理 |
|---|---|---|---|
| Plan review | 本文件 PR 已完成合同、符号、状态和文件范围审计。 | 所有第 1.1 节主题可定位；无未定义 error/stage/event/policy；Scope 不含 Slice 8。 | 修正计划；不得创建实施分支。 |
| Pre-implementation review | 用户明确批准计划；从最新干净 `dev` 创建独立实施分支。 | 基线、允许文件、禁止文件、配置、唯一事实源、事务和测试计划。 | 合同/范围不一致时停止并请求补正。 |
| Increment review | 每个 S7-T0x 的最小实现单元完成。 | 对应真实 SQLite 测试、Repository 无 commit/rollback、无直接 ORM 更新、架构守卫。 | 不合并后续任务；先修复当前单元。 |
| PR review | 所有 S7-T0x 和完整测试矩阵完成。 | required quality check、zero new violations、完整 web-ui 与干净基线失败签名对比。 | 新回归、质量失败或范围异常时阻塞合并。 |
| Closeout review | 实现 PR 已合并且独立只读审计完成。 | 第 18.4 节验收证据、PR/commit/测试/回归归因和用户批准。 | Slice 7 Closeout 保持 `Not completed`。 |

### 18.2 交付节奏

1. 用户批准本计划后，从最新干净 `dev` 创建独立 Slice 7 实施分支。
2. 每个 S7-T0x 以最小可审查单元实现和验证；生产与对应测试保持同一逻辑提交。
3. 完成针对性、EvieAi、质量和全量回归归因后，创建实现 PR；不得在 PR 中混入 Slice 8。
4. 实现合并后执行独立只读审查；所有验收项有真实证据后，才可提出 Slice 7 Closeout 文档。
5. 用户明确批准 Closeout 前，Slice 7 Closeout 保持 `Not completed`。

### 18.3 回滚策略

- 本 Slice 不含 Migration；因此不得以修改历史版本、直接数据库更新或删除审计记录作为回滚手段。
- 在未合并 PR 阶段，回滚采用丢弃/反转该独立分支的未合并实现，由 Git 历史处理。
- 合并后如需回退代码，使用独立、审查过的 revert；已提交的 Version、Review、Audit、
  Idempotency 和 Claim 事实不得被普通业务操作原地篡改。
- 业务数据纠正只能通过后续已批准的生命周期操作或受审计的专项迁移/运维程序进行；后者不属于
  Slice 7 自动授权范围。

### 18.4 Slice 7 验收标准

Slice 7 只有同时满足以下条件，才可进入 Closeout 审计：

- 两个唯一 Service 已实现，且不存在平行 Lifecycle/Review 写入口；
- 第 8--13 节所有状态、不可变、事务、并发、权限、幂等、同步执行、错误和审计合同均有真实持久化证据；
- 新版本、历史恢复、审核、删除、恢复、replay、冲突和失败回滚矩阵通过；
- 无 Router/API、前端、ORM、Migration、Candidate、Preview、Compiler、Runner、TestCase 或
  Slice 8 变更；
- Quality Gate、架构守卫、必要回归和完整 web-ui 基线比较通过，新增质量违规与新增回归均为 0；
- PR、commit、测试输出、失败归因与 Closeout 证据被记录；
- 用户明确批准 Slice 7 Closeout。

上述条件不宣告 Phase 1 完成；完整 Phase 1 Closeout 仍受 Slice 8、Slice 9 及后续合同和
用户决策约束。

## 19. 风险、Open Questions 与 Deferred Decisions

### 19.1 Risks

| ID | 风险或待决策 | 处理方式 | 是否阻塞本计划 |
|---|---|---|---|
| S7-R01 | 已批准的产品原型最终基线当前不在 `origin/dev` 的权威文档中。 | Slice 7 不从外部原型创造领域规则；在 Slice 8/11 前，单独建立产品决策、Figma Frame 与实现追踪文档。后端规则只来自 Phase 1 Specification 和仓库权威合同。 | 不阻塞本技术计划；若实施需依赖其新增业务规则则阻塞实现。 |
| S7-R02 | 已有 Content Claim `add` 只接受 active Asset，而 restore 需要先重新获取 Claim。 | 仅增加第 4 节规定的受限恢复操作，并用跨项目/非 deleted/非 current/冲突测试限制。 | 不阻塞；是 S7-T02 的核心验收。 |
| S7-R03 | 审核与转换状态容易被实现为同一字段或同一命令副作用。 | 通过独立 Service、Policy、CAS 和测试确保 Review 不改 conversion，Version 才按矩阵映射。 | 不阻塞；违反时阻塞 Closeout。 |
| S7-R04 | SQLite 并发测试可能无法替代未来完整多数据库压力验证。 | Slice 7 使用真实 SQLite 事务和确定性 CAS/唯一约束测试；不声称替代后续集成/数据库验证。 | 不阻塞本 Slice；结果如不稳定则阻塞其验证。 |
| S7-R05 | Slice 8 API 参数、HTTP 映射和前端交互尚未开始。 | 明确保留给 Slice 8；Service 仅返回类型化领域结果/错误，不预设 HTTP 行为。 | 不阻塞 Slice 7。 |

### 19.2 Open Questions

1. 产品原型最终基线的权威文件路径或可审查副本是什么；它是否引入任何不在 D-04、D-06、
   D-07、D-08、D-10 中的后端行为？在获得该证据前，Slice 7 仅实施本文件已有合同，且
   Slice 8/11 不得省略产品决策、Figma Frame 和实现追踪的独立治理记录。
2. Slice 8 未来如何将服务结果绑定到既有 HTTP 错误 envelope 与公开响应 Schema，不由 Slice 7
   预先决定。
3. 后续多数据库/多节点并发验收的环境、负载和成功阈值由哪份 Phase 1 后续合同定义，不由
   SQLite 单元集成测试推断。

这些问题均不得改变本计划已明确的状态、事务、权限或错误边界；若答案要求改变它们，必须先
进行计划补正和用户批准。

### 19.3 Deferred Decisions

以下决定明确延期，不由 Slice 7 计划或实现自行决定：

1. Slice 8 的 HTTP 路径、请求/响应 Schema 绑定、HTTP status 和 API 兼容策略；
2. 前端资产中心的编辑、审核、删除和恢复交互，以及产品原型如何映射为界面行为；
3. Slice 10 Requirement Lifecycle 的版本、审核、删除和恢复规则；
4. Slice 11 及完整 Phase 1 的治理、收口条件和最终用户 Closeout；
5. PostgreSQL 压力/多节点并发验收、生命周期事件对外投递及保留策略；
6. Asset-to-Case、资源绑定、Compiler、TestCase、Runner 和执行报告的后续合同。

以下任一情况发生时必须停止实现并发起计划补正：需要 ORM/Schema/Migration、需要新增错误码或
状态、需要改变 Slice 5/6 合同、需要 HTTP/Router/前端、需要默认项目或身份回退、需要引入新
依赖、需要修改 quality baseline、或发现产品决策与本计划已接受合同冲突。

## 20. Final Planning Decision

技术合同、当前模型、既有 Repository、Slice 5/6 基础和质量门禁均足以形成可审批的 Slice 7
实施计划。产品原型最终基线文件在干净仓库中不可定位已被记录为 S7-R01，但不影响本计划中
完全由已接受 Phase 1 合同确定的后端生命周期和审核边界。

**Planning conclusion: Ready for Slice 7 implementation.**
