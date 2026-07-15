# EvieAi 阶段追踪矩阵

创建日期：2026-07-12
最后更新：2026-07-15
状态：Authoritative
适用范围：EvieAi 完整目标能力、阶段实施边界、交付物追踪、验收证据和架构偏差检查

本文用于连接 EvieAi 完整目标能力与分阶段实施边界，防止因为架构图或 Excel 中存在某项能力，就自动把它加入当前任务。

本文同时用于回答：

- 某项能力属于哪个阶段
- 当前阶段是否允许实施
- 当前阶段需要交付什么
- 当前阶段如何验收
- 后续阶段依赖哪些前置条件
- 某项能力是否偏离总体架构
- 架构文档、Excel、代码和测试之间如何追踪

完整参考：

- `AGENTS.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/natural-language-test-assets.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/engineering/coding-standards.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-specification.md`
- `docs/evie-ai/implementation/phase-1-natural-language-asset-lifecycle-plan.md`
- `docs/evie-ai/decisions/ADR-0001-phase1-natural-language-asset-lifecycle.md`
- `docs/evie-ai/reference/2026-07-12_evie-ai-architecture-flow.mmd`
- `docs/evie-ai/reference/EvieAi_架构分层功能清单_完整实施版.xlsx`

> 如果 Excel 尚未完成文件名迁移，可以暂时引用旧文件名，但权威路径最终必须统一为 EvieAi 命名，不得长期并存两份内容相同的文件。

---

## 1. 使用规则

### 1.1 核心规则

```text
Excel 定义完整目标空间
架构图定义领域关系和主链路
架构专题定义领域边界
阶段追踪矩阵定义能力所属阶段
Phase 文档定义本次实际实施边界
```

阶段追踪矩阵不能替代当前 Phase 实施文档。

某项能力只有同时满足以下条件，才可以进入当前任务：

1. 当前 Phase 实施文档明确纳入
2. 用户当前任务明确要求
3. 不违反 `AGENTS.md`
4. 前置能力已满足
5. 有明确验收方式
6. 不会把后续阶段对象提前落库或提前接入主链

### 1.2 冲突优先级

发生冲突时，按以下优先级处理：

1. 用户当前任务中的明确确认
2. `AGENTS.md`
3. 当前阶段实施文档
4. EvieAi 架构专题文档
5. 本文
6. EvieAi 架构图
7. Excel 完整设计参考
8. 旧文档
9. 旧代码现状

旧代码只能证明当前系统如何运行，不能证明 EvieAi 应该如何设计。

### 1.3 禁止自动扩阶段

以下行为不允许：

- 因 Excel 存在实体，就在当前 Migration 中提前建表
- 因架构图存在服务，就在当前 Phase 提前创建空目录或占位实现
- 因后续需要某个字段，就在当前模型中提前添加大量 nullable 占位字段
- 因旧代码已有实现，就把旧调用链复制到 EvieAi
- 因“后续一定会用”，就绕过当前 Phase 边界
- 因测试方便，就在当前阶段引入后续状态或业务对象

---

## 2. 阶段定义

### Phase 0：领域模型基线

目标：

- 建立 Requirement 和自然语言 TestAsset 的最小持久化基础
- 建立版本、来源和 ID 基线
- 建立 Repository 事务一致性
- 建立架构守卫

主要交付：

- Requirement
- RequirementVersion
- TestAsset
- TestAssetVersion
- TestAssetSource
- ID 扩展
- ORM
- Schema
- Repository
- Alembic Migration
- 架构边界测试
- 权威文档

明确不包含：

- 完整 Intake
- AI 生成
- 文档解析改造
- Candidate 迁移
- 语义去重
- Asset-to-Case
- ConversionAttempt
- TestCase
- Runner
- 前端资产中心

### Phase 1：自然语言资产生命周期

目标：

- 建立手工/API 自然语言资产入口
- 建立统一资产入库服务
- 建立编辑、版本、审核、软删除、来源和查询能力
- 建立幂等和精确重复处理

