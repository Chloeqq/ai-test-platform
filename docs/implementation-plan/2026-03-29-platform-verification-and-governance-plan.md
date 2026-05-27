# 2026-03-29 平台核查与治理推进方案

## 1. 结论摘要

基于对 `/Users/bettyhuang/PycharmProjects/ai-test-platform` 当前代码、测试与运行链路的实际核查，可以得到以下结论：

- 当前项目的主链路已经真实存在：`输入 -> requirement parse -> test points -> YAML/case -> pytest/playwright 执行 -> evidence/report -> review/gate`
- 用户给出的功能盘点整体方向基本正确，但其中有几项需要从“完全属实”修正为“部分属实”
- 当前最大的工程性风险不再是“主链路缺失”，而是：
  - 路由文件过重
  - schema/tool 治理不闭环
  - 多输入源实现深度不足
  - 平台级分析能力仍偏启发式

本轮额外确认到一个重要事实：

- `pytest` 全量已恢复通过：`182 passed, 1 skipped`

## 2. 核查结果修正

### 2.1 属实

- `legacy_workbench.py` 体量与职责严重集中
- failure source / failure analysis 仍偏规则启发式，可信度解释不够强
- `data-generation-agent` 当前仍是 MVP
- 自愈能力存在，但默认仍应视为“受控能力”，不适合直接大规模自动开启

### 2.2 部分属实

- 多输入源接入不足  
  当前接口层已经能接收 `openapi_spec / prd_text / git_diff / runtime_logs / defect_ticket`，但 orchestrator 侧工具文件仍未闭环，接入深度不足。

- 页面语义驱动不足  
  页面分析与 `PageSurfaceV1 / PageSemanticModel / TestPointPlanV1` 已存在，但生成主链仍主要由 requirement 驱动，页面语义尚未成为主导输入。

- 跨 case/run 分析缺失  
  失败聚类、flaky、trend 页面和接口已经有雏形，但更偏启发式报表，不是成熟的数据分析中心。

- 报告治理视图不足  
  报告拆页与 dashboard 已有基础，但经理/治理视角的跨 run 指标仍然不够完整。

### 2.3 需要修正表述

- “缺少结构化测试点中间层”  
  更准确的说法应为：
  “结构化测试点中间层已经存在，但 orchestrator 的 schema/tool/traceability 治理未完全闭环。”

## 3. 当前关键事实

### 3.1 已确认存在的能力

- 共享契约层：`PageSurfaceV1 / TestPointPlanV1 / ExecutionRecordV1 / EvidenceManifestV1`
- web-ui-service 主展示层与治理层
- ai-orchestrator 主编排层
- web-playwright-python Runner
- review_state / execution_gate / failure_source calibration 状态链路
- failure cluster / flaky / trend 的基础查询能力
- self-healing preview / apply / rollback / rerun 控制链路

### 3.2 已确认存在的结构性问题

- `apps/web-ui-service/app/routers/legacy_workbench.py` 仍然过大
- `apps/ai-orchestrator/src/schemas/test-point.schema.py` 为空文件
- `apps/ai-orchestrator/src/tools/openapi-parser.tool.py` 为空文件
- `apps/ai-orchestrator/src/tools/git-diff.tool.py` 为空文件
- `apps/ai-orchestrator/src/tools/jira-reader.tool.py` 为空文件

## 4. 建议优先级

### P0：先做闭环稳定性

目标：让现有主链路更可维护、更可验证，而不是继续堆功能入口。

任务：

- 完成 `legacy_workbench.py` 的 router/service 彻底拆层
- 补齐 orchestrator 侧 test-point schema
- 补齐多输入源 tool 的最小可用实现
- 明确 requirement quality gate 与 fallback 行为边界

验收标准：

- `legacy_workbench.py` 只保留路由与兼容壳
- test point schema 在 orchestrator 内部有统一定义和单测
- openapi/git diff/jira 至少 2 项具备真实可运行实现
- quality gate 在真实 parser 与 fallback parser 下都有稳定单测

### P1：增强治理可信度

目标：让治理链路从“有界面/有状态”升级到“有解释/可复核/可追踪”。

任务：

- failure source 置信度依据输出标准化
- 网络证据结构化，补齐 evidence manifest 消费面
- review/gate 历史按 run/page/case 建立统一审计视图
- self-healing 增加策略级别、审批边界和追踪字段

验收标准：

- failure source 输出包含 evidence basis
- report/risk/review 页面能回显结构化证据摘要
- 自动修复链路可以区分 preview-only / manual-apply / controlled-auto

### P2：推进平台级洞察

目标：从单 case 执行平台升级为 run/project 级分析平台。

