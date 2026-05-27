# Agent 设计文档索引

> 本目录存放“当前已补齐的 Agent 设计文档”，不是全部实现能力的一一镜像。
> **最后更新**: 2026-03-21

---

## 📚 文档列表

| # | Agent | 设计文档状态 | 优先级 | 设计文档 | 成熟度目标 |
|---|-------|-------------|--------|----------|-----------|
| 1 | Requirement Parser | 已补齐 | P1 | [01-requirement-parser-agent-design.md](./01-requirement-parser-agent-design.md) | L2 → L4 |
| 2 | Test Design | 已补齐 | P1 | [02-test-design-agent-design.md](./02-test-design-agent-design.md) | L2 → L4 |
| 3 | Script Generation | 已补齐 | P2 | [03-script-generation-agent-design.md](./03-script-generation-agent-design.md) | L3 → L4 |
| 4 | Execution Planner | 已补齐 | P1 | [04-execution-planner-agent-design.md](./04-execution-planner-agent-design.md) | L2 → L4 |
| 5 | Failure Analysis | 已补齐 | P1 | [05-failure-analysis-agent-design.md](./05-failure-analysis-agent-design.md) | L2 → L4 |
| 6 | Risk Evaluation | 已补齐 | P2 | [06-risk-evaluation-agent-design.md](./06-risk-evaluation-agent-design.md) | L2 → L4 |
| 7 | Failure Triage | 已补齐 | P2 | [07-failure-triage-agent-design.md](./07-failure-triage-agent-design.md) | L3 → L4 |
| 8 | Self-Healing Advisor | 已补齐 | P2 | [08-self-healing-advisor-agent-design.md](./08-self-healing-advisor-agent-design.md) | L2 → L4 |
| 9 | Data Generation | 已补齐，最小可用实现已落地 | P1 | [09-data-generation-agent-design.md](./09-data-generation-agent-design.md) | L1 → L4 |

---

## 补充专题

| 主题 | 文档 | 说明 |
|---|---|---|
| 测试设计技术补充 | [test-case-design-techniques.md](./test-case-design-techniques.md) | Test Design Agent 的专题补充文档，已按当前实现进度补入现实边界、差距和分阶段完善计划 |

---

## 当前仓库适配说明

这组设计文档描述的是目标态，不等于当前实现态。结合仓库现状，建议按下面的边界理解：

- `test-design-agent` 已经有可运行实现，并且已经在输出 `confidence / requires_review / review_summary / dependent_elements`。
- `data-generation-agent` 已完成最小可用确定性服务，当前应视为“已落地但仍需企业级治理增强”，而不是空壳目录配设计稿。
- 页面分析、执行门禁、确认点回显这些能力，当前更接近“确定性底座 + AI 辅助”的混合形态，而不是纯 AI 流程。
- 后续补文档时，优先写清楚“当前能力、卡点、下一步优先级”，避免把规划态写成已落地事实。
- 这里表格里的“状态”字段主要是设计跟踪状态，不等同于代码仓库里是否已经存在实现文件；如果实现与文档冲突，优先信任当前审计和调用链文档。
- 各设计稿在“模块划分”“代码示例”“测试文件”里列出的很多 `src/...` 路径，更多表示**目标模块拆分方案**，不等于当前仓库里这些文件都已存在；要判断真实实现，请优先看每份文档的 `1.4 当前实现状态与卡点`。

### 当前文档覆盖边界

- 当前目录已覆盖 9 份 Agent 设计文档。
- 这不代表对应能力不存在，只表示“设计稿索引还未补齐到同等颗粒度”。

### 当前实现对齐摘要

| Agent | 当前实现判断 | 主要卡点 | 设计文档状态 |
|---|---|---|---|
| Requirement Parser | 已落地，规则优先 + LLM overlay | `page_surface` 一等输入仍缺 | 已补齐 |
| Test Design | 已落地，且已具备 confidence/review 语义 | 仍偏需求驱动，页面语义驱动可继续增强 | 已补齐 |
| Script Generation | 已落地，当前以 Playwright Python 为主 | 多框架能力尚未展开 | 已补齐 |
| Execution Planner | 已落地，偏单次运行计划 | 还不是全局任务调度中心 | 已补齐 |
| Risk Evaluation | 已落地，规则化评分与门禁建议 | 仍是启发式，不是预测模型 | 已补齐 |
| Failure Analysis | 已落地，但入口为 `analyze.py` | 应用 bug / 测试 bug 边界仍需增强 | 已补齐 |
| Failure Triage | 已落地，路由与分诊可用 | 依赖上游 failure-analysis 质量 | 已补齐 |
| Self-Healing Advisor | 已落地，且强约束自动修复 | 只能做 locator/timeout/selector 级修复 | 已补齐 |
| Data Generation | 已落地最小可用实现 | 还需继续补企业级治理与质量看板 | 已补齐 |

### 文档现实贴合度审查（2026-03-21）

这张表不是评价“设计好不好”，而是评价“文档和当前仓库现实贴得有多近”。

