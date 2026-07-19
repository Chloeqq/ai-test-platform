# EvieAi Architecture Overview

Status: Consolidated overview for `Target Architecture v2`

Effective target architecture date: 2026-07-18

Historical architecture reference date: 2026-07-12

Current overview scope: overall architecture explanation only

## 1. Document Purpose

本文是 EvieAi 的总体架构说明文档，用于面向开发、测试、架构和产品人员解释：

- 当前已接受的长期目标架构是什么；
- 11 个逻辑架构区域如何协同；
- 5 个核心业务域分别负责什么；
- 自然语言资产到执行结果的主链如何成立；
- 横向平台能力如何支撑核心业务域；
- 哪些实施合同已批准且当前有效、哪些基础已经落地；
- 哪些能力已进入已接受目标架构但尚未进入实施合同；
- 哪些技术名词仍只是后续专题评估候选。

本文的权威来源包括：

- [AGENTS.md](../../AGENTS.md)
- [ARCHITECTURE_BASELINE](../ARCHITECTURE_BASELINE.md)
- [ADR-0002](../decisions/ADR-0002-target-architecture-v2.md)
- [2026-07-18 Mermaid](../reference/2026-07-18_evie-ai-target-architecture-v2.mmd)
- [2026-07-18 PNG](../reference/2026-07-18_evie-ai-target-architecture-v2.png)

目标架构语义解释顺序为：

```text
ADR-0002 Accepted decision
→ ARCHITECTURE_BASELINE consolidated interpretation
→ Mermaid source
→ PNG rendering
```

必须同时明确：

- [AGENTS.md](../../AGENTS.md) 继续是仓库硬约束。
- 当前 Phase 合同决定当期允许实施范围。
- 本文只做总体架构解释，不扩大任何当前 Phase。
- 图中的技术名称不自动成为已批准技术选型。
- 本文与 `ADR-0002` 或 `ARCHITECTURE_BASELINE` 冲突时，必须停止后续实施并修正文档，
  不得自行选择。

本文不承担以下职责：

- 代替 `ARCHITECTURE_BASELINE`；
- 代替 ADR；
- 代替 Phase 实施合同；
- 设计详细数据库表；
- 设计详细 API；
- 批准技术产品；
- 宣称目标能力已经实现；
- 变成任务清单或项目进度表。

## 2. Architecture Status

截至 2026-07-18，EvieAi 当前架构状态如下：

- `ADR-0002` 已于 2026-07-18 `Accepted`。
- `ARCHITECTURE_BASELINE` 当前状态为 `Active`。
- `Target Architecture v2` 已成为 EvieAi 当前长期目标架构。
- 2026-07-18 新图是 `Accepted Target Architecture Reference`。
- 2026-07-12 旧图当前关系为 `Superseded for target architecture`。
- 旧图继续保留为历史架构演进证据。
- `Target Architecture v2` 不代表全部能力已经实现。
- 当前实施范围仍由有效 Phase 合同决定。

当前总体解释入口应理解为：

- `ADR-0002` 决定长期目标架构边界。
- `ARCHITECTURE_BASELINE` 统一收编并解释该目标边界。
- 本 overview 为面向协作方的总体架构说明入口。
- `target-capability-map`、`phase-traceability` 和各 Phase 文档负责后续能力落位与实施范围。

## 3. Product Architecture Principle

EvieAi 当前长期目标架构遵循以下稳定原则：

- `TestAsset` 表达“测什么”。
- `TestCase` 表达“如何执行”。
- `TestAsset` 与 `TestCase` 生命周期分离。
- 自然语言资产正文事实源是 `TestAssetVersion`。
- 可执行脚本事实源是 `TestCaseVersion.script_code`。
- `Asset-to-Case` 是唯一自然语言转机器执行表示入口。
- Runner 不重新理解自然语言。
- `Candidate`、`Preview`、`selected_candidates`、`TestPointPlan` 不回归主链。
- AI 生成侧只生成自然语言测试点，不生成机器执行表示。
- 报告由执行事实派生，不能反向覆盖执行事实。
- 失败反馈只能形成建议、归因、治理任务或新版本入口，不能自动覆盖版本化事实源。

