# Release Gate

本文档描述当前平台的发布门禁与运行门禁现实，不把“风险评估建议”误写成“自动发布裁决”。

## 当前定位

- 当前门禁链是 `review_state + risk_report + execution_gate + manual decision` 的组合。
- AI 可以给出风险解释和建议，但不能作为最终发布裁判。
- 真正影响是否放行的，是确定性规则与人工确认动作。

## 当前关键对象

### `review_state`

- 表示元素确认、测试点确认、风险确认三类状态。
- 是“确认点链路”的主体。

### `risk_report`

- 来自 `risk-evaluation-agent` 优先，规则兜底。
- 用于提供风险等级、风险分、evidence、gate 建议。

### `execution_gate`

- 是系统最终门禁对象。
- 会综合失败状态、待确认项、低置信度项、风险 gate 结果。

## 当前主链

当前更真实的门禁链路是：

1. 页面分析/测试点/风险结果生成
2. 形成 `review_state`
3. 形成 `risk_report`
4. 通过规则生成 `execution_gate`
5. 允许人工做 override / approve / revoke
6. 动作进入审计历史

主要实现集中在：

- [apps/web-ui-service/app/api/workbench/facade.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/api/workbench/facade.py)
- [apps/web-ui-service/app/core/config.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/core/config.py)

## 当前确定性规则

当前门禁应被视为确定性逻辑优先：

- failed status 可拦截
- risk gate 为 `block` 可拦截
- pending reviews 可触发 `manual_review`
- 缺失关键页面对象/必需元素可触发 block 或 warning

当前人工动作包括：

- 保存 review
- 决策 execution gate
- 二次审批
- revoke 已有人工决策

## 当前人工与 AI 边界

### AI 负责

- 风险解释
- evidence 摘要
- 建议 `allow / manual_review / block`

### 系统规则负责

- 根据配置计算门禁
- 记录 decision source
- 处理审批状态和权限边界

### 人工负责

- 最终放行或拦截决定
- 高风险 override
- 二次审批和撤销

## 当前卡点

1. 门禁逻辑目前主要集中在 `app/api/workbench/facade.py`，仍需继续按域下沉。
2. `execution_gate` 还没有完全抽成独立 service/controller 层。
3. 风险评估虽然已接 Agent 优先，但仍以启发式为主，不是统计预测模型。

## 下一步优先级

### P0

- 保持“AI 建议，人工最终决策”的边界，不要把 pass/fail 或 release 决策外包给模型。

### P1

- 把 execution gate 相关逻辑从大路由中继续拆分。
- 让 audit、review、gate 三块形成更清晰的 service 边界。

### P2

- 再做更细的门禁配置治理和可视化。

## 关键配置

- `EXECUTION_GATE_BLOCK_MISSING_REQUIRED_THRESHOLD`
- `EXECUTION_GATE_BLOCK_ON_FAILED_STATUS`
- `EXECUTION_GATE_BLOCK_ON_RISK_BLOCK`
- `EXECUTION_GATE_WARN_ON_PENDING_REVIEWS`
- `EXECUTION_GATE_WARN_ON_LOW_CONFIDENCE_ELEMENTS`
- `EXECUTION_GATE_WARN_ON_PENDING_TEST_POINTS`
- `EXECUTION_GATE_DUAL_APPROVAL_ENABLED`

配置来源见：

- [apps/web-ui-service/app/core/config.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/core/config.py)

## 推荐阅读

1. [current-architecture-and-flows.md](./current-architecture-and-flows.md)
2. [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
3. [product/url-driven-oneclick-automation-plan-2026-03-20.md](../product/url-driven-oneclick-automation-plan-2026-03-20.md)
