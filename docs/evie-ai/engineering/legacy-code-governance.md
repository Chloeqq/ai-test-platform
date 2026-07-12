# EvieAi 历史代码治理规范

日期：2026-07-12
状态：Authoritative
适用范围：EvieAi 建设期间的历史代码、旧业务链、历史工程违规、迁移适配、技术债基线和旧链退役

本文定义 EvieAi 建设期间对历史代码、旧业务链和历史工程违规的渐进治理规则。

本文不要求在单个任务中一次性重写全部历史代码，但禁止把历史违规模式复制到 EvieAi 新代码。

完整参考：

- `AGENTS.md`
- `docs/evie-ai/engineering/coding-standards.md`
- `docs/evie-ai/architecture/evie-ai-overview.md`
- `docs/evie-ai/architecture/natural-language-test-assets.md`
- `docs/evie-ai/architecture/target-capability-map.md`
- `docs/evie-ai/implementation/phase-traceability.md`
- `docs/evie-ai/migration/legacy-chain-freeze-list.md`

发生冲突时，优先级如下：

1. 用户当前任务中的明确确认
2. `AGENTS.md`
3. 当前阶段实施文档
4. EvieAi 架构专题
5. 本文
6. 旧文档
7. 旧代码现状

旧代码可以证明当前系统如何运行，但不能证明 EvieAi 应该如何设计。

---

## 1. 治理目标

历史代码治理的目标是：

- 新代码不继续产生技术债
- 高风险历史问题优先消除
- 普通历史问题有记录、有负责人、有退出计划
- 旧 Candidate、提前结构化和直接编译链不再扩展
- EvieAi 不依赖错误的旧业务边界
- 可复用技术能力通过适配层进入正确领域
- 旧链能够分阶段迁移、对账、切流和退役
- 治理过程不破坏现有生产能力
- 每次治理都可审查、可验证、可回滚

最终目标不是“立即重写全部旧代码”，而是：

```text
新代码零新增违规
P0 风险不得保留
相关 P1 随修改同步治理
P2 有计划持续减少
旧链不再扩展
EvieAi 不再依赖错误的旧业务主链
```

---

## 2. 基本原则

处理历史代码时必须遵循：

1. EvieAi 新代码必须完全遵守 `AGENTS.md` 和 `coding-standards.md`。
2. 未被当前任务触及的历史代码可以暂时保留，但不视为合规实现。
3. 修改历史代码时，新增和修改部分必须符合当前规范。
4. 与当前任务直接相关的高风险问题必须同步修复。
5. 与当前任务无关的问题必须登记，不得扩大当前提交。
6. 不得以“旧代码一直这样写”为理由复制违规模式。
7. 历史违规基线只允许减少，不允许无审批增加。
8. 大规模历史重构必须使用独立计划、独立测试和独立提交。
9. 技术组件可复用，不代表旧业务调用位置可复用。
10. 冻结旧链后，只允许修复，不允许继续增加产品能力。
11. 迁移前必须建立追踪、映射、对账和回滚方案。
12. 删除旧代码前必须证明无有效调用、无数据依赖和无回滚需求。

---

## 3. 适用对象

本文适用于：

- 旧 Candidate 主链
- selected_candidates
- Candidate Preview
- 保存所选候选
- TestPointPlan
- point 与 candidate 往返转换
- 生成阶段结构化
- 生成阶段提前编译
- Orchestrator 内部编译
- Web 层再次校验或再次编译
- 旧 TestPointAsset
- 旧编译入口
- 旧 Runner 接口
- 历史 Repository 和 Facade
- 历史硬编码
- 历史配置散落
- 历史无事务写入
- 历史错误处理问题
- 历史数据模型不一致
- 历史架构文档
- 历史测试和 Fixture
- 历史 Migration
- 历史依赖和本地调试产物

---

## 4. 历史代码处理模式

历史代码分为四种处理模式。

### 4.1 保留

适用于：

- 当前仍在生产使用
- 当前任务未触及
- 风险可接受
- 暂无迁移前置条件
- 已登记治理计划

保留不等于合规。

### 4.2 修复

适用于：

- 生产缺陷
- 安全问题
- 数据一致性问题
- 当前任务直接相关的 P1 问题
- 测试回归
- 可观测性缺失

修复必须保持最小范围。

### 4.3 适配

适用于：

- 旧技术能力仍有复用价值
- 旧业务接口不符合 EvieAi 领域边界
- 暂时不能直接替换底层实现

正确方式：

```text
EvieAi 公开接口
→ Adapter
→ 旧技术组件
```

