# EvieAi Phase 1 Slice 5 API 安全前置实施计划

日期：2026-07-19

状态：

Accepted / Active

适用范围：

EvieAi Phase 1 Slice 5 — API Security Prerequisites

- 本文件是 Slice 5 独立实施计划。
- 本文件从 `ADR-0001`、Phase 1 Specification 和 Phase 1 Overall Plan 派生。
- 本文件不能扩大已批准合同。
- 本文件已获得用户批准，当前状态为 `Accepted / Active`。
- 本文件中的实施前门禁和 `Not started` 表述记录计划批准时点；当前实施与合并证据见第 21 节。
- 当前 Phase 1 仍为 In Progress。
- 当前 Closeout 仍为 Not completed。
- 当前未进入 Phase 2。

Slice 5 implementation plan status: Accepted / Active
Slice 5 implementation status: Completed
Slice 5 targeted validation: Passed (56 passed)
Slice 5 regression attribution: 0 new regressions
Slice 5 merge status: Merged into `dev`
Phase 1 overall status: In Progress
Phase 1 closeout status: Not completed

## 1. 文档定位与权威关系

本计划的权威关系固定为：

```text
AGENTS.md
→ ADR-0001
→ Phase 1 Specification
→ Phase 1 Overall Implementation Plan
→ Slice 5 Independent Implementation Plan
→ future implementation tasks and acceptance evidence
```

- `AGENTS.md` 定义 EvieAi 实施硬边界，尤其是自然语言资产、Asset-to-Case、Runner、ID、日志、安全、事务和 Git 规则。
- `ADR-0001` 是 Phase 1 自然语言资产生命周期的 governing decision。
- `phase-1-natural-language-asset-lifecycle-specification.md` 是 Phase 1 合同的详细字段、状态、错误和接口约束来源。
- `phase-1-natural-language-asset-lifecycle-plan.md` 定义 Slice 0～11 的实施边界和顺序。
- 本文件只把 Slice 5 拆成可审查、可批准、可实施、可验收的独立计划，不修改上级合同。
- `phase-traceability.md` 只记录当前状态和验证证据，不授予实施授权。
- `ADR-0002`、`ARCHITECTURE_BASELINE.md`、`evie-ai-overview.md` 和 `target-capability-map.md` 只限定长期目标边界、状态口径和阶段关系，不改变 Phase 1 的已批准实施合同。
- 本计划 PR 合入 `dev` 前不得创建 Slice 5 实施分支或开始编码；该实施前门禁现已满足，保留为历史流程记录。

## 2. 计划制定时的历史基线

- 计划制定时的 `dev` HEAD：`71535b5a3dac3501b2a6b31a4293cf30d29d5896`
- 计划制定时的 `origin/dev`：`71535b5a3dac3501b2a6b31a4293cf30d29d5896`
- 计划制定时的计划分支：`codex/evie-ai-phase1-slice5-plan`
- 计划制定时的 `dev` 已包含：
  - Slice 4 Repository / Query 实现；
  - Target Architecture v2 文档基线；
  - PR #12 合并提交 `71535b5a3dac3501b2a6b31a4293cf30d29d5896`
- Slice 1～4 的既有层级验证证据绑定于 `0912696c0d68f56fac756956f2cfceaa6ffc4fa3`；以上内容为 Slice 5 实施前的历史动态验证证据。

### 2.1 Slice 1～4 既有验证快照

| Slice | Verification layer | Result |
|---|---|---|
| Slice 1 | unit / policy / ID | 37 passed |
| Slice 2 | unit / ORM / Schema | 52 passed |
| Slice 3 | migration pytest layer | 10 passed |
| Slice 4 | repository / query | 39 passed |
| Total | Slice 1～4 | 138 passed |

- `138 passed` 不等于全仓 CI 通过。
- `138 passed` 不等于 Asset Lifecycle Core 完成。
- `138 passed` 不等于 Phase 1 完成。
- `138 passed` 不等于 Slice 5 已开始。

### 2.2 计划制定时的阶段状态

- Phase 1 contract status: Accepted / Active
- Phase 1 overall status: In Progress
- Phase 1 closeout status: Not completed
- Slice 5～11 当时均为 `Not started`
- Service、Router/API 和集成主链尚未完成
- Target Architecture v2 已合入 `dev`
- Slice 5 只读预审已经完成
- Slice 5 当时尚未开始

## 3. CI 基线与冻结失败

本节记录当前 `dev` 的已知冻结失败。它们不是通过状态，不得被写成 Slice 5 已满足的 Acceptance Criteria。

| Baseline ID | Workflow/check | Failure location | Failure signature | Present before Slice 5 | Slice 5 responsibility |
|---|---|---|---|---|---|
| CI-B01 | `unit-tests` | `apps/web-ui-service/tests/unit/test_workbench_facade.py` | `8 failures`；`app.api.workbench.facade.test_case_service` import failure | Yes；已存在于 `dev@0912696c0d68f56fac756956f2cfceaa6ffc4fa3` | 不属于 Slice 5；Slice 5 不负责修复；Slice 5 不得增加新失败 |
| CI-B02 | `static-baseline` | `apps/ai-orchestrator/tests/integration/test_app_flask_client.py` | collection failure because `apps/ai-orchestrator/src/app.py` is missing | Yes；已存在于 `dev@0912696c0d68f56fac756956f2cfceaa6ffc4fa3` | 不属于 Slice 5；Slice 5 不负责修复；Slice 5 不得增加新失败 |

后续回归时采用以下判定规则：

- Existing baseline failure：失败节点、失败数量和失败签名与 `CI-B01` 或 `CI-B02` 冻结记录一致。
- New regression：新增失败节点；既有失败数量扩大；失败签名变化；或失败进入 Slice 5 直接修改路径。
- Resolved baseline failure：既有冻结失败消失，可以记录，但不得自动归功于 Slice 5，除非 Slice 5 明确修改了对应路径且有独立证据。
- 无法判断：必须停止，不得自动把结果归类为“既有失败”或“Slice 5 回归”。

## 4. Slice 5 合同追踪

| Contract ID | 合同要求 | 权威来源与章节 | Slice 5 交付方式 | 验收证据 |
|---|---|---|---|---|
| C-02 | 缺少配置不得静默使用固定项目；新链必须验证显式 `project_code` | `AGENTS.md` §§11-12；ADR-0001 A-02；Specification §3.5；Overall Plan §4 Slice 5；Discovery / preflight evidence：`2026-07-14_phase-1-natural-language-asset-lifecycle-preflight.md` §5 | 引入 `ProjectScopeService`；禁止复用 `ensure_project_seed()`、`get_project_status()`、`ensure_project_writable()` 的默认/自动创建语义 | scope 单元测试；active/not found/inactive/missing/invalid 路径；无默认 `mall`；无写数据库副作用 |
| C-03 | 不得记录未经脱敏的需求/自然语言正文 | `AGENTS.md` §§20-21；ADR-0001 D-11；Specification §12；Overall Plan §4 Slice 5；Discovery / preflight evidence：`2026-07-14_phase-1-natural-language-asset-lifecycle-preflight.md` §5 | 引入 `Natural-language Logging Guard`；在 `main.py` 的 HTTP middleware 中对 EvieAi 路径执行 suppress/redact；保留下游 body 可重复读取 | logging guard 单测；integration 验证 JSON、multipart、non-JSON、streaming、不记录正文和 secret |
| C-05 | API 必须使用稳定结构化错误 | `AGENTS.md` §§19、25；ADR-0001 A-09；Specification §12、§12.1；Overall Plan §4 Slice 5；Discovery / preflight evidence：`2026-07-14_phase-1-natural-language-asset-lifecycle-preflight.md` §5 | 引入 `EvieAi HTTP Error Adapter`；对 EvieAi namespace 下的 `EvieAiDomainError`、`HTTPException`、`RequestValidationError` 和未预期异常执行 path-scoped 结构化 HTTP 适配；不改变非 EvieAi 路由既有行为 | error adapter 单测；integration 验证稳定 envelope、status、request_id、不泄露内部异常 |
| P-09 | 认证主体必须绑定稳定公共身份字段 | Overall Plan §1、§4 Slice 5；`phase-traceability.md` §6.3；Specification §3.5.2 A-11 | 基于现有 JWT `sub=User.id` 兼容链，补齐 `TrustedUserPrincipal` 构造、stable actor 生成和 fail-closed 行为 | principal/actor 测试；现有 JWT 兼容测试；非法/缺失 `user_public_id` 拒绝 |
| A-02 | `project scope`、actor、channel 的权威来源固定；admin-only；active project；禁止自动创建默认项目 | ADR-0001 A-02；Specification §3.5、§3.5.1；Overall Plan §4 Slice 5 | `ProjectScopeService`、`ProjectAccessAuthorizer`、`RequestActorContext`、`RequestChannelContext` | admin allow / non-admin deny；不存在/inactive 拒绝；无客户端 actor/channel；transport-agnostic 验证 |
| A-09 | API 成功/冲突语义和稳定错误映射 | ADR-0001 A-09；Specification §12、§12.1 | 在不创建 TestAsset 业务 API 的前提下，先落实 Slice 5 需要的前置错误映射约束和 envelope 形态 | HTTP status / error code / request_id 映射测试；无内部异常泄露 |
| A-11 | `User.user_public_id` 是唯一、稳定、服务端生成的公共身份；actor 固定 `user:<user_public_id>` | ADR-0001 A-11；Specification §3.5.2；Overall Plan §1、§4 Slice 5 | 引入 `UserPublicIdentityService`，仅在认证后校验现有 `user_public_id` 并建立只读 `TrustedUserPrincipal`；`RequestActorContext` 基于 `TrustedUserPrincipal` 输出稳定 actor；`auth.register` 保持兼容回归对象而非本 Slice 生产改动目标 | `auth.register` 兼容测试；JWT `sub=User.id` 兼容测试；`UserRead` 暴露 `user_public_id`；客户端输入不能覆盖服务端身份；actor 规范化与 fail-closed |
| D-11 / Spec-12 | 显式 Schema、稳定错误协议、不暴露内部 PK | ADR-0001 D-11；Specification §12 | Slice 5 只补 HTTP adapter 和安全上下文，不新增业务 Router；为未来 Slice 8 保留稳定输入输出前置条件 | schema/error envelope 验证；确认内部 `User.id` 不进入 EvieAi actor 和错误响应 |

