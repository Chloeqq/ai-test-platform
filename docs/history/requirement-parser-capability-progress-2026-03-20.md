# Requirement Parser 能力进度（2026-03-20）

## 当前目标
将需求解析链路从“文本直出 YAML”升级为“多源输入 -> 结构化测试点 -> 可追溯输出”。

## 本次已完成
- 多源输入适配（P0）
  - 支持：`requirement`、`input_sources`、`prd_text`、`user_story`、`openapi_spec`、`git_diff`、`defect_ticket`、`runtime_logs`
  - 支持 source type 别名归一化（`swagger -> openapi`、`gitdiff -> git_diff` 等）
- NLP 实体识别（P0）
  - 提取页面、字段、动作、UI 元素、API 路径、URL、变更文件
- 测试点提取（P0）
  - 按 source type 分流解析，避免将 `git diff` 元信息误拆为测试点
  - 输出测试点类型：`functional / api / negative / performance / security / compatibility / regression`
- 优先级判定（P0）
  - 综合高风险关键词、缺陷严重度、变更规模、source 类型信号
- 依赖分析（P0）
  - 自动构建 `dependencies` 与 `dependency_graph`
- 覆盖矩阵（P1）
  - `coverage_matrix` 支持按 `source_id` 追踪，并保留 `traceability_status`
- 变更影响分析（P1）
  - 输出 `changed_areas`、`impact_score`、`affected_intent_ids`
- 需求消歧（P1）
  - 识别模糊词、性能指标缺失、强制/可选冲突、缺失预期结果
- 业务规则提取（P1）
  - 提取 must/range/permission/risk 规则并去重
- 历史学习（P1）
  - 基于历史 report 聚合失败模式，并补充历史执行模式分布

## 兼容性与接口
- `apps/ai-orchestrator/src/orchestrator_service.py`
  - `parse_requirement` 支持 `page` 为空并自动推断页面
- `apps/ai-orchestrator/src/orchestrator_service.py`
  - `orchestrate` 主入口已支持多源输入参数透传（`input_sources/openapi_spec/prd_text/user_story/git_diff/defect_ticket/runtime_logs`）
  - 支持 `requirement/page` 为空时由解析结果自动推断并继续编排
- `POST /requirements/parse`（orchestrator + web-ui compat）
  - 返回 `RequirementSpecV1`，包含 `source_inputs / test_intents / coverage_matrix / dependency_graph / business_rules / ambiguities / change_impact / historical_patterns`
  - 新增 `quality_gate`（`RequirementQualityGateV1`）：输出解析质量指标、阈值与 `allow/block` 决策（parse 阶段仅提示，不阻断）
- `POST /orchestrate`（orchestrator + web-ui compat）
  - 已可直接走“多源输入 -> 测试点 -> YAML 用例（generate_only 模式）”
  - 新增生成前质量门禁：当 `REQUIREMENT_QUALITY_GATE_ENABLED=true` 且命中阻断条件时，返回 `validation_error`，避免低质量需求继续生成不可靠用例
  - 质量门禁 `blockers` 已标准化为结构化对象：`code/category/severity/alert_code/metric_key/value/threshold`
  - 已内置稳定 blocker code（如 `low_parse_confidence`、`insufficient_test_intents`），可直接用于告警聚合与治理看板统计
- Web UI 生成页 `/workbench/generate`
  - 已新增多输入源表单（PRD/用户故事/OpenAPI/Git Diff/缺陷单/运行日志/附加 JSON）
  - 支持本地 JSON 文件导入：可识别 OpenAPI JSON / Postman Collection / `input_sources` 数组
  - `生成用例` 与 `一键自动生成并执行` 两条入口均可携带多输入源字段
  - 已新增“预览测试点”能力：先看 `test_intents/coverage/ambiguities`，再决定是否生成
  - 已新增 `quality_gate` 透出：预览与生成成功响应均返回质量门禁信息（decision/metrics/blockers）
  - 已收口门禁阻断语义：当 orchestrator 返回质量门禁 `block` 时，Web UI 不再静默 fallback 生成，而是直接返回阻断详情给前端展示
  - 新增质量门禁聚合接口：`GET /api/workbench/quality-gates/summary`，可输出拦截率、`alert_code` Top 分布与最近阻断事件
  - 失败聚类页已接入质量门禁看板，支持在同一页面查看 failure cluster 与 requirement quality gate 风险
  - 支持 `alert_code -> 样本 + 修复建议` 联动：点击告警码可查看对应阻断样本，并一键跳转到失败样本页面（按 `case_id`）
  - 仪表盘已接入 quality gate 24h 卡片：展示门禁事件数、拦截率、Top 告警码与小时级趋势
  - 仪表盘 Top 告警码支持深链跳转：`/quality/clusters?alert_code=...`，进入后自动选中对应告警并展示明细
  - 质量门禁汇总接口与页面支持双维过滤：`alert_code + page`（如 `.../quality-gates/summary?alert_code=REQQG_CONFIDENCE_LOW&page=product`）
- OpenAPI 契约补齐
  - `apps/ai-orchestrator/openapi/orchestrator-openapi.yaml` 已补 `POST /requirements/parse`
  - 已新增 `ParseRequirementRequest/Response`、`RequirementSpecV1`、`RequirementQualityGateV1` 等 schema，便于前后端按同一契约演进
- 稳定性增强
  - orchestrator 在测试设计阶段出现 YAML 解析异常时不再直接 500，自动降级为 fallback 可执行用例，保证主链不中断
  - orchestrator 输出 `design_generation` 元数据（`fallback_used/fallback_reason`）
  - web-ui `/api/workbench/generate` 已透出 `orchestrator_design_fallback_used`，前端生成页可直接提示“设计兜底”

## 质量门槛（已验证）
- 自动化测试：
  - `apps/ai-orchestrator/tests/integration/test_requirement_parser_multisource.py`
  - `apps/ai-orchestrator/tests/integration/test_orchestrator_service_asset_flow.py`（新增 design fallback 元数据断言）
  - `apps/ai-orchestrator/tests/integration/test_openapi_contract.py`（新增 `/requirements/parse` 与 requirement schema 契约断言）
  - `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py`（新增 preview/generate/auto-run 多输入源契约测试）
  - 回归通过：`67 passed`（`make test-orchestrator` 62 + `web-ui-service` 5）
- 手工验收：
  - 复杂多源 payload 下，`git diff` 噪声标题（`+++`、`@@`）已消除
  - `change_impact` 已输出 `impact_score` 与 `changed_areas`

## 仍需优化（下一阶段）
- 引入更强中文语义模型（当前为规则+启发式）
- 覆盖矩阵增加“未覆盖测试点”反向索引
- 历史学习接入向量检索与相似需求召回
- 将多源输入与队列化执行模型打通（execution_record/evidence_manifest 一致化）
