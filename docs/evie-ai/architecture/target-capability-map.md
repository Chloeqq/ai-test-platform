# EvieAi 目标能力地图

日期：2026-07-12
状态：Authoritative
适用范围：EvieAi 完整目标能力空间、领域边界、阶段路线、能力追踪和架构偏差检查

本文概括 EvieAi 的完整目标能力空间，来源于：

- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/natural-language-test-assets.md`
- EvieAi 架构图：`docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
- Excel 完整设计参考：`docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`

本文只描述长期目标能力，不自动扩大当前阶段实施范围。

当前阶段具体建设内容，以 `docs/evie-ai/implementation/` 下对应阶段文档为准。

---

## 1. 文档定位

本文用于回答：

- EvieAi 最终需要具备哪些能力
- 每个架构域负责什么
- 各领域主要有哪些实体、对象和事实源
- 哪些能力属于当前阶段，哪些属于后续阶段
- 当前实现是否偏离完整目标架构
- Excel、架构图和 Phase 文档之间如何分工

本文不是：

- 当前提交的代码任务单
- 当前 Migration 的表清单
- 当前 API 的完整接口契约
- 当前 Phase 的验收标准
- 所有对象必须立即落成数据库表的强制要求

本文列出的“实体 / 对象”可能是：

- 持久化实体
- 版本对象
- 领域值对象
- 事件
- 快照
- 任务
- 策略
- 逻辑能力接口

是否落表、何时落表、如何拆表，以对应阶段实施文档和数据模型专题为准。

---

## 2. 使用规则

### 2.1 核心规则

```text
Excel 定义完整目标空间
架构图定义领域和主链关系
架构专题定义领域边界
Phase 文档定义本次实施边界
```

### 2.2 冲突优先级

发生冲突时，按以下优先级判断：

1. 用户本次明确确认的决策
2. `AGENTS.md`
3. 当前阶段实施文档
4. EvieAi 架构专题文档
5. 本文
6. EvieAi 架构图
7. Excel 完整设计参考
8. 旧文档
9. 旧代码现状

旧文档只能用于历史和迁移分析。

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

### 2.3 阶段边界

完整能力地图不得自动扩大当前任务范围。

例如：

- Excel 中存在 `ConversionAttempt`，不代表 Phase 0 必须创建该表。
- 架构图中存在 Runner，不代表资产模型提交可以修改 Runner。
- 能力地图中存在语义去重，不代表 Phase 0 必须实现向量检索。
- 目标模型中存在 `project_id`，不覆盖 Phase 0 已确认使用 `TestProject.project_code` 的决策。

---

## 3. 阶段定义

为避免“长期目标”和“当前建设”混淆，本文使用以下阶段定义。

### Phase 0：领域模型基线

目标：

- 建立 Requirement 和自然语言 TestAsset 的最小持久化基础
- 建立版本和来源关系
- 建立统一 ID 扩展
- 建立 Migration、Repository 和架构守卫

包含：

- Requirement
- RequirementVersion
- TestAsset
- TestAssetVersion
- TestAssetSource
- ID
- ORM
- Schema
- Repository
- Migration
- 架构守卫
- 对应测试

不包含完整 Intake、AI 生成、Asset-to-Case、TestCase 和前端。

### Phase 1：自然语言资产生命周期

目标：

- 提供手工或 API 资产录入
- 建立统一资产入库服务
- 提供资产编辑、版本、审核、软删除和来源查询
- 建立幂等和精确重复处理

主要能力：

- TestAssetIntakeService
- 资产列表、详情和版本
- 编辑生成新版本
- 审核记录
- 幂等
- 精确重复
- 资产来源
- 审计
- 基础质量评估

### Phase 2：多元输入与 AI 生成

目标：

- 把需求文档、OpenAPI、缺陷、日志等输入接入统一自然语言资产主线
- 建立 GenerationContext、GenerationBatch 和 ModelRun
- AI 只生成自然语言资产

主要能力：

- Input Adapter
- 文档与来源版本
- GenerationContext
- GenerationBatch
- ModelRun
- Prompt和模型版本
- AI输出Schema校验
- 异步智能评估
- 疑似语义重复

### Phase 3：Asset-to-Case

目标：

- 建立唯一自然语言转机器语言入口
- 建立资源需求、资源绑定、Bound Plan 和统一转换质量门
- 生成版本化 TestCase

主要能力：