| 文档 | 现实贴合度 | 判断 |
|---|---|---|
| `08-self-healing-advisor-agent-design.md` | 高 | 大部分关键文件真实存在，正文也明确承认当前边界与限制 |
| `02-test-design-agent-design.md` | 中高 | 已能对应到真实 `design_bundle / review_summary / dependent_elements` 主链，但模块拆分仍偏目标态 |
| `01-requirement-parser-agent-design.md` | 中高 | 已能对应到真实 `tools/ + utils/ + agent.py`，但 `input_normalizer.py` 等模块仍是目标拆分 |
| `06-risk-evaluation-agent-design.md` | 中 | 真实 Agent 已落地，但 `change_analyzer.py` 等模块仍是目标拆分 |
| `07-failure-triage-agent-design.md` | 中 | 真实 Agent 已落地，但 `severity_assessor.py` 等模块仍是目标拆分 |
| `03-script-generation-agent-design.md` | 中 | 当前主链真实存在，但大部分“生成器子模块”仍是目标蓝图 |
| `04-execution-planner-agent-design.md` | 中 | 当前执行计划能力真实存在，但“调度中心式模块化”仍明显超前于现实 |
| `05-failure-analysis-agent-design.md` | 中 | 文档已承认现实主入口是 `analyze.py`，但后半段大多是目标重构蓝图 |
| `09-data-generation-agent-design.md` | 中 | 设计稿仍偏目标态，但现实里已经有最小可用实现，当前需要继续对齐治理边界 |

补充说明：

- 这里的“高/中高/中”不代表成熟度高低，只代表“文档有没有把现实和目标分清楚”。
- 当前没有哪份设计稿适合被理解为“完全等同代码实现说明书”。
- 如果要判断真实能力，依旧优先看每份文档的 `1.4 当前实现状态与卡点`。

如果要先看现实状态与风险分布，优先参考：

- [project-inventory-and-risk-audit-2026-03-21.md](../project-inventory-and-risk-audit-2026-03-21.md)
- [current-architecture-and-flows.md](../current-architecture-and-flows.md)

## 📊 设计文档结构

每个 Agent 设计文档包含以下章节：

```
1. Agent 概述
   1.1 职责定义
   1.2 设计原则
   1.3 在平台中的位置

2. 架构设计
   2.1 整体架构
   2.2 模块划分

3. 输入输出契约
   3.1 输入 Schema (Pydantic)
   3.2 输出 Schema (Pydantic)

4. 核心功能实现
   4.x 各模块详细实现代码

5. Agent 主实现
   - 主类代码
   - 编排逻辑

6. 测试策略
   6.1 单元测试
   6.2 Golden Test Set

7. 实施计划
   - Phase 1: 基础框架
   - Phase 2: 核心能力
   - Phase 3: 企业级能力

8. 验收标准
   - 功能验收
   - 质量验收
   - 运维验收
```

---

## 🎯 通用能力标准

所有 Agent 必须满足的通用标准见：
[../agent-enterprise-capabilities.md](../agent-enterprise-capabilities.md)

包括：
- 输入输出契约规范
- 质量指标（准确率>85%、置信度校准>0.7）
- 运维要求（日志、监控、告警）
- 成熟度等级定义（L1-L5）

---

## 📅 实施路线图

整体实施计划见：
[../agent-implementation-roadmap.md](../agent-implementation-roadmap.md)

关键里程碑：
- **Week 6**: Data Generation Agent 完成
- **Week 8**: Test Design Agent 完成
- **Week 10**: Requirement Parser + Execution Planner + Failure Analysis 完成
- **Week 12**: 全部 Agent 达到 L4

---

## 🔧 开发规范

### 代码组织

说明：下面的目录树用于表达推荐拆分方式；当前仓库不少 Agent 仍采用更轻量的 `schema.py + tools/ + utils/` 结构，请以真实目录和各文档的 `1.4 当前实现状态与卡点` 为准。

```
agents/{agent-name}/
├── src/
│   ├── agent.py              # Agent 主类
│   ├── schema.py             # Pydantic Schema（当前仓库主流）
│   ├── {module1}.py          # 功能模块
│   ├── {module2}.py
│   └── utils/                # 工具函数
├── tests/
│   ├── test_{module1}.py     # 单元测试
│   ├── test_{module2}.py
│   └── golden_tests.py       # Golden Test Set
├── README.md                 # 使用说明
└── requirements.txt          # 依赖
```

### Schema 命名规范

```python
# 输入
{AgentName}Input

# 输出
{AgentName}Output

# 中间模型
{EntityName}V1  # 带版本号便于演进
```

### 置信度规范

```python
# 所有输出必须包含置信度
confidence: float  # 0-1

# 置信度解释
0.0-0.5  # 低，需要人工审核
0.5-0.7  # 中，建议使用但需验证
0.7-0.9  # 高，可直接使用
0.9-1.0  # 极高，几乎确定
```

---

## 📝 变更日志

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-03-21 | 1.5 | 补充 `test-case-design-techniques.md` 专题索引，明确其为已校正的补充设计稿 | AI Test Platform Core Team |
| 2026-03-21 | 1.4 | 对 01/02/03/04/05/06/07/09 设计稿补充“目标实现 vs 当前实现”护栏，并修正文档中的 `schema.py` / 测试蓝图口径 | AI Test Platform Core Team |
| 2026-03-21 | 1.1 | 修正文档索引与实际覆盖边界，明确“已补齐设计稿”和“已落地实现”不是同一概念 | AI Test Platform Core Team |
| 2026-03-21 | 1.2 | 补入 Failure Triage 设计文档索引，并同步更新覆盖范围与实现状态 | AI Test Platform Core Team |
| 2026-03-21 | 1.3 | 补入 Self-Healing Advisor 设计文档索引，并完成 01-09 覆盖 | AI Test Platform Core Team |

---

*维护团队：AI Test Platform Core Team*
