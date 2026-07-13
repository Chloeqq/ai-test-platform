# AGENTS.md — Codex 硬约束

本文件是 Codex 在本仓库执行任务时必须优先读取和遵守的硬约束。

除非用户在当前任务中明确覆盖某条规则，否则不得违反本文件。若任务要求与本文件冲突，必须先指出冲突并停止实施，不得自行选择折中方案。

---

## 1. EvieAi 资料优先级

涉及测试资产、测试点生成、用例生成、编译、Runner、页面对象、需求文档、AI 生成链路的任务，必须按任务范围读取资料。

默认读取顺序：

```text
AGENTS.md
→ 当前阶段实施文档
→ 相关架构专题
→ 按需查阅架构图和 Excel 对应工作表
```

发生冲突时，优先级如下：

1. 用户本次明确确认的决策
2. `AGENTS.md`
3. `docs/evie-ai/implementation/当前阶段文档`
4. `docs/evie-ai/architecture/专题文档`
5. EvieAi 架构图
6. Excel 完整设计参考
7. 旧文档
8. 旧代码现状

旧文档只能用于历史和迁移分析，不得作为目标架构依据。

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

Excel 定义完整目标空间，Phase 文档定义本次实施边界。Excel 不是每次代码修改的直接需求清单。

开始 EvieAi 相关任务前，至少确认：

- 当前阶段
- 当前任务允许修改的模块
- 当前任务明确不处理的内容
- 是否存在已确认的人工决策
- 是否存在未提交工作区改动
- 当前 Alembic head、Git branch 和 HEAD 是否需要核对

---

## 2. 自然语言测试资产硬边界

EvieAi 以自然语言 `TestAsset` 为中心。

`TestAsset` 是一等持久化业务实体，负责表达“测什么”。

`TestCase` 是执行实体，负责表达“如何执行”。

两者是不同生命周期，不得混用。

自然语言测试资产允许包含：

- `title`
- `precondition`
- `natural_steps`
- `expected_result`
- `priority`
- `tags`
- `review_status`
- `conversion_status`
- 版本、来源和审计信息

自然语言测试资产不得包含：

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

低质量、低置信度、存在歧义或暂时不可执行的自然语言资产，也必须允许进入资产中心。

---

## 3. 生成侧禁止事项

AI 生成侧只允许生成自然语言测试点。

生成侧不得：

- 生成 `action / target / value`
- 生成 `structured_steps`
- 生成 DSL 或 Compiler IR
- 解析页面元素、Locator、Selector
- 调用 Behavior Registry
- 调用 ContractValidator
- 调用 ExecutionCompiler
- 调用 CaseQualityGate
- 调用 Runner
- 生成 `script_code`
- 创建可执行 TestCase
- 直接绑定执行资源
- 使用固定页面、固定元素或固定环境补全缺失信息

生成上下文必须在模型调用前建立。

AI 可以消费经过后端验证的上下文，但不得生成或覆盖权威数据库 ID。

---

## 4. 资产入库禁止事项

资产入库只负责：

- ID 分配
- 来源绑定
- 幂等检查
- 精确重复检测
- 疑似语义重复标记
- 自然语言资产版本持久化
- 必要的审计与追踪

资产入库不得：

- 判断可执行性
- 解析页面对象
- 解析测试数据
- 生成机器步骤
- 编译
- 选择 Runner
- 执行质量门拦截
- 创建 TestCase
- 写入 `script_code`

低质量、低置信度、暂时不可执行的自然语言资产也必须允许入库。

智能评估只能在入库后异步执行，只能产生评分、标签、警告或建议，不得阻止资产入库。

---

## 5. Candidate 必须退出业务主链

EvieAi 不存在以下产品主链概念：

- Candidate Preview
- 候选项复选框
- 全选候选
- 保存所选候选
- 只有被选中才分配资产 ID
- Candidate 作为持久化业务实体

AI 响应可以在服务内部短暂使用 DTO，但必须立即进入统一资产入库，不得暴露为可选择业务对象。