- ConversionAttempt
- 场景识别
- ExecutionRequirementManifest
- ResourceCapabilityGateway
- ResourceResolutionDecision
- ResourceBindings
- ResourceBindingSnapshot
- BoundExecutionPlan
- 测试矩阵展开
- QualityGate
- CompilerRouter
- TestCase / TestCaseVersion

### Phase 4：执行、证据与反馈治理

目标：

- 建立完整测试计划、调度、执行、证据、报告和 Flaky 治理

主要能力：

- TestSuite
- TestPlan
- TestCampaign
- Scheduler
- Reservation
- RunnerRouter
- Execution
- ExecutionStepResult
- RetryAttempt
- CleanupResult
- Evidence
- Report
- Flaky
- Quarantine
- FailureAnalysis

### Phase 5+：企业治理和规模化

目标：

- 强化租户、AI治理、成本、数据安全、覆盖分析、迁移、容量和灾备

主要能力：

- 租户治理
- 资源容量
- AI评估中心
- 成本治理
- 数据保留
- Legal Hold
- 大规模迁移
- 多Runner
- 高可用
- 灾备

阶段名称用于能力规划，不替代实际项目排期。

---

## 4. 目标能力总览

| 架构域 | 核心目标 | 主要实体 / 对象 | 主要阶段 | 设计来源 |
|---|---|---|---|---|
| 1. 多元输入与自然语言生成域 | 多来源接入、上下文建立、AI自然语言生成、统一提交资产入库 | SourceRecord、SourceDocument、DocumentVersion、DocumentSection、SourceDocumentPage、GenerationContext、GenerationBatch、ModelRun、PromptVersion | Phase 2 | Excel 01/02、架构图 |
| 2. 自然语言测试资产域 | 统一入库、版本、来源、审核、幂等、重复治理、资产中心 | Requirement、RequirementVersion、TestAsset、TestAssetVersion、TestAssetSource、AssetReviewRecord、DuplicateRelation、AssetQualityAssessment | Phase 0/1/2 | Excel 03、ID字典、状态枚举 |
| 3. Asset-to-Case 转换域 | 资产版本锁定、执行需求分析、资源解析、Bound Plan、质量门、编译和用例构建 | ConversionAttempt、ExecutionRequirementManifest、ResourceResolutionDecision、ResourceBinding、ResourceBindingSnapshot、BoundExecutionPlan、CompilerRun、CaseBuildResult | Phase 3 | Excel 04、字段传递链 |
| 4. 公共资源与能力域 | 统一资源网关、版本化资源、健康和治理策略 | ResourceDescriptor、ResourceVersion、PageObject、PageObjectVersion、DataProfile、Environment、CredentialRef、MockProfile、FaultProfile、SecurityProfile、PerformanceProfile、AtomicCapability、Policy | Phase 3+ | Excel 05 |
| 5. 测试用例、执行、证据与反馈域 | 版本化用例、计划、调度、资源预占、Runner、步骤结果、证据、报告、Flaky和失败归因 | TestCase、TestCaseVersion、TestSuite、TestPlan、TestCampaign、ExecutionJob、Execution、ExecutionStepResult、RetryAttempt、CleanupResult、Evidence、Report、FlakyRecord、QuarantineRecord | Phase 3/4 | Excel 06、16/17/18 |
| 6. 平台控制面 | 项目/租户作用域、ID、Trace、审计、异步任务、事件、RBAC、Feature Flag、AI治理、发布追踪 | Project、Tenant、TraceContext、AuditEvent、Job、DomainEvent、FeatureFlag、ModelRegistry、PromptRegistry、Release、Build、Deployment | 分阶段 | Excel 07、19/20/21 |
| 7. 技术基础设施域 | 数据库、缓存、对象存储、MQ、Worker、CI/CD、可观测性、配置、密钥、备份和灾备 | MySQL/PostgreSQL、Redis、ObjectStorage、MQ、Worker、Vault/KMS、Monitoring、Backup、DR | 复用/持续建设 | Excel 08 |

---

# 5. 多元输入与自然语言生成域

## 5.1 能力目标

该领域负责把不同来源转化为统一的自然语言资产输入。

输入包括：

- 需求文档
- OpenAPI
- 缺陷
- 日志
- 业务规则
- 验收标准
- 手工录入
- API提交
- CI提交
- 批量导入

## 5.2 两类入口

### AI生成入口

```text
需求文档 / OpenAPI / 缺陷 / 日志
→ Input Adapter
→ GenerationContext
→ AI自然语言生成
→ TestAssetIntakeService
```

### 直接资产入口

```text
手工 / API / CI / 批量导入
→ TestAssetIntakeService
```