## 5. 目标

Slice 5 的目标限定为以下 API 安全前置能力：

- 可信认证 principal
- stable `user_public_id`
- 显式且 fail-closed 的 `project scope`
- 项目访问授权
- 稳定 actor
- 可信 channel
- `request_id / correlation_id` 内部上下文
- `EvieAiDomainError` 到结构化 HTTP 响应适配
- 自然语言请求日志保护
- 为后续 Slice 6 和 Slice 8 提供安全前置

必须明确：

- Slice 5 不提供 `TestAsset` 业务 API。
- Slice 5 在形成安全上下文后结束，不调用 Intake，不创建 `TestAsset`，不进入 Lifecycle/Review 主链。

## 6. 明确非目标

以下内容不属于 Slice 5：

- `TestAssetIntakeService`
- Intake 事务主链
- Idempotency 业务编排
- Content Claim 业务编排
- Lifecycle Service
- Review Service
- `TestAsset` 业务 Router
- `/api/evie-ai/test-assets` 完整 API
- Requirement 生命周期
- 前端资产中心
- Upload Security
- 文件扫描
- RAG
- `TestPointEvidencePack`
- Streaming
- Notification
- Asset-to-Case
- ORM 变更
- 新数据库字段
- 新 Migration
- 全平台 auth 重构
- 修复全部旧默认 `mall`
- 修复旧 Workbench CI 基线
- 修复 `ai-orchestrator` `static-baseline`
- Phase 2 能力

## 7. 已批准安全语义

### 7.1 Project scope

- `project_code` 必须显式输入。
- 不允许默认值。
- 不允许默认 `mall`。
- 不允许 auto-create。
- 项目必须已存在且为 `active`。
- 缺失、非法、不存在和不可访问均 fail closed。
- 项目存在性与 `active` 校验只在 global admin 授权通过后进行。
- Slice 5 不决定最终 HTTP 传输位置。
- Slice 5 只提供 transport-agnostic 校验。

### 7.2 Authorization

- Phase 1 首版只允许全局 `admin`。
- 非 `admin` 必须拒绝。
- 非 `admin` 路径不得泄露项目存在性。
- 授权必须在任何 `TestProjectRepository` 查询前完成。
- `ProjectAccessAuthorizer` 只校验 `TrustedUserPrincipal.role=admin`，并确认 `TrustedUserPrincipal.is_active`。
- `ProjectAccessAuthorizer` 不引入项目 membership，也不接收原始 ORM `User`。

### 7.3 Stable actor

- JWT `sub` 继续为内部 `User.id`。
- principal 必须暴露合法 `user_public_id`。
- `actor_or_client_id` 固定为 `user:<user_public_id>`。
- 内部 `User.id` 不进入 EvieAi 审计字段。
- actor 不由客户端提交。
- 缺失或非法 `user_public_id` 必须 fail closed。

### 7.4 Channel

- 服务端固定为 `api`。
- 客户端不能覆盖。
- 后续扩展必须通过新合同批准。

### 7.5 Trace

- 复用 `request_id`。
- `correlation_id` 当前只规划为内部上下文。
- 不发明新的外部 Header 合同。
- 不允许客户端控制可信 `correlation identity`。

## 8. 当前实现与复用矩阵

| 能力 | 当前路径/符号 | 当前行为 | 复用结论 | Slice 5 适配方式 |
|---|---|---|---|---|
| `get_current_user` | `apps/web-ui-service/app/core/security.py` | 用 JWT `sub` 解析内部 `User.id`，校验 active，返回 `User` ORM；未单独校验 `user_public_id` | Reuse with adapter | 保留 token 兼容；不修改 `app/core/security.py`；由 Slice 5 的 `UserPublicIdentityService` 把 authenticated `User` 收敛为 `TrustedUserPrincipal` 并补充 `user_public_id` fail-closed 校验 |
| `User.user_public_id` | `apps/web-ui-service/app/models/user.py` | 已存在 `NOT NULL` + `UNIQUE uq_users_user_public_id` | Direct reuse | 作为 stable actor 唯一事实源 |
| `TrustedUserPrincipal` | Slice 5 内部只读合同 | 计划新增内部值对象；仅携带 `user_public_id`、`role`、`is_active` | New internal contract | 只能由 `UserPublicIdentityService` 从 authenticated `User` 构造；下游不再直接接收原始 ORM `User` |
| `generate_user_public_id` | `apps/web-ui-service/app/core/id_gen.py` | 已有统一 `usr_<uuid4hex32>` 生成器 | Direct reuse（compatibility evidence only） | 继续作为现有注册链路的兼容事实；不是 Slice 5 新增安全组件的生产依赖 |
| `UserRead` | `apps/web-ui-service/app/schemas/user.py` | 暴露 `user_public_id`，不暴露内部 `id` | Direct reuse | 用于 auth 兼容和 principal 响应验证 |
| `UserCreate` | `apps/web-ui-service/app/schemas/user.py` | `extra="ignore"`；客户端提供的 `user_public_id` / `actor_or_client_id` 不参与 Schema 绑定 | Direct reuse | 保持当前外部注册兼容语义；客户端字段不覆盖服务端身份，不进入 `TrustedUserPrincipal`，也不要求额外 `422` |
| `auth.register` | `apps/web-ui-service/app/routers/auth.py` | 当前注册路径会生成合法 `user_public_id`，JWT `sub` 继续绑定内部 `User.id`，`UserRead` 暴露 `user_public_id` | Do not modify / compatibility regression target | Slice 5 不计划修改该 Router；仅把它作为注册兼容与公共身份外显行为的回归对象 |
| `TestProject` | `apps/web-ui-service/app/models/test_project.py` | 现有项目存在性和 `status` 事实源 | Direct reuse | 作为 Slice 5 只读 project scope 基础事实 |
| `TestProjectRepository` | `apps/web-ui-service/app/repositories/test_project_repository.py` | 提供 `get_by_code`、`list_by_codes` 等只读查询 | Direct reuse | `ProjectScopeService` 直接依赖该 Repository，避免旧 Workbench 语义 |
| `ensure_project_seed` | `apps/web-ui-service/app/services/test_case_bootstrap_service.py` | 允许创建固定默认项目并写数据库 | Do not reuse | Slice 5 禁止隐式 seed、禁止默认项目 |
| `get_project_status` | `apps/web-ui-service/app/services/test_project_service.py` | 对空值、非法值或不存在项目回退为 `active` | Do not reuse | Slice 5 必须显式 fail closed，不能把非法 scope 视作 `active` |
| `ensure_project_writable` | `apps/web-ui-service/app/services/workbench_project_service.py` | 缺项目时自动创建；随后校验 active | Do not reuse | Slice 5 禁止 auto-create 和默认 `mall` 语义 |
| `EvieAiDomainError` | `apps/web-ui-service/app/errors/evie_ai.py` | 已有稳定 code/domain/stage/message/retryable 合同 | Direct reuse | 作为 Slice 5 域错误基础类型 |
| `EvieAiErrorResponse` | `apps/web-ui-service/app/schemas/evie_ai/operations.py` | 已有 `error` envelope；需与 Specification 对齐为 `request_id` 位于 `error` 对象内部 | Reuse with adapter | 由 HTTP adapter 统一输出；不把 `request_id` 提升到顶层 wrapper |
| exception handlers | `apps/web-ui-service/app/main.py` | 当前 `HTTPException` 和通用异常主要返回自由 `detail` | Reuse with adapter | 在不影响非 EvieAi 路由的前提下，为 EvieAi namespace 添加 path-scoped `HTTPException`、`RequestValidationError` 和 Unexpected Exception 结构化映射 |
| request_id middleware | `apps/web-ui-service/app/main.py` | 生成/透传 `X-Request-Id`，读取并记录 body preview，支持下游重读 body | Reuse with adapter | 保留 `request_id` 和 body replay；`correlation_id` 保持 internal-only；在 EvieAi 路径前置 Natural-language Logging Guard |
| logging redaction | `shared_backend/observability/logging.py` | 对敏感 key 做递归脱敏；不识别“自然语言正文路径语义” | Reuse with adapter | 继续复用通用脱敏，对 EvieAi 路径增加正文 suppress/redact 判定 |
| dependency override fixtures | `apps/web-ui-service/tests/unit/evie_ai/conftest.py` 和现有 FastAPI `dependency_overrides` 模式 | 已有 SQLite/Session/FastAPI override 测试基座 | Direct reuse | 为 Slice 5 单元/集成测试扩展 `TrustedUserPrincipal`、project scope 和 request context fixtures |