以下旧概念不得进入 EvieAi 新模型、API、前端交互和数据库表：

- `selected_candidates`
- `candidate preview`
- `save selected`
- `TestPointPlan`
- point 与 candidate 往返转换

---

## 6. Asset-to-Case 是唯一转换入口

自然语言转机器语言只能发生在 Asset-to-Case 转换域。

唯一合法链路：

```text
TestAssetVersion
→ ConversionAttempt
→ 场景识别
→ Execution Requirement Manifest
→ 资源能力网关
→ Resource Bindings
→ Bound Execution Plan
→ 测试用例矩阵展开
→ 统一转换质量门
→ Compiler Router
→ TestCase → TestCaseVersion → script_code
```

Asset-to-Case 必须锁定明确的 `TestAssetVersion`。

页面对象、测试数据、环境、凭证、Mock、异常、安全、性能和原子能力，只能在转换阶段解析和绑定。

转换失败时：

- 保留 TestAsset
- 保留 TestAssetVersion
- 保留用户编辑
- 记录 ConversionAttempt 错误
- 不创建无效 TestCase
- 不创建无效 `script_code`
- 不回写或篡改自然语言资产内容

`review_status` 与 `conversion_status` 必须分离。

合法状态包括：

```text
review_status = approved
conversion_status = blocked
```

---

## 7. Runner 硬边界

Runner 只读取：

- `TestCaseVersion.script_code`
- 运行时资源引用
- 版本化资源绑定快照
- 明确的环境和凭证引用

Runner 不得：

- 重新理解自然语言资产
- 重新解析自然语言
- 运行时重新编译
- 运行时生成机器步骤
- 从 TestAsset 推导执行行为
- 直接修改 TestAsset 或 TestAssetVersion
- 使用固定项目、固定环境、固定账号或固定资源作为回退

---

## 8. ID 规则

必须复用或扩展当前系统已有 ID 模块和规则。

不得建立平行 ID 系统。

特别注意：

- `requirement_id` 不是 `request_id`
- 文档页 ID 不是页面对象 ID
- AI 不得生成权威数据库 ID
- 前端不得生成内部权威数据库 ID
- 资产 ID 不再依赖候选选择
- 生成上下文必须在模型调用前建立
- 不得使用 8 位短 hex 作为核心业务 ID
- EvieAi Phase 0 项目作用域复用现有 `TestProject.project_code`
- EvieAi Phase 0 核心业务 ID 使用 `<prefix>_<uuid4hex32>`
- 外部系统 ID 与内部业务 ID 必须分离
- ID 前缀和格式只能在统一 ID 模块定义
- 不得在其他领域复制 ID 生成逻辑

Phase 0 已确认的 ID 形式：

```text
req_<uuid4hex32>
reqv_<uuid4hex32>
ta_<uuid4hex32>
tav_<uuid4hex32>
tas_<uuid4hex32>
```

---

## 9. 命名规则

新增权威文档、代码、测试、Migration 和提交信息必须使用 EvieAi 命名。

| 类型 | 命名 |
|---|---|
| 产品名 / 文档标题 | `EvieAi` |
| 文档目录 / Git scope | `evie-ai` |
| Python 包目录 | `evie_ai` |
| 权威文档路径 | `AGENTS.md`, `docs/evie-ai/**` |

不得新增或长期保留旧产品名对应的权威文档路径、Python 包路径或测试路径。

数据库表名保持业务通用命名，不增加品牌前缀：

- `requirements`
- `requirement_versions`
- `test_assets`
- `test_asset_versions`
- `test_asset_sources`

领域类保持业务通用命名，不增加 `EvieAi` 前缀：

- `Requirement`
- `RequirementVersion`
- `TestAsset`
- `TestAssetVersion`
- `TestAssetSource`

Git scope 使用：

```text
docs(evie-ai)
feat(evie-ai)
fix(evie-ai)
test(evie-ai)
refactor(evie-ai)
```