AI 不是所有资产的必经入口。

## 5.3 核心能力

- 输入适配器
- 来源规范化
- 来源版本
- GenerationContext
- GenerationBatch
- ModelRun
- Prompt版本
- AI输出Schema校验
- Token、成本和延迟记录
- 安全和PII处理
- 异步任务
- 重试和Fallback
- 输出直接进入统一资产入库

## 5.4 主要对象

```text
SourceRecord
SourceDocument
DocumentVersion
DocumentSection
SourceDocumentPage
GenerationContext
GenerationBatch
ModelRun
PromptVersion
ModelConfiguration
```

## 5.5 边界

不得：

- 生成机器步骤
- 解析Locator
- 创建TestCase
- 调用Compiler
- 调用Runner
- 生成script_code
- 自行保存Candidate业务实体

---

# 6. 自然语言测试资产域

## 6.1 能力目标

该领域负责自然语言资产的统一身份、内容版本、来源、审核和生命周期。

## 6.2 能力分解

### Phase 0

- Requirement
- RequirementVersion
- TestAsset
- TestAssetVersion
- TestAssetSource
- ID
- ORM、Schema、Repository、Migration
- current_version一致性
- 架构守卫

### Phase 1

- TestAssetIntakeService
- 手工/API录入
- 幂等
- 精确重复
- 来源绑定
- 列表、详情、版本
- 编辑
- 软删除
- 审核
- 审计

### Phase 2

- 疑似语义重复
- 异步质量评估
- 场景建议
- 自动化适配建议
- 质量标签
- 多来源扩展

## 6.3 主要对象

```text
Requirement
RequirementVersion
TestAsset
TestAssetVersion
TestAssetSource
AssetReviewRecord
AssetQualityAssessment
DuplicateRelation
IdempotencyRecord
```

## 6.4 关键规则

- TestAsset表达“测什么”
- 正文只保存在TestAssetVersion
- 历史版本不可覆盖
- 低质量资产仍然入库
- 疑似语义重复不阻断入库
- 内容Hash不阻止恢复历史内容
- review_status和conversion_status独立
- Candidate不是业务实体

---

# 7. Asset-to-Case 转换域

## 7.1 能力目标

该领域是自然语言转机器语言的唯一入口。

## 7.2 核心链路

```text
TestAssetVersion
→ ConversionAttempt
→ ScenarioAnalysis
→ ExecutionRequirementManifest
→ ResourceCapabilityGateway
→ ResourceResolutionDecision
→ ResourceBindings
→ ResourceBindingSnapshot
→ BoundExecutionPlan
→ VariantMatrix
→ ConversionQualityGate
→ CompilerRouter
→ TestCase
→ TestCaseVersion
```

## 7.3 主要能力

- TestAssetVersion锁定
- ConversionAttempt生命周期
- 场景识别
- 执行需求分析
- Manifest
- 资源解析
- 等待资源处理
- 绑定快照
- 矩阵展开
- 转换质量门
- Compiler路由
- Case构建
- 输入/Manifest/BoundPlan/script哈希
- 失败诊断
- 可重试转换

## 7.4 主要对象

```text
ConversionAttempt
ScenarioAnalysis
ExecutionRequirementManifest
ResourceResolutionDecision
ResourceBinding
ResourceBindingSnapshot
BoundExecutionPlan
VariantMatrix
ConversionQualityReport
CompilerRun
CaseBuildResult
```

## 7.5 边界

- 转换必须锁定明确TestAssetVersion
- 资源必须通过Gateway访问
- Compiler只读取BoundPlan
- 转换失败不得修改TestAssetVersion
- 不创建无效TestCaseVersion
- TestAsset.conversion_status不能替代ConversionAttempt事实

---

# 8. 公共资源与能力域

## 8.1 能力目标

该领域向Asset-to-Case提供版本化、可解析、可审计的执行资源。

## 8.2 资源类别

- 页面对象
- 页面元素
- 测试数据
- 环境
- 凭证
- Mock
- 异常注入
- 安全能力
- 性能能力
- 原子能力
- 业务规则和治理策略

## 8.3 核心能力

- ResourceCapabilityGateway
- 资源描述和版本
- 资源所有权
- 资源健康
- 资源兼容性
- 资源解析策略
- 资源替代策略
- 容量
- 可用性
- 维护窗口
- 资源审计
- 资源废弃和迁移

## 8.4 主要对象