## 4. Eleven Logical Architecture Areas

以下 11 个区域构成 EvieAi 当前长期目标架构的逻辑分区：

1. 用户与调用方
2. 边缘与接入层
3. 多元输入与需求智能域
4. 自然语言测试资产域
5. Asset-to-Case 转换与质量拦截域
6. 公共资源与能力域
7. 测试用例、执行、证据与反馈域
8. 大模型与 AI 能力层
9. 平台控制面
10. 数据与知识存储层
11. 基础设施与运维治理层

通用解释规则：

- 11 个区域不等于 11 个微服务。
- 11 个区域不等于当前实现状态。
- 11 个区域不自动对应数据库表。
- 11 个区域不批准部署单元数量。

### 4.1 用户与调用方

核心作用：

- 定义谁发起需求、资产、治理、执行和结果消费。

主要边界：

- 真实主体包括产品经理、测试人员、开发人员、平台管理员、CI/CD Pipeline、
  第三方平台、CLI、SDK Client、API Client 和通知接收方。
- 它不承担业务事实源职责。
- 它不决定内部领域模型。

相邻关系：

- 通过边缘与接入层进入系统。
- 执行结果、报告和通知也通过接入与交付能力返回给外部主体。

区域分类：

- 横向支撑入口，不属于核心业务域。

### 4.2 边缘与接入层

核心作用：

- 接收身份信息、建立请求上下文、暴露 API、承接上传和流式交付能力。

主要边界：

- 负责提取和验证 `project scope`。
- 负责执行访问控制结果。
- 负责限流、Trace、文件上传入口和实时或准实时结果回传。
- 平台控制面定义项目、租户、权限和隔离策略；接入层只执行确认后的策略。
- 接入层不持有项目事实源。
- 接入层不得猜测或回退 `project_code`。
- 缺失或非法作用域必须 fail closed。
- 不批准具体 API Gateway、WAF、SSE 或 WebSocket 产品。

相邻关系：

- 上接用户与调用方。
- 下接多元输入、资产查询、执行结果交付和控制面策略执行。

区域分类：

- 横向支撑层，不属于核心业务域。

### 4.3 多元输入与需求智能域

核心作用：

- 接入需求文档、OpenAPI、缺陷、日志、手工/API/CI 输入，并为自然语言测试点生成建立受控上下文。

主要边界：

- 维护 `Requirement` / `RequirementVersion`。
- 通过 `Requirement Knowledge RAG` 生成面向自然语言测试点的上下文。
- 只输出自然语言测试点，不输出执行 DSL、Locator 或 `script_code`。

相邻关系：

- 上接接入层。
- 下接自然语言测试资产域。
- 通过 AI 平台、控制面和数据层获得支撑。

区域分类：

- 核心业务域。

### 4.4 自然语言测试资产域

核心作用：

- 统一管理自然语言测试资产的身份、版本、来源、审核和生命周期。

主要边界：

- 维护 `TestAsset` / `TestAssetVersion`。
- 负责统一 Intake、Idempotency、Content Claim、Review、Audit 和版本化生命周期。
- 允许低质量、低置信度或暂不可执行资产入库。
- 不保存机器执行字段。

相邻关系：

- 上接多元输入与需求智能域以及手工/API/CI 直提入口。
- 下接 `Asset-to-Case` 转换域。

区域分类：

- 核心业务域。

### 4.5 Asset-to-Case 转换与质量拦截域

核心作用：

- 作为自然语言转机器执行表示的唯一合法入口，负责把锁定的资产版本组织成可验证、可编译、可追溯的执行输入。

主要边界：

- 负责 `ConversionAttempt`、执行需求分析、上下文检索、绑定、验证、质量门、有限修复、
  Preflight 和 `TestCaseVersion` 生成。
- 不修改 `TestAssetVersion` 正文。
- 不直接执行测试。
- 不在 Runner 阶段重新解释自然语言。

相邻关系：

