# AI自动化测试平台技术架构蓝图 v1.0

**版本**：v1.0  
**适用范围**：AI 自动化测试平台 / AI 用例生成平台 / 测试执行与治理平台  
**目标**：提供一份可直接落地的企业级技术架构蓝图，统一平台分层、模块边界、数据流、AI 调用链路、执行链路和治理机制，降低后续反复重构的概率。

---

# 1. 架构目标

本平台的核心目标不是“做一个能生成测试用例的 AI 工具”，而是建设一个具备以下能力的企业级平台：

- 支持 AI 生成测试用例、步骤、预期结果、标签和基础脚本建议
- 支持人工审核、修订、发布与版本管理
- 支持测试计划、测试执行、执行结果和缺陷闭环
- 支持规范治理、字典治理、审计追踪和质量评估
- 支持 AI 提示词、模型、规则、fallback 策略的统一治理
- 支持后续扩展到多项目、多团队、多模型、多环境

---

# 2. 总体架构原则

## 2.1 平台优先，不做 AI Demo
AI 只是平台能力的一部分，不能把平台架构建立在某一个模型或单次 prompt 上。

## 2.2 强治理优先于自由生成
所有 AI 生成结果必须进入平台治理体系，不能绕过字典、版本、审核、状态机和审计。

## 2.3 分层清晰，职责稳定
系统必须明确区分：接入层、应用编排层、领域层、基础设施层、AI 适配层、治理层。

## 2.4 数据先结构化，再智能化
先解决对象模型、状态流、版本流、主键规则、日志规则，再做生成、推荐、评分、优化。

## 2.5 AI 可替换，模型无锁定
平台必须抽象 AI Provider 层，不让业务直接依赖具体模型。

---

# 3. 整体系统分层

推荐采用以下六层架构：

```text
[接入层]
  Web Console / Admin Console / Open API / Webhook

[应用编排层]
  Case Application / Plan Application / Run Application / AI Task Orchestrator

[领域层]
  Case Domain / Suite Domain / Plan Domain / Run Domain / Result Domain / Governance Domain

[AI 能力层]
  Prompt Manager / Model Router / AI Provider Adapter / Output Validator / Fallback Engine

[基础设施层]
  DB / Cache / MQ / Object Storage / Search / Log / Trace / Config Center

[治理与运维层]
  Auth / Audit / Metrics / Alert / Feature Flag / Rule Engine / Dictionary Center
```

---

# 4. 核心业务模块划分

推荐拆分为 10 个核心模块。

## 4.1 用例中心（Case Center）
职责：

- 测试用例创建、编辑、审核、发布、废弃
- Case ID 生成
- 用例标题、步骤、预期、标签维护
- 用例版本管理
- 用例来源管理（AI / 人工 / 导入 / fallback）

核心对象：

- Case
- CaseVersion
- CaseReview
- CaseTag
- LegacyCaseMapping

---

## 4.2 套件中心（Suite Center）
职责：

- 测试套件管理
- 用例归档与组织
- Suite 与 Case 的多对多管理
- 冒烟套件 / 回归套件 / 模块套件维护

核心对象：

- Suite
- SuiteCaseRel
- SuiteVersion

---

## 4.3 计划中心（Plan Center）
职责：

- 测试计划创建、排期、发布
- 套件绑定
- 环境绑定
- 执行范围控制

核心对象：

- Plan
- PlanSuiteRel
- PlanConfig

---

## 4.4 执行中心（Execution Center）
职责：

- Run 创建
- 任务调度
- 执行状态流转
- 并发控制
- 重试 / 超时 / 取消

核心对象：

- Run
- RunTask
- RunStep
- RunLog

---

## 4.5 结果中心（Result Center）
职责：

- 执行结果保存
- 截图 / 日志 / Trace 归档
- 结果查询与筛选
- 失败原因聚合分析

核心对象：

- Result
- ResultArtifact
- ResultAssertion
- FailureAnalysis

---

## 4.6 缺陷中心（Bug Center）
职责：

- 失败结果转缺陷
- 缺陷绑定 Case / Run / Result
- 缺陷状态同步
- 缺陷去重与聚合

核心对象：

- Bug
- BugLink
- BugSyncLog

---

## 4.7 AI 生成中心（AI Generation Center）
职责：

- 用例生成任务
- prompt 装配
- 模型调用
- 输出校验
- fallback 策略
- 生成质量记录

核心对象：

- AITask
- PromptTemplate
- PromptVersion
- AIOutput
- AIFallbackRecord

---

## 4.8 字典与规则中心（Dictionary & Rule Center）
职责：

- 页面、模块、类型、来源等字典维护
- 正则规则、禁止规则、审核规则
- 生成约束规则维护

核心对象：

- DictionaryItem
- RuleDefinition
- ValidationPolicy

---

