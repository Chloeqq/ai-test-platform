# Self-Healing Advisor Agent 详细设计

> **状态**: ⏳ L2 → L4 提升中
> **优先级**: P2
> **目标成熟度**: L4（企业级）
> **预计完成**: 2026-05-16（3 周）
> **当前准确率**: ~75%
> **目标准确率**: > 85%

---

## 1. Agent 概述

### 1.1 职责定义

Self-Healing Advisor Agent 负责在失败发生后输出**受控范围内的修复建议**，并在满足严格条件时，对 `ai-generated` YAML 用例执行单次自动修复尝试。

它的核心职责不是“自动把所有失败修好”，而是：

- 识别适合修复的失败类型
- 输出结构化修复建议
- 生成 patch preview
- 在受控范围内 apply patch
- 触发单次 rerun 验证
- rerun 失败时自动 rollback

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **安全优先** | 宁可不修，也不能误改业务逻辑 |
| **边界明确** | 只允许 locator/timeout/selector 等有限修复 |
| **人工兜底** | 低置信度或高风险场景必须人工审核 |
| **可回滚** | 所有自动修复必须可撤销 |
| **证据驱动** | 修复建议必须来自 failure analysis 和现有 target 信息 |

### 1.3 在平台中的位置

```
Failure Analysis → [Self-Healing Advisor] → Patch Preview / Apply / Rollback
       ↓                    ↓                         ↓
    失败归因           修复建议与计划              rerun 验证结果
```

### 1.4 当前实现状态与卡点

当前仓库里的自愈能力并不是空白，而是已经有一套可运行的受限实现，主要体现在这些文件里：

- `agents/self-healing-advisor-agent/suggest.py`
- `agents/self-healing-advisor-agent/self_healing_orchestrator.py`
- `agents/self-healing-advisor-agent/self_healing_executor.py`
- `agents/self-healing-advisor-agent/apply_fix.py`
- `agents/self-healing-advisor-agent/src/agent.py`

当前更准确的现实判断是：

1. 它已经不是“只有 prompt 的建议器”，而是带 preview / apply / rollback / rerun 的受控修复链。
2. 它仍然不是“全自动修复器”，而是强约束、低范围、人工优先的修复助手。
3. 当前边界已经相当明确：
   - 只允许修改 `assets/test-cases/ai-generated/*`
   - 不允许直接修改 `smoke` 用例
   - 不自动写回 `assets/page-objects/*`
   - 自动修复最多单次尝试
   - `confidence` 必须严格大于阈值
   - rerun 失败会自动 rollback
4. 后续最值得补的重点，不是“修更多东西”，而是：
   - 影响分析更准确
   - 审批判断更稳定
   - 修复类型限制更制度化
   - 与 failure-analysis / triage / execution_gate 的联动更强

这意味着本文应被理解为：

**“已部分落地的 Self-Healing Advisor 的企业级增强设计稿”**，而不是“当前已全部实现的说明书”。

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                 Self-Healing Advisor Agent                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Failure      │  │ Suggestion   │  │ Patch        │          │
│  │ Context      │→ │ Generator    │→ │ Preview      │          │
│  │ Loader       │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                    ↓                   ↓              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Safety       │  │ Apply        │  │ Rerun        │          │
│  │ Guardrails   │← │ Executor     │← │ Runner       │          │
│  │              │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↓                                    ↓                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Rollback / Receipt / Audit                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │ Healing Result  │
                    │ + Receipt       │
                    └─────────────────┘
```

### 2.2 模块划分

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| `suggest.py` | `agents/self-healing-advisor-agent/suggest.py` | 结构化修复建议生成 |
| `src/agent.py` | `agents/self-healing-advisor-agent/src/agent.py` | 轻量 Agent 入口与 schema 输出 |
| `self_healing_orchestrator.py` | `agents/self-healing-advisor-agent/self_healing_orchestrator.py` | 单次自愈编排 |
| `self_healing_executor.py` | `agents/self-healing-advisor-agent/self_healing_executor.py` | preview/apply/rollback 执行 |
| `apply_fix.py` | `agents/self-healing-advisor-agent/apply_fix.py` | CLI 入口 |
| `rerun_runner.py` | `agents/self-healing-advisor-agent/rerun_runner.py` | rerun 触发 |
| `rollback.py` | `agents/self-healing-advisor-agent/rollback.py` | 回滚逻辑 |
| `src/schema.py` | `agents/self-healing-advisor-agent/src/schema.py` | 建议输出 schema |

---

## 3. 输入输出契约

### 3.1 输入 Schema

```python
# agents/self-healing-advisor-agent/src/schema.py

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SelfHealingInput(BaseModel):
    page: str
    failure_reason: str
    failure_analysis: Dict[str, Any]
    available_targets: List[str]
    current_case_path: Optional[str] = None
    artifact_dir: Optional[str] = None
    previous_attempts: int = 0
