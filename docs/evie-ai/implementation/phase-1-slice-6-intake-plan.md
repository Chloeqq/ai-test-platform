# EvieAi Phase 1 Slice 6 Intake 实施计划

日期：2026-07-27

状态：

Proposed / Pending user approval

适用范围：

EvieAi Phase 1 Slice 6 - TestAsset Intake Service

Slice 6 implementation plan status: Proposed / Pending user approval
Slice 6 implementation status: Not started
Phase 1 overall status: In Progress
Phase 1 closeout status: Not completed
Slice 7 status: Not started
Slice 8 status: Not started

本文件仅把已批准的 Slice 6 合同拆分为可审查、可批准、可实施和可验收的计划。它不授权开始编码、创建实施分支、修改 API、执行 Migration 或进入 Slice 7/8。计划 PR 合入 `dev` 且用户明确批准实施前，Slice 6 implementation 必须保持 `Not started`。

## 1. 文档定位与权威关系

本计划的权威关系固定为：

```text
AGENTS.md
-> ADR-0001
-> Phase 1 Specification
-> Phase 1 Overall Implementation Plan
-> Slice 6 Independent Implementation Plan
-> future implementation tasks and acceptance evidence
```

- `AGENTS.md` 定义自然语言资产、事务、ID、日志、安全、测试和 Git 的硬边界。
- `ADR-0001` 是 Phase 1 自然语言资产生命周期的 governing decision。
- `phase-1-natural-language-asset-lifecycle-specification.md` 是字段、来源、幂等、重复、审计和错误合同的详细来源。
- `phase-1-natural-language-asset-lifecycle-plan.md` 定义 Slice 6 顺序、P-04 竞态协调和审计矩阵。
- `phase-traceability.md` 记录当前状态和验证证据，不授予实施授权。
- `ADR-0002` 和 `ARCHITECTURE_BASELINE.md` 只约束长期目标架构，不扩大 Slice 6 的 Phase 实施范围。

如本计划与上述上级合同冲突，必须以上级合同为准，并停止相应实施而非在代码中折中。

## 2. 计划基线与当前状态

- 计划基线：`origin/dev@1223ce26101ac0ff50134dcabef93b174c1e108d`。
- 计划分支：`codex/evie-ai-phase1-slice6-plan`。
- Slice 1 已提供 ID、内容规范化、内容指纹、请求指纹、来源身份和 actor identity Policy。
- Slice 2/3 已提供 TestAsset、不可变 TestAssetVersion、Source、Idempotency Record、Content Claim、Audit Event 及数据库约束。
- Slice 4 已提供 Repository、Query、Source 完整性、Idempotency CAS 和 Content Claim 访问能力。
- Slice 5 已完成 TrustedUserPrincipal、project scope、actor/channel/trace、结构化错误和自然语言日志保护。
- 当前不存在 `TestAssetIntakeService`；本 Slice 只补齐这一服务主链及直接测试。

当前已知冻结 CI 基线仍为：

| Baseline ID | 已知失败 | Slice 6 责任 |
|---|---|---|
| CI-B01 | Workbench facade 缺少 `app.api.workbench.facade.test_case_service` | 不修复；不得新增或改变其失败签名。 |
| CI-B02 | `apps/ai-orchestrator/src/app.py` 缺失导致静态基线收集失败 | 不修复；不得新增或改变其失败签名。 |

## 3. 目标与固定边界

### 3.1 唯一创建入口

`TestAssetIntakeService` 是 Manual 和 Requirement 自然语言资产创建的唯一公开业务入口。

- 未来 Router、AI producer、CI 或批量 producer 只能构造已验证的输入并调用该 Service。
- Adapter 不得各自实现平行的 Asset、Version、Source、Idempotency、Content Claim 或 Audit 保存链。
- 内部竞态协调器只能是该 Service 的私有实现细节，不得成为第二个公开保存服务。

### 3.2 本 Slice 必须实现

- Manual 和 Requirement 来源的统一 Intake。
- 服务端分配 `ta_`、`tav_`、`tas_` 和 `tae_` 公共 ID。
- TestAsset、首个不可变 TestAssetVersion、Source、Content Claim、Audit 和 Idempotency Result 的原子创建或复用。
- 请求幂等、过期 record 的 generation CAS 和精确重复复用。
- Requirement 公开 ID、版本归属和项目归属校验。
- 可信 project、actor、channel、request_id/correlation_id 上下文的复用。
- P-04 定义的命名唯一约束识别与全新 Session 单次重试。
- 直接单元、事务、并发和架构边界测试。

