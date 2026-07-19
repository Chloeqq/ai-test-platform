# ADR-0002：EvieAi Target Architecture v2

## Status

Accepted

## Date

2026-07-18

## Decision Owners

User-approved

## Context

EvieAi 已经通过既有架构、Phase 0 和 Phase 1 合同建立了自然语言测试资产主线、唯一事实源、
版本不可变、统一资产入库、Asset-to-Case 唯一转换入口以及 Runner 硬边界。

截至 2026-07-18：

- `TestAsset` 继续表达“测什么”；
- `TestCase` 继续表达“如何执行”；
- Phase 0 已建立 Requirement / TestAsset 最小持久化基线；
- Phase 1 已建立自然语言资产生命周期的批准合同；
- `docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md` 继续保持
  `Accepted`；
- 2026-07-12 架构图和既有七域叙事已经形成历史目标架构表达；
- 2026-07-18 新架构图完成只读扫描后，最初以 `Draft / Proposed Target Architecture`
  身份进入 ADR 审查；自 ADR-0002 于 2026-07-18 被接受后，该图成为 EvieAi 已接受的
 目标架构参考图（`Accepted Target Architecture Reference`），但仍不是 Phase 实施合同，
  且仍需由 `ARCHITECTURE_BASELINE`、`evie-ai-overview` 和入口文档正式收编；本步骤未完成
  这些后续收编。

现有总体架构已经清晰建立：

- 自然语言资产主线；
- 资产和用例生命周期分离；
- Candidate 退出主链；
- 资源只能在转换阶段绑定；
- `TestCaseVersion.script_code` 是可执行代码唯一事实源。

但现有总体表达对以下长期目标内容仍然不足：

- 边缘与接入层；
- 大模型与 AI 平台边界；
- Requirement Knowledge RAG 与 Execution Context Retrieval 的区分；
- 公共资源与能力域的完整展开；
- Web、API、Android、iOS 多平台执行目标；
- 数据与知识存储职责分工；
- 平台控制面；
- 基础设施与运维治理；
- 逻辑领域与部署单元的区分；
- 新旧架构图和 Phase 文档的权威关系。

因此需要新增一份总体架构 ADR，用于决定 2026-07-18 新图的正式身份、适用范围、
与既有合同的关系，以及权威文档后续收编顺序。

## Problem Statement

当前 EvieAi 的总体文档治理面临以下问题：

1. 业务领域和技术基础设施在既有总览中仍存在混合表达。
2. 逻辑领域与部署单元尚未正式区分，容易把架构分层误读为微服务拆分方案。
3. 接入层边界不完整，缺少对 API Gateway、BFF、上传安全、SSE/WebSocket 和外部调用方的统一表达。
4. AI 调用缺少统一平台边界，容易让业务模块直接依赖具体 Provider SDK。
5. Requirement Knowledge RAG 与 Execution Context Retrieval 尚未在权威文档中正式区分。
6. 公共资源与能力域虽已存在原则，但页面、API、移动端、数据、Secret、Mock、安全、性能等能力展开不足。
7. Asset-to-Case 粒度过粗，尚未正式表达 Execution Context、Intent IR、Oracle、Binder、Preflight 等内部层次。
8. Web、API、Android、iOS 多平台执行缺少正式架构边界，Runner、Adapter、Orchestrator 的职责未被完整固定。
9. 数据与知识存储职责不清，缓存、向量、对象存储、关系型事实源和分析能力的边界未正式表达。
10. 平台控制面能力不完整，权限、审批、配额、异步任务、AI 治理和版本治理尚未形成统一高层合同。
11. 基础设施和运维治理表达不完整，无法清楚区分“平台治理规则”和“运行时技术底座”。
12. 2026-07-18 新图、2026-07-12 旧图、Phase 0/1 合同和既有专题文档可能形成竞争性事实源。

## Decision

以下内容是 ADR-0002 已接受的总体架构决策。

本 ADR 自 2026-07-18 用户明确批准后生效。