## 9. 目标组件和职责

### 9.1 UserPublicIdentityService

- 输入：authenticated `User`。
- 输出：`TrustedUserPrincipal`。
- 内部只读合同：`TrustedUserPrincipal`
  - 字段：`user_public_id`、`role`、`is_active`
  - 只能由 `UserPublicIdentityService` 从 authenticated `User` 构造
  - 构造前必须校验 `user_public_id` 非空且格式合法
  - `role` 和 `is_active` 取自 authenticated `User`
  - 客户端不能构造或覆盖
  - 下游不再接收原始 ORM `User`
  - 不包含内部 `User.id`，除非已有上级合同明确要求
  - 按项目现有惯例实现为不可变或只读内部值对象
- 失败语义：`user_public_id` 缺失或格式非法时，按 `EVIE_DATA_INTEGRITY_ERROR + HTTP 500` fail closed；inactive `User` 继续由现有 auth 层拒绝，不由该服务修复。
- 数据库读取：无额外读取；只消费已认证 `User` 对象上的既有字段。
- 数据库写入：无。
- 事务责任：不创建独立事务，不 `commit`，不 `rollback`。
- 可复用方：`RequestActorContext`、`ProjectAccessAuthorizer` 和后续 EvieAi API 认证依赖。
- 明确禁止：生成 `user_public_id`；修改 `User`；额外数据库查询；数据库写入；客户端提交 `user_public_id`；下游继续消费原始 ORM `User`。

### 9.2 ProjectScopeService

- 输入：admin 授权通过后的显式 `project_code`。
- 输出：已验证的 project scope 结果，包含项目存在性、`active` 状态和标准化 `project_code`。
- 失败语义：缺失、非法、不存在、inactive 时 fail closed。
- 数据库读取：通过 `TestProjectRepository.get_by_code()` 读取项目事实。
- 数据库写入：无。
- 事务责任：只读，不创建事务，不修改项目状态。
- 可复用方：未来 Slice 6 和 Slice 8 的 EvieAi 请求入口。
- 明确禁止：把 principal 当作项目存在性查询的前置替代；默认 `mall`；调用 `ensure_project_seed()`；调用 `ensure_project_writable()`；auto-create；吞掉不存在/非法状态；负责全局角色授权。

### 9.3 ProjectAccessAuthorizer

- 输入：`TrustedUserPrincipal` only。
- 输出：显式 allow/deny 决策；通过时才允许进入后续 `project_code` 解析。
- 失败语义：非 `admin` 统一拒绝为 `403 EVIE_PROJECT_SCOPE_FORBIDDEN`；不得通过错误差异泄露项目存在性。
- 数据库读取：无；必须在任何 `TestProjectRepository` 查询前执行。
- 数据库写入：无。
- 事务责任：无。
- 可复用方：未来 EvieAi 列表、详情、历史和写接口。
- 授权依据：仅 `principal.role` 和 `principal.is_active`。
- 明确禁止：接收 ORM `User`；要求已解析 project；自行查询旧 Workbench 权限模型；查询数据库；查询 project；查询 membership；根据项目存在性分叉非 `admin` 响应；在授权层引入项目成员体系。

### 9.4 RequestActorContext

- 输入：`TrustedUserPrincipal` only。
- 输出：稳定 `actor_or_client_id = user:<user_public_id>`。
- 失败语义：缺失或非法 `user_public_id` 必须 fail closed。
- 数据库读取：无。
- 数据库写入：无。
- 事务责任：无。
- 可复用方：后续 Review、Audit、Source、Idempotency 和 Router 适配层。
- 明确禁止：接受 ORM `User`；接受客户端 `actor`；查询数据库；使用 `username`、`email`、内部 `User.id`、token 或 request body 兜底。

### 9.5 RequestChannelContext

- 输入：受信任 API adapter 的内部上下文。
- 输出：固定值 `api`。
- 失败语义：无法建立受信任 channel 时 fail closed。
- 数据库读取：无。
- 数据库写入：无。
- 事务责任：无。
- 可复用方：后续 Audit、Source 和 Idempotency。
- 明确禁止：读取请求正文中的 `channel`；接受客户端覆盖；为未批准的 channel 建立新枚举。

### 9.6 RequestTraceContext

- 输入：HTTP request、当前 `request_id` 上下文、受信任的内部调用元数据。
- 输出：可信 `request_id` 和内部 `correlation_id` 载体。
- 失败语义：内部上下文构造失败时 fail closed；不得默默相信客户端控制的相关性身份，也不得把缺少外部 metadata 解释为客户端 `400`。
- 数据库读取：无。
- 数据库写入：无。
- 事务责任：无。
- 可复用方：EvieAi HTTP adapter、logging guard、后续 Service/Audit。
- 明确禁止：发明新的外部 Header 合同；把客户端值直接当可信 `correlation identity`；为业务审计生成持久化写入。

### 9.7 EvieAi HTTP Error Adapter

- 输入：`EvieAiDomainError`、`HTTPException`、`RequestValidationError`、Unexpected Exception、request trace context、必要的 path metadata。
- 输出：稳定 HTTP status 和结构化 `EvieAi` error envelope。
- 失败语义：未知领域错误或未映射错误码时返回受控内部错误，不泄露堆栈、SQL、token、内部对象或请求正文。
- 数据库读取：无。
- 数据库写入：无。
- 事务责任：无；只做 transport adapter。
- 可复用方：未来 Slice 8 EvieAi Router。
- 适配边界：
  - `EvieAiDomainError`：按既有领域错误码和 HTTP 映射输出
  - `HTTPException`：仅当请求路径属于 `/api/evie-ai/` namespace 时进入 EvieAi adapter；其中 `401 → EVIE_AUTHENTICATION_REQUIRED + HTTP 401`，其他 `HTTPException` 保持其状态码或按已批准映射输出，但必须使用 EvieAi error envelope
  - `RequestValidationError`：仅当请求路径属于 `/api/evie-ai/` namespace 时映射为 `EVIE_REQUEST_VALIDATION_ERROR + HTTP 422`，`details` 使用受控结构化校验信息，不包含请求正文或敏感值
  - Unexpected Exception：仅当请求路径属于 `/api/evie-ai/` namespace 时映射为 `EVIE_DATA_INTEGRITY_ERROR + HTTP 500`
  - 非 EvieAi 路由保持原有 `HTTPException`、`RequestValidationError` 和通用异常行为
- 明确禁止：改写非 EvieAi 路由既有错误格式；无批准新增 error enum；把内部异常直接透传给客户端；创建生产 Router；创建测试用生产 endpoint；把 `request_id` 移到顶层。

### 9.8 Natural-language Logging Guard

- 输入：HTTP request path、method、content-type、body preview、trusted trace context。
- 输出：允许记录、脱敏记录或完全 suppress 的日志摘要。
- 失败语义：无法安全判断时默认不记录正文。
- 数据库读取：无。
- 数据库写入：无。
- 事务责任：无。
- 可复用方：`main.py` HTTP middleware 和后续 EvieAi API 接入层。
- 明确禁止：记录自然语言正文；记录 `Authorization`、`Cookie`、`token`、`secret`、`password`；破坏下游 body 重读；改变 multipart、non-JSON 或 streaming 请求语义；实现业务 endpoint。

## 10. 请求安全处理链

目标处理链固定为：

```text
JWT authentication
→ authenticated User
→ stable user_public_id validation
→ TrustedUserPrincipal
→ global admin authorization
→ explicit project scope normalization
→ project existence and active-state validation
→ actor context
→ channel context
→ request / correlation context
→ future Slice 6 or Slice 8 consumer
```

必须明确：