- 上接自然语言测试资产域。
- 横向依赖公共资源与能力域、AI 平台、控制面和数据层。
- 下接测试用例、执行、证据与反馈域。

区域分类：

- 核心业务域。

### 4.6 公共资源与能力域

核心作用：

- 为转换域和执行域提供版本化、独立治理、可审计的执行资源与能力。

主要边界：

- 覆盖 Web、API、Android、iOS 资源。
- 覆盖测试数据、环境、设备、Secret、Mock、故障注入、安全、性能和 Capability Registry。
- 资源必须经过独立治理和版本化后才能绑定。
- 不控制 `TestAsset` 生命周期。

相邻关系：

- 向转换域提供执行上下文和绑定结果。
- 向执行域提供运行时资源基础。

区域分类：

- 核心业务域。

### 4.7 测试用例、执行、证据与反馈域

核心作用：

- 承载版本化用例、执行调度、证据、报告、失败归因和反馈闭环。

主要边界：

- 维护 `TestCase` / `TestCaseVersion`、Runner Orchestration、Platform Adapter、
  Evidence、Report、Failure Classification、Flaky 和 Quarantine 等能力。
- Runner 只执行版本化可执行输入和资源引用。
- Runner 不得重新理解 `TestAsset`。
- 反馈不得自动覆盖版本化资产。

相邻关系：

- 上接转换域输出的 `TestCaseVersion.script_code`。
- 横向依赖公共资源与能力域、控制面、AI 平台、数据层和基础设施。

区域分类：

- 核心业务域。

### 4.8 大模型与 AI 能力层

核心作用：

- 为输入域、转换域和治理域提供统一模型调用、结构化输出和检索支撑。

主要边界：

- 覆盖 `Model Gateway`、`Provider Adapter`、`Model Router`、`Model Registry`、
  `Prompt Registry`、`Structured Output`、`Embedding Service`、`Guardrail`、
  `Evaluation`、`Trace` 和 `Token / Cost / Quota`。
- AI 不成为业务事实源。
- 业务代码不应直接绑定具体 Provider SDK。

相邻关系：

- 支撑多元输入与需求智能域。
- 支撑 `Asset-to-Case` 的上下文检索与有限修复。
- 受控制面和数据层治理。

区域分类：

- 横向支撑层。

### 4.9 平台控制面

核心作用：

- 提供横向的身份、项目、租户、审计、审批、任务、版本、配额和 AI 治理能力。

主要边界：

- 持有用户和项目事实。
- 定义租户或项目边界、角色与权限策略、项目隔离策略和治理策略。
- 提供审计、配额、Feature Flag、审批、Job、Domain Event、统一 ID、Trace、
  `Model Registry` 和 `Prompt Registry` 治理入口。
- 不替代核心业务域。

相邻关系：

- 为接入层提供项目和权限策略定义。
- 为五个核心业务域提供横向治理和平台事实。

区域分类：

- 横向支撑层。

### 4.10 数据与知识存储层

核心作用：

- 为业务事实、转换快照、对象证据、索引、缓存和分析能力提供统一存储边界。

主要边界：

- 承载关系型业务事实、结构化快照、对象存储、索引、缓存和分析候选。
- Redis、缓存、队列、索引和分析结果不得成为核心业务事实源。
- 技术名词仅代表评估候选，不自动批准产品选型。

相邻关系：

- 为核心业务域和横向支撑层提供数据支撑。
- 受控制面和基础设施层治理。

区域分类：

- 横向支撑层。

### 4.11 基础设施与运维治理层

核心作用：

- 为部署、交付、运行、观测、安全、备份和运维治理提供技术底座。

主要边界：

- 覆盖部署单元、容器与编排、CI/CD、任务队列、服务治理、可观测性、日志与审计、
  备份与容灾和安全运维。
- 不定义核心业务事实。
- 不因图中出现部署名称而批准最终服务拆分。

相邻关系：

- 向接入层、AI 平台、转换域、执行域和数据层提供运行底座。

区域分类：

- 横向支撑层。

## 5. Five Core Business Domains

当前长期目标架构中的 5 个核心业务域为：

