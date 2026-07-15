# EvieAi Phase 1 自然语言测试资产生命周期规格合同

日期：2026-07-15
状态：Approved
适用范围：Phase 1 Asset Lifecycle Core
决策记录：`docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`

## 1. 合同目的

本合同把 2026-07-15 用户明确批准的 D-01～D-14 固化为 Phase 1
权威实施边界。其中：

- D-12 规定前端作为独立切片，不阻塞 Asset Lifecycle Core 后端验收；
- D-13 规定 Migration 与确定性数据库 baseline；
- D-14 规定 Requirement Lifecycle 独立拆分。

实现不得用当前旧代码惯例替代本合同，也不得从本文推导后续阶段对象。

2026-07-15 两轮合同评审识别的 A-01～A-10 已获得用户明确签字，并纳入本合同。合同门禁
已经解除，但必须先完成文档提交、审查和合并，再从最新 `dev` 创建 Slice 1 功能分支；
不得在当前文档分支直接实施代码。

2026-07-15 可实施性评审进一步明确了读取权限、新建 Content Claim 顺序、
`conversion_status` 合法集、非版本领域事实和历史版本恢复 API。这些修订只完整表达
已签字规则，不新增架构决策。

Phase 1 Asset Lifecycle Core 负责：

- Manual/API 自然语言资产入口；
- 统一 Intake；
- 多来源、幂等和精确重复；
- 编辑、新版本和历史恢复；
- 审核历史；
- 软删除和恢复；
- 查询和操作审计。

本合同不包含：AI 生成、Candidate、Preview、语义重复、完整异步质量评估、
Asset-to-Case、ConversionAttempt、Compiler、Runner、TestCase 或完整前端资产中心。

## 2. 领域事实源

| 事实 | 权威存储 |
|---|---|
| 资产稳定身份和当前状态 | `TestAsset` |
| 当前自然语言内容 | `TestAsset.current_version` 指向的 `TestAssetVersion` |
| 历史自然语言内容 | 不可变 `TestAssetVersion` |
| 来源关系 | `TestAssetSource` 及类型化来源子表 |
| 当前审核状态 | `TestAsset.review_status` |
| 审核历史 | 不可变 `TestAssetReviewRecord` |
| 当前删除状态 | `TestAsset.deleted_at` |
| 生命周期操作历史 | 不可变 `TestAssetAuditEvent` |
| 幂等重放结果 | `TestAssetIdempotencyRecord` |
| 有效资产内容占用 | `TestAssetContentClaim` |

任何缓存、摘要、审计事件或幂等记录都不得覆盖自然语言内容事实源。

## 3. 统一入口和事务合同（D-01、D-03）

### 3.1 Service 边界

- `TestAssetIntakeService`：创建或复用资产、首版本、来源、幂等、精确重复和创建审计。
- `TestAssetLifecycleService`：创建新版本、历史恢复、删除和恢复。
- `TestAssetReviewService`：审核状态机和不可变审核记录。
- 查询 Service/Repository：列表、详情、版本和审核历史，只读。

所有 API、前端 Adapter、未来导入器和 AI Producer 必须调用同一合同。不得平行实现
另一条资产保存主链。

### 3.2 事务控制

Phase 1 不引入全平台通用 Unit of Work 框架。Application Service 或轻量 transaction
runner 使用：

```python
with session.begin():
    service_orchestration()
```

Repository 只 add、flush、query；不得 commit 或 rollback。Router 不直接操作 ORM。
数据库异常必须使整个事务回滚，失败 Session 不得继续使用。

### 3.3 创建事务流程

```text
认证与 project scope
→ 请求规范化
→ 计算 request fingerprint
→ 获取幂等 claim
→ 计算 content fingerprint
→ 查询 content claim
→ 根据结果进入新建路径或复用路径
```

新建路径：

```text
创建 TestAsset
→ 创建 TestAssetVersion(version_no=1)
→ 创建 TestAssetSource
→ 设置 current_version_pk
→ 创建 asset_created AuditEvent
→ 保存幂等结果
→ commit
```

精确重复复用路径：

```text
读取已有有效 TestAsset
→ 必要时新增尚不存在的真实来源
→ 创建 exact_duplicate_reused AuditEvent
→ 保存幂等结果
→ commit
```

精确重复复用路径不得创建新的 TestAsset 或 TestAssetVersion。上述任一步失败时，幂等、
content claim、领域记录、来源和审计必须全部回滚。