---

## 10. 旧链判断

以下旧实现只能用于历史分析、兼容迁移或技术复用评估，不得作为 EvieAi 目标架构：

- CandidateNormalizer
- selected_candidates
- candidate preview
- 保存所选候选
- TestPointPlan
- point ↔ candidate 往返转换
- resolve_explicit_step
- structured_steps_from_candidate
- Behavior Registry 提前介入
- Direct compile
- Orchestrator 内部编译
- Web 层再次校验或再次编译
- 生成侧调用质量门
- 资产保存时提前结构化
- Runner 运行时重新理解自然语言

旧 Compiler、Runner、Evidence、Report、Page Object 等模块可以作为技术能力评估复用，但必须重新放入正确的 EvieAi 领域边界中。

技术组件可复用，不代表旧业务调用位置可复用。

---

## 11. 禁止散落业务硬编码

业务代码中不得散落以下内容：

- 默认项目、固定 `project_code`
- 固定 requirement、asset、case、page、element、environment、resource ID
- 固定 URL、端口、Bucket、数据库地址
- 固定模型名称、Prompt 版本
- 固定超时、重试次数、并发数
- 固定质量阈值、评分阈值
- 固定环境名
- 固定用户名、密码、Token、Secret
- 根据某个具体客户、租户或项目编写的条件分支
- 状态 magic string
- 错误码 magic string
- 未命名的 magic number

处理规则：

- 环境差异使用 Settings 或环境变量
- 租户/项目差异使用数据库配置或项目配置服务
- 业务策略使用枚举、Policy 或版本化规则对象
- 函数行为使用显式、类型化参数
- 敏感配置使用 Vault/KMS/Secret reference
- 稳定协议常量集中定义
- 同一个默认值只能有一个权威定义位置

缺少必填配置时必须明确失败，不得静默使用固定项目、固定环境或固定资源回退。

测试数据可以使用固定值，但必须放在 fixture、factory 或 test helper 中，并明确只用于测试。

---

## 12. 配置化和参数化

配置按以下边界管理：

- 环境配置：Settings / environment variables
- 租户或项目配置：数据库配置或项目配置服务
- 领域规则：Policy、枚举或版本化规则对象
- 函数行为：显式、类型化参数
- 敏感配置：Vault/KMS/Secret reference
- 可调阈值：配置对象或 Policy
- Schema 版本：统一常量或 Schema Registry

不得：

- 在函数内部读取多个不透明全局变量
- 使用任意 `dict` 传递核心业务参数
- 在多个模块重复定义相同默认值
- 通过 `metadata` JSON 承载核心状态、外键或强业务语义
- 在失败时静默退回固定项目、固定环境、固定页面或固定账号
- 将环境变量读取散落在业务代码中
- 在 Repository 内部决定业务策略默认值

所有新增配置必须说明：

- 配置名
- 类型
- 默认值
- 是否必填
- 权威定义位置
- 生效范围
- 安全级别
- 测试覆盖

---

## 13. 模块化和单一职责

分层职责：

- Router：认证、请求校验、调用 Service、返回响应
- Schema：输入输出契约，不承载业务流程
- Service：业务编排、状态转换、事务边界
- Repository：数据库查询和持久化
- Model：持久化结构和关系
- Policy：业务规则、状态转换、阈值判断
- Adapter：外部系统和基础设施适配
- Compiler：转换机器执行表示
- Runner：执行已生成的 `script_code`

不得：

- Router 直接执行复杂 ORM 写入
- Router 直接控制事务
- Repository 调用 AI、Compiler、Runner 或外部 HTTP API
- ORM Model 执行业务编排
- Schema 执行数据库查询
- 跨领域导入其他模块私有函数
- 为方便复制已有业务逻辑
- 在多个入口重复实现同一业务流程
- 通过 Facade 掩盖不清晰的领域边界
- 创建职责模糊的大型 util 模块
- 将多个领域聚合到一个超大文件

