# ADR-0001：EvieAi Phase 1 自然语言测试资产生命周期

状态：Accepted
日期：2026-07-15
决策人：用户明确确认
适用阶段：EvieAi Phase 1 Asset Lifecycle Core

## 背景

EvieAi Phase 0 已建立 `Requirement`、`RequirementVersion`、`TestAsset`、
`TestAssetVersion` 和 Requirement-only `TestAssetSource` 的持久化基线。

2026-07-14 的 Phase 1 只读规格预检确认：统一 Intake、版本不可变、多来源、
审核历史、幂等、精确重复、软删除恢复和审计均属于 Phase 1，但其物理实现必须
先完成人工签字。数据库前向兼容阻塞 C-01 已通过 PR #4 修复并合并到 `dev`，合并提交为
`f5c8226`；合并记录包含 77 项定向测试通过和真实 PostgreSQL 16 验证 6/6 通过。

本 ADR 记录用户在 2026-07-15 明确批准的 Phase 1 核心决策。详细字段、状态、
错误和接口合同以
`docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-specification.md`
为准。

实施计划评审状态（2026-07-15）：

D-01～D-14 的核心架构决策保持 Accepted。

以下补充合同已于 2026-07-15 获得用户明确签字：

- A-01：asset_code 权威生成规则；
- A-02：project scope、actor 和 channel 权威来源；
- A-03：编辑时 Content Claim 原子替换；
- A-04：来源主表与子类型表跨表一致性；
- A-05：downgrade 业务数据保护；
- A-06：存量 Content Claim 回填冲突处理；
- A-07：来源身份算法；
- A-08：审核并发与重复审核语义；
- A-09：API 和查询细节；
- A-10：版本字段边界。

上述补充合同必须同步进入 Specification 和 Implementation Plan。只有文档提交、审查和合并
完成后，才允许从最新 `dev` 创建 Slice 1 功能分支；本 ADR 本身不直接授权跳过切片审查。

## 决策

### D-01：统一 Intake 与事务边界

- 所有资产创建入口必须调用统一的 `TestAssetIntakeService`。
- 所有版本创建、历史恢复、删除和恢复操作必须调用 `TestAssetLifecycleService`。
- 所有审核操作必须调用 `TestAssetReviewService`。
- Adapter 不得自行实现平行的资产保存、生命周期或审核主链。
- Phase 1 不引入全平台通用 Unit of Work 框架。
- Application Service 或轻量 transaction runner 使用 `session.begin()` 控制事务。
- Repository 只允许 add、flush、query，不 commit、不 rollback。
- Router 不直接操作 ORM 或控制事务。

### D-02：多来源模型

- `test_asset_sources` 演进为通用来源主表。
- 新增 `test_asset_requirement_sources` 作为 Requirement 来源子表。
- Phase 1 首批 `source_type` 为 `requirement` 和 `manual`。
- API、前端、CI 是渠道，不是来源类型。
- 现有 Requirement-only 来源必须无损回填到子表。

### D-03：创建聚合的原子事务

一次创建必须在同一事务中完成：幂等 claim、精确重复 claim、TestAsset、首版本、
来源、`current_version_pk` 和审计事件。创建失败时全部回滚。

精确重复复用路径不创建新的 `TestAsset` 或 `TestAssetVersion`。该路径只允许在同一事务中
完成：

- 幂等结果记录；
- 内容 claim 校验；
- 必要且尚不存在的真实来源新增；
- `exact_duplicate_reused` 审计事件。

其中任一步失败时全部回滚。

### D-04：幂等模型

- 新增独立 `test_asset_idempotency_records`。
- 所有公开写接口要求 `Idempotency-Key`。
- 唯一作用域为 project、operation、actor/client 和 key。
- 相同 key/相同请求返回原结果；相同 key/不同请求返回
  `EVIE_IDEMPOTENCY_CONFLICT`。
- 默认保留期 7 天，必须配置化。

### D-05：精确重复

- 同一 `project_code` 下的有效资产参与精确重复检测。
- 新增 `test_asset_content_claims`，唯一约束为
  `(project_code, content_fingerprint)`。
- 创建命中时复用已有资产并按真实语义新增来源，不返回冲突。
- 编辑命中另一有效资产时返回 `EVIE_EXACT_DUPLICATE_CONFLICT`。
- 删除释放 claim；恢复必须重新申请 claim。

编辑创建新版本且内容指纹发生变化时，必须在创建版本的同一事务中原子替换 content
claim。

事务必须保证：