1. 多元输入与需求智能域
2. 自然语言测试资产域
3. Asset-to-Case 转换与质量拦截域
4. 公共资源与能力域
5. 测试用例、执行、证据与反馈域

### 5.1 多元输入与需求智能域

- 负责：接入多类上游输入、维护 `Requirement` / `RequirementVersion`、建立
  `Requirement Knowledge RAG`、生成自然语言测试点。
- 输入：需求文档、OpenAPI、缺陷、日志、手工输入、API / CI / 批量提交。
- 输出：`Requirement` / `RequirementVersion`、生成上下文、自然语言测试资产输入。
- 事实源：需求正文事实源仍是 `RequirementVersion`；需求聚合身份和当前版本由
  `Requirement` 承担。
- 不负责：执行 DSL、机器步骤、执行资源绑定、`TestCase` 创建、Runner 调用。

### 5.2 自然语言测试资产域

- 负责：统一 Intake、稳定资产身份、版本、审核、来源、幂等、精确重复、审计和删除恢复。
- 输入：上游域输出的自然语言测试点，以及手工/API 直接提交的自然语言资产。
- 输出：版本化自然语言测试资产、审核与审计事实、供转换域使用的稳定资产身份。
- 事实源：自然语言正文事实源是 `TestAssetVersion`；当前聚合状态和版本指针由 `TestAsset`
  承担。
- 不负责：元素绑定、Intent IR、DSL、Compiler、Runner、`script_code`。

### 5.3 Asset-to-Case 转换与质量拦截域

- 负责：锁定明确的 `TestAssetVersion`，组织执行需求、执行上下文、语义对象、绑定、质量门、
  平台编译和转换追踪。
- 输入：已锁定的 `TestAssetVersion`、版本化资源、平台策略、转换规则和 AI 辅助能力。
- 输出：`ConversionAttempt`、逻辑转换记录、`Bound Execution Plan`、`TestCase`、
  `TestCaseVersion`。
- 事实源：转换过程事实由 `ConversionAttempt` 承担；可执行脚本唯一事实源仍是
  `TestCaseVersion.script_code`。
- 不负责：修改自然语言正文、重建 Candidate 主链、直接执行平台动作、运行时重新解释自然语言。

### 5.4 公共资源与能力域

- 负责：独立治理执行资源与能力，并通过统一网关输出版本化绑定能力。
- 输入：资源元数据、资源版本、治理策略、环境和凭证引用。
- 输出：版本化资源描述、能力解析结果、绑定决策和运行时资源基础。
- 事实源：资源版本、能力定义、治理策略、健康或可用性事实由资源域自身治理。
- 不负责：控制 `TestAsset` 生命周期、替代 `Asset-to-Case`、替代 Runner Orchestrator。

### 5.5 测试用例、执行、证据与反馈域

- 负责：执行 `TestCaseVersion`、管理计划与调度、保存证据、生成报告、进行失败归因和稳定性治理。
- 输入：`TestCaseVersion`、资源绑定快照、执行策略和运行时参数。
- 输出：`Execution`、`StepResult`、`AssertionResult`、`Evidence`、`Report`、
  失败与反馈治理结果。
- 事实源：可执行脚本事实源是 `TestCaseVersion.script_code`；执行事实源是
  `Execution / StepResult / AssertionResult / Evidence`；`Report` 由执行事实派生。
- 不负责：重新理解 `TestAsset`、运行时重新编译、回写 `TestAssetVersion`、绕过资源绑定快照。

## 6. End-to-End Business Flow

EvieAi 的高层逻辑主链如下：

```text
多元输入
→ Requirement / RequirementVersion
→ Requirement Knowledge RAG
→ 自然语言测试点
→ 统一 Intake
→ TestAsset / TestAssetVersion
→ Review / Version / Audit
→ Asset-to-Case
→ Execution Context Retrieval
→ Intent IR / Oracle / Binding
→ Platform Compile / Validation / Preflight
→ TestCaseVersion.script_code
→ Runner Orchestration
→ Platform Adapter
→ Execution / Evidence
→ Report / Failure Classification / Feedback
```

