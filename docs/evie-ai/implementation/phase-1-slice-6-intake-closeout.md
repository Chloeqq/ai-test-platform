# EvieAi Phase 1 Slice 6 Intake Closeout

日期：2026-07-29

状态：Completed

Slice 6 contract status: Accepted / Completed

Slice 6 implementation status: Completed

Slice 6 validation status: Passed

Slice 6 regression status: 0 new regressions

Slice 6 merge status: Completed

Slice 6 closeout status: Completed

Phase 1 overall status: In Progress

Phase 1 closeout status: Not completed

Slice 7 status: Not started

Slice 8 status: Not started

## 1. Scope

本报告收口 [Slice 6 Intake 实施计划](phase-1-slice-6-intake-plan.md)定义的
`TestAssetIntakeService` 能力，并记录计划、实现、质量治理、阻塞修复、测试和合并证据。

本 Closeout 只证明 Slice 6 已完成，不代表 Phase 1 已完成，不批准 Slice 7/8，也不改变
`AGENTS.md`、Phase 1 合同或
[Architecture Baseline](../ARCHITECTURE_BASELINE.md)定义的架构边界。

## 2. Delivered Capabilities

| 能力 | Closeout 结果 |
|---|---|
| 统一入口 | `TestAssetIntakeService` 是 Manual 和 Requirement 来源资产创建的唯一公开 Intake 入口。 |
| 可信上下文 | 使用可信 principal、project、actor、channel 和 trace 上下文；客户端不能覆盖权威身份或作用域。 |
| Requirement 来源 | 使用 Requirement 和 RequirementVersion 公开 ID，并验证父子关系、软删除和项目归属。 |
| 聚合事务 | Asset、Version、Source、Requirement Source、Content Claim、Audit 和 Idempotency 共同提交或共同回滚。 |
| 初始版本 | 创建完成后的数据库事实和返回结果均保持 `row_version = 1`。 |
| 后续 CAS | 创建期首版本绑定不推进 row version；后续 `set_current_version()` 按 `1 -> 2` 推进。 |
| 幂等 | 支持 claim、completed replay、同键冲突、过期 generation CAS 和损坏结果 fail-closed。 |
| 精确重复 | 同项目精确重复复用既有 Asset/Version；只在存在真实新来源时新增 Source。 |
| 竞态重试 | 仅两个白名单唯一约束允许使用全新 Session 完整重试一次，并重新验证 project scope。 |
| Winner 校验 | winner outcome 在提交前验证；winner 不可读取或损坏时完整回滚。 |
| Replay 完整性 | 校验 Asset/project、Version/Asset、created/reused flags、created `row_version = 1` 和当前请求 checksum。 |
| Source / Audit | 新建、精确重复和新来源路径遵守事件矩阵；同键重放不新增 Source 或 Audit。 |
| Audit 安全 | payload 不包含正文、原始幂等键、内部 PK、SQL、token、凭据、异常对象或堆栈。 |

## 3. Deferred Scope

以下内容没有进入 Slice 6，继续受后续 Slice 或 Phase 合同治理：

- Slice 7 Lifecycle / Review Service；
- Slice 8 Router / API；
- Slice 9 Core 集成验收；
- Slice 10 Requirement 生命周期；
- Slice 11 前端资产中心；
- 语义疑似重复、RAG 和 Embedding；
- Candidate、Preview、DSL、Compiler、TestCase 和 Runner；
- Router/API、前端、ORM、Migration 和 Schema 变更。

## 4. PR and Commit Traceability

所有下列提交及 merge commit 均已确认包含在
`origin/dev@6a718254b405eab35de4f7351792b0a48916ab5c`。