## 4.9 权限与审计中心（Auth & Audit Center）
职责：

- 角色权限控制
- 操作审计
- 变更追踪
- AI / 人工区分

核心对象：

- User
- Role
- Permission
- AuditLog
- ChangeLog

---

## 4.10 配置与观测中心（Config & Observability Center）
职责：

- 环境配置
- Feature Flag
- 模型配置
- 日志、指标、追踪、告警

核心对象：

- AppConfig
- FeatureFlag
- MetricRecord
- TraceRecord
- AlertRule

---

# 5. 推荐部署形态

## 5.1 第一阶段：模块化单体（推荐）
适合你现在这个阶段。

架构建议：

```text
Frontend Console
   |
Backend Monolith
   |- Case Module
   |- Suite Module
   |- Plan Module
   |- Run Module
   |- AI Module
   |- Governance Module
   |
MySQL + Redis + MQ + Object Storage
```

优点：

- 研发成本低
- 事务简单
- 上线快
- 便于快速迭代规范和模型

适用阶段：

- 0 到 20 人团队
- 需求快速变化
- 架构仍在收敛期

---

## 5.2 第二阶段：按能力拆服务
当出现以下特征时考虑拆分：

- AI 调用量激增
- 执行任务量明显增加
- 结果查询和文件存储压力大
- 不同模块由不同团队维护
- 需要独立扩缩容

建议优先拆分：

- AI 生成服务
- 执行调度服务
- 结果归档服务

---

# 6. 前端架构建议

推荐前端采用以下分层：

```text
src/
  app/
  pages/
  modules/
  components/
  services/
  stores/
  hooks/
  types/
  schemas/
  utils/
  constants/
```

页面层职责：

- 页面装配
- 交互组织
- 调用领域模块能力

业务模块层职责：

- 业务逻辑封装
- API 封装
- mapper
- schema
- 局部状态

禁止：

- 页面层直接写复杂业务逻辑
- 页面直接调 request
- 超长大文件持续追加
- AI 擅自新增顶层目录

---

# 7. 后端架构建议

推荐后端采用标准分层：

```text
backend/
  controllers/
  application/
  domain/
  repository/
  infrastructure/
  ai/
  governance/
  jobs/
  common/
```

各层职责如下。

## 7.1 controllers
负责：

- 接口接入
- 参数接收
- 调用 application
- 返回标准响应

不负责：

- 业务规则
- 复杂编排
- 数据库访问

## 7.2 application
负责：

- 业务流程编排
- 跨领域协作
- 权限校验调用
- 事务边界组织

## 7.3 domain
负责：

- 领域对象
- 状态机
- 领域规则
- 领域服务

## 7.4 repository
负责：

- 数据访问抽象
- 持久化接口定义

## 7.5 infrastructure
负责：

- DB / Cache / MQ / OSS / Search / 第三方 SDK 适配

## 7.6 ai
负责：

- prompt 管理
- provider 适配
- 输出校验
- fallback
- 生成日志

## 7.7 governance
负责：

- 字典
- 规则
- 校验
- 审计
- 配置策略

## 7.8 jobs
负责：

- 异步任务
- 调度
- 重试
- 清理
- 补偿

---

# 8. 核心数据流设计

## 8.1 用例生成链路

```text
用户发起生成请求
  → Application 接收请求
  → Dictionary / Rule Center 校验输入
  → Prompt Manager 组装 prompt
  → Model Router 选择模型
  → AI Provider 调用模型
  → Output Validator 校验输出结构
  → Fallback Engine（必要时触发）
  → 生成 Draft CaseVersion
  → 审计记录
  → 返回前端待审核结果
```

关键原则：

- AI 输出必须是结构化字段，不是自由文本
- 不允许 AI 直接生成正式 Case ID
- 不允许 AI 直接入 Ready 状态
- 所有生成必须留下 prompt_version / model / source / latency / fallback 记录

---

## 8.2 用例审核发布链路

```text
Draft CaseVersion
  → 人工审核
  → Review 通过
  → 发布为 Ready
  → 更新 is_latest
  → 写入审计记录
```

关键原则：

- 审核与发布分离
- 发布必须生成版本记录
- Ready 版本不可被直接覆盖

---

## 8.3 执行链路

```text
Plan 发布
  → 创建 Run
  → 解析 RunTask
  → 投递 MQ
  → Worker 执行
  → 写入 StepResult / Result
  → 收集 Artifact
  → 聚合结果
  → 失败触发缺陷流程
```

关键原则：

- Run 与 CaseVersion 强绑定
- Worker 无状态化
- 执行任务必须支持 retry / timeout / cancel
- 大文件产物单独存储到对象存储

---

## 8.4 缺陷闭环链路

```text
失败 Result
  → 失败归因
  → 手工/自动创建 Bug
  → 绑定 Case / Run / Result
  → 缺陷状态同步
  → 回流报表
```

