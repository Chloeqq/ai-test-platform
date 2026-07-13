# EvieAi 架构总览

日期：2026-07-12
状态：Authoritative
适用范围：EvieAi 完整目标架构、领域边界、主链路、横向治理和阶段实施校验

本文保存 EvieAi 的总体架构、分层职责、主链路、事实源、状态边界和旧链迁移原则。

完整业务背景与详细设计参考：

- `docs/evie-ai/architecture/natural-language-test-assets.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/implementation/phase-traceability.md`
- EvieAi 架构 Mermaid 图：`docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
- Excel 完整设计参考：`docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`

本文描述 EvieAi 的完整目标架构，不代表所有能力在当前阶段同时实施。

发生冲突时，优先级如下：

1. 用户当前任务中的明确确认
2. `AGENTS.md`
3. 当前阶段实施文档
4. 本文及相关架构专题
5. EvieAi 架构图
6. Excel 完整设计参考
7. 旧文档
8. 旧代码现状

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

---

## 1. 架构目标

EvieAi 的目标是建立一条以自然语言测试资产为核心、以版本和来源为基础、以 Asset-to-Case 为唯一机器转换入口、以版本化资源绑定和可执行用例为执行事实源的测试资产全生命周期平台。

核心原则：

1. 自然语言 `TestAsset` 是一等持久化业务实体。
2. `TestAsset` 表达“测什么”，`TestCase` 表达“如何执行”。
3. AI 生成只生产自然语言测试点，不生成机器步骤。
4. 所有来源统一进入同一个资产入库服务。
5. Candidate、Preview、selected candidates 不属于 EvieAi 产品主链。
6. 自然语言到机器语言只允许发生在 Asset-to-Case。
7. Asset-to-Case 必须锁定明确的 `TestAssetVersion`。
8. 页面对象、数据、环境、凭证、Mock、安全、性能等资源，只能在转换阶段通过资源能力网关解析和绑定。
9. `TestCaseVersion.script_code` 是可执行代码唯一事实源。
10. Runner 只执行已生成的 `script_code` 和运行时资源引用。
11. 版本化事实不得原地覆盖。
12. 审核状态、转换状态、用例状态和执行状态必须独立。
13. 低质量、低置信度、存在歧义或暂不可执行的自然语言资产，也必须允许入库。
14. 失败分析只能产生归因、建议和治理任务，不能未经审核直接覆盖版本化事实源。
15. 架构图和 Excel 定义完整目标空间，Phase 文档定义当前实施边界。

---

## 2. 七个架构域

EvieAi 完整目标架构由七个领域组成：

```text
1. 多元输入与自然语言生成域
2. 自然语言测试资产域
3. Asset-to-Case 转换与统一质量门域
4. 公共资源与能力域
5. 测试用例、执行、证据与反馈域
6. 平台控制面
7. 技术基础设施域
```

三个横向关注点贯穿所有领域：

```text
A. 版本与唯一事实源
B. 覆盖与端到端追溯
C. 安全、数据治理与 AI 治理
```

---

## 3. 总体主链路

EvieAi 的核心主链不是单一“AI 生成链”，而是多个生产者统一进入自然语言资产中心。

### 3.1 AI 生成路径

```text
需求文档 / OpenAPI / 缺陷 / 日志
→ Input Adapter
→ GenerationContext
→ AI 生成自然语言测试点
→ 统一资产入库
```

### 3.2 直接资产路径

```text
手工录入 / API 直接提交 / CI / 批量导入
→ 自然语言测试资产输入
→ 统一资产入库
```

### 3.3 统一资产主链

```text
统一资产入库
→ 后端分配权威 ID
→ 来源绑定
→ 幂等检查
→ 精确重复检测
→ 疑似语义重复标记
→ TestAsset / TestAssetVersion 持久化
→ 资产中心
→ 用户编辑、版本、审核、来源追踪
```

### 3.4 转换与执行主链

```text
用户或系统发起转换
→ 锁定 TestAssetVersion
→ 创建 ConversionAttempt
→ 场景识别
→ Execution Requirement Manifest
→ Resource Capability Gateway
→ Resource Bindings
→ ResourceBindingSnapshot
→ Bound Execution Plan
→ 测试用例矩阵展开
→ 统一转换质量门
→ Compiler Router
→ TestCase
→ TestCaseVersion
→ script_code
→ TestPlan / Scheduler / ExecutionControl
→ RunnerRouter
→ Runner
→ Execution / ExecutionStepResult
→ RetryAttempt / CleanupResult
→ Evidence / Report
→ Failure Analysis / Flaky Governance
```

---

## 4. 多元输入与自然语言生成域

### 4.1 职责

该领域负责：

- 接收需求文档、OpenAPI、缺陷、日志等机器或半结构化输入。
- 接收 Web、API、CI、批量任务触发。
- 建立 `GenerationContext`。
- 记录输入来源、调用方、项目作用域、模型配置和追踪信息。
- 调用 AI 生成自然语言测试点。
- 将生成结果立即提交给统一资产入库服务。

### 4.2 输入适配器

建议使用统一 Input Adapter 抽象：

```text
RequirementDocumentAdapter
OpenAPIAdapter
DefectAdapter
LogAdapter
ManualInputAdapter
BatchImportAdapter
CIAdapter
```

不同适配器只负责把来源转换为统一输入契约，不得各自实现资产保存逻辑。

### 4.3 GenerationContext

模型调用前必须建立生成上下文。

至少包含：

- `generation_context_id`
- `project_code`
- `source_type`
- 来源业务 ID
- 来源版本 ID
- 调用入口
- actor
- trace_id
- batch_id
- model/provider
- prompt_version
- parameters
- schema_version
- 数据分类
- 安全策略

AI 不得生成这些权威上下文字段。

### 4.4 输出边界

AI 生成侧只允许输出自然语言资产字段，例如：

- `title`
- `precondition`
- `natural_steps`
- `expected_result`
- `priority`
- `tags`

生成侧不得：

- 生成 `action / target / value`
- 生成 `structured_steps`
- 生成 Locator 或 Selector
- 调用 Behavior Registry
- 调用 ContractValidator
- 调用 Compiler
- 调用 Runner
- 生成 `script_code`
- 创建 TestCase
- 分配权威数据库 ID

### 4.5 直接输入不经过 AI

以下入口不应强制经过 AI：

- 手工录入
- API 直接提交
- CI 直接提交
- 批量导入自然语言测试资产

AI 只是资产生产者之一，不是所有资产的必经入口。

---

## 5. 自然语言测试资产域

### 5.1 职责

该领域负责：

- 统一资产入库。
- 后端分配权威 ID。
- 来源绑定。
- 幂等处理。
- 精确重复检测。
- 疑似语义重复标记。
- 保存 `TestAsset` 和 `TestAssetVersion`。
- 维护审核状态和转换状态。
- 支持编辑、版本、来源追踪、软删除和审计。
- 为覆盖关系和后续转换提供稳定资产身份。

### 5.2 核心实体

```text
TestAsset
TestAssetVersion
TestAssetSource
AssetReviewRecord
```

后续可扩展：

```text
AssetQualityAssessment
AssetDuplicateRelation
AssetCoverageRelation
AssetAutomationEligibility
```

### 5.3 自然语言字段边界

资产内容只保存在 `TestAssetVersion`。

允许字段：

- `title`
- `precondition`
- `natural_steps`
- `expected_result`
- `priority`
- `tags`

禁止字段：

- `action`
- `target`
- `value`
- `locator`
- `selector`
- `structured_steps`
- `steps_hint`
- `compiler_ir`
- `dsl`
- `script_code`
- Runner 专用步骤

### 5.4 统一资产入库语义

资产入库默认不因以下原因阻断：

- 质量低
- 置信度低
- 暂不可执行
- 缺少页面对象
- 缺少测试数据
- 缺少环境资源
- 存在疑似语义重复
- 预期结果不完整
- 自然语言存在歧义

不同检查的行为：

| 检查 | 行为 |
|---|---|
| 相同幂等请求 | 返回已有结果 |
| 精确重复 | 按 Intake 规则复用、关联或返回已有资产 |
| 疑似语义重复 | 标记，不阻断 |
| 低质量 | 入库后异步评估 |
| 暂不可执行 | 仍然入库 |
| 资源缺失 | 不影响资产入库 |

### 5.5 编辑与版本

编辑资产时：

```text
TestAsset
→ 创建新的 TestAssetVersion
→ 更新 current_version
```

不得原地覆盖历史版本。

每个版本必须保留：

- `test_asset_version_id`
- `version_no`
- 内容
- 内容指纹
- 创建人
- 创建时间
- 来源和审计关联

### 5.6 状态边界

`review_status` 与 `conversion_status` 独立。

示例：

```text
review_status = approved
conversion_status = blocked
```

资产审核不等于可转换成功。

建议状态：

```text
review_status:
pending / approved / rejected