必须明确：

- 这是逻辑流程，不代表全部模块已经实现。
- 中间逻辑对象不自动成为数据库表。
- Runner 阶段不得重新解释 `TestAsset`。
- `Report` 是由执行事实派生。
- 失败反馈不得自动覆盖版本化资产。

## 7. Requirement Knowledge RAG and TestPointEvidencePack

为避免与执行域 `Evidence` 混淆，本文将输入域的逻辑证据载体统一称为
`TestPointEvidencePack`。

`Requirement Knowledge RAG` 的职责是为自然语言测试点生成提供受控证据上下文。

`TestPointEvidencePack` 作为逻辑证据载体，可包含：

- 来源文档或 `RequirementVersion` 引用；
- 来源片段引用；
- 版本信息；
- 检索得分或权重；
- 来源类型；
- 项目和权限作用域；
- 生成追踪信息。

必须明确：

- `TestPointEvidencePack` 不替代 `RequirementVersion`。
- 它不成为需求正文事实源。
- 它不等于执行阶段的 `Evidence`。
- 它不自动表示数据库表。
- 具体模型、存储和权限实现由后续 RAG 专题 ADR 与 Phase 合同决定。

## 8. OpenAPI Dual Governance

OpenAPI 在 EvieAi 中可以承担两类不同角色：

- 作为需求输入，用于理解接口需求、提取业务行为并辅助生成自然语言测试资产。
- 作为版本化 API 执行资源，用于独立治理 API specification、endpoint、schema、认证和依赖。

必须明确：

- 两条治理链的目的不同。
- 需求输入不能自动成为执行资源。
- 执行资源必须独立导入、验证、版本化并接受项目作用域治理。

## 9. Asset-to-Case Internal Responsibility

`Asset-to-Case` 在总体层面需要覆盖以下逻辑职责：

- `Execution Requirement`
- `Execution Context`
- `Intent IR`
- `Test Oracle`
- `Binder`
- `Bound Execution Plan`
- `Platform Compiler`
- `Validation`
- `Quality Gate`
- `Limited Repair`
- `Preflight`
- `Conversion Trace`

这些名称首先是目标架构中的逻辑能力，不自动表示数据库表、ORM 模型、独立服务或已批准状态机。

对于 `Binder`，后续转换专题必须显式决定以下结果语义：

- `BOUND`
- `AMBIGUOUS`
- `UNRESOLVED`

同时必须明确：

- 这些状态名称是目标架构规划语义。
- 具体状态机、错误模型和持久化方式尚未批准。
- `AMBIGUOUS` 或 `UNRESOLVED` 不得通过猜测、固定资源回退或默认绑定继续执行。
- 是否进入 blocked、failed 或人工处理状态，由后续 `Asset-to-Case` 专题 ADR 决定。

## 10. Execution Governance Planning Checkpoints

执行域后续必须在专题 ADR 和 Phase 合同中显式覆盖以下概念：

- Runner Orchestration
- Platform Adapter
- Worker / Device Pool
- `Resource Lease`
- `Binding Stale`
- `Replay`
- `Manual Override`
- Failure Classification
- Flaky
- Quarantine
- Evidence Normalization

这些概念不是同一类状态，必须区分：

- `Resource Lease`：资源协调机制。
- `Binding Stale`：资源或绑定有效性条件。
- `Replay`：执行操作。
- `Manual Override`：必须受权限、审批和审计约束的管理动作。
- Failure Classification：失败归因体系。
- Flaky / Quarantine：稳定性治理机制。

必须进一步明确：

- 具体状态机和 taxonomy 尚未批准。
- `Manual Override` 不得绕过审计、资源权限或安全策略。
- `Replay` 不得修改原始 `Execution` 和 `Evidence`。
- 这些内容由执行专题 ADR 和后续 Phase 合同决定。

## 11. AI Platform and Quality Governance

AI 平台在长期目标架构中的高层能力包括：

