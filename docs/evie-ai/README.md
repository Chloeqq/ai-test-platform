# EvieAi 文档中心

本目录是 EvieAi 的权威文档入口。

EvieAi 的核心口径：

- 测试资产以自然语言 `TestAsset` 为中心。
- AI 生成阶段只产生自然语言测试资产，不产生 `action / target / value`。
- `Candidate`、`selected_candidates`、保存所选候选、生成阶段结构化、生成阶段提前编译，均属于旧架构。
- 只有用户触发 Asset-to-Case 后，才进入资源绑定、质量门、Compiler 和 Runner。
- 执行代码唯一事实源是 `TestCaseVersion.script_code`。

## 当前事实源

1. [EvieAi 自然语言测试资产架构](./architecture/natural-language-test-assets.md)
2. [EvieAi 架构总览](./architecture/evie-ai-overview.md)
3. [EvieAi 目标能力地图](./architecture/target-capability-map.md)
4. [EvieAi Phase 0 领域模型实施计划](./implementation/phase-0-domain-model.md)
5. [EvieAi 阶段追踪矩阵](./implementation/phase-traceability.md)
6. [EvieAi 文档清理计划](./migration/docs-cleanup-plan.md)
7. [旧链冻结清单](./migration/legacy-chain-freeze-list.md)

## 本地参考资料

- [参考资料说明](./reference/README.md)
- [EvieAi_架构分层功能清单 Excel](reference/EvieAi_架构分层功能清单_完整实施版.xlsx)
- [EvieAi 架构 Mermaid 图](./reference/2026-07-12_evie-ai-architecture-flow.mmd)

Excel 和架构图定义完整目标空间，不自动扩大当前阶段实施范围。当前阶段具体建设内容以 `implementation/` 下对应阶段文档为准。

## 历史旧链归档

旧生成链相关文档已开始归档到：

- [2026-07 legacy generation archive](../archive/2026-07-legacy-generation/)

归档不等于删除。归档文档只作为历史证据，不再作为当前架构事实源。

## 命名规则

| 类型 | 命名 |
|---|---|
| 产品名 / 文档标题 | `EvieAi` |
| 文档目录 / Git scope | `evie-ai` |
| Python 包目录 | `evie_ai` |
| 数据库表 | `requirements`, `requirement_versions`, `test_assets`, `test_asset_versions`, `test_asset_sources` |
| 领域类 | `Requirement`, `RequirementVersion`, `TestAsset`, `TestAssetVersion`, `TestAssetSource` |

不得同时保留旧产品命名目录作为权威文档路径。
