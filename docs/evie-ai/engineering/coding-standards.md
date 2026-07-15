# EvieAi Coding Standards

日期：2026-07-12
状态：Authoritative
适用范围：EvieAi 相关后端、前端、数据模型、Migration、测试、文档、AI 调用、Compiler、Runner 和基础设施适配代码

本文是 EvieAi 的详细工程规范。`AGENTS.md` 定义不可违反的硬约束，本文负责说明具体编码规则、实现方式、示例、审查要点和允许的例外。

发生冲突时，优先级如下：

1. 用户当前任务中的明确确认
2. `AGENTS.md`
3. 当前阶段实施文档
4. 本文
5. EvieAi 架构专题
6. 架构图和 Excel
7. 旧文档
8. 旧代码现状

---

## 1. 基本原则

EvieAi 代码必须满足以下原则：

- 领域边界清晰
- 模块职责单一
- 业务规则显式
- 配置来源唯一
- 数据事实源唯一
- 多表写入强一致
- 版本不可变
- 状态转换可审计
- 核心写操作可重试且幂等
- 错误结构稳定
- 日志可追踪且不泄露敏感信息
- 测试与风险匹配
- 变更范围最小
- 不依赖临时硬编码完成目标

任何“先写死，后续再改”“先复制一份，之后再抽象”“先绕过事务，后面补”的实现方式，默认不接受。

---

## 2. Python 代码规范

### 2.1 Python 版本和语言特性

- 使用仓库当前明确支持的 Python 版本。
- 不得为了使用新语法私自提升运行时版本。
- 优先使用标准库和现有依赖。
- 未经批准不得新增第三方依赖。
- 使用现代类型注解，不使用无约束的动态对象传播核心业务数据。

推荐：

```python
def create_asset(command: CreateTestAssetCommand) -> TestAsset:
    ...
```

不推荐：

```python
def create_asset(data: dict):
    ...
```

### 2.2 类型注解

以下位置必须有类型注解：

- 所有公开函数
- Service 方法
- Repository 方法
- Policy 方法
- Adapter 接口
- Domain command/result
- 配置对象
- 事件对象

不得使用：

```python
Any
dict[str, Any]
list[Any]
```

承载核心业务语义，除非是明确的边界适配层，并且进入领域层前已转换为类型化对象。

### 2.3 函数长度和复杂度

单个函数应聚焦一个明确动作。

建议标准：

- 一般函数不超过 40 行
- 分支复杂度过高时拆分 Policy 或私有方法
- 嵌套层级不超过 3 层
- 超过 5 个独立参数时，优先使用 command/config 对象
- 不使用布尔参数控制多个行为分支

不推荐：

```python
create_asset(data, validate=True, dedup=True, save=True, compile=False)
```

推荐：

```python
create_asset(command: CreateTestAssetCommand)
```

### 2.4 命名

命名必须表达领域含义。

推荐：

```python
requirement_id
test_asset_version_id
source_identity_hash
conversion_status
```

禁止模糊命名：

```python
data
obj
item
info
tmp
flag
result2
new_data
```

私有帮助函数必须仍然表达具体意图：

```python
_build_source_identity_hash()
_validate_current_version_ownership()
```

### 2.5 不使用通用 util 承载业务逻辑

禁止创建以下类型的大型文件：

```text
utils.py
helpers.py
common.py
misc.py
```

用于堆放跨领域业务逻辑。

可接受的 util 只应包含稳定、无领域语义、无副作用的基础函数，例如：

- 时间格式化
- 哈希
- 通用分页
- 安全字符串处理

领域逻辑必须进入：

- Service
- Policy
- Domain helper
- Repository
- Adapter

---

## 3. 模块与依赖方向

### 3.1 推荐目录职责

```text
app/
  api/ or routers/
  schemas/
  services/
  policies/
  repositories/
  models/
  adapters/
  core/
```

职责：

| 层 | 职责 |
|---|---|
| Router | 请求解析、认证授权、调用 Service、映射响应 |
| Schema | 输入输出契约和字段校验 |
| Service | 业务编排、事务边界、跨 Repository 协调 |
| Policy | 状态转换、规则判断、策略计算 |
| Repository | 数据持久化和查询 |
| Model | ORM结构、关系、数据库默认值 |
| Adapter | 外部系统、消息队列、对象存储、模型服务 |
| Core | Settings、日志、ID、错误、事务基础设施 |