新模块必须明确：

- 输入
- 输出
- 事实源
- 依赖方向
- 事务边界
- 错误模型
- 可测试边界
- 不承担的职责

---

## 14. 唯一事实源

同一业务事实只能有一个权威存储位置。

EvieAi 当前事实源包括：

- Requirement 正文：`RequirementVersion`
- 自然语言测试资产正文：`TestAssetVersion`
- 当前需求版本：`Requirement.current_version`
- 当前资产版本：`TestAsset.current_version`
- 可执行脚本：`TestCaseVersion.script_code`
- 运行时资源：版本化 Resource Binding Snapshot
- 环境配置：Settings 或配置中心
- 敏感信息：Credential / Secret reference
- 执行事实：Execution / StepResult / Evidence
- 报告：由执行事实派生

不得：

- 同时在 Requirement 和 RequirementVersion 保存需求正文
- 同时在 TestAsset 和 TestAssetVersion 保存自然语言内容
- 从多个字段推测同一个状态
- 把缓存、快照或派生字段当作主事实源
- 通过修改历史版本纠正当前内容
- 在 Runner 中重新解释 TestAsset 自然语言
- 在多个配置文件重复定义同一业务默认值
- 在数据库和代码中同时维护两份状态转换规则

派生数据必须：

- 能从事实源重新计算
- 明确标识为派生结果
- 记录计算版本或规则版本
- 不反向覆盖事实源

---

## 15. 数据一致性和事务

涉及多个实体的写操作必须在同一个事务中完成。

必须保证：

- 主实体、版本和来源要么全部成功，要么全部回滚
- `current_version` 必须属于对应聚合
- 版本号在聚合内唯一
- 历史版本不可原地覆盖
- 软删除实体默认不参与正常查询
- 更新聚合时使用 `row_version` 或等价并发控制
- 唯一性由业务校验和数据库约束共同保护
- 数据库异常不得被转换成部分成功
- 重试不得产生重复实体或重复版本
- 多表写入不得跨多个独立 commit
- 事务失败后不得继续使用脏 Session
- Repository 必须明确 `flush / commit / rollback` 的责任归属

禁止：

- 先 commit 主实体，再单独创建版本
- 捕获数据库异常后继续执行
- 只用“查询后插入”代替数据库唯一约束
- 绕过 Repository 直接修改 `current_version`
- 依赖前端保证数据库一致性
- 修改历史版本记录
- 在事务外更新聚合状态
- 以最终一致性掩盖本应强一致的聚合内写入

Phase 0 `current_version` 允许暂不建立数据库外键，但必须由 Repository 事务和测试保证父子一致性。

---

## 16. 版本不可变

以下对象一旦创建，不得原地覆盖业务内容：

- RequirementVersion
- TestAssetVersion
- TestCaseVersion
- 版本化资源快照
- 执行证据

修改内容必须创建新版本。

版本表原则上只保留：

- `created_at`
- `created_by`

不得为不可变版本表增加用于业务编辑的：

- `updated_at`
- `updated_by`

如确需修复历史脏数据，必须使用独立迁移、审计记录和明确批准，不得通过普通业务接口修改。

---

## 17. 幂等和重复处理

所有可能被重试的创建型操作必须明确幂等策略。

必须定义：

- 幂等作用域
- 幂等键来源
- 内容规范化规则
- 指纹计算规则
- 重复请求返回已有结果还是明确冲突
- 并发请求时的数据库保护方式
- 幂等记录的保留周期
- 失败请求是否可重试

禁止：

- 只通过内存缓存实现关键幂等
- 将精确重复、语义重复和版本内容相同混为一类
- 用资产版本表唯一约束代替完整 Intake 去重规则
- 在无数据库约束时依赖单次查询结果
- 用随机 sleep 规避并发冲突

精确重复、疑似语义重复、同资产历史内容恢复必须分别处理。

---

## 18. 显式状态机

状态值必须：