conversion_status:
not_started / processing / blocked / succeeded / stale
```

---

## 6. Asset-to-Case 转换与统一质量门域

### 6.1 职责

该领域是自然语言转机器语言的唯一入口。

负责：

- 创建 `ConversionAttempt`
- 锁定明确的 `TestAssetVersion`
- 场景识别
- 执行需求分析
- 生成 `ExecutionRequirementManifest`
- 调用资源能力网关
- 形成资源绑定
- 保存 `ResourceBindingSnapshot`
- 生成 `BoundExecutionPlan`
- 展开测试用例矩阵
- 执行统一转换质量门
- 路由到 Compiler
- 创建 `TestCase` 和 `TestCaseVersion`
- 保存 `script_code`
- 记录转换诊断和失败原因

### 6.2 版本锁定

每次转换必须明确绑定：

```text
ConversionAttempt.test_asset_version_id
```

转换开始后，即使用户编辑资产并产生新版本：

- 当前 Attempt 继续基于原版本。
- 不得自动切换到新版本。
- 新版本需要新的 ConversionAttempt。
- 已生成 TestCase 必须可追溯到对应 TestAssetVersion。

### 6.3 Execution Requirement Manifest

Manifest 表达“要执行这个资产，需要什么”。

例如：

- 场景类型
- 页面对象需求
- 数据需求
- 环境需求
- 凭证需求
- Mock需求
- 异常注入需求
- 安全能力需求
- 性能能力需求
- 原子动作能力需求

Manifest 不应直接包含最终脚本。

### 6.4 Resource Bindings

资源解析必须通过：

```text
Asset-to-Case
→ Resource Capability Gateway
→ 各资源提供方
```

Asset-to-Case 不得直接查询具体资源表并自行解释资源语义。

### 6.5 Bound Execution Plan

Bound Plan 是经过资源解析后的机器可编译计划。

必须包含：

- 锁定的 TestAssetVersion
- Manifest版本
- 资源绑定
- 资源版本
- 场景参数
- 数据矩阵
- 环境约束
- 编译目标
- 质量门输入
- 可追踪哈希

### 6.6 统一转换质量门

质量门只在转换域中执行。

检查对象包括：

- Manifest完整性
- 资源绑定完整性
- Bound Plan一致性
- 编译目标合法性
- 权限与安全约束
- 数据和环境可用性
- 生成矩阵规模
- 不可恢复阻塞问题

资产生成和资产入库阶段不得提前执行转换质量门。

### 6.7 转换失败语义

转换失败时：

- 保留 TestAsset
- 保留 TestAssetVersion
- 保留用户编辑
- 更新 ConversionAttempt
- 保存结构化错误
- 不创建无效 TestCase
- 不创建无效 TestCaseVersion
- 不写入空或部分 `script_code`
- 不回写或篡改自然语言资产

### 6.8 转换关系

允许：

```text
TestAsset 1
→ ConversionAttempt N
→ TestCase N
```

不同环境、资源、数据矩阵和执行目标可以产生多个 TestCase。

---

## 7. 公共资源与能力域

### 7.1 职责

该领域统一管理 Asset-to-Case 所需的可执行资源和能力。

包括：

- 页面对象中心
- 测试数据工厂
- 环境中心
- 凭证中心
- Mock能力
- 异常注入能力
- 安全测试能力
- 性能测试能力
- 原子能力注册
- 规则与治理策略
- 资源版本
- 资源健康状态
- 容量与可用性

### 7.2 Resource Capability Gateway

资源能力网关是 Asset-to-Case 访问资源的唯一入口。

网关职责：

- 根据 Manifest 查询资源能力。
- 屏蔽不同资源中心的数据结构。
- 返回版本化资源描述。
- 记录解析决策。
- 返回可用性和阻塞原因。
- 生成资源绑定结果。

资源返回至少包含：

- resource_id
- resource_version_id
- capability_type
- binding_status
- resolution_decision
- health_status
- unavailable_reason
- policy_version

### 7.3 ResourceBindingSnapshot

生成 TestCase 时必须保存资源绑定快照。

快照用于回答：

- 当时绑定了哪个页面对象版本。
- 当时使用了哪个环境。
- 当时使用了哪个数据集或数据策略。
- 当时使用了哪个 Mock、凭证引用或能力版本。
- 后续资源变化后，旧 TestCase 为什么仍按原方式生成。

### 7.4 访问限制

Asset-to-Case 不得：

- 直接查询 PageObject表并自行拼装。
- 直接读取明文凭证。
- 直接选择默认环境。
- 直接绕过资源治理策略。
- 使用无版本资源创建长期可执行用例。

---

## 8. 测试用例、执行、证据与反馈域

### 8.1 职责

该领域负责：

- 管理可执行 TestCase。
- 管理 TestCaseVersion。
- 管理 `script_code`。
- 管理测试套件、计划和活动。
- 进行环境和数据预占。
- 调度执行。
- 控制并发、取消、暂停和超时。
- 路由 Runner。
- 保存步骤级执行结果。
- 保存重试和清理结果。
- 保存证据和报告。
- 进行 Flaky识别、隔离和治理。
- 生成失败归因和治理建议。

### 8.2 核心对象

```text
TestCase
TestCaseVersion
TestSuite
TestPlan
TestCampaign
TestPlanExecution
Scheduler
ExecutionControl
RunnerRouter
Execution
ExecutionStepResult
RetryAttempt
CleanupResult
Evidence
Report
FlakyRecord
QuarantineRecord
```

### 8.3 TestCase 与 TestCaseVersion

`TestCase` 保存稳定身份和当前版本。

`TestCaseVersion` 保存：

- script_code
- resource_binding_snapshot
- compiler版本
- Bound Plan哈希
- schema版本
- 创建信息
- 状态

`script_code` 只能存在于 TestCaseVersion 等版本化执行事实中。

### 8.4 用例状态

建议区分：

```text
ready
stale
disabled
```

示例：

- 资产新版本产生后，旧 TestCase 可能变为 stale。
- 资源版本失效后，相关 TestCase 可能变为 stale。
- 人工停用的 TestCase 为 disabled。

### 8.5 执行控制

执行域至少应支持：

- 调度
- 并发限制
- 取消
- 暂停
- 超时
- 重试策略
- 环境预占
- 数据预占
- 清理
- Runner路由

### 8.6 Runner 硬边界

Runner 只读取：

- `TestCaseVersion.script_code`
- ResourceBindingSnapshot
- 运行时环境和凭证引用
- 明确执行参数

Runner 不得：

- 重新理解自然语言资产
- 重新解析自然语言
- 运行时重新编译
- 运行时生成机器步骤
- 修改 TestAsset
- 修改 TestAssetVersion
- 推断缺失页面对象
- 静默使用默认项目、环境或账号

### 8.7 执行事实

执行事实源包括：

```text
Execution
ExecutionStepResult
RetryAttempt
CleanupResult
Evidence
```

Report 由执行事实派生，不是底层事实源。

### 8.8 Flaky 和隔离

Flaky治理至少包括：

- 重复失败模式识别
- 环境波动识别
- 页面对象不稳定识别
- 数据污染识别
- Runner差异识别
- 隔离策略
- 解除隔离规则
- 人工审核

---

## 9. 失败分析与反馈边界

执行失败后，可以生成：

- FailureAttribution
- FailureCategory
- RootCauseCandidate
- RepairRecommendation
- ReviewTask
- ResourceGovernanceEvent
- AssetReviewSuggestion

正确链路：

```text
执行失败
→ Failure Analysis
→ Attribution
→ Recommendation / Review Task
→ 人工或受控自动化决策
→ 创建新版本
```

不得：

```text
执行失败
→ 自动覆盖 TestAssetVersion
```

也不得未经审核自动覆盖：

- PageObjectVersion
- TestData版本
- Environment配置
- TestCaseVersion
- script_code

任何修复必须通过新版本或受控治理流程完成。

---

## 10. 平台控制面

### 10.1 职责

平台控制面负责横向平台治理。

包括：

- 项目作用域和数据隔离
- 租户隔离能力
- 统一 ID
- Trace / Request / Batch
- 版本管理
- 审计日志
- 异步任务
- 事件总线
- 事件幂等消费
- RBAC
- Feature Flag
- API Gateway
- Schema版本管理
- 配置管理
- 数据分类
- 数据保留和删除策略
- AI治理
- Release / Build / Deployment / Commit追踪

### 10.2 项目与租户

Phase 0 复用：

```text
TestProject.project_code
```

完整目标中仍需保留：

- tenant作用域
- project作用域
- 权限隔离
- 数据隔离
- 配置隔离
- 审计隔离

### 10.3 异步任务与事件

适合异步处理的能力：

- AI生成
- 质量评估
- 语义重复分析
- 转换
- 批量编译
- 执行调度
- 报告生成
- 失败分析
- 数据清理

事件必须具备：

- event_id
- event_type
- schema_version
- producer
- trace_id
- project_code
- aggregate_id
- occurred_at
- idempotency_key

### 10.4 AI治理

AI治理至少记录：

- model
- provider
- prompt_version
- parameters
- token_usage
- cost
- latency
- fallback
- schema_validation
- safety_result
- data_classification
- PII处理结果
- evaluation结果

模型名、Prompt和参数必须配置化和版本化。

---

## 11. 技术基础设施域

### 11.1 职责

该领域为 EvieAi 提供运行底座。

包括：

- 容器与 Kubernetes
- MySQL / PostgreSQL 等关系数据库
- Redis
- 对象存储
- 消息队列
- 异步任务基础设施
- CI/CD
- 配置中心
- Vault / KMS / Secret管理
- 日志、指标、Trace
- 告警
- 容量治理
- 限流
- 弹性伸缩
- 备份
- 恢复
- 灾备
- 数据归档
- 数据保留与删除
- 依赖和制品管理

### 11.2 与控制面的区别

```text
平台控制面：
业务和平台治理规则