- `Model Gateway`
- `Provider Adapter`
- `Model Router`
- `Model Registry`
- `Prompt Registry`
- `Structured Output`
- `Embedding Service`
- `Guardrail`
- `Evaluation`
- `Trace`
- `Token / Cost / Quota`

必须明确：

- 这些是目标能力，不代表全部已实现。
- 具体供应商和产品未批准。
- 业务代码不得直接绑定 Provider SDK。
- `Embedding Service` 是 AI 平台逻辑能力，不自动表示独立服务。
- Embedding 模型、向量产品和索引方案仍属于 `Deferred Decisions`。

当前 overview 仅在高层收编以下质量治理检查点：

- 绑定准确率
- `False Executable Rate`
- 结构化输出有效率
- 转换成功率
- 资源未解析率
- AI 调用成本与延迟

必须明确：

- 这些指标名称目前属于高层治理检查点。
- 最终定义、分母、采样规则、阈值和告警策略由质量治理专题决定。
- overview 不伪造当前指标值。

## 12. Edge Delivery and Notification

接入和结果交付能力在长期目标架构中需要覆盖：

- 文件类型和大小校验；
- 上传安全扫描；
- 异步任务状态查询；
- 实时或准实时结果回传；
- 通知订阅；
- Email；
- IM；
- `Webhook`；
- 报告推送。

必须明确：

- SSE 和 WebSocket 是可能的传输方式，不是本文批准的最终选型。
- 通知接收方属于外部调用方或结果接收方。
- 通知能力不成为执行事实源。
- 通知失败不得覆盖 `Execution`、`Evidence` 或 `Report`。
- `Webhook` 必须受认证、签名、重试、幂等和审计约束。
- 具体实现由接入专题和后续 Phase 决定。

## 13. Data and Knowledge Planning Checklist

后续数据专题必须显式评估以下类别：

- 关系型业务事实；
- JSONB 快照或结构化转换记录；
- 向量索引；
- 搜索索引；
- 对象存储；
- 缓存；
- 队列；
- 分析存储；
- Secret 管理；
- 可重建锁或任务协调机制。

以下技术名词来自目标架构参考图，仅作为后续数据 ADR 的评估候选：

- PostgreSQL
- JSONB
- pgvector
- Redis
- S3 或兼容对象存储
- Vault / KMS
- `OpenSearch`
- `ClickHouse`

必须明确：

- 这些名称只是候选，不代表已批准选型。
- overview 不据此安装依赖、创建基础设施或建立数据库。
- Redis、缓存、队列、索引和分析结果不得成为核心业务事实源。
- “可重建锁”必须由后续专题明确其权威事实、恢复和并发语义。

## 14. Cross-Cutting Control Plane

平台控制面在总体层面提供以下横向能力：

- 用户和项目事实；
- 身份与权限；
- 项目隔离策略；
- 审计；
- 配额；
- Feature Flag；
- 审批；
- Job；
- Domain Event；
- 统一 ID；
- Trace；
- `Model Registry`；
- `Prompt Registry`；
- AI 治理；
- 成本与资源策略。

必须明确：

- 控制面不替代核心业务域。
- 接入层执行控制面定义的项目和权限策略。
- 具体数据模型和服务拆分尚未批准。

## 15. Implementation Status Boundary

当前 overview 必须区分以下三类状态。

### 15.1 已批准且当前有效的实施合同与已落地基础

#### 当前有效合同

- `ADR-0001`；
- Phase 1 Specification；
- Phase 1 Implementation Plan；
- Phase 0 Domain Model。

这些合同和文档已经批准并生效，但它们当前有效不等于对应 Phase 已整体完成。

#### 已落地基础

- 已通过实际代码、Migration、Repository 和验收结果确认的能力；
- 具体完成范围以 `phase-traceability`、对应 Slice 验收记录和代码事实为准；
- Phase 0 最小持久化基线；
- Phase 1 已落地的 Migration、Repository 和生命周期基础能力；
- legacy chain freeze。

已完成部分不得被描述为整个 Phase 已完成。

#### 当前阶段状态

- Phase 1 overall status: In Progress
- Phase 1 closeout status: Not completed

必须明确：