新建默认值：

```text
version_no = 1
row_version = 1
review_status = pending
conversion_status = not_started
deleted_at = null
```

创建时不生成虚假审核记录。

### 3.3.1 新建路径的 Content Claim 顺序

创建请求先按 content fingerprint 查询已有 claim。已有 claim 时进入精确重复
复用路径。

未查询到 claim 时，新建路径必须在一个业务事务中按以下顺序执行：

1. 创建 `TestAsset` 并 flush，取得内部 PK；
2. 创建首个 `TestAssetVersion` 和 `TestAssetSource`；
3. 插入指向新 `TestAsset` 的 `TestAssetContentClaim`；
4. 设置 `current_version_pk`；
5. 写入审计和幂等结果；
6. commit。

若插入 Content Claim 时因并发请求触发
`UNIQUE(project_code, content_fingerprint)` 冲突：

- 当前新建事务必须整体回滚；
- 不保留 TestAsset、Version、Source、Content Claim、AuditEvent 或幂等结果；
- 不得在失败 Session 或失败事务中继续查询或写入；
- 应用层必须开启新的干净事务，重新校验 project scope、请求规范化和
  request fingerprint，并从幂等检查开始重新执行完整 Intake 流程；
- 新事务必须重新校验相同 scope/key 的幂等状态；
- 若另一个同幂等请求已经完成，直接返回其原结果；
- 否则重新读取已存在的 Content Claim，并进入精确重复复用路径。

并发回退不得绕过 project scope、幂等 claim 或 request fingerprint 校验。

### 3.4 A-01：Asset code 合同

已确认边界：

- `test_asset_id` 是全局稳定公共身份；
- `asset_code` 是项目内稳定业务编号，新资产取值等于 `test_asset_id`；
- `asset_code` 由服务端生成，客户端不得在创建请求中提供；
- 创建后不可修改，软删除和恢复不重新分配；
- 必须满足 `UNIQUE(project_code, asset_code)`；
- 不得使用无锁的 `SELECT MAX(...) + 1`。
- 存量资产的 `asset_code` 不重写。

### 3.5 A-02：Project scope 与调用身份合同

所有写操作必须通过只读 `ProjectScopeService`：

1. project_code 显式提供；
2. 项目已经存在；
3. 项目状态为 active；
4. 当前 principal 的全局角色为 admin；
5. 不创建默认项目；
6. 不 commit 或修改项目数据。

`actor_or_client_id` 只能由认证 principal 规范化。首版用户使用
`user:<stable-user-id>`；不得使用 display name、临时 token 或请求正文中的 actor。

channel 由受信任的服务器 Adapter 固定设置为 `api`，不得从业务请求正文读取。

项目存在/状态事实源为现有 `TestProject`，角色事实源为认证上下文中的 `User.role`。
非 admin、项目不存在或项目非 active 均 fail-closed。禁止自动创建默认项目。

### 3.5.1 读取权限

Phase 1 Asset Lifecycle Core 的全部公开 API，包括查询和写入，暂时只允许全局
admin 访问已经存在且状态为 active 的 project。

非 admin 访问列表、详情、版本历史、审核历史或写接口时，统一返回
`403 EVIE_PROJECT_SCOPE_FORBIDDEN`。在项目成员和项目级权限事实源建立前，不得
自行开放普通用户只读访问。

## 4. 多来源合同（D-02）

### 4.1 主表

`test_asset_sources`：

- `id`：内部 Integer PK；
- `test_asset_source_id`：现有 `tas_<uuid4hex32>` 公共 ID；
- `test_asset_pk`：资产聚合 FK；
- `source_type`：`requirement` 或 `manual`；
- `source_identity_hash`：来源稳定身份；
- `created_at`、`created_by`。

唯一约束固定为：

```text
UNIQUE(test_asset_pk, source_identity_hash)
```

`source_identity_hash` 的 canonical 输入已包含 `source_type`，因此唯一键不重复加入
`source_type`。

### 4.2 Requirement 子表

`test_asset_requirement_sources`：

- 内部 Integer PK；
- `test_asset_source_pk`：唯一 FK 到通用来源主表；
- `requirement_pk`；
- `requirement_version_pk`。

`requirement` 来源必须存在子表记录，且 RequirementVersion 必须属于对应 Requirement。
`manual` 来源只需要主表记录。

### 4.3 来源生命周期