---

# 9. AI 技术架构设计

## 9.1 Prompt Manager
职责：

- 模板管理
- 变量装配
- 场景隔离
- 版本管理
- 回滚能力

建议目录：

```text
prompts/
  case_generation/
  code_generation/
  migration/
  review/
```

必须记录：

- prompt_version
- prompt_template_id
- prompt_hash
- 场景类型
- 生效时间

---

## 9.2 Model Router
职责：

- 根据任务类型选择模型
- 根据成本 / 质量 / 延迟路由
- 支持主模型 + fallback 模型

示例策略：

- Case 生成：高质量模型
- 标签补齐：低成本模型
- JSON 修复：小模型
- 大上下文分析：长上下文模型

---

## 9.3 AI Provider Adapter
必须统一接口，例如：

```text
generate(prompt, config) -> AIResponse
```

适配层下挂：

- OpenAI
- Anthropic
- Azure OpenAI
- 本地模型
- 私有推理服务

业务层不得直接依赖具体 Provider SDK。

---

## 9.4 Output Validator
职责：

- JSON schema 校验
- 字典命中校验
- 字段缺失校验
- 风险输出检测
- 命名规则校验

只有通过校验的结果才能进入 Draft。

---

## 9.5 Fallback Engine
职责：

- 主模型失败时切备用模型
- 主输出不合规时触发修复模型
- 修复失败则进入人工待处理队列

必须记录：

- fallback_reason
- fallback_provider
- fallback_count
- final_source_code（AI / FB）

---

# 10. 数据模型设计建议

## 10.1 核心主键策略
统一采用：

- 内部主键：`id`（数据库自增或雪花）
- 对外业务 ID：`case_id`, `suite_id`, `plan_id`, `run_id`

## 10.2 关键表建议
至少包括：

- test_case
- test_case_version
- test_suite
- test_suite_case_rel
- test_plan
- test_run
- test_result
- ai_task
- ai_output
- prompt_template
- prompt_version
- dictionary_item
- audit_log
- change_log

## 10.3 必备字段
对所有核心对象建议统一保留：

- created_by
- updated_by
- source_code
- status
- version_no
- is_deleted
- created_at
- updated_at

---

# 11. 状态机设计

## 11.1 Case 状态机

```text
Draft → Review → Ready → Deprecated
```

说明：

- Draft：AI 生成或人工草稿
- Review：待审核
- Ready：可正式执行
- Deprecated：废弃，不再推荐使用

## 11.2 AI 任务状态机

```text
Pending → Running → Success / Failed / Cancelled / Fallback
```

## 11.3 Run 状态机

```text
Pending → Queued → Running → Passed / Failed / Blocked / Cancelled / Timeout
```

状态流转必须由领域层统一管理，不允许前端直接任意改状态。

---

# 12. 配置中心设计

必须集中管理以下配置：

- 环境配置
- 数据源配置
- MQ 配置
- 对象存储配置
- 模型路由配置
- prompt 生效配置
- fallback 开关
- Feature Flag
- 字典配置
- 审核策略配置

禁止：

- 把 prompt 写死在业务代码里
- 把环境变量散落在各模块
- 把模型参数硬编码在 controller 或 service 中

---

# 13. 日志、监控与告警设计

## 13.1 日志规范
建议统一结构：

```json
{
  "trace_id": "xxx",
  "user_id": "u001",
  "module": "ai_generation",
  "action": "generate_case",
  "status": "success",
  "source": "AI",
  "latency_ms": 1320,
  "error_code": "",
  "error_message": ""
}
```

## 13.2 必须监控的指标
- AI 调用成功率
- AI 调用平均时延
- fallback 触发率
- 生成结果通过校验率
- 用例审核通过率
- Run 成功率
- Run 超时率
- 执行失败率
- Bug 创建率
- MQ 堆积量
- Worker 并发占用

## 13.3 告警建议
必须配置的告警：

- AI 调用连续失败
- fallback 激增
- 执行队列堆积
- Run 超时率升高
- 对象存储写入失败
- DB 慢查询激增
- 审核队列积压

---

# 14. 安全与权限设计

## 14.1 角色建议
至少包含：

- Admin
- QA Lead
- QA Engineer
- Developer
- Viewer
- AI Agent / System

## 14.2 权限边界
需明确：

- 谁能维护字典
- 谁能修改 prompt
- 谁能切换模型
- 谁能发布 Ready 用例
- 谁能废弃用例
- 谁能执行计划
- 谁能重跑 Run
- 谁能查看 AI 原始输出

## 14.3 安全建议
- Prompt 模板修改必须审计
- 关键配置修改必须审批
- 所有 AI 原始输出保留访问控制
- 敏感字段脱敏

---

# 15. 技术选型建议

