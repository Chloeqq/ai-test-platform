# EvieAi Architecture Baseline

本文件定义 EvieAi 当前长期目标架构基线，并保留 2026-07-12 冻结基线的历史记录。
当前长期目标架构由已接受的 ADR-0002 治理，由本 `ARCHITECTURE_BASELINE` 统一收编和解释，
并由 2026-07-18 Mermaid 与 PNG 架构图进行可视化表达；历史基线仅用于架构演进追溯，
不再与当前目标基线并列生效。

## 1. Baseline Status

Baseline status: Active

Baseline version: Target Architecture v2

Effective date: 2026-07-18

Governing decision: [ADR-0002](decisions/ADR-0002-target-architecture-v2.md)

当前已接受的目标架构参考包括：

- [ADR-0002](decisions/ADR-0002-target-architecture-v2.md)
- [2026-07-18_evie-ai-target-architecture-v2.mmd](reference/2026-07-18_evie-ai-target-architecture-v2.mmd)
- [2026-07-18_evie-ai-target-architecture-v2.png](reference/2026-07-18_evie-ai-target-architecture-v2.png)

`ADR-0002` 已经 `Accepted`。`Target Architecture v2` 已成为 EvieAi 当前长期目标架构基线，
但这不代表所有架构区域已经实施，不自动扩大任何当前 Phase 范围，也不批准
`Deferred Decisions` 中的任何具体方案。

## 2. Authority and Scope

`ARCHITECTURE_BASELINE` 的职责是：

- 定义当前长期目标架构基线。
- 定义五个核心业务域和横向支撑层。
- 定义当前权威架构图及其解释关系。
- 定义后续实现不得破坏的高层边界。
- 定义与 Phase 合同、专题 ADR 和历史基线的关系。

`ARCHITECTURE_BASELINE` 不负责：

- 代替 Phase 实施合同。
- 代替专题架构文档。
- 代替数据模型。
- 代替 API 合同。
- 代替技术选型 ADR。
- 直接授权代码、数据库、依赖或部署变更。

资料优先关系继续受 [AGENTS.md](../../AGENTS.md) 约束。`AGENTS.md` 继续是仓库硬约束；
`ARCHITECTURE_BASELINE` 定义长期目标架构；当前 Phase 实施文档定义当期允许实施的范围。
目标架构中存在某项能力，不等于当前 Phase 可以实现该能力。

## 3. Accepted Architecture Reference

以下文件是当前目标架构参考：

- [2026-07-18_evie-ai-target-architecture-v2.mmd](reference/2026-07-18_evie-ai-target-architecture-v2.mmd)
- [2026-07-18_evie-ai-target-architecture-v2.png](reference/2026-07-18_evie-ai-target-architecture-v2.png)

解释规则如下：

- `ADR-0002` 是 `Target Architecture v2` 的 governing decision。
- `ARCHITECTURE_BASELINE` 是对已接受 `ADR-0002` 的当前统一收编解释，不得扩展或改变
  `ADR-0002`。
- Mermaid `.mmd` 文件是可维护的结构化架构源图。
- PNG 文件是 Mermaid 的可视化渲染结果。
- 目标架构语义解释顺序为：
  - `ADR-0002` accepted decision
  - `ARCHITECTURE_BASELINE` consolidated interpretation
  - Mermaid source
  - PNG rendering
- PNG 与 Mermaid 不一致时，以 Mermaid 为准。
- Mermaid 与 ADR-0002 不一致时，以 ADR-0002 为准。
- `ARCHITECTURE_BASELINE` 与 `ADR-0002` 不一致时，必须停止后续实施，通过文档修订或
  新 ADR 消除冲突，不得自行选择。
- 该顺序只用于解释 `Target Architecture v2`，不重写仓库资料优先级。
- `AGENTS.md` 仍然是仓库硬约束；当前 Phase 合同仍然决定当期允许实施范围。
- 任何实施必须同时满足 `AGENTS.md`、当前 Phase 合同、Accepted ADR 和
  `ARCHITECTURE_BASELINE`。