### 3.3 本 Slice 不得实现

- Candidate、Preview、selected candidates、TestPointPlan 或候选选择流程。
- action、target、value、locator、selector、structured steps、DSL、Compiler IR 或 `script_code`。
- TestCase、TestCaseVersion、Runner、Asset-to-Case、资源绑定或可执行性判断。
- Router/API、HTTP endpoint、前端、Migration、ORM 字段或数据库表变更。
- 语义去重、RAG、Embedding、向量检索或异步 AI 评估。
- Slice 7 Lifecycle/Review、Slice 8 Router/API，或 CI-B01/CI-B02 修复。

低质量、低置信度、描述不完整、有歧义、缺少页面对象/测试数据/环境/凭证的自然语言内容必须允许进入 Intake；这些不是拒绝条件。

## 4. 输入、输出与事实源

### 4.1 可信输入边界

未来调用方在进入 `TestAssetIntakeService` 前必须获得或传入下列既有受控上下文：

| 输入 | 权威来源 | 使用规则 |
|---|---|---|
| `TrustedUserPrincipal` | Slice 5 `UserPublicIdentityService` | 只能由 authenticated User 构造；不接受 ORM User、内部 `User.id`、email、username 或请求正文身份。 |
| project scope and access | Slice 5 `ProjectAccessAuthorizer`、`ProjectScopeService` + `TestProject` | 先以 TrustedUserPrincipal 执行 active-admin 授权，再校验显式 project 存在且 active；不得默认、猜测或自动创建 project。每次干净重试重新校验 project scope。 |
| actor | Slice 5 `RequestActorContext` | 固定为 `user:<user_public_id>`；客户端不得覆盖。 |
| channel | Slice 5 `RequestChannelContext` | 当前服务端受控值为 `api`；不是客户端字段，也不是来源类型。 |
| trace | Slice 5 `RequestTraceContext` | 使用已有 `request_id` 和服务端生成的 `correlation_id`；客户端不得提供 correlation ID。 |
| create command | `TestAssetCreate` 和 Manual/Requirement discriminated union | 仅包含 project、source 和六个自然语言内容字段；不得提交权威 ID、actor、source hash、状态或治理字段。 |
| idempotency key | 未来 Adapter 的 `Idempotency-Key` | Service 接收已提取的字符串值，不接收 HTTP Request；空白或缺失 fail-closed。 |

Service 只能依赖这些类型化输入、Repository 和既有 Policy。不得通过任意 `dict`、全局请求对象、环境变量或请求正文补齐核心业务事实。

### 4.2 输出

Service 返回现有 `TestAssetOperationResult`，并在同一事务保存对应的 `IdempotencyResultSummary`。

| 结果 | `created` | `reused_existing` | 预期 HTTP 语义，供 Slice 8 使用 |
|---|---:|---:|---:|
| 新建资产 | `true` | `false` | 201 |
| 精确重复复用 | `false` | `true` | 200 |
| 同键重放 | 保存的原结果 | 保存的原结果 | 保存的原 HTTP 语义 |

Slice 6 不创建 Router，不直接返回 `HTTPException`，也不实现 HTTP response envelope。它只抛出 `EvieAiDomainError`，由 Slice 5 已有 path-scoped adapter 和未来 Slice 8 Router 负责传输适配。

### 4.3 唯一事实源

- 自然语言正文：首个 `TestAssetVersion` 的六个内容字段；不得写回 `TestAsset`。
- 当前版本：`TestAsset.current_version_pk` 指向所属 Version。
- 来源事实：`TestAssetSource` 及 Requirement 类型化子表。
- 精确重复当前占用：`TestAssetContentClaim`。
- 幂等重放结果：`TestAssetIdempotencyRecord` 当前 generation 的摘要。
- 审计历史：不可变 `TestAssetAuditEvent`。
- 项目事实：既有 `TestProject.project_code` 与状态；不得新增平行项目表。

## 5. 新建路径、状态与事务边界

### 5.1 固定处理顺序

每次业务尝试的公共顺序固定为：

```text
trusted principal authorization and project scope validation
-> request normalization
-> request fingerprint
-> idempotency claim
-> content fingerprint
-> content claim lookup
-> create path or exact-duplicate reuse path
```

