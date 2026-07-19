# EvieAi 目标能力地图

日期：2026-07-18
状态：Authoritative
适用范围：EvieAi 完整目标能力空间、领域边界、阶段路线、能力追踪和架构偏差检查

本文概括 EvieAi 的完整目标能力空间，来源于：

- `docs/evie-ai/decisions/ADR-0002-target-architecture-v2.md`
- `docs/evie-ai/ARCHITECTURE_BASELINE.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- EvieAi Target Architecture v2 Mermaid：`docs/evie-ai/reference/2026-07-18_evie-ai-target-architecture-v2.mmd`
- EvieAi Target Architecture v2 PNG：`docs/evie-ai/reference/2026-07-18_evie-ai-target-architecture-v2.png`
- Excel 完整设计参考：`docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`

`docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
仅作为历史演进参考，不再作为当前 Target Architecture v2 的主表达。

本文只描述长期目标能力，不自动扩大当前阶段实施范围。

当前阶段具体建设内容，以 `docs/evie-ai/implementation/` 下对应阶段文档为准。

本文登记的长期能力包含 `Accepted target` 和 `Planned` 项，
但它们不代表已实现，也不单独授权进入当前 Phase 实施。

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
ADR-0002 治理长期目标架构
ARCHITECTURE_BASELINE 统一收编解释
overview 与本文登记目标能力和规划检查点
Mermaid / PNG 负责可视化表达
Excel 提供完整目标空间和设计参考
Phase 文档定义本次实施边界
```

### 2.2 目标架构解释与实施授权

#### 2.2.1 Target Architecture 语义解释顺序

用于解释长期目标架构时，应按以下顺序理解：

```text
ADR-0002 Accepted decision
→ ARCHITECTURE_BASELINE consolidated interpretation
→ evie-ai-overview
→ target-capability-map
→ Mermaid source
→ PNG rendering
→ Excel design reference
```

必须明确：

- `AGENTS.md` 继续是仓库硬约束。
- 本文不得扩展 `ADR-0002`。
- 图和 Excel 不能批准技术选型。
- 当前文件状态 `Authoritative` 只表示它是目标能力登记入口，不表示它能够授权实施。

旧文档只能用于历史和迁移分析。

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

#### 2.2.2 Current Implementation Authorization

判断某项能力是否允许进入当前实现时，必须同时满足：

1. 用户对当前任务的明确授权
2. `AGENTS.md`
3. 当前有效的 Phase ADR
4. 当前有效的 Phase Specification
5. 当前有效的 Phase Implementation Plan
6. 必要的专题 ADR
7. 仓库已有工程约束

必须明确：

- Target Architecture、Baseline、overview 和 capability map 可以定义长期方向。
- 它们不能单独扩大当前 Phase。
- capability map 中的 `Recommended Phase` 不是实施授权。
- 当长期目标能力尚未进入当前 Phase 合同时，不得实施。
- 当前 Phase 合同也不得违反 Accepted ADR 和 Architecture Baseline。
- 若二者发生真实冲突，必须停止并修订文档，不能自行选择。

### 2.3 阶段边界

完整能力地图不得自动扩大当前任务范围。

例如：

- Excel 中存在 `ConversionAttempt`，不代表 Phase 0 必须创建该表。
- 架构图中存在 Runner，不代表资产模型提交可以修改 Runner。
- 能力地图中存在语义去重，不代表 Phase 0 必须实现向量检索。
- 目标模型中存在 `project_id`，不覆盖 Phase 0 已确认使用 `TestProject.project_code` 的决策。
- 本文中的 `Recommended Phase` 只是规划建议，不代表 `phase-traceability` 或对应 Phase 合同已经批准。
- 本文新增的 `Accepted target` / `Planned` 能力不会自动扩大 Phase 1。

### 2.4 能力状态口径

- `Accepted contract / Active phase scope`：已由 ADR、Specification 或 Implementation Plan 批准，当前仍是有效实施边界，不代表所有能力已经实施完成。
- `Verified implemented`：已有代码、Migration、Repository、测试或 Slice 验收证据；具体完成范围可由 `phase-traceability` 和验收记录核实，不得仅根据计划文档标记。
- `In progress`：对应 Phase 或能力仍在实施，尚未完成正式 Closeout。
- `Historical implemented`：只能用于已经有明确历史实现证据的单项能力，不得用它概括整个 Phase 1。
- `Accepted target`：已进入 Accepted Target Architecture，但不代表已实现。
- `Planned`：已登记为后续能力，等待后续 Phase 合同。
- `Requires ADR`：需要专题 ADR 或等价专题设计先行澄清。
- `Deferred technology selection`：高层能力已接受，但具体产品和技术方案尚未批准。

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

Phase 1 contract status: Accepted / Active
Phase 1 overall status: In Progress
Phase 1 closeout status: Not completed

`ADR-0001`、Phase 1 Specification 和 Phase 1 Implementation Plan 已批准。
Phase 1 的部分 Slice、Migration、Repository 和生命周期能力已经实施。
已完成部分以 `phase-traceability`、Slice 验收记录、测试和代码事实为准。
以下列出的是 Phase 1 合同能力范围，不表示全部能力已经完成。
在正式 Closeout 并获得明确批准前，不得宣布 Phase 1 已完成，
当前也不得宣布已正式进入 Phase 2 实施。

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

本文后续如标记 `Recommended Phase`，均只表示规划建议，
不替代正式 Phase 合同，也不修改 `phase-traceability`。

---

## 4. 目标能力总览

### 4.1 当前 Target Architecture v2 逻辑区域

| 当前逻辑区域 | 核心目标 | 章节承接 | 主要阶段 | 设计来源 |
|---|---|---|---|---|
| 1. 用户与调用方 | 产品经理、测试人员、开发人员、平台管理员、CLI / SDK / API Client 与通知接收方等访问与交付对象 | 第 9 章、第 10 章 | 分阶段 | overview、架构图 |
| 2. 边缘与接入层 | 认证、项目作用域、上传接入、安全校验、异步查询和流式结果交付入口 | 第 5 章、第 10 章 | Phase 2+ / Cross-phase | overview、架构图 |
| 3. 多元输入与需求智能域 | 多来源接入、Requirement Knowledge RAG、TestPointEvidencePack、AI 自然语言生成 | 第 5 章 | Phase 2 | overview、架构图 |
| 4. 自然语言测试资产域 | 统一入库、版本、来源、审核、幂等、重复治理、资产中心 | 第 6 章 | Phase 0 / Phase 1 / Phase 2 | Phase 文档、overview |
| 5. Asset-to-Case 转换与质量拦截域 | 资产版本锁定、Oracle / Binder、质量门、编译前置检查和用例构建 | 第 7 章 | Phase 3 | ADR-0002、overview |
| 6. 公共资源与能力域 | 统一资源网关、版本化资源、资源策略、绑定输入和变更信号 | 第 8 章 | Phase 3+ | overview |
| 7. 测试用例、执行、证据与反馈域 | 版本化用例、计划、调度、Resource Lease、Runner、Evidence Normalization、Report、失败归因 | 第 9 章 | Phase 3 / Phase 4 | overview、架构图 |
| 8. 大模型与 AI 能力层 | 模型、Prompt、Embedding、评估和 AI 质量治理 | 第 5 章、第 10 章、第 16 章 | Phase 2+ / Cross-phase | overview、架构图 |
| 9. 平台控制面 | 项目 / 租户、ID、Trace、审计、异步任务、权限、Feature Flag、AI 治理、交付治理 | 第 10 章 | 分阶段 | ADR-0002、ARCHITECTURE_BASELINE |
| 10. 数据与知识存储层 | 关系事实、JSONB / Vector / Search / Object Storage 等知识与存储治理 | 第 11 章、第 12 章、第 17 章 | Cross-phase | overview、架构图 |
| 11. 基础设施与运维治理层 | Worker、Queue、部署、可观测性、密钥、备份、灾备和扩缩容 | 第 11 章 | 复用 / 持续建设 | overview、架构图 |

### 4.2 历史七域章节编排视图

以下七域章节编排作为历史能力分组保留，
用于承接既有能力地图、Phase 0 历史基线、Phase 1 已批准合同与已落地事实和旧章节结构。

它们不再单独声称是当前 Target Architecture v2 的主区域划分。
当前目标能力区域以第 4.1 节的 11 个逻辑区域为准。

| 历史章节编排 | 当前逻辑区域映射 | 说明 |
|---|---|---|
| 第 5 章：多元输入与自然语言生成域 | 2, 3, 8, 9, 10 | 保留旧章节名，承接输入、RAG、AI 生成和接入治理 |
| 第 6 章：自然语言测试资产域 | 4 | 与当前目标模型直接对应 |
| 第 7 章：Asset-to-Case 转换域 | 5 | 与当前目标模型直接对应 |
| 第 8 章：公共资源与能力域 | 6 | 与当前目标模型直接对应 |
| 第 9 章：测试用例、执行、证据与反馈域 | 7 | 与当前目标模型直接对应 |
| 第 10 章：平台控制面 | 1, 2, 9 | 继续承接作用域、权限、异步和交付治理 |
| 第 11 章：技术基础设施域 | 10, 11 | 历史章节名保留，当前职责拆分到数据与知识存储层和基础设施治理层 |

### 4.3 本次补充登记的规划检查点

| 规划检查点 | 当前逻辑区域 | 状态 | Recommended Phase | ADR / 说明 |
|---|---|---|---|---|
| Upload Security | 2, 9, 10, 11 | Accepted target / Planned / Deferred technology selection / 不代表已实现 | Phase 2 | 需要接入与上传安全专题设计 |
| Async status and streaming delivery | 2, 7, 9 | Accepted target / Planned / Deferred technology selection / 不代表已实现 | AI / conversion：Phase 2 / Phase 3；execution：Phase 4；overall：Cross-phase | SSE / WebSocket 仅为候选传输方式 |
| TestPointEvidencePack | 3, 8, 9, 10 | Accepted target / Planned / Requires ADR / Deferred technology selection / 不代表已实现 | Phase 2 | Requires RAG and Knowledge Governance ADR |
| Oracle / Binder result governance | 5, 6 | Accepted target / Planned / Requires ADR / 不代表已实现 | Phase 3 | Requires Asset-to-Case Compiler Architecture ADR |
| Execution governance | 6, 7, 9, 11 | Accepted target / Planned / Requires ADR / 不代表已实现 | Binding Stale：Phase 3 / Phase 4；others：Phase 4 | Requires Multi-platform Execution and Evidence Governance ADR |
| Embedding Service and AI quality metrics | 8, 9, 10 | Accepted target / Planned / Requires ADR / Deferred technology selection / 不代表已实现 | Embedding Service：Phase 2；metrics：Phase 3 / Phase 5；overall：Cross-phase | Requires AI Platform ADR；Requires Evaluation and Quality Governance design |
| Notification, subscription and report push | 1, 2, 7, 9 | Accepted target / Planned / Requires ADR / Deferred technology selection / 不代表已实现 | Phase 4；enterprise governance：Phase 5 | Requires Access and Delivery Architecture design |
| Data and knowledge architecture governance checklist | 9, 10, 11 | Accepted target / Planned / Requires ADR / Deferred technology selection / 不代表已实现 | Cross-phase / ADR prerequisite | Requires Data and Knowledge Architecture ADR |

---

# 5. 多元输入与自然语言生成域

本章沿用历史章节名，但当前主要对应：

- 2. 边缘与接入层
- 3. 多元输入与需求智能域
- 8. 大模型与 AI 能力层
- 9. 平台控制面
- 10. 数据与知识存储层

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
- Upload Security
- Requirement Knowledge RAG
- TestPointEvidencePack
- 输出直接进入统一资产入库

### 5.3.1 Upload Security

- 当前逻辑区域：2. 边缘与接入层；横向依赖 9. 平台控制面、10. 数据与知识存储层、11. 基础设施与运维治理层。
- 状态：Accepted target；Planned；Deferred technology selection；不代表已实现。
- Recommended Phase: Phase 2。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- 需要接入与上传安全专题设计。

能力边界：

- `File Upload Validation`：文件类型、大小、文件名与内容类型一致性检查。
- `Upload Security Scanning`：恶意文件或风险内容扫描。
- `Upload Quarantine / Rejection`：风险文件隔离或拒绝，保持 fail closed。
- `Upload Audit`：上传来源、处理结果、项目作用域和审计追踪记录。
- 上传入口必须验证项目作用域，不得跳过 project scope 校验。
- 当前不批准具体杀毒产品、WAF、对象存储或扫描引擎。

规划依赖：

```text
Upload Security
→ project scope
→ object or file storage
→ Intake / Requirement import
```

### 5.3.2 Requirement Knowledge RAG 与 TestPointEvidencePack

- 当前逻辑区域：3. 多元输入与需求智能域；横向依赖 8. 大模型与 AI 能力层、9. 平台控制面、10. 数据与知识存储层。
- 状态：Accepted target；Planned；Requires ADR；Deferred technology selection；不代表已实现。
- Recommended Phase: Phase 2。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires RAG and Knowledge Governance ADR。

`TestPointEvidencePack` 的逻辑职责包括：

- `RequirementVersion` 引用
- 来源文档引用
- 来源片段引用
- 来源类型
- 版本信息
- 检索得分或权重
- 项目和权限作用域
- 生成 Trace
- 到自然语言测试点的可追溯关系

边界：

- `TestPointEvidencePack` 不替代 `RequirementVersion`。
- `RequirementVersion` 仍是需求正文唯一事实源。
- `TestPointEvidencePack` 不等于执行域 `Evidence`。
- `TestPointEvidencePack` 不自动表示数据库表。
- 具体 Schema、存储方式、ACL 和生命周期由后续 ADR 决定。
- 当前不批准具体向量数据库、搜索产品或 Embedding Provider。

规划依赖：

```text
来源内容 / RequirementVersion
→ 文本解析与切片
→ Embedding Service / 索引支撑
→ Requirement Knowledge RAG
→ TestPointEvidencePack
→ AI natural-language test-point generation
```

- `Embedding Service / 索引支撑` 是 Requirement Knowledge RAG 的候选支撑方式。
- 具体模型、索引和检索产品尚未批准。
- 并非所有小规模或精确检索场景都必须经过向量检索。
- `TestPointEvidencePack` 是检索和证据组织结果，不是正文事实源。

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

以下是 Phase 0、Phase 1 和 Phase 2 的合同能力范围与规划拆分，
不表示对应 Phase 的全部能力已经完成。

其中 Phase 1 仍为 In Progress，具体已完成范围以 `phase-traceability`、
Slice 验收记录、测试和代码事实为准。

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

本章沿用历史章节名，但当前主要对应：

- 5. Asset-to-Case 转换与质量拦截域
- 横向依赖 6. 公共资源与能力域

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
- Test Oracle Resolution
- Target / Resource Binding
- Binding Result Classification
- Ambiguity Handling
- Unresolved Resource Handling
- Conversion Blocking
- Manual Resolution Entry
- Binding Trace
- Compiler路由
- Case构建
- 输入/Manifest/BoundPlan/script哈希
- 失败诊断
- 可重试转换

### 7.3.1 Oracle / Binder 结果治理

- 当前逻辑区域：5. Asset-to-Case 转换与质量拦截域；横向依赖 6. 公共资源与能力域。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 3。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Asset-to-Case Compiler Architecture ADR。

Binder 目标结果语义：

- `BOUND`
- `AMBIGUOUS`
- `UNRESOLVED`

治理边界：

- `BOUND / AMBIGUOUS / UNRESOLVED` 是目标架构结果语义，不代表数据库枚举、持久化状态机、错误模型或 API 已批准。
- `AMBIGUOUS` 和 `UNRESOLVED` 必须 fail closed。
- 不得通过固定页面、固定环境、固定元素或名称猜测继续绑定。
- `blocked`、`failed`、`needs_review` 或 manual resolution 的最终状态设计由后续专题 ADR 决定。
- `Manual Resolution Entry` 和 `Binding Trace` 可以登记为目标能力，但不在本步骤内推导具体表结构。

规划依赖：

```text
TestAssetVersion
→ Execution Context Retrieval
→ Oracle / Binder
→ BOUND / AMBIGUOUS / UNRESOLVED
→ Compiler / Preflight
→ TestCaseVersion
```

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
- Binding Stale 信号
- Resource Lease 协调输入
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

本章沿用历史章节名，但当前主要对应：

- 7. 测试用例、执行、证据与反馈域
- 横向依赖 6. 公共资源与能力域、9. 平台控制面、11. 基础设施与运维治理层

## 9.1 测试用例能力

- TestCase稳定身份
- TestCaseVersion
- script_code
- compiler版本
- BoundPlan哈希
- ResourceBindingSnapshot
- ready / stale / disabled生命周期
- Binding Stale
- 资产、资源变化后的stale传播

### 9.1.1 Binding Stale

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 6. 公共资源与能力域。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 3 / Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

`Binding Stale` 表示绑定有效性条件，而不是单一状态机字段：

- 资源版本变化
- 页面或元素版本变化
- API Specification 变化
- 环境变化
- 重新绑定或重新编译要求

它可以驱动 `stale` 传播，但不自动批准最终数据库状态设计。

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
- Resource Lease
- 冲突检测
- 超时释放
- 清理

### 9.3.1 Resource Lease

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 6. 公共资源与能力域、9. 平台控制面、11. 基础设施与运维治理层。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

`Resource Lease` 是资源协调机制，涉及：

- 环境
- 设备
- Worker
- 并发占用
- 租约续期
- 超时释放
- 崩溃恢复
- 审计

## 9.4 执行能力

- Scheduler
- ExecutionControl
- RunnerRouter
- ExecutionJob
- Execution
- ExecutionStepResult
- RetryAttempt
- Replay
- CleanupResult
- Cancel / Pause / Timeout
- 并发和限流

### 9.4.1 Replay

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 6. 公共资源与能力域、9. 平台控制面。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

`Replay` 是执行操作，不等于普通重试：

- 复用明确的 `TestCaseVersion`
- 根据策略决定复用已有绑定或重新解析资源绑定
- 保留原始 `Execution`
- 生成新的 `Execution`
- 不覆盖原始 `Evidence`

## 9.5 证据与报告

- Screenshot
- Video
- Network Record
- Log
- Trace
- Evidence
- Report
- Evidence Normalization
- 脱敏
- 保留周期
- 下载和访问控制

### 9.5.1 Evidence Normalization

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 11. 基础设施与运维治理层。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

`Evidence Normalization` 是跨平台证据归一能力，覆盖：

- Web
- API
- Android
- iOS
- 后续 Performance / Security

## 9.6 反馈治理

- FailureAnalysis
- FailureAttribution
- Failure Classification
- Manual Override
- RepairRecommendation
- FlakyRecord
- QuarantineRecord
- ReviewTask
- ResourceGovernanceEvent

### 9.6.1 Failure Classification

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 9. 平台控制面。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

候选分类包括：

- Product Failure
- Test Logic Failure
- Binding Failure
- Resource Failure
- Environment Failure
- Infrastructure Failure
- Timeout
- Flaky
- Unknown

当前这些名称只是能力规划候选，不代表 taxonomy、优先级、自动分类规则或人工纠正流程已经批准。

### 9.6.2 Manual Override

- 当前逻辑区域：7. 测试用例、执行、证据与反馈域；横向依赖 9. 平台控制面。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: Phase 4。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Multi-platform Execution and Evidence Governance ADR。

`Manual Override` 是受控管理动作，必须涉及：

- 权限
- 审批
- 原因
- 审计
- 范围
- 到期或撤销
- 风险提示

`Manual Override` 不得绕过：

- 项目隔离
- Secret 权限
- 安全策略
- Evidence 保存
- 审计

## 9.7 边界

- `TestCaseVersion.script_code` 是可执行代码唯一事实源
- Runner只执行，不重新理解自然语言
- 失败分析不得直接覆盖版本化事实源
- Report由执行事实派生
- `Binding Stale`、`Resource Lease`、`Replay`、`Manual Override`、`Failure Classification`、`Evidence Normalization` 是独立治理能力，不得被压缩成同一个状态字段

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
- 状态查询
- 进度事件
- 断线恢复或重新查询

### 10.4.1 异步状态与实时结果回传

- 当前逻辑区域：2. 边缘与接入层、7. 测试用例、执行、证据与反馈域、9. 平台控制面。
- 状态：Accepted target；Planned；Deferred technology selection；不代表已实现。
- Recommended Phase: AI generation / conversion 为 Phase 2 / Phase 3，execution delivery 为 Phase 4，整体可标记为 Cross-phase。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。

登记的能力包括：

- 异步任务状态查询
- 任务进度事件
- AI 生成进度回传
- 转换任务进度回传
- 执行进度回传
- 实时或准实时结果交付
- 断线后状态恢复或重新查询
- 鉴权和项目作用域
- Trace 和审计

边界：

- SSE 和 WebSocket 是候选传输方式，当前未批准最终选型。
- 流式交付不是业务事实源。
- 流式消息丢失不能覆盖任务数据库事实。
- 客户端必须能够通过权威查询恢复状态。

### 10.4.2 通知、订阅、回调和报告推送

- 当前逻辑区域：1. 用户与调用方、2. 边缘与接入层、7. 测试用例、执行、证据与反馈域、9. 平台控制面。
- 状态：Accepted target；Planned；Requires ADR；Deferred technology selection；不代表已实现。
- Recommended Phase: Phase 4；企业级订阅治理可延迟到 Phase 5。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires Access and Delivery Architecture design。

登记的能力包括：

- Notification Subscription
- Email Delivery
- IM Delivery
- Webhook Callback
- Report Push
- Notification Template
- Delivery Retry
- Delivery Idempotency
- Delivery Audit
- Delivery Failure Tracking
- Subscription Scope and Permission

边界：

- 通知不是执行事实源。
- 通知失败不得覆盖 `Execution`、`Evidence` 或 `Report`。
- `Webhook Callback` 必须考虑认证、签名、重放保护、重试、幂等和审计。
- `Report Push` 必须引用明确的 `Report` 或 `Execution`。
- 通知内容不得泄露 Secret。
- 当前不批准具体邮件、IM、Webhook、消息队列或推送产品。

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
- Embedding Service
- AI与转换质量指标

### 10.7.1 Embedding Service

- 当前逻辑区域：8. 大模型与 AI 能力层；横向依赖 9. 平台控制面、10. 数据与知识存储层。
- 状态：Accepted target；Planned；Requires ADR；Deferred technology selection；不代表已实现。
- Recommended Phase: Phase 2。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires AI Platform ADR。

`Embedding Service` 是逻辑能力，覆盖：

- Embedding 模型适配
- 批量向量化
- 文本切片输入
- 版本和模型标识
- 向量重建
- 调用 Trace
- 成本与配额
- 项目和权限作用域

边界：

- `Embedding Service` 不自动表示独立微服务。
- 当前不批准具体 Embedding 模型。
- 当前不批准具体向量数据库。
- 业务代码不得直接绑定具体 Embedding Provider SDK。

### 10.7.2 AI 与转换质量指标治理

- 当前逻辑区域：8. 大模型与 AI 能力层；横向依赖 9. 平台控制面、10. 数据与知识存储层。
- 状态：Accepted target；Planned；Requires ADR；不代表已实现。
- Recommended Phase: 转换质量指标建议在 Phase 3，跨产品质量看板和治理建议在 Phase 5 或 Cross-phase。该 Recommended Phase 仅是规划建议，不构成正式 Phase 合同，也不扩大 Phase 1。
- Requires AI Platform ADR。
- Requires Evaluation and Quality Governance design。

登记的高层指标包括：

- 绑定准确率
- False Executable Rate
- 结构化输出有效率
- 转换成功率
- 资源未解析率
- AI 调用成本
- AI 调用延迟

边界：

- 当前只登记指标治理能力。
- 当前不设置虚构指标值。
- 当前不设置未经批准的阈值。
- 分子、分母、采样、时间窗口、基线和告警由质量治理专题决定。
- 绑定准确率和 `False Executable Rate` 可能依赖人工标注和评估集。

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

本章沿用历史章节名，但当前主要对应：

- 10. 数据与知识存储层
- 11. 基础设施与运维治理层

## 11.1 数据基础设施

- MySQL / PostgreSQL
- Redis
- Object Storage
- Schema Migration
- 备份
- 恢复
- 数据归档

### 11.1.1 数据与知识架构治理检查清单

- 当前逻辑区域：9. 平台控制面、10. 数据与知识存储层、11. 基础设施与运维治理层。
- 状态：Accepted target；Planned；Requires ADR；Deferred technology selection；不代表已实现。
- Recommended Phase: Cross-phase。它应作为 Phase 2 到 Phase 4 的架构前置约束，但不替代正式 Phase 合同。
- Requires Data and Knowledge Architecture ADR。

后续数据 ADR 必须覆盖：

- 关系型业务事实
- JSONB 快照或结构化转换记录
- 向量索引
- 搜索索引
- 对象存储
- 缓存
- 队列
- 分析存储
- Secret 管理
- 可重建锁或任务协调机制
- 数据保留
- 归档
- 删除
- 恢复
- ACL
- 审计
- 跨项目隔离

目标架构参考中的评估候选包括：

- PostgreSQL
- JSONB
- pgvector
- Redis
- S3 或兼容对象存储
- Vault / KMS
- OpenSearch
- ClickHouse

边界：

- 以上名称只是后续数据 ADR 的评估候选，不代表具体产品已批准。
- 当前不得据此安装依赖或建立基础设施。
- Redis、缓存、队列、索引和分析结果不得成为核心业务事实源。
- Secret 只能使用引用。
- “可重建锁”后续必须定义权威任务事实、锁丢失恢复、过期、并发、幂等和崩溃恢复。

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

| 业务事实 | 权威事实源 |
|---|---|
| 需求正文 | RequirementVersion |
| 当前需求版本指针 | Requirement.current_version |
| 自然语言资产正文 | TestAssetVersion |
| 当前资产版本指针 | TestAsset.current_version |
| 来源关系 | TestAssetSource |
| 转换尝试事实 | ConversionAttempt |
| 可执行代码 | TestCaseVersion.script_code |
| 执行事实 | Execution / ExecutionStepResult / AssertionResult / Evidence |
| 报告 | 由执行事实派生 |

必须避免：

- 正文双写
- 状态双写
- script_code双写
- 版本原地覆盖
- 缓存代替事实源
- Runner重新推导执行逻辑

补充边界：

- `TestPointEvidencePack` 只提供检索与生成追溯，不替代 `RequirementVersion`。
- 流式状态消息、通知、缓存、队列、向量索引、搜索索引和分析结果不是核心业务事实源。
- dropped stream message 或 failed notification 不得覆盖数据库中的权威任务事实。

### 转换链路逻辑载体和候选权威记录

以下对象当前首先是目标架构逻辑概念：

- `ExecutionRequirementManifest`
- `ResourceResolutionDecision`
- `ResourceBindingSnapshot`
- `BoundExecutionPlan`
- `Intent IR`
- `Oracle`
- `Conversion Trace`

这些对象可以承担：

- 版本化转换输入
- 不可变快照
- 解析决定
- 绑定结果
- 编译输入
- 追溯记录

但必须明确：

- 它们当前不应全部被直接提升为已经批准的唯一事实源。
- 是否持久化、如何持久化、是否成为独立事实记录，由 Asset-to-Case、公共资源和数据专题 ADR 决定。
- 它们不得替代 `RequirementVersion`、`TestAssetVersion` 或 `TestCaseVersion.script_code`。
- Runner 不得根据这些对象重新理解自然语言。

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

补充的规划依赖链：

```text
Upload Security
→ project scope
→ object or file storage
→ Intake / Requirement import
```

```text
来源内容 / RequirementVersion
→ 文本解析与切片
→ Embedding Service / 索引支撑
→ Requirement Knowledge RAG
→ TestPointEvidencePack
→ AI natural-language test-point generation
```

上述链路表示高层处理流，不表示具体技术实现固定为向量检索。

- `Embedding Service / 索引支撑` 是 Requirement Knowledge RAG 的候选支撑方式。
- 具体模型、索引和检索产品尚未批准。
- 并非所有小规模或精确检索场景都必须经过向量检索。
- `TestPointEvidencePack` 是检索和证据组织结果，不是正文事实源。

```text
TestAssetVersion
→ Execution Context Retrieval
→ Oracle / Binder
→ BOUND / AMBIGUOUS / UNRESOLVED
→ Compiler / Preflight
→ TestCaseVersion
```

```text
TestCaseVersion
→ Binding Stale Check
→ Resource Lease
→ Runner
→ Evidence Normalization
→ Failure Classification
→ Report
→ Notification Delivery
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