```text
ResourceDescriptor
ResourceVersion
ResourceHealth
ResourceOwnership
PageObject
PageObjectVersion
PageElement
PageElementVersion
DataProfile
DataFactoryPolicy
Environment
CredentialRef
MockProfile
FaultProfile
SecurityProfile
PerformanceProfile
AtomicCapability
ResourcePolicy
```

## 8.5 边界

Asset-to-Case不得直接查询具体资源表并自行解释资源。

资源访问必须经过：

```text
ResourceCapabilityGateway
```

凭证只能保存引用，不保存明文。

---

# 9. 测试用例、执行、证据与反馈域

## 9.1 测试用例能力

- TestCase稳定身份
- TestCaseVersion
- script_code
- compiler版本
- BoundPlan哈希
- ResourceBindingSnapshot
- ready / stale / disabled生命周期
- 资产、资源变化后的stale传播

## 9.2 测试组织能力

- TestSuite
- TestPlan
- TestCampaign
- TestPlanExecution
- Release / Build关联
- 环境和数据组合
- 选择、过滤和分组

## 9.3 资源预占能力

- DataReservation
- EnvironmentReservation
- Capacity
- MaintenanceWindow
- CredentialLease
- 冲突检测
- 超时释放
- 清理

## 9.4 执行能力

- Scheduler
- ExecutionControl
- RunnerRouter
- ExecutionJob
- Execution
- ExecutionStepResult
- RetryAttempt
- CleanupResult
- Cancel / Pause / Timeout
- 并发和限流

## 9.5 证据与报告

- Screenshot
- Video
- Network Record
- Log
- Trace
- Evidence
- Report
- 脱敏
- 保留周期
- 下载和访问控制

## 9.6 反馈治理

- FailureAnalysis
- FailureAttribution
- RepairRecommendation
- FlakyRecord
- QuarantineRecord
- ReviewTask
- ResourceGovernanceEvent

## 9.7 边界

- `TestCaseVersion.script_code` 是可执行代码唯一事实源
- Runner只执行，不重新理解自然语言
- 失败分析不得直接覆盖版本化事实源
- Report由执行事实派生

---

# 10. 平台控制面

## 10.1 作用域和隔离

- Tenant
- Project
- project_code
- 数据隔离
- 权限隔离
- 配置隔离
- 审计隔离

Phase 0继续复用`TestProject.project_code`。

## 10.2 ID和追踪

- 统一业务ID
- request_id
- trace_id
- batch_id
- job_id
- event_id
- execution_id
- 版本ID
- 外部ID与内部ID分离

## 10.3 审计

- actor
- action
- aggregate
- before/after
- reason
- trace
- timestamp
- 数据分类

## 10.4 异步任务和事件

- Job
- DomainEvent
- Outbox
- 幂等消费
- 重试
- Dead Letter
- Schema版本
- 任务状态
- 取消

## 10.5 认证授权

- RBAC
- 项目权限
- 资源权限
- 数据分类权限
- Secret访问权限
- 审计权限

## 10.6 Feature Flag和API治理

- FeatureFlag
- API Gateway
- BFF
- API版本
- Schema版本
- 兼容策略
- 限流
- 配额

## 10.7 AI治理

- Model Registry
- Provider
- Prompt Registry
- PromptVersion
- Parameters
- Token Usage
- Cost
- Latency
- Fallback
- Schema Validation
- Safety Result
- PII处理
- Evaluation
- 质量基线

## 10.8 发布追踪

- Release
- Build
- Deployment
- Commit
- Artifact
- ServiceVersion
- TestPlan和Execution关联

---

# 11. 技术基础设施域

## 11.1 数据基础设施

- MySQL / PostgreSQL
- Redis
- Object Storage
- Schema Migration
- 备份
- 恢复
- 数据归档

## 11.2 消息与任务

- MQ
- Worker
- Task Queue
- Scheduler Infrastructure
- Dead Letter Queue
- Outbox
- 消费幂等

## 11.3 部署与交付

- Docker
- Kubernetes
- CI/CD
- Artifact Registry
- 环境配置
- 灰度和回滚

## 11.4 可观测性

- Log
- Metrics
- Trace
- Alert
- Dashboard
- SLO
- 容量
- 成本

## 11.5 配置与密钥

- Config Center
- Vault
- KMS
- Secret Rotation
- Credential Audit

## 11.6 可用性和灾备

- High Availability
- Backup
- Restore Drill
- Disaster Recovery
- RPO / RTO
- Capacity Planning
- Rate Limit
- Auto Scaling

---

# 12. 横向能力 A：版本与唯一事实源