- Slice 5 到安全上下文形成即结束。
- Slice 5 不调用 Intake。
- Slice 5 不创建 `TestAsset`。
- Slice 5 不写业务 Audit、Source 或 Review。
- Slice 5 不自行 `commit`。

## 11. 错误语义与 HTTP 映射

| 场景 | Domain error code | HTTP status | 隐藏资源存在性 | 响应字段 | 合同依据 |
|---|---|---:|---|---|---|
| 未认证 / EvieAi namespace 下的 `HTTPException(401)` | `EVIE_AUTHENTICATION_REQUIRED` | 401 | N/A | 稳定 `error` envelope；`request_id` 位于 `error` 对象内部；仅用于无法形成 trusted authenticated `User` 的认证失败；保持既有 token 兼容 | A-09；现有 auth compatibility；S5-D03B approved decision |
| principal 缺少 `user_public_id` | `EVIE_DATA_INTEGRITY_ERROR` | 500 | N/A | `error.code`、`error.domain`、`error.stage`、`error.message`、`error.request_id` | A-11；P-09 |
| `user_public_id` 非法 | `EVIE_DATA_INTEGRITY_ERROR` | 500 | N/A | 同上 | A-11；P-09 |
| `project scope` 缺失 | `EVIE_REQUEST_VALIDATION_ERROR` | 422 | N/A | 稳定 `error` envelope + `error.request_id`；用于业务安全链之前的必需输入校验失败；不得退化为默认项目 | C-02；A-09；S5-D03B approved decision |
| `project_code` 非法 | `EVIE_REQUEST_VALIDATION_ERROR` | 422 | N/A | 稳定 `error` envelope + `error.request_id`；用于显式 `project_code` 格式非法等合同输入错误 | C-02；A-09；S5-D03B approved decision |
| admin 查询 project 不存在 | `EVIE_PROJECT_NOT_FOUND` | 404 | 对 `admin` 路径不需要额外隐藏；对非 `admin` 不应到达此分支 | 稳定 `error` envelope + `error.request_id` | A-02；A-09 |
| admin 查询 project inactive | `EVIE_PROJECT_INACTIVE` | 409 | 对 `admin` 路径不需要额外隐藏；对非 `admin` 不应到达此分支 | 稳定 `error` envelope + `error.request_id` | A-02；A-09 |
| 非 `admin` | `EVIE_PROJECT_SCOPE_FORBIDDEN` | 403 | Yes | 稳定 `error` envelope + `error.request_id`；不得泄露项目是否存在 | A-02；Specification §3.5.1 |
| channel 内部不变量失败 | `EVIE_DATA_INTEGRITY_ERROR` | 500 | Yes | 稳定 `error` envelope + `error.request_id`；不回显内部 channel 元数据 | A-02；channel approved semantics |
| request / correlation context 内部不变量失败 | `EVIE_DATA_INTEGRITY_ERROR` | 500 | Yes | 稳定 `error` envelope + `error.request_id`；`correlation_id` 保持 internal-only | Trace semantics；S5-D01 |
| EvieAi namespace 下的 `RequestValidationError` | `EVIE_REQUEST_VALIDATION_ERROR` | 422 | N/A | 受控结构化 `details` + `error.request_id`；不包含请求正文或敏感值 | C-05；A-09；path-scoped FastAPI validation adaptation |
| EvieAi namespace 下的未预期内部错误 | `EVIE_DATA_INTEGRITY_ERROR` | 500 | Yes | 受控错误 envelope + `error.request_id`；不暴露堆栈、SQL、token、内部对象或请求正文 | C-05；A-09；`AGENTS.md` §19 |

补充说明：

- 现有错误码优先复用；如仓库现状未包含批准名称，则 Slice 5 允许最小新增 `EVIE_AUTHENTICATION_REQUIRED` 和 `EVIE_REQUEST_VALIDATION_ERROR`。
- `EVIE_AUTHENTICATION_REQUIRED` 仅表示无法形成 trusted authenticated `User` 的认证失败，不用于已认证 `User` 的持久化身份不变量破坏。
- `EVIE_REQUEST_VALIDATION_ERROR` 仅用于业务安全链之前的合同输入校验失败，包括显式 `project_code` 缺失或格式非法。
- 已认证 `User` 的 `user_public_id` 缺失或非法继续使用 `EVIE_DATA_INTEGRITY_ERROR` + HTTP 500。
- 本次批准不授权新增任何 Slice 6、Slice 7、Slice 8 的业务错误码。
- `Specification` 已确定 `request_id` 位于 `error` 对象内部；Slice 5 计划中的 `EvieAiErrorBody / EvieAiErrorResponse` 必须与该结构对齐。
- `correlation_id` 当前只作为 internal-only 上下文；没有新的客户端 Header 合同，也没有“malformed metadata = 400”对外规则。
- `app/core/security.py` 和 `get_current_user` 保持不变；由 `main.py` 中的 path-scoped handler 适配现有异常来源。
- 所有 EvieAi 错误统一保持：

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {},
    "request_id": "..."
  }
}
```

## 12. 精确文件计划

### 新增文件

| 路径 | 内容 | 合同依据 | 依赖 | 所属任务 |
|---|---|---|---|---|
| `apps/web-ui-service/app/services/evie_ai/__init__.py` | Slice 5 安全前置组件导出 | A-02；A-11；P-09 | 现有 `app.services` 目录结构 | S5-T01～S5-T07 |
| `apps/web-ui-service/app/services/evie_ai/user_public_identity_service.py` | 认证后校验现有 `user_public_id` 并建立只读 `TrustedUserPrincipal` | A-11；P-09 | `app/models/user.py` | S5-T01 |
| `apps/web-ui-service/app/services/evie_ai/project_scope_service.py` | admin 通过后执行显式 project scope 规范化、存在性与 active 校验 | C-02；A-02 | `TestProjectRepository`；`TestProject` | S5-T03 |
| `apps/web-ui-service/app/services/evie_ai/project_access_authorizer.py` | 仅基于 `TrustedUserPrincipal` 的全局 `admin` 授权决策与防枚举规则 | A-02 | `TrustedUserPrincipal` | S5-T04 |
| `apps/web-ui-service/app/services/evie_ai/request_actor_context.py` | 基于 `TrustedUserPrincipal` 的 stable actor 规范化 | A-11；P-09 | `actor_identity_policy.py`；`TrustedUserPrincipal` | S5-T02 |
| `apps/web-ui-service/app/services/evie_ai/request_channel_context.py` | 固定可信 channel=`api` | A-02 | 无数据库依赖 | S5-T02 |
| `apps/web-ui-service/app/services/evie_ai/request_trace_context.py` | `request_id` / internal `correlation_id` context | Trace semantics | `shared_backend.observability`；`main.py` middleware | S5-T05 |
| `apps/web-ui-service/app/services/evie_ai/http_error_adapter.py` | EvieAi namespace 下的 `EvieAiDomainError`、`HTTPException`、`RequestValidationError` 和 Unexpected Exception 到 HTTP 响应映射 | C-05；A-09 | `app/errors/evie_ai.py`；`app/schemas/evie_ai/operations.py` | S5-T06 |
| `apps/web-ui-service/app/services/evie_ai/logging_guard.py` | EvieAi 自然语言日志 suppress/redact 策略 | C-03；`AGENTS.md` §§20-21 | `shared_backend/observability/logging.py` | S5-T07 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_service.py` | `UserPublicIdentityService` 单测 | A-11；P-09 | `pytest`；现有 `evie_ai` test pattern | S5-T01 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_scope_service.py` | scope 解析与 fail-closed 单测 | C-02；A-02 | `conftest.py`；`TestProject` fixtures | S5-T03 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_access_authorizer.py` | admin-only / no-enumeration 单测 | A-02 | principal fixtures | S5-T04 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_request_contexts.py` | actor/channel/trace 单测 | A-02；A-11 | new request context services | S5-T02；S5-T05 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_http_error_adapter.py` | error mapping 单测 | C-05；A-09 | `EvieAiDomainError` | S5-T06 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_logging_guard.py` | body redact/suppress 单测 | C-03 | `logging_guard.py` | S5-T07 |
| `apps/web-ui-service/tests/integration/evie_ai/test_evie_ai_api_security_contract.py` | FastAPI 层安全链集成验证；使用测试专用 app 或测试专用 route，不进入生产 Router 注册表 | C-02；C-03；C-05；A-02；A-09；A-11 | `main.py` 的通用 middleware / exception handling；dependency overrides | S5-T08 |

### 修改文件

| 路径 | 最小修改 | 合同依据 | 兼容风险 | 所属任务 |
|---|---|---|---|---|
| `apps/web-ui-service/app/main.py` | 为 EvieAi 路径接入 `RequestTraceContext`、`Natural-language Logging Guard` 和 path-scoped `EvieAiDomainError` / `HTTPException` / `RequestValidationError` handler；只允许通用 middleware / exception handling，不创建生产业务 endpoint 或测试探针 Router | C-03；C-05；A-09 | 中；涉及全局 middleware/handler 接线 | S5-T05；S5-T06；S5-T07 |
| `apps/web-ui-service/app/schemas/evie_ai/operations.py` | 对错误 envelope 做最小合同对齐，确保 `request_id` 位于 `error` 对象内部 | A-09；Specification §12 示例；S5-D03A | 中；需避免破坏既有 schema 测试 | S5-T06 |
| `apps/web-ui-service/app/errors/evie_ai.py` | 复用现有稳定错误码；如仓库现状未包含批准名称，则最小新增 `EVIE_AUTHENTICATION_REQUIRED` 和 `EVIE_REQUEST_VALIDATION_ERROR` | A-09；S5-D03B approved decision | 中；不得新增其他未批准错误码 | S5-T06 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py` | 扩展现有 auth 兼容测试，覆盖 stable principal / actor 绑定 | A-11；P-09 | 低 | S5-T01；S5-T02 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_schemas.py` | 同步 schema 断言，确保 `request_id` 位于 `error` 对象内部 | A-09；S5-D03A | 低至中 | S5-T06 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py` | 增加 Slice 5 守卫，禁止默认 project、auto-create、client actor/channel、Intake/Compiler/Runner 越界 | Slice 5 static guard requirements | 低 | S5-T08 |