技术基础设施域：
支撑平台运行的技术底座
```

例如：

- RBAC属于控制面。
- 身份认证服务部署属于基础设施。
- Feature Flag规则属于控制面。
- Feature Flag存储和分发基础设施属于基础设施。
- 数据保留策略属于控制面。
- 对象存储生命周期配置属于基础设施。

---

## 12. 版本与唯一事实源

同一业务事实只能有一个权威存储位置。

| 业务事实 | 唯一事实源 |
|---|---|
| 需求正文 | RequirementVersion |
| 当前需求版本 | Requirement.current_version |
| 自然语言测试资产正文 | TestAssetVersion |
| 当前资产版本 | TestAsset.current_version |
| 转换事实 | ConversionAttempt |
| 执行需求 | ExecutionRequirementManifest |
| 资源绑定 | ResourceBindingSnapshot |
| 编译输入 | BoundExecutionPlan |
| 可执行代码 | TestCaseVersion.script_code |
| 执行事实 | Execution / ExecutionStepResult |
| 重试事实 | RetryAttempt |
| 清理事实 | CleanupResult |
| 证据事实 | Evidence |
| 报告 | 由执行事实派生 |
| 环境配置 | Settings / 配置中心 |
| 敏感信息 | Credential / Secret reference |

禁止：

- 在 Requirement 和 RequirementVersion 双写正文。
- 在 TestAsset 和 TestAssetVersion 双写自然语言内容。
- 在多个模块维护同一状态转换规则。
- 把缓存或派生结果当作主事实源。
- 在 Runner 中重新解释 TestAsset。
- 原地覆盖历史版本。

---

## 13. 状态模型

不同生命周期必须使用独立状态字段。

### 13.1 资产审核状态

```text
review_status:
pending / approved / rejected
```

### 13.2 资产转换状态

```text
conversion_status:
not_started / processing / blocked / succeeded / stale
```

### 13.3 用例状态

```text
test_case_status:
ready / stale / disabled
```

### 13.4 执行状态

```text
execution_status:
queued / running / passed / failed / cancelled / timed_out / blocked
```

### 13.5 资源绑定状态

```text
binding_status:
resolved / partial / blocked / unavailable
```

禁止用单一 `status` 同时表达审核、转换、用例和执行生命周期。

---

## 14. 覆盖与端到端追溯

EvieAi 需要建立需求到执行结果的完整追溯链。

建议关系：

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
→ Evidence / Report
```

