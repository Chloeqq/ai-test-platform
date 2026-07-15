# EvieAi Phase 1 自然语言测试资产生命周期只读规格预检报告

日期：2026-07-14
任务类型：只读规格预检
状态：待人工签字，不构成实施授权
审计基线：`dev@bdedc7e0248f0e1ce1464d2a80def5fd3c968591`

> 本文记录实施前只读盘点结果。文中的“建议”不等于已批准架构决策；涉及物理模型、事务合同、API 合同和 Migration 的待定项，必须获得人工签字后才能进入正式实施计划。

> 后续状态（2026-07-15）：用户已明确批准 D-01～D-14 与 A-01～A-11，P-01～P-09 已闭合。正式权威口径已迁移到
> `phase-1-natural-language-asset-lifecycle-specification.md`、对应实施计划和 ADR-0001。
> 本文继续作为历史预检证据，不再作为当前决策状态来源。C-01 已通过 PR #4 合并并复验。

## 1. 执行基线

- 仓库根目录：`/Users/bettyhuang/PycharmProjects/ai-test-platform`
- 当前分支：`dev`
- 当前 HEAD：`bdedc7e0248f0e1ce1464d2a80def5fd3c968591`
- `bdedc7e` 是否为当前 HEAD 祖先：是，退出码 `0`
- 代码相关工作区状态：clean
- Phase 0 是否已合并：是
- 确定性 baseline 是否已合并：是
- Alembic heads：`20260713_121000 (head)`
- Alembic current：`20260713_120000`
- 一致性：本地数据库落后代码 head 一个 revision；本次仅记录，未升级
- Phase 1 Migration 父 revision 候选：`20260713_121000`
- 实际加载的规则文件：仅根目录 `AGENTS.md`
- 子目录 `AGENTS.md`：未发现
- `AGENTS.override.md`：未发现
- 专门的 Phase 1 实施文档：未发现；Phase 1 规则目前分布在阶段追踪矩阵和架构专题中

存在一个经用户确认忽略的本地私人未跟踪文件，本任务未读取、修改或提交该文件。

## 2. 已读取的权威文档

| 文件 | 权威级别 | 主要约束 | 是否存在歧义 |
|---|---|---|---|
| `AGENTS.md:1-850` | 最高硬约束 | 自然语言资产边界、事务、不可变版本、幂等、状态机、API、Migration 和架构守卫 | 无 |
| `docs/evie-ai/ARCHITECTURE_BASELINE.md:1-96` | Frozen baseline | 冻结主链、事实源和阶段边界，见 33–49 行 | “当前阶段仍为 Phase 0”，见 86–94 行，已滞后 |
| `docs/evie-ai/README.md:1-49` | 权威入口 | 文档事实源、命名、旧链归档 | 无 |
| `docs/evie-ai/architecture/evie-ai-overview.md:1-340` | Authoritative | 七领域、统一 Intake、唯一转换入口、事实源 | 无 |
| `docs/evie-ai/architecture/natural-language-test-assets.md:99-1135` | Authoritative | TestAsset、版本、来源、Intake、重复、事务完整定义 | 部分物理表尚未定案 |
| `docs/evie-ai/architecture/target-capability-map.md:336-375` | Authoritative target | Phase 0/1 能力范围和长期目标 | 不自动决定当前物理实现 |
| `docs/evie-ai/implementation/phase-0-domain-model.md:278-786` | 已批准 Phase 0 规则 | 五表、current_version、状态迁移、Requirement-only 来源 | 无 |
| `docs/evie-ai/implementation/phase-traceability.md:124-442` | 阶段权威矩阵 | Phase 1 Intake、版本、审核、幂等、重复、删除恢复、审计 | 物理实现待签字 |
| `docs/evie-ai/engineering/coding-standards.md:1-330` | Authoritative engineering | 分层、事务、错误、配置、测试 | 无 |
| `docs/evie-ai/engineering/legacy-code-governance.md:1-100` | Authoritative governance | 旧代码只作证据，旧违规不得复制 | 无 |
| `docs/evie-ai/migration/legacy-chain-freeze-list.md:1-63` | 冻结清单 | Candidate、structurer、提前编译不得进入新主链 | 无 |
| `docs/engineering/alembic-deterministic-baseline-plan.md:70-209` | 已批准数据库设计 | 冻结 121000、静态 bootstrap、受管库增量升级 | 实现存在 Phase 1 向前兼容缺口 |

## 3. 已确认规则