不计划修改以下已核实文件：

- `apps/web-ui-service/app/routers/auth.py`
- `apps/web-ui-service/app/core/security.py`
- `apps/web-ui-service/app/services/test_project_service.py`
- `apps/web-ui-service/app/services/workbench_project_service.py`
- `apps/web-ui-service/app/models/user.py`
- `apps/web-ui-service/app/models/test_project.py`
- `apps/web-ui-service/app/repositories/test_project_repository.py`
- `shared_backend/observability/logging.py`

原因：

- 它们分别承载当前旧 `seed` / auto-create 语义、既有 ORM 事实源、现有 Repository 事实源和通用日志工具；
- `auth.py` 当前已经满足注册生成合法 `user_public_id`、JWT `sub=User.id` 和 `UserRead` 外显公共身份的兼容事实；
- `app/core/security.py` 当前已经负责 authenticated `User` 建立和 active 校验；Slice 5 不改写 `get_current_user`；
- Slice 5 应尽量通过新 adapter/service 层隔离旧行为，而不是扩大为全平台 auth / project / logging 重构。

## 13. 任务拆分

### S5-T01：稳定 `TrustedUserPrincipal` 与 `user_public_id`

- 目标：让 authenticated `User` 经过现有 `user_public_id` 校验后形成只读 `TrustedUserPrincipal`，并保持 JWT `sub` 兼容。
- 合同依据：A-11；P-09；Overall Plan Slice 5。
- 前置依赖：无。
- 新增文件：`app/services/evie_ai/user_public_identity_service.py`；`tests/unit/evie_ai/test_evie_ai_user_public_identity_service.py`
- 修改文件：`tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py`
- 实现要求：
  - 输入必须是 authenticated `User`；
  - 只读取现有 `user_public_id`；
  - 校验非空和格式合法；
  - 输出 `TrustedUserPrincipal`；
  - `TrustedUserPrincipal` 仅包含 `user_public_id`、`role`、`is_active`；
  - 不改 JWT `sub`；
  - 不引入全平台认证重构；
  - 不生成、不修改、不持久化 `user_public_id`。
- 明确禁止：
  - 生成新的 `user_public_id`；
  - 修改 `User`；
  - 额外数据库读取；
  - 数据库写入；
  - 客户端输入 `user_public_id`。
- 测试：
  - authenticated `User` 可生成 `TrustedUserPrincipal`；
  - 缺失或非法 `user_public_id` fail closed；
  - 注册路径继续生成合法 `usr_<uuid4hex32>`；
  - 兼容现有 token `sub=User.id`；
  - `UserRead` 继续返回 `user_public_id`；
  - 非法 public identity 时不能形成 `TrustedUserPrincipal`；
  - 不暴露内部 `User.id`。
- 验收：
  - authenticated `User` → existing `user_public_id` validation → `TrustedUserPrincipal`；
  - 兼容行为不回退。
- 完成证据：单测通过、auth 兼容测试更新、`auth.py` 保持未修改。
- 是否可独立提交：Yes

### S5-T02：Actor / Channel Context

- 目标：建立 stable actor 和 trusted channel。
- 合同依据：A-02；A-11。
- 前置依赖：S5-T01。
- 新增文件：`request_actor_context.py`；`request_channel_context.py`；`tests/unit/evie_ai/test_evie_ai_request_contexts.py`
- 修改文件：`tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py`
- 实现要求：
  - `RequestActorContext` 只接收 `TrustedUserPrincipal`；
  - actor 固定 `user:<user_public_id>`；
  - channel 固定 `api`；
  - 客户端不能覆盖。
- 明确禁止：
  - 接收 ORM `User`；
  - 使用 `username`、`email`、内部 PK；
  - 从请求正文读取 channel。
- 测试：
  - actor 规范化；
  - 非法或缺失 public id fail closed；
  - ORM `User` 不能直接进入 `RequestActorContext`；
  - `Actor Context` 只接受 `TrustedUserPrincipal`；
  - channel 恒定为 `api`。
- 验收：
  - 无 client-controlled actor/channel；
  - 历史字段未来可直接复用。
- 完成证据：单测、现有 identity policy 回归。
- 是否可独立提交：Yes

### S5-T03：ProjectScopeService

- 目标：在 global admin 授权通过后，建立显式、只读、fail-closed 的 project scope 规范化与项目状态校验。
- 合同依据：C-02；A-02。
- 前置依赖：S5-T04。
- 新增文件：`project_scope_service.py`；`tests/unit/evie_ai/test_evie_ai_project_scope_service.py`
- 修改文件：无生产旧文件计划内强制修改。
- 实现要求：
  - 只在 admin 校验通过后调用；
  - 读取现有 `TestProject`；
  - 必须显式 project；
  - 校验 active；
  - 不写数据库；
  - 不把 principal 当作项目存在性查询前置替代。
- 明确禁止：
  - `ensure_project_seed()`；
  - `get_project_status()` 的默认 active 回退；
  - `ensure_project_writable()` 的 auto-create；
  - 负责全局角色授权。
- 测试：
  - 合法 active project；
  - admin 路径下的缺失、非法、不存在、inactive；
  - 无默认 `mall`；
  - 无写数据库；
  - 只有 admin 能进入 project not found / inactive 分支。
- 验收：
  - 所有非法 scope 都 fail closed；
  - 不触发 seed 或 auto-create。
- 完成证据：scope 单测、Repository 调用痕迹、与授权前置顺序一致。
- 是否可独立提交：Yes

### S5-T04：ProjectAccessAuthorizer

- 目标：建立在任何项目查询前执行的 admin-only 授权和防枚举拒绝逻辑。
- 合同依据：A-02；Specification §3.5.1。
- 前置依赖：S5-T02。
- 新增文件：`project_access_authorizer.py`；`tests/unit/evie_ai/test_evie_ai_project_access_authorizer.py`
- 修改文件：无。
- 实现要求：
  - `ProjectAccessAuthorizer` 只接收 `TrustedUserPrincipal`；
  - 首版只允许全局 admin；
  - 非 admin 统一 `403 EVIE_PROJECT_SCOPE_FORBIDDEN`；
  - 不暴露项目存在性；
  - 在任何 `TestProjectRepository.get_by_code()` 查询前执行；
  - 不读取数据库；
  - 授权依据仅 `principal.role` 和 `principal.is_active`。
- 明确禁止：
  - 接收 ORM `User`；
  - 引入项目成员体系；
  - 根据项目存在性分叉非 admin 响应；
  - 要求已解析 project 才能授权。
- 测试：
  - admin allow 进入后续 scope 解析；
  - non-admin 对存在、不存在、inactive 的 `project_code` 均返回相同 `403`；
  - non-admin 调用时 `TestProjectRepository.get_by_code()` 未被调用；
  - ORM `User` 不能直接进入 `ProjectAccessAuthorizer`；
  - `Authorizer` 只接受 `TrustedUserPrincipal`。
- 验收：
  - 首版权限语义稳定；
  - 不泄露项目存在性；
  - 先授权、后查项目的顺序成立。
- 完成证据：授权单测、Repository 未调用断言。
- 是否可独立提交：Yes

### S5-T05：RequestTraceContext

- 目标：把 `request_id` 和内部 `correlation_id` 整理为可信上下文。
- 合同依据：Trace approved semantics；Specification §12。
- 前置依赖：S5-T02。
- 新增文件：`request_trace_context.py`
- 修改文件：`app/main.py`；`tests/unit/evie_ai/test_evie_ai_request_contexts.py`
- 实现要求：
  - 复用现有 `request_id`；
  - 不发明新外部 Header；
  - 仅建立内部 trace carrier。