主要交付：

- TestAssetIntakeService
- 手工/API 创建资产
- 资产列表、详情和版本历史
- 新版本创建
- 审核记录
- 幂等策略
- 精确重复策略
- 软删除和恢复
- 审计
- 基础前端资产中心，可按产品排期拆分

### Phase 2：多元输入与 AI 自然语言生成

目标：

- 接入需求文档、OpenAPI、缺陷、日志等输入
- 建立 GenerationContext、GenerationBatch 和 ModelRun
- AI 只生成自然语言资产
- AI 输出直接进入统一资产入库
- 完成 Candidate 生成主链切流

主要交付：

- Input Adapters
- SourceDocument / DocumentVersion / Section
- GenerationContext
- GenerationBatch
- ModelRun
- PromptVersion
- AI 输出 Schema 校验
- AI 生成任务
- 异步质量评估
- 疑似语义重复
- 旧 Candidate 生成入口切流准备与切换

### Phase 3：Asset-to-Case 与版本化 TestCase

目标：

- 建立唯一自然语言转机器语言入口
- 建立资源需求、资源解析、绑定快照和 Bound Plan
- 生成版本化 TestCase

主要交付：

- ConversionAttempt
- ScenarioAnalysis
- ExecutionRequirementManifest
- ResourceCapabilityGateway
- ResourceResolutionDecision
- ResourceBinding
- ResourceBindingSnapshot
- BoundExecutionPlan
- VariantMatrix
- ConversionQualityGate
- CompilerRouter
- TestCase
- TestCaseVersion
- script_code

### Phase 4：计划、执行、证据与反馈治理

目标：

- 建立测试计划、调度、执行、步骤结果、证据、报告和 Flaky 治理

主要交付：

- TestSuite
- TestPlan
- TestCampaign
- Reservation
- Scheduler
- ExecutionControl
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

### Phase 5+：企业治理、规模化与旧链退役

目标：

- 完成租户治理、AI治理、数据治理、覆盖分析和旧平台退役
- 提升高可用、容量、成本和灾备能力

主要交付：

- Tenant 隔离
- AI 评估中心
- 成本治理
- 数据保留与删除
- Legal Hold
- 覆盖与影响分析深化
- 迁移批次与对账
- 旧链退役
- 高可用和灾备
- 容量与弹性治理

阶段编号用于能力追踪，不等同于固定发布时间。

---

## 3. 状态标记说明

矩阵中使用以下标记：

| 标记 | 含义 |
|---|---|
| 实施 | 当前阶段必须交付并验收 |
| 基线 | 只建立最小模型、接口或约束，不提供完整业务能力 |
| 约束 | 作为架构规则或守卫存在，不实现完整业务功能 |
| 可选 | 可按产品排期实施，但必须单独确认 |
| 延后 | 不允许在该阶段实施 |
| 复用 | 复用既有技术能力，但必须重新放入正确领域边界 |
| 迁移 | 仅进行迁移、切流或退役工作 |

---

## 4. 核心阶段追踪矩阵