| 主题 | 已确认规则 | 权威来源 | Phase 0 实现状态 |
|---|---|---|---|
| 自然语言边界 | TestAsset 表达“测什么”，不保存机器字段 | `AGENTS.md:50-83` | 已满足 |
| 唯一 Intake | 所有入口进入 `TestAssetIntakeService` | `natural-language-test-assets.md:174-186` | 尚未实施 |
| Candidate 退出 | 新资产主链不得依赖 Candidate/Preview/selected_candidates | `AGENTS.md:146-165` | EvieAi 包已守卫；旧链仍保留 |
| 版本不可变 | 编辑创建新版本，历史版本不得原地覆盖 | `natural-language-test-assets.md:333-361` | 表结构满足；尚无生命周期 Service |
| 多来源 | TestAsset 1:N TestAssetSource；编辑不覆盖来源 | `natural-language-test-assets.md:365-414` | 1:N 已具备；仅 Requirement 来源 |
| Repository 边界 | Repository 只 add/flush/query，不 commit/rollback | `AGENTS.md:403-429` | 已满足 |
| current_version | 版本必须属于聚合，多表同事务维护 | `phase-0-domain-model.md:466-512` | Repository 已校验归属和 row_version |
| 状态迁移 | 新版本重置审核状态并按批准规则迁移转换状态 | `phase-0-domain-model.md:499-509` | 常量存在；生命周期编排未实现 |
| 审核历史 | Phase 1 必须有不可变审核记录 | `phase-traceability.md:133-144,279` | 尚未实施 |
| 幂等与重复 | 幂等、精确重复、语义重复、历史恢复必须分离 | `natural-language-test-assets.md:487-521` | 尚未实施 |
| 软删除 | 聚合使用 `deleted_at`，普通查询隐藏 | `phase-0-domain-model.md:318` | 字段及默认隐藏查询已实现 |
| 低质量入库 | 质量低、存在歧义或暂不可执行不能阻止入库 | `natural-language-test-assets.md:456-483` | Schema 允许空自然语言内容 |
| review/conversion | 两个状态维度相互独立 | `ARCHITECTURE_BASELINE.md:45-47` | 已分列并有 Check Constraint |
| 确定性数据库 | baseline 保持 121000，Phase 1 使用新增量 Migration | `alembic-deterministic-baseline-plan.md:123-167` | baseline 已合并 |

## 4. Phase 0 当前实现约束

| 实现项 | 当前状态 | 对 Phase 1 的影响 |
|---|---|---|
| 公共 ID | 五类完整 UUID4 hex ID 已实现，见 `app/core/id_gen.py:28-93` | 新表若需 review/audit/idempotency 公共 ID，必须另行批准前缀 |
| TestAsset | 聚合状态、current_version、row_version、deleted_at 已有，见 `app/models/evie_ai/test_asset.py:28-84` | 可扩展生命周期，不应保存正文 |
| TestAssetVersion | 自然语言正文、非唯一 checksum、不可变字段形态，见 `test_asset.py:87-132` | 编辑必须新增记录 |
| TestAssetSource | Requirement 三个强 FK/唯一来源 hash，见 `test_asset.py:135-187` | Manual 来源需要数据保留式演进 |
| Repository | add/flush/query、归属校验、乐观锁；无 commit/rollback，见 `test_asset_repository.py:24-159` | 可作为低层持久化基础 |
| 删除查询 | 普通 get/list 隐藏 deleted，见 `test_asset_repository.py:54-115` | 需新增显式 include_deleted/恢复访问 |
| 不可变守卫 | Schema/结构测试存在，但数据库未禁止直接 UPDATE 历史版本 | 生命周期 Service、Repository API 和测试必须继续封闭更新路径 |
| Schema | `extra=forbid`，机器字段守卫存在，见 `test_evie_ai_architecture_boundaries.py:92-116` | Phase 1 Schema 可继续复用 |
| 审核记录 | 无 EvieAi 审核历史表 | Phase 1 必须新增 |
| 幂等 | 无 EvieAi 幂等记录 | Phase 1 必须新增 |
| 通用审计 | 无可直接复用的 EvieAi 审计模型 | 需要签字物理模型 |
| API/Service | 无 EvieAi Router、Intake 或生命周期 Service | Phase 1 核心实施内容 |
| 鉴权 | 有 JWT 用户鉴权，但未发现 EvieAi 项目级授权 | API 前需明确 project scope |
| 分页 | 存在通用 offset/cursor 工具，见 `app/core/pagination.py:17-240` | 技术可复用，合同仍需签字 |
| 架构守卫 | 已覆盖禁用旧链导入、机器字段、事实源和约束 | Phase 1 新目录必须加入扫描范围 |

## 5. 文档、代码和 Phase 1 目标冲突

| 编号 | 权威文档定义 | 当前代码 | Phase 1 目标 | 是否阻塞 |
|---|---|---|---|---|
| C-01 | 冻结 baseline 后继续执行增量 Migration | 受管库 revision ≥121000 时仍执行全库 fingerprint 等值检查；fingerprint 枚举全部表 | Phase 1 新表会使健康检查误判 schema drift | **阻塞 Phase 1 Migration/部署** |
| C-02 | 缺少配置不得静默使用固定项目 | `ensure_project_active_for_write()` 调用旧 `ensure_project_seed()`；后者创建固定默认项目并 commit | 新 Intake 必须验证显式 project_code | **阻塞直接复用该 Service** |
| C-03 | 不得记录未经脱敏的需求/自然语言正文 | 全局中间件读取并记录 JSON body preview，见 `app/main.py:136-158` | POST/编辑 API 将携带自然语言正文 | **阻塞 Phase 1 API 上线** |
| C-04 | 当前阶段由当前 Phase 文档定义 | 架构基线仍声明“当前阶段 Phase 0”，见 `ARCHITECTURE_BASELINE.md:86-94` | 进入 Phase 1 | 阻塞正式实施文档定版，不阻塞本次预检 |
| C-05 | API 必须使用稳定结构化错误 | 当前全局 HTTPException 主要返回自由 `detail`，见 `app/main.py:196-249` | 幂等、重复、乐观锁、状态机需稳定错误码 | 阻塞 Phase 1 API 合同定版 |