新建路径在同一个 Session 和 `session.begin()` 事务中按以下顺序执行：

```text
create TestAsset and flush internal PK
-> create TestAssetVersion(version_no=1)
-> create TestAssetSource and Requirement subtype when applicable
-> add TestAssetContentClaim
-> set current_version_pk through the repository
-> append asset_created AuditEvent
-> complete Idempotency Result
-> commit
```

Repository 只允许 add、flush、query 或条件更新；不得 commit、rollback 或自行决定业务重试。Service 或其私有协调器拥有事务边界。

### 5.2 初始状态

新建聚合必须使用已批准的初始业务状态：

```text
version_no = 1
review_status = pending
conversion_status = not_started
deleted_at = null
```

创建时不得生成 ReviewRecord，不得生成 `failed` conversion status，也不得创建任何执行实体。

### 5.3 全回滚要求

以下任一步失败时，当前尝试中的 Idempotency Record、TestAsset、Version、Source、Requirement subtype、Content Claim、Audit Event 和结果摘要必须全部回滚：

- Requirement 公开 ID、版本归属或项目归属校验失败。
- Source 写入或 subtype 写入失败。
- Content Claim 唯一冲突以外的持久化失败。
- current version 归属或乐观锁失败。
- Audit 或 result completion 失败。
- 任意未列入允许重试名单的 `IntegrityError`。

失败 Session 必须 rollback、close 并弃用；不得在失败事务中查询、再次 `begin()` 或继续写入。

## 6. Requirement 来源与 Source 规则

### 6.1 Requirement 解析

`requirement` source 必须只使用公开 `requirement_id` 和 `requirement_version_id`。Slice 6 将在 `RequirementRepository` 增加一个最小只读解析能力，用于在同一 Session 中解析未删除的 Requirement 与指定 Version，并证明：

- Version 属于该 Requirement。
- Requirement 与经验证 project scope 相同。
- 内部 PK 仅在 Service 调用已有 `TestAssetSourceRepository` 时使用，绝不进入响应或审计公开事实。

找不到、父子不匹配或跨项目的来源必须 fail-closed，并使用现有 `EVIE_SOURCE_SCOPE_MISMATCH` / `EvieAiErrorStage.INTAKE` 合同；不得创建空来源、跨项目绑定或自动复制 Requirement。

### 6.2 Source identity

- Requirement Source hash 只由 `source_type`、`requirement_id` 和 `requirement_version_id` 的既有 Policy 生成。
- Manual Source hash 只由 project、trusted actor、`create_asset`、idempotency key 和 request fingerprint 的既有 Policy 生成。
- 客户端不得提供、覆盖或反向计算 `source_identity_hash`。
- 同一精确重复资产只有当该 source identity 尚不存在时才追加 Source。
- 相同 idempotency scope/key 的重放不得新增 Source 或 Audit。

## 7. 幂等、精确重复与语义疑似重复

### 7.1 幂等

作用域固定为：

```text
project_code + create_asset + actor_or_client_id + idempotency_key
```

request fingerprint 使用既有 `CreateAssetFingerprintInput`，包含 source type、Requirement 公开 ID（如适用）和规范化后的六个内容字段；不得包含 project、actor、channel、trace、时间或 idempotency key。

| 状况 | 行为 |
|---|---|
| scope/key 不存在 | 创建 generation 1 claim，继续 Intake。 |
| 未过期且 fingerprint 相同，且已有完成结果 | 重放保存的不可变结果；不新建领域记录或审计。 |
| 未过期且 fingerprint 不同 | `EVIE_IDEMPOTENCY_CONFLICT`，stage=`intake`，不写领域记录。 |
| 已过期 | 用既有 generation CAS 重新占用；CAS 失败后重新读取，绝不无条件覆盖。 |
| 缺失、空白或非法 key | `EVIE_IDEMPOTENCY_KEY_REQUIRED`，stage=`intake`，不开始事务写入。 |

使用既有 `EVIE_AI_IDEMPOTENCY_RETENTION_DAYS` Settings，默认 7 天。Slice 6 不新增配置，也不得在业务代码直接读取环境变量。

### 7.2 精确重复

content fingerprint 只基于规范化后的 title、precondition、natural_steps、expected_result、priority 和 tags。命中同项目的 `TestAssetContentClaim` 后：

```text
read existing active TestAsset
-> add only a genuinely new Source when needed
-> append source_added when a Source was added
-> append exact_duplicate_reused
-> save idempotency result
-> commit
```