系统应能够回答：

- 哪条需求有自然语言测试资产。
- 哪条验收标准尚未覆盖。
- 哪个资产来自哪个需求版本。
- 哪个资产版本产生了哪些用例。
- 哪个资源版本参与了用例生成。
- 哪次执行验证了哪个需求版本。
- 需求变化后哪些资产变旧。
- 资产变化后哪些 TestCase 变旧。
- 资源变化后哪些 TestCase 需要重新转换。

---

## 15. 安全、数据治理与保留

EvieAi 必须支持：

- 数据分类
- 敏感字段识别
- PII处理
- Secret引用
- 日志脱敏
- 证据脱敏
- Prompt安全
- 模型输入输出安全
- 数据保留
- 归档
- 删除
- Legal Hold
- 审计
- 访问控制

不得在以下位置保存明文 Secret：

- TestAsset
- TestCase
- script_code
- Prompt
- 模型响应
- 日志
- 报告
- 截图
- 网络记录

---

## 16. 架构质量与工程约束

所有实现必须遵守：

- `AGENTS.md`
- `docs/evie-ai/engineering/coding-standards.md`
- 当前 Phase 文档

关键工程原则：

- 禁止散落业务硬编码
- 配置化
- 参数化
- 模块化
- 单一职责
- 唯一事实源
- 强事务一致性
- 幂等
- 版本不可变
- 显式状态机
- 结构化异常
- 安全日志
- 自动化架构守卫
- 最小变更范围
- 历史代码渐进治理