| 能力 | Excel / 架构位置 | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5+ |
|---|---|---|---|---|---|---|---|
| 项目作用域 | 07 平台控制面、20 通用字段规范 | 实施：复用 `TestProject.project_code` | 实施：查询和写入隔离 | 实施：生成和来源隔离 | 实施：转换和资源隔离 | 实施：计划与执行隔离 | 租户与多项目治理 |
| Tenant | 07 平台控制面 | 延后 | 延后 | 延后 | 可选基线 | 可选 | 实施 |
| Requirement | 10 ID、11 实体关系、14 数据明细、15 覆盖模型 | 实施：最小聚合根 | 实施：独立后续切片 | 实施：作为输入来源 | 实施：覆盖追踪输入 | 实施：执行追溯 | 影响分析深化 |
| RequirementVersion | 10 ID、15 覆盖模型 | 实施：正文版本 | 实施：独立后续切片 | 实施：文档/生成绑定 | 实施：资产追溯 | 实施：执行追溯 | 影响分析深化 |
| RequirementItem | 15 覆盖模型 | 延后 | 可选 | 实施或后续确认 | 实施：覆盖关系 | 实施：执行追溯 | 深化 |
| AcceptanceCriterion | 15 覆盖模型 | 延后 | 可选 | 实施或后续确认 | 实施：覆盖关系 | 实施：覆盖报告 | 深化 |
| BusinessRule | 15 覆盖模型 | 延后 | 可选 | 实施或后续确认 | 实施：场景输入 | 实施：覆盖报告 | 深化 |
| TestAsset | 03 自然语言资产、10 ID、14 数据明细 | 实施：聚合根 | 实施：完整生命周期 | 实施：AI统一写入 | 实施：转换输入 | 实施：执行追溯 | 治理深化 |
| TestAssetVersion | 03 自然语言资产、11 实体关系 | 实施：自然语言正文 | 实施：编辑和历史 | 实施：AI生成版本 | 实施：转换锁定 | 实施：执行追溯 | 影响分析 |
| TestAssetSource | 03 自然语言资产、13 字段传递链 | 实施：仅 Requirement 来源 | 实施：通用主表、Requirement 子表、Manual 来源 | 实施：文档、章节、批次等来源 | 实施：追溯 | 实施：报告追溯 | 治理深化 |
| TestAssetIntakeService | 03 自然语言资产 | 延后 | 实施 | 复用并扩展生产者 | 复用 | 复用 | 复用 |
| 幂等检查 | 03 自然语言资产、13 字段传递链 | 延后 | 实施 | 扩展任务和消息幂等 | 实施：转换幂等 | 实施：执行任务幂等 | 深化 |
| 精确重复检测 | 03 自然语言资产 | 延后 | 实施 | 扩展来源和批次范围 | 复用 | 复用 | 合并治理 |
| 疑似语义重复 | 03 自然语言资产、19 AI治理 | 延后 | 可选 | 实施 | 作为转换提示，不阻断 | 作为治理输入 | 深化 |
| 异步资产质量评估 | 03 自然语言资产、19 AI治理 | 延后 | 可选基础 | 实施 | 作为转换输入 | 作为反馈输入 | 评估中心 |
| AssetReviewRecord | 03 自然语言资产 | 延后 | 实施 | 复用 | 复用 | 复用 | 深化 |
| 软删除和恢复 | 03 自然语言资产、20 通用字段 | 基线：字段与查询规则 | 实施 | 复用 | 复用 | 复用 | 数据治理整合 |
| Candidate 退出产品主链 | 22 迁移计划、架构专题 | 约束：新模块禁止依赖 | 约束：新资产入口无 Candidate | 实施：AI生成切流 | 迁移：旧编译入口退出 | 迁移：旧执行依赖退出 | 删除旧链 |
| SourceDocument | 01/02 输入域 | 延后 | 延后 | 实施 | 复用 | 追溯 | 治理 |
| DocumentVersion | 01/02 输入域 | 延后 | 延后 | 实施 | 复用 | 追溯 | 治理 |
| DocumentSection | 01/02 输入域 | 延后 | 延后 | 实施 | 复用 | 追溯 | 治理 |
| SourceDocumentPage | 01/02 输入域、10 ID | 延后 | 延后 | 实施 | 复用 | 追溯 | 治理 |
| OpenAPI 输入 | 01/02 输入域 | 延后 | 延后 | 实施 | 复用 | 追溯 | 深化 |
| 缺陷和日志输入 | 01/02 输入域 | 延后 | 延后 | 实施或分批 | 复用 | 反馈闭环 | 深化 |
| GenerationContext | 02 输入与生成、13 字段链 | 延后 | 延后 | 实施 | 追溯 | 追溯 | 治理 |
| GenerationBatch | 02 输入与生成 | 延后 | 延后 | 实施 | 追溯 | 追溯 | 治理 |
| ModelRun | 02 输入与生成、19 AI治理 | 延后 | 延后 | 实施 | 追溯 | 评估 | 治理 |
| PromptVersion | 19 AI治理 | 延后 | 可选基线 | 实施 | 复用 | 评估 | 治理深化 |
| AI 自然语言生成 | 02 输入与生成 | 延后 | 延后 | 实施 | 不参与机器转换 | 不参与运行时 | 治理深化 |
| ConversionAttempt | 04 Asset-to-Case、12 状态 | 延后 | 延后 | 延后 | 实施 | 追溯 | 治理 |
| ScenarioAnalysis | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 追溯 | 深化 |
| ExecutionRequirementManifest | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 追溯 | 深化 |
| ResourceCapabilityGateway | 04/05 转换与资源域 | 延后 | 延后 | 延后 | 实施 | 复用 | 深化 |
| ResourceResolutionDecision | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 追溯 | 深化 |
| ResourceBinding | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 运行时使用 | 治理 |
| ResourceBindingSnapshot | 04/06 字段传递与执行 | 延后 | 延后 | 延后 | 实施 | 执行事实输入 | 治理 |
| BoundExecutionPlan | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 追溯 | 深化 |
| VariantMatrix | 04 Asset-to-Case | 延后 | 延后 | 延后 | 实施 | 追溯 | 深化 |
| ConversionQualityGate | 04 Asset-to-Case | 约束：不得提前调用 | 约束：不得提前调用 | 约束：不得提前调用 | 实施 | 与 Execution Precheck 分离 | 深化 |
| CompilerRouter | 04 Asset-to-Case | 约束：不得调用 | 约束：不得调用 | 约束：不得调用 | 实施 | 仅消费版本化输入 | 多Compiler治理 |
| PageObject / Version | 05 资源域 | 延后 | 延后 | 可迁移准备 | 实施：通过Gateway绑定 | 运行时引用 | 治理深化 |
| 测试数据工厂 | 05 资源域 | 延后 | 延后 | 延后 | 实施或按场景分批 | 预占与执行 | 深化 |
| 环境中心 | 05 资源域、17 资源预占 | 延后 | 延后 | 延后 | 实施基础 | 实施预占与健康 | 深化 |
| 凭证中心 | 05 资源域、21 安全保留 | 约束：不得保存明文 | 约束：只保存引用 | 可选基础 | 实施 | 执行租约 | 轮换和治理 |
| Mock / Fault / Security / Performance | 05 资源域 | 延后 | 延后 | 延后 | 按场景分批实施 | 执行支持 | 深化 |
| AtomicCapability | 05 资源域 | 延后 | 延后 | 延后 | 实施或分批 | Runner消费 | 治理 |
| TestCase | 06 用例与执行 | 延后 | 延后 | 延后 | 实施 | 实施生命周期 | 治理 |
| TestCaseVersion | 06 用例与执行、13 字段链 | 延后 | 延后 | 延后 | 实施 | 执行唯一输入版本 | 治理 |
| `script_code` 唯一执行事实源 | 06 用例与执行 | 约束 | 约束 | 约束 | 实施 | 实施 | 持续约束 |
| TestSuite | 16 测试计划与套件 | 延后 | 延后 | 延后 | 可选 | 实施 | 深化 |
| TestPlan | 16 测试计划与套件 | 延后 | 延后 | 延后 | 可选 | 实施 | 深化 |
| TestCampaign | 16 测试计划与套件 | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| DataReservation | 17 资源环境预占 | 延后 | 延后 | 延后 | 可选 | 实施 | 深化 |
| EnvironmentReservation | 17 资源环境预占 | 延后 | 延后 | 延后 | 可选 | 实施 | 深化 |
| Scheduler | 06 执行、17 预占 | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| ExecutionControl | 06 执行 | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| RunnerRouter | 06 执行 | 约束：不得修改 | 约束：不得接收资产 | 约束：不得接收资产 | 可选接口准备 | 实施 | 多Runner治理 |
| Runner | 06 执行 | 约束：只执行script_code | 同左 | 同左 | 同左 | 实施/复用 | 深化 |
| Execution | 06 执行 | 延后 | 延后 | 延后 | 延后 | 实施 | 治理 |
| ExecutionStepResult | 18 执行步骤与Flaky | 延后 | 延后 | 延后 | 延后 | 实施 | 治理 |
| RetryAttempt | 18 执行步骤与Flaky | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| CleanupResult | 18 执行步骤与Flaky | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| Evidence | 06 执行与证据 | 延后 | 延后 | 延后 | 延后 | 实施 | 保留治理 |
| Report | 06 执行与证据 | 延后 | 延后 | 延后 | 延后 | 实施 | 治理 |
| Flaky | 18 执行步骤与Flaky | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| Quarantine | 18 执行步骤与Flaky | 延后 | 延后 | 延后 | 延后 | 实施 | 深化 |
| FailureAnalysis | 06/18 执行与反馈 | 延后 | 延后 | 延后 | 延后 | 实施 | AI辅助深化 |
| CoverageRelation | 15 需求覆盖模型 | 延后 | 可选基础 | 实施或分批 | 实施追踪 | 实施报告 | 深化 |
| Release / Build / Deployment / Commit | 14/16/20 通用追踪 | 延后 | 延后 | 可选 | 可选 | 实施关联 | 深化 |
| AI治理与评估 | 19 AI治理 | 约束：配置和安全边界 | 可选基础 | 实施生成治理 | 实施转换AI治理 | 实施反馈AI治理 | 评估中心 |
| 数据安全与保留 | 21 数据安全与保留 | 约束：边界原则 | 基础审计和软删除 | 输入与Prompt治理 | 资源与凭证治理 | 证据和报告治理 | 完整保留/删除 |
| 旧平台迁移 | 22 迁移计划 | 冻结和盘点 | 兼容入口准备 | AI生成主链切流 | 转换链切流 | 执行链切流 | 对账、删除和退役 |
| 技术基础设施 | 08 基础设施 | 复用现有DB/Alembic/CI | 补可观测性 | 补异步任务和模型治理 | 补MQ/Worker/资源服务 | 补调度和对象存储 | HA/DR/容量 |