| 交付 | PR | Implementation / Head commit | Merge commit | 状态 |
|---|---|---|---|---|
| Slice 6 计划 | [#17](https://github.com/Chloeqq/ai-test-platform/pull/17) | `d9d1457ed48c9593c0d4bcfcd4617ce24462174c` | `0235197ce5c0dad19d2425ce11c30dea21324112` | Merged |
| Slice 6 初始实现 | [#18](https://github.com/Chloeqq/ai-test-platform/pull/18) | `3a29afeb9cdac13bc36f782cd9942c39d8deafde` | `c4b70dbf47a4bf0f7553e72520e6058b46341a99` | Merged |
| Code Quality Gate | [#19](https://github.com/Chloeqq/ai-test-platform/pull/19) | `36a22ac3a14049d580c5251963c9cbf099efc8b4` | `8cbe8679cf32278fa1236d673f68ed59300a0b6c` | Merged |
| 安全基线收缩治理 | [#20](https://github.com/Chloeqq/ai-test-platform/pull/20) | `008da370192b828f903f58e12ef2e1bd9e659318` | `2dcebe9b1681471673b3a704fefe5897c3cdf7c5` | Merged |
| Slice 6 Closeout 阻塞修复 | [#21](https://github.com/Chloeqq/ai-test-platform/pull/21) | `c8113fb628f3917c7d97641ab648b22d93eabf19` | `6a718254b405eab35de4f7351792b0a48916ab5c` | Merged |

PR #17 还包含计划建立和 S6-R01 关闭提交；PR 的最终 head 和 merge commit 是本报告使用的
计划事实快照。

## 5. Review Findings and Resolutions

| 发现 | 处置 | Closeout 状态 |
|---|---|---|
| S6-R01 初始 row version 语义 | 创建期首版本绑定固定为 `1`，后续 CAS 才推进为 `2`。 | Closed |
| winner outcome 可能在本地聚合提交后才失败 | 将 winner outcome 完整性校验放在事务提交前；失败共同回滚。 | Closed |
| 白名单冲突重试边界 | 只识别两个命名约束；全新 Session 最多一次，并重新验证 project scope。 | Closed |
| Requirement Repository 类型声明与运行时值不一致 | Repository 运行时返回真实 tuple。 | Closed |
| Clock、函数复杂度、Ruff、format 和 Mypy 新增违规 | 显式 Clock 与最小职责拆分；新增违规归零。 | Closed |
| completed replay 可错误关联同项目其他内容 | 复用 `build_content_fingerprint`，严格校验持久化 Version checksum。 | Closed |
| replay 失败可能产生副作用 | 真实 SQLite/SQLAlchemy 测试证明相关八类记录前后完全不变。 | Closed |

独立 PR #21 复审未发现未关闭的 Critical、High、Medium、Low 或 Test Gap。

## 6. Quality Gate Evidence

| 证据 | 结果 |
|---|---|
| Required check | `evie-ai-code-quality`: Passed |
| Repository Ruleset | Active；作用于 `dev`；无 bypass |
| Base baseline / scan | `77 / 77` |
| Head baseline / scan | `50 / 50` |
| Removed violations | `27` |
| Added exemptions | `0` |
| Replacements | `0` |
| Reclassifications | `0` |
| New violations | `0` |
| 门禁单元测试 | `59 passed` |
| 架构守卫 | `11 passed` |

Baseline 收缩由 Base/Head 双快照算法验证。保留 50 项的路径、规则、分类、指纹和修复方向
未改变；工具版本、阈值、扫描范围、exclude、ignore 和 `noqa` 未被扩大或削弱。

## 7. Test Evidence

| 测试组 | 结果 |
|---|---|
| checksum 与合法 replay 专项 | `3 passed` |
| Slice 6 targeted | `82 passed` |
| Repository | `14 passed` |
| EvieAi unit + integration | `261 passed` |
| 门禁测试 | `59 passed` |
| 架构守卫 | `11 passed` |
| 完整 web-ui unit | `717 passed, 32 failed, 43 warnings` |
| 干净 `origin/dev` 对照 | `711 passed, 32 failed, 43 warnings` |
| 新增回归 | `0` |

完整 web-ui 对照中，失败 node ID、首要异常类型、归一化异常签名和 warning 数量一致。
PR 侧新增的 6 个测试均通过。checksum 负向反证还确认：移除 checksum 比较后，
错误关联专项测试会失败，因此该测试不是假阳性。

## 8. Known Pre-existing Failures

32 个完整 web-ui unit 失败均在干净 `origin/dev` 上重现：

| 分类 | 文件 | 数量 | 归因 |
|---|---|---:|---|
| CI-B01 | `test_workbench_facade.py` | 8 | 缺少 `app.api.workbench.facade.test_case_service` |
| 其他既有失败 | `test_case_id_flow.py` | 1 | 与干净 dev 的 node ID 和失败签名一致 |
| 其他既有失败 | `test_step_field_consistency.py` | 1 | 与干净 dev 的 node ID 和失败签名一致 |
| 其他既有失败 | `test_test_point_asset_candidate_sync.py` | 1 | 与干净 dev 的 node ID 和失败签名一致 |
| 其他既有失败 | `test_workbench_generation_service.py` | 21 | 与干净 dev 的 node ID 和失败签名一致 |

CI-B02 是独立的 `static-baseline` collection failure：仓库缺少
`apps/ai-orchestrator/src/app.py`。它不属于上述 32 个 web-ui unit 失败。

CI-B01、其余 24 个既有 web-ui 失败和 CI-B02 均未在 Slice 6 中修复、修改或重新分类。

## 9. Residual Risks

- 完整 web-ui 仍保留 32 个既有失败，CI-B02 仍阻断对应静态基线收集；它们是范围外技术债。
- 质量基线仍保留 50 项历史违规；required zero-new gate 阻止新增或重新引入。
- Slice 7 生命周期、Slice 8 API 和 Slice 9 集成验收尚未开始，因此
  Asset Lifecycle Core 后端尚未 Closeout。
- Phase 1 仍有 Slice 7～11 和最终全量验收工作，不能据此进入 Phase 2。

上述风险不阻塞 Slice 6 自身 Closeout，但继续阻塞更高层级的 Phase 1 Closeout。

## 10. Explicit Non-deliverables

本 Slice 没有交付或修改：

- 生产 Router 或 API；
- 前端；
- ORM、Migration 或 Schema；
- Candidate、Preview 或旧生成链；
- DSL、Compiler、TestCase 或 Runner；
- Slice 7/8；
- CI-B01 或 CI-B02 修复；
- Architecture Baseline、ADR 或 Phase 0/1 范围定义；
- GitHub workflow 或 Repository Ruleset。

## 11. Final Decision

Slice 6 的计划、实现、阻塞修复、真实持久化测试、回归归因、质量门禁和 merge 证据完整。
不存在未关闭的 Slice 6 Closeout 阻塞项。

Final decision: Slice 6 Closeout Completed

该决定只关闭 Slice 6：

- Phase 1 overall status: In Progress
- Phase 1 closeout status: Not completed
- Slice 7 status: Not started
- Slice 8 status: Not started