Requirement-only 来源、尚未实现 Intake/审核/幂等，以及本地 DB current 落后 head，属于阶段状态或待实施内容，不属于架构冲突。

## 6. 必须人工签字的设计项

### D-01：统一 Intake 的落地边界

- 分类：A（唯一入口）+ B（物理事务边界）
- 已确认规则：所有生产入口统一进入 `TestAssetIntakeService`；Adapter 不自行写聚合。
- 待决定内容：是否引入独立 Unit of Work、fixture/迁移工具绕过范围、入口渠道存储位置。
- 权威依据：`natural-language-test-assets.md:174-186`
- 当前实现：只有低层 Repository；`get_db()` 只 yield/close，不控制事务。
- 可选方案：Service 直接管理 Session 事务；或轻量 EvieAi Unit of Work。
- 建议：唯一 Intake 接收类型化 command；API/手工/未来 AI 只做 Adapter。Repository 保留给 Service、受控迁移和测试 factory；业务入口不得绕过。
- 建议依据：符合唯一入口和多表原子性，且避免复制旧 Facade。
- 影响范围：Service、事务、Adapter、测试。
- 是否阻塞 ORM：否
- 是否阻塞 Migration：否
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-02：TestAssetSource 多来源物理模型

- 分类：B
- 已确认规则：TestAsset 可有多个来源；已有 Requirement 来源必须无损保留；渠道不自动等于来源类型。
- 待决定内容：单表、多表继承或平行来源表。
- 权威依据：`natural-language-test-assets.md:365-414`
- 当前实现：Requirement FK 全部非空。
- 可选方案：A 单表 nullable 字段 + Check；B 通用来源主表 + Requirement 子表；C 保留当前表并新增 Manual 来源表。
- 建议：方案 B。主表保留 asset、source type、identity hash 和审计字段；Requirement 关联进入专用子表。Manual 来源由主表表达，入口渠道另存审计/幂等信息。
- 建议依据：长期扩展性和 FK 完整性最好，不依赖大量 nullable 字段。
- 影响范围：ORM、Schema、Repository、Migration、查询、Intake。
- 是否阻塞 ORM：是
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-03：创建资产原子事务

- 分类：A（原子性）+ B（字段合同）
- 已确认规则：Asset、Version、Source、current pointer 必须同事务；失败全部回滚。
- 待决定内容：最小必填字段、asset_code 分配、初始审核记录、幂等记录和审计事件是否同事务。
- 当前实现：Schema 允许空 title/steps/expected；asset_code 由请求传入。
- 可选方案：客户端提供 asset_code；后端生成；或项目策略生成。
- 建议：后端生成公共 ID；asset_code 的权威来源需签字。初始 version_no=1、review=pending、conversion=not_started、row_version=1。幂等 claim、聚合、来源、审计必须处于同一事务。
- 建议依据：防止客户端控制权威身份和部分成功。
- 影响范围：Schema、Policy、Service、ID、事务测试。
- 是否阻塞 ORM：视 asset_code 决策
- 是否阻塞 Migration：视新增记录表
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-04：幂等模型

- 分类：B
- 已确认规则：幂等 key 与 content checksum 不同。
- 待决定内容：key 位置、作用域、冲突语义、保留期、失败重试、覆盖的操作。
- 当前实现：无 IdempotencyRecord。
- 可选方案：HTTP Header；请求字段；两者兼容。
- 建议：HTTP `Idempotency-Key` 作为协议入口，转入类型化 command。唯一范围建议为 `(project_code, operation_type, actor/client_id, key)`；保存 request fingerprint 和资源引用，不保存完整自然语言响应。相同 key/同请求返回原结果；不同请求返回 409；失败事务不占用成功 key。
- 建议依据：可支持 API、UI 和未来 Producer，且不与内容去重混淆。
- 影响范围：新表、Policy、Service、API、清理配置。
- 是否阻塞 ORM：是
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-05：精确重复策略

- 分类：B
- 已确认规则：由 Intake Policy 确定性处理；与质量、语义重复、幂等分离。
- 待决定内容：检测范围、hash 字段、规范化、删除资产处理和结果语义。
- 当前实现：`content_checksum` 只有普通索引，不能跨资产防止并发重复。
- 可选方案：拒绝、返回已有、复用并增加来源、创建重复关系、仅记录。
- 建议：作用域先限定项目内有效资产；规范化 title/precondition/steps/expected/priority/排序后 tags，使用 Unicode NFC、统一换行和 SHA-256；source 不进入内容 hash。建议“返回/复用已有资产并增加真实来源”。已删除匹配不得静默恢复。
- 建议依据：最大化资产复用，同时保留多来源事实。
- 影响范围：Policy、可能的唯一 claim 表、Intake、并发测试。
- 是否阻塞 ORM：是
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-06：编辑与版本生命周期

