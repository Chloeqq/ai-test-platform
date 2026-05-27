# AI 编排层 Agent 联动与一键全自动方案（2026-03-19）

## 1. 当前真实实现状态（基于代码扫描）

### 1.1 八个专业化 Agent 现状（2026-03-20 更新）

| Agent | 当前状态 | 证据位置 | 结论 |
|---|---|---|---|
| 需求解析 Agent（Requirement Parser） | 已实现 RequirementSpecV1 生成并接入 `/requirements/parse`、`/orchestrate` | `agents/requirement-parser-agent/src/*`、`apps/ai-orchestrator/src/orchestrator_service.py` | 已实现（MVP） |
| 测试设计 Agent（Test Design） | 可执行；支持 requirement/test points -> YAML（当前仍偏 smoke） | `agents/test-design-agent/src/agent.py`、`agents/test-design-agent/src/test_points.py` | 已实现（MVP） |
| 脚本生成 Agent（Script Generation） | 已实现 GeneratedScriptV1 生成、脚本落盘并接入接口 | `agents/script-generation-agent/src/*`、`reports/executions/generated-scripts/` | 已实现（MVP） |
| 执行规划 Agent（Execution Planner） | 已实现 ExecutionPlanV1，支持阶段、重试、并发、调度提示 | `agents/execution-planner-agent/src/*`、`POST /execution/plan` | 已实现（MVP） |
| 风险评估 Agent（Risk Evaluation） | 已实现 RiskReportV1，支持评分、门禁结论、建议 | `agents/risk-evaluation-agent/src/*`、`POST /risk/evaluate` | 已实现（MVP） |
| 失败归因 Agent（Failure Analysis） | 可执行；LLM+规则双路径；可输出分类/风险/建议 | `agents/failure-analysis-agent/analyze.py` | 已实现（MVP） |
| 失败分类 Agent（Failure Triage） | 已实现 FailureTriageV1，支持分级/归队/责任团队建议，并带历史聚类字段（cluster_id/occurrence_count/similar_cases） | `agents/failure-triage-agent/src/*`、`POST /failures/triage` | 已实现（MVP+） |
| 自愈建议 Agent（Self-Healing Advisor） | 建议、patch preview/apply/rollback、自动重跑流程可用 | `agents/self-healing-advisor-agent/*` | 已实现（MVP） |

### 1.2 其他相关 Agent 现状

| Agent | 当前状态 | 结论 |
|---|---|---|
| Data Generation / Coverage Optimizer | 仍未落地独立 Agent | 未实现（骨架） |
| 统一编排顺序 | 已在 orchestrator 固化为 8 段顺序并回传到 report | 已实现（MVP） |

### 1.3 当前主链路真实能力

当前可跑通主链路接近：

`需求文本 -> 需求解析 -> 测试设计生成 YAML -> 脚本生成 -> 执行规划 -> 执行 -> 风险评估 -> 失败归因 -> 自愈建议/回滚`

当前缺口在于：

- 多输入源（OpenAPI/Git Diff/缺陷单/日志）尚未形成统一生产级入口
- 脚本生成仍以 Playwright + Python 为主，跨语言/跨 Runner 不完整
- 仍有部分空骨架目录，会造成“看起来有，实际不可用”的认知偏差

补充说明（2026-03-20）：

- 风险评估 Agent 已接入 failure triage 信号（severity/manual_review）参与评分。
- orchestrator 报告已包含 `Failure Triage` 分区和聚类字段，支持后续失败聚类看板对接。
- 新增失败聚类查询 API：
  - `GET /failures/clusters?limit=200&max_clusters=20`
  - `GET /failures/clusters/{cluster_id}`
  - 支持筛选：`queue`、`failure_class`、`severity`
- Web UI 已接入“失败聚类”页面：
  - 页面路径：`/quality/clusters`
  - 功能：聚类筛选（队列/故障类/严重级别）、聚类详情、按聚类一键创建缺陷关联（`POST /api/defects`）

---

## 2. 为什么目前还达不到“一键全自动企业级”

1. Agent 编排还不是“完整流水线编排”，更像“单点调用 + 补丁式扩展”。
2. 契约未完全统一为版本化模型（虽已有 `test_points/execution_record/evidence_manifest` 雏形，但未形成统一 schema 包与严格校验闭环）。
3. 多输入源虽在路线图里，但尚未作为统一入口接入并稳定落地。
4. 风险评估与门禁决策链路未打通，无法形成“自动执行 -> 风险结论 -> 发布建议”的企业闭环。

---

## 3. 目标架构（一键全自动）

目标流水线：

`输入源接入 -> 需求解析 Agent -> 测试设计 Agent -> 脚本生成 Agent -> 执行调度 -> Runner 执行 -> 失败归因 Agent -> 风险评估 Agent -> 自愈 Agent -> 报告/门禁`

当前 orchestrator 固定编排顺序（与产品要求一致）：

1. 需求解析（`requirement-parser-agent`）
2. 测试设计（`test-design-agent`）
3. 脚本生成（`script-generation-agent`）
4. 执行规划（`execution-planner-agent`）
5. 风险评估（`risk-evaluation-agent`）
6. 失败归因（`failure-analysis-agent`）
7. 失败分类（`failure-triage-agent`，当前占位）
8. 自愈建议（`self-healing-advisor-agent`）