`Binding Stale`、`Resource Lease`、`Replay`、`Manual Override`、
`Failure Classification` 和 `Evidence Normalization` 是独立治理能力，
不得被压缩成同一个状态字段。

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

以上是历史能力地图中的占位表达。

Target Architecture v2 现补充 Binder 结果语义：

```text
BOUND / AMBIGUOUS / UNRESOLVED
```

它们是 Accepted target 的规划语义，不代表数据库枚举、
API 字段或持久化状态机已经批准。
最终设计由 Asset-to-Case Compiler Architecture ADR 决定。

## 14.6 TestCase

```text
ready / stale / disabled
```

## 14.7 Execution

```text
queued / running / passed / failed / cancelled / timed_out / blocked
```

`Replay`、`Manual Override` 和 `Failure Classification`
不等同于上述 `Execution` 状态字段。

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

# 19. Phase 0 历史实施边界

EvieAi Phase 0 在其实施时点是完整目标架构的最小领域模型切片。

本节记录 Phase 0 在其实施时点获批并落地的最小领域模型边界。

本节用于历史追溯、兼容性检查和防止未来反向改写。

本节不是当前实施阶段声明。

当前 Phase 1 仍为 In Progress。

Phase 1 尚未完成正式 Closeout。

不得因为保留 Phase 0 历史边界而把当前阶段解释为 Phase 0。

