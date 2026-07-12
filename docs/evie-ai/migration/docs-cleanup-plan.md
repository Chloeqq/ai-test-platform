# EvieAi 文档清理计划

日期：2026-07-12

## 1. 清理目标

让文档入口和事实源与 EvieAi 保持一致：

- 自然语言测试资产是主线。
- Candidate / selected_candidates / 生成阶段结构化 / 生成阶段提前编译是旧链。
- 旧链文档保留为历史证据，但不再作为当前架构事实源。
- 新增权威文档统一放在 `docs/evie-ai/**`。
- 不再新增旧产品命名对应的平行事实源。

## 2. 已执行处理

第一批旧链文档已归档到：

```text
docs/archive/2026-07-legacy-generation/
```

归档范围：

- `docs/architecture/2026-07-07_*` 中明确描述旧 Candidate、preview、quality gate 接入生成阶段、structurer 的文档。
- `docs/architecture/2026-07-10_compilation_*` 中描述旧编译管线、`steps_hint`、`resolve_explicit_step` 的文档。
- `docs/architecture/2026-07-11_hardcoded_token_removal_plan.md`
- `docs/bugfixes/2026-07-11_generation-layer-*`

## 3. 暂不删除的原因

这些文档虽然不再是事实源，但仍有价值：

- 保留历史决策上下文。
- 保留旧链问题取证。
- 支持后续迁移比对。
- 避免误删仍被引用的材料。

删除动作必须等到：

1. EvieAi 文档补齐。
2. 旧文档引用修复完成。
3. 至少一个版本周期后确认无人依赖。

## 4. 后续清理顺序

### Phase 1：入口修正

- 更新 `AGENTS.md`
- 更新 `docs/README.md`
- 更新 `docs/architecture/README.md`
- 建立 `docs/evie-ai/README.md`

### Phase 2：旧链归档

- 归档明确旧链文档。
- 不删除。

### Phase 3：规则文档更新

重点更新：

- `CLAUDE.md`
- `README.md`
- `docs/core/platform_rules.md`
- `docs/core/test_asset_rules.md`
- `agents/test-design-agent/README.md`
- `runners/web-playwright-python/PROJECT_DOCS.md`

### Phase 4：失效链接修复

优先修复：

- `docs/architecture/README.md`
- `docs/api/README.md`
- `README.md`
- `apps/ai-orchestrator/README.md`
- `docs/onboarding/README.md`

## 5. 分类口径

| 分类 | 含义 |
|---|---|
| EVIE_AI_SOURCE_OF_TRUTH | EvieAi 当前事实源 |
| CURRENT_SHARED | 当前仍可作为通用规则或使用说明 |
| REUSABLE_REFERENCE | 可参考，但不是当前事实源 |
| LEGACY | 旧架构文档，应归档 |
| NEEDS_REVIEW | 需要人工判断是否更新或归档 |

## 6. 删除原则

当前没有第一批可安全删除文档。

建议删除策略：

```text
archive → 修复引用 → 观察一个版本周期 → delete_after_verification
```