- Mermaid 图不能扩大当前 Phase。
- 图中的技术名称不得自动解释为已批准技术选型。
- 架构图不能代替专题合同，也不能代替 Phase 实施合同。

本步骤不修改图文件，只在本基线中正式收编其权威关系。

## 4. Eleven Logical Architecture Areas

以下 11 个区域是 EvieAi 当前长期目标架构的逻辑分区：

- 它们是逻辑架构分区，不等于 11 个微服务。
- 它们不等于当前已实施状态。
- 它们不自动成为数据库实体划分。
- 它们不自动批准部署单元。

### 4.1 用户与调用方

覆盖产品经理、测试、开发、平台管理员、CI/CD Pipeline、第三方平台、CLI、SDK Client、
API Client 和通知接收方。它定义“谁发起需求、治理、执行和反馈”，但不承担业务事实源。

### 4.2 边缘与接入层

负责统一入口、传输安全、认证入口、项目作用域验证和隔离策略执行、限流、上传和流式通信。
它负责接收认证信息、建立请求身份上下文、提取和验证 `project scope`、执行访问控制结果，
并传递 `trace`、`request` 和 `project` 上下文，但不负责领域状态转换或 Repository 事务。
它不定义项目，不持有项目事实源，不定义角色权限业务规则，不决定项目隔离政策，也不得在
接入层自行猜测或回退 `project_code`。

### 4.3 多元输入与需求智能域

负责接入需求文档、OpenAPI、缺陷、日志、手工/API/CI 输入，维护 Requirement 与
RequirementVersion，并通过 Requirement Knowledge RAG 支撑自然语言测试点生成。

### 4.4 自然语言测试资产域

负责 TestAsset、TestAssetVersion、统一 Intake、Source、Review、Audit、Idempotency、
Content Claim 和版本生命周期，保证“测什么”的版本化自然语言事实源。

### 4.5 Asset-to-Case 转换与质量拦截域

负责把锁定的自然语言资产版本转换为机器可执行表示，组织 Execution Context、Intent IR、
Binder、Quality Gate、Compiler 和 TestCaseVersion 生成。

### 4.6 公共资源与能力域

负责 Web、API、Android、iOS 资源，以及测试数据、环境、设备、Secret、Mock、安全、
性能和 Capability Registry 的独立治理，并通过统一网关输出版本化资源绑定能力。

### 4.7 测试用例、执行、证据与反馈域

负责 TestCase 和 TestCaseVersion、执行调度、Runner Orchestration、Evidence、Report、
Failure Classification 和反馈闭环，承载“如何执行”和“执行后发生了什么”。

### 4.8 大模型与 AI 能力层

负责统一模型调用边界、Prompt、结构化输出、评测、成本和两类检索支撑。它提供模型能力，
但不成为业务事实源。

### 4.9 平台控制面

负责用户和项目事实、租户或项目边界定义、角色与权限策略、项目隔离规则、审计、配额、审批、
任务、Feature Flag、统一 ID/Trace 和成本治理。它定义项目隔离和权限策略；边缘与接入层
只执行经过控制面和认证体系确认的策略。它是治理层，不替代五个核心业务域。

### 4.10 数据与知识存储层

负责事实库、快照、对象、索引、缓存、向量和分析存储支撑。它定义存储职责边界，
但不单独决定具体产品和物理分工。

### 4.11 基础设施与运维治理层

负责部署、容器与编排、任务执行、可观测性、安全、备份和运维支撑。它提供运行底座，
但不定义核心业务事实。

## 5. Five Core Business Domains

以下五个领域是 11 个逻辑区域中的核心业务域。

### 5.1 多元输入与需求智能域

核心职责：理解需求、维护 `Requirement` / `RequirementVersion`、建立 Requirement Knowledge RAG，
并生成自然语言测试点。