### 3.2 依赖方向

推荐依赖：

```text
Router
  ↓
Service
  ↓
Policy / Repository / Adapter interface
  ↓
Model / Infrastructure adapter
```

禁止依赖：

```text
Repository → Router
Repository → AI Client
Repository → Compiler
Repository → Runner
Model → Service
Schema → Repository
Runner → TestAsset natural-language parser
```

### 3.3 跨领域访问

跨领域调用必须通过公开接口。

不得：

- 导入其他领域的 `_private_function`
- 直接读取其他领域内部表实现业务规则
- 复制其他领域逻辑
- 绕过公开 Service 调用 Repository

跨领域依赖必须说明：

- 调用方
- 被调用方
- 输入契约
- 输出契约
- 失败语义
- 事务归属
- 可用性要求

---

## 4. 禁止硬编码

### 4.1 禁止的硬编码类型

业务代码中不得散落：

- 固定 `project_code`
- 固定用户、租户、客户、环境
- 固定 URL、端口、数据库地址
- 固定 Bucket、Topic、Queue
- 固定模型名称
- 固定 Prompt 版本
- 固定资源 ID
- 固定页面和元素编码
- 固定超时、重试次数、并发数
- 固定状态字符串
- 固定错误码
- 固定质量阈值
- 固定凭证和 Token
- 针对某个客户的 if/else

禁止：

```python
project_code = "mall"
timeout = 30
model = "gpt-4"
base_url = "http://localhost:8000"
```

### 4.2 允许的稳定常量

以下内容可以集中定义为常量：

- 已确认 ID 前缀
- 已确认状态枚举
- 协议版本
- Schema 版本
- 不随租户、环境或项目变化的稳定技术常量

例如：

```python
REQUIREMENT_ID_PREFIX = "req"
TEST_ASSET_ID_PREFIX = "ta"
```

这些常量必须集中维护，不得散落重复定义。

### 4.3 默认值规则

默认值只能有一个权威定义位置。

例如：

- Settings 默认值：定义在 Settings
- ORM 默认值：仅用于数据库安全兜底
- Schema 默认值：仅用于 API 契约
- Policy 默认值：用于领域规则

不得在三处同时定义不同默认值。

缺少关键配置时，应明确失败，不得偷偷使用业务默认值。

---

## 5. 配置化

### 5.1 配置分类

| 配置类型 | 权威来源 |
|---|---|
| 环境配置 | Settings / 环境变量 |
| 项目配置 | 项目配置表或配置服务 |
| 租户配置 | 租户配置表或配置服务 |
| 领域规则 | Policy / 版本化规则对象 |
| AI模型配置 | 模型注册中心或配置表 |
| Prompt | Prompt版本库 |
| Secret | Vault/KMS/Secret reference |
| 超时/重试 | 类型化配置对象 |
| Feature Flag | Feature Flag服务或统一配置 |

### 5.2 配置对象

推荐：

```python
@dataclass(frozen=True)
class ConversionPolicyConfig:
    max_variants: int
    timeout_seconds: int
    allow_partial_binding: bool
```

不推荐：

```python
config = {
    "max": 10,
    "timeout": 30,
    "allow": True,
}
```

### 5.3 环境变量读取

环境变量只能在统一 Settings 层读取。

禁止在业务代码中：

```python
os.getenv("DATABASE_URL")
os.getenv("MODEL_NAME")
```

应通过注入后的 Settings 或配置对象使用。

### 5.4 配置校验

应用启动时应校验必填配置。

至少校验：

- 类型
- 非空
- 合法范围
- 互斥关系
- 依赖关系
- Secret 引用格式

错误配置必须启动失败，不得运行到业务请求阶段才暴露。

---

## 6. 参数化

### 6.1 显式参数

函数行为差异应通过显式、类型化参数表达。

推荐：

```python
def list_assets(
    project_code: str,
    *,
    include_deleted: bool = False,
    limit: int = 50,
) -> list[TestAsset]:
    ...
```