- 明确禁止：
  - 客户端可信 `correlation identity`；
  - 业务持久化写入；
  - 因缺少外部 metadata 返回客户端 `400`。
- 测试：
  - `request_id` 透传/生成；
  - internal-only `correlation_id`；
  - 内部上下文构造失败时受控失败；
  - 非 EvieAi 路由不受影响。
- 验收：
  - 可被 error adapter 和 logging guard 复用；
  - 不改变现有 `X-Request-Id` 行为。
- 完成证据：trace 单测和集成测试。
- 是否可独立提交：Yes

### S5-T06：EvieAi HTTP Error Adapter

- 目标：对 EvieAi namespace 下的 `EvieAiDomainError`、`HTTPException`、`RequestValidationError` 和未预期异常执行 path-scoped 结构化 HTTP 适配。
- 合同依据：C-05；A-09；D-11 / Spec §12。
- 前置依赖：S5-T03；S5-T04；S5-T05。
- 新增文件：`http_error_adapter.py`；`tests/unit/evie_ai/test_evie_ai_http_error_adapter.py`
- 修改文件：`app/main.py`；`app/schemas/evie_ai/operations.py`；`app/errors/evie_ai.py`（如仓库现状未包含批准名称，则最小新增稳定错误码）；`tests/unit/evie_ai/test_evie_ai_schemas.py`
- 实现要求：
  - 保持既有非 EvieAi 路由错误行为；
  - 不修改 `app/core/security.py`；
  - 不改写 `get_current_user`；
  - 由 `main.py` 中 path-scoped handler 适配现有异常来源；
  - 为 EvieAi 路径输出稳定 envelope、status 和 `error.request_id`；
  - 覆盖 EvieAi namespace 下的 `EvieAiDomainError`、`HTTPException`、`RequestValidationError` 和 Unexpected Exception；
  - 对 `401` 使用 `EVIE_AUTHENTICATION_REQUIRED`；
  - 对 `422` 使用 `EVIE_REQUEST_VALIDATION_ERROR`；
  - 已认证 `User` 的 `user_public_id` 缺失或非法继续映射为 `EVIE_DATA_INTEGRITY_ERROR` + `500`；
  - 不新增未经批准 error enum。
- 明确禁止：
  - 把自由 `detail` 当最终 EvieAi 合同；
  - 直接暴露内部异常；
  - 改变非 EvieAi 路由的 `HTTPException` 或 FastAPI validation 行为。
- 测试：
  - 稳定 error code / stage / `error.request_id`；
  - 401/403/404/409/422/500；
  - EvieAi namespace 下的 `HTTPException` / `RequestValidationError` 适配；
  - 旧路由不回归。
- 验收：
  - 结构化错误成立；
  - Slice 5 不把冻结失败写成通过。
- 完成证据：adapter 单测、integration error contract 测试，以及 EvieAi namespace 下 `HTTPException` / `RequestValidationError` / Unexpected Exception 的 path-scoped 适配证据。
- 是否可独立提交：Yes

### S5-T07：Natural-language Logging Guard

- 目标：阻止自然语言正文进入日志，同时保留请求兼容性。
- 合同依据：C-03；`AGENTS.md` §§20-21。
- 前置依赖：S5-T05。
- 新增文件：`logging_guard.py`；`tests/unit/evie_ai/test_evie_ai_logging_guard.py`
- 修改文件：`app/main.py`
- 实现要求：
  - EvieAi 路径 suppress 或 redacted body preview；
  - 保持 body 可重复读取；
  - 兼容 JSON、multipart、non-JSON、streaming；
  - 只基于已批准的 `/api/evie-ai/` namespace 做日志判定，不实现业务 endpoint。
- 明确禁止：
  - 记录自然语言正文；
  - 破坏请求体；
  - 扩大为全站日志系统重写。
- 测试：
  - payload suppress/redact；
  - secret redact；
  - body replay；
  - 非 EvieAi 路由不变。
- 验收：
  - 不泄露正文；
  - 不引入新请求兼容问题。
- 完成证据：logging guard 单测和 integration 验证。
- 是否可独立提交：Yes

### S5-T08：兼容性、架构守卫与回归验证

- 目标：补齐 Slice 5 相关 guard、兼容性和冻结 CI 对比规则。
- 合同依据：Slice 5 static guard；`phase-traceability` current status；CI-B01/CI-B02 baseline rules。
- 前置依赖：S5-T01～S5-T07。
- 新增文件：`apps/web-ui-service/tests/integration/evie_ai/test_evie_ai_api_security_contract.py`
- 修改文件：`tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py`
- 实现要求：
  - Guard 防 Candidate/Compiler/Runner/Intake/default project/auto-create/client actor/channel 越界；
  - 记录 138 passed 回归和 CI-B01/CI-B02 基线对比方法；
  - integration test 使用测试专用 FastAPI app 或测试专用 route；
  - 测试 route 只存在于测试文件，不进入生产 Router 注册表；
  - 不注册 `/api/evie-ai/test-assets`，不进入 Slice 8。
- 明确禁止：
  - 修改冻结 CI 失败路径；
  - 把 CI-B01/CI-B02 写成通过；
  - 开始 Slice 6/8 业务实现。
- 测试：
  - Slice 5 targeted tests；
  - auth compatibility；
  - 138 项回归；
  - 冻结基线差异比较。
- 验收：
  - 无新增失败；
  - 既有失败不扩大；
  - 无越界依赖。
- 完成证据：测试报告、基线差异报告、Git 审计。
- 是否可独立提交：Yes

## 14. 测试与基线比较计划

所有命令一律使用：

```text
.venv/bin/python -m pytest
```

不得使用普通 `python`。

### 14.1 测试矩阵