以下是偏务实的推荐，不追求花哨。

## 15.1 前端
推荐：

- React + TypeScript
- Zustand / Redux Toolkit
- React Query / TanStack Query
- Zod / Yup
- Vitest / Jest
- Playwright（若平台自带前端 E2E）

## 15.2 后端
推荐两种路线：

### 路线 A：Python
- FastAPI
- SQLAlchemy
- Pydantic
- Celery / RQ / Dramatiq
- Redis
- MySQL / PostgreSQL

适合：

- AI 集成多
- 原型快
- 数据校验强

### 路线 B：Java
- Spring Boot
- MyBatis / JPA
- Spring Validation
- Redis
- RabbitMQ / Kafka
- MySQL / PostgreSQL

适合：

- 企业治理要求高
- 团队 Java 基础强
- 需要稳定中后台体系

## 15.3 存储
- 结构化数据：MySQL / PostgreSQL
- 缓存：Redis
- 日志检索：ELK / OpenSearch
- 对象存储：S3 / OSS / MinIO
- 全文检索：OpenSearch / ES（用于 Case 检索）

## 15.4 队列
- RabbitMQ：中小规模易上手
- Kafka：高吞吐更合适
- 早期优先 RabbitMQ 即可

---

# 16. 单体到服务化的演进路线

## Phase 1：治理先行
目标：

- 完成对象模型
- 完成字典体系
- 完成 Case / AI / Run 最小闭环
- 完成审计和日志

部署：

- 单体 + MQ + Redis + OSS

## Phase 2：AI 中台化
目标：

- Prompt 版本化
- Provider 可切换
- fallback 稳定
- AI 任务队列化

拆分：

- AI Generation Service
- Prompt Service

## Phase 3：执行平台化
目标：

- 执行调度独立
- Worker 池扩缩容
- 执行结果归档独立
- 失败分析增强

拆分：

- Execution Service
- Result Service

## Phase 4：智能治理化
目标：

- 用例质量评分
- AI 输出质量评分
- 重复用例识别
- 自动建议重构和归档

---

# 17. 推荐最小可落地版本（MVP）

如果你现在要最小可用但不容易推翻，建议第一版只做：

## 必做模块
- Case Center
- AI Generation Center
- Dictionary & Rule Center
- Run Center
- Result Center
- Audit & Config

## 必做能力
- 结构化 Case Draft 生成
- 字典约束
- Case 审核发布
- Plan / Run / Result 基础闭环
- prompt_version 记录
- fallback 记录
- 审计日志
- 任务状态机

## 先不做
- 不急着微服务
- 不急着复杂推荐系统
- 不急着全自动缺陷闭环
- 不急着插件系统

---

# 18. 研发实施优先级

## P0：必须先做
- 领域对象模型
- ID 规则
- 字典与规则中心
- Case 状态机
- AI 输出校验
- 审计日志
- Run 状态机
- 配置中心基础版

## P1：尽快做
- Prompt 版本管理
- Model Router
- fallback 引擎
- Result Artifact 归档
- 失败归因基础能力

## P2：后续增强
- 多模型路由优化
- 智能推荐
- 质量评分
- 自动归档
- 插件化扩展

---

# 19. 你当前阶段最应该冻结的 12 条底线

1. 顶层模块不随意新增  
2. AI 不能直接生成正式 ID  
3. AI 不能绕过字典和规则  
4. Ready 用例不可直接覆盖  
5. Run 必须绑定 CaseVersion  
6. 所有核心对象必须可审计  
7. Prompt 必须版本化  
8. 模型调用必须可替换  
9. 所有异步任务必须有状态机  
10. 所有执行产物必须归档  
11. 所有关键配置必须集中管理  
12. 所有核心流程必须可观测  

---

# 20. 结论

一套真正能用的 AI 自动化测试平台技术架构，不是把“AI 调起来”就结束，而是要同时解决：

- 结构化对象模型
- 治理边界
- AI 可替换
- 状态可控
- 结果可追踪
- 架构可演进

现阶段最优解不是一开始做复杂微服务，而是：

**先做模块化单体 + 强治理 + AI 适配层抽象 + 执行链路闭环。**

这条路线最务实，也最不容易返工。

---

# 21. 附录：建议下一步输出的文档清单

建议你接下来继续沉淀以下 6 份文档：

1. 《AI自动化测试平台数据模型设计 v1.0》
2. 《AI自动化测试平台接口契约规范 v1.0》
3. 《AI自动化测试平台错误码规范 v1.0》
4. 《AI自动化测试平台 Prompt 管理规范 v1.0》
5. 《AI自动化测试平台任务调度规范 v1.0》
6. 《AI自动化测试平台观测与告警规范 v1.0》

这些文档一旦补齐，你的平台架构会稳很多。

---

**文档结束**