- Source 绑定 TestAsset 聚合，不绑定内容版本。
- 编辑新版本不得复制、覆盖或删除已有来源。
- 只有新的真实来源出现时才新增来源记录。
- API、前端、CI 属于 channel，写入请求上下文和审计，不是 `source_type`。

### 4.4 A-07：来源身份合同

`source_identity_hash` 由服务端按 canonical JSON 的 UTF-8 字节计算 SHA-256，客户端不得
直接提交 hash。canonical JSON 必须使用稳定字段集合、键名排序、无非必要空白和 UTF-8
编码；同一逻辑输入必须跨进程和数据库得到相同字节序列。

Requirement 来源身份字段：

```text
source_type=requirement
requirement_id
requirement_version_id
```

Manual 来源身份字段：

```text
source_type=manual
project_code
actor_or_client_id
operation_type
idempotency_key
request_fingerprint
```

不得把自然语言内容 checksum 作为 Manual 来源身份。相同幂等请求重放不重复新增来源；
不同幂等请求提交相同内容可以形成新的 Manual 来源事实；channel 不参与 source type 判定。

Requirement、RequirementVersion、TestAsset 和请求 project scope 必须属于同一项目；
跨项目来源绑定返回 `EVIE_SOURCE_SCOPE_MISMATCH`。

### 4.5 A-04：来源子类型一致性合同

Phase 1 不引入数据库 trigger。数据库负责：

- Requirement 子表的 `test_asset_source_pk` 唯一 FK；
- Requirement 和 RequirementVersion FK；
- 同一来源最多一个 Requirement 子记录。

Application Service 和 Repository 负责：

- requirement source 创建时同事务插入子记录；
- manual source 不得插入 Requirement 子记录；
- 读取聚合发现类型与子记录不一致时 fail-closed；
- 来源主表和子表同事务完成。

Migration 必须验证：每个 requirement source 恰有一个子记录；不存在 manual source 子记录；
RequirementVersion 属于 Requirement。跨表完整性不得被描述为普通 CHECK Constraint。

## 5. 幂等合同（D-04）

新增 `test_asset_idempotency_records`。所有公开写接口必须使用：

```http
Idempotency-Key: <client-generated-key>
```

唯一作用域：

```text
project_code + operation_type + actor_or_client_id + idempotency_key
```

覆盖操作：create asset、create version、restore historical version、review、delete、
restore asset。

规则：

- 同 scope/key/request fingerprint：返回原业务结果，不重复写入或审计。
- 同 scope/key、不同 request fingerprint：409 `EVIE_IDEMPOTENCY_CONFLICT`。
- 失败事务不保留 completed 结果，允许相同 key 重试。
- 保存请求指纹、operation type、结果资源公共 ID/类型、原结果语义、创建和过期时间。
- 不保存完整自然语言请求/响应正文或机器执行内容。
- 默认保留期 7 天，必须由单一 Settings/Policy 配置定义。
- 幂等记录过期后，同一 key 可作为新请求重新使用。过期清理和重新占用必须使用
  数据库唯一性与事务保护，不得产生并发窗口。

配置合同：

| 配置 | 类型 | 默认值 | 必填 | 权威位置 | 范围 | 安全级别 |
|---|---|---:|---|---|---|---|
| `EVIE_AI_IDEMPOTENCY_RETENTION_DAYS` | 正整数 | 7 | 否 | `app/core/config.py` Settings | Web Service 进程 | 非敏感 |

实现测试必须覆盖默认值、合法覆盖值、零值/负数/非整数拒绝；业务代码不得直接散落读取
环境变量。

## 6. 精确重复合同（D-05）

新增 `test_asset_content_claims`，至少包含：

- 内部 Integer PK；
- `test_asset_pk`：非空 FK；
- `project_code`；
- `content_fingerprint`；
- `created_at`。

已批准的唯一约束：

```text
UNIQUE(project_code, content_fingerprint)
```

A-06 已批准的补充唯一约束：

```text
UNIQUE(test_asset_pk)
```

其目标语义是：一个有效 TestAsset 在事务完成后只能拥有当前版本对应的一个 content
claim。

只有同项目下有效（未软删除）资产占用 claim。

### 6.1 指纹

参与字段：title、precondition、natural_steps、expected_result、priority、tags。

不参与：来源、created_by、channel、审核/转换状态、公共 ID 和时间字段。