错误方式：

```text
EvieAi Service
→ 导入旧模块私有函数
```

### 4.4 退役

适用于：

- 已无有效业务入口
- 新链已稳定替代
- 数据已迁移并对账
- 运行时调用为零
- 回滚窗口已结束
- 已获得用户明确批准

退役必须按计划执行，不能仅凭文件名含 `legacy` 就直接删除。

---

## 5. 风险等级

### 5.1 P0：不得豁免

以下问题发现后必须停止相关实施并优先处理：

- 明文密码、Token、Secret
- 固定生产地址或生产凭证
- 跨项目或跨租户数据污染
- 数据丢失或不可逆覆盖
- 多表写入部分成功
- 捕获异常后返回假成功
- 历史版本被原地覆盖
- `current_version` 指向错误聚合
- Migration 可能破坏或丢失数据
- Runner 重新解释自然语言资产
- EvieAi 新模块直接依赖 Candidate 主链
- EvieAi 生成侧直接调用 Compiler 或 Runner
- TestAsset 保存 `script_code` 或机器执行字段
- 明文凭证进入日志、报告、Prompt 或 Evidence
- 删除旧数据但没有映射、对账和回滚方案
- 未隔离工作区改动就执行破坏性 Git 操作

P0 问题不得进入历史豁免基线。

### 5.2 P1：修改到相关逻辑时必须治理

包括：

- 固定 `project_code`
- 固定环境、页面、元素或资源 ID
- 模型、Prompt、超时和阈值硬编码
- Repository 承担业务编排
- Router 直接进行复杂 ORM 写入
- 状态使用散落字符串
- 重复实现相同业务规则
- 缺少数据库唯一约束
- 缺少事务回滚
- 缺少幂等保护
- 多处定义相同默认值
- 错误码不稳定
- 捕获通用异常但未映射领域错误
- 软删除查询不一致
- 测试只覆盖 happy path
- 配置读取散落在业务代码
- 旧代码直接暴露内部数据库 PK
- 关键查询存在明显 N+1 或无分页风险

修改相关函数、类、事务或接口时，必须同步修复直接相关的 P1 问题。

### 5.3 P2：进入专项重构计划

包括：

- 文件过大
- 命名不一致
- 普通代码重复
- 低风险分层问题
- 注释和文档不足
- 格式与风格历史债务
- 非关键性能优化
- 辅助模块职责模糊
- 普通类型注解不足
- 低风险日志字段不统一

P2 问题不得混入普通功能提交，应安排独立重构任务。

---

## 6. 当前旧链冻结范围

以下旧实现处于冻结状态：

- Candidate Preview
- selected_candidates
- 保存所选候选
- 只有候选被选中才分配资产 ID
- Candidate 作为持久化业务实体
- TestPointPlan
- point 与 candidate 往返转换
- resolve_explicit_step
- structured_steps_from_candidate
- 生成阶段结构化
- Behavior Registry 提前介入
- Direct compile
- Orchestrator 内部编译
- Web 层再次编译
- 多个 point builder
- 多个 Compiler 入口
- 生成侧调用质量门
- 资产保存时提前结构化
- Runner 重新理解自然语言
- Runner 运行时重新编译

旧链允许：

- 生产故障修复
- 安全修复
- 数据一致性修复
- 必要兼容修复
- 增加迁移观测
- 增加审计
- 增加受控适配层
- 增加回归测试
- 增加切流开关

旧链禁止：

- 增加新产品功能
- 增加新 Candidate 交互
- 增加新直接编译入口
- 增加新的保存所选候选流程
- 被 EvieAi 新模块直接依赖
- 复制到 EvieAi 新领域
- 继续扩展旧 TestPointAsset 作为未来事实源
- 新增结构化步骤字段到自然语言资产
- 新增默认项目或默认环境回退

---

## 7. 新代码零违规规则

以下目录从创建开始必须零新增违规：

```text
apps/web-ui-service/app/models/evie_ai/**
apps/web-ui-service/app/schemas/evie_ai/**
apps/web-ui-service/app/repositories/evie_ai/**
apps/web-ui-service/app/services/evie_ai/**
apps/web-ui-service/app/policies/evie_ai/**
apps/web-ui-service/app/adapters/evie_ai/**
apps/web-ui-service/tests/**/evie_ai/**
docs/evie-ai/**
```

不得为 EvieAi 新目录设置历史豁免。

必须保证：

