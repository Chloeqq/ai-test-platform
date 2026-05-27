# Architecture

这一组文档描述“当前真实架构”和“未来目标架构”两层内容。

## 阅读顺序

1. [overview.md](./overview.md)
2. [current-architecture-and-flows.md](./current-architecture-and-flows.md)
3. [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
4. [project-structure.md](./project-structure.md)
5. [ai-orchestrator.md](./ai-orchestrator.md)
6. [runners.md](./runners.md)
7. [evidence-pipeline.md](./evidence-pipeline.md)
8. [release-gate.md](./release-gate.md)
9. [agent-enterprise-capabilities.md](./agent-enterprise-capabilities.md)
10. [agent-implementation-roadmap.md](./agent-implementation-roadmap.md)
11. [agents/README.md](./agents/README.md)

## 分层说明

### 当前事实层

- `current-architecture-and-flows.md`
- `project-inventory-and-risk-audit-2026-03-21.md`
- `overview.md`

### 能力与路线层

- `agent-enterprise-capabilities.md`
- `agent-implementation-roadmap.md`

### 子系统说明层

- `ai-orchestrator.md`
- `evidence-pipeline.md`
- `release-gate.md`
- `runners.md`
- `project-structure.md`

### 方案与蓝图层

- `web-ui-enterprise-er-api-design.md`

### Agent 设计层

- `agents/README.md`
- `agents/01-requirement-parser-agent-design.md`
- `agents/02-test-design-agent-design.md`
- `agents/03-script-generation-agent-design.md`
- `agents/04-execution-planner-agent-design.md`
- `agents/05-failure-analysis-agent-design.md`
- `agents/06-risk-evaluation-agent-design.md`
- `agents/07-failure-triage-agent-design.md`
- `agents/08-self-healing-advisor-agent-design.md`
- `agents/09-data-generation-agent-design.md`

### 历史快照与进度记录

- [../history/p0-a-contract-standardization-progress-2026-03-20.md](../history/p0-a-contract-standardization-progress-2026-03-20.md)
- [../history/requirement-parser-capability-progress-2026-03-20.md](../history/requirement-parser-capability-progress-2026-03-20.md)
- [../history/rollback-audit-2026-03-19.md](../history/rollback-audit-2026-03-19.md)

## 当前口径

- 这套目录里，`current-architecture-and-flows.md` 和 `project-inventory-and-risk-audit-2026-03-21.md` 优先作为当前事实来源。
- `agents/` 下的设计文档是目标设计，不等于所有能力都已落地。
- `agent-enterprise-capabilities.md` 是企业级目标标准，不等于当前仓库已经满足这些 SLA/指标。
- `agent-implementation-roadmap.md` 是建设路线图，不是实时进度看板；当前状态仍应优先看审计文档和当前调用链文档。
- `web-ui-enterprise-er-api-design.md` 更接近平台化数据底座蓝图与历史设计快照，不是当前 runtime 真相。
- `legacy_workbench.py` 的拆分与收口现状，优先参考 `docs/implementation-plan/` 下的：
  - `2026-03-29-legacy-workbench-route-map.md`
  - `2026-03-31-legacy-workbench-responsibility-inventory.md`
  - `README.md`
- `data-generation-agent` 已完成最小可用确定性服务，但企业级治理闭环仍需继续增强。
- 如果设计和实现冲突，先信任当前架构审计与调用链文档。
