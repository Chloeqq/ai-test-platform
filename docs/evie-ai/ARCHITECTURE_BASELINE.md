# EvieAi Architecture Baseline

基线日期：2026-07-12
状态：Frozen
基线名称：EvieAi Architecture Baseline 2026-07-12

## 1. 基线目的

本基线冻结 EvieAi 的总体架构、自然语言测试资产边界、
目标能力空间、工程约束和阶段实施边界。

冻结后，普通功能实现不得自行修改架构主链、领域职责、
事实源、状态模型、ID规则或阶段边界。

## 2. 基线文件

本基线包括：

- `AGENTS.md`
- `docs/evie-ai/README.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/natural-language-test-assets.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/engineering/coding-standards.md`
- `docs/evie-ai/implementation/phase-0-domain-model.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-specification.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-plan.md`
- `docs/evie-ai/implementation/phase-traceability.md`
- `docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`
- `docs/evie-ai/migration/legacy-chain-freeze-list.md`
- `docs/evie-ai/migration/docs-cleanup-plan.md`
- `docs/evie-ai/reference/README.md`
- `docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`
- `docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`

## 3. 已冻结的核心决策

- 自然语言 TestAsset 是一等持久化业务实体。
- TestAsset 表达“测什么”，TestCase 表达“如何执行”。
- AI生成侧只生成自然语言测试点。
- 所有资产生产者进入统一资产入库。
- Candidate退出EvieAi产品主链。
- Asset-to-Case是唯一自然语言转机器语言入口。
- 每个ConversionAttempt锁定明确的TestAssetVersion。
- 资源只能通过Resource Capability Gateway解析和绑定。
- TestCaseVersion.script_code是执行代码唯一事实源。
- Runner只执行，不重新理解自然语言。
- 版本化事实不得原地覆盖。
- review_status和conversion_status相互独立。
- 失败反馈不得未经审核覆盖版本化事实源。
- Phase文档定义当前实施边界。
- Excel和架构图不得自动扩大当前任务范围。

## 4. 变更规则

冻结后，如需修改架构决策，必须：

1. 获得用户明确确认。
2. 说明变更原因和影响范围。
3. 新增或更新ADR。
4. 更新受影响的架构专题。
5. 更新阶段追踪矩阵。
6. 必要时更新架构图和Excel。
7. 更新当前Phase实施文档。
8. 运行跨文档一致性检查。
9. 创建新的架构基线提交和Git Tag。

不得在普通功能提交中顺便修改架构决策。

纯文字修正、断链修复和不改变语义的排版调整，
可以不创建ADR，但仍需保持单独的文档提交。

## 5. ADR路径

架构决策记录使用：

`docs/evie-ai/decisions/ADR-XXXX-<topic>.md`

每个ADR至少包含：

- 状态
- 日期
- 背景
- 决策
- 替代方案
- 影响
- 迁移要求

## 6. 当前实施阶段

当前阶段：EvieAi Phase 1 Asset Lifecycle Core

状态：D-01～D-14 与 A-01～A-11 已批准；P-01～P-09 已闭合；权威文档已通过
PR #5 合并到 `dev@adb2b2b`，允许从最新 `dev` 创建 Slice 1 功能分支。

权威实施范围以：

- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-specification.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-plan.md`
- `docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`

为准。

Phase 0 已完成持久化基线。数据库前向兼容 C-01 已通过 PR #4 合并并复验。
A-01～A-11 合同门禁已解除；A-11 固定 `User.user_public_id` 和
`user:<user_public_id>` actor 合同。Slice 0 权威文档已合并；后续必须按实施计划逐切片
交付，不得越过 Slice 1 直接实施 ORM、Migration、Service 或 API。
Requirement 生命周期仍属于 Phase 1，但作为 Asset Lifecycle Core 之后的独立切片；
该切片完成前不得宣告完整 Phase 1 完成。

完整能力地图和 Excel 只用于长期方向校验，不自动扩大 Phase 1 实施范围。
