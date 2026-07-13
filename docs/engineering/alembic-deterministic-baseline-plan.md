# Alembic 确定性安装基线设计

状态：已签字；作为 `fix/alembic-deterministic-baseline` 的实施合同。

日期：2026-07-13

分支：`fix/alembic-deterministic-baseline`
审计基线：`f244d9d8b63c31eafc599ae1b5e003ad28cda2cf`（`dev` 合并后的 EvieAi Phase 0）

## 1. 问题与结论

当前 Alembic 根 revision `20260323_143500` 不是历史 schema 快照。它在 upgrade 时导入**当前** `app.models`，再调用 `Base.metadata.create_all()`。因此相同 revision 的真实 DDL 会随着今天的 ORM 模型改变，不能作为可重复的历史迁移。

证据：

- [`20260323_143500_initial_enterprise_schema.py`](../../apps/web-ui-service/migrations/versions/20260323_143500_initial_enterprise_schema.py#L17) 的 `upgrade()` 在第 20–23 行导入当前模型并调用 `Base.metadata.create_all()`；第 26–28 行的 downgrade 是 no-op。
- [`app/models/__init__.py`](../../apps/web-ui-service/app/models/__init__.py) 当前会注册 EvieAi Phase 0 模型，因此根 revision 已能看见它们。
- 临时空 SQLite 数据库实际执行 `alembic upgrade 20260323_143500` 后，revision 表为 `20260323_143500`，却已创建 43 张用户表，其中包含 `requirements`、`requirement_versions`、`test_assets`、`test_asset_versions`、`test_asset_sources`。
- 从同一空库继续 `alembic upgrade head` 成功并停在 `20260713_120000`；EvieAi migration 的“已有表结构”校验路径是这一历史漂移的临时防御，而不是根因修复。见 [`20260713_120000_evie_ai_phase0_assets.py`](../../apps/web-ui-service/migrations/versions/20260713_120000_evie_ai_phase0_assets.py#L187)。

此外，动态建表并不只存在于根 migration：

- [`scripts/bootstrap_database.py`](../../apps/web-ui-service/scripts/bootstrap_database.py#L46) 第 46–51 行会创建当前 metadata；第 93–121 行会在“缺失 revision”或“有表但无版本”场景创建 metadata 后直接 stamp 当前 head。
- Docker 启动脚本在 [`start-web-with-desktop.sh`](../../scripts/docker/start-web-with-desktop.sh#L62) 第 63 行调用该 bootstrap；Docker 环境关闭了应用启动时的自动建表，见 [`docker-compose.yml`](../../docker-compose.yml#L9) 第 10–12 行。
- 本地开发启动仍可由 [`app/main.py`](../../apps/web-ui-service/app/main.py#L83) 第 86–87 行的开关调用 `Base.metadata.create_all()`。这不是本设计第一阶段的修改目标，但必须与新安装迁移语义区分。

结论：不能再把“当前 ORM metadata”当成任何历史 revision 或数据库接管流程的 schema 来源。

## 2. 已验证的根 revision 实际产物

2026-07-13 在临时 SQLite 文件中执行：

```bash
DATABASE_URL="sqlite:////tmp/alembic-baseline-audit.db" alembic upgrade 20260323_143500
```

得到以下 43 张用户表（不含 `alembic_version`）：

```text
assertion_execution_logs
assertion_templates
behavior_registry
orchestration_tasks
page_element_health_checks
page_element_locators
page_element_versions
page_elements
page_object_candidate_elements
page_object_candidate_groups
page_object_governance_logs
page_object_recorder_sessions
page_object_refs
page_objects
prompt_templates
quality_eval_datasets
quality_eval_items
quality_eval_results
quality_eval_runs
requirement_documents
requirement_versions
requirements
test_asset_sources
test_asset_versions
test_assets
test_case_defects
test_case_executions
test_case_steps
test_case_tree_nodes
test_case_versions
test_cases
test_data_pool_audit_logs
test_data_pool_items
test_data_pools
test_points
test_projects
users
workbench_defect_links
workbench_execution_gate_decisions
workbench_failure_source_calibrations
workbench_history_events
workbench_review_decisions
workbench_runtime_runs
```

这证明根 revision 当前不仅会提前创建之后的旧链表，也会提前创建 2026-07-13 才引入的 EvieAi 表。未来任意新增 ORM 表或列都可能再次改变空库从该根 revision 开始的结果。

## 3. 已有数据库的证据与未知项

仓库中存在“该 revision 曾进入共享 PostgreSQL / Docker 路径”的历史证据：

- [`platform-data-and-deployment-upgrade-plan-2026-03-23.md`](../architecture/platform-data-and-deployment-upgrade-plan-2026-03-23.md#L352) 第 356–364 行记录 Docker 启动先执行 Alembic，并记录当时 PostgreSQL 的版本为 `20260323_143500`。
- 当前 Docker 仍通过 bootstrap 启动，见 [`start-web-with-desktop.sh`](../../scripts/docker/start-web-with-desktop.sh#L62)。

该记录只能证明历史共享/容器 PostgreSQL 曾使用该 revision；仓库没有生产或共享数据库的实时连接信息，**无法证明今天哪些环境仍停留在该 revision**。

实施前必须由环境所有者在每个共享环境只读执行：

```sql
SELECT version_num FROM alembic_version;
```

并记录：环境名、数据库类型、revision、用户表数量、备份位置和变更窗口。没有这份清单时，不允许改写历史 revision，也不允许对“无版本旧库”自动 stamp。

## 4. 方案比较

| 方案 | 做法 | 优点 | 核心风险 | 结论 |
| --- | --- | --- | --- | --- |
| A：改写历史根 migration | 把 `20260323_143500` 替换为静态 `op.create_table()` 链 | 一个 Alembic 线性链，空库可直接 `upgrade head` | 根 revision 已有共享 PostgreSQL 使用证据；原始 2026-03 schema 快照不存在，后续多个 migration 还是 reconstructed/no-op，无法安全证明重写后与旧库一致 | 不选 |
| B：新增确定性安装 baseline | 保留 legacy chain 供已有受管库升级；空库通过固定 schema baseline 建库、验证并 stamp 到冻结 revision | 不重写已发布历史；新安装结果可重复；可先阻断 Phase 1 前的继续漂移 | 需要明确 bootstrap 为唯一空库入口；必须处理未知/无版本旧库；手工直接 `alembic upgrade head` 仍不能作为新安装流程 | 推荐 |
| C：继续结构守卫 | 每个新 migration 检查“表可能已提前存在” | 改动最小 | 每新增表都扩大例外路径；无法让历史结果可重复；会把 Phase 1+ 绑定在旧缺陷上 | 仅作为 B 实施前的短期保护，不作为长期方案 |

## 5. 推荐方案：B，确定性安装 baseline

### 5.1 冻结点

第一份确定性 baseline 的 schema 冻结点为当前已验证的 Alembic head：

```text
20260713_120000
```

它包含 EvieAi Phase 0 的五张表。该版本选择的前提是：在 baseline 实施完成前，不创建 Phase 1 schema migration。若有新的 schema migration 先合入，必须重新选择并重新审计冻结点，不能让 baseline 静默使用“最新 metadata”。

### 5.2 目标行为

```text
空数据库
→ 确认没有用户表
→ 执行冻结在 20260713_120000 的静态 DDL
→ 对表、列、PK、FK、唯一约束、检查约束和索引做 schema fingerprint 校验
→ alembic stamp 20260713_120000
→ 如有更新 revision，再执行正常 alembic upgrade head

已有且版本受管的数据库
→ 读取 alembic_version
→ 仅执行正常 alembic upgrade head

已有用户表但无 alembic_version，或 version 指向缺失 revision
→ 明确失败
→ 输出只读盘点和人工接管步骤
→ 不调用 create_all，不自动 stamp
```

静态 DDL 必须来自冻结的 schema 定义文件，使用确定性的 `op.create_table`、`op.create_index` 和显式约束名称；不得导入 `app.models`、`Base` 或运行时 metadata。它必须同时覆盖项目支持的 SQLite 和 PostgreSQL。

### 5.3 模块边界（实施阶段）

| 模块 | 未来职责 | 明确禁止 |
| --- | --- | --- |
| `migrations/baselines/<frozen-revision>_schema.py` | 声明固定 DDL、依赖顺序和 schema fingerprint | 导入 ORM model、读取 Settings、调用 `create_all` |
| `scripts/bootstrap_database.py` | 根据数据库状态选择“空库 baseline”或“已受管升级”；事务与错误出口 | 通过当前 metadata 修复 schema、未知库自动 stamp head |
| `migrations/versions/**` | 既有受管库的增量演进 | 把 baseline DDL 混入下一条业务 migration |
| CI 验证 | 验证空库和已有库两条路径 | 用 `Base.metadata.create_all()` 作为 migration 正确性证明 |

安装 baseline 是**安装工具的固定 schema 快照**，不作为第二条 Alembic head，也不建立平行业务迁移图。它完成后将数据库 stamp 到既有线性链的冻结 revision；之后所有数据库继续使用同一条 Alembic 线性链。

### 5.4 为什么不直接用新的 Alembic root revision

在同一 Alembic script location 新增一个 `down_revision = None` 的 root，会形成双 head。已有数据库随后会尝试执行新 root 并重复建表；新库则仍需决定如何跳过 legacy root。它不能自动同时兼容两个数据库族。

因此 Phase 1 前的最小安全方式是：**静态安装 baseline + 明确 stamp 到现有冻结 revision**。如果未来要完全替换 legacy chain，应单独设计“新 migration repository / schema squash / 受管环境一次性 bridge”的迁移项目，不与业务 schema 变更混合。

## 6. 与旧 migration 的关系

本方案不在第一实施提交改写 [`20260323_143500_initial_enterprise_schema.py`](../../apps/web-ui-service/migrations/versions/20260323_143500_initial_enterprise_schema.py#L11)。原因：

1. 历史根 revision 可能已被共享 PostgreSQL 执行；
2. 根 revision 的原始静态 schema 已无法从现有历史迁移可靠还原；
3. 多个旧 revision 标注为 reconstructed 或 no-op，见例如 [`20260327_181500_add_test_cases_data_config.py`](../../apps/web-ui-service/migrations/versions/20260327_181500_add_test_cases_data_config.py#L15)；
4. 先改写历史文件会把“修复新安装流程”和“改写已有数据库的历史解释”耦合在同一个高风险动作中。

但这不意味着旧根 migration 可继续作为空库安装入口。baseline 实施后：

- 官方 Docker / `make db-bootstrap` 空库路径必须改为确定性 baseline；
- README 和部署文档必须明确：空库不得直接以 `alembic upgrade head` 初始化；
- CI 必须覆盖官方 bootstrap，且禁止该路径导入 `Base` 或 `app.models`；
- 后续单独评估是否让 legacy root 对空库 fail-closed。该动作若要实施，仍需先确认所有需要直接执行 legacy chain 的环境。

## 7. 已签字的门禁

### 7.1 实施门禁

以下项目已经确认，可以开始代码实施：

1. 选择方案 B；
2. 冻结 revision 为 `20260713_120000`；
3. 空库、无版本旧库、缺失 revision 的状态机已经签字；
4. 可使用隔离 PostgreSQL 环境验证；
5. 本任务独立于 EvieAi Phase 1，必须先完成、验收和合并。

共享环境 revision 清单**不是**代码实施门禁：本方案不改写旧 migration、不自动接管共享数据库，也不会在开发或测试中连接共享环境。

### 7.2 发布门禁

在部署新 bootstrap、修改共享 Docker/正式启动入口、在共享数据库执行 bootstrap，或宣布旧启动路径退役前，必须完成环境清单：环境名、数据库类型、`alembic_version`、用户表数量、备份位置和变更窗口。

## 8. 实施切片和提交边界

### Commit 1：静态 baseline 定义与规范化 fingerprint

新增冻结 schema 定义与只读 fingerprint helper；不修改 legacy migration、bootstrap 或业务模型。

验收：同一冻结 DDL 在空 SQLite 与空 PostgreSQL 都能创建预期结构；定义文件不导入 `Base`、`app.models` 或任何 ORM model。fingerprint 比较规范化逻辑结构，而不比较两个方言的原始 DDL 文本。

### Commit 2：安全 bootstrap 状态机

修改 `scripts/bootstrap_database.py`：空库走 baseline；受管库走 Alembic 增量；未知/无版本旧库 fail-closed。删除该脚本的当前 metadata 同步和自动 stamp 行为。

验收：三种数据库状态分别走唯一、可观测且无歧义的分支；失败时不写 `alembic_version`，也不创建额外表。

### Commit 3：空库 Alembic 守卫、Docker、文档和 CI

增加空库裸 `alembic upgrade` fail-closed 守卫；更新官方启动与文档入口；新增架构测试和 SQLite/PostgreSQL 验证脚本。

验收：CI 证明官方空库安装结果稳定；空库裸 `alembic upgrade head` 默认失败并提示使用 bootstrap；README 不再把裸 `alembic upgrade head` 描述为新安装流程。唯一例外必须显式设置默认关闭的 `ALLOW_LEGACY_EMPTY_DB_ALEMBIC_UPGRADE=1`，Docker 不得默认开启该变量。

每个提交独立审查、可回滚。不得混入 EvieAi Phase 1、Candidate 旧链、Compiler 或 Runner 修改。

## 9. 必须通过的验证

1. 空 SQLite：baseline → schema fingerprint → stamp `20260713_120000` → upgrade head；
2. 空 PostgreSQL：同样流程，验证 PK、FK、索引、JSON、默认值和约束名；
3. 已受管的旧 revision 数据库：记录原有表名、行数和版本后升级；确认只应用后续 revision，旧表与记录不变；
4. 已受管的 `20260713_120000` 数据库：bootstrap 不创建/删除任何表，仅确认版本；
5. 有用户表但无 `alembic_version`：明确失败，且不写任何表、列、版本记录；
6. `alembic_version` 含仓库不存在的 revision：明确失败，且不自动同步 metadata；
7. 可重复性：两次空库 baseline 的 schema fingerprint 完全一致；
8. 架构守卫：baseline 和 bootstrap 的空库路径 AST 不得导入 `app.models`、`Base`，不得引用 `metadata.create_all`；
9. 回滚：只验证增量 migration 的 downgrade。baseline 只用于全新空库，安装失败时不 stamp，直接销毁该新库或恢复空库，不在含数据数据库执行 baseline downgrade。

### 9.1 规范化 fingerprint 合同

SQLite 与 PostgreSQL 的原始 DDL、反射类型、identity 表达、JSON、默认值和索引实现不同，禁止直接比较 SQL 文本。冻结 manifest 和两个方言各自反射的 schema 必须先规范化为以下逻辑结构：

```text
table name
column name
normalized logical type
nullable
primary key
foreign key target
unique constraint
check constraint
index columns
index uniqueness
stable server-default semantics
```

例如 SQLite 的 JSON 文本与 PostgreSQL 的 JSON/JSONB 规范化为 `json`；SQLite 的整数主键与 PostgreSQL 的 integer identity 规范化为 `integer-auto-pk`。验收关系是：

```text
SQLite normalized fingerprint = frozen manifest
PostgreSQL normalized fingerprint = frozen manifest
```

而不是两个数据库的原始 DDL 相等。

### 9.2 Bootstrap 五态

| 状态 | 判断 | 行为 |
| --- | --- | --- |
| `EMPTY` | 无用户表、无版本表 | 执行静态 baseline，fingerprint 成功后才 stamp |
| `MANAGED` | 版本存在于当前 ScriptDirectory，且最小 schema 健康 | 正常 `upgrade head` |
| `UNVERSIONED` | 有用户表、无版本表 | fail-closed |
| `UNKNOWN_REVISION` | 版本记录不在当前 ScriptDirectory | fail-closed |
| `VERSIONED_EMPTY_OR_INCONSISTENT` | 有版本记录但关键 schema 缺失或不匹配 | fail-closed |

`stamp` 只能发生在静态 DDL 和完整 fingerprint 校验成功之后。不得使用当前 ORM metadata 补齐任何异常状态。

## 10. 仍然存在、但不在本设计实现范围内的风险

- [`app/main.py`](../../apps/web-ui-service/app/main.py#L83) 的开发自动建表会使本地开发 schema 与 Alembic 状态脱钩；它需要独立治理，不能作为本任务的隐性变更。
- 历史 migration 中存在 reconstructed/no-op 记录，故本设计不能声称已恢复完整可逆的历史演进。
- 旧文档中曾建议对无版本旧库自动补齐 metadata 后 stamp；该做法与本方案的 fail-closed 接管原则冲突，实施时必须更新该运行文档。
- 共享/生产数据库的实时 revision 尚无仓库内证据；未完成环境盘点前，不得选择方案 A 或在已有数据库做强制 stamp。

## 11. 当前签字结论

建议批准：**方案 B，冻结 `20260713_120000`，以静态安装 baseline 替代空库的动态 metadata 建表；已有受管数据库继续使用既有 Alembic 增量链。**

本设计签字前，本分支不得修改旧 migration、`bootstrap_database.py`、Docker 启动逻辑或任何 Phase 1 业务表。