主要输入：需求文档、OpenAPI、缺陷、日志、手工输入、API / CI / 批量提交。

主要输出：`Requirement` / `RequirementVersion`、生成上下文、自然语言测试资产输入。

最重要的禁止越界事项：不得生成执行 DSL，不得创建可执行 `TestCase`，不得绑定执行资源，
不得调用 `Runner`。

### 5.2 自然语言测试资产域

核心职责：管理 `TestAsset`、`TestAssetVersion`、Intake、Source、Review、Audit、
Idempotency、Content Claim 和版本生命周期。

主要输入：上游域输出的自然语言测试点，以及手工/API 直接提交的自然语言资产。

主要输出：版本化自然语言测试资产、审核与审计事实、供 Asset-to-Case 使用的稳定资产身份。

最重要的禁止越界事项：不得保存机器步骤，不得保存 DSL，不得保存 `script_code`，
不得调用 `Compiler` 或 `Runner`。

### 5.3 Asset-to-Case 转换与质量拦截域

核心职责：它是自然语言转机器执行表示的唯一合法入口，负责锁定明确的
`TestAssetVersion`、管理 `ConversionAttempt`、组织执行上下文、质量门和平台编译。

主要输入：已锁定的 `TestAssetVersion`、版本化资源和能力绑定结果、平台策略与转换规则。

主要输出：`ConversionAttempt`、`Bound Execution Plan`、`TestCase`、`TestCaseVersion`
和转换追踪记录。

最重要的禁止越界事项：不得修改 `TestAssetVersion` 正文，不得重新建立 Candidate 产品主链，
不得直接执行测试，不得在 Runner 阶段重新理解自然语言。

### 5.4 公共资源与能力域

核心职责：治理版本化资源和能力，为转换域和执行域提供 Web/API/移动端资源、测试数据、
环境、设备、Secret 引用、Mock、安全和性能能力。

主要输入：资源元数据、资源版本、治理策略、环境与凭证引用。

主要输出：版本化资源描述、能力解析决策和 `Resource Binding` 结果。

最重要的禁止越界事项：不得控制 `TestAsset` 生命周期，不得替代 Asset-to-Case，
不得替代 Runner Orchestrator。

### 5.5 测试用例、执行、证据与反馈域

核心职责：执行 `TestCaseVersion`、管理调度、证据、报告、失败归因和反馈闭环。

主要输入：`TestCaseVersion`、资源绑定快照、执行策略和运行时参数。

主要输出：`Execution`、`StepResult`、`AssertionResult`、`Evidence`、`Report`
以及失败和反馈治理结果。

最重要的禁止越界事项：不得重新理解 `TestAsset`，不得运行时重新编译，不得修改
`TestAssetVersion`，不得绕过版本化资源绑定。

## 6. Core Facts and Authority Boundaries

当前基线确认以下唯一事实源：

- 需求正文：`RequirementVersion`
- 自然语言测试资产正文：`TestAssetVersion`
- 可执行脚本：`TestCaseVersion.script_code`
- 执行事实：`Execution / StepResult / AssertionResult / Evidence`
- 报告：由执行事实派生

同时明确：

- `Requirement` 和 `TestAsset` 只维护聚合身份、状态和当前版本指针。
- 派生上下文、检索证据、Intent IR、Bound Plan、DSL 中间结果不能替代正文或脚本事实源。
- `Report` 不得反向覆盖执行事实。
- Redis、缓存、队列、向量索引和分析结果不得成为核心业务事实源。
- Secret 只能使用引用。
- AI 不得生成、覆盖或猜测权威数据库 ID。

本基线不设计新的数据库表。

## 7. Stable Architectural Boundaries

以下边界已经作为稳定架构边界生效：