- 分类：A（不可变和状态迁移）+ B（操作细节）
- 已确认规则：编辑创建新版本；review 重置 pending；conversion 按批准规则迁移；processing 禁止编辑。
- 待决定内容：空修改、编辑 rejected 资产、编辑原因、版本号并发分配、历史恢复方式。
- 当前实现：唯一版本号约束、current_version ownership 和 row_version 已有。
- 可选方案：历史恢复直接切指针；复制历史内容创建新版本。
- 建议：复制历史内容创建新版本，保持时间线单向增长；相同当前内容不创建版本；资产行锁/row_version 与数据库唯一约束共同保护 version_no。
- 建议依据：符合版本不可变和审计可解释性。
- 影响范围：Lifecycle Service、Policy、Repository、审计。
- 是否阻塞 ORM：编辑原因若需字段则是
- 是否阻塞 Migration：视审计模型
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-07：审核记录物理模型

- 分类：A（必须有历史）+ B（表结构）
- 已确认规则：审核记录必须不可变；聚合 review_status 只表示当前状态。
- 待决定内容：表名、关联版本、允许转换、重复审核、撤销方式和公共 ID。
- 当前实现：无 EvieAi 审核表；旧 `WorkbenchReviewDecision` 可更新且绑定 run/page，不能作为新事实源。
- 可选方案：只绑 Asset；只绑 Version；同时绑 Asset 和具体 Version。
- 建议：不可变 `AssetReviewRecord` 同时绑定 TestAsset 和被审核的 TestAssetVersion；记录 from/to status、reviewer、时间、comment/reason、request/trace。撤销通过新增反向事件，不更新旧记录。
- 建议依据：审核结论必须明确对应内容版本。
- 影响范围：新表、状态 Policy、Service、API、查询。
- 是否阻塞 ORM：是
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-08：软删除与恢复

- 分类：A（保留历史）+ B（合同细节）
- 已确认规则：删除针对聚合；Version/Source 不物理删除；需要恢复。
- 待决定内容：include_deleted、详情语义、重复删除、恢复、原因字段、deleted actor、重复检测关系。
- 当前实现：只有 `deleted_at`；普通 Repository 查询隐藏删除项。
- 可选方案：删除元数据放聚合；放审计事件；两者混合。
- 建议：聚合保留 `deleted_at` 作为当前事实；actor/reason/restore 信息写不可变审计。保留 current_version、公共 ID 和 asset_code；删除资产禁止编辑。删除/恢复均要求 row_version 和幂等 key。
- 建议依据：符合单一事实源及可追踪恢复。
- 影响范围：Lifecycle Service、Audit、Repository、API。
- 是否阻塞 ORM：取决于审计模型
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-09：查询合同

- 分类：B
- 已确认规则：必须明确分页、排序、过滤；不得暴露内部 PK。
- 待决定内容：offset/cursor、过滤集合、默认排序、deleted 语义、详情聚合范围。
- 当前实现：通用分页工具支持两种模式，但没有 EvieAi 查询 Repository。
- 可选方案：page/page_size；cursor。
- 建议：Phase 1 首版采用 page/page_size，默认 20、最大 100，由一个权威配置定义；稳定排序 `created_at DESC, test_asset_id DESC`。详情返回当前版本、来源摘要和审核摘要；版本、审核历史使用独立分页接口。
- 建议依据：适配基础后台 UI，避免一次详情加载无限历史。
- 影响范围：查询 Repository、Schema、API、索引。
- 是否阻塞 ORM：部分索引
- 是否阻塞 Migration：部分索引
- 是否阻塞 Service：否
- 是否阻塞 API：是

### D-10：操作审计物理模型

- 分类：A（必须追踪）+ B（物理实现）
- 已确认规则：创建、版本、来源、审核、删除恢复等关键操作必须可追踪。
- 待决定内容：通用审计表、EvieAi 专用表或领域记录组合。
- 当前实现：`WorkbenchHistoryEvent` 和 `TestDataPoolAuditLog` 都是旧领域专用，不可作为 EvieAi 事实源。
- 可选方案：A 全平台通用 AuditEvent；B EvieAi `test_asset_audit_events`；C Review/Version/Idempotency 等专属记录组合。
- 建议：Phase 1 使用领域专属不可变 `test_asset_audit_events`；全平台 AuditEvent 留待控制面统一设计。事件记录 actor、action、aggregate、channel、request/trace、reason 和前后状态摘要。
- 建议依据：范围最小且不依赖旧 Workbench。
- 影响范围：新表、Service、查询、日志。
- 是否阻塞 ORM：是
- 是否阻塞 Migration：是
- 是否阻塞 Service：是
- 是否阻塞 API：部分

### D-11：API 合同

- 分类：B
- 已确认规则：显式 Schema、稳定错误码、无内部 PK、明确幂等和分页。
- 待决定内容：review endpoint 形态、row_version 位置、duplicate 响应、Manual/Requirement source union。
- 当前实现：只有 JWT 用户鉴权和通用 Router 注册；结构化领域错误映射不足。
- 可选方案：PATCH review_status；或 POST 不可变 review record。
- 建议：采用 POST review record；row_version 使用请求字段或 `If-Match` 二选一签字；项目由已授权 scope 明确传入；channel 由服务器上下文产生，不作为 source_type。
- 建议依据：避免 PATCH 聚合状态绕过审核历史。
- 影响范围：Router、Schema、错误映射、鉴权、日志。
- 是否阻塞 ORM：否
- 是否阻塞 Migration：否
- 是否阻塞 Service：是
- 是否阻塞 API：是