复用路径不得创建 TestAsset、TestAssetVersion 或第二条 Content Claim。所有复用审计共享 actor、channel、request_id、correlation_id、operation type、idempotency scope/key hash 和 generation 快照；每条 Audit Event 仍有独立 `tae_` ID。

### 7.3 语义疑似重复

语义近似不等于精确重复。本 Slice 不实现疑似关系、Embedding、RAG、向量存储或任何阻断策略。未来异步评估可以标记疑似关系或提供审核建议，但不得阻止或回滚本 Slice 的 Intake。

## 8. P-04 竞态协调与 Session 规则

`TestAssetIntakeService` 是唯一公开入口。其同文件私有协调逻辑负责为每次尝试创建一个新 Session 和事务；不得引入通用 Unit of Work、第二个公开 Intake Service 或跨请求共享 Session。

只有以下明确命名的唯一约束允许触发竞态回退：

| 约束 | 允许行为 |
|---|---|
| `uq_test_asset_idempotency_scope_key` | 失败 Session 全回滚并关闭；新 Session 从 project scope、fingerprint 和幂等检查重新开始。 |
| `uq_test_asset_content_claims_project_fingerprint` | 失败 Session 全回滚并关闭；新 Session 从完整 Intake 重新开始；最多一次完整重入。 |

- 约束检测必须白名单化，并覆盖数据库驱动返回命名约束或结构化唯一列信息的情形。
- 不得把任意 `IntegrityError`、Source 冲突、Version 冲突或业务异常误判为幂等/重复竞态。
- 完整重入后若不能读取获胜的已完成 idempotency result 或 Content Claim，或再次发生未预期冲突，必须以现有 `EVIE_DATA_INTEGRITY_ERROR` fail-closed。
- 不得无限循环、使用 sleep、进程内锁或复用失败 Session。

## 9. 错误、审计和日志

### 9.1 领域错误

Service 必须复用现有 `EvieAiDomainError`、`EvieAiErrorCode` 和 `EvieAiErrorStage.INTAKE`。本计划不授权新增 Slice 6 错误码。

| 场景 | 稳定错误码 |
|---|---|
| 缺失或空白 Idempotency Key | `EVIE_IDEMPOTENCY_KEY_REQUIRED` |
| 同 scope/key 不同请求 | `EVIE_IDEMPOTENCY_CONFLICT` |
| Requirement/Version 不存在、不归属或跨项目 | `EVIE_SOURCE_SCOPE_MISMATCH` |
| 未白名单的持久化异常、获胜方不可读取或不变量破坏 | `EVIE_DATA_INTEGRITY_ERROR` |

Service 不得抛出 `HTTPException`、暴露 SQL、约束原文、内部 PK、token、请求正文或堆栈。

### 9.2 Audit 和日志

| 结果 | 必须写入的审计事件 |
|---|---|
| 新建 Asset 及首来源 | `asset_created` |
| 精确重复，无新 Source | `exact_duplicate_reused` |
| 精确重复，有真实新 Source | `source_added` 和 `exact_duplicate_reused` |
| 同键重放 | 不新增审计事件 |

Audit 只保存公共 ID、版本号、状态、checksum、来源类型、必要的脱敏状态摘要和既有上下文字段。不得保存 title、precondition、natural_steps、expected_result、Requirement 正文、原始 Idempotency-Key 或完整请求/响应正文。Slice 5 的自然语言日志保护必须保持不变。

## 10. 拟修改文件