建议统一数据契约（版本化）：

- `RequirementSpecV1`
- `TestPointPlanV1`
- `TestCaseBundleV1`
- `ExecutionRecordV1`
- `EvidenceManifestV1`
- `FailureInsightV1`
- `RiskReportV1`
- `HealingPlanV1`

---

## 4. 五个核心 Agent 功能规划（企业级）

## 4.1 需求解析 Agent（P0）

必须能力：

- 多源输入：PRD/OpenAPI/Git Diff/缺陷单/日志
- 实体抽取：页面、对象、动作、约束
- 测试点提取：功能/异常/边界/权限/兼容
- 输出标准：`RequirementSpecV1`（含优先级、依赖、覆盖标签）

落地建议：

- 先实现 OpenAPI + 纯文本 PRD 两个入口（最快产生价值）
- Git Diff、缺陷单、日志作为第二批接入

## 4.2 测试设计 Agent（P0）

必须能力：

- 输入 `RequirementSpecV1`，输出 `TestPointPlanV1`
- 风险优先级打标（P0/P1/P2）
- 覆盖矩阵字段（requirement_id -> test_point_ids）

当前已做可复用：

- `test-design-agent` 中步骤级 test points 反推能力
- 稳定 baseline 约束能力（减少漂移）

## 4.3 脚本生成 Agent（P0/P1）

必须能力：

- 输入 `TestPointPlanV1`，输出 `TestCaseBundleV1`
- P0 先支持 `Playwright + Python`
- P1 再扩展 `Java/JS` 与 API/Mobile 框架

关键策略：

- 严格复用 Page Object，不允许临时硬编码 selector
- 统一代码模板和 lint 规则，保证可维护性

## 4.4 失败归因 Agent（P0）

当前状态：

- 已具备分类、风险、建议基础能力

增强方向：

- 从单用例归因升级到批量聚类（同类失败合并）
- 引入证据权重与置信度解释（可审计）

## 4.5 风险评估 Agent（P1）

必须能力：

- 输入执行结果、失败聚类、历史 flaky、变更范围
- 输出 `RiskReportV1`（风险分、风险级别、发布建议）
- 对接门禁策略（阻断/放行/人工审批）

---

## 5. 6 周落地排期（快速可执行）

## 第 1-2 周（P0-A，契约收口）

- 建立 `apps/shared_backend`（或同等共享模块）并落地上述 V1 schema
- orchestrator/web-ui/runner 全链路 schema 校验
- 将目录扫描降级为兼容路径，主路径改为 `execution_record + evidence_manifest`

验收：

- 所有关键接口返回均含 schema version
- schema 校验失败时返回标准错误码

## 第 2-3 周（P0-B，补齐核心 Agent）

- 实现 Requirement Parser（至少 PRD/OpenAPI）
- 重构 Test Design 输入为 `RequirementSpecV1`
- 新建 Script Generation Agent（先 Playwright Python）
- 串接 orchestrator：`parser -> design -> script -> execute`

验收：

- 单次 API 可从 requirement 自动得到 test points 与可执行 YAML
- 生成内容与页面对象一致性 > 90%（抽样）

## 第 4-5 周（P1，多输入与风险）

- 接入 Git Diff/缺陷单/日志输入
- 实现 Risk Evaluation Agent（可输出门禁结论）
- 增加失败聚类与趋势分析最小版

验收：

- 可给出自动门禁建议（allow/block/manual）
- 可生成模块级风险榜单

## 第 6 周（稳定化）

- 压测、回归、观测（trace_id、agent latency、失败重试）
- 完成“人工兜底策略”和“自动化失败降级策略”

---

## 6. 一键全自动 API 设计建议

新增统一入口（示例）：

`POST /api/v1/auto-test/oneclick`

请求：

- `project_id`
- `input_sources`（文本、openapi_url、git_diff、defect_ids、log_range）
- `execution_config`（env、browser、parallelism、retry）
- `governance`（auto_heal、gate_policy）

响应（同步提交 + 异步执行）：

- `workflow_id`
- `status`（queued/running/completed/failed）
- `links`（test_points、case_bundle、execution_record、report）

---

## 7. 你当前最该优先做的三件事（建议顺序）

1. 先补 Requirement Parser Agent（至少文本+OpenAPI）
2. 把 Script Generation Agent 真正落地（先单框架 Playwright Python）
3. 实现 Risk Evaluation Agent 最小可用版（打通门禁闭环）

理由：

- 这三项补齐后，才是“从需求输入到发布建议”的完整自动化闭环。
- 否则只能算“可执行工具链”，还不是“企业级测试平台”。

---

## 8. 风险与治理建议

- 所有 Agent 输出必须有 `trace_id`、`schema_version`、`confidence`。
- 自动修复默认灰度开启：先建议、后审批、再自动。
- 低置信度场景强制人工复核，避免误修复。
- 保留人工覆写入口，确保平台在复杂业务下可控。
