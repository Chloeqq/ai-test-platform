# 执行模块归属矩阵

> **适用范围**: Runner / Orchestrator / Agent 分层
> **最后更新**: 2026-03-21
> **文档性质**: 当前项目实施归属基线

---

## 1. 为什么要有这份矩阵

当前项目已经进入“Agent 逐步落地 + Runner 主链稳定化”的阶段，最容易出问题的地方不是“有没有设计”，而是“模块到底该放在哪一层”。

如果把本该由确定性执行层承担的能力塞进 Agent，会带来三个直接风险：

- 拓扑依赖和变量解析变成不稳定推理
- Runner 结果不再可复现
- 回归测试的确定性被 AI 干扰

所以这份文档要解决的是：

**把执行相关模块明确分到 Agent、Orchestrator、Runner、Shared Core 四层。**

---

## 2. 总体原则

### 2.1 一句话边界

- Agent：负责决策、规划、建议
- Orchestrator：负责编排、透传、协调
- Runner：负责确定性执行
- Shared Core：负责跨 Runner 复用的确定性能力

### 2.2 判定规则

如果一个模块主要在回答：

- “应该怎么执行？” → 更偏 Agent / Planner
- “按什么顺序调度？” → 更偏 Orchestrator / Planner
- “实际怎么跑步骤？” → 更偏 Runner
- “变量、输出、证据怎么稳定解析？” → 更偏 Shared Core / Runner

---

## 3. 你关注的 5 个模块该归谁

| 模块 | 推荐归属 | 是否应由 Agent 实现 | 当前项目状态 | 说明 |
|---|---|---|---|---|
| `DependencyResolver` | Execution Planner Agent + Orchestrator | 部分是 | 设计态，未落地主链 | 依赖图与运行顺序属于规划/调度层，不应先塞进 Web Runner YAML |
| `MultiPageExecutor` | Web Runner | 否 | 已有可实施方案，未编码 | 这是页面对象切换和步骤执行问题，必须走确定性执行层 |
| `MultiRunnerExecutor` | Orchestrator / Shared Runner Core | 否 | 设计态，未落地 | 这是跨 Runner 编排，不属于单个 Agent 的职责 |
| `OutputExtractor` | Shared Core / Evidence Pipeline | 否 | 设计态，未形成统一模块 | 输出提取必须稳定、可重复，被 Failure/Risk Agent 消费即可 |
| `VariableResolver` 增强 | Shared Core / Runner | 否 | 已有基础实现，需增强 | 变量解析属于确定性替换与引用解析，不应做成 LLM 逻辑 |

---

## 4. 分模块详细说明

### 4.1 `DependencyResolver`

#### 最合理归属

- 规划侧：`Execution Planner Agent`
- 协调侧：`AI Orchestrator`

#### 为什么不是 Runner

因为它解决的是：

- 哪些任务先执行
- 哪些任务依赖上游结果
- 失败后是否跳过后续任务

这些都属于“运行计划”和“任务编排”，不是单个 Web YAML 步骤执行问题。

#### 为什么又不能只交给 Agent

因为依赖解析里真正确定性的部分包括：

- 拓扑排序
- 循环依赖检测
- 缺依赖报错
- 运行状态传播

这些不该由 LLM 推理完成，而应该由确定性代码完成。  
更合理的方式是：

- Agent 定义任务和依赖语义
- Orchestrator/Planner 用确定性代码做解析与校验

#### 当前项目对应证据

- 当前 Execution Planner 设计文档已把 `dependency_resolver.py` 放在其目标模块里：
  - [04-execution-planner-agent-design.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/agents/04-execution-planner-agent-design.md)
- 但当前真实实现还只是基础执行计划：
  - [agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/execution-planner-agent/src/agent.py)

#### 推荐文件落点

- `agents/execution-planner-agent/src/dependency_resolver.py`
- `apps/ai-orchestrator/src/services/execution_dependency_service.py`

---

### 4.2 `MultiPageExecutor`

#### 最合理归属

- `runners/web-playwright-python`

#### 为什么不该由 Agent 做

多页面执行本质上是：

- step 使用哪个 page object
- 某个 target 到底去哪份 page object 里解析
- 同一个浏览器 page 上如何稳定执行步骤

这必须是确定性行为，不应该让 Agent 在执行时“理解页面”。

#### 当前项目对应证据

- 当前真实执行器：
  - [yaml_executor.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/yaml_executor.py)
- 当前可实施方案文档：
  - [multi-page-web-runner-plan.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/runners/multi-page-web-runner-plan.md)

#### 推荐文件落点

- 不建议单独新建 `multi_page_executor.py` 立即分叉
- 当前更建议：
  - 先增强 `runners/web-playwright-python/runner/yaml_executor.py`
  - 如复杂度继续上升，再拆为：
    - `runners/web-playwright-python/runner/multi_page_executor.py`

#### 当前优先级

- P0 / P1 之间，优先于多 Runner

---

### 4.3 `MultiRunnerExecutor`

#### 最合理归属