不推荐：

```python
def list_assets(**kwargs):
    ...
```

### 6.2 核心业务参数禁止放 metadata

不得将以下字段放入自由 JSON：

- 权威 ID
- 项目作用域
- 主状态
- 外键
- 版本号
- 幂等键
- 权限
- 数据分类
- Secret 引用

自由 JSON 只用于低约束扩展信息，并且必须有：

- Schema版本
- 最大尺寸
- 允许字段范围
- 序列化规则

---

## 7. 领域模型规范

### 7.1 聚合根和版本对象

聚合根保存：

- 稳定身份
- 当前版本引用
- 生命周期状态
- 审计字段
- 乐观锁版本

版本对象保存：

- 业务内容
- 版本号
- 内容指纹
- 创建信息

示例：

```text
TestAsset
  └── TestAssetVersion[]
```

### 7.2 版本不可变

版本对象不得原地修改业务内容。

禁止：

```python
asset_version.title = new_title
asset_version.updated_at = now
```

必须：

```python
new_version = TestAssetVersion(
    version_no=previous.version_no + 1,
    ...
)
```

### 7.3 事实源

EvieAi 事实源：

| 业务事实 | 唯一事实源 |
|---|---|
| 需求正文 | RequirementVersion |
| 测试资产正文 | TestAssetVersion |
| 当前需求版本 | Requirement.current_version |
| 当前资产版本 | TestAsset.current_version |
| 可执行脚本 | TestCaseVersion.script_code |
| 执行结果 | Execution / ExecutionStepResult |
| 证据 | Evidence |
| 配置 | Settings / 配置中心 |
| Secret | Credential reference |

不得在聚合根和版本表双写正文。

### 7.4 派生字段

派生字段必须满足：

- 可从事实源重算
- 有明确计算规则
- 有规则版本
- 不可反向覆盖事实源
- 失效时可识别

例如：

```text
coverage_score
quality_score
automation_eligibility
```

必须标识为派生结果。

---

## 8. ORM 模型规范

### 8.1 字段定义

每个字段必须明确：

- 类型
- 是否可空
- 默认值
- 长度
- 索引
- 唯一性
- 业务语义

禁止随意使用无限长字符串。

推荐：

```python
project_code = mapped_column(String(64), nullable=False, index=True)
```

### 8.2 时间字段

统一使用 UTC。

要求：

- 数据库存储 UTC
- API 返回 ISO 8601
- 不使用无时区本地时间
- 不在业务代码中散落 `datetime.now()`
- 使用统一 clock/provider

### 8.3 JSON 字段

JSON 不得承载核心关系和状态。

允许：

- 标签列表
- 扩展展示信息
- 低约束元数据

不允许：

- 外键
- 当前状态
- 权威 ID
- 资源绑定核心结构
- 版本关系

### 8.4 软删除

软删除使用：

```text
deleted_at
```

规则：

- 普通查询默认排除软删除记录
- 明确管理查询才允许包含
- 唯一约束与软删除冲突需明确设计
- 不得同时用 `status=deleted` 和 `deleted_at` 表达同一事实

### 8.5 乐观锁

聚合根应使用：

```text
row_version
```

更新规则：

```text
WHERE id = ? AND row_version = ?
```

成功后递增。

冲突必须返回稳定领域错误，不得静默覆盖。

---

## 9. Repository 规范

### 9.1 职责

Repository 负责：

- 查询
- 新增
- 持久化
- 锁定
- Flush
- 映射数据库异常

Repository 不负责：

- AI调用
- HTTP调用
- 业务状态机
- Prompt拼装
- Compiler
- Runner
- 资源解析
- 用户权限判断

### 9.2 方法命名

推荐：

```python
get_by_test_asset_id()
list_by_project_code()
add_version()
exists_source_identity()
lock_for_update()
```

禁止：

```python
do_save()
handle_data()
process_asset()
```

### 9.3 commit 责任

默认建议：

- Service 管理事务
- Repository 执行 `add/flush/query`
- Repository 不自行 commit

必须在项目中统一，不得部分 Repository 自动 commit，部分不 commit。

### 9.4 锁和并发