EvieAi 新代码必须零新增违规。

历史代码可以分阶段治理，但高风险问题不得豁免。

---

## 17. 旧链处理原则

旧文档、旧代码和旧流程只能用于：

- 历史分析
- 兼容迁移
- 技术能力复用评估
- 回归验证

不得把以下旧概念作为目标设计：

- Candidate Preview
- selected_candidates
- 保存所选候选
- Candidate作为持久化业务实体
- TestPointPlan作为资产事实源
- 生成阶段结构化
- 生成阶段提前编译
- 生成阶段质量门
- Orchestrator内部编译
- Web层再次编译
- Runner运行时重新理解自然语言

旧链允许：

- 生产故障修复
- 安全修复
- 数据一致性修复
- 必要兼容修复
- 增加迁移观测和适配层

旧链禁止：

- 增加新产品能力
- 增加新Candidate交互
- 增加新的直接编译入口
- 被EvieAi新领域直接依赖
- 复制到EvieAi新模块

---

## 18. 实施阶段边界

本文描述 EvieAi 完整目标架构，不自动扩大当前阶段范围。

每次开发范围以：

1. 用户明确确认
2. `AGENTS.md`
3. 当前阶段实施文档

为准。

架构图和 Excel 用于长期方向校验，不自动扩大当前任务。