---

## 5. Phase 0 详细追踪

### 5.1 允许实施的能力

| 能力 | 当前交付 | 主要代码位置 | 验收证据 |
|---|---|---|---|
| EvieAi 文档权威链 | README、架构、工程和Phase文档 | `AGENTS.md`、`docs/evie-ai/**` | 路径、引用和命名一致性检查 |
| ID 扩展 | req/reqv/ta/tav/tas | `app/core/id_gen.py` | 前缀、长度、字符集、批量无碰撞测试 |
| Requirement | 最小聚合根 | `app/models/evie_ai/requirement.py` | ORM字段和约束测试 |
| RequirementVersion | 不可变正文版本 | 同上 | 版本号唯一、正文只在版本表 |
| TestAsset | 自然语言资产聚合根 | `app/models/evie_ai/test_asset.py` | 不含正文和机器字段 |
| TestAssetVersion | 自然语言正文版本 | 同上 | 不含结构化步骤和script_code |
| TestAssetSource | 仅 Requirement 来源 | 同上 | 来源唯一约束和外键测试 |
| Schema | 自然语言字段契约 | `app/schemas/evie_ai/**` | extra forbid、机器字段拒绝 |
| Repository | 最小事务读写 | `app/repositories/evie_ai/**` | 创建、回滚、current_version一致性 |
| Migration | 五张基础表 | `migrations/versions/**` | Alembic head正确、结构测试 |
| 架构守卫 | 阻止旧链和机器字段进入 | `tests/unit/evie_ai/**` | AST、Schema和ORM守卫测试 |