- 使用 Enum 或集中常量
- 有明确允许的转换关系
- 通过领域方法或 Policy 转换
- 对非法转换明确报错
- 记录转换原因和操作者
- 必要时记录状态转换事件
- 与持久化字段保持一一对应

不得：

- 在任意代码位置直接赋自由字符串状态
- 通过多个布尔字段隐式拼出主状态
- 由前端任意指定最终状态
- 静默修正非法状态
- 把审核状态、转换状态、执行状态混为一个字段

EvieAi Phase 0 已确认：

- TestAsset 新版本后 `review_status = pending`
- 原 `conversion_status = succeeded / stale`，新版本状态为 `stale`
- 原 `conversion_status = not_started / blocked`，新版本状态为 `not_started`
- `conversion_status = processing` 时禁止直接编辑

---

## 19. 错误和异常处理

必须使用结构化领域异常。

错误至少应包含：

- stable error code
- domain
- stage
- human-readable message
- retryable
- trace_id
- 可选修复提示
- 可选关联实体 ID

禁止：

- `except Exception: pass`
- 捕获异常后返回假成功
- 记录异常但继续提交事务
- 直接向客户端暴露堆栈、SQL、Secret
- 使用自由文本作为唯一错误判断依据
- 在多个模块重复定义相同错误码
- 将预期业务冲突返回为 500
- 将数据库唯一约束错误吞掉并重新创建对象

只有真正可恢复的异常才能重试。

所有数据库异常必须触发明确 rollback 或由统一事务管理器处理。

---

## 20. 日志和可观测性

日志必须结构化，并至少支持：

- `trace_id`
- `request_id`
- `project_code`
- 领域对象 ID
- 操作名称
- 状态
- duration
- error_code

不得：

- 使用 `print` 代替日志
- 记录明文 Secret
- 记录完整 Authorization、Cookie、Password、Token
- 记录未经脱敏的需求正文、日志输入或模型 Prompt
- 只记录“失败了”而没有错误码和上下文
- 在多个模块重复记录同一异常堆栈

可观测性标签必须统一命名，不能各模块自定义同义字段。

---

## 21. 安全和敏感信息

不得在以下位置保存或打印明文 Secret：

- 源代码
- 配置文件
- 日志
- 数据库普通业务字段
- TestAsset
- `TestCaseVersion.script_code`
- 测试报告
- Prompt 和模型响应
- 截图、视频、网络记录

凭证只能保存引用。

日志和证据必须按规则脱敏：

- Authorization
- Cookie
- Password
- Token
- Personal data
- 内部地址
- 请求和响应中的敏感字段

不得为了调试临时提交真实凭证、生产数据或客户数据。

---

## 22. Migration 规范

Migration 必须：

- 读取真实 Alembic head
- 不按文件日期猜测 `down_revision`
- upgrade 和 downgrade 顺序明确
- 明确新表、字段、索引、唯一约束和外键
- 不修改范围外旧表
- 不顺便迁移旧链数据
- 支持在目标数据库和测试数据库中的兼容行为
- 避免依赖 nullable 多列唯一约束实现关键身份
- 对循环外键给出明确处理策略
- 对大表变更说明锁表和回滚风险

禁止：

- 手工编造 `down_revision`
- 将 Schema 变更和业务数据迁移混在同一个不可审查步骤
- 在 downgrade 中删除范围外数据
- 用 Migration 修复应用层状态机
- 在未确认数据库类型时使用数据库专属语法
- 为通过测试而跳过实际索引或约束

Migration 实施前必须只读确认：

```text
alembic heads
alembic history
```

---

## 23. 测试要求

每个变更必须覆盖与其风险匹配的测试。

最低要求：

- 纯函数：单元测试
- ID：格式、长度、字符集、碰撞测试
- ORM字段和约束：模型测试
- Pydantic Schema：字段边界测试
- 多表事务：Repository测试
- Migration：upgrade/downgrade或结构测试
- 模块边界：AST架构测试
- 数据一致性：失败回滚、并发和唯一约束测试
- 状态机：合法与非法转换测试
- Bug修复：失败复现测试
- 配置：缺失、默认值和安全性测试
- 软删除：默认查询过滤测试