| 文件 | 动作 | 计划职责 |
|---|---|---|
| `apps/web-ui-service/app/services/evie_ai/test_asset_intake_service.py` | 新增 | 唯一公开 Intake Service、同文件私有单次竞态协调、事务编排、上下文复用与稳定领域错误。 |
| `apps/web-ui-service/app/repositories/evie_ai/requirement_repository.py` | 修改 | 增加最小公开 ID 对解析能力；不改变 Requirement 生命周期、事务或数据模型。 |
| `apps/web-ui-service/tests/unit/evie_ai/conftest.py` | 修改 | 为 Intake 事务测试提供隔离 Session factory 和包含 `TestProject` 的最小测试表集合。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_intake_service.py` | 新增 | 服务、回滚、重放、来源、审计和竞态测试。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py` | 修改 | 覆盖 Requirement 公开 ID/Version 解析、父子归属、软删除和项目范围。 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py` | 修改 | 将 Slice 5 专属守卫限定到 Slice 5 文件，同时继续保护 Intake 不依赖 Candidate、Compiler、Runner、默认项目或 API path。 |

不得修改：`app/core/security.py`、`app/routers/auth.py`、`app/main.py`、生产 Router、ORM、Alembic、Schema、ID 模块、Slice 5 服务、前端或架构合同。

## 11. 实施单元

### S6-T01：Requirement 公开来源解析

- 在 `RequirementRepository` 增加最小只读解析操作，返回同一 Requirement 的指定 Version。
- 校验软删除、公开 ID、Version 父子归属和 project scope。
- 不写数据、不控制事务、不新增错误码。

### S6-T02：Intake 上下文与输入验证

- `TestAssetIntakeService` 只接受既有 Schema、TrustedUserPrincipal、Idempotency Key 和内部 trace context。
- 复用 Slice 5 project/actor/channel 服务；原始 ORM User、内部 PK、客户端 actor/channel/correlation ID 一律拒绝。
- 在每次干净尝试中重新校验 project scope。

### S6-T03：Idempotency claim 与结果重放

- 使用既有 scope、fingerprint、generation CAS 和 result summary Repository。
- 固定 create asset operation、过期重新占用、同键冲突和已完成结果重放语义。
- 不把未完成或失败记录当作成功重放。

### S6-T04：新建聚合事务

- 按第 5 节顺序创建 Asset、首 Version、Source、Claim、current pointer、Audit 和 idempotency result。
- 只使用现有 ID、content fingerprint、source identity 和 asset code Policy。
- 每一步 flush 的失败必须触发整体 rollback。

### S6-T05：精确重复复用与来源审计

- 按 project/content fingerprint 查询有效 claim。
- 不创建新 Asset/Version；只在 Source identity 不存在时追加真实来源。
- 严格使用第 9.2 节事件矩阵。

### S6-T06：P-04 单次竞态回退

- 仅识别第 8 节的两个命名唯一约束。
- 新 Session 从完整链路重入一次；不得复用失败 Session。
- 覆盖 winner result 重放、winner content claim 复用和不可归因冲突 fail-closed。

### S6-T07：边界与回归验证

- 更新 Slice 5 专属 AST 守卫的作用范围，不降低任何 Candidate/Compiler/Runner/default project 防护。
- 运行 Intake、Schema、fingerprint、source、repository、coordination、governance、Slice 5 context 和架构边界回归。

## 12. 测试矩阵

| 测试组 | 最小覆盖 | 通过标准 |
|---|---|---|
| 新建主链 | Manual/Requirement 新建、六个内容字段不完整、服务端 ID、首 Version、Source、Claim、初始状态和结果摘要 | 一个事务内记录完整；无机器字段或 ReviewRecord。 |
| 可信上下文 | ORM User、客户端 actor/channel/trace、默认 project、非法/非 active project | 全部 fail-closed；无数据库写入。 |
| Requirement 来源 | 未知公开 ID、错误 Version 父子关系、跨项目、重复来源 | 不跨项目绑定；只为有效真实来源建子表。 |
| 幂等 | 同键同指纹、同键异指纹、过期 CAS、失败事务后重试 | 重放原结果；不重复 Asset/Source/Audit；冲突稳定。 |
| 精确重复 | 同项目同 content、不同 project、无新 Source、有新 Manual/Requirement Source | 只复用同项目有效 Asset；事件矩阵正确。 |
| 事务与竞态 | 每个持久化阶段故障、两个允许唯一冲突、非白名单 IntegrityError | 完全回滚；新 Session 最多重入一次；其余 fail-closed。 |
| 审计和隐私 | event context、idempotency snapshots、无正文/原 key/内部 PK | 审计不可变且只存脱敏摘要。 |
| 架构守卫 | 新 Service import/文本 AST 检查 | 不导入 Candidate、Preview、Compiler、Runner、TestCase 或旧生成链；无 `/api/evie-ai/test-assets`。 |
| 直接回归 | Slice 1-5 Policy、Schema、Repository、Coordination、Governance、Slice 5 context | 不引入新失败；CI-B01/CI-B02 仅按既有基线归因。 |

计划中的最小验证命令如下，实施阶段才执行：

```text
python -m pytest apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_intake_service.py -q
python -m pytest apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py -q
python -m pytest apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_coordination_repositories.py -q
python -m pytest apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_source_repository.py -q
python -m pytest apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py -q
```

实施 PR 还必须执行与修改路径相关的 Slice 5 context、Schema、Policy、Governance 和必要的 Phase 1 回归组，并记录 collected、passed、failed、errors、skipped、warnings 与 CI-B01/CI-B02 归因。

## 13. 验收标准

Slice 6 只有在以下全部满足时才可声明 implementation complete：

1. `TestAssetIntakeService` 是唯一公开创建入口，且无平行保存链。
2. 新建路径以单一事务完成全部聚合、claim、audit 和幂等结果写入。
3. 任意中途失败不留下部分 Asset、Version、Source、Claim、Audit 或 completed result。
4. 新建初始 review/conversion 状态、版本和删除状态符合已批准合同。
5. Requirement 的公开 ID、版本归属和项目归属均由服务端验证。
6. actor 固定来自 TrustedUserPrincipal，channel/trace/project scope 不可由客户端覆盖。
7. 幂等重放、冲突、过期 CAS 与结果摘要符合第 7.1 节。
8. 精确重复复用不创建新 Asset/Version，Source/Audit 矩阵正确。
9. 只识别两个白名单唯一约束，并使用全新 Session 最多完整重试一次。
10. 非白名单异常、获胜方不可读取和数据不变量破坏均 fail-closed。
11. Audit 和日志不保存自然语言正文、原始 Idempotency-Key、内部 PK 或敏感值。
12. 所有新增/修改的 Slice 6 测试和必要回归通过，且无已证明的新回归。
13. `git diff --check` 通过；禁止文件、Migration、Router/API、前端和 Slice 7/8 无改动。

## 14. 风险与实施前待决项

| ID | 风险或待决项 | 处理要求 |
|---|---|---|
| S6-R01 | 现有 `TestAssetRepository.set_current_version()` 会推进 `row_version`，而创建合同写明初始 `row_version = 1`。 | 编码前必须确认创建完成后对外结果是 `1` 还是 pointer 写入后的 `2`，并以批准结论调整 Repository 合同或创建路径；不得绕过 Repository 直接更新 ORM。 |
| S6-R02 | P-04 需要可靠识别 PostgreSQL 与 SQLite 的同一命名唯一约束。 | 在实施设计和测试中固定白名单检测方式；不能以泛化异常字符串或任意 IntegrityError 重试。 |
| S6-R03 | 每次干净重试必须重做 project scope 校验，同时不能接收原始请求或 ORM User。 | 在 Service 的类型化输入和 Session factory 注入中固定此职责；不得创建全局 Unit of Work。 |
| S6-R04 | 当前 EvieAi repository fixture 未包含 `TestProject` 和可复用的 Session factory。 | 仅扩展测试 fixture 的最小表集合与 factory，不改生产数据库配置。 |
| S6-R05 | 语义疑似重复是长期能力但暂无事实模型或异步合同。 | 保持非目标；不得为方便测试引入 Embedding、RAG、字段或表。 |

S6-R01 是编码前必须关闭的合同冲突。其余项目可在获批实施设计中通过本计划已定义的最小边界解决，不能扩大到 Slice 7/8。

## 15. 明确非动作

- 不修改 `AGENTS.md`、ADR、ARCHITECTURE_BASELINE、Phase 1 Specification、Overall Plan 或 phase traceability 状态。
- 不创建或修改 TestAsset API endpoint、Router、前端、Migration、ORM、Schema、ID 格式或第三方依赖。
- 不处理 `.playwright-mcp/**`、`outputs/**`、CI-B01 或 CI-B02。
- 不把 Slice 6 计划写成已经实施、已经验证或已经 Closeout。
- 不宣布 Phase 1 completed、Phase 1 closeout completed、Slice 7/8 started 或 Phase 2 started。

## 16. 实施授权门禁

开始 Slice 6 编码前必须同时满足：

1. 本计划通过独立 Docs PR 审查并合入 `dev`。
2. 用户明确批准本计划并关闭 S6-R01。
3. 从最新、干净的 `dev` 创建独立 Slice 6 实施分支。
4. 原工作区无混入的本地产物、个人文件或无关改动。
5. 实施前重新核对当前 Git branch、HEAD、worktree、相关测试环境和 Slice 5/CI 基线。

在上述门禁满足前，Slice 6 implementation status 必须保持 `Not started`。