- 无固定 `project_code`
- 无固定环境
- 无固定模型名
- 无 Secret
- 无 Candidate 依赖
- 无提前 Compiler
- 无 Runner 依赖
- 无机器字段进入 TestAsset
- 无并行 ID 系统
- 无正文双写
- 无版本原地覆盖
- 无静默异常
- 无无事务多表写入

---

## 8. 修改历史代码的规则

修改历史代码时：

- 新增代码必须合规
- 修改部分不得新增硬编码
- 不得新增跨层依赖
- 不得新增静默异常
- 不得复制旧私有函数
- 不得扩大旧 Candidate 链
- 不得增加新的直接编译入口
- 不得把旧 structured_steps 写入 TestAsset
- 不得把旧代码现状当作目标架构依据
- 不得顺手大范围重构无关逻辑
- 不得删除未验证的历史兼容路径
- 不得用旧 Fixture 证明新模型正确
- 不得通过降低测试断言掩盖回归

如果无法判断某个问题属于“当前任务必要修复”还是“范围外重构”，必须先报告，不得自行扩大范围。

---

## 9. 技术能力复用规则

旧技术组件可以评估复用，例如：

- SQLAlchemy 基础设施
- Alembic
- BaseRepository
- Settings
- TestProject
- RequirementDocument 上传能力
- Page Object 技术能力
- Behavior Registry 技术能力
- ContractValidator 技术能力
- Compiler 技术能力
- Runner
- Evidence
- Report
- Pytest Fixture
- 可观测性基础设施

复用要求：

1. 先确认技术职责与业务职责。
2. 只复用技术能力，不继承错误调用位置。
3. 使用公开接口或 Adapter。
4. 不导入私有函数。
5. 不让 EvieAi 资产域依赖 Compiler 或 Runner。
6. 不让生成侧依赖页面对象解析。
7. 不把旧状态模型复制到新领域。
8. 对复用组件增加契约测试。
9. 对旧组件异常进行领域错误映射。
10. 明确未来替换成本。

推荐：

```text
EvieAi Service
→ Port / Interface
→ Legacy Adapter
→ 旧技术组件
```

禁止：

```text
EvieAi Repository
→ 旧 Workbench Facade
```

---

## 10. 历史违规基线

历史违规基线建议存放于：

```text
tools/quality/legacy-violations.json
```

每条记录至少包含：

```text
rule_id
path
symbol
risk
reason
replacement
owner
created_at
expires_at
```

建议扩展字段：

```text
status
detected_by
issue_id
last_verified_at
notes
```

示例：

```json
{
  "rule_id": "EVIE-HARDCODED-PROJECT",
  "path": "apps/web-ui-service/app/api/workbench/example.py",
  "symbol": "build_legacy_request",
  "risk": "P1",
  "reason": "Legacy WorkBench implementation",
  "replacement": "EvieAi project scope service",
  "owner": "legacy-workbench",
  "status": "accepted_temporarily",
  "created_at": "2026-07-12",
  "expires_at": "2026-10-31"
}
```

基线规则：

- 只允许减少，不允许自动增加
- 不允许整个仓库、目录或模块永久忽略
- 不允许无原因的 `noqa`
- 不允许无原因的 `nosec`
- 不允许无原因的 `type: ignore`
- 修复后必须删除对应基线项
- 不能只比较违规总数
- 应使用 `rule_id + path + symbol` 识别具体违规
- 到期项必须重新评估
- P0 不得进入基线
- 新 EvieAi 目录不得进入基线
- 基线变更必须单独审查

---

## 11. CI 治理策略

CI 分为三层。

### 11.1 EvieAi 新目录

要求：

- 零违规
- 发现违规直接失败
- 不设置历史豁免
- 架构守卫必须运行
- Schema 和 ORM 边界必须运行
- 配置和 Secret 检查必须运行

### 11.2 已修改历史文件

要求：

- 阻止新增违规
- P0 必须修复
- 直接相关 P1 必须治理
- 未修改历史问题可以暂时保留
- 修改旧模块时运行相关回归测试
- 修改事务时运行真实数据库测试

### 11.3 全仓扫描

目标：

- 输出历史违规趋势
- 不因普通 P1/P2 一次性阻塞全部提交
- 违规数量和风险持续下降
- 不允许新增未登记基线项
- 生成按领域、风险和到期时间的报告

建议指标：

```text
P0 count
P1 count
P2 count
new violations
resolved violations
expired exceptions
violations by domain
violations by owner
```

---

## 12. 硬编码治理

历史硬编码需要分类处理。

### 12.1 必须立即移除

- Secret
- 生产地址
- 生产凭证
- 默认项目导致跨项目污染
- 默认环境导致错误执行
- 固定用户导致权限绕过