```

### 3.2 输出 Schema

```python
class SelfHealingAdvice(BaseModel):
    summary: str
    suggestion_type: str
    suggested_changes: list[str]
    rationale: str
    confidence: float
    safe_to_apply_manually: bool

class SelfHealingResult(BaseModel):
    status: str                 # success / rollback / rejected
    reason: str
    attempts_used: int
    max_attempts: int
    confidence: float
    rolled_back: bool
    healed: bool
    plan_path: str = ""
    result_path: str = ""
```

### 3.3 当前允许的 suggestion_type

当前实现已经限制在下面这几个类型：

- `locator_update`
- `assertion_update`
- `wait_strategy`
- `data_adjustment`
- `environment_check`
- `no_change`

这里最重要的不是类型多，而是**类型边界稳**。

---

## 4. 当前已落地能力

### 4.1 建议生成

当前已经支持：

1. 基于 failure category 输出结构化建议
2. 在有模型时走模型建议，没有模型时自动回退到规则建议
3. 对低置信度结果做降级处理
4. 对 target 名称进行合法性校验

### 4.2 安全边界

当前已经明确限制：

1. 仅允许对 `ai-generated` YAML 尝试自动修复
2. 低置信度建议直接拒绝 apply
3. 超过最大尝试次数直接拒绝
4. patch preview 不通过则拒绝 apply
5. rerun 失败时自动 rollback

### 4.3 patch 工作流

当前已经形成的工作流是：

1. `suggestion.json`
2. `patch preview`
3. `apply`
4. `rerun`
5. `success` 或 `rollback`
6. `self_healing_result.json`

这比“只给一段建议文字”已经前进很多。

---

## 5. 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **修复建议生成** | 输出结构化、可操作建议 | 可执行建议率 > 90% |
| **安全边界控制** | 严格限制修复范围 | 不安全修复率 0% |
| **patch preview** | 应用前校验 patch 风险 | preview 拒绝误放行率 < 5% |
| **rerun 验证** | patch 后自动验证效果 | rerun 决策准确率 > 90% |
| **rollback** | 失败时稳定回滚 | rollback 完整率 100% |
| **审批联动** | 高风险场景强制审批 | 审批判断准确率 > 95% |
| **影响分析** | 说明改动影响范围 | 影响分析准确率 > 80% |

---

## 6. 当前主要卡点

### 6.1 修复边界仍需进一步制度化

虽然当前实现已经较保守，但还需要把这些边界更明确地固化到平台治理层：

1. 不改业务断言
2. 不改业务流程
3. 不自动改 page object 主资产
4. 不在高风险门禁下自动放行

### 6.2 依赖上游 failure-analysis 质量

如果 failure-analysis 误判：

1. 建议类型会偏离
2. patch preview 会浪费轮次
3. rerun 失败率会上升

因此 Self-Healing 的上限很大程度取决于 failure-analysis 的质量。

### 6.3 影响分析还不够强

当前更偏“单 case 修复”，还不是“受影响 case 集分析器”。

企业级补强方向包括：

1. patch 对哪些 case 生效
2. patch 是否影响共享 target
3. patch 是否会放大不稳定性

---

## 7. 风险控制

| 风险场景 | 当前控制手段 |
|---------|-------------|
| 把业务 bug 当成 locator 问题修掉 | 低置信度拒绝 + 人工审批 |
| 修改到稳定 smoke 资产 | 仅允许 ai-generated YAML |
| 修完后引入更大问题 | rerun + rollback |
| 反复尝试导致污染 | 最大尝试次数限制 |
| 无模型或模型异常时乱输出 | 规则 fallback |
| suggestion 指向不存在 target | target 合法性校验 |

---

## 8. 实施优先级

### P0

1. 把修复类型限制写成平台硬约束
2. 与 execution_gate / review_state 对齐
3. 明确审批和拒绝记录进入审计链

### P1

1. 加强影响分析
2. 加强与 failure-analysis / triage 的联动
3. 让 rerun 结果与风险评估更好串联

### P2

1. 票据系统联动
2. 批量修复候选聚类
3. 更细粒度的历史成功率统计

---

## 9. 验收标准

- [ ] suggestion 类型严格限制在允许集合内
- [ ] 低置信度建议不能自动 apply
- [ ] 非 `ai-generated` YAML 不能自动 apply
- [ ] rerun 失败时 rollback 100% 可执行
- [ ] 不安全修复率 0%
- [ ] 审计中能追溯谁批准了哪次修复

---

## 10. 当前结论

Self-Healing Advisor Agent 在当前仓库里的合理定位不是“自动修复一切失败”，而是：

**一个带安全边界、带单次修复尝试、带 rerun 与 rollback 的受控自愈助手。**

后续最重要的方向不是把它做成更激进的自动修复器，而是继续压实：

1. 修复边界
2. 审批边界
3. 影响分析
4. 与 failure-analysis / execution_gate / audit 的联动