必须覆盖的关键一致性场景：

- 创建聚合中途失败时全部回滚
- `current_version` 不能指向其他聚合版本
- 并发创建相同 `version_no` 只能成功一个
- 重复来源只能保留一条关系
- `row_version` 冲突不能静默覆盖
- 软删除数据不出现在普通查询
- 数据库唯一约束冲突返回稳定领域错误
- 历史版本不可被普通更新接口覆盖

不得：

- 为使测试通过而删除有效断言
- 修改生产逻辑适配错误 fixture
- 大范围更新 snapshot 掩盖行为变化
- 跳过失败测试而不记录原因
- 把 Mock 行为当作真实数据库一致性证明
- 只测 happy path
- 只运行新增测试而不运行必要回归测试

---

## 24. 架构守卫

EvieAi 必须使用自动化架构守卫保护边界。

至少包括：

### AST Import 检查

EvieAi 资产模块不得依赖：

- structurer
- execution_compiler
- ContractValidator
- resolve_explicit_step
- TestPointAsset
- Candidate
- selected_candidates
- Runner
- QualityGate

### Schema 字段检查

TestAsset / TestAssetVersion 不得包含：

- structured_steps
- steps_hint
- action
- target
- value
- locator
- selector
- compiler_ir
- dsl
- script_code
- runner_steps

### ORM 字段检查

- `requirements` 不保存正文
- `test_assets` 不保存自然语言正文
- 版本表不保存机器字段
- 版本表不得原地更新业务内容
- TestAssetSource Phase 0 不预建 Document/Page/Generation 占位字段
- `content_checksum` 不能误设为阻止历史恢复的唯一约束

纯文本搜索只能作为辅助，不能替代 AST、Schema 和 ORM 结构检查。

---

## 25. API 和兼容性

新增或修改 API 时必须：

- 使用显式 Schema
- 明确状态码
- 使用稳定错误码
- 保持向后兼容或提供迁移方案
- 不在 Router 中实现业务事务
- 不暴露内部数据库 PK
- 不允许客户端控制权威 ID
- 不返回明文 Secret
- 明确分页、排序和过滤行为
- 明确幂等语义

未经确认不得：

- 修改已有公共 API 语义
- 删除旧字段
- 改变 ID 格式
- 改变状态枚举
- 将旧 API 静默代理到不兼容的新逻辑

---

## 26. 第三方依赖

未经用户明确批准，不得新增第三方依赖。

确需新增依赖时，必须先说明：

- 依赖名称和版本
- 使用目的
- 为什么现有标准库或已有依赖无法满足
- 许可证
- 安全风险
- 运行时影响
- 替代方案
- 移除成本

不得为了一个小工具引入大型框架。

---

## 27. 变更范围

每次任务必须保持最小变更范围。

禁止：

- 在功能提交中顺便重构无关模块
- 在 Migration 提交中修改旧业务链
- 在文档提交中混入依赖升级
- 在 EvieAi 提交中修复旧 Candidate 链
- 未经批准修改公共 API、数据库字段或 ID 格式
- 未经批准新增第三方依赖
- 顺手修复范围外问题
- 将格式化整个仓库混入功能变更
- 删除旧文档或旧代码而没有迁移和验证依据

发现范围外问题时，应记录为风险或后续任务，不得扩大当前提交。

---

## 28. Git 和工作区规则

实施前必须检查：

```text
git branch --show-current
git rev-parse HEAD
git status --short
```

必须区分：

- 已提交基线
- 当前未提交改动
- 当前任务新增改动
- 旧链修复
- 文档改动
- 依赖文件改动
- 本地调试产物

不得：