### 5.2 Phase 0 明确排除

Phase 0 不允许包含：

- AI 生成
- GenerationContext
- 文档解析改造
- Candidate 数据迁移
- Candidate 前端切流
- TestAssetIntakeService
- 完整幂等服务
- 精确重复服务
- 语义去重
- 异步智能评估
- Asset-to-Case
- ConversionAttempt
- Manifest
- ResourceCapabilityGateway
- ResourceBindingSnapshot
- BoundExecutionPlan
- Compiler
- TestCase
- Runner 改造
- Scheduler
- Evidence
- Report
- 前端资产中心
- 旧数据迁移
- 旧链删除

### 5.3 Phase 0 架构约束

虽然以下能力不在 Phase 0 实施，但必须通过守卫防止错误提前发生：

- TestAsset 不得包含机器字段
- 生成侧不得调用 Compiler
- EvieAi Repository 不得依赖旧 TestPointAsset
- EvieAi 模块不得依赖 Candidate
- Runner 只允许执行版本化 `script_code`
- `script_code` 不得写入 TestAsset
- `current_version` 必须属于对应聚合
- 历史版本不可原地覆盖
- 不得新增默认 `project_code`
- 不得建立平行 ID 系统

---

## 6. 阶段入口条件与退出条件

### 6.1 Phase 0 入口条件