- `AI Orchestrator`
- 或未来 `shared-runner-sdk`

#### 为什么不该由单个 Agent 做

它关注的是：

- API Runner、Web Runner、Mobile Runner 如何串起来
- 阶段执行如何传递上下文
- 哪个阶段失败后如何终止或降级

这是“跨执行器编排”问题，不是某个 Agent 的语义能力问题。

#### 当前项目现实

- API/Mobile Runner 目录基本为空
- 当前只有 Web Runner 相对成熟

这意味着现在直接实现 `MultiRunnerExecutor` 的 ROI 不高，也容易做出一个文档很完整、实际不可运行的空壳。

#### 推荐文件落点

- `apps/ai-orchestrator/src/services/multi_runner_service.py`
- 或未来：
  - `runners/shared-runner-sdk/src/multi_runner_executor.py`

#### 当前优先级

- P3，必须晚于 Web 多页面和 execution record/evidence 协议统一

---

### 4.4 `OutputExtractor`

#### 最合理归属

- Shared Core
- Evidence Pipeline

#### 为什么不该由 Agent 做

输出提取如果不稳定，会直接污染：

- 失败分析
- 风险评估
- 历史回显
- 依赖输入传递

所以它必须是：

- 确定性规则
- 明确 extractor 类型
- 明确失败和空值行为

Agent 可以消费提取结果，但不应该拥有“提取器本身”。

#### 当前项目对应证据

- 当前证据主链已经在往 `execution_record + evidence_manifest` 收口：
  - [evidence-pipeline.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/evidence-pipeline.md)

#### 推荐文件落点

- `runners/shared-runner-sdk/src/output_extractor.py`
- 或现阶段先放：
  - `apps/ai-orchestrator/src/services/output_extractor.py`

#### 当前优先级

- P2，高于 `MultiRunnerExecutor`

---

### 4.5 `VariableResolver` 增强

#### 最合理归属

- Runner / Shared Core

#### 当前现实

当前已经存在基础版本：

- [variable_resolver.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/variable_resolver.py)

当前只支持：

- 字符串里的 `{{var}}`
- 简单替换
- 缺变量不报错

#### 为什么不该交给 Agent

变量解析一旦不确定，会让执行不可复现。  
尤其如果后续支持跨用例引用：

- `{{ upstream.outputs.user_id }}`
- `{{ task_001.outputs.token }}`

那么解析必须由规则和上下文字典完成，不能让 Agent 动态猜值。

#### 推荐文件落点

短期：

- 继续增强：
  - `runners/web-playwright-python/runner/variable_resolver.py`

中期：

- 抽到：
  - `runners/shared-runner-sdk/src/variable_resolver.py`

#### 当前优先级

- P1，和 `MultiPageExecutor` 搭配推进

---

## 5. 当前有没有 Agent 被安排做这些

### 已有明确承担者

- `Execution Planner Agent`
  - 已明确承担“执行计划、阶段、并发、重试、调度提示”
  - 但还没有正式成为全局依赖调度中心

### 还没有 Agent 正式承担的

- `MultiPageExecutor`
- `MultiRunnerExecutor`
- `OutputExtractor`
- Runner 级 `VariableResolver` 增强

这些当前更应该作为：

- Runner 主链增强
- Orchestrator 编排增强
- Shared Core 收口增强

而不是新增一个“万能执行 Agent”来包办。

---

## 6. 推荐实施顺序

### P0

- `MultiPageExecutor`
  - 实际上先做成 `YamlExecutor` 的最小增强
- `VariableResolver` 增强
  - 让 step/page/data 上下文解析更稳

### P1

- `DependencyResolver`
  - 先在 planner/orchestrator 层形成 run-level dependency graph

### P2

- `OutputExtractor`
  - 与 evidence pipeline 接轨
  - 为 failure/risk/triage 提供稳定输入

### P3

- `MultiRunnerExecutor`
  - 必须等 API/Mobile 至少有一个真实 Runner 后再做

---

## 7. 建议的文件落点总表

| 模块 | 建议文件落点 |
|---|---|
| `DependencyResolver` | `agents/execution-planner-agent/src/dependency_resolver.py` |
| `DependencyResolver` 协调层 | `apps/ai-orchestrator/src/services/execution_dependency_service.py` |
| `MultiPageExecutor` | `runners/web-playwright-python/runner/yaml_executor.py`，后续可拆 `multi_page_executor.py` |
| `MultiRunnerExecutor` | `apps/ai-orchestrator/src/services/multi_runner_service.py` |
| `OutputExtractor` | `apps/ai-orchestrator/src/services/output_extractor.py` 或未来 `runners/shared-runner-sdk/src/output_extractor.py` |
| `VariableResolver` 增强 | `runners/web-playwright-python/runner/variable_resolver.py`，后续可抽 `shared-runner-sdk` |

---

## 8. 一句话结论

你列的这 5 个模块里，真正适合由 Agent 主导的只有 `DependencyResolver` 的“规划层部分”；其余都更适合放在 Runner、Orchestrator 或 Shared Core，用确定性代码实现。

