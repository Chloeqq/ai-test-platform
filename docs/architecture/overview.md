# Architecture Docs

## 阅读顺序

1. [企业级 AI 自动化测试平台全景架构与缺口补齐（2026-04-06）](./enterprise-ai-test-platform-full-architecture-and-gap-closure-2026-04-06.md)
2. [企业级 AI 测试平台缺口补齐工作包台账（2026-04-06）](./enterprise-ai-platform-gap-closure-work-packages-2026-04-06.md)
3. [当前架构与调用链](./current-architecture-and-flows.md)
4. [项目模块与风险审计（2026-03-21）](./project-inventory-and-risk-audit-2026-03-21.md)
5. [Agent 企业级能力标准](./agent-enterprise-capabilities.md)
6. [Agent 能力建设实施路线图](./agent-implementation-roadmap.md)
7. [URL 驱动一键全自动落地改造方案](../product/url-driven-oneclick-automation-plan-2026-03-20.md)

## 当前口径

- 当前仓库更准确的描述是“确定性底座 + AI 辅助 + 人工门禁”的混合自动化平台。
- `PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1 / PageAnalysisBundleV1`、页面分析规则、`review_state`、`execution_gate`、`evidence_manifest` 是当前最值得优先理解的现实能力。
- `data-generation-agent` 已完成最小可用确定性服务，但还不能按“企业级治理已完成”来阅读。
- 如果文档描述与代码实现有冲突，优先相信当前架构审计与当前调用链文档。