- Phase 1 合同已经批准，但整体实施尚未完成。
- 未完成部分继续受 Phase 1 合同约束。
- 历史事实有效不等于 Phase 1 整体完成。
- 不得宣布 Phase 1 已完成。
- 在 Phase 1 Closeout 完成并获得明确批准前，不得宣布正式转入 Phase 2 实施。

### 15.2 已接受目标架构、但尚未形成实施合同

- 11 个逻辑区域；
- 5 个核心业务域；
- AI Platform；
- 两类 RAG；
- 公共资源与能力域展开；
- 多平台执行；
- 执行治理；
- 数据和控制面长期能力。

必须同时明确：

- Phase 2～5 当前仍属于目标规划和后续合同范围。
- Recommended Phase 不是实施授权。
- 本 overview 不决定 Phase 切换时间。

### 15.3 尚未批准的具体方案

- 具体数据库和中间件；
- 具体模型供应商；
- 具体 Gateway；
- 具体 DSL；
- 具体 Runner Adapter；
- 具体服务拆分；
- 具体设备云；
- 具体 MCP Server；
- 具体指标阈值。

不得把目标能力写成当前已完成能力。

## 16. Planning Checkpoints Not Yet Assigned to Phase Contracts

本次只读复核识别出以下 7 类后续规划检查点：

1. 上传安全扫描和实时结果回传；
2. `TestPointEvidencePack` 治理；
3. Oracle / Binder 结果语义与未解析治理；
4. `Resource Lease`、`Binding Stale`、`Replay`、`Manual Override` 和失败分类；
5. `Embedding Service` 与 AI 质量指标；
6. 通知、订阅、回调和报告推送；
7. 数据与知识存储专题检查清单。

必须明确：

- 这些能力已存在于 `Accepted Target Architecture` 的目标表达中。
- 它们当前并不表示已实现。
- 它们不自动进入 Phase 1。
- 它们也不自动授权启动未经批准的 Phase 2 实施。
- 本节只防止后续规划遗漏。
- 具体落位将在 `target-capability-map`、`phase-traceability`、专题 ADR 和对应 Phase 合同中完成。
- 本步骤不修改上述文件。

## 17. Historical Architecture

### 17.1 Historical Seven-Domain Narrative

2026-07-12 历史总体架构曾以七域模型表达长期目标：

1. 多元输入与自然语言生成域
2. 自然语言测试资产域
3. Asset-to-Case 转换与统一质量门域
4. 公共资源与能力域
5. 测试用例、执行、证据与反馈域
6. 平台控制面
7. 技术基础设施域

该叙事在当时为 Phase 0 和 Phase 1 提供了历史总体说明，仍具有追溯价值。

### 17.2 Current Historical Relationship

历史图文件为：

- [2026-07-12 Mermaid](../reference/2026-07-12_evie-ai-architecture-flow.mmd)

必须明确：

- 旧图不再定义当前长期目标架构。
- `Superseded for target architecture` 不否定历史合同。
- Phase 0、Phase 1 的当时事实继续有效。
- Phase 1 历史事实有效，不等于 Phase 1 整体完成。
- `Target Architecture v2` 已 Accepted，不代表 Phase 1 自动结束。
- 旧图不得删除。
- 不得根据当前文件内容反向解释历史基线。

因此，旧七域内容在本 overview 中只作为历史架构记录保留，不再与当前 `Target Architecture v2`
并列生效。

## 18. Follow-up Governance

后续治理顺序如下：

```text
evie-ai-overview
→ target-capability-map
→ docs/evie-ai/README
→ docs/evie-ai/reference/README
→ phase-traceability
→ Phase 2～5 合同
→ 专题 ADR 和专题架构
→ engineering standards
→ 最后评估 AGENTS.md
```

本步骤只完成 `evie-ai-overview`。

必须同时明确：

- `target-capability-map` 和 `phase-traceability` 可以继续规划 Phase 2～5。
- 但在 Phase 1 Closeout 完成并获得明确批准前，不得依据本 overview 宣布进入 Phase 2 实施。
- 本 overview 不决定 Phase 切换时间。