其生效范围是 EvieAi 长期目标架构、领域边界和文档治理关系。
本 ADR 不自动扩大任何当前 Phase 的实施范围，也不自动批准 Deferred Decisions
中的技术选型、数据模型、部署拓扑或第三方依赖。

必须明确区分：

- 架构决策已经生效；
- 实施合同没有自动生效；
- 技术候选没有自动获批；
- Phase 0 和 Phase 1 没有被修改。

### 1. Adopt Target Architecture v2

EvieAi 的长期目标架构采用 2026-07-18 新架构图表达的 Target Architecture v2。

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

明确约束：

- 11 个区域是逻辑架构区域，不等于 11 个独立服务。
- 11 个区域不代表当前已经实现。
- 11 个区域不自动扩大当前 Phase 实施范围。
- 11 个区域不能反向覆盖 `AGENTS.md`、Phase 0、Phase 1 或 `ADR-0001`。

### 2. Five Core Business Domains

本 ADR 将以下五个领域确认为 EvieAi 长期目标架构中的核心业务域。

1. 多元输入与需求智能域
2. 自然语言测试资产域
3. Asset-to-Case 转换与质量拦截域
4. 公共资源与能力域
5. 测试用例、执行、证据与反馈域

#### 2.0 逻辑概念与实现形态说明

本节出现的对象名称首先是逻辑架构概念，不自动表示：

- 数据库表
- ORM Model
- 独立微服务
- 必须持久化的对象

这些对象在后续设计中可以实现为：

- 持久化实体
- 值对象
- 不可变快照
- 事件
- 任务
- 策略
- 临时转换结构
- 派生记录

具体实现形态由对应专题 ADR、Specification 和 Phase 合同决定。

以下名称目前不因 ADR-0002 自动成为数据库表：

- Execution Requirement Manifest
- Execution Context
- Intent IR
- Oracle
- Bound Execution Plan
- Conversion Trace
- Resource Descriptor
- Resource Version
- Capability Registry
- Resource Binding
- Failure Classification
- Flaky Record
- Quarantine Record

本 ADR 不设计上述对象的字段。

#### 2.1 多元输入与需求智能域

主要职责：

- 接入多种上游输入；
- 维护 Requirement 和 RequirementVersion；
- 进行文档解析和来源理解；
- 建立 Requirement Knowledge RAG；
- 生成自然语言测试点。

输入：

- 需求文档
- OpenAPI
- 缺陷
- 日志
- 手工输入
- API / CI / 批量提交

输出：

- Requirement / RequirementVersion
- 生成上下文
- 自然语言测试资产输入

核心事实源：

- 需求正文事实源：`RequirementVersion`
- 需求聚合和当前版本指针：`Requirement`
- 来源、检索证据和生成上下文：版本化来源或派生记录，不得覆盖
  `RequirementVersion` 正文

依赖方向：

- 可依赖边缘与接入层、AI 能力层、平台控制面和数据支撑层；
- 输出进入自然语言测试资产域；
- 不得直接依赖 Runner 或具体平台执行 Adapter。

不承担的职责：

- DSL
- 机器步骤
- 执行资源绑定
- TestCase 创建
- Runner 调用

#### 2.1.1 OpenAPI 的双重治理角色

同一 OpenAPI 文件可以经过两条不同治理链，但两条链的目的、版本、来源和事实关系不同。

OpenAPI 作为需求输入时，用于：

- 理解接口需求
- 提取业务行为
- 辅助生成自然语言测试资产
- 建立 Requirement 或来源证据

OpenAPI 作为执行资源时，用于：

- 建立版本化 API Specification
- 解析 Endpoint
- 绑定 method、path、request schema、response schema
- 为 API Binder、Compiler 和 Runner 提供执行上下文

明确约束：

- 不得因为 OpenAPI 已被用于需求理解，就自动成为经独立治理确认的执行资源。
- 执行资源必须经过独立导入、验证、版本化和项目作用域治理。