版本号生成等并发敏感逻辑必须使用：

- 行锁
- 数据库唯一约束
- 乐观锁
- 可重试冲突处理

不得只通过：

```python
max(version_no) + 1
```

然后无保护插入。

---

## 10. Service 规范

### 10.1 事务边界

Service 负责定义业务事务。

例如创建资产：

```text
BEGIN
  创建 TestAsset
  创建 TestAssetVersion
  创建 TestAssetSource
  更新 current_version
COMMIT
```

任一步失败必须全部回滚。

### 10.2 Command / Result

推荐：

```python
@dataclass(frozen=True)
class CreateTestAssetCommand:
    project_code: str
    title: str
    natural_steps: tuple[str, ...]
```

Result 应返回稳定领域数据，不直接暴露 ORM 实例给 API。

### 10.3 状态转换

状态转换必须调用 Policy 或领域方法。

禁止：

```python
asset.review_status = "pending"
```

推荐：

```python
asset_review_policy.reset_after_new_version(asset)
```

---

## 11. 状态机规范

### 11.1 枚举

所有状态使用 Enum。

推荐：

```python
class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
```

禁止散落字符串。

### 11.2 转换表

每个状态机应有明确转换表。

例如：

| 当前状态 | 事件 | 新状态 |
|---|---|---|
| approved | create_new_version | pending |
| succeeded | create_new_version | stale |
| blocked | create_new_version | not_started |
| processing | edit | forbidden |

### 11.3 非法转换

非法转换必须：

- 抛出结构化领域异常
- 提供稳定错误码
- 不修改任何持久化状态
- 记录必要审计信息

---

## 12. 幂等规范

### 12.1 必须明确的内容

每个创建型 API 必须说明：

- 幂等作用域
- 幂等键
- 规范化方式
- 重复请求响应
- 并发保护
- 失败重试行为

### 12.2 指纹

内容指纹必须基于规范化后的稳定字段。

例如：

```text
title
precondition
natural_steps
expected_result
priority
tags
```

规范化应明确：

- 去除首尾空白
- 换行统一
- Unicode标准化
- 标签排序
- JSON稳定序列化

### 12.3 幂等与重复区分

必须区分：

- 相同请求重试
- 精确内容重复
- 疑似语义重复
- 同资产恢复历史内容
- 同来源重复绑定

不得用一个 `duplicate_status` 处理全部场景。

---

## 13. 哈希规范

### 13.1 算法

默认使用 SHA-256。

不得使用：

- Python内置 `hash()`
- MD5承载安全或唯一身份
- 基于数据库自增PK生成跨环境身份哈希

### 13.2 Source Identity

Phase 0 Requirement 来源建议规范化为：

```text
requirement:<requirement_id>:<requirement_version_id>
```

再计算 SHA-256。

必须使用业务 ID，不使用数据库内部 PK。

---

## 14. ID 规范

### 14.1 生成位置

权威 ID 只能在统一 ID 模块生成。

不得：

- 在 Model 中重复生成
- 在 Router 中生成
- 在前端生成
- 由 AI 生成
- 在测试外手写固定生产格式ID

### 14.2 Phase 0 格式

```text
req_<uuid4hex32>
reqv_<uuid4hex32>
ta_<uuid4hex32>
tav_<uuid4hex32>
tas_<uuid4hex32>
```

### 14.3 Phase 1 用户稳定公共 ID

Phase 1 用户稳定公共 ID：

```text
usr_<uuid4hex32>
```

该 ID 只能由统一 ID 模块生成。`User.id` 是内部 Integer PK，不得作为 EvieAi actor 身份；
actor 规范形式固定为 `user:<user_public_id>`。

### 14.4 测试

至少覆盖：

- 前缀
- 长度
- 字符集
- 批量无重复
- 不使用短hex
- 不接受非法格式

---

## 15. Schema 和 API 契约

### 15.1 输入输出分离

创建、更新、读取 Schema 必须分离。

例如：

```text
TestAssetCreate
TestAssetUpdate
TestAssetRead
```

不得使用一个 Schema 同时承担全部场景。

### 15.2 禁止客户端控制字段

客户端不得直接设置：