### D-12：前端范围

- 分类：C（可拆分产品排期）+ B（若纳入则需合同）
- 已确认规则：基础资产中心可按产品排期拆分。
- 待决定内容：是否与后端 Phase 1 同 PR/同里程碑。
- 当前实现：有通用 DataTable、ConfirmDialog、Pagination 和 HTTP client；旧 `/assets/test-points` 页面属于旧事实源。
- 可选方案：后端先行；最小 UI 同期；完整 UI 独立排期。
- 建议：后端合同和生命周期先验收，最小 UI 独立切片。只复用通用组件，不复用旧 TestPoint/Candidate 页面状态和 API。
- 建议依据：减少 Phase 1 核心 PR 风险。
- 影响范围：前端 Route、Feature、API client、组件。
- 是否阻塞 ORM：否
- 是否阻塞 Migration：否
- 是否阻塞 Service：否
- 是否阻塞 API：否

### D-13：Migration 与确定性 baseline

- 分类：A（规则固定）+ B（来源迁移方式）
- 已确认规则：不修改 baseline、120000、121000；新 Migration 从唯一 head 延伸；支持 SQLite/PostgreSQL；显式命名且 ≤63 字节。
- 待决定内容：来源演进 Migration、downgrade 数据处理；bootstrap 健康检查的向前兼容修复。
- 当前实现：唯一 head 121000；identifier guard 仅显式列出 120000/121000。bootstrap 对 future head 做全库 frozen equality 检查。
- 可选方案：来源单表 batch rebuild；或新增主表/子表并 backfill。
- 建议：先独立修复 bootstrap 的“冻结 schema 兼容子集/按 revision 校验”问题，不修改 frozen manifest。随后新增 Phase 1 Migration；SQLite 使用受控 batch/backfill，PostgreSQL 使用显式 create/alter/backfill。无法无损降级 Manual 来源时应 fail-closed，不静默丢数据。
- 建议依据：保证冻结 baseline 不变，同时允许线性链继续演进。
- 影响范围：数据库基础设施前置修复、Phase 1 Migration、CI。
- 是否阻塞 ORM：否
- 是否阻塞 Migration：是
- 是否阻塞 Service：否
- 是否阻塞 API：否

### D-14：Requirement 生命周期范围

- 分类：B
- 已确认规则：Requirement API 和生命周期属于 Phase 1。
- 待决定内容：与资产生命周期同计划、独立切片或仅复用 Phase 0 持久化。
- 当前实现：Requirement/Version 模型和 Repository 已有；无完整 API/Service。
- 可选方案：A 与资产生命周期同一完整计划；B Phase 1 独立后续切片；C 当前只绑定已存在 Requirement。
- 建议：方案 B。资产核心先支持 Manual 和绑定已有 Requirement；Requirement API/生命周期作为 Phase 1 独立切片，但必须在宣告完整 Phase 1 完成前交付。
- 建议依据：避免扩大单个 PR，同时不静默遗漏权威能力。
- 影响范围：Phase 1 计划拆分、API、前端排期。
- 是否阻塞 ORM：否
- 是否阻塞 Migration：否
- 是否阻塞 Service：Requirement 来源端到端验收前是
- 是否阻塞 API：Requirement 创建入口是

## 7. Phase 1 规格矩阵

| 能力 | 输入 | 已确认规则 | 待定物理规则 | 持久化对象 | 事务边界 | 错误/冲突 | 待签字 |
|---|---|---|---|---|---|---|---|
| Manual 创建 | project、自然语言、actor | 统一 Intake、允许低质量 | Manual source、asset_code | Asset/Version/Source/Idempotency/Audit | 单事务 | 404/409/422 | D02–D05 |
| Requirement 创建 | Requirement/Version 公共 ID | 来源归属必须验证 | 来源新模型 | 同上 + Requirement subtype | 单事务 | 来源不存在/跨项目 | D02–D05 |
| API 幂等重放 | key、fingerprint | 不等于内容重复 | 作用域/保留期 | IdempotencyRecord | 与业务结果同事务 | key payload mismatch | D04 |
| exact duplicate | 规范化内容 | Intake Policy 决定 | hash/范围/行为 | claim/duplicate identity | 与 Intake 同事务 | reuse/409 | D05 |
| 新版本 | asset ID、row_version、正文 | 新版本、状态迁移 | 空修改/原因 | AssetVersion/Audit | 单事务 | 409 optimistic conflict | D06 |
| 历史版本恢复 | 历史 version ID | 不修改历史 | 复制还是切指针 | 推荐新 AssetVersion | 单事务 | 404/409 | D06 |
| 新增来源 | source command | 不覆盖旧来源 | source model | Source 主/子表、Audit | 单事务 | duplicate source | D02 |
| 审核 | version、decision、actor | 不可变历史 | 转换图/重复审核 | ReviewRecord/Asset/Audit | 单事务 | illegal transition | D07 |
| 删除 | asset、row_version、reason | 不删历史 | actor/reason 位置 | Asset/Audit/Idempotency | 单事务 | already deleted/conflict | D08 |
| 恢复 | asset、row_version、reason | 显式恢复 | duplicate 关系 | Asset/Audit/Idempotency | 单事务 | already active/conflict | D08 |
| 列表 | filters/page/sort | 不暴露 PK | 分页/过滤 | 查询投影 | 只读 | 参数 422 | D09 |
| 详情 | asset ID | 当前版本为事实源 | deleted 可见性 | 聚合投影 | 只读 | 404/deleted | D09 |
| 版本历史 | asset ID/page | 历史不可变 | 分页排序 | AssetVersion | 只读 | 404 | D09 |