#### 2.2 自然语言测试资产域

主要职责：

- 管理 TestAsset、TestAssetVersion 和 Source；
- 统一 Intake；
- 管理 Review、Audit、Idempotency、Content Claim；
- 管理生命周期、软删除和版本。

输入：

- 多元输入与需求智能域输出的自然语言资产
- 手工/API 直接提交的自然语言资产

输出：

- 版本化自然语言资产
- 审核与审计事实
- 供 Asset-to-Case 使用的稳定资产身份

核心事实源：

- 自然语言测试资产正文事实源：`TestAssetVersion`
- 资产聚合和当前版本指针：`TestAsset`
- `TestAssetSource`、Review、Audit、Idempotency 和 Content Claim 属于治理事实或
  关系事实，不得被表述为资产正文事实源

依赖方向：

- 可依赖平台控制面提供的项目、身份、审计和幂等基础；
- 输出到 Asset-to-Case；
- 不得依赖 Compiler、Runner 或平台执行资源。

不承担的职责：

- 页面解析
- 元素绑定
- Intent IR
- DSL
- Compiler
- Runner

#### 2.3 Asset-to-Case 转换与质量拦截域

主要职责：

- 锁定明确的 TestAssetVersion；
- 维护 ConversionAttempt；
- 分析执行需求；
- 组织 Execution Context、Intent IR、Oracle、Binder 和 Bound Plan；
- 进行用例展开、平台编译、DSL 校验、质量门、有限修复和 Preflight；
- 生成 TestCaseVersion 和 Conversion Trace。

输入：

- 已锁定的 TestAssetVersion
- 版本化资源和能力绑定结果
- 平台策略与转换规则

输出：

- ConversionAttempt
- Bound Execution Plan
- TestCase
- TestCaseVersion
- Conversion Trace

核心事实源：

- 转换过程事实：`ConversionAttempt`
- `Execution Requirement Manifest`、`Execution Context`、`Intent IR`、`Oracle`、
  `Resource Binding`、`Bound Execution Plan` 和 `Conversion Trace` 可以作为版本化转换
  记录或快照，但不能替代可执行脚本事实源
- 可执行脚本唯一事实源：`TestCaseVersion.script_code`
- Runner 不得在运行时根据上述中间对象重新解释自然语言或重新编译

依赖方向：

- 依赖自然语言测试资产域提供稳定资产版本；
- 依赖公共资源与能力域提供版本化资源；
- 输出给测试用例、执行、证据与反馈域；
- 不得依赖运行时重新解释自然语言。

不承担的职责：

- 修改 TestAssetVersion 正文
- 建立 Candidate 产品主链
- 直接执行平台动作
- 运行时重新解释自然语言

#### 2.4 公共资源与能力域

主要职责：

- 提供 Web、API、Android、iOS 等执行资源；
- 提供测试数据、环境、设备、Secret 引用、Mock、故障注入、安全和性能能力；
- 提供 Capability Registry；
- 通过 Resource Capability Gateway 提供版本化资源解析。

输入：

- 资源元数据
- 资源版本
- 能力策略
- 环境与凭证引用

输出：

- 版本化资源描述
- 资源解析决策
- Resource Binding 结果

核心事实源：

- 版本化资源定义
- 能力定义
- 资源状态或健康事实
- 资源治理策略

说明：

- 具体实体、表、Schema、版本模型和快照结构由后续公共资源专题 ADR 决定。

依赖方向：

- 可依赖平台控制面和数据治理基础；
- 为 Asset-to-Case 和执行域提供资源；
- 不得控制自然语言资产生命周期。

不承担的职责：

- 决定 TestAsset 正文
- 控制资产生命周期
- 编排完整测试执行
- 替代 Runner Orchestrator

#### 2.5 测试用例、执行、证据与反馈域

主要职责：

- 管理 TestCase 和 TestCaseVersion；
- 承载执行计划、调度和 Runner Orchestration；
- 管理平台 Adapter、Worker / Device Pool、Evidence、Report、Failure Classification、
  Flaky、Quarantine、Replay 和 Feedback。

输入：

- TestCaseVersion
- 绑定资源快照
- 执行策略
- 运行时参数

输出：

- Execution
- Step Result
- Evidence
- Report
- Failure / Flaky / Feedback 治理结果

核心事实源：

- 用例聚合和当前版本指针：`TestCase`
- 可执行脚本唯一事实源：`TestCaseVersion.script_code`
- 执行事实：`Execution`、`StepResult`、`AssertionResult`、`Evidence`
- `Report` 是由执行事实派生的结果，不得反向覆盖 `Execution`、`StepResult`、
  `AssertionResult` 或 `Evidence`，且必须能够追溯到明确的 `Execution` 与 `Evidence`

依赖方向：

- 依赖 Asset-to-Case 提供版本化可执行输入；
- 依赖公共资源与能力域提供经独立治理和版本化的资源；
- 不得回写自然语言资产正文。

不承担的职责：

- 重新理解自然语言资产
- 运行时编译
- 修改 TestAssetVersion
- 绕过资源绑定快照

### 3. Cross-Cutting Supporting Areas

本 ADR 将以下区域确认为横向支撑层：

- 边缘与接入层
- 大模型与 AI 能力层
- 平台控制面
- 数据与知识存储层
- 基础设施与运维治理层

这些区域的职责是为核心业务域提供接入、治理、平台、存储和运行时支撑。

明确约束：

- 横向支撑层不能被建模为自然语言资产主链中的普通步骤。
- 横向支撑层不能替代核心业务域的事实源。
- 横向支撑层的存在不意味着必须立即拆分为独立服务。

#### 边缘与接入层

负责：

- 外部入口
- 传输安全
- 请求认证入口
- 限流
- Trace 上下文
- 上传入口
- 流式通信
- API 暴露

不负责：

- TestAsset 状态转换
- Conversion 业务判断
- Runner 调度
- Repository 事务
- 资产或用例事实源

#### 平台控制面

负责高层治理：

- 用户和项目
- 身份和权限
- 项目隔离
- 审计
- 配额
- Feature Flag
- 审批
- 任务治理
- 统一标识和 Trace
- 成本和资源策略

不替代：

- 自然语言测试资产域
- Asset-to-Case
- 公共资源与能力域
- 执行域

本 ADR 不设计控制面的具体数据模型或服务拆分。

### 4. AI Platform Boundary

本 ADR 确认 AI 平台的以下高层边界：

- 业务领域通过统一 AI Platform 使用模型能力；
- 业务模块不应直接绑定具体 Provider SDK；
- Requirement Knowledge RAG 与 Execution Context Retrieval 必须分离；
- AI 输出必须经过结构化校验；
- AI 不是权威数据库事实源；
- AI 不得生成权威数据库 ID；
- AI 不得覆盖权威数据库 ID；
- AI 不得根据名称、标题或自然语言猜测权威 ID；
- 权威 ID 必须由服务端统一 ID 模块或权威持久化流程分配；
- AI 可以返回候选描述、语义标签或非权威临时引用；
- 临时引用必须经过后端解析和验证后才能绑定到权威资源；
- 解析失败必须明确失败，不得使用固定页面、固定环境或固定资源回退；
- AI 不得绕过 Intake、Policy、Compiler、Runner 或数据库约束。

本 ADR 不决定以下具体设计：

- Model Gateway 的实现细节
- Provider Adapter 结构
- Router / Registry 细粒度设计
- Guardrail / Evaluation / Trace / Cost 的具体产品和接口

### 5. Resource and Capability Boundary

本 ADR 确认以下高层边界：

- 公共资源与能力域独立存在；
- 转换域通过 Resource Capability Gateway 获取版本化资源；
- Runner 使用已绑定且经独立治理确认的资源快照；
- Capability Registry 与旧 Behavior Registry 不是自动等价的事实源；
- 是否复用旧 Behavior Registry 必须单独评估。

#### MCP and Skill Boundary

本 ADR 确认以下高层原则：

- MCP 和 Skill 可以作为辅助集成方式；
- 可以用于页面探索、设备探索、元素发现、调试、资源发现、测试生成辅助和外部工具集成；
- MCP 和 Skill 不得成为生产执行事实源；
- MCP 和 Skill 不得成为 `TestCaseVersion.script_code` 的替代品；
- MCP 和 Skill 不得绕过身份认证、项目作用域、Capability Registry、
  Resource Capability Gateway、风险审批、DSL 或结构校验、Evidence 归一或审计；
- MCP 或 Skill 返回的结果默认是外部输入或建议；
- 结果必须经过 Schema、权限、来源和安全验证；
- 具体协议、产品、服务、权限模型和 Adapter 由后续 ADR 决定。

本 ADR 不批准任何具体 MCP Server 或 Skill 实现。

### 6. Multi-Platform Target

本 ADR 将以下执行平台确认为 EvieAi 的长期目标支持范围：

- Web UI
- API
- Android
- iOS

明确约束：

- 这是长期目标，不代表当前已实施；
- 不代表 Phase 0 或 Phase 1 已实现；
- DSL、Adapter、Runner 和执行技术选型由后续 ADR 决定；
- Performance、Security、Chaos 属于后续扩展目标，而非本 ADR 已接受的实施范围。

### 7. Logical Architecture and Deployment Units

本 ADR 继续明确区分逻辑领域和部署单元：

- 逻辑领域不等于独立微服务；
- 不因架构图包含多个区域就立即拆分服务；
- “模块化单体 + AI Worker + Runner Worker”只属于候选部署策略；
- ADR-0002 不决定最终服务数量；
- 部署单元由独立 ADR 决定。

本 ADR 不把以下名称写成最终定案：

- `evie-api`
- `evie-ai-worker`
- `evie-runner-worker`

### 8. Data and Knowledge Boundary

本 ADR 确认数据与知识边界的以下高层原则：

- 关系型业务事实必须有明确事实源；
- Redis、缓存、队列不得成为生命周期、审核、幂等或 Content Claim 的事实源；
- Secret 只能通过引用使用；
- 大文件和执行证据不得写入自然语言资产正文；
- 向量、索引、缓存和分析结果属于派生或附属能力；
- 具体数据库和存储产品分工延迟到后续 ADR。

### 9. Relationship to Architecture Diagrams

#### 9.1 2026-07-18 新图

新图文件：

- `docs/evie-ai/reference/2026-07-18_evie-ai-target-architecture-v2.mmd`
- `docs/evie-ai/reference/2026-07-18_evie-ai-target-architecture-v2.png`

自 ADR-0002 于 2026-07-18 被接受后，
2026-07-18 新图成为 EvieAi 已接受的目标架构参考图（Accepted Target Architecture Reference）。

它定义长期目标架构和逻辑领域关系，但不替代 Phase 实施合同、专题 ADR、数据模型或
技术选型决定。

明确约束：

- 该图在 ADR-0002 接受前的身份为 `Draft / Proposed`；
- 它现在已经获得目标架构层面的批准；
- 它仍然不是 Phase 实施合同；
- 它仍需由 `ARCHITECTURE_BASELINE`、`evie-ai-overview` 和入口文档正式收编；
- 在正式收编完成前，现有入口引用不会自动改变；
- 图中 Deferred Decisions 仍然不是已批准技术选型。

#### 9.2 2026-07-12 旧图

旧图文件：

- `docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`

ADR-0002 已接受新的长期目标架构。

2026-07-12 旧图因此不再承担最新长期目标架构的定义职责，但在入口文档和
`docs/evie-ai/reference/README.md` 完成后续收编前，本步骤不修改其文件状态或现有引用。

旧图必须：

- 继续保留；
- 不删除；
- 不覆盖；
- 继续作为历史架构演进证据；
- 继续承载 Phase 0、Phase 1 的历史实施语义。

正式的下述标签将在后续入口文档收编步骤中写入：

- `Superseded for target architecture`

届时必须同时保留以下说明：

- 仅长期目标架构表达被替换；
- 历史 Phase 合同和当时实施事实继续有效；
- 文件不得删除或覆盖。

### 10. Historical Contract Protection

本 ADR 明确保护以下历史合同：

- Phase 0 保持历史合同；
- Phase 1 `ADR-0001` 保持 `Accepted`；
- Phase 1 Specification 保持批准语义；
- Phase 1 Implementation Plan 保持实施历史；
- A-01～A-12 不重写；
- 已完成 Migration 不修改；
- frozen baseline 不修改；
- 已完成 Repository 和生命周期能力不被重新定义；
- 新架构只影响后续阶段和后续专题设计。

本 ADR 不得：

- 把未来能力写成 Phase 0 已完成；
- 把未来能力写成 Phase 1 已完成；
- 重新解释 TestAsset / TestCase 关系；
- 重新引入 Candidate、Preview、selected_candidates 或 TestPointPlan 主链。

### 11. Authority and Adoption Sequence

ADR-0002 已接受，后续建议的正式收编顺序为：

```text
ADR-0002 Accepted
→ ARCHITECTURE_BASELINE
→ evie-ai-overview
→ target-capability-map
→ README 和 reference README
→ phase-traceability
→ Phase 2～5 合同
→ 专题 ADR 和架构文档
→ 最后评估 AGENTS.md 补充
```

明确约束：

- ADR-0002 被接受也不会自动修改全部权威文档；
- 在文档收编完成前，Phase 0/1 合同继续按原优先级生效。

## Alternatives Considered

### Alternative A：继续使用旧七域架构，不引入 v2

优点：

- 当前文档无需新增 ADR；
- 现有引用关系保持稳定；
- 短期治理成本较低。

缺点：

- 无法完整表达接入层、AI 平台、资源能力域、多平台执行和数据治理；
- 无法正式区分逻辑域与部署单元；
- Phase 2～5 会继续缺乏高层目标边界。

不采用原因：

- 旧七域表达已不足以承载长期目标架构治理。

### Alternative B：直接把新图写入 AGENTS.md

优点：

- 可快速把新图内容推为硬约束；
- 能立即统一后续任务引用口径。

缺点：

- 容易把尚未批准的目标设计写成已生效合同；
- 会反向污染 Phase 0/1 历史合同；
- 风险高且难以局部审查。

不采用原因：

- `AGENTS.md` 是当前最高级硬约束之一，不应被草案图直接反写。

### Alternative C：立即按图拆成大量微服务

优点：

- 逻辑区域与服务表面上更容易一一对应；
- 有利于在图上直接映射部署边界。

缺点：

- 会在未完成领域合同前提前冻结部署拓扑；
- 容易放大复杂度、治理成本和跨服务事务风险；
- 与当前阶段最小变更和历史合同保护不一致。

不采用原因：

- 本次需要先解决逻辑架构和权威治理，不是立即批准微服务拆分。

### Alternative D：只保留架构图，不建立 ADR 和专题合同

优点：

- 文档工作量更小；
- 图像表达直观。

缺点：

- 图无法替代可审查的文字合同；
- 无法明确旧图关系、历史合同保护和后续收编顺序；
- 容易形成竞争性事实源。

不采用原因：

- 需要审查级文字合同来承接长期目标架构。

## Consequences

### Positive Consequences

ADR-0002 被接受后，形成以下架构治理结果：

- 业务领域边界更清楚。
- AI 与业务事实源分离将获得更明确的高层治理位置。
- 公共资源与能力域将获得更清晰的正式定位。
- 多平台执行将获得长期扩展结构。
- 数据与治理问题可以通过独立 ADR 分解。
- Phase 2～5 获得规划基础。
- 旧链不会因新图收编而回流到新主链。

### Costs and Trade-offs

- 文档治理成本增加。
- 需要多个后续 ADR。
- 新旧图会并存一段时间。
- 不能把图中全部能力立即转成开发任务。
- 需要持续维护目标架构与阶段范围的映射。

### Risks

- 技术候选被误读为强制选型。
- 新图被误认为当前完成状态。
- Phase 0/1 被反向修改。
- 公共资源域与 Runner 职责混淆。
- Capability Registry 与旧 Behavior Registry 混用。
- MCP / Skill 被误当作生产执行事实源。
- 逻辑域被错误拆成微服务。

## Out of Scope

本 ADR 不实施以下内容：

- 代码
- ORM
- Schema
- Migration
- Repository
- Service
- Router
- Worker
- Runner
- RAG
- Model Gateway
- 向量数据库
- API Gateway
- 多平台 DSL
- MCP
- 第三方依赖
- 基础设施部署

## Deferred Decisions

以下问题必须延迟到后续独立 ADR：

1. 接入层和服务部署
2. Model Gateway 与 Provider 隔离
3. 两类 RAG 与知识治理
4. Intent IR、Oracle、Binder、Compiler
5. 公共资源与 Capability Registry
6. Web/API/Android/iOS DSL 与 Runner Adapter
7. 数据与知识存储分工
8. 执行风险、副作用和审批
9. Stale 依赖关系
10. 人工修改 TestCase 的事实源
11. MCP/Skill 受控边界
12. Evidence 归一和失败分类
13. 可观测性、SLO 和成本
14. 逻辑领域与部署单元关系

上述问题在本 ADR 中均未被视为既定方案。

## Required Follow-up Documents

以下文档属于 ADR-0002 接受后的后续治理任务。

本步骤没有完成这些文档的收编或更新，它们仍需要逐步创建或修改：

- `ARCHITECTURE_BASELINE`
- `evie-ai-overview`
- `target-capability-map`
- `docs/evie-ai/README`
- `reference/README`
- `phase-traceability`
- Phase 2～5 合同
- 接入与部署专题
- AI 平台专题
- RAG 专题
- 公共资源专题
- Asset-to-Case 专题
- 多平台执行专题
- 数据专题
- 控制面专题
- 安全与副作用专题
- 可观测性专题
- 后续 `AGENTS.md` 补充

## Acceptance Criteria

| 验收项 | 状态 | 证据 |
|---|---|---|
| 用户明确批准 | satisfied | 用户于 2026-07-18 明确批准 ADR-0002 |
| 11 个区域无遗漏 | satisfied | Decision §1 |
| 五个核心业务域边界无冲突 | satisfied | Decision §2 |
| Phase 0/1 保护完整 | satisfied | Decision §10 |
| 新旧架构图关系明确 | satisfied | Decision §9 |
| 技术候选未成为强制选型 | satisfied | Deferred Decisions |
| 长期目标未写成当前完成状态 | satisfied | Decision、Out of Scope |
| 后续 ADR 清单完整 | satisfied | Deferred Decisions、Required Follow-up Documents |
| 引用路径验证 | satisfied | 路径检查：2026-07-18 新图、2026-07-12 旧图、ADR-0001 均存在 |
| 文档 Diff 人工审查 | satisfied | 用户明确批准当前 ADR 内容 |

## Approval Record

Approval status: Accepted
Approval date: 2026-07-18
Approval source: Explicit user approval

Approved decisions:

- Accept the 11-area target architecture.
- Accept the five core business-domain boundaries.
- Accept the relationship between the 2026-07-18 target diagram and the 2026-07-12 historical diagram.
- Confirm that Phase 0 and Phase 1 historical contracts remain unchanged.
- Confirm that technology selections and deployment topology remain deferred.

Approval limitations:

- This approval does not approve Deferred Decisions.
- This approval does not expand Phase 0 or Phase 1.
- This approval does not authorize code, database, dependency, infrastructure, or deployment changes.
- This approval does not complete the required follow-up document updates.
