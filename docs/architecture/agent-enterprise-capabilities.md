# Agent 企业级能力标准（2026-03-21）

> 本文档定义每个 Agent 要达到企业级别可用所需具备的能力、质量指标和运维要求。
> 用于指导 Agent 的迭代开发和验收标准。

## 阅读说明

这份文档的定位是：**企业级目标标准文档**。

阅读时请注意：

1. 这里定义的是“达到企业级时应具备什么”，不是“当前仓库里已经全部做到什么”。
2. 当前真实能力状态、卡点和优先级，优先参考：
   - [current-architecture-and-flows.md](./current-architecture-and-flows.md)
   - [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
   - [agent-implementation-roadmap.md](./agent-implementation-roadmap.md)
   - [agents/README.md](./agents/README.md)
3. 文中出现的准确率、SLA、P95、覆盖率等阈值，应理解为目标验收线，而不是当前对外承诺值。
4. 如果标准文档与代码现实冲突，先信任当前架构审计和代码扫描结论。

---

## 📋 企业级能力通用标准

所有 Agent 在**声明达到企业级能力**时，应满足以下通用要求：

### 1. 输入输出契约

```python
class AgentContract:
    # 输入
    input_schema: dict          # Pydantic 模型定义
    input_validation: bool      # 必须校验
    input_versioning: str       # 输入 schema 版本
    
    # 输出
    output_schema: dict         # Pydantic 模型定义
    output_validation: bool     # 必须校验
    confidence_score: float     # 0-1 置信度
    warnings: List[str]         # 警告信息
    requires_review: bool       # 是否需要人工审核
    
    # 元数据
    agent_version: str          # Agent 版本
    model_used: str             # 使用的 LLM 模型
    processing_time_ms: int     # 处理耗时
    token_usage: dict           # token 消耗统计
```

### 2. 质量指标

| 指标 | 定义 | 企业级标准 |
|------|------|-----------|
| **准确率** | 输出正确的比例 | > 85% |
| **置信度校准** | 置信度与实际准确率的相关性 | > 0.7 |
| **可解释性** | 输出附带依据/推理过程 | 100% |
| **稳定性** | 相同输入输出一致的比例 | > 95% |
| **延迟** | P95 响应时间 | < 10s |
| **可用性** | 服务可用时间比例 | > 99% |

### 3. 运维要求

- ✅ 结构化日志（JSON 格式，包含 trace_id）
- ✅ 指标上报（Prometheus 兼容）
- ✅ 错误分类（可重试 vs 不可重试）
- ✅ 降级策略（LLM 不可用时的 fallback）
- ✅ 版本管理（支持灰度发布和回滚）

---

## 🤖 Agent 能力矩阵

说明：

- 以下各 Agent 小节描述的是“企业级目标能力矩阵”。
- 这不等于当前每个 Agent 都已经满足对应标准。
- 当前仓库里，大多数 Agent 都属于“已部分落地，但距离企业级标准仍有差距”；`data-generation-agent` 已完成最小可用确定性服务，但企业级治理仍未收口。

### 1. Requirement Parser Agent

**职责**：解析多源需求输入，提取结构化测试意图

#### 输入输出契约

```python
class RequirementParserInput:
    source_type: str           # prd/swagger/git_diff/bug_report/logs
    content: str               # 原始内容
    metadata: dict             # 来源、版本、时间戳
    context: Optional[dict]    # 相关业务上下文

class RequirementParserOutput:
    requirement_spec: dict     # 结构化需求
    test_intents: List[dict]   # 测试意图列表
    entities: List[dict]       # 业务实体识别
    ambiguities: List[dict]    # 歧义点及位置
    priority: str              # P0/P1/P2
    parse_confidence: float    # 解析置信度
    quality_gate: dict         # 质量门禁结果
    warnings: List[str]
    requires_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **多源输入支持** | PRD/Swagger/Git Diff/缺陷单/日志 | 5 种输入源全部支持 |
| **实体识别** | 识别业务对象、操作、规则、约束 | F1 > 0.85 |
| **歧义检测** | 识别模糊、矛盾、缺失的需求 | 召回率 > 80% |
| **优先级判定** | 基于业务影响自动判定优先级 | 与人工判定一致性 > 85% |
| **质量门禁** | 检测需求完整性和可测试性 | 准确识别不可测试需求 |
| **版本追溯** | 需求变更与版本关联 | 100% 可追溯 |

#### 质量指标

```yaml
metrics:
  accuracy:
    entity_extraction_f1: 0.85
    intent_classification_accuracy: 0.90
    ambiguity_detection_recall: 0.80
    priority_agreement_rate: 0.85
  
  performance:
    p95_latency_ms: 8000
    throughput_per_minute: 50
  
  reliability:
    confidence_calibration: 0.75
    stability_rate: 0.95
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 需求过于模糊 | 输出 `requires_review=true`，列出需要澄清的问题 |
| 置信度低于阈值 | 自动阻断，要求人工介入 |
| 多源输入冲突 | 标记冲突点，输出置信度对比 |
| LLM 输出不稳定 | 使用 self-consistency，多次采样取多数 |

---

### 2. Test Design Agent

**职责**：基于需求设计测试点和测试场景

#### 输入输出契约

```python
class TestDesignInput:
    requirement_spec: dict       # 来自 Requirement Parser
    existing_test_points: List   # 现有测试点（用于去重）
    page_objects: List           # 可用页面对象
    coverage_goals: dict         # 覆盖目标
    constraints: dict            # 约束条件（时间、资源）

class TestDesignOutput:
    test_point_plan: dict        # 测试点计划
    test_cases: List[dict]       # 生成的测试用例
    coverage_matrix: dict        # 覆盖矩阵
    traceability: dict           # 需求→测试点→用例追溯
    design_confidence: float     # 设计置信度
    gaps: List[dict]             # 覆盖缺口
    warnings: List[str]
    requires_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **测试点生成** | 从需求生成完整测试点 | 覆盖率 > 90% |
| **场景设计** | 正常/异常/边界场景完整 | 场景完整性 > 85% |
| **优先级分配** | 基于风险和业务价值 | 与人工优先级一致性 > 85% |
| **去重能力** | 识别并合并相似测试点 | 重复率 < 5% |
| **追溯能力** | 需求→测试点→用例双向追溯 | 100% 可追溯 |
| **覆盖分析** | 识别覆盖缺口和冗余 | 缺口识别准确率 > 80% |

#### 质量指标

```yaml
metrics:
  accuracy:
    test_point_coverage: 0.90
    scenario_completeness: 0.85
    priority_agreement_rate: 0.85
    deduplication_accuracy: 0.95
  
  performance:
    p95_latency_ms: 10000
    test_points_per_minute: 30
  
  reliability:
    confidence_calibration: 0.70
    stability_rate: 0.95
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 测试点遗漏 | 与历史用例对比，识别覆盖缺口 |
| 测试点过多 | 基于优先级和约束进行筛选 |
| 边界场景缺失 | 强制包含边界值分析模板 |
| 业务逻辑错误 | P0/P1 测试点必须人工审核 |

---

### 3. Script Generation Agent

**职责**：将测试点转换为可执行脚本

#### 输入输出契约

```python
class ScriptGenerationInput:
    test_points: List[dict]      # 测试点列表
    page_objects: List[dict]     # 页面对象定义
    target_framework: str        # playwright/appium/pytest
    coding_standards: dict       # 编码规范
    reusable_components: List    # 可复用组件库

class ScriptGenerationOutput:
    generated_scripts: List[dict]  # 生成的脚本
    script_metadata: dict          # 脚本元数据
    validation_results: dict       # 语法/静态检查结果
    generation_confidence: float   # 生成置信度
    code_quality_score: float      # 代码质量评分
    warnings: List[str]
    requires_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **代码生成** | 生成可执行的测试脚本 | 语法正确率 > 98% |
| **框架适配** | 支持多种测试框架 | Playwright/API/Appium |
| **规范遵循** | 遵循团队编码规范 | 规范符合率 > 95% |
| **组件复用** | 优先使用可复用组件 | 复用率 > 60% |
| **静态检查** | 通过 lint/type 检查 | 零错误，警告 < 5 |
| **可维护性** | 代码可读、可修改 | 可维护性评分 > 80 |

#### 质量指标

```yaml
metrics:
  accuracy:
    syntax_correctness: 0.98
    framework_compliance: 0.95
    coding_standard_adherence: 0.95
    component_reuse_rate: 0.60
  
  performance:
    p95_latency_ms: 5000
    scripts_per_minute: 20
  
  reliability:
    confidence_calibration: 0.80
    stability_rate: 0.98
    first_run_pass_rate: 0.85
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 生成的代码不可执行 | 强制执行环境验证（dry-run） |
| 使用已废弃的 API | 集成 API 弃用检查 |
| 硬编码敏感信息 | 自动检测并标记敏感数据 |
| 代码质量差 | 集成代码质量评分，低于阈值需审核 |

---

### 4. Execution Planner Agent

**职责**：规划测试执行策略和资源分配

#### 输入输出契约

```python
class ExecutionPlannerInput:
    test_cases: List[dict]       # 待执行用例
    environments: List[dict]     # 可用环境
    resources: dict              # 资源约束（并发、时间）
    priorities: dict             # 优先级配置
    dependencies: List[dict]     # 用例依赖关系

class ExecutionPlannerOutput:
    execution_plan: dict         # 执行计划
    schedule: List[dict]         # 调度时间表
    resource_allocation: dict    # 资源分配方案
    risk_assessment: dict        # 执行风险评估
    plan_confidence: float       # 计划置信度
    warnings: List[str]
    requires_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **智能调度** | 基于优先级和依赖的调度 | 调度合理性 > 90% |
| **资源优化** | 最大化资源利用率 | 资源利用率 > 75% |
| **并发控制** | 合理分配并发任务 | 无资源冲突 |
| **重试策略** | 智能重试（区分 flaky） | 重试成功率 > 60% |
| **风险评估** | 识别执行风险 | 风险识别准确率 > 80% |
| **动态调整** | 执行中动态调整计划 | 调整响应时间 < 1min |

#### 质量指标

```yaml
metrics:
  accuracy:
    schedule_feasibility: 0.95
    resource_utilization: 0.75
    retry_success_rate: 0.60
    risk_detection_accuracy: 0.80
  
  performance:
    p95_latency_ms: 3000
    plan_generation_time: < 30s
  
  reliability:
    confidence_calibration: 0.85
    stability_rate: 0.98
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 资源过度分配 | 设置资源上限，超额时排队 |
| 依赖循环检测 | 执行前验证依赖图无环 |
| 环境不可用 | 环境健康检查，自动切换备用 |
| 执行超时 | 设置超时阈值，自动终止 |

---

### 5. Risk Evaluation Agent

**职责**：评估版本/变更的风险等级

#### 输入输出契约

```python
class RiskEvaluationInput:
    change_scope: dict           # 变更范围
    test_results: List[dict]     # 测试结果
    historical_data: dict        # 历史数据
    business_context: dict       # 业务上下文
    release_criteria: dict       # 发布标准

class RiskEvaluationOutput:
    risk_score: float            # 风险评分 0-100
    risk_level: str              # low/medium/high/critical
    risk_factors: List[dict]     # 风险因素明细
    contributing_evidence: dict  # 支撑证据
    release_recommendation: str  # 发布建议
    mitigation_suggestions: List # 缓解建议
    evaluation_confidence: float # 评估置信度
    warnings: List[str]
    requires_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **风险量化** | 输出可解释的风险评分 | 评分可解释性 100% |
| **因素分析** | 识别具体风险因素 | 因素识别准确率 > 85% |
| **趋势预测** | 基于历史预测风险趋势 | 预测准确率 > 75% |
| **发布建议** | 给出明确的发布建议 | 建议合理性 > 90% |
| **缓解建议** | 提供可执行的缓解措施 | 建议可操作性 > 80% |
| **阈值配置** | 支持自定义风险阈值 | 配置覆盖率 100% |

#### 质量指标

```yaml
metrics:
  accuracy:
    risk_factor_accuracy: 0.85
    trend_prediction_accuracy: 0.75
    recommendation_agreement_rate: 0.90
    mitigation_actionability: 0.80
  
  performance:
    p95_latency_ms: 5000
    evaluations_per_minute: 30
  
  reliability:
    confidence_calibration: 0.80
    stability_rate: 0.95
    false_negative_rate: < 0.05  # 高风险误判为低风险
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 高风险误判为低风险 | 设置保守阈值，宁可高估 |
| 风险因素遗漏 | 强制检查清单（变更范围、测试结果、历史） |
| 建议不可执行 | 建议必须包含具体行动项 |
| 业务上下文缺失 | 缺失时自动标记 requires_review |

---

### 6. Failure Analysis Agent

**职责**：分析测试失败根因

#### 输入输出契约

```python
class FailureAnalysisInput:
    test_case: dict              # 失败用例信息
    execution_evidence: dict     # 执行证据（截图、日志、trace）
    historical_failures: List    # 历史相似失败
    environment_info: dict       # 环境信息

class FailureAnalysisOutput:
    failure_category: str        # 失败分类
    likely_cause: str            # 可能根因
    confidence: float            # 置信度
    evidence_summary: dict       # 证据摘要
    alternative_hypotheses: List # 其他可能原因
    application_bug_probability: float  # 应用 bug 概率
    test_bug_probability: float    # 测试脚本 bug 概率
    suggested_actions: List[str] # 建议行动
    analysis_confidence: float   # 分析置信度
    warnings: List[str]
    requires_manual_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **失败分类** | 准确分类失败类型 | 分类准确率 > 85% |
| **根因定位** | 定位到具体原因 | 根因定位准确率 > 75% |
| **证据分析** | 综合分析多源证据 | 证据利用率 > 90% |
| **应用/测试区分** | 区分应用 bug 和脚本 bug | 区分准确率 > 80% |
| **相似案例** | 识别历史相似失败 | 召回率 > 70% |
| **可解释性** | 输出分析依据 | 100% 可解释 |

#### 质量指标

```yaml
metrics:
  accuracy:
    failure_category_accuracy: 0.85
    root_cause_accuracy: 0.75
    bug_type_distinction: 0.80
    similar_case_recall: 0.70
  
  performance:
    p95_latency_ms: 8000
    analyses_per_minute: 25
  
  reliability:
    confidence_calibration: 0.75
    stability_rate: 0.90
    false_negative_rate: < 0.10  # 应用 bug 误判为脚本问题
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 应用 bug 误判为脚本问题 | 设置保守阈值，置信度低时标记人工复核 |
| 证据不足 | 明确标注证据缺口，不强行归因 |
| 多根因场景 | 输出多个假设及概率分布 |
| 置信度虚高 | 定期校准置信度与实际准确率 |

---

### 7. Failure Triage Agent

**职责**：失败分类路由和责任分配

#### 输入输出契约

```python
class FailureTriageInput:
    failure_analysis: dict       # 来自 Failure Analysis
    team_structure: dict         # 团队结构
    ownership_rules: dict        # 责任归属规则
    severity_criteria: dict      # 严重程度标准
    ticket_system_config: dict   # 票据系统配置

class FailureTriageOutput:
    severity: str                # 严重程度
    owner_team: str              # 责任团队
    assigned_to: Optional[str]   # 具体负责人
    ticket_action: str           # 票据动作（create/update/close）
    queue_priority: int          # 队列优先级
    escalation_required: bool    # 是否需要升级
    triage_confidence: float     # 分类置信度
    routing_rationale: str       # 路由依据
    warnings: List[str]
    requires_manual_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **严重程度判定** | 准确判定失败严重性 | 判定准确率 > 90% |
| **责任路由** | 正确分配责任团队 | 路由准确率 > 85% |
| **优先级排序** | 合理设置处理优先级 | 优先级合理性 > 85% |
| **升级识别** | 识别需要升级的场景 | 升级识别准确率 > 90% |
| **票据动作** | 自动创建/更新票据 | 票据准确率 > 95% |
| **路由可解释** | 说明路由依据 | 100% 可解释 |

#### 质量指标

```yaml
metrics:
  accuracy:
    severity_accuracy: 0.90
    routing_accuracy: 0.85
    priority_reasonableness: 0.85
    escalation_accuracy: 0.90
    ticket_accuracy: 0.95
  
  performance:
    p95_latency_ms: 3000
    triages_per_minute: 50
  
  reliability:
    confidence_calibration: 0.85
    stability_rate: 0.95
    misrouting_rate: < 0.05  # 错误路由比例
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 错误路由导致延误 | 置信度低时标记人工复核 |
| 严重程度低估 | 设置保守阈值，宁高勿低 |
| 责任团队不存在 | 维护团队有效性检查 |
| 票据信息不完整 | 强制字段校验 |

---

### 8. Self-Healing Advisor Agent

**职责**：生成测试脚本自愈建议

#### 输入输出契约

```python
class SelfHealingInput:
    failure_analysis: dict       # 失败分析结果
    current_script: str          # 当前脚本
    page_objects: List[dict]     # 页面对象
    allowed_fix_types: List[str] # 允许的修复类型
    safety_constraints: dict     # 安全约束

class SelfHealingOutput:
    patch_plan: dict             # 修复计划
    patch_diff: str              # 代码 diff
    fix_type: str                # 修复类型
    confidence: float            # 修复置信度
    risk_assessment: dict        # 修复风险评估
    rollback_plan: dict          # 回滚计划
    test_rerun_required: bool    # 是否需要重跑
    approval_required: bool      # 是否需要审批
    healing_confidence: float    # 自愈置信度
    warnings: List[str]
    requires_manual_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **修复建议** | 生成可执行的修复方案 | 方案可执行率 > 95% |
| **类型限制** | 仅允许安全修复类型 | 100% 遵循约束 |
| **风险评估** | 评估修复风险 | 风险识别准确率 > 85% |
| **回滚计划** | 提供回滚方案 | 回滚方案完整率 100% |
| **影响分析** | 分析修复影响范围 | 影响分析准确率 > 80% |
| **审批判断** | 判断是否需要人工审批 | 审批判断准确率 > 95% |

#### 质量指标

```yaml
metrics:
  accuracy:
    patch_executability: 0.95
    constraint_compliance: 1.00
    risk_identification: 0.85
    impact_analysis_accuracy: 0.80
    approval_judgment_accuracy: 0.95
  
  performance:
    p95_latency_ms: 6000
    healing_suggestions_per_minute: 20
  
  reliability:
    confidence_calibration: 0.80
    stability_rate: 0.95
    unsafe_patch_rate: 0.00  # 不允许出现不安全修复
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 修复引入新 bug | 强制代码审查 + 重跑验证 |
| 修改业务逻辑 | 严格限制修复类型（仅 locator/timeout/selector） |
| 回滚失败 | 回滚方案必须预先验证 |
| 修复置信度虚高 | 置信度低于阈值时强制人工审批 |

---

### 9. Data Generation Agent ⚠️（最小可用确定性服务已完成）

**职责**：生成测试数据和数据治理

#### 输入输出契约

```python
class DataGenerationInput:
    data_requirements: dict      # 数据需求
    data_templates: List[dict]   # 数据模板
    constraints: dict            # 约束条件（合规、脱敏）
    existing_data: Optional[dict] # 现有数据（用于增量）

class DataGenerationOutput:
    generated_data: List[dict]   # 生成的数据
    data_metadata: dict          # 数据元数据
    validation_results: dict     # 数据验证结果
    coverage_analysis: dict      # 覆盖分析
    sensitivity_flags: List[str] # 敏感数据标记
    generation_confidence: float # 生成置信度
    warnings: List[str]
    requires_manual_review: bool
```

#### 企业级能力要求

| 能力 | 详细说明 | 验收标准 |
|------|---------|---------|
| **边界值生成** | 自动生成边界值数据 | 边界值覆盖率 100% |
| **关联数据** | 生成有业务关联的数据 | 关联正确率 > 95% |
| **数据脱敏** | 自动脱敏敏感信息 | 脱敏完整率 100% |
| **数据验证** | 验证数据有效性 | 验证通过率 > 98% |
| **数据清理** | 测试后清理污染数据 | 清理完整率 100% |
| **数据版本** | 数据与业务版本绑定 | 版本追溯率 100% |

#### 质量指标

```yaml
metrics:
  accuracy:
    boundary_value_coverage: 1.00
    data_relationship_accuracy: 0.95
    data_masking_completeness: 1.00
    data_validation_pass_rate: 0.98
    cleanup_completeness: 1.00
  
  performance:
    p95_latency_ms: 5000
    data_records_per_minute: 100
  
  reliability:
    confidence_calibration: 0.85
    stability_rate: 0.98
    data_leak_rate: 0.00  # 不允许数据泄露
```

#### 风险控制

| 风险场景 | 缓解措施 |
|---------|---------|
| 生成敏感数据泄露 | 强制脱敏检查，泄露零容忍 |
| 数据不符合业务规则 | 集成业务规则验证 |
| 数据污染生产环境 | 环境隔离 + 数据标记 |
| 数据清理失败 | 清理失败自动告警 |

#### 实施优先级

```
Phase 1 (P0):
- 边界值生成器
- 基础数据模板管理
- 数据验证框架

Phase 2 (P1):
- 关联数据生成
- 数据脱敏
- 数据清理

Phase 3 (P2):
- 生产数据脱敏复用
- 数据版本管理
- 数据质量看板
```

---

## 📊 Agent 能力成熟度模型

### 成熟度等级定义

| 等级 | 名称 | 特征 | 可用场景 |
|------|------|------|---------|
| **L1** | 实验级 | 功能可用，准确率低，需人工复核 | 内部测试 |
| **L2** | 可用级 | 准确率>70%，有基本监控 | 非关键业务 |
| **L3** | 生产级 | 准确率>85%，完整监控告警 | 一般业务 |
| **L4** | 企业级 | 准确率>90%，SLA 保障，灰度发布 | 关键业务 |
| **L5** | 自治级 | 准确率>95%，自优化，零人工介入 | 核心业务 |

### 当前 Agent 成熟度评估

| Agent | 当前等级 | 目标等级 | 差距分析 |
|-------|---------|---------|---------|
| Requirement Parser | L2 | L4 | 多源输入支持不足，置信度校准待提升 |
| Test Design | L2 | L4 | 测试点中间层缺失，追溯能力待完善 |
| Script Generation | L3 | L4 | 代码质量评分需提升，静态检查待集成 |
| Execution Planner | L2 | L4 | 统一任务模型缺失，调度能力待增强 |
| Risk Evaluation | L2 | L4 | 风险因素可解释性待提升 |
| Failure Analysis | L2 | L4 | 应用/测试 bug 区分准确率待提升 |
| Failure Triage | L3 | L4 | 路由准确率待提升 |
| Self-Healing Advisor | L2 | L4 | 修复类型限制已较好，影响分析待完善 |
| Data Generation | L1 | L4 | 最小可用确定性服务已完成，模板 / registry / cleanup 基础可用；脱敏 / 版本 / 看板仍待补 |

---

## 🔧 运维与监控要求

### 1. 日志规范

```json
{
  "timestamp": "2026-03-21T10:00:00Z",
  "trace_id": "abc123",
  "agent_name": "failure-analysis-agent",
  "agent_version": "1.2.0",
  "action": "analyze_failure",
  "input_hash": "sha256:...",
  "output": {
    "failure_category": "locator_not_found",
    "confidence": 0.85,
    "requires_manual_review": false
  },
  "metrics": {
    "processing_time_ms": 2345,
    "token_usage": {"prompt": 1200, "completion": 450},
    "model_used": "openai-compatible-model"
  },
  "level": "INFO"
}
```

### 2. 指标上报

```python
# Prometheus 指标示例
agent_processing_duration_seconds{agent="failure-analysis-agent"}
agent_requests_total{agent="failure-analysis-agent",status="success"}
agent_confidence_score{agent="failure-analysis-agent"}
agent_accuracy_rate{agent="failure-analysis-agent",metric="root_cause"}
```

### 3. 告警规则

| 告警 | 条件 | 响应 |
|------|------|------|
| 准确率下降 | 连续 1h 准确率 < 阈值 -10% | 通知 Agent 负责人 |
| 延迟升高 | P95 延迟 > 阈值 * 2 | 检查 LLM 服务 |
| 错误率升高 | 错误率 > 5% | 检查输入数据质量 |
| 置信度异常 | 平均置信度 > 0.95 | 可能置信度校准失效 |

### 4. 灰度发布流程

```
1. 新版本部署到 5% 流量
2. 监控关键指标 24h
3. 指标正常 → 扩大到 50%
4. 继续监控 24h
5. 指标正常 → 全量发布
6. 任一阶段指标异常 → 自动回滚
```

---

## 📈 持续改进机制

### 1. 反馈闭环

```
AI 输出 → 人工修正 → 记录修正 → 定期分析 → 优化 prompt/模型
                                    ↓
                            Golden Test Set 更新
```

### 2. 定期评估

| 频率 | 活动 | 参与者 |
|------|------|--------|
| 每周 | 准确率趋势 review | Agent 负责人 |
| 每月 | 全面能力评估 | 技术委员会 |
| 每季度 | 企业级标准对齐 | 质量团队 |

### 3. Golden Test Set

- 每个 Agent 维护 50-100 个标准测试案例
- 每次代码/prompt 变更后自动运行
- 准确率下降时阻断发布

---

## 📝 文档维护要求

| 文档类型 | 更新频率 | 负责人 |
|---------|---------|--------|
| Agent 能力文档 | 每次迭代 | Agent 负责人 |
| 输入输出契约 | Schema 变更时 | 架构师 |
| 质量指标报告 | 每周 | 质量团队 |
| 运维手册 | 每次架构变更 | SRE |

---

## ✅ 验收清单

新 Agent 或 Agent 重大升级在**对外声明达到企业级标准前**，应完成以下验收：

- [ ] 输入输出 Schema 定义完整
- [ ] 质量指标达到企业级标准
- [ ] 监控指标接入 Prometheus
- [ ] 日志格式符合规范
- [ ] 告警规则配置完成
- [ ] 灰度发布流程验证通过
- [ ] Golden Test Set 通过率 > 目标值
- [ ] 运维手册更新完成
- [ ] 回滚方案验证通过
- [ ] 安全审查通过（数据泄露、注入等）

---

## 当前项目适配结论

这份能力标准本身是合理的，但结合当前仓库，落地时需要把“确定性优先”写成硬约束，而不是建议项。

### 1. 不要把工程事实交给 AI

以下环节应优先使用规则、schema 校验和确定性逻辑：

- URL 解析
- DOM 提取
- 页面与路由归一化
- locator / target 标准化
- pass / fail 断言
- 证据索引与归档

这些地方的价值是稳定和可重复，不是语义推理。

### 2. 适合 AI 的环节只做辅助

以下环节可以保留 AI，但必须同时输出 `confidence / warnings / requires_review`：

- 页面语义分类
- 测试点提炼
- 风险解释
- 失败归因摘要
- 用例草稿填充

这里 AI 的角色是“建议”和“补充”，不是最终裁决者。

### 3. 人工确认点应按条件触发

当前方案里提到的 3 个确认点是合理的，但不建议每次都强制出现。更适合的策略是：

- 低置信度元素触发元素确认
- 测试点依赖低置信度元素时触发测试点确认
- 高风险发布或回归门禁触发风险决策确认

这样可以避免“自动化反而更慢”。

### 4. Data Generation 应按确定性服务设计

`data-generation-agent` 不应该先设计成“LLM 生成器”，而应该先成为：

- 模板驱动的数据生成器
- 关系图驱动的数据编排器
- 生成后校验器
- 脱敏器
- 清理与追溯注册器

AI 如果参与，也只能作为模板推荐或边界值建议，不能直接产出未校验的测试数据。

### 5. 当前最需要补的不是“重新设计整个系统”

更准确的结论是：

- 主架构方向是对的，不需要推倒重来。
- 需要重做的是“能力边界”和“优先级排序”。
- 现阶段应该优先补 `data-generation-agent`、测试点中间层、执行调度任务模型和证据治理。
- 只有在这些确定性底座稳定后，AI 编排层才值得继续扩展。

---

## 当前现实一句话总结

当前仓库距离这份“企业级能力标准”还有明显距离，但方向基本正确。

更准确的判断是：

- 这份文档可以继续作为目标标准保留。
- 不能把它当成当前能力承诺。
- 当前最关键的是先补齐确定性底座，再逐步让各 Agent 向企业级标准逼近。

---

*文档版本：1.1*
*创建日期：2026-03-21*
*最后更新：2026-03-21*
*维护团队：AI Quality Assurance Platform Core Team*