规范化：Unicode NFC；CRLF/CR 转 LF；去字段首尾空白；去每行末尾空白；保留正文
内部有意义的空格和换行；tags 去空、去重、稳定排序。

规范化后的六个字段必须由服务端组装为 canonical JSON：使用固定键名、键排序、UTF-8
编码且无非必要空白，再对最终字节流计算 SHA-256。不得使用未定义分隔符的字符串
拼接，也不得进行语义改写。

### 6.2 创建命中

- 不创建新的 TestAsset/TestAssetVersion。
- 返回已有资产；来源不同且确为新来源时追加来源。
- 写 `exact_duplicate_reused` 审计事件。
- 返回 200，`created=false`、`reused_existing=true`。

### 6.3 编辑、删除和恢复

- 编辑命中另一有效资产：409 `EVIE_EXACT_DUPLICATE_CONFLICT`。
- 删除释放当前内容 claim。
- 恢复重新申请 claim；被占用时 409 `EVIE_RESTORE_DUPLICATE_CONFLICT`。
- 已删除资产不参与创建复用，也不得被静默恢复或合并。

### 6.4 A-03：编辑时 Content Claim 原子替换合同

创建新版本且 fingerprint 发生变化时，Service 必须锁定 TestAsset 及其唯一现有 claim，
校验目标指纹未被其他有效资产占用，并原子更新现有 claim，使其对应新 current version
的内容。不得通过让同一资产临时持有两条 claim 实现替换。

新版本、current_version_pk、row_version、claim、审计和幂等结果必须在同一事务提交。
目标指纹冲突时不创建版本，原 claim 保持有效；任一步骤失败时整体回滚。编辑为自身当前
fingerprint 仍按空修改处理。

## 7. 版本生命周期合同（D-06）

- 正文或版本化治理字段变化必须创建新 TestAssetVersion。
- `version_no` 在聚合内单调递增；历史版本不可修改。
- 规范化输入与当前版本一致时返回当前版本，`changed=false`，不创建伪版本。
- 历史恢复复制旧版本内容创建新版本，不允许把 `current_version_pk` 指回历史记录。
- 普通编辑 reason 可选；历史恢复 reason 必填。
- 所有变更请求携带 `expected_row_version`。
- Service 使用聚合行锁或等价保护、row_version CAS 和
  `UNIQUE(test_asset_pk, version_no)`；冲突返回 `EVIE_ROW_VERSION_CONFLICT`，
  不自动吞掉并生成其他版本号。

状态规则沿用已批准 Phase 0 合同：

- 合法 `conversion_status` 仅包含 `not_started`、`processing`、`blocked`、
  `succeeded`、`stale`，不包含 `failed`；
- 新版本后 `review_status=pending`；
- succeeded/stale → stale；not_started/blocked → not_started；
- processing 禁止编辑；
- rejected 可编辑并进入新 pending 版本；
- 已删除资产禁止编辑；
- 编辑默认不增加来源。

### 7.1 A-10：版本字段边界合同

以下字段属于 `TestAssetVersion` 内容，规范化后任一变化必须创建新版本：

- `title`；
- `precondition`；
- `natural_steps`；
- `expected_result`；
- `priority`；
- `tags`。

以下字段不属于内容版本：

- `test_asset_id`；
- `asset_code`；
- `current_version_pk`；
- `review_status`；
- `conversion_status`；
- `deleted_at`；
- `row_version`；
- `TestAssetSource`；
- `TestAssetReviewRecord`；
- `TestAssetAuditEvent`；
- `TestAssetIdempotencyRecord`；
- `TestAssetContentClaim`。

这些字段或领域事实发生变化时，不得修改历史 `TestAssetVersion`，也不得通过
创建内容版本代替对应的来源、审核、审计、幂等或 claim 领域操作。

## 8. 审核合同（D-07）

新增不可变 `test_asset_review_records`，公共 ID 为 `tar_<uuid4hex32>`。

每条记录同时绑定资产与被审核的当前版本，并至少保存：from/to status、reviewer、
reviewed_at、comment、reason、request/correlation ID 和幂等关联。

状态：pending、approved、rejected。

允许转换：

```text
pending → approved
pending → rejected
approved → pending（显式 reopen，reason 必填）
rejected → pending（显式 reopen，reason 必填）
```

记录只插入，不更新或删除。审核只能针对当前版本；历史版本记录保留但不能改变当前
聚合状态。创建资产不写虚假审核记录；新版本重置 pending，旧审核历史保留。