例如 EvieAi Phase 0 只允许：

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

Phase 0 不允许：

- AI生成
- Candidate迁移
- 完整Intake
- 语义去重
- Asset-to-Case
- ConversionAttempt
- Manifest
- Resource Binding
- Bound Plan
- Compiler
- Runner
- TestCase创建
- 前端页面
- 旧数据迁移
- 旧链删除

---

## 19. 架构图

Mermaid 源文件：

```text
docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd
```

建议架构图至少包含：

- 两类输入路径
- 七个架构域
- 统一资产入库
- TestAsset / TestAssetVersion
- Asset-to-Case
- Resource Capability Gateway
- ResourceBindingSnapshot
- TestCase → TestCaseVersion → script_code
- Runner
- Execution / Evidence / Report
- 平台控制面
- 技术基础设施域
- 版本与追溯关系

---

## 20. 结论

EvieAi 的核心业务主链是：

```text
多元输入
→ 自然语言资产
→ 版本化资产中心
→ Asset-to-Case
→ 版本化资源绑定
→ TestCaseVersion.script_code
→ Runner执行
→ 步骤结果、证据和报告
→ 归因、建议和受控治理
```

架构的核心边界是：

```text
生成侧只生成自然语言
资产域只保存“测什么”
Asset-to-Case唯一负责自然语言转机器语言
资源通过能力网关绑定
TestCaseVersion保存可执行事实
Runner只执行，不重新理解
反馈只产生建议，不直接覆盖版本化事实源
```

任何实现不得重新引入 Candidate 主链、生成阶段结构化、提前编译或 Runner 重新解释自然语言。