- `TestAsset` 表达“测什么”。
- `TestCase` 表达“如何执行”。
- 两者生命周期分离。
- `Candidate`、`Preview`、`selected_candidates`、`TestPointPlan` 不得回归主链。
- AI 生成侧只生成自然语言测试点。
- Requirement Knowledge RAG 与 `Execution Context Retrieval` 分离。
- Asset-to-Case 是唯一自然语言转机器语言入口。
- 公共资源只能经过独立治理和版本化后绑定。
- Runner 只执行版本化可执行输入和运行时资源引用。
- Runner 不重新理解自然语言。
- MCP 和 Skill 只能作为受控辅助输入或集成方式。
- 逻辑领域不等于独立微服务。
- Phase 0、Phase 1 历史合同不得被反向修改。
- 技术候选仍需独立 ADR。

## 8. OpenAPI Dual Governance Role

OpenAPI 在 EvieAi 中可以同时承担两类角色：

- 作为需求理解输入。
- 作为版本化 API 执行资源。

但它们必须经过两条不同治理链：

- 作为需求输入时，它服务于需求理解、业务行为提取和自然语言测试资产生成。
- 作为执行资源时，它必须独立导入、验证、版本化并接受项目作用域治理。

因此：

- 作为需求输入，不等于已经成为可执行资源。
- 执行资源必须独立治理。
- 具体实现由后续专题 ADR 决定。

## 9. Cross-Cutting Areas

### 9.1 边缘与接入层

该层提供传输安全、认证入口、项目作用域验证和隔离策略执行、限流、Trace、上传和流式通信。
它负责建立并传递请求身份、`request`、`trace` 和 `project` 上下文，拒绝缺失或非法作用域的
请求；但它不得定义项目事实、权限业务规则或隔离策略，也不得承担领域状态转换或
Repository 事务。

### 9.2 大模型与 AI 能力层

该层提供统一模型能力边界、结构化输出和两类检索支撑。它不得成为业务事实源，也不得绕过
领域流程、权威 ID 分配或受控绑定。

### 9.3 平台控制面

该层提供用户和项目事实、租户或项目边界定义、角色与权限策略、项目隔离规则、审计、配额、
审批、任务、Feature Flag、Trace 和成本治理。它定义项目隔离和权限策略；边缘与接入层
只执行经过控制面和认证体系确认的策略。它不得替代五个核心业务域。

### 9.4 数据与知识存储层

该层提供事实、快照、对象、索引、缓存和分析能力的存储支撑。具体产品和物理分工仍属于
`Deferred Decisions`。

### 9.5 基础设施与运维治理层

该层提供运行时、任务执行、可观测性、安全、备份和运维支撑。它不定义核心业务事实。

## 10. Multi-Platform Target

当前长期目标平台包括：

- Web UI
- API
- Android
- iOS

同时必须明确：

- 这不代表上述平台已经实施。
- 不代表 Phase 0 或 Phase 1 已实现多平台执行。
- DSL、Adapter、Runner、Worker 和设备资源设计仍需后续 ADR。
- Performance、Security、Chaos 属于后续扩展目标。

## 11. Logical Architecture vs Deployment

当前基线明确：

- 领域划分不等于服务拆分。
- 当前基线不批准最终服务数量。
- “模块化单体 + AI Worker + Runner Worker”仍是候选部署策略。
- `evie-api`、`evie-ai-worker`、`evie-runner-worker` 不得在本基线中写成最终定案。
- 最终部署策略由后续 ADR 决定。

## 12. Historical Architecture Relationship

历史目标架构图为：

- [2026-07-12_evie-ai-architecture-flow.mmd](reference/2026-07-12_evie-ai-architecture-flow.mmd)

当前基线明确：

- 它不再定义最新长期目标架构。
- 它在当前基线中的状态是 `Superseded for target architecture`。
- 它只是在长期目标架构表达上被替代。
- 它不得删除、不得覆盖。
- 它继续保留为架构演进证据。
- Phase 0、Phase 1 和当时实施事实继续有效。
- 旧图中的有效历史边界不因 `Superseded for target architecture` 而失效。