### 8.1 A-08：审核并发与重复操作合同

`reopen` 是审核操作，不是审核状态。审核状态仍只有 pending、approved、rejected。

审核请求必须提供 `expected_row_version`，并在一个事务中：

1. 校验资产未删除；
2. 校验目标版本等于当前 `current_version_pk`；
3. 校验 `expected_row_version`；
4. 校验合法状态转换；
5. 插入不可变 ReviewRecord；
6. 更新 `TestAsset.review_status`；
7. 增加 `TestAsset.row_version`；
8. 插入 AuditEvent；
9. 保存幂等结果。

相同 Idempotency-Key 重放返回原审核结果，不新增记录。不同 Idempotency-Key 重复提交
已完成的相同状态转换，返回 409 `EVIE_INVALID_REVIEW_TRANSITION`，不得新增
ReviewRecord 或 AuditEvent。

## 9. 删除恢复合同（D-08）

`TestAsset.deleted_at` 是当前删除状态的唯一事实源，不新增 deleted/restored actor、time、
reason 等重复字段；详细事实写审计事件。

删除和恢复都必须提供 `expected_row_version`、reason 和 Idempotency-Key。

删除：设置 deleted_at、增加 row_version、保留 current version/Source/Review/Audit、释放
claim，并禁止编辑和审核。公共 ID 和 asset_code 永久保留。

恢复：先申请当前内容 claim，成功后清空 deleted_at 并增加 row_version，不创建内容版本。

同 key 重放返回原结果。不同 key 重复删除或重复恢复返回 409 状态冲突，不新增审计事件。

## 10. 查询合同（D-09）

分页：`page=1`、`page_size=20`、`max_page_size=100`，返回 total。

默认排序：`created_at DESC, test_asset_id DESC`。

首版过滤：授权 project_code、review_status、conversion_status、priority、tags、
requirement_id、source_type、created_by、created_at 范围、keyword、受权限控制的
include_deleted。

A-09 keyword 合同：Phase 1 Core 仅对当前版本 title 执行可移植、不区分大小写的
子串匹配；不引入 PostgreSQL 全文索引、SQLite FTS、语义搜索或自然语言正文全文检索。

列表返回公共字段、当前版本摘要、priority/tags、状态、来源类型摘要、created/updated、
row_version 和 deleted 状态；不返回全部历史或内部 PK。

详情返回聚合状态、当前完整自然语言、来源列表、最新审核摘要和 row_version。
版本历史与审核历史使用独立分页接口。普通详情对已删除资产返回 404；授权调用方可显式
include_deleted。

## 11. 审计合同（D-10）

新增不可变 `test_asset_audit_events`，公共 ID 为 `tae_<uuid4hex32>`。

事件至少包括：asset_created、exact_duplicate_reused、source_added、version_created、
version_restored、review_changed、asset_deleted、asset_restored。

保存 asset、event type、actor、channel、request/correlation、幂等关联、相关版本/来源/
审核公共 ID、reason、before/after 状态摘要和 created_at。

不得保存完整 title、precondition、natural_steps、expected_result 或需求正文；只允许公共
ID、checksum、状态、版本号、变化字段名和必要脱敏摘要。审计不能替代 Version 或 Review。

## 12. API 合同（D-11）

```http
POST   /api/evie-ai/test-assets
GET    /api/evie-ai/test-assets
GET    /api/evie-ai/test-assets/{test_asset_id}
POST   /api/evie-ai/test-assets/{test_asset_id}/versions
GET    /api/evie-ai/test-assets/{test_asset_id}/versions
POST   /api/evie-ai/test-assets/{test_asset_id}/versions/{test_asset_version_id}/restore
POST   /api/evie-ai/test-assets/{test_asset_id}/reviews
GET    /api/evie-ai/test-assets/{test_asset_id}/reviews
DELETE /api/evie-ai/test-assets/{test_asset_id}
POST   /api/evie-ai/test-assets/{test_asset_id}/restore
```

不提供 `PATCH /review-status`。首次创建 TestAsset 不需要 `expected_row_version`；创建新版本、
审核、删除和恢复必须在请求 Schema 中提供 `expected_row_version`。Phase 1 不以 `If-Match`
作为唯一并发协议。

历史版本恢复使用独立端点：

```http
POST /api/evie-ai/test-assets/{test_asset_id}/versions/{test_asset_version_id}/restore
Idempotency-Key: <client-generated-key>
```