### 12.2 修改时治理

- 模型名
- Prompt版本
- 超时
- 重试次数
- 并发数
- 质量阈值
- 固定资源ID
- 固定页面对象ID
- 固定Runner类型

### 12.3 允许集中保留

- 稳定ID前缀
- 协议常量
- Schema版本
- 已确认状态枚举

允许保留的常量必须集中定义，不能散落。

---

## 13. 数据一致性治理

历史代码涉及以下场景时，必须优先治理：

- 创建主实体和版本不在同一事务
- 多次 commit 导致部分成功
- `current_version` 手工拼接
- “先查询再插入”但无数据库唯一约束
- 捕获数据库异常后继续执行
- 软删除记录仍参与普通查询
- 版本号通过无锁 `max + 1` 生成
- 重试产生重复记录
- 外键关系只靠前端保证
- 历史版本可被普通更新接口修改

治理要求：

- 明确事务边界
- 明确 commit 责任
- 明确 rollback 行为
- 增加数据库约束
- 增加并发测试
- 增加失败回滚测试
- 增加结构化领域错误

---

## 14. 测试治理

历史代码治理必须有与风险匹配的测试。

### P0 修复

必须包含：

- 失败复现测试
- 回归测试
- 真实事务或集成测试
- 必要的安全检查

### P1 修复

至少包含：

- 单元测试
- 状态转换测试
- 错误映射测试
- 配置测试
- 受影响接口回归

### P2 重构

必须证明：

- 行为不变
- 公共接口不变
- 关键回归测试通过
- 性能未明显下降

不得：

- 删除断言使测试通过
- 批量更新 Snapshot 掩盖变化
- 只依赖 Mock 证明数据库一致性
- 跳过失败测试而不记录
- 修改生产逻辑适配错误 Fixture
- 把旧测试通过当作新架构正确证据

---

## 15. 迁移治理

旧链迁移建议分为以下阶段：

### 15.1 盘点

- 入口
- 调用方
- 数据表
- ID
- 状态
- 事件
- API
- 前端交互
- 测试
- 运维依赖

### 15.2 冻结

- 禁止新增产品能力
- 禁止新增入口
- 禁止新增持久化模型
- 禁止新增直接编译路径
- 只允许修复和观测

### 15.3 映射

建立：

- 旧 ID → 新 ID
- 旧实体 → 新实体
- 旧状态 → 新状态
- 旧来源 → TestAssetSource
- 旧脚本 → TestCaseVersion
- 旧证据 → Evidence

### 15.4 影子验证

- 双读
- 双写或事件镜像，需单独批准
- 结果对比
- 数据对账
- 性能对比
- 错误率对比

### 15.5 切流

- Feature Flag
- 分批项目
- 可回滚
- 监控
- 观察窗口
- 失败降级

### 15.6 退役

- 无调用
- 无数据依赖
- 无回滚需求
- 文档更新
- 索引更新
- 用户批准
- 删除旧代码
- 删除旧配置
- 删除旧表需单独 Migration

---

## 16. 旧数据迁移规则

旧数据迁移不得：

- 把 Candidate 迁移成新持久化主实体
- 把 structured_steps 写入 TestAssetVersion
- 把旧 script_code 写入 TestAsset
- 丢失原来源
- 丢失旧 ID 映射
- 丢失版本历史
- 未对账就删除旧数据
- 在普通 Schema Migration 中混入大规模数据迁移

正确映射示例：

```text
旧自然语言测试点
→ TestAsset / TestAssetVersion

旧来源信息
→ TestAssetSource

旧可执行脚本
→ TestCase / TestCaseVersion

旧执行记录
→ Execution / Evidence
```

迁移必须保留：

- MigrationRun
- LegacyMapping
- MigrationBatch
- MigrationError
- ReconciliationResult
- CutoverPlan
- RollbackPlan

---

## 17. 文档治理

旧文档分为：

### 17.1 当前权威

只允许存在于：

```text
AGENTS.md
docs/evie-ai/**
```

### 17.2 历史归档

应移动到：

```text
docs/archive/**
```

并明确：

- 原始日期
- 原始路径
- 归档原因
- 是否被新文档替代
- 不再作为目标架构依据

### 17.3 禁止事项

不得：

- 删除旧文档但不保留历史证据
- 在两个目录保留两份权威版本
- 让旧 README 继续指向旧架构
- 在普通功能提交中大规模移动文档
- 把新架构内容写入旧产品命名路径

---

## 18. Git 和提交规则

历史治理提交必须：