| 测试文件 | 测试层级 | 测试对象 | 正向场景 | 失败场景 | 合同依据 |
|---|---|---|---|---|---|
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_service.py` | Unit | `UserPublicIdentityService` | authenticated `User` 通过现有 `user_public_id` 校验并形成 `TrustedUserPrincipal` | 缺失 public id；非法 public id；不能形成 `TrustedUserPrincipal` | A-11；P-09 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_scope_service.py` | Unit | `ProjectScopeService` | admin 校验通过后的合法显式 `project_code`；active project | 缺失；非法；不存在；inactive；无默认 `mall`；不调用 seed；不写数据库 | C-02；A-02 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_access_authorizer.py` | Unit | `ProjectAccessAuthorizer` | `admin` allow 并进入后续 scope 解析；仅接受 `TrustedUserPrincipal` | non-admin 对存在/不存在/inactive `project_code` 均统一 403；`TestProjectRepository.get_by_code()` 未被调用；ORM `User` 不可直接输入；不泄露存在性 | A-02 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_request_contexts.py` | Unit | `RequestActorContext`、`RequestChannelContext`、`RequestTraceContext` | actor=`user:<user_public_id>`；channel=`api`；可信 `request_id`；`RequestActorContext` 仅接受 `TrustedUserPrincipal` | 缺失/非法 public id；ORM `User` 直接输入；client actor；client channel；internal-only trace context failure；external correlation trust | A-02；A-11 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_http_error_adapter.py` | Unit | `EvieAi HTTP Error Adapter` | 稳定 envelope；稳定 status；`request_id` 位于 `error` 对象内部；`401 → EVIE_AUTHENTICATION_REQUIRED`；`422 → EVIE_REQUEST_VALIDATION_ERROR`；EvieAi namespace 下 `HTTPException` / `RequestValidationError` 受控适配 | 未认证；public id 缺失/非法；scope 错误；未知内部错误；不泄露堆栈、SQL、token 或请求正文 | C-05；A-09 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_logging_guard.py` | Unit | `Natural-language Logging Guard` | JSON body suppress/redact；secret redact | 自然语言正文泄露；multipart/non-JSON/streaming 被破坏；下游无法重读 body | C-03；`AGENTS.md` §§20-21 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py` | Unit | auth compatibility | JWT `sub` 继续兼容；`UserRead` 继续返回 `user_public_id`；客户端输入不覆盖服务端身份 | 客户端提交的 `user_public_id` 影响持久化结果；`actor_or_client_id` 进入安全上下文；内部 `id` 外泄 | A-11；P-09 |
| `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py` | Static / Unit | Slice 5 架构守卫 | 仅依赖批准路径；不碰旧链 | default project；auto-create；client actor/channel；Intake/Compiler/Runner 越界 | Slice 5 static guard |
| `apps/web-ui-service/tests/integration/evie_ai/test_evie_ai_api_security_contract.py` | Integration | 测试专用 FastAPI app / route + middleware + handler + `TrustedUserPrincipal` chain | auth compatibility；scope success；error envelope；logging guard；body replay；无生产 Router 注册 | 未认证；非 admin；project missing/inactive；internal context failure；旧路由不变 | C-02；C-03；C-05；A-02；A-09；A-11 |

### 14.2 必须覆盖的场景

#### Identity

- JWT `sub` 兼容
- principal 暴露 `user_public_id`
- 缺失和非法身份 fail closed
- 非法 public identity 不能形成 `TrustedUserPrincipal`
- actor 只能是 `user:<user_public_id>`
- 客户端不能伪造 actor
- 注册继续生成 `user_public_id`
- 客户端输入的 `user_public_id` 不能覆盖服务端身份
- `actor_or_client_id` 不进入任何安全上下文

#### Project scope

- 合法显式 `project_code`
- 缺失
- 非法
- 不存在
- inactive
- 无默认 `mall`
- 不调用 seed
- 不调用 auto-create
- 不写数据库

#### Authorization

- `admin` 允许
- 未认证由上游 auth 层 `401` 拒绝
- 非 `admin` 拒绝
- 非 `admin` 对存在、不存在、inactive `project_code` 返回相同 `403`
- non-admin 调用时 `TestProjectRepository.get_by_code()` 不被调用
- `ProjectAccessAuthorizer` 只接受 `TrustedUserPrincipal`
- ORM `User` 不能直接进入 `ProjectAccessAuthorizer`
- 不泄露存在性

#### Channel / Trace

- channel 固定 `api`
- 客户端不能覆盖
- `request_id`
- `correlation_id` 不依赖未批准 Header
- `RequestActorContext` 只接受 `TrustedUserPrincipal`
- ORM `User` 不能直接进入 `RequestActorContext`
- 内部上下文构造失败受控失败

#### Error mapping

- 稳定 envelope
- HTTP status
- error code
- stage
- `request_id` 位于 `error` 对象内部
- `401 → EVIE_AUTHENTICATION_REQUIRED`
- `422 → EVIE_REQUEST_VALIDATION_ERROR`
- 已认证 `User` 缺失/非法 `user_public_id` 继续 `500 → EVIE_DATA_INTEGRITY_ERROR`
- EvieAi namespace 下的 `HTTPException` 使用 path-scoped envelope 适配
- EvieAi namespace 下的 `RequestValidationError` 使用受控结构化 `details`
- 不泄露内部异常
- 非 EvieAi 路由不变

#### Logging

- 自然语言正文不入日志
- `Authorization`、`Cookie`、`token`、`secret`、`password` 不入日志
- body 下游仍可读
- multipart、non-JSON、streaming 不被破坏

#### Regression

必须区分：

1. Slice 5 针对性测试；
2. auth / middleware 兼容测试；
3. Slice 1～4 的 138 项测试；
4. 冻结 `CI-B01` 和 `CI-B02` 对比；
5. 较大范围回归。

### 14.3 验收规则

- `138` 项必须继续全部通过。
- `CI-B01` 和 `CI-B02` 可以保持相同失败签名。
- 不允许新增失败。
- 不允许既有失败数量扩大。
- 不允许失败签名迁移到 Slice 5 路径。
- CI 全绿不是当前 Slice 5 可独立保证的条件。
- Slice 5 Closeout 必须提供基线差异报告。

### 14.4 精确测试命令

- 以下命令只在 Slice 5 实施阶段执行。
- 本次计划补正不执行测试。
- 所有命令必须使用 `.venv/bin/python -m pytest`。
- 不使用普通 `python`。
- 新增测试文件在实施完成前可能尚不存在。
- 实施时必须按以下顺序执行。
- 前一层失败时停止，不自动扩大修复范围。

#### 14.4.1 Slice 5 针对性测试

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_service.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_access_authorizer.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_project_scope_service.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_request_contexts.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_http_error_adapter.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_logging_guard.py \
  apps/web-ui-service/tests/integration/evie_ai/test_evie_ai_api_security_contract.py
```

验收：

- 全部 collected。
- `0 failed`。
- `0 errors`。
- `0 skipped`，除非测试本身具有经批准的平台条件。
- 不得把“测试文件不存在”归类为通过。

#### 14.4.2 Auth、Schema 与架构兼容测试

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_schemas.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py
```

验收：

- JWT `sub=User.id` 兼容。
- 注册链继续生成服务端 `user_public_id`。
- 客户端 identity 字段不能覆盖服务端身份。
- `error.request_id` Schema 通过。
- Slice 5 静态边界通过。
- `auth.py` 和 `core/security.py` 保持未修改。

#### 14.4.3 Slice 1 Group A 回归

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_ids.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_constants.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_content_fingerprint.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_request_fingerprint.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_review_policy.py
```

预期：

- `37 passed`

#### 14.4.4 Slice 2 Group B 回归

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_models.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_schemas.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_user_public_identity_compat.py
```

预期：

- `52 passed`

说明：

- 若 Slice 5 合法增加了这些既有文件中的测试数量，collected 数量可以高于历史 `52`。
- 历史 `52` 个测试必须继续全部通过。
- 新增测试也必须通过。
- 不得机械要求总数仍恰好等于 `52`。

#### 14.4.5 Slice 4 Group C 回归

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_repositories.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_source_repository.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_coordination_repositories.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_governance_repositories.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_query_repository.py
```

预期：

- `39 passed`

#### 14.4.6 Slice 3 Group D 回归

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_phase1_migration.py \
  apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_migration.py
```

预期：

- `10 passed`

明确：

- 不手工运行 Alembic。
- 只允许测试使用自己的临时数据库。
- 不操作 `dev.db`。

#### 14.4.7 Slice 1～4 历史 138 项判定

- Group A 的历史 `37` 项必须通过。
- Group B 的历史 `52` 项必须通过。
- Group C 的历史 `39` 项必须通过。
- Group D 的历史 `10` 项必须通过。
- 历史基线合计 `138` 项不得回归。
- Slice 5 对既有测试文件增加新测试时，总 collected 数量可以超过 `138`。
- `138` 项继续通过不等于最终总测试数必须恰好为 `138`。
- 所有 Slice 5 新增测试也必须通过。
- The historical Slice 1–4 baseline of 138 tests must remain passing, and all newly added Slice 5 tests must also pass.

### 14.5 冻结 CI 基线比较命令

#### 14.5.1 CI-B01

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/test_workbench_facade.py
```

比较字段：

- `collected`
- `failed`
- error node IDs
- exception type
- import failure signature
- 第一处项目路径

冻结签名：

- `8 failures`
- `app.api.workbench.facade.test_case_service import failure`

判定：

- 完全一致：`Existing baseline failure`
- 数量增加、节点增加或签名变化：`New regression`
- 失败消失：`Resolved baseline failure`
- 无法确认：停止

#### 14.5.2 CI-B02

```bash
.venv/bin/python -m pytest -q \
  apps/ai-orchestrator/tests/integration/test_app_flask_client.py
```

冻结签名：

- collection failure
- `apps/ai-orchestrator/src/app.py missing`

比较：

- collection stage
- error type
- missing path
- traceback first project frame

不得为了执行此命令：

- 安装额外依赖
- 创建缺失 `app.py`
- 修改 import path
- 修改冻结失败文件
- 把冻结失败写成通过

### 14.6 最终较大范围回归

第一层：

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit/evie_ai \
  apps/web-ui-service/tests/integration/evie_ai
```

验收：

- Slice 1～5 范围全部通过。
- 不允许新增 failed、error 或未经批准的 skip。

第二层仅在第一层通过后执行：

```bash
.venv/bin/python -m pytest -q \
  apps/web-ui-service/tests/unit
