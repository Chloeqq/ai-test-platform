# Architecture

本目录保留平台架构文档和历史架构分析。

当前权威架构口径以 EvieAi 为准：自然语言测试资产是主线，旧 `Candidate / selected_candidates / steps_hint / structurer / generation-time compile` 链路只作为历史兼容和迁移背景。

## 当前优先阅读

1. [EvieAi 文档中心](../evie-ai/README.md)
2. [EvieAi 自然语言测试资产架构](../evie-ai/architecture/natural-language-test-assets.md)
3. [EvieAi 架构总览](../evie-ai/architecture/evie-ai-overview.md)
4. [EvieAi Phase 0 领域模型实施计划](../evie-ai/implementation/phase-0-domain-model.md)

## 可复用专题

- [Agent 设计文档索引](./agents/README.md)
- [Runner 专题评估与实施计划](./runners/README.md)
- [页面对象治理文档](../page-object-governance/README.md)

## 历史归档

旧生成链、旧编译链、旧质量治理接入生成阶段的文档已开始归档到：

- [2026-07 legacy generation archive](../archive/2026-07-legacy-generation/)

归档文档不再作为当前架构事实源。

## 阅读规则

如果文档之间冲突：

1. 先看 `AGENTS.md`。
2. 再看 `docs/evie-ai/**`。
4. 旧链归档文档只用于理解历史，不用于指导新实现。