- 校验目标 `(project_code, content_fingerprint)` 未被其他有效资产占用；
- 目标指纹冲突时不创建版本，原 claim 保持有效；
- 成功时更新该资产唯一的现有 claim，使其对应新 current version 的内容；
- 新版本、`current_version_pk`、`row_version`、claim、审计和幂等结果在同一事务提交；
- 任一步失败时整体回滚；
- 同一有效资产在事务完成后必须且只能拥有一条当前内容 claim。

不得通过让同一资产临时持有两条 claim 实现替换。A-03 已确定通过锁定并原子更新该资产
唯一的现有 claim 实现；冲突或任一步失败时整体回滚。

### D-06：编辑和历史恢复

- 正文或版本化治理字段变化必须创建新 `TestAssetVersion`。
- 规范化后为空修改时不创建版本。
- 历史恢复通过复制旧内容创建新版本，不回指旧版本。
- 所有版本变更使用 `expected_row_version`、聚合并发保护和版本号唯一约束。

### D-07：审核记录

- 新增不可变 `test_asset_review_records`。
- 每条记录同时绑定资产和被审核的当前版本。
- 审核记录只插入，不更新、不删除。
- 审核状态仅包括 `pending`、`approved`、`rejected`；`reopen` 是审核操作，不是第四种状态。
- 允许的状态转换为：
  - `pending -> approved`；
  - `pending -> rejected`；
  - `approved -> pending`，操作类型为 reopen；
  - `rejected -> pending`，操作类型为 reopen。
- reopen 必须提供 reason，并通过新增不可变审核记录表达。
- 审核 Service 必须在事务中校验被审核版本等于资产当时的 `current_version_pk`。后续创建
  新版本后，既有审核记录仍永久关联原被审核版本，不得重写为新版本。

### D-08：软删除和恢复

- `TestAsset.deleted_at` 是当前删除状态的唯一事实源。
- 操作者、原因和恢复历史进入不可变审计事件，不在聚合重复存储。
- 删除保留 current version、来源、审核、审计和公共 ID，并释放内容 claim。
- 恢复重新申请 claim；冲突时返回 `EVIE_RESTORE_DUPLICATE_CONFLICT`。

### D-09：查询合同

- Phase 1 使用 `page/page_size`，默认 1/20，最大 100，并返回 total。
- 默认稳定排序为 `created_at DESC, test_asset_id DESC`。
- 列表、详情、版本历史和审核历史使用独立接口。
- 普通查询隐藏已删除资产；授权调用方可显式 `include_deleted=true`。
- 内部 Integer PK 不得暴露。

### D-10：操作审计

- 新增 EvieAi 专用不可变 `test_asset_audit_events`。
- 不复用旧 Workbench 或 TestDataPool 审计事实源。
- 审计只保存公共 ID、checksum、状态、版本号、变化字段和必要脱敏摘要，
  不保存完整自然语言正文。

### D-11：API 合同

- 使用显式 Pydantic Schema 和稳定结构化错误协议。
- 修改已有 `TestAsset` 聚合的写接口必须在请求体提供 `expected_row_version`，包括创建
  新版本、审核、删除和恢复。
- 首次创建 `TestAsset` 不需要 `expected_row_version`。
- 所有公开写接口均通过 `Idempotency-Key` Header 提供幂等键。
- 审核使用 POST review record，不使用 `PATCH /review-status`。
- 创建来源使用 manual/requirement discriminated union。
- API、UI、CI 渠道由服务器上下文记录，客户端不得伪装为 source type。

### D-12：前端范围

- 前端资产中心属于 Phase 1，但不阻塞 Asset Lifecycle Core 后端能力验收。
- Phase 1 前端最小能力包括资产列表、手工创建、详情、版本历史、编辑、审核、删除和恢复，
  并作为独立实施切片，在核心 API 合同稳定后交付。
- 前端只允许复用通用表格、分页、表单、确认对话框和认证请求组件。
- 禁止复用 Candidate、Preview、旧 TestPointAsset、旧 Workbench 审核状态或旧保存链作为
  EvieAi 新事实源。所有写操作必须调用 Phase 1 API，不得绕过统一
  Intake/Lifecycle/Review Service。

### D-13：Migration 与确定性数据库 baseline

- Phase 1 数据库变更只允许通过新的线性 Alembic Migration 实施。
- 实施时必须读取真实唯一 Alembic head；当前预期父 revision 为 `20260713_121000`。
- 禁止修改冻结 baseline、`20260713_120000` 和 `20260713_121000`，禁止把 Phase 1 结构
  回写到冻结 manifest，禁止使用 `Base.metadata.create_all()` 代替 Migration。
- Requirement 来源数据必须无损回填。SQLite 使用受控 batch rebuild；PostgreSQL 使用
  显式 DDL、backfill 和约束收紧。