- 内部业务 ID
- `current_version`
- 审计字段
- `row_version` 初始值
- 最终状态
- 内部错误字段
- Secret引用以外的凭证明文

### 15.3 Extra 字段

输入 Schema 应禁止未知字段。

推荐：

```python
model_config = ConfigDict(extra="forbid")
```

避免客户端偷偷传入机器字段。

### 15.4 API 稳定性

API 变更必须说明：

- 新增
- 兼容
- 废弃
- 删除计划
- 迁移方式

未经确认不得破坏已有接口。

---

## 16. 错误模型

### 16.1 结构

推荐错误结构：

```json
{
  "code": "EVIE_ASSET_VERSION_CONFLICT",
  "message": "Asset version conflict",
  "domain": "test_asset",
  "stage": "repository",
  "retryable": false,
  "trace_id": "...",
  "details": {}
}
```

### 16.2 错误码

错误码必须：

- 稳定
- 集中定义
- 不依赖自由文本
- 与HTTP状态码分离
- 不重复

### 16.3 异常映射

数据库异常必须映射为领域错误：

- UniqueViolation
- ForeignKeyViolation
- OptimisticLockConflict
- NotFound
- InvalidStateTransition

禁止直接把数据库异常暴露给客户端。

---

## 17. 日志规范

### 17.1 结构化字段

日志建议包含：

- `trace_id`
- `request_id`
- `project_code`
- `actor_id`
- 领域对象 ID
- operation
- status
- duration_ms
- error_code

### 17.2 日志级别

| 级别 | 用途 |
|---|---|
| DEBUG | 开发诊断，不含敏感内容 |
| INFO | 正常业务事件 |
| WARNING | 可恢复异常或降级 |
| ERROR | 当前操作失败 |
| CRITICAL | 系统级不可用 |

### 17.3 禁止内容

不得记录：

- Token
- Password
- Cookie
- Authorization
- Secret
- 完整需求正文
- 完整Prompt
- 客户敏感数据
- SQL参数中的敏感字段

---

## 18. 安全规范

### 18.1 Secret

Secret 只能保存引用。

禁止：

- 明文入库
- 明文日志
- 硬编码
- 写入 TestAsset
- 写入 TestCase
- 写入报告
- 写入 Prompt

### 18.2 数据分类

新增字段必须考虑：

- Public
- Internal
- Confidential
- Restricted

敏感字段必须定义：

- 是否加密
- 是否脱敏
- 保留周期
- 删除策略
- 审计要求

### 18.3 输入安全

所有外部输入必须校验：

- 类型
- 长度
- 格式
- 枚举
- 文件大小
- MIME
- 路径
- URL
- JSON深度

---

## 19. Migration 规范

### 19.1 基本要求

Migration 必须：

- 使用真实 Alembic head
- 明确 upgrade/downgrade
- 不猜 `down_revision`
- 不修改范围外旧表
- 不混入无关数据迁移
- 明确索引、唯一约束、外键
- 考虑目标数据库兼容性

### 19.2 命名

EvieAi Migration 文件使用：

```text
<revision>_evie_ai_<purpose>.py
```

### 19.3 数据迁移

Schema Migration 和 Data Migration 尽量拆分。

大数据迁移必须说明：

- 批次
- 锁
- 超时
- 回滚
- 重试
- 进度
- 审计

### 19.4 循环引用

存在循环外键时：

- 允许字段先为空
- 先建表
- 后补外键，或由Repository守护
- 文档必须说明一致性策略

---

## 20. 测试规范

### 20.1 测试层级

| 测试类型 | 目标 |
|---|---|
| 单元测试 | 纯函数、Policy、状态机 |
| 模型测试 | 字段、默认值、约束 |
| Schema测试 | 输入输出边界 |
| Repository测试 | 事务、回滚、并发、约束 |
| Integration测试 | DB、Migration、外部适配 |
| Architecture测试 | 导入方向和字段边界 |
| Regression测试 | 防止旧功能回归 |

### 20.2 必测场景

- 创建成功
- 输入非法
- 非法状态转换
- 唯一约束冲突
- 事务中途失败
- 回滚后无残留
- 并发冲突
- 软删除过滤
- 历史版本不可修改
- current_version归属校验
- 配置缺失
- Secret不泄露
- 错误码稳定