任务：

- flaky 识别口径统一
- cluster 与风险排序统一到同一数据模型
- dashboard 增加项目级趋势和管理 KPI
- 成功执行路径与稳定路径统计沉淀

验收标准：

- 同一条失败在 cluster、dashboard、history 中口径一致
- dashboard 能展示 run/project 级趋势
- flaky/环境问题/应用问题区分规则明确

## 5. legacy_workbench 拆层建议

建议按以下顺序推进，避免一次性重构过大：

### 阶段 1：冻结边界

- 不再往 `legacy_workbench.py` 新增新逻辑
- 新增能力只允许落到 `app/services/*`
- router 内只保留参数解析、鉴权、响应组装

### 阶段 2：按领域迁移

- `generate / preview / save` 迁到 `workbench_asset_service`
- `review / audit` 迁到 `workbench_review_service`
- `execution gate` 迁到 `workbench_gate_service`
- `runtime run / rerun / heal` 迁到 `workbench_runtime_service`
- `history / trend / summary` 迁到 `workbench_history_service`
- `page analysis / risk context` 迁到 `workbench_analysis_service`

### 阶段 3：精简 legacy router

- legacy router 只保留兼容入口
- helper 全部从 router 中删除
- 对外 URL 与返回结构保持不变

### 阶段 4：补测试

- 每个 service 至少补单测
- legacy router 只保留接口兼容测试
- 新行为只能通过 service 测试进入回归集

## 6. 建议的两周执行节奏

### 第 1 周

- D1-D2：梳理 `legacy_workbench.py` 路由到 service 的映射表
- D2-D3：补齐 `test-point.schema.py`
- D3-D4：实现 `openapi-parser.tool.py` 最小版
- D4-D5：实现 `git-diff.tool.py` 最小版，并补集成测试

### 第 2 周

- D1-D2：failure source 输出补 evidence basis
- D2-D3：evidence manifest 消费统一到 report/risk
- D3-D4：拆掉 `legacy_workbench.py` 中剩余运行态聚合逻辑
- D5：回归、补文档、冻结接口契约

## 7. 本轮建议的直接下一步

最推荐的落地顺序：

1. 先做 `legacy_workbench.py` 路由映射清单
2. 再补 orchestrator 空 schema/tool 文件
3. 然后收敛 failure source 与 evidence manifest 的解释链路

这样做的原因是：

- 先拆边界，后补能力，返工最少
- 先补 schema/tool，后做平台分析，数据基础更稳
- 先提升可信度，再扩治理范围，产出更可落地

## 8. 2026-04-02 进展更新

本轮已经开始把“真正的平台治理能力”落到现有 dashboard，而不是停留在拆层和盘点上。

### 已完成

- 新增治理总览接口：`GET /api/dashboard/governance`
- 新增治理聚合 service：[workbench_governance_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/workbench_governance_service.py)
- 已接入 3 条现有治理信号源：
  - quality gate 24h 摘要与阻断趋势
  - execution task governance risk 摘要
  - failure clusters 热点聚合
- 已在 dashboard 页面补充管理视角区块：
  - 高风险治理任务
  - 缺失 Manifest 任务
  - 失败聚类数
  - 需人工复核聚类
  - 治理行动建议
  - Top 治理风险任务
- 已继续补充趋势治理能力：
  - `trend_14d`
  - `trend_summary_7d`
  - 14 天治理趋势图
  - 7 天治理摘要卡片
- 已补齐接口与页面骨架测试，并完成治理页相关回归：
  - `web-ui-service: 134 passed`

### 新的阶段判断

- “平台治理能力”已经不再只是规划项，现已具备第一版管理视角总览入口
- dashboard 已开始具备 run/project 级治理趋势视角，而不再只是单点摘要
- 下一阶段不应回到继续机械拆 legacy，而应继续推进：
  - 治理指标统一口径
  - 趋势与聚类的跨 run/project 洞察
  - orchestrator schema/tool 闭环

### 本轮补充完成

- `web-ui-service` 已完成弃用 warning 清理，测试 warning 降为 0
- ai-orchestrator 的空 schema/tool 文件已补齐最小实现，并接入 fallback 主链
- dashboard 治理 KPI 卡片与治理趋势摘要卡片已升级为可点击入口
- 已新增人工验收清单：
  - [2026-04-02-governance-acceptance-checklist.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-02-governance-acceptance-checklist.md)
- ai-orchestrator 已新增自有 ASGI 适配层：
  - [wsgi_asgi.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/wsgi_asgi.py)
- 当前全仓最新结果为：
  - `189 passed, 1 skipped`