- 权威文档完成
- 人工决策已收口
- 旧链未提交改动已隔离
- Git branch、HEAD、工作区已确认
- Alembic heads/history已读取
- ID、字段、约束命名一致

### 6.2 Phase 0 退出条件

- 五个领域模型完成
- Migration可执行
- Repository事务测试通过
- current_version一致性测试通过
- 不可变版本测试通过
- ID测试通过
- 架构守卫通过
- 无Phase 1+对象混入
- 文档与代码一致
- 实际测试结果已记录

### 6.3 Phase 1 入口条件

- Phase 0模型稳定
- Repository事务边界明确
- API错误模型明确
- Intake幂等规则已确认
- 精确重复策略已确认
- 审核和状态转换已确认

当前状态（2026-07-15）：

- Phase 0 模型和 Repository 基线已合并；
- 确定性数据库 baseline 已合并；
- C-01 前向兼容阻塞已通过 PR #4 修复并复验；
- D-01～D-14 已写入核心 Approved 合同；
- A-01～A-10 已完成用户明确签字并写入 Approved 规格合同；
- 必须先完成权威文档提交、审查和合并，再从最新 `dev` 创建 Slice 1 功能分支。

### 6.3.1 Phase 1 Asset Lifecycle Core 退出条件

- Manual 和已存在 Requirement 来源均进入统一 Intake；
- 幂等、精确重复、来源、版本、审核、删除恢复、审计和查询合同全部实现；
- SQLite 与 PostgreSQL Migration、并发和失败回滚测试通过；
- API 项目作用域、日志脱敏和结构化错误门禁通过；
- Candidate、structurer、Compiler 和 Runner 未进入新资产链；
- 相比冻结旧链基线没有新增失败；
- 合并后复验和实施证据已更新到任务档案。

完成以上条件可以宣告 `Phase 1 Asset Lifecycle Core` 完成。
Requirement 生命周期独立切片交付前，不得宣告完整 Phase 1 完成。

### 6.4 Phase 2 入口条件

- 统一Intake稳定
- 直接资产入口已验证
- GenerationContext字段已确认
- 模型、Prompt和安全治理具备基础
- AI输出可以直接进入Intake
- Candidate切流方案已批准

### 6.5 Phase 3 入口条件

- TestAssetVersion稳定
- ConversionAttempt状态机已确认
- Manifest契约已确认
- 资源网关接口已确认
- BoundPlan和Compiler输入契约已确认
- TestCaseVersion事实源规则已确认

### 6.6 Phase 4 入口条件

- `TestCaseVersion.script_code` 契约稳定
- Runner输入契约固定
- 环境和数据预占方案明确
- Execution和StepResult模型确认
- Evidence保留与安全规则确认

---

## 7. 追踪记录要求