| 业务事实 | 唯一事实源 |
|---|---|
| 需求正文 | RequirementVersion |
| 当前需求版本 | Requirement.current_version |
| 自然语言资产正文 | TestAssetVersion |
| 当前资产版本 | TestAsset.current_version |
| 来源关系 | TestAssetSource |
| 转换事实 | ConversionAttempt |
| 执行需求 | ExecutionRequirementManifest |
| 资源解析决策 | ResourceResolutionDecision |
| 资源绑定 | ResourceBindingSnapshot |
| 编译输入 | BoundExecutionPlan |
| 可执行代码 | TestCaseVersion.script_code |
| 执行结果 | Execution / ExecutionStepResult |
| 证据 | Evidence |
| 报告 | 由执行事实派生 |

必须避免：

- 正文双写
- 状态双写
- script_code双写
- 版本原地覆盖
- 缓存代替事实源
- Runner重新推导执行逻辑

---

# 13. 横向能力 B：覆盖与端到端追溯

完整追踪链：

```text
Requirement
→ RequirementVersion
→ RequirementItem / AcceptanceCriterion / BusinessRule
→ CoverageRelation
→ TestAsset
→ TestAssetVersion
→ ConversionAttempt
→ TestCase
→ TestCaseVersion
→ Execution
→ Evidence
→ Report
```

目标能力：

- 需求覆盖率
- 验收标准覆盖率
- 业务规则覆盖率
- 资产到用例追踪
- 用例到执行追踪
- 执行到证据追踪
- 需求变更影响分析
- 资产变更stale传播
- 资源变更stale传播
- Release/Build覆盖报告

主要对象：

```text
RequirementItem
AcceptanceCriterion
BusinessRule
CoverageRelation
CoverageMetric
ImpactAnalysis
```

---

# 14. 横向能力 C：状态模型

状态必须按生命周期拆分。

## 14.1 Requirement

```text
draft / active / closed / archived
```

## 14.2 RequirementVersion

```text
draft / effective / superseded / removed
```

## 14.3 TestAsset审核

```text
pending / approved / rejected
```

## 14.4 TestAsset转换

```text
not_started / processing / blocked / succeeded / stale
```

## 14.5 ResourceBinding

```text
resolved / partial / blocked / unavailable
```

## 14.6 TestCase

```text
ready / stale / disabled
```

## 14.7 Execution

```text
queued / running / passed / failed / cancelled / timed_out / blocked
```

不得使用单一`status`表达多个生命周期。

---

# 15. 横向能力 D：通用字段规范

领域表应按需要统一考虑：

```text
tenant_id
project_code
business_id
schema_version
trace_id
created_at
created_by
updated_at
updated_by
deleted_at
row_version
data_classification
```

并非所有字段都必须在Phase 0立即加入。

当前阶段字段以Phase实施文档为准。

规则：

- 业务ID与数据库PK分离
- 时间统一UTC
- 版本对象不可原地更新
- 聚合根使用row_version或等价并发控制
- 软删除使用deleted_at
- Secret只保存引用
- JSON不得承载核心外键和状态

---

# 16. 横向能力 E：AI治理与评估

AI治理覆盖：

- 模型注册
- Provider
- Prompt版本
- 参数
- Token
- 成本
- 延迟
- Fallback
- Schema校验
- 安全校验
- PII处理
- 数据分类
- 离线评估
- 在线质量指标
- 回归数据集
- 人工评审
- 规则版本

主要对象：

```text
ModelRegistry
ModelConfiguration
PromptTemplate
PromptVersion
ModelRun
EvaluationDataset
EvaluationRun
EvaluationMetric
SafetyResult
```

AI生成结果不是权威ID和权威状态来源。

---

# 17. 横向能力 F：数据安全、保留与删除

能力包括：

- 数据分类
- PII识别
- 脱敏
- 加密
- Secret引用
- 访问控制
- 审计
- 保留策略
- 删除策略
- 归档
- Legal Hold
- 备份保留
- 证据生命周期
- Prompt和模型响应治理

主要对象：

```text
DataClassification
RetentionPolicy
DeletionRequest
DeletionJob
LegalHold
MaskingPolicy
CredentialRef
```

不得在TestAsset、script_code、Prompt、日志、证据和报告中保存明文Secret。

---

# 18. 横向能力 G：旧平台迁移

迁移目标：

- 旧Candidate链冻结
- 旧TestPointAsset分析
- 旧文档归档
- 旧ID映射
- 旧资产迁移
- 新旧数据对账
- 双读或影子验证
- 切换入口
- 退役旧链
- 保留审计和回滚依据