- 单一职责
- 可独立审查
- 可独立回滚
- 有回归测试
- 不混入新功能
- 不混入依赖升级
- 不混入架构改写
- 不顺便格式化整个仓库
- 不覆盖用户未提交改动

建议提交：

```text
fix(legacy): remove hardcoded project scope
fix(legacy): make workbench asset save transactional
refactor(legacy): isolate candidate compiler adapter
test(legacy): cover workbench transaction rollback
docs(evie-ai): archive legacy generation documents
```

禁止使用模糊提交：

```text
fix stuff
cleanup
refactor all
update files
```

---

## 19. 例外管理

任何历史豁免必须：

1. 明确规则
2. 明确文件和 symbol
3. 明确风险等级
4. 说明保留原因
5. 说明替代方案
6. 指定 owner
7. 指定到期时间
8. 获得明确批准
9. 进入机器可读基线
10. 到期后重新评估

不得使用：

- 永久豁免
- 整个目录忽略
- 无 owner 豁免
- 无期限豁免
- 无理由的 lint ignore
- P0 豁免
- EvieAi 新目录豁免

---

## 20. 旧链退出条件

旧模块只有满足以下条件后才能删除：

- 已无有效业务入口
- 已无运行时调用
- 已无定时任务
- 已无事件消费者
- 已无数据写入
- 新链已完成验证
- 数据迁移已完成
- 新旧结果已对账
- 回滚方案已确认
- 观察期已结束
- 文档和索引已更新
- 监控未发现异常
- 用户明确批准删除

删除后还必须：

- 删除无效 Feature Flag
- 删除无效配置
- 删除无效测试
- 删除无效文档入口
- 更新架构守卫
- 更新迁移记录
- 保留必要审计信息

---

## 21. 治理任务实施前报告

实施前必须输出：

1. 当前 Git branch、HEAD 和工作区状态
2. 涉及的历史模块
3. 当前有效调用方
4. 风险等级
5. 是否属于当前任务必要修复
6. 计划修改文件
7. 事务和数据风险
8. 兼容性风险
9. 测试计划
10. 回滚方式
11. 明确不处理的历史问题
12. 是否修改基线

发现 P0、范围冲突或无法安全隔离的工作区改动时，必须停止并报告。

---

## 22. 治理任务实施后报告

实施完成后必须输出：

1. 实际修改文件
2. 修复的规则和风险等级
3. 是否减少历史基线项
4. 是否新增 Adapter
5. 是否改变公共接口
6. 数据和事务影响
7. 运行的测试及结果
8. 未运行测试及原因
9. 兼容性验证
10. 未解决风险
11. 后续退出计划
12. 是否可以进入下一迁移阶段

不得声称旧链已退役，除非退出条件全部满足。

---

## 23. Phase 0 特别规则

EvieAi Phase 0 期间：

允许：

- 冻结旧链
- 增加架构守卫
- 修复阻塞 Phase 0 的 P0 问题
- 隔离旧代码改动
- 复用 SQLAlchemy、Alembic、BaseRepository 等基础设施
- 建立后续迁移清单

不允许：

- 迁移 Candidate 数据
- 删除旧 Candidate 链
- 修改旧 Runner
- 修改旧 Compiler 主链
- 实施完整 Intake
- 实施 Asset-to-Case
- 实施 TestCase
- 为后续迁移提前增加大量占位字段
- 把旧结构化步骤带入 TestAsset
- 顺便重构整个 Workbench

Phase 0 的目标是建立新领域基线，不是完成旧平台全面迁移。

---

## 24. 治理度量

建议持续记录：

```text
P0 remaining
P1 remaining
P2 remaining
new violations
resolved violations
expired exceptions
legacy modules frozen
legacy modules adapted
legacy modules migrated
legacy modules removed
test coverage for modified legacy code
transaction rollback coverage
```

趋势目标：

- P0 始终为 0
- 新增违规始终为 0
- P1 持续下降
- P2 按计划下降
- 冻结模块不再增加产品代码
- EvieAi 对旧业务私有函数依赖始终为 0

---

## 25. 最终标准

历史代码治理完成的判断标准不是“旧文件全部删除”，而是：

```text
EvieAi 新代码完全遵守当前架构和工程规范
旧链不再扩展
高风险旧问题已清零
新旧事实源边界清晰
迁移数据可对账
旧技术能力通过适配层受控复用
运行时已切换到新链
旧链无有效调用
退役过程可审计、可验证、可回滚
```

任何历史问题都不能成为 EvieAi 新代码继续违反规范的理由。