## 8. 推荐数据模型变化

### 必须项

- 不可变审核记录表：
  - 内部 Integer PK
  - TestAsset/TestAssetVersion FK
  - from/to review status
  - reviewer、reviewed_at、comment/reason
  - request/trace
  - 显式 PK/FK/Index 名
- 幂等记录表：
  - scope、operation_type、key、request_fingerprint
  - result resource public ID、status、created/expires
  - 数据库唯一约束保护并发
- 操作审计：
  - 至少覆盖 create/version/source/review/delete/restore
  - 不复用旧 Workbench 表
- TestAssetSource 演进：
  - 无损迁移当前 Requirement 来源
  - 支持 Manual 来源
  - 保持一个 TestAsset 多来源
- 架构守卫：
  - 新 Model/Schema/Repository/Service 目录纳入 AST 和字段检查

### 待签字项

- 通用来源主表 + Requirement 子表
- exact duplicate 独立唯一 claim 表
- review/audit/idempotency 公共 ID 及前缀
- 删除/恢复 actor 和 reason 是否只在审计表
- asset_code 的生成和永久占用规则
- idempotency 保留期
- source_identity_hash 的统一计算方
- 新版本 `edit_reason` 是否进入 Version 或 Audit
- exact duplicate 对已删除资产的行为

### 可选项

- 基础前端资产中心
- 语义重复基础标签
- 异步质量事件接口

后两项未经单独批准不得进入核心 Phase 1。

### Phase 1 非目标

Candidate、Preview、AI Producer、文档解析、Asset-to-Case、ConversionAttempt、Compiler、QualityGate、Runner、TestCase、DSL、script_code、正式语义模型和完整异步质量流程。

### Migration 要点

- 父 revision：`20260713_121000`
- 不修改 frozen manifest/schema
- 所有约束和索引显式命名
- 所有标识符按 UTF-8 字节 ≤63
- Requirement 来源数据先 backfill，再收紧约束
- SQLite 根据最终来源方案使用 batch rebuild
- PostgreSQL 使用显式 DDL/backfill
- downgrade 不得静默丢失 Manual 来源
- upgrade/downgrade/upgrade 均需验证
- identifier guard 必须自动覆盖新 Migration，不能继续手工只列 120000/121000

## 9. 推荐 Service 和事务边界

| 组件 | 推荐职责 | 禁止职责 |
|---|---|---|
| `TestAssetIntakeService` | 创建/复用资产、首版本、来源、幂等、精确重复、审计编排 | 机器转换、质量门、Compiler |
| `TestAssetLifecycleService` | 新版本、历史恢复、删除和恢复、row_version | 原地修改历史版本 |
| `TestAssetReviewService` | 审核状态机、不可变审核记录、聚合状态更新 | 直接覆盖审核历史 |
| Idempotency Policy/Repository | key claim、fingerprint、重放结果 | 内容重复判断 |
| ExactDuplicate Policy | 内容规范化、指纹和处理策略 | 语义相似判断 |
| Audit 组件 | 追加不可变生命周期事件 | 修改领域聚合代替 Service |
| Repository | add、flush、query、受控 update | commit、rollback、业务事务 |
| API Adapter | 鉴权、scope、Schema、调用 Service、异常映射 | ORM 写入、事务控制 |
| Unit of Work/事务编排 | commit/rollback、多 Repository 原子性 | 业务策略默认值 |

事务规则：

- 只有应用事务编排层可以 commit。
- Repository、Router 禁止 commit。
- 数据库异常由事务层 rollback；失败 Session 不继续使用。
- current_version_pk、状态、row_version 与新 Version 同事务更新。
- 幂等 claim、exact duplicate claim、业务结果和审计不得跨独立 commit。
- 409 分别表达幂等 payload 冲突、exact duplicate 策略冲突、row_version 冲突和非法状态转换，使用不同稳定 error code。

## 10. 推荐 API 合同

| Method | Path | 请求要点 | 响应要点 | 错误语义 | 待签字 |
|---|---|---|---|---|---|
| POST | `/api/evie-ai/test-assets` | project、自然语言、source union、Idempotency-Key | 201 新建或已存在资源 | 404/409/422 | duplicate 响应 |
| GET | `/api/evie-ai/test-assets` | filters、page、page_size、sort | items、pagination、total | 422 | 过滤/分页 |
| GET | `/api/evie-ai/test-assets/{id}` | include_deleted 受权限控制 | 当前版本、来源、审核摘要 | 404 | deleted 语义 |
| POST | `/api/evie-ai/test-assets/{id}/versions` | expected row_version、自然语言、原因、key | 新版本及新 row_version | 404/409/422 | row_version 位置 |
| GET | `/api/evie-ai/test-assets/{id}/versions` | page/page_size | 不可变版本列表 | 404 | 分页 |
| POST | `/api/evie-ai/test-assets/{id}/reviews` | version ID、decision、comment、key | review record + current status | 409/422 | 状态图 |
| GET | `/api/evie-ai/test-assets/{id}/reviews` | page/page_size | 审核历史 | 404 | 是否首版交付 |
| DELETE | `/api/evie-ai/test-assets/{id}` | row_version、reason、key | 删除状态/新 row_version | 404/409 | 重复删除 |
| POST | `/api/evie-ai/test-assets/{id}/restore` | row_version、reason、key | 恢复状态/新 row_version | 404/409 | duplicate 交互 |