请求体：

```json
{
  "expected_row_version": 3,
  "reason": "Restore previously approved content"
}
```

成功返回 `201 Created` 和新创建的版本，不得直接返回或重指向历史版本。
`test_asset_version_id` 必须是后端分配的 `tav_<uuid4hex32>` 公共 ID，不得接收或暴露
内部 Integer PK。

来源是 `manual`/`requirement` discriminated union。Requirement 来源请求使用公共
`requirement_id` 和 `requirement_version_id`，后端验证项目作用域和父子归属。

创建新资产返回 201/created=true；精确重复复用返回 200/reused_existing=true。

错误结构：

```json
{
  "error": {
    "code": "EVIE_ROW_VERSION_CONFLICT",
    "message": "The asset was modified by another request.",
    "details": {},
    "request_id": "..."
  }
}
```

稳定错误码至少包括：

- `EVIE_ASSET_NOT_FOUND`
- `EVIE_ASSET_DELETED`
- `EVIE_ASSET_STATE_CONFLICT`
- `EVIE_IDEMPOTENCY_CONFLICT`
- `EVIE_IDEMPOTENCY_KEY_REQUIRED`
- `EVIE_ROW_VERSION_CONFLICT`
- `EVIE_EXACT_DUPLICATE_CONFLICT`
- `EVIE_RESTORE_DUPLICATE_CONFLICT`
- `EVIE_INVALID_REVIEW_TRANSITION`
- `EVIE_REVIEW_VERSION_NOT_CURRENT`
- `EVIE_VERSION_NOT_FOUND`
- `EVIE_VERSION_SCOPE_MISMATCH`
- `EVIE_SOURCE_SCOPE_MISMATCH`
- `EVIE_PROJECT_NOT_FOUND`
- `EVIE_PROJECT_INACTIVE`
- `EVIE_PROJECT_SCOPE_FORBIDDEN`
- `EVIE_DATA_INTEGRITY_ERROR`

API 上线前必须完成显式 project scope、禁止自动创建默认项目、自然语言请求体日志脱敏/
关闭，以及结构化领域异常映射。

### 12.1 A-09：API 成功与冲突语义合同

所有公开写接口缺少 `Idempotency-Key` 时返回稳定错误码
`EVIE_IDEMPOTENCY_KEY_REQUIRED`。

| 操作 | HTTP 状态 |
|---|---:|
| 新建资产 | 201 |
| 精确重复复用 | 200 |
| 创建新版本 | 201 |
| 空修改 | 200 |
| 历史版本恢复并创建新版本 | 201 |
| 创建审核记录 | 201 |
| 删除 | 200 |
| 恢复 | 200 |
| 查询 | 200 |

删除返回 200 而不是 204，以返回新的 row_version、删除状态并支持幂等重放。

固定错误映射：未认证 401；project scope 无权限 403；资源不存在或普通查询隐藏已删除资源
404；幂等、乐观锁、状态和重复冲突 409；Schema、参数或必需 Header 不合法 422。

普通查询已删除资源统一返回 404 `EVIE_ASSET_NOT_FOUND`，避免泄露存在性。已经完成授权并
定位到聚合的编辑、审核或重复删除等写操作返回 409 `EVIE_ASSET_DELETED`。只有授权的
`include_deleted=true` 查询可以显式返回 deleted 状态。

## 13. 前端范围合同（D-12）

完整前端资产中心不属于 Asset Lifecycle Core 的核心验收条件。核心 API 稳定后，可以独立
实施最小前端切片：资产列表、Manual 创建、详情、版本历史、编辑、审核、删除和恢复。

前端只能复用通用 UI、分页、表单、认证和请求组件，不得复用 Candidate、Preview、旧
TestPointAsset 或 Workbench 状态作为新事实源。所有前端写操作必须调用本合同定义的 API，
不得绕过统一 Intake/Lifecycle/Review Service。

## 14. Migration 合同（D-13）

- 实施前重新读取真实 Alembic heads/history；当前预期父 revision 为 `20260713_121000`。
- 不修改 frozen baseline、120000 或 121000。
- 新建 Requirement 来源子表，回填并验证现有来源，再移除主表专用字段。
- SQLite 使用受控 batch rebuild；PostgreSQL 使用显式 backfill 和约束收紧。
- 所有约束和索引显式命名，UTF-8 字节不超过 63。
- upgrade/downgrade/upgrade、真实 PostgreSQL、外键开启 SQLite 和 bootstrap 回归必须通过。
- identifier 守卫必须自动扫描所有 Alembic revision、SQLAlchemy metadata 以及显式表、列、
  约束和索引，不得继续手工只列已知 Migration。

