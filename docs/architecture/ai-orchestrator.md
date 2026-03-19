# AI Orchestrator

本文档描述当前仓库里 `apps/ai-orchestrator/` 的真实职责、边界、卡点和下一步优先级。

## 当前定位

- 当前实现是一个以 Flask 为主的编排 API 服务，不是“全自治的 Agent 操作系统”。
- 它的职责更接近：统一接入多 Agent 能力、输出规范化契约、承接执行前后治理数据。
- 当前最重要的价值不是“AI 很聪明”，而是把 `RequirementSpec / GeneratedScript / ExecutionPlan / RiskReport / FailureTriage` 这些输出收口成稳定 API。

## 当前模块职责

### 入口与协议

- `apps/ai-orchestrator/src/app.py`
  - 暴露当前主入口。
  - 已提供 `/orchestrate`、`/requirements/parse`、`/scripts/generate`、`/execution/plan`、`/risk/evaluate`、`/failures/triage`、`/healing/preview` 等接口。
- `apps/ai-orchestrator/openapi/orchestrator-openapi.yaml`
  - 对外契约入口。

### 编排核心

- `apps/ai-orchestrator/src/orchestrator_service.py`
  - 当前最关键的业务实现。
  - 负责 requirement 解析、脚本生成、执行计划、风险评估、失败分诊、自愈预览的统一编排。
  - 负责 `execution_record` 和 `evidence_manifest` 的归一化与透传。

### 资产与兼容能力

- `apps/ai-orchestrator/src/asset_service.py`
  - 提供 Page Object、脚手架模板等资产侧接口。
- `apps/ai-orchestrator/src/tools/`、`src/prompts/`、`src/policies/`
  - 当前更适合作为 prompt/tool/policy 资源目录理解。
  - 不应被误读为每个子目录都已经形成完整的企业级运行子系统。

## 当前主链

当前更可信的 orchestrator 调用链是：

1. Web UI 或手工请求进入 `app.py`
2. `orchestrator_service.py` 做输入归一化与 Agent/规则编排
3. 产出 schema 化结果
4. 对执行结果补 `execution_record` / `evidence_manifest`
5. 把风险评估、失败分诊、自愈建议回传给 Web UI 或报告层

## 确定性与 AI 边界

### 确定性职责

- API 契约与输入校验
- 输出 envelope 结构
- `execution_record` / `evidence_manifest` 规范化
- 运行结果状态透传
- 失败时 fallback 和降级处理

### AI 辅助职责

- requirement 语义解析
- 测试点与脚本生成建议
- 风险解释与发布建议
- 失败归因解释
- 自愈建议生成

## 当前卡点

1. `orchestrator_service.py` 仍然过重，承担了过多编排、归一化、fallback 和报告拼装职责。
2. 很多 `src/controllers/`、`src/services/`、`src/workflows/` 路径更接近目标拆分，不应等同于当前主链事实。
3. 任务调度层还不是真正的队列中心，更多是同步/单次编排。
4. AI 输出虽已逐步契约化，但跨 Agent 的真实可观测性和质量追踪仍不足。

## 下一步优先级

### P0

- 把 orchestrator 继续当“契约与编排层”而不是“万能业务层”收口。
- 优先稳固 `requirements -> test points -> script -> execution plan -> risk/triage` 这条主链契约。

### P1

- 继续拆轻 `orchestrator_service.py`，把 execution record、risk、triage、report 组装逻辑分层。
- 强化与 `apps/shared_backend/schemas/contracts.py` 的单一事实源关系。

### P2

- 再考虑更完整的 workflow/controller/service 分层落地。
- 再考虑更复杂的异步队列和多 Runner 统一调度。

## 阅读顺序

如果要理解这块，建议按下面顺序看：

1. [current-architecture-and-flows.md](./current-architecture-and-flows.md)
2. [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
3. [apps/ai-orchestrator/src/app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/app.py)
4. [apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