### 20.3 Fixture

Fixture 必须：

- 明确作用域
- 不依赖执行顺序
- 自动清理
- 不使用生产数据
- 不隐藏业务前置条件

### 20.4 Mock

Mock 只用于隔离外部依赖。

不得用 Mock 证明：

- 数据库唯一约束
- 真实事务回滚
- Migration正确性
- 并发一致性

---

## 21. 架构守卫

### 21.1 AST Import 守卫

至少检查：

- EvieAi资产域不导入旧Candidate链
- Repository不导入AI/Compiler/Runner
- Runner不导入自然语言解析
- Router不承担事务编排
- Model不导入Service

### 21.2 字段守卫

TestAsset相关Schema和ORM不得出现：

```text
action
target
value
selector
locator
structured_steps
steps_hint
compiler_ir
dsl
script_code
runner_steps
```

### 21.3 事实源守卫

自动测试应断言：

- requirements不含正文
- test_assets不含正文
- 版本表不含业务更新字段
- script_code只在TestCaseVersion
- current_version字段语义唯一

---

## 22. AI 调用规范

### 22.1 模型配置

模型名、参数、Prompt版本必须配置化。

不得：

- 在业务代码写死模型名
- 在多个地方重复Prompt
- 直接拼接未经版本管理的Prompt
- 将Secret放入Prompt

### 22.2 输出校验

AI输出必须经过：

- Schema校验
- 长度限制
- 字段白名单
- 安全检查
- 失败重试策略

生成侧输出只允许自然语言资产字段。

### 22.3 可观测性

记录：

- model/provider
- prompt_version
- parameters
- latency
- token usage
- cost
- fallback
- schema validation result

不得记录完整敏感Prompt或客户数据。

---

## 23. Compiler 规范

Compiler 只能存在于 Asset-to-Case 后半段。

输入必须是：

- Bound Execution Plan
- 已解析资源绑定
- 明确版本信息

输出必须是：

- TestCaseVersion
- script_code
- 编译诊断

Compiler不得：

- 直接读取自然语言TestAsset
- 自己查询任意资源表
- 修改TestAsset
- 在Runner运行时执行

---

## 24. Runner 规范

Runner只执行：

- `script_code`
- 运行时资源引用
- 明确环境配置

Runner不得：

- 重新解析自然语言
- 重新调用AI
- 重新编译
- 修改资产
- 推断缺失资源
- 静默使用默认账号或默认环境

Runner必须输出：

- Execution
- ExecutionStepResult
- Evidence
- CleanupResult
- 稳定错误码

---

## 25. 前端规范

### 25.1 事实源

前端不得维护与后端重复的业务事实。

例如：

- 状态值来自后端
- 权威ID来自后端
- current_version来自后端
- 权限来自后端

### 25.2 配置

API地址、Feature Flag、环境标识必须统一配置。

不得写死：

```javascript
const baseUrl = "http://localhost:8000"
```

### 25.3 状态管理

不得通过多个组件各自维护同一资产状态。

必须有统一数据获取和失效策略。

### 25.4 表单

表单字段必须与Schema一致。

不得提交：

- 内部ID
- 审计字段
- 机器字段
- 未知字段

---

## 26. 性能规范

### 26.1 查询

避免：

- N+1
- 无分页列表
- 无索引过滤
- 在Python中加载全表后过滤
- 大字段默认全量返回

### 26.2 分页

列表接口必须有分页。

推荐：

- 稳定排序
- 最大page_size
- 明确默认值
- 大规模数据优先cursor

### 26.3 批处理

批量任务必须：

- 分批
- 可重试
- 可观察
- 可中断
- 不在单事务内处理无限数据

---

## 27. 代码审查清单

每个 PR 至少检查：

### 架构

- 是否符合当前Phase边界
- 是否跨层调用
- 是否复制旧链逻辑
- 是否引入新的事实源

### 配置

- 是否有硬编码
- 是否重复默认值
- 是否新增配置未文档化
- 是否泄露Secret

### 数据