后续任务引用 Excel、架构图或能力地图时，必须同时说明：

1. 使用了哪个工作表或架构章节
2. 对应哪个能力
3. 属于哪个阶段
4. 当前 Phase 文档是否明确纳入
5. 依赖哪些前置能力
6. 计划修改哪些代码或文档
7. 如何验收
8. 哪些相关能力明确不在本次实施

推荐任务说明格式：

```text
能力：
Excel工作表：
架构章节：
所属Phase：
当前Phase是否纳入：
前置依赖：
计划交付：
验收证据：
明确排除：
```

---

## 8. 代码与测试追踪要求

每项已实施能力至少应能追踪到：

```text
目标能力
→ 架构章节
→ Phase
→ 实施文档
→ 代码模块
→ Migration
→ 测试
→ 提交
```

示例：

```text
TestAssetVersion
→ natural-language-test-assets.md / TestAsset聚合
→ Phase 0
→ phase-0-domain-model.md
→ app/models/evie_ai/test_asset.py
→ <revision>_evie_ai_phase0_assets.py
→ test_evie_ai_models.py
→ feat(evie-ai): add requirement and natural language asset models
```

没有测试或其他验证证据的能力，不得标记为“完成”。

---

## 9. 追踪状态

建议在后续执行版矩阵中使用以下状态：

```text
not_started
planned
in_progress
blocked
implemented
verified
deprecated
removed
```

定义：

| 状态 | 含义 |
|---|---|
| not_started | 尚未规划实施 |
| planned | 已进入已确认Phase计划 |
| in_progress | 正在实施 |
| blocked | 存在明确阻塞 |
| implemented | 代码或配置已实现，但未完成全部验证 |
| verified | 实现和验收证据均完成 |
| deprecated | 已停止扩展，等待迁移 |
| removed | 已完成删除且无有效调用 |

“完成”应使用 `verified`，不能仅凭文件存在或代码已提交判断。

---

## 10. 变更治理

本文必须在以下情况更新：

- Phase 边界调整
- 某能力提前或延后
- 新增关键实体或事实源
- 状态模型发生变化
- 旧链切流计划变化
- Excel工作表重命名
- 权威文档路径变化
- 某阶段完成并产生实际代码路径

更新时必须同时检查：

- `target-capability-map.md`
- 当前 Phase 文档
- 架构图
- Excel引用
- README导航
- 代码和测试路径

不得只修改本矩阵而不更新对应 Phase 文档。

---

## 11. 架构偏差检查

每个 Phase 结束前，应检查：

### 11.1 范围偏差

- 是否实现了当前 Phase 未纳入的能力
- 是否提前创建后续实体
- 是否增加无业务语义的占位字段
- 是否把架构目标误当作当前任务

### 11.2 边界偏差

- 生成侧是否出现机器步骤
- 资产域是否出现 Compiler 或 Runner 依赖
- Asset-to-Case是否仍是唯一转换入口
- Runner是否重新解析自然语言
- 资源是否绕过Gateway

### 11.3 事实源偏差

- 正文是否双写
- script_code是否双写
- 版本是否被原地修改
- current_version是否可能错误关联
- 派生结果是否覆盖事实源

### 11.4 工程偏差

- 是否新增硬编码
- 是否新增平行配置来源
- 是否缺少事务
- 是否绕过Repository
- 是否缺少错误模型
- 是否缺少验收测试
- 是否复制历史违规模式

---

## 12. 结论

EvieAi 阶段追踪矩阵的核心作用是：

```text
完整目标能力
→ 明确所属Phase
→ 明确当前是否实施
→ 明确交付物
→ 明确验收证据
→ 防止越界
```

完整能力地图保证长期方向完整。

阶段追踪矩阵保证能力不会遗漏或提前实施。

Phase 文档保证当前任务范围可执行、可审查、可验收。

任何能力如果未被当前 Phase 文档明确纳入，只能作为背景、风险或后续建议，不得直接实施。