Phase 0 合同仅授权并实施：

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

Phase 0 合同未授权：

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

Phase 0 当时额外确认：

- 使用`TestProject.project_code`
- 不新增Project表
- 不新增`project_id / project_uuid`
- 不新增`intent_id`
- TestAssetSource只支持Requirement来源
- 不预建Document/Page/Generation占位字段
- 核心业务ID使用`<prefix>_<uuid4hex32>`
- current_version由Repository事务维护
- 历史版本不可原地覆盖
- 本文新增的 `Accepted target` / `Planned` 能力仍属于后续规划，不代表已实现，也不扩大 Phase 0 或 Phase 1

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
- 上传入口是否保持 `Upload Security` 和 project scope 的 fail closed
- `TestPointEvidencePack` 是否被误当需求正文或执行证据
- `AMBIGUOUS` / `UNRESOLVED` 是否被错误放行为绑定成功
- `Manual Override` 是否绕过审批、审计或项目隔离

## 21.2 事实源检查

- 正文是否双写
- script_code是否双写
- 版本是否被原地覆盖
- current_version是否一致
- 派生结果是否覆盖事实源
- 流式状态、通知、缓存、队列、向量索引、搜索索引和分析结果是否被误当事实源

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
- 是否把 `Recommended Phase` 当成正式 Phase 合同
- 是否在缺少 ADR 的情况下硬编码扫描引擎、Embedding Provider、向量库或回调产品

---

# 22. 结论

EvieAi 完整能力空间当前按 11 个逻辑区域解释，
并保留历史七域章节编排视图承接既有能力地图、Phase 0 历史基线以及
Phase 1 已批准合同与已落地事实。

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

本文新增登记的 `Upload Security`、`TestPointEvidencePack`、
`BOUND / AMBIGUOUS / UNRESOLVED`、`Binding Stale`、`Resource Lease`、
`Replay`、`Manual Override`、`Failure Classification`、
`Evidence Normalization`、`Embedding Service`、通知回调和数据架构治理清单，
均属于 Accepted target / Planned 的规划检查点，不代表已实现，也不单独授权进入当前 Phase。

任何实施不得因为完整能力地图中存在某项能力，就在未经确认的情况下将其加入当前任务。