```

说明：

- 该命令预期仍可能包含 `CI-B01`。
- 必须输出“冻结失败与新增失败”的差异报告。
- 不要求 Slice 5 修复 `CI-B01`。
- 除冻结签名外不得出现新增失败。

`ai-orchestrator` 的 `CI-B02` 使用 §14.5.2 单独复现，不得把其收集失败混入 `web-ui-service` 的结果统计。

### 14.7 测试执行顺序

顺序固定为：

```text
Slice 5 targeted
→ auth/schema/architecture compatibility
→ Group A
→ Group B
→ Group C
→ Group D
→ CI-B01 comparison
→ CI-B02 comparison
→ EvieAi larger regression
→ web-ui-service unit regression
```

停止规则：

- Slice 5 targeted 失败：停止
- auth/schema compatibility 失败：停止
- 历史 `138` 项任一回归：停止
- 出现新的 CI 失败：停止
- 冻结失败签名变化：停止并标记无法判断或新回归
- 不得自动修改代码
- 不得扩大到无关路径
- 不得把 rerun 后偶然通过作为根因解决证据

## 15. 静态架构守卫

Slice 5 规划的守卫重点如下：

- 不依赖 Candidate
- 不依赖 `TestPointAsset`
- 不调用 Compiler
- 不调用 Runner
- 不调用 Intake
- 不创建 `TestAsset`
- 不写业务 `AuditEvent`
- 不使用默认 `project_code`
- 不调用项目 auto-create
- actor 不来自客户端
- channel 不来自客户端
- `RequestActorContext` 不接收 ORM `User`
- `ProjectAccessAuthorizer` 不接收 ORM `User`
- 下游只接收 `TrustedUserPrincipal`
- 不新增 Migration
- 不新增业务 Router
- 不创建生产 Router 探针
- 不注册 `/api/evie-ai/test-assets`
- 不进入 Upload Security
- 不修改 `app/core/security.py`
- 不修改冻结 CI 失败涉及的旧 Workbench 和 `ai-orchestrator` 路径

建议把这些守卫落到：

- `apps/web-ui-service/tests/unit/evie_ai/test_evie_ai_architecture_boundaries.py`
- `apps/web-ui-service/tests/integration/evie_ai/test_evie_ai_api_security_contract.py`

## 16. 验收标准

### 16.1 静态验收

- 组件职责单一
- 无默认 project
- 无 auto-create
- 无客户端 actor/channel
- 只读 `TrustedUserPrincipal` 边界成立
- 无 ORM `User` 直接流入下游安全组件
- 无内部 `User.id` 写入 actor
- 无 Slice 6/7/8 越界
- 无 Candidate
- 无 ORM/Migration
- 无新业务 API
- 无生产 Router 探针
- 无 `/api/evie-ai/test-assets`
- 无 Phase 2
- 无敏感日志
- 文件范围符合批准计划

### 16.2 动态验收

- Slice 5 新测试通过
- auth compatibility 通过
- authorization 先于项目解析通过
- scope 和 authorization 通过
- error mapping 通过
- EvieAi namespace 下的 HTTPException、RequestValidationError 适配通过
- logging guard 通过
- 非 EvieAi 路由异常行为不变
- body 重读及 multipart/non-JSON/streaming 兼容
- 精确命令已按 §14.4～§14.7 执行
- 历史 `138` 项继续通过
- Slice 5 新增测试全部通过
- 总 collected 可以高于 `138`
- `CI-B01` 和 `CI-B02` 已按冻结签名比较
- 除冻结失败外无新增失败
- 较大范围回归已完成
- 无新的全仓失败

### 16.3 Git 验收

- 实施分支从计划 PR 合入后的最新 `dev HEAD` 创建
- 不混入个人文件
- 不混入缓存或数据库
- 不混入无关文档
- 不修改冻结失败路径
- 每个提交符合任务边界

## 17. 风险与待决策项

| ID | 问题 | 当前事实 | 合同状态 | 推荐处理 | 是否阻塞 |
|---|---|---|---|---|---|
| S5-D01 | `correlation_id` 是否存在外部合同 | 当前只批准“内部上下文”；未批准新的外部 Header | 外部传输未决；内部-only 已批准 | Slice 5 保持 internal-only；不得新增外部 Header | No |
| S5-D02 | `project_code` 的最终 HTTP 位置 | Overall Plan 在 Slice 8 才固定不同 API 的 transport 位置；本 Slice 明确 transport-agnostic | 运输层未来已规划；本 Slice 不决定 | Slice 5 只实现 service-level validation，HTTP 位置留到 Slice 8 | No |
| S5-D03A | `request_id` 字段位置 | Specification 已确定 `request_id` 位于 `error` 对象内部；计划需与 schema 对齐 | Resolved | 按 `error.request_id` 实施；不再作为待决项 | No |
| S5-D03B | `401` 和 `422` 的稳定 error code 名称 | 用户已明确批准：`401 → EVIE_AUTHENTICATION_REQUIRED`；`422 → EVIE_REQUEST_VALIDATION_ERROR`；已认证 `User` 缺失/非法 `user_public_id` 保持 `500 → EVIE_DATA_INTEGRITY_ERROR` | Approved | 复用现有错误码；如仓库现状未包含批准名称，则最小新增；不得扩展到 Slice 6/7/8 业务错误码 | No |
| S5-D04 | 日志保护接入方式 | 当前 `main.py` 是全局 HTTP middleware，读取并记录 body preview；`shared_backend` 仅做 key-based redact | 目标已批准，接入点未定 | 优先选择 path-scoped guard，最小修改 `main.py`，不重写通用 logging 框架 | No |
| S5-D05 | auth 测试 stub 兼容 | 现有 auth compatibility 测试通过 monkeypatch Router/DB；还没有 `TrustedUserPrincipal` + scope 专用 fixture | 开放实现细节 | 扩展现有 `evie_ai` fixture 和 auth compat 测试，避免改写无关测试 | No |
| S5-D06 | 冻结 CI 失败的差异比较方式 | `CI-B01` / `CI-B02` 已有 check、路径、数量和签名；但仓库尚未有 Slice 5 专用差异报告模板 | Closeout 证据方法未定 | 以 workflow/check + 文件路径 + 数量 + failure signature 建立冻结基线，对比新增失败和签名变化 | No |

## 18. 实施顺序

实施顺序固定为：

```text
计划已批准
→ 计划 PR 合入 dev
→ 从最新 dev 创建 Slice 5 实施分支
→ S5-T01
→ S5-T02
→ S5-T04
→ S5-T03
→ S5-T05
→ S5-T06
→ S5-T07
→ S5-T08
→ Slice 5 针对性测试
→ Slice 1～4 138 项回归
→ 冻结 CI 基线差异比较
→ Git 范围审计
→ 实施证据更新
→ 用户验收
```

- 必须明确：

- 在计划 PR 合入 `dev` 前不得创建实施分支。
- 必须先将计划 PR 合入 `dev`，再从最新 `dev` 创建 Slice 5 实施分支。
- 尽量按任务独立提交。
- 不混入 Slice 6/8。
- 不自动扩大失败修复范围。
- 合并前和合并后均需要验证。

## 19. 回滚策略

若 Slice 5 实施后需要回滚，策略固定为：

- 回滚 Slice 5 提交
- 恢复 dependency wiring
- 恢复 exception handler
- 恢复 logging middleware
- 保持 `User.user_public_id` 和 Slice 1～4 数据结构
- 不执行数据库 downgrade
- 不操作业务数据
- 回滚后运行 auth、Slice 1～4 和冻结基线对比

## 20. 完成定义

只有以下条件全部满足，Slice 5 才可完成：

- 计划经用户批准
- `S5-T01`～`S5-T08` 完成
- 批准文件全部完成
- 新增测试通过
- auth、scope、authorization、actor/channel、trace、error、logging 通过
- 精确命令已按 §14.4～§14.7 执行
- 历史 Slice 1～4 基线 `138` 项继续通过
- Slice 5 新增测试全部通过
- 总 collected 可以高于 `138`
- `CI-B01`、`CI-B02` 已完成冻结签名比较且未增加或变化为新回归
- 较大范围回归完成
- 无 Candidate/Compiler/Runner
- 无 Slice 6/7/8 越界
- 无 ORM/Migration
- Git 审计通过
- 合并后 `dev` 复验
- `phase-traceability` 更新
- 用户明确批准 Closeout

## 21. 实施与合并记录（2026-07-27）

本节是 Slice 5 的当前实施证据记录，并取代本文中计划制定时的 `Not started` 状态表述。
它只确认已批准 Slice 5 的实现与合并结果，不宣布 Phase 1 完成、Closeout 完成或开始 Slice 6。

| 项目 | 当前记录 |
|---|---|
| Slice 5 implementation | Completed |
| Slice 5 targeted validation | Passed (`56 passed`) |
| Regression attribution | `0 new regressions` |
| Merge status | Merged into `dev` |
| Pull Request | [PR #14](https://github.com/Chloeqq/ai-test-platform/pull/14) |
| Slice 5 implementation commit | `5186687b641e3fb2d8c93b3b54e2584d58ced789` |
| Merge commit on `dev` | `bd08b802cdb28c9ffc688cc39823af2c65fa6c3a` |
| Phase 1 overall status | In Progress |
| Phase 1 closeout status | Not completed |

验证与回归归因记录：

- Slice 5 targeted validation：`56 passed`。
- EvieAi unit + integration：`215 passed`。
- 完整 web-ui unit：当前 Slice 5 工作区为 `703 collected, 671 passed, 32 failed`；干净基线
  `8f28f181` 为 `650 collected, 618 passed, 32 failed`。
- 两侧的 32 个失败均复现为相同失败签名；本次归因确认 `0 new regressions`。
- `CI-B01` 仍是已知基线失败：8 个 Workbench facade 测试因缺少
  `app.api.workbench.facade.test_case_service` 失败。
- `CI-B02` 仍是已知基线失败：`apps/ai-orchestrator/src/app.py` 缺失导致 collection failure。
- `git diff --check` 已在实施分支与本次文档收口分支分别执行；本节不把已知基线失败写作通过。

范围确认：

- 本次记录未修改 Slice 5 合同边界，也未修改 Phase 0/1 范围。
- Slice 6 及后续 Slice 仍未开始；本记录不构成其实施授权。