- 所有约束和索引必须显式命名，UTF-8 字节长度不得超过 63。
- downgrade 不得静默丢失 Manual 来源或其他 Phase 1 业务事实。

### D-14：Requirement 生命周期拆分

- Requirement 生命周期仍属于 Phase 1，但作为独立后续切片实施。
- Asset Lifecycle Core 首批支持 Manual 创建和绑定已存在的 Requirement/Version。
- Requirement 生命周期切片完成前，只能宣告 Phase 1 Asset Lifecycle Core 完成，
  不能宣告完整 Phase 1 完成。

## 补充合同（A-01～A-10）

### A-01：Asset code

- 新资产 `asset_code = test_asset_id`。
- 由后端生成，客户端不得提交，创建后不得修改。
- 存量资产不重写 `asset_code`。

### A-02：Project scope、actor 和 channel

- 首版仅认证上下文中的全局 admin 可以操作已经存在且状态为 active 的 project。
- actor 只能来自认证上下文。
- channel 由服务端设置为 `api`。
- 禁止自动创建默认项目。

### A-03：编辑时 Content Claim 原子替换

- 每个有效资产必须且只能拥有一条当前内容 claim。
- 编辑时锁定并原子更新现有 claim，不插入同资产第二条临时 claim。
- 目标指纹冲突或任一步失败时整体回滚，原版本和原 claim 保持有效。

### A-04：来源主表与子类型表一致性

- 不使用数据库 trigger。
- 通过数据库约束、Service 原子事务、Repository fail-closed 和 Migration 校验共同保证。

### A-05：Downgrade 业务数据保护

- Phase 0 无法表达的业务事实存在时必须 fail-closed。
- 不允许静默丢失、部分降级或通过强制参数绕过。
- 上述限制适用于普通 Alembic downgrade。确需回退时，必须先执行独立、显式批准的数据
  导出和治理流程，使数据库重新满足无损 downgrade 前置条件；不得在 Migration 中提供
  force 参数绕过保护。

### A-06：存量 Content Claim 回填冲突

- Migration 回填前必须只读预检重复和 current version 一致性。
- 发现重复、缺失、错属或无法稳定计算 fingerprint 时 fail-closed。
- 不自动合并、删除、软删除或跳过资产。

### A-07：来源身份算法

- 来源身份由服务端按 canonical JSON 的 UTF-8 字节计算 SHA-256。
- Requirement 来源使用 Requirement 和 RequirementVersion 身份。
- Manual 来源使用 project、actor/client、operation、Idempotency-Key 和 request fingerprint。
- 客户端不得提交 `source_identity_hash`。

### A-08：审核并发与重复审核

- 审核必须针对 current version，并提供 `expected_row_version`。
- 审核记录、聚合状态、row_version、审计和幂等结果在同一事务提交。
- 使用新幂等键重复提交已完成的相同状态转换返回 409。

### A-09：API 和查询细节

- 采用 Specification 定义的成功状态码、结构化错误和 deleted 可见性语义。
- keyword 仅对 current version 的 title 做可移植、不区分大小写的子串查询。

### A-10：版本字段边界

版本内容仅包括：`title`、`precondition`、`natural_steps`、`expected_result`、`priority`、
`tags`。审核、转换、删除、并发、来源、审计和幂等事实不得写入版本正文。

## 被否决或未采用的方案

- 不采用来源单表大量 nullable 字段。
- 不采用独立 `manual_sources` 平行来源表。
- 不用内容 checksum 代替幂等键。
- 不对精确重复创建返回 409，也不创建第二个重复资产。
- 不直接切换 `current_version_pk` 恢复历史版本。
- 不使用可变审核记录或 `PATCH /review-status`。
- 不在聚合重复保存 deleted/restored actor 和 reason。
- 不复用旧 Workbench/TestDataPool 审计表。
- 不在 Phase 1 Asset Lifecycle Core 同一切片实现完整 Requirement 生命周期。

## 影响

- Phase 1 将新增来源子表、幂等、内容 claim、审核记录和审计事件等持久化对象。
- `test_asset_sources` 需要无损数据演进；SQLite 与 PostgreSQL 使用不同 DDL 路径，
  但必须得到相同逻辑结构。
- 所有写操作都必须具备多表事务、失败回滚、幂等和并发测试。
- API 上线前必须完成项目作用域校验、默认项目隐式创建治理、自然语言请求体日志
  脱敏和结构化异常映射。
- 本 ADR 不授权实现 AI 生成、Candidate、Asset-to-Case、Compiler、Runner、
  TestCase 或前端完整资产中心。