- 事务是否完整
- 约束是否充分
- current_version是否一致
- 版本是否不可变
- 软删除是否正确
- 并发是否安全

### API

- Schema是否显式
- 错误码是否稳定
- 是否暴露内部PK
- 是否兼容已有调用

### 测试

- 是否覆盖失败路径
- 是否覆盖回滚
- 是否覆盖唯一约束
- 是否运行必要回归测试
- 是否存在跳过或弱化断言

---

## 28. Git 和提交规范

### 28.1 提交原则

每个提交必须：

- 单一职责
- 可独立审查
- 可独立回滚
- 不混入无关改动

### 28.2 Scope

EvieAi 使用：

```text
docs(evie-ai)
feat(evie-ai)
fix(evie-ai)
test(evie-ai)
refactor(evie-ai)
```

### 28.3 禁止混合

不得在同一提交混入：

- 文档清理
- 依赖升级
- Migration
- 旧链修复
- EvieAi新功能
- 大范围格式化

---

## 29. 实施前输出模板

编码前必须输出：

```text
1. Git branch / HEAD / 工作区状态
2. 计划修改文件
3. 每个文件职责
4. 新增参数及来源
5. 新增配置及权威定义位置
6. 唯一事实源
7. 事务边界
8. 幂等和唯一性
9. 状态转换
10. 数据一致性
11. 测试计划
12. 明确不处理内容
13. 风险和待确认项
```

发现冲突时停止实施。

---

## 30. 实施后输出模板

实施完成后必须输出：

```text
1. 实际修改文件
2. 与计划偏差
3. 新增配置
4. 参数化清单
5. 数据库和Migration变化
6. 事务与回滚行为
7. 唯一约束和幂等规则
8. 状态转换
9. 运行测试和结果
10. 未运行测试和原因
11. 未解决风险
12. 后续建议
```

不得声称未实际验证的结果。

---

## 31. 例外管理

任何违反本文的例外必须：

1. 明确列出规则
2. 说明原因
3. 说明风险
4. 说明替代方案
5. 获得用户明确批准
6. 记录在ADR或当前实施文档
7. 定义清理或到期条件

不得以“临时实现”为理由绕过规则。

---

## 32. EvieAi Phase 0 特别约束

Phase 0 只允许：

- Requirement
- RequirementVersion
- TestAsset
- TestAssetVersion
- TestAssetSource
- ID扩展
- ORM
- Schema
- Repository
- Migration
- 架构守卫
- 测试
- 权威文档

Phase 0 不允许：

- AI生成
- Candidate迁移
- 完整Intake
- 语义去重
- Asset-to-Case
- ConversionAttempt
- Compiler
- Runner
- TestCase创建
- 前端页面
- 旧数据迁移
- 旧链删除

Phase 0 已确认：

- 使用 `TestProject.project_code`
- 不新增 `project_id/project_uuid`
- 不新增 `intent_id`
- TestAssetSource只支持Requirement来源
- 核心ID使用UUID4 hex32
- current_version由Repository事务维护
- 历史版本不可原地覆盖
- `content_checksum`不阻止恢复历史内容


## 历史代码兼容与技术债治理

### 适用规则

- 新文件：完全遵守当前规范。
- 新增代码：完全遵守当前规范。
- 修改代码：不得新增违规，并修复与当前修改直接相关的高风险问题。
- 未修改历史代码：登记到基线，按风险逐步治理。
- 冻结领域：只能修复，不得继续扩展。

### 高风险问题

以下问题不允许通过历史基线豁免：

- Secret泄露
- 跨项目或跨租户数据污染
- 数据丢失或不可逆覆盖
- 多表写入部分成功
- 静默异常和假成功
- 版本内容被原地覆盖
- current_version错误关联
- Runner重新解释自然语言
- EvieAi依赖旧Candidate业务链

### 基线管理

每条历史豁免必须记录：

- rule_id
- 文件路径
- 类或函数
- 风险等级
- 保留原因
- 替代方案
- 责任域
- 到期时间

禁止：

- 全文件、全目录无期限忽略
- 无原因的 noqa / nosec / type ignore
- 为通过CI降低规则级别
- 修复后继续保留基线项
- 用历史代码存在作为新增违规理由