本步骤只在 `ARCHITECTURE_BASELINE` 中记录该关系，不修改旧图文件、README 或
`reference/README`。

## 13. Historical Contract Protection

当前基线必须继续保护以下历史合同和历史事实：

- [phase-0-domain-model.md](implementation/phase-0-domain-model.md)
- [ADR-0001-phase1-natural-language-asset-lifecycle.md](decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md)
- [phase-1-natural-language-asset-lifecycle-specification.md](implementation/phase-1-natural-language-asset-lifecycle-specification.md)
- [phase-1-natural-language-asset-lifecycle-plan.md](implementation/phase-1-natural-language-asset-lifecycle-plan.md)
- A-01～A-12
- 已完成 Migration
- frozen baseline
- 已完成 Repository 和生命周期能力
- [legacy-chain-freeze-list](migration/legacy-chain-freeze-list.md)

因此不得把以下能力写成 Phase 0 / Phase 1 已完成能力：

- RAG
- 多平台执行
- AI Platform
- Runner Orchestration 扩展能力

## 14. Deferred Decisions

以下内容仍未被批准，必须继续保持为 `Deferred Decisions`：

- 接入层产品与部署。
- Model Gateway 和 Provider Adapter 具体设计。
- 两类 RAG 的数据、索引和评估设计。
- Intent IR、Oracle、Binder、Compiler、Preflight 具体模型。
- Capability Registry 和 Resource Capability Gateway 实现。
- Web、API、Android、iOS DSL 与 Runner Adapter。
- 数据和知识存储产品分工。
- 执行风险、副作用与审批。
- Stale 依赖关系。
- 人工编辑 `TestCase` 的事实源关系。
- MCP / Skill 具体实现。
- Evidence 归一、Failure Classification、Flaky 和 Quarantine。
- 可观测性、SLO 和成本。
- 逻辑领域与部署单元。
- 任何新增第三方依赖。

`Target Architecture v2` 中出现这些概念，不代表它们的具体方案已经批准。

## 15. Phase Boundary

截至本基线生效日 2026-07-18，当前有效实施合同仍为
`EvieAi Phase 1 Asset Lifecycle Core`。

该描述是基线生效时点的历史状态，不是永久性的当前阶段声明。

截至 2026-07-18 的有效实施合同记录包括：

- [phase-1-natural-language-asset-lifecycle-specification.md](implementation/phase-1-natural-language-asset-lifecycle-specification.md)
- [phase-1-natural-language-asset-lifecycle-plan.md](implementation/phase-1-natural-language-asset-lifecycle-plan.md)
- [ADR-0001-phase1-natural-language-asset-lifecycle.md](decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md)

2026-07-18 之后实际生效的当前阶段，应以以下资料为准：

- [phase-traceability.md](implementation/phase-traceability.md)
- 对应阶段已接受的 ADR
- 对应阶段的 Specification
- 对应阶段的 Implementation Plan

`ARCHITECTURE_BASELINE` 定义长期目标架构，不承担动态维护实施进度的职责。
Phase 文档决定当期实施范围；架构基线决定长期正确方向；任何任务必须同时满足两者。
架构基线允许但当前 Phase 未授权的能力，不得实施；新 Phase 合同也不得违反已接受的目标
架构基线。Phase 0、Phase 1 继续保持历史语义；Phase 2～5 仍需后续独立建立正式合同。

## 16. Follow-up Adoption Sequence

后续文档应按以下顺序继续收编，但本步骤不执行后续项：

```text
ARCHITECTURE_BASELINE
→ evie-ai-overview
→ target-capability-map
→ docs/evie-ai/README
→ docs/evie-ai/reference/README
→ phase-traceability
→ Phase 2～5 合同
→ 专题 ADR 和专题架构
→ engineering standards
→ 最后评估 AGENTS.md
```

当前步骤只完成第一项：`ARCHITECTURE_BASELINE`。

## 17. Change Control

未来如需修改本架构基线，必须：

- 有新的 `Accepted` ADR，或明确更新 `ADR-0002`。
- 说明对五个核心业务域和 11 个区域的影响。
- 说明对 Phase 合同的影响。
- 说明对历史合同的影响。
- 不得仅根据代码现状修改目标架构。
- 不得仅根据单张图片修改硬约束。
- 不得把技术候选直接升级为强制方案。

架构决策记录继续使用：

`docs/evie-ai/decisions/ADR-XXXX-<topic>.md`

## 18. Previous Baseline

### 18.1 Historical Baseline Record

上一版长期目标基线记录如下：

Previous baseline status: Frozen historical baseline

Previous baseline version: EvieAi Architecture Baseline 2026-07-12

Previous baseline effective date: 2026-07-12

该基线保留 2026-07-12 时点的目标架构表达、文件集合和阶段治理信息，仅用于历史追溯，
不再作为当前长期目标架构基线。

### 18.2 Historical Baseline File Set

以下清单是 2026-07-12 时点的历史路径快照。它记录这些文件当时参与旧基线的事实、
内容身份和治理作用，不代表这些路径当前版本仍属于旧基线，也不冻结其在新 `Accepted ADR`
下的后续合法更新。

后续修改这些文件时，必须保留 Git 历史和架构演进记录；不得通过修改当前文件反向改写
2026-07-12 的历史事实。需要追溯旧内容时，应通过 Git 历史、冻结提交和当时留档获取，
不得根据文件当前内容反向解释旧基线。

2026-07-12 冻结基线历史上覆盖以下文件集合：

- `AGENTS.md`
- `docs/evie-ai/README.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/natural-language-test-assets.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/engineering/coding-standards.md`
- `docs/evie-ai/implementation/phase-0-domain-model.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-specification.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-plan.md`
- `docs/evie-ai/implementation/phase-traceability.md`
- `docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`
- `docs/evie-ai/migration/legacy-chain-freeze-list.md`
- `docs/evie-ai/migration/docs-cleanup-plan.md`
- `docs/evie-ai/reference/README.md`
- `docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`
- `docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`

### 18.3 Historical Frozen Core Decisions

2026-07-12 冻结基线保留的核心决策包括：

- 自然语言 `TestAsset` 是一等持久化业务实体。
- `TestAsset` 表达“测什么”，`TestCase` 表达“如何执行”。
- AI 生成侧只生成自然语言测试点。
- 所有资产生产者进入统一资产入库。
- Candidate 退出 EvieAi 产品主链。
- Asset-to-Case 是唯一自然语言转机器语言入口。
- 每个 `ConversionAttempt` 锁定明确的 `TestAssetVersion`。
- 资源只能通过 `Resource Capability Gateway` 解析和绑定。
- `TestCaseVersion.script_code` 是执行代码唯一事实源。
- Runner 只执行，不重新理解自然语言。
- 版本化事实不得原地覆盖。
- `review_status` 和 `conversion_status` 相互独立。
- 失败反馈不得未经审核覆盖版本化事实源。
- Phase 文档定义当前实施边界。
- Excel 和架构图不得自动扩大当前任务范围。

这些历史决策继续作为 2026-07-12 时点的历史事实有效，但当前长期目标架构仍以
`ADR-0002` 和现行 `ARCHITECTURE_BASELINE` 为准。

### 18.4 Historical Phase Note

2026-07-12 冻结基线同时记录：当前实施阶段为 `EvieAi Phase 1 Asset Lifecycle Core`，
且 Phase 0 已建立最小持久化基线。该历史记录继续有效，但它属于实施边界历史，
不再承担当前长期目标架构基线的定义职责，也不得替代当前阶段资料对实际生效阶段的判断。