API Schema 不接受机器执行字段，不暴露内部 Integer PK。入口渠道由服务端上下文记录，不自动转成 source_type。

## 11. Requirement 生命周期范围建议

- 权威 Phase 1 定义：Requirement API 和版本生命周期属于 Phase 1。
- 当前用户任务：自然语言测试资产生命周期。
- 方案 A：同一完整计划和同一实施批次。
- 方案 B：同属 Phase 1，但拆成独立后续切片。
- 方案 C：当前只使用 Phase 0 Requirement 持久化能力。
- 推荐：**方案 B**。

理由：

- Manual 资产不依赖 Requirement API。
- 绑定已有 Requirement 的资产可先复用 Phase 0 Repository。
- Requirement 创建/编辑 API 会显著扩大单个 PR。
- 但完整 Phase 1 不能永久停在方案 C。

是否阻塞资产生命周期：不阻塞 Manual 主链；会阻塞“从 API 新建 Requirement 后创建来源资产”的完整端到端验收。

需要人工签字的最终问题：

> 是否批准 Requirement 生命周期作为 Phase 1 独立后续切片，并允许资产生命周期首切片只绑定已存在 Requirement？

## 12. 前端拆分建议

后端核心完成条件：

- Intake、幂等、exact duplicate、版本、审核、删除恢复、查询和审计 API 完成。
- SQLite/PostgreSQL、事务和并发测试通过。
- 不依赖前端即可完成 API 端到端验收。

Phase 1 前端最小可用范围：

- 资产列表
- 手工新建
- 详情和版本历史
- 编辑创建新版本
- 审核
- 删除/恢复

可独立产品排期：

- 高级过滤
- 来源关系可视化
- 审核工作台
- 批量操作
- 完整审计事件页面

可复用技术组件：

- `DataTable`
- `ConfirmDialog`
- `TablePagination`
- 现有认证 fetch transport

禁止复用为新事实源：

- `AiGenerationPage`
- `TestPointAssetsPage`
- `TestPointAssetEditPage`
- Candidate/Preview/selectedCandidates 状态和 API
- 旧 TestPointAsset 数据模型

## 13. 测试矩阵

| 测试域 | 必须覆盖 |
|---|---|
| ID | 新公共 ID 格式、长度、字符集、完整 UUID、碰撞 |
| Model | 字段、FK、Unique、Check、Index、审计字段 |
| Schema | extra forbid、自然语言边界、public ID、不暴露 PK |
| Repository | add/flush/query、无 commit/rollback、删除过滤、来源归属 |
| Service | Intake、版本、审核、删除恢复、错误映射 |
| Transaction | 任一中间步骤失败时 Asset/Version/Source/Idempotency/Review/Audit 全回滚 |
| SQLite | `PRAGMA foreign_keys=ON`，batch migration，约束行为 |
| PostgreSQL | 原生 FK/unique/lock/concurrency |
| Concurrency | 同 key、同 fingerprint、同 version_no、row_version 冲突 |
| Idempotency | 同 key 同请求、不同请求、失败重试、删除后重放 |
| Exact duplicate | 多来源、不同 tags/priority、已删除、并发 |
| Version immutability | 普通 API/Repository 不允许更新历史内容 |
| Provenance | 多来源、重复来源、Requirement version ownership |
| Review | 合法/非法转换、重复审核、新版本 reset、不可变历史 |
| Delete/restore | 默认隐藏、重复操作、row_version、保留历史 |
| Audit | 每个关键操作产生一条正确不可变事件 |
| API | 201/200/404/409/422、project scope、稳定错误码 |
| Migration | 121000→新 head、downgrade/upgrade、数据保留 |
| Bootstrap | 空库 baseline→新 head；future head 不被 frozen equality 误拒 |
| Identifier | 所有新表/列/约束/索引 UTF-8 ≤63 字节 |
| Architecture | 禁止 Candidate/structurer/compiler/runner 导入和机器字段 |
| Logging/security | 自然语言正文不进入 access log，凭证不泄露 |
| Legacy baseline | 旧链已知失败不增加；EvieAi 变更不触碰旧事实源 |

本次没有运行测试；任务是只读规格预检，仅执行了 Git 与 Alembic 的只读状态命令。

## 14. 推荐实施切片

### Slice 0：数据库向前兼容前置修复

- 目标：使 bootstrap 能接受 121000 之后的合法增量 schema
- 已确认规则：frozen baseline 不修改
- 前置签字：健康检查采用兼容子集还是 revision-specific manifest
- 文件范围：bootstrap/fingerprint/数据库测试
- Migration 影响：无
- 测试：baseline drift、future table/column、SQLite/PostgreSQL
- Commit：`fix(database): allow managed schema evolution past frozen baseline`

### Slice 1：Phase 1 权威规格