主要对象：

```text
MigrationRun
LegacyMapping
MigrationBatch
MigrationError
ReconciliationResult
CutoverPlan
RollbackPlan
```

迁移原则：

- 先冻结，后迁移
- 不直接删除
- 先建立映射
- 必须可对账
- 必须保留历史来源
- 不把Candidate继续迁移成新主链概念
- 不把旧structured_steps写入TestAssetVersion
- 旧可执行脚本按TestCaseVersion迁移，不写入自然语言资产

---

# 19. 当前 Phase 0 边界

EvieAi Phase 0 是完整目标架构的最小领域模型切片。

Phase 0 只实施：

- Requirement
- RequirementVersion
- TestAsset
- TestAssetVersion
- TestAssetSource
- ID扩展
- ORM
- Schema
- Repository
- Alembic Migration
- 架构守卫
- 对应测试
- 权威文档

Phase 0 不实施：

- AI生成链路改造
- 输入适配器
- GenerationContext
- Candidate迁移
- 完整Intake
- 幂等服务
- 精确重复服务
- 语义去重
- 异步智能评估
- Asset-to-Case
- ConversionAttempt
- Manifest
- ResourceCapabilityGateway
- ResourceBindingSnapshot
- BoundPlan
- Compiler
- TestCase
- TestPlan
- Scheduler
- Runner
- Evidence
- Report
- 前端资产中心
- 旧数据迁移
- 旧链删除

Phase 0 额外确认：

- 使用`TestProject.project_code`
- 不新增Project表
- 不新增`project_id / project_uuid`
- 不新增`intent_id`
- TestAssetSource只支持Requirement来源
- 不预建Document/Page/Generation占位字段
- 核心业务ID使用`<prefix>_<uuid4hex32>`
- current_version由Repository事务维护
- 历史版本不可原地覆盖

---

# 20. Excel 的正确职责

Excel 主要回答：

- EvieAi 最终需要哪些能力
- 每个领域有哪些节点
- 输入、输出和依赖是什么
- 每个领域有哪些实体和 ID
- 状态如何定义
- 字段如何跨链路传递
- 后续需要建设哪些资源和治理能力
- 当前阶段是否偏离总体目标
- 旧平台如何迁移

Excel 不直接回答：

- 当前提交必须修改哪些文件
- 当前 Migration 必须创建哪些表
- 当前阶段必须实现哪些接口
- 当前任务是否允许新增依赖
- 当前代码应如何拆分提交

这些内容由：

- 用户当前确认
- `AGENTS.md`
- 当前阶段实施文档
- `coding-standards.md`

共同决定。

---

# 21. 架构一致性检查

每个Phase完成后，应使用本文检查：

## 21.1 边界检查

- 生成侧是否仍只生成自然语言
- 资产域是否出现机器字段
- Asset-to-Case是否仍是唯一转换入口
- Runner是否重新理解自然语言
- 资源是否绕过Gateway直接访问

## 21.2 事实源检查

- 正文是否双写
- script_code是否双写
- 版本是否被原地覆盖
- current_version是否一致
- 派生结果是否覆盖事实源

## 21.3 状态检查

- review_status和conversion_status是否分离
- TestCase状态是否独立
- Execution状态是否独立
- 非法状态转换是否被拒绝

## 21.4 追溯检查

- RequirementVersion能否追踪到TestAssetVersion
- TestAssetVersion能否追踪到ConversionAttempt
- TestCaseVersion能否追踪到BoundPlan和资源快照
- Execution能否追踪到TestCaseVersion和Evidence

## 21.5 工程检查

- 是否新增硬编码
- 是否重复配置
- 是否缺少事务
- 是否绕过Repository
- 是否新增历史违规
- 是否扩大当前Phase范围

---

# 22. 结论

EvieAi 完整能力空间由七个架构域和多个横向治理能力组成。

核心主链是：

```text
多元输入
→ 自然语言资产生产
→ 统一资产入库
→ 版本化TestAsset
→ Asset-to-Case
→ 资源能力网关
→ ResourceBindingSnapshot
→ BoundExecutionPlan
→ TestCaseVersion.script_code
→ Runner
→ Execution / Evidence / Report
→ 失败归因和受控治理
```

能力地图的作用是保证长期方向完整。

Phase 文档的作用是保证当前建设范围可控。

任何实施不得因为完整能力地图中存在某项能力，就在未经确认的情况下将其加入当前任务。
