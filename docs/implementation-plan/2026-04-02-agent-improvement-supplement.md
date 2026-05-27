# 2026-04-02 Agent 模块待完善清单补充项

## 背景

本清单用于吸收 `docs/architecture/agents-analysis.md` 中仍然有参考价值、且适合纳入当前平台待完善事项的部分。

说明：

- 不修改原始分析文档口径
- 只提炼“当前仍值得继续做”的事项
- 不再重复纳入已经完成或已经过时的判断

---

## 当前判断

截至 2026-04-02，Agent 层的准确状态应定义为：

- 主链能力：已可用
- orchestrator 接入：已稳定
- Agent 统一抽象：未完全统一
- Agent 内部复杂度：仍存在热点
- Agent 层测试与配置治理：仍需增强

这意味着后续对 Agent 模块的投入，不再是“从 0 到 1 补能力”，而是：

1. 收敛复杂度热点
2. 统一跨 Agent 基础设施
3. 提升可维护性与可验证性

---

## 建议纳入当前待完善清单的事项

### A1. 拆分 requirement-parser-agent 内部职责

优先级：`P1`

现状：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/requirement-parser-agent/src/agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/requirement-parser-agent/src/agent.py) 当前约 `1584` 行
- 已承担：
  - 多源输入归一
  - requirement parsing
  - intent 提取
  - business rule / ambiguity / dependency / coverage 组装

问题：

- 该 Agent 已成为 Agent 层最明显的复杂度热点之一
- 当前虽然可用，但后续继续叠加多源规则、traceability、explainability 时，维护成本会持续上升

建议动作：

1. 将 source normalization、intent extraction、coverage/dependency assembly 拆为内部独立模块
2. 明确 parser runtime / fallback / explainability 的边界
3. 将规则集与结果整形进一步从主 agent 文件中抽离

验收标准：

- `agent.py` 明显收缩
- 关键输出 contract 不变
- 多源解析相关回归不退化

---

### A2. 拆分 test-design-agent 内部职责

优先级：`P1`

现状：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/test-design-agent/src/agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/test-design-agent/src/agent.py) 当前约 `1289` 行
- 已承担：
  - test case generation
  - test point generation
  - traceability 组装
  - quality / warning / review 建议

问题：

- 该 Agent 是 Agent 层第二个明显的复杂度热点
- 它直接影响 `test point -> case -> execution plan` 主链质量

建议动作：

1. 将 test point generation、traceability assembly、quality heuristics 拆开
2. 强化与 `TestPointPlanV1`、CoverageMatrix 的边界映射
3. 将 warning / fallback / confidence 逻辑单独收敛

验收标准：

- 设计链输出结构保持兼容
- traceability 与 test point 质量判断更容易单测
- `agent.py` 继续减重

---

### A3. 统一 Agent 配置、fallback、日志与错误契约

优先级：`P1`

现状：

- 9 个 Agent 已可被 orchestrator 稳定调用
- 但配置读取、fallback 标记、错误输出、日志字段仍偏分散

问题：

- 后续维护时容易出现“同一类失败，不同 Agent 表现不一致”
- 不利于平台级 observability 与统一排障

建议动作：

1. 定义 Agent 级统一配置入口
2. 统一 fallback / degraded / partial-success 元数据字段
3. 统一错误结构与日志关键字段
4. 补充 Agent 级运行元信息 contract

验收标准：

- orchestrator 在消费不同 Agent 结果时，不需要为同类错误写多套兼容逻辑
- fallback 行为可统一出现在 telemetry / report / governance 中

---

### A4. 增强 Agent 层单元测试与黄金样本回归

优先级：`P1`

现状：

- 当前项目全仓测试稳定，但 Agent 级测试强度仍不均衡
- requirement parser、test design、failure triage、self-healing 这几条高价值链仍有补强空间

问题：

- 主链虽能跑，但一旦规则变动，Agent 层局部退化不一定第一时间暴露

建议动作：

1. 优先给 requirement parser 补更多 golden fixtures
2. 给 test design 补 test point / traceability / fallback 关键路径单测
3. 给 failure triage / self-healing 补高价值决策分支覆盖

验收标准：

- Agent 关键输出具备更稳定的 golden 基线
- 复杂规则调整时能更快发现退化

---

### A5. 增强 data-generation-agent 的企业级能力

优先级：`P2`

现状：

- [/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/data-generation-agent/src/agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/data-generation-agent/src/agent.py) 当前约 `415` 行
- 以确定性规则为主，适合作为基础能力

问题：

- 当前可用，但仍不是平台强项
- 企业级测试数据治理、敏感数据约束、模板化策略还不够强

建议动作：

1. 增加更多业务数据模板与字段策略
2. 补敏感数据脱敏/伪造规则
3. 让生成策略更好地与 test point / case generation 对齐

验收标准：

- 数据生成不再只是基础兜底
- 能支撑更多真实业务场景的数据准备需求

---

## 不建议直接纳入当前待完善清单的事项

以下内容虽然出现在 Agent 分析文档中，但当前不建议按原说法直接纳入：

1. “失败聚类分析缺失”
   - 当前已完成第一版 failure clusters / flaky / risk scoring v2

2. “测试点中间层缺失”
   - 当前 `TestPointPlanV1` 与 CoverageMatrix 第一版已存在

3. “必须立即引入统一 Agent 基类”
   - 当前更适合作为 `P1/P2` 的结构优化项，而不是阻塞项

4. “self-healing-advisor-agent 是超大核心单体”
   - 当前代码规模并不支持这一判断，重点热点仍是 requirement parser 与 test design

---

## 推荐纳入 backlog 的简版条目

可直接作为当前 backlog 的 Agent 补充项：

1. 拆分 `requirement-parser-agent` 内部职责，降低复杂度热点
2. 拆分 `test-design-agent` 内部职责，强化 test point / traceability 边界
3. 统一 Agent 配置、fallback、日志与错误契约
4. 增强 Agent 层单元测试与黄金样本回归
5. 增强 `data-generation-agent` 的企业级数据治理能力

---

## 当前建议

若继续推进 Agent 层，推荐顺序如下：

1. `A1 requirement-parser-agent`
2. `A2 test-design-agent`
3. `A3 Agent 统一配置/契约`
4. `A4 Agent 测试增强`
5. `A5 data-generation-agent 企业级增强`