- 目标：记录 D02–D11、D14 签字结果
- 前置签字：全部核心物理决策
- 文件范围：`docs/evie-ai/implementation/**`
- Migration 影响：无
- 测试：文档一致性
- Commit：`docs(evie-ai): approve phase1 asset lifecycle specification`

### Slice 2：领域常量、Policy 和模型

- 目标：来源、审核、幂等、审计模型与状态 Policy
- 前置签字：D02、D04、D05、D07、D08、D10
- 文件范围：models/constants/policies/ID
- Migration 影响：尚不生成 Migration 或与下一切片分开
- 测试：Model、Policy、ID、架构守卫
- Commit：`feat(evie-ai): add phase1 asset lifecycle domain models`

### Slice 3：增量 Migration

- 目标：从 121000 演进并无损迁移 Requirement 来源
- 前置签字：最终数据模型和 downgrade 策略
- 文件范围：单一新 Migration、Migration/identifier tests
- Migration 影响：新增表、来源演进、索引
- 测试：SQLite/PostgreSQL upgrade/downgrade/upgrade
- Commit：`feat(evie-ai): add phase1 asset lifecycle schema`

### Slice 4：Repository 与查询

- 目标：新表持久化、过滤分页、并发访问
- 前置签字：D09
- 文件范围：repositories/evie_ai、errors
- Migration 影响：无
- 测试：Repository、DB unique、FK、concurrency
- Commit：`feat(evie-ai): add phase1 lifecycle repositories`

### Slice 5：Intake 和生命周期 Service

- 目标：统一 Intake、版本、删除恢复、审核、幂等和审计事务
- 前置签字：D01、D03–D08、D10
- 文件范围：services/policies/UoW
- Migration 影响：无
- 测试：事务、回滚、状态机、重放、重复
- Commit：`feat(evie-ai): implement natural language asset lifecycle services`

### Slice 6：API 与安全适配

- 目标：Router、Schema、错误映射、project scope
- 前置签字：D11
- 文件范围：routers/schemas/main registration/log redaction
- Migration 影响：无
- 测试：API、鉴权、错误、安全日志
- Commit：`feat(evie-ai): expose natural language asset lifecycle APIs`

### Slice 7：Requirement 生命周期

- 目标：Requirement API 和版本生命周期
- 前置签字：D14
- 文件范围：独立 Requirement Service/API
- Migration 影响：视最终合同
- 测试：Requirement 事务、版本、来源集成
- Commit：`feat(evie-ai): add requirement lifecycle APIs`

### Slice 8：前端资产中心

- 目标：基础列表、新建、详情、版本、审核和删除恢复
- 前置签字：产品排期与 API 稳定
- 文件范围：独立 EvieAi feature/routes
- Migration 影响：无
- 测试：组件和 E2E
- Commit：`feat(evie-ai): add natural language asset center`

## 15. 阻塞项和进入实施条件

未签字前禁止 ORM：

- D02 来源物理模型
- D04 幂等表
- D05 exact duplicate claim
- D07 审核记录
- D08 删除恢复审计
- D10 操作审计

未签字前禁止 Migration：

- 上述所有表结构
- SQLite 来源迁移方式
- PostgreSQL backfill 顺序
- downgrade 对 Manual 来源的处理

此外，C-01 bootstrap 向前兼容缺陷必须先独立修复并合并。

未签字前禁止 Service：

- D01 Unit of Work/事务合同
- D03 创建合同
- D04/D05 冲突语义
- D06 编辑和历史恢复
- D07 审核状态图
- D08 删除恢复规则
- D10 审计写入规则

未签字前禁止 API：

- D09 查询合同
- D11 row_version、幂等、duplicate 和审核 endpoint
- 项目 scope 授权策略
- 自然语言请求体日志脱敏方案

可以推迟到独立切片：

- 前端资产中心
- Requirement 完整 API，但必须经 D14 签字
- 疑似语义重复
- 异步质量评估
- AI Producer
- Asset-to-Case

是否可以开始编写正式 Phase 1 实施计划：**暂不可以定版**。阶段入口条件明确要求幂等、精确重复、审核和状态转换先确认，见 `phase-traceability.md:429-436`。

数据库 baseline 状态：

- 设计和 head 正常。
- 本地 current 落后 head，不影响只读规划，但后续测试前需按受管库路径升级。
- bootstrap 对 future schema 的全量等值检查是实际实现阻塞；不得通过修改 frozen baseline 解决。

## 16. 最终结论

**需要先完成指定人工签字。**

必须优先签字：

1. D02 多来源物理模型；
2. D04 幂等作用域和表结构；
3. D05 exact duplicate 范围、指纹和行为；
4. D06 空修改、历史恢复和并发版本规则；
5. D07 审核记录表和状态转换；
6. D08 删除恢复语义；
7. D09 查询合同；
8. D10 审计物理模型；
9. D11 API 幂等、row_version 和审核 endpoint；
10. D14 Requirement 生命周期拆分方式；
11. bootstrap 对 121000 之后 schema 的健康检查修复方案。

签字并完成数据库向前兼容前置修复后，才可以编写并冻结正式 Phase 1 实施计划；本结论不授权开始编码。

本次预检为只读规格分析，未修改数据库或 Git 历史。本文仅作为预检结果留档。