### 14.1 A-05：Downgrade 数据保护合同

从 Phase 1 降级到 121000 前，以下任一条件成立必须 fail-closed：

- 存在非 requirement 来源；
- 存在 TestAssetReviewRecord；
- 存在 TestAssetAuditEvent；
- 存在无法还原到 Phase 0 source 结构的数据；
- 来源主/子表不一致；
- 存在未知 Phase 1 source_type。

IdempotencyRecord 和 ContentClaim 是可重建技术状态，仅在业务数据保护检查通过后删除。

允许 downgrade 时依次：回填 Requirement 字段、验证非空/唯一/父子归属、重建 Phase 0
source 表、删除可重建技术表、删除已确认为空的 Phase 1 业务历史表、验证结构 fingerprint。
不得用 `--force` 或捕获异常继续绕过。

该限制适用于普通 Alembic downgrade。确需回退时，必须先执行独立、显式批准的数据导出
和治理流程，使数据库重新满足无损 downgrade 前置条件；Migration 不提供 force 参数。

Migration 测试必须区分：空 Phase 1 业务数据时 downgrade 成功；存在不可逆业务数据时
downgrade 被明确拒绝且数据库保持不变。

### 14.2 A-06：存量 Content Claim 回填冲突合同

Phase 1 Migration 在回填 Content Claim 前必须执行只读数据预检。以下任一情况存在时，
Migration 必须在创建或修改业务结构前 fail-closed：

- 同一 project 下多个有效 TestAsset 具有相同 content fingerprint；
- 有效 TestAsset 缺少 current version；
- current version 不属于对应 TestAsset；
- 无法按批准算法稳定计算 fingerprint。

Migration 不得自动选择 canonical asset，不得合并、删除、软删除或跳过重复资产。失败信息
只能包含 project 标识、重复组数量和资产公共 ID，不得包含自然语言正文。

预检无冲突后，才允许为每个有效 TestAsset 建立唯一 claim，并保证：

```text
UNIQUE(project_code, content_fingerprint)
UNIQUE(test_asset_pk)
```

#### 14.2.1 Migration 指纹算法确定性

Content Claim 回填所使用的内容规范化、canonical JSON 序列化和 SHA-256 算法，
必须作为该 Alembic revision 的冻结实现存在。

Migration 不得导入当前应用层 ORM、Service、Policy、Settings 或其他可继续演进的
业务模块来计算历史数据指纹。允许的实现方式仅为：

- 将冻结算法直接实现于该 Migration；
- 或使用仅服务于该 revision、内容不可变的 migration-local helper。

冻结实现必须通过固定测试向量验证，并在 Phase 1 发布时与当前应用 Policy
产生相同指纹。失败诊断只能输出公共 ID、项目标识和计数，不得输出自然语言正文。

后续如修改内容规范化算法，必须通过新的版本化 Migration 和新的业务决策处理，
不得修改已经发布的历史 Migration。

## 15. Requirement 生命周期（D-14）

Requirement 生命周期属于 Phase 1，但作为独立后续切片。Asset Lifecycle Core 首批支持
Manual 创建和绑定已存在 Requirement/RequirementVersion，不要求新 Requirement API。

可以先宣告 `Phase 1 Asset Lifecycle Core` 完成；Requirement 创建、列表、详情、新版本、
删除恢复及来源集成完成前，不得宣告完整 Phase 1 完成。

## 16. 验收门禁

Phase 1 Asset Lifecycle Core 至少要求：

- 模型、Schema、Repository、Policy、Service、API、Migration 和架构守卫测试；
- 多表中途失败全部回滚；
- 同幂等 key 并发只产生一个结果；
- 同内容 claim 并发只占用一个有效资产；
- version_no 与 row_version 冲突不静默覆盖；
- Version、Review、Audit 不可变；
- 删除默认隐藏，恢复冲突明确；
- SQLite/PostgreSQL migration 和 bootstrap 回归；
- 自然语言正文不进入 access log 或 audit；
- 旧 Candidate/Compiler/Runner 失败基线不增加。

本合同批准实施计划编写，不等于允许跳过分切片审查直接提交全部代码。