- 混入无关工作区改动
- 提交 `.playwright-mcp` 等本地产物
- 将 docs、依赖升级、Migration 和业务代码混成不可审查提交
- 覆盖用户未提交改动
- 未经允许执行 destructive reset
- 未经允许强推
- 在不清楚改动来源时删除文件

每个提交应：

- 单一职责
- 可独立审查
- 可独立回滚
- Commit scope 使用 `evie-ai`
- 不混入旧链无关改动

---

## 29. 实施前报告

编码前必须先输出：

1. 当前 Git branch、HEAD 和工作区状态
2. 计划修改的文件
3. 每个文件的职责
4. 新增参数及其来源
5. 新增配置及其权威定义位置
6. 唯一事实源
7. 事务边界
8. 唯一性和幂等规则
9. 状态转换
10. 数据一致性约束
11. 测试计划
12. 明确不在本次范围内的内容
13. 风险和待确认项

发现以下情况时必须停止并报告，不得自行绕过：

- 需要固定项目、固定环境或固定资源
- 需要复制已有业务逻辑
- 需要导入其他领域私有函数
- 需要无事务多表写入
- 需要新增未经批准依赖
- 需要修改当前阶段之外的数据模型
- 资料之间存在未解决冲突
- 当前工作区存在无法安全隔离的无关改动

---

## 30. 实施后报告

实施完成后必须输出：

1. 实际修改文件
2. 与计划的偏差
3. 新增或修改的配置
4. 参数化清单
5. 数据库和 Migration 变化
6. 事务和回滚行为
7. 唯一约束和幂等规则
8. 状态转换规则
9. 运行的测试及完整结果
10. 未运行的测试及原因
11. 未解决风险
12. 后续建议，但不得自动扩大本次任务

不得声称测试通过，除非实际运行并获得通过结果。

不得声称问题已修复，除非有可复现证据或测试证明。

---

## 31. Phase 0 额外限制

EvieAi Phase 0 只允许实施：

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
- 架构守卫
- 对应测试
- 权威文档

EvieAi Phase 0 不允许实施：

- AI 生成
- 文档解析链改造
- Candidate 迁移
- 完整 Asset Intake
- 语义去重
- Asset-to-Case
- ConversionAttempt
- Manifest
- Resource Binding
- Bound Plan
- Compiler
- Runner
- TestCase 创建
- 前端页面
- 旧数据迁移
- 旧链删除

Phase 0 的 `TestAssetSource` 只支持 Requirement 来源。

Phase 0 不新增：

- `intent_id`
- `project_id`
- `project_uuid`
- Document / Section / Page / GenerationContext / GenerationBatch 占位字段
- 平行 Project 表
- 平行 ID 服务

---

## 32. 违反规则时的处理

当任务要求可能违反本文件时，必须：

1. 明确指出冲突规则
2. 说明潜在后果
3. 停止相关实施
4. 请求用户确认新的决策
5. 在用户明确确认前，不得提交临时绕过方案

不得以“先临时实现”“后续再重构”为理由违反硬边界。

## 历史代码渐进治理

本规范不要求在单个任务中一次性重写所有历史代码。

处理原则：

1. EvieAi 新增代码必须完全符合本文件和 coding-standards。
2. 历史代码未被当前任务触及时，可以暂时保留，但不视为合规实现。
3. 修改历史代码时，所有新增和修改部分必须符合规范。
4. 与当前任务直接相关的高风险违规必须同步修复。
5. 与当前任务无关的历史问题必须登记，不得扩大当前提交。
6. 不得复制历史违规模式到新代码。
7. 历史违规基线只允许减少，未经用户明确批准不得增加。
8. Candidate、提前结构化和直接编译等旧链处于冻结状态，不得新增产品能力。
9. 安全泄露、数据损坏、跨项目污染、假成功、无事务多表写入等高风险问题不得获得历史豁免。
10. 大规模旧代码治理必须使用独立计划、独立测试和独立提交。

当无法判断某个问题属于当前任务必要修复还是范围外重构时，必须先报告，不得自行扩大范围。