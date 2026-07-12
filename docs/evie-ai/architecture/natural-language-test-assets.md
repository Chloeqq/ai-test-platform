# EvieAi 自然语言测试资产架构

日期：2026-07-12
状态：Authoritative
适用范围：EvieAi 的自然语言测试资产、AI 生成、统一资产入库、Asset-to-Case、TestCase、Compiler、Runner、页面对象、需求文档、覆盖追踪和旧链迁移

本文是 EvieAi 自然语言测试资产主线的权威架构文档。

后续涉及以下内容的任务，必须优先阅读并遵守本文：

- AI 生成
- 需求文档
- OpenAPI、缺陷、日志和批量导入
- 自然语言测试资产
- 测试点生成
- 测试资产入库
- 测试用例生成
- Asset-to-Case
- Compiler
- Runner
- 页面对象
- 测试数据
- 环境和凭证
- 执行资源
- 覆盖追踪
- 旧链迁移

完整目标能力参考：

- `AGENTS.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/implementation/当前阶段文档`
- `docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
- `docs/evie-ai/reference/ATP_V2_架构分层功能清单_完整实施版.xlsx`

发生冲突时，优先级如下：

1. 用户当前任务中的明确确认
2. `AGENTS.md`
3. 当前阶段实施文档
4. 本文
5. 其他 EvieAi 架构专题
6. EvieAi 架构图
7. Excel 完整设计参考
8. 旧文档
9. 旧代码现状

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

本文描述完整目标架构，不自动扩大当前 Phase 的实施范围。

---

## 1. 核心背景

这里的“自然语言”不是普通描述字段，也不是生成机器步骤之前的临时文本。

自然语言测试资产是平台的一等业务资产。

它必须具备：

- 稳定业务 ID
- 持久化存储
- 独立版本
- 来源追踪
- 用户编辑
- 内容审核
- 转换状态
- 覆盖关系
- 审计记录
- 生命周期管理

EvieAi 的核心业务分层是：

```text
TestAsset
负责表达“测什么”

TestCase
负责表达“如何执行”
```

自然语言测试资产的价值不依赖其是否能够立即自动化。

一条资产可以：

- 内容完整但暂时没有页面对象
- 审核通过但缺少测试数据
- 存在歧义但仍值得保存
- 适合人工执行但不适合自动执行
- 转换失败但仍保留业务价值
- 因需求变化而需要新版本

这些情况都不能成为拒绝入库或删除资产的理由。

---

## 2. 核心架构原则

EvieAi 自然语言测试资产主线必须遵守以下原则：

1. `TestAsset` 是一等持久化业务实体。
2. `TestAssetVersion` 是自然语言内容唯一事实源。
3. AI 生成只负责生产自然语言测试点。
4. AI 不是所有资产的必经入口。
5. 所有来源统一进入同一个资产入库服务。
6. Candidate、Preview、selected candidates 不属于 EvieAi 产品主链。
7. 资产入库不判断执行资源是否齐备。
8. 低质量、低置信度和暂不可执行资产也允许入库。
9. 自然语言到机器语言只能发生在 Asset-to-Case。
10. 每个 ConversionAttempt 必须锁定明确的 TestAssetVersion。
11. 资源解析只能通过 Resource Capability Gateway。
12. TestCaseVersion 保存可执行代码和版本化资源绑定事实。
13. `TestCaseVersion.script_code` 是执行代码唯一事实源。
14. Runner 只执行，不重新理解自然语言。
15. 历史版本不可原地覆盖。
16. 审核状态、转换状态、用例状态和执行状态相互独立。
17. 转换失败不得修改自然语言资产内容。
18. 失败分析不得未经审核自动覆盖任何版本化事实源。
19. 所有多表写入必须满足事务一致性。
20. 新实现不得复制旧 Candidate、提前结构化和直接编译链。

---

## 3. 输入与资产生产路径

EvieAi 存在两类资产生产路径。

### 3.1 AI 生成路径

适用于：

- 需求文档
- OpenAPI
- 缺陷
- 日志
- 业务规则
- 验收标准
- 其他结构化或半结构化输入

链路：

```text
输入源
→ Input Adapter
→ GenerationContext
→ AI 生成自然语言测试点
→ 统一资产入库
```

AI 输出仍然只是自然语言资产内容，不是 TestCase。

### 3.2 直接资产路径

适用于：

- 手工录入
- API 直接提交
- CI 直接提交
- 批量导入
- 外部系统已生成的自然语言测试点
- 迁移后的人工测试资产

链路：

```text
自然语言资产输入
→ 统一资产入库
```

这类输入不需要经过 AI。

### 3.3 统一入口原则

AI 生成、手工录入、API、CI 和批量导入，不得分别实现不同保存逻辑。

唯一允许的方式：

```text
各类资产生产者
→ TestAssetIntakeService
→ TestAsset / TestAssetVersion / TestAssetSource
```

不同入口只负责适配输入，不负责自行写库。

---

## 4. GenerationContext

所有 AI 模型调用必须在调用前建立生成上下文。

GenerationContext 用于明确：

- 谁发起生成
- 属于哪个项目
- 来自哪个输入源
- 关联哪个需求或文档版本
- 使用哪个模型和 Prompt
- 属于哪个批次
- 如何追踪和审计

建议包含：

```text
generation_context_id
project_code
source_type
source_business_id
source_version_id
entry_type
actor_id
trace_id
request_id
batch_id
model
provider
prompt_version
parameters
schema_version
data_classification
created_at
```

AI 可以消费经过后端验证的上下文。

AI 不得：

- 生成权威数据库 ID
- 修改 project scope
- 自行构造内部 requirement_id
- 自行构造 test_asset_id
- 自行决定资源版本
- 通过输出覆盖后端上下文

---

## 5. AI 生成侧边界

AI 生成侧只负责生成自然语言测试点。

允许输出：

- `title`
- `precondition`
- `natural_steps`
- `expected_result`
- `priority`
- `tags`

不得输出或负责：

- `action`
- `target`
- `value`
- `structured_steps`
- `steps_hint`
- Locator
- Selector
- Compiler IR
- DSL
- `script_code`
- Runner 专用步骤
- TestCase
- TestCaseVersion
- ResourceBinding
- BoundExecutionPlan

AI 生成侧不得调用：

- Behavior Registry
- ContractValidator
- ExecutionCompiler
- CaseQualityGate
- Runner
- 页面对象解析服务
- 测试数据解析服务

AI 可以给出场景建议、风险建议或自然语言标签，但这些都不能替代后端的权威状态、ID 和资源绑定。

---

## 6. TestAsset 聚合

### 6.1 TestAsset

`TestAsset` 表达稳定资产身份和聚合状态。

它不保存自然语言正文。

建议保存：

- `test_asset_id`
- `project_code`
- `current_version`
- `review_status`
- `conversion_status`
- 审计字段
- 软删除字段
- 乐观锁版本

### 6.2 TestAssetVersion

`TestAssetVersion` 保存自然语言业务内容。

允许字段：

- `title`
- `precondition`
- `natural_steps`
- `expected_result`
- `priority`
- `tags`
- `content_checksum`
- `version_no`
- 创建信息

不得包含：

- `action`
- `target`
- `value`
- Locator
- Selector
- `structured_steps`
- `steps_hint`
- Compiler IR
- DSL
- `script_code`
- Runner 专用步骤

### 6.3 版本不可变

TestAssetVersion 创建后不得原地覆盖业务内容。

禁止：

```text
UPDATE TestAssetVersion SET title = ...
```

正常编辑必须：

```text
读取当前版本
→ 创建新的 TestAssetVersion
→ 更新 TestAsset.current_version
```

历史版本必须保留。

版本表原则上只保存：

- `created_at`
- `created_by`

不应通过普通业务接口维护：

- `updated_at`
- `updated_by`

---

## 7. TestAssetSource 与多来源模型

一条自然语言测试资产可以拥有多个来源。

关系：

```text
TestAsset
1 → N TestAssetSource
```

完整目标来源包括：

- Requirement
- RequirementVersion
- RequirementItem
- AcceptanceCriterion
- BusinessRule
- RequirementDocument
- DocumentVersion
- DocumentSection
- SourceDocumentPage
- OpenAPI Operation
- Defect
- Log
- Manual Input
- Batch Import
- GenerationContext
- GenerationBatch

每条来源建议至少包含：

```text
test_asset_source_id
test_asset_id
source_type
source_business_id
source_version_id
source_identity_hash
created_at
created_by
```

来源关系不得因资产编辑而被覆盖。

资产产生新版本时，原来源仍然保留。

Phase 0 可以只支持 Requirement 来源，但完整目标模型必须允许扩展为多来源。

Phase 0 不应提前创建大量无外键的 nullable 占位字段。

---

## 8. 统一资产入库

所有资产必须通过统一资产入库服务。

建议逻辑职责：

```text
TestAssetIntakeService
```

负责：

- 验证项目作用域
- 验证来源作用域
- 后端分配权威 ID
- 建立来源关系
- 幂等处理
- 精确重复检测
- 疑似语义重复标记
- 创建 TestAsset
- 创建 TestAssetVersion
- 创建 TestAssetSource
- 更新 current_version
- 记录审计和追踪
- 触发异步评估事件

不得负责：

- 判断页面对象是否存在
- 判断测试数据是否完整
- 判断环境是否可用
- 判断可自动化性
- 生成机器步骤
- 编译
- 选择 Runner
- 创建 TestCase
- 运行转换质量门

### 8.1 无条件入库原则

以下情况不能阻止资产入库：

- 质量低
- 置信度低
- 描述不完整
- 存在歧义
- 暂不可执行
- 缺少页面对象
- 缺少测试数据
- 缺少环境
- 缺少凭证
- 疑似语义重复

智能评估只能在入库后异步进行。

评估可以产生：

- 质量评分
- 风险标签
- 置信度
- 场景建议
- 自动化建议
- Warning
- 疑似重复关系

评估不得删除或拒绝资产。

---

## 9. 幂等、重复与历史恢复

幂等、精确重复、语义重复和历史恢复是不同概念。

### 9.1 幂等

目的：

```text
相同请求被重复提交时，不重复创建业务结果
```

行为：

```text
相同 idempotency scope + idempotency key
→ 返回已有结果
```

### 9.2 精确重复

目的：

```text
识别规范化内容完全一致的资产输入
```

行为由 Intake Policy 决定：

- 返回已有资产
- 给已有资产增加来源
- 创建新资产但标记精确重复
- 明确返回冲突

具体策略必须显式配置，不能散落在入口代码中。

### 9.3 疑似语义重复

目的：

```text
识别语义近似但文本不完全相同的资产
```

行为：

- 标记疑似关系
- 提供审核建议
- 不阻止入库

### 9.4 历史内容恢复

合法场景：

```text
版本 1 = 内容 A
版本 2 = 内容 B
版本 3 = 恢复内容 A
```

因此：

- content checksum 可以建普通索引
- 不得通过唯一约束阻止恢复历史内容

---

## 10. Candidate 退出业务主链

EvieAi 不存在以下产品主链概念：

- Candidate Preview
- 候选项复选框
- 全选候选
- 保存所选候选
- 只有选中后才分配资产 ID
- Candidate 作为持久化业务实体
- Candidate 作为资产中心的前置状态

AI 响应可以在内部短暂使用 DTO 承载。

该 DTO 必须：

- 不持久化为 Candidate
- 不暴露为用户选择对象
- 不拥有独立业务生命周期
- 立即进入统一资产入库

旧 Candidate 链只能用于历史分析和迁移。

---

## 11. TestAsset 与 TestCase 的生命周期分离

### 11.1 TestAsset

TestAsset：

- 保存自然语言内容
- 回答“测什么”
- 支持编辑
- 支持审核
- 支持版本
- 支持来源追踪
- 支持覆盖关系
- 可以长期存在但尚未转换
- 可以审核通过但仍无法自动化
- 转换失败不影响资产本身

### 11.2 TestCase

TestCase：

- 只在 Asset-to-Case 成功后创建
- 保存稳定用例身份
- 保存当前 TestCaseVersion
- 表达“如何执行”
- 可以因资产、资源或编译规则变化而 stale
- 可以存在多个版本

### 11.3 TestCaseVersion

TestCaseVersion 保存：

- `script_code`
- `runner_type`
- 编译器版本
- Bound Plan 哈希
- TestAssetVersion 追踪信息
- ConversionAttempt 追踪信息
- ResourceBindingSnapshot
- Schema 版本
- 创建信息

`script_code` 不属于 TestCase 聚合根。

唯一执行代码事实源：

```text
TestCaseVersion.script_code
```

### 11.4 关系

允许：

```text
TestAsset 1
→ TestAssetVersion N
→ ConversionAttempt N
→ TestCase N
→ TestCaseVersion N
```

同一资产版本可以因为以下差异生成多条 TestCase：

- 数据矩阵
- 环境
- 浏览器
- 设备
- 账号
- 权限
- Mock
- 场景组合
- 安全或性能目标

---

## 12. Asset-to-Case 唯一转换入口

自然语言转机器语言只能发生在 Asset-to-Case 转换域。

唯一合法链路：

```text
TestAssetVersion
→ ConversionAttempt
→ 场景识别
→ Execution Requirement Manifest
→ Resource Capability Gateway
→ Resource Resolution Decision
→ Resource Bindings
→ ResourceBindingSnapshot
→ Bound Execution Plan
→ 测试用例矩阵展开
→ 统一转换质量门
→ Compiler Router
→ TestCase
→ TestCaseVersion
→ script_code
```

禁止其他模块直接完成自然语言到机器语言转换。

禁止：

- 生成侧提前结构化
- 资产入库时编译
- Orchestrator 内部直接编译
- Web 层二次编译
- Runner 运行时重新编译
- 多个并行 Compiler 入口

---

## 13. ConversionAttempt 与版本锁定

每次转换必须创建或复用明确的 ConversionAttempt。

每个 ConversionAttempt 必须锁定：

```text
test_asset_id
test_asset_version_id
```

转换开始后，即使用户编辑资产并产生新版本：

- 当前 Attempt 继续基于原 TestAssetVersion
- 不得自动切换到最新版本
- 不得在同一 Attempt 中混用多个版本
- 新版本需要新的 ConversionAttempt
- 已生成 TestCaseVersion 必须能追溯到原 TestAssetVersion

建议追踪字段：

```text
conversion_attempt_id
test_asset_id
test_asset_version_id
manifest_id
bound_plan_id
resource_binding_snapshot_id
compiler_run_id
test_case_id
test_case_version_id
```

### 13.1 转换错误

转换错误至少记录：

- `conversion_attempt_id`
- `test_asset_version_id`
- `stage`
- `error_code`
- `message`
- `retryable`
- `resource_type`
- `resource_id`
- `trace_id`
- `created_at`

`TestAsset.conversion_status` 只是当前聚合状态摘要。

完整转换事实必须保存在 ConversionAttempt。

---

## 14. Execution Requirement Manifest

Manifest 表达：

```text
执行这条自然语言资产，需要哪些能力和资源
```

可能包含：

- 场景类型
- 页面对象需求
- 测试数据需求
- 环境需求
- 凭证需求
- Mock需求
- 异常注入需求
- 安全能力需求
- 性能能力需求
- 原子动作能力需求
- 数据矩阵需求
- 执行目标
- 约束和优先级

Manifest 不包含最终 script_code。

Manifest 必须版本化或至少保存稳定快照。

---

## 15. Resource Capability Gateway

Asset-to-Case 不得直接查询具体资源表并自行解释资源。

唯一访问方式：

```text
Asset-to-Case
→ Resource Capability Gateway
→ 各资源提供方
```

资源提供方包括：

- Page Object Center
- Test Data Factory
- Environment Center
- Credential Center
- Mock Capability
- Fault Injection Capability
- Security Capability
- Performance Capability
- Atomic Capability Registry

网关返回至少包括：

- `resource_id`
- `resource_version_id`
- `capability_type`
- `binding_status`
- `resolution_decision`
- `health_status`
- `unavailable_reason`
- `policy_version`

不得：

- 直接读取明文凭证
- 静默选择默认环境
- 使用无版本资源生成长期执行用例
- 绕过资源治理策略
- 在 Compiler 内自行查询资源

---

## 16. ResourceBindingSnapshot

生成 TestCaseVersion 时必须保存 ResourceBindingSnapshot。

快照用于回答：

- 当时绑定了哪个 PageObjectVersion
- 当时使用了哪个环境
- 当时使用了哪个数据策略或数据版本
- 当时引用了哪个凭证
- 当时使用了哪个 Mock 或能力版本
- 当时哪些资源缺失或被替代
- 当时采用了哪个解析策略

资源后续变化时，历史 TestCaseVersion 仍然必须可解释和可审计。

ResourceBindingSnapshot 是 TestCaseVersion 的组成事实，不是临时缓存。

---

## 17. Bound Execution Plan

Bound Execution Plan 是经过资源解析后的可编译计划。

至少包含：

- 锁定的 TestAssetVersion
- Manifest 版本
- 资源绑定
- 资源版本
- 场景参数
- 测试数据矩阵
- 环境约束
- 凭证引用
- Mock和异常能力
- 编译目标
- Runner类型
- 质量门输入
- 规则版本
- 稳定哈希

Bound Plan 是 Compiler 的输入。

Compiler 不得直接读取自然语言 TestAsset。

---

## 18. 统一转换质量门

转换质量门只负责判断：

```text
是否能够生成有效、完整、可追踪的 TestCaseVersion
```

检查范围包括：

- Manifest 完整性
- 资源绑定完整性
- Bound Plan 一致性
- 编译目标合法性
- 权限和安全约束
- 数据和环境可用性
- 矩阵规模
- 必要资源健康状态
- 不可恢复阻塞问题

资产生成和资产入库阶段不得提前执行转换质量门。

执行阶段仍可以存在独立 Execution Precheck，例如：

- 环境当前是否可用
- 凭证是否过期
- 资源是否被占用
- 测试计划是否取消
- Runner是否可用

Execution Precheck 不属于自然语言转机器语言质量门。

---

## 19. 转换失败语义

转换失败时必须：

- 保留 TestAsset
- 保留 TestAssetVersion
- 保留用户编辑
- 保留来源关系
- 创建或更新 ConversionAttempt 错误
- 保存结构化诊断
- 不创建无效 TestCase
- 不创建无效 TestCaseVersion
- 不写入空或部分 `script_code`
- 不回写自然语言内容
- 不自动修改页面对象或资源版本

转换失败不能通过删除资产或回退资产版本处理。

---

## 20. 状态模型

### 20.1 审核状态

```text
review_status:
pending
approved
rejected
```

### 20.2 转换状态

```text
conversion_status:
not_started
processing
blocked
succeeded
stale
```

### 20.3 状态独立性

合法状态：

```text
review_status = approved
conversion_status = blocked
```

表示业务内容已审核通过，但执行资源尚不完整。

### 20.4 新版本状态转换

创建新的 TestAssetVersion 时：

```text
review_status → pending
```

转换状态规则：

```text
原 conversion_status = succeeded
→ stale

原 conversion_status = stale
→ stale

原 conversion_status = not_started
→ not_started

原 conversion_status = blocked
→ not_started

原 conversion_status = processing
→ 禁止直接编辑
```

状态转换必须由统一 Policy 或领域方法执行。

不得由调用方自由赋字符串。

---

## 21. 关键 ID 和来源链

必须复用或扩展当前系统已有 ID 模块，不建立平行 ID 体系。

目标链路包括：

```text
project_code
requirement_id
requirement_version_id
requirement_item_id
acceptance_criterion_id
business_rule_id
test_asset_source_id
document_id
document_version_id
section_id
source_document_page_id
page_object_id
page_object_version_id
generation_context_id
generation_batch_id
model_run_id
test_asset_id
test_asset_version_id
conversion_attempt_id
manifest_id
resource_resolution_decision_id
resource_binding_snapshot_id
bound_plan_id
test_case_id
test_case_version_id
execution_job_id
execution_id
execution_step_result_id
evidence_id
report_id
```

特别注意：

- `requirement_id` 不是 `request_id`
- `source_document_page_id` 不是 `page_object_id`
- `test_asset_version_id` 不能缩写成含义不明的 `asset_version_id`
- `test_asset_source_id` 不能缩写成含义不明的 `source_id`
- AI 不得生成权威数据库 ID
- 前端不得生成内部权威 ID
- 资产 ID 不依赖候选选择
- GenerationContext 必须在模型调用前建立
- Phase 0 不新增 `intent_id`
- Phase 0 项目作用域复用 `TestProject.project_code`
- Phase 0 不新增 Project 表
- Phase 0 不新增 `project_id / project_uuid`
- Phase 0 核心业务 ID 使用 `<prefix>_<uuid4hex32>`

---

## 22. 唯一事实源

不同阶段的唯一事实源必须明确。

| 业务事实 | 唯一事实源 |
|---|---|
| 需求正文 | RequirementVersion |
| 当前需求版本 | Requirement.current_version |
| 自然语言测试资产正文 | TestAssetVersion |
| 当前资产版本 | TestAsset.current_version |
| 来源关系 | TestAssetSource |
| 转换事实 | ConversionAttempt |
| 执行需求 | ExecutionRequirementManifest |
| 资源解析决策 | ResourceResolutionDecision |
| 资源绑定事实 | ResourceBindingSnapshot |
| 编译输入 | BoundExecutionPlan |
| 可执行代码 | TestCaseVersion.script_code |
| 执行事实 | Execution / ExecutionStepResult |
| 重试事实 | RetryAttempt |
| 清理事实 | CleanupResult |
| 证据事实 | Evidence |
| 报告 | 由执行事实派生 |

禁止：

- Requirement 与 RequirementVersion 双写正文
- TestAsset 与 TestAssetVersion 双写自然语言内容
- TestCase 与 TestCaseVersion 双写 script_code
- 多处维护同一状态转换规则
- 把缓存当作事实源
- 修改历史版本修正当前事实
- Runner重新解释 TestAsset

---

## 23. 事务与数据一致性

### 23.1 创建资产

至少应在同一个事务中完成：

```text
BEGIN
创建 TestAsset
创建 TestAssetVersion
创建 TestAssetSource
更新 TestAsset.current_version
COMMIT
```

任一步失败：

```text
ROLLBACK
```

不得产生：

- 无版本 TestAsset
- 无聚合的 TestAssetVersion
- current_version 指向错误版本
- 无资产的来源关系
- 部分成功响应

### 23.2 创建新版本

同一个事务中完成：

```text
锁定或校验 TestAsset
校验 processing 状态
生成 version_no
创建 TestAssetVersion
更新 current_version
重置 review_status
迁移 conversion_status
递增 row_version
提交
```

### 23.3 一致性要求

必须保证：

- current_version 属于对应 TestAsset
- version_no 在 TestAsset 内唯一
- 历史版本不可更新
- 软删除资产默认不可编辑
- 并发创建相同版本只能成功一个
- 唯一性由数据库约束和业务校验共同保护
- 数据库异常不能转成假成功
- 重试不能产生重复资产或重复版本

---

## 24. 覆盖与端到端追溯

EvieAi 必须支持需求到执行证据的完整追踪。

建议链路：

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

系统应能够回答：

- 哪条需求已经有测试资产
- 哪条验收标准尚未覆盖
- 某资产来自哪个需求版本
- 某资产版本生成了哪些 TestCaseVersion
- 某 TestCaseVersion 使用了哪些资源版本
- 某次执行验证了哪个需求版本
- 需求变化后哪些资产 stale
- 资产变化后哪些用例 stale
- 资源变化后哪些用例需要重新转换

---

## 25. Runner 边界

Runner 只读取：

- `TestCaseVersion.script_code`
- ResourceBindingSnapshot
- 运行时资源引用
- 明确环境参数
- 明确凭证引用
- 执行控制参数

Runner 不得：

- 读取自然语言 TestAsset 重新解释
- 重新调用 AI
- 运行时重新编译
- 运行时生成机器步骤
- 修改 TestAsset
- 修改 TestAssetVersion
- 修改 TestCaseVersion
- 自动补全缺失页面对象
- 静默使用默认环境
- 静默使用默认账号
- 静默使用默认项目

Runner 输出：

- Execution
- ExecutionStepResult
- RetryAttempt
- CleanupResult
- Evidence
- 稳定错误码

---

## 26. 失败分析与反馈边界

执行失败后允许产生：

- FailureAttribution
- FailureCategory
- RootCauseCandidate
- RepairRecommendation
- AssetReviewSuggestion
- ResourceGovernanceEvent
- ReviewTask
- QuarantineRecommendation

正确链路：

```text
执行失败
→ Failure Analysis
→ Attribution
→ Recommendation / Review Task
→ 人工或受控自动化决策
→ 创建新版本
```

禁止：

```text
执行失败
→ 自动覆盖 TestAssetVersion
```

禁止未经审核自动覆盖：

- PageObjectVersion
- TestData版本
- Environment配置
- TestCaseVersion
- `script_code`

所有修复必须通过新版本或受控治理流程完成。

---

## 27. 旧实现边界与冻结策略

以下旧实现只能用于：

- 历史分析
- 兼容迁移
- 技术能力复用评估
- 回归验证

不得作为 EvieAi 目标架构：

- CandidateNormalizer
- selected_candidates
- candidate preview
- 保存所选候选
- TestPointPlan
- point 与 candidate 往返转换
- resolve_explicit_step
- structured_steps_from_candidate
- Behavior Registry 提前介入
- Direct compile
- Orchestrator 内部编译
- Web 层再次校验
- Web 层再次编译
- 多个 point builder
- 多个 Compiler 入口
- 生成侧调用质量门
- 资产保存时提前结构化
- Runner 运行时重新理解自然语言

旧链允许：

- 生产故障修复
- 安全修复
- 数据一致性修复
- 必要兼容修复
- 增加迁移观测
- 增加适配层

旧链禁止：

- 增加新产品能力
- 增加新 Candidate 交互
- 新增直接编译入口
- 被 EvieAi 新领域直接依赖
- 复制进 EvieAi 新模块

技术组件可以复用，但旧业务调用位置不能直接继承。

---

## 28. 命名边界

新增权威文档、代码目录、测试目录、Migration 和提交信息必须使用 EvieAi 命名。

| 类型 | 命名 |
|---|---|
| 产品名 / 文档标题 | `EvieAi` |
| 文档目录 / Git scope | `evie-ai` |
| Python 包目录 | `evie_ai` |
| 权威文档路径 | `AGENTS.md`, `docs/evie-ai/**` |

数据库表不增加品牌前缀，继续使用业务通用命名。

领域类不增加 EvieAi 前缀。

推荐：

```text
Requirement
RequirementVersion
TestAsset
TestAssetVersion
TestAssetSource
ConversionAttempt
TestCase
TestCaseVersion
```

不推荐：

```text
EvieAiRequirement
EvieAiTestAsset
```

---

## 29. 阶段实施边界

本文描述完整目标架构，不代表当前 Phase 全部实施。

每个任务的实际范围以：

1. 用户明确确认
2. `AGENTS.md`
3. 当前 Phase 实施文档

为准。

架构图和 Excel 用于长期方向校验，不自动扩大任务范围。

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

## 30. 结论

EvieAi 自然语言测试资产主线是：

```text
多元输入
→ 自然语言资产生产
→ 统一资产入库
→ TestAsset / TestAssetVersion
→ 用户编辑、审核和版本管理
→ Asset-to-Case
→ Manifest
→ 资源能力网关
→ ResourceBindingSnapshot
→ Bound Execution Plan
→ 转换质量门
→ Compiler
→ TestCase → TestCaseVersion → script_code
→ Runner
→ Execution / Evidence / Report
→ 归因、建议和受控治理
```

核心边界是：

```text
生成侧只生成自然语言
资产域只保存“测什么”
Asset-to-Case唯一负责自然语言转机器语言
资源只能通过能力网关解析和绑定
TestCaseVersion保存可执行事实
Runner只执行，不重新理解
失败反馈只产生建议，不直接覆盖版本化事实源
```

任何实现不得重新引入：

- Candidate 产品主链
- 生成阶段结构化
- 资产入库时编译
- 多个 Compiler 入口
- Runner 重新解释自然语言
- 失败后自动覆盖历史版本
