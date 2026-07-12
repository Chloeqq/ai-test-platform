# EvieAi 旧链冻结清单

日期：2026-07-12

本文记录 EvieAi Phase 0 之后不得继续扩展为主链的旧业务流程。

## 1. 必须冻结的旧业务概念

- Candidate Preview
- `selected_candidates`
- 候选项复选框
- 全选候选
- 保存所选候选
- 只有被选中才分配资产 ID
- Candidate 作为持久化业务实体

## 2. 必须冻结的提前转换行为

- 生成阶段调用 `structurer`
- 生成阶段调用 `resolve_explicit_step`
- 生成阶段生成 `action / target / value`
- 生成阶段生成 `structured_steps`
- 生成阶段调用 Behavior Registry
- 生成阶段调用 ContractValidator
- 生成阶段调用 ExecutionCompiler
- 生成阶段调用 CaseQualityGate
- 生成阶段生成 `script_code`

## 3. 可保留的技术复用边界

以下模块可以作为历史兼容、迁移分析或未来 Asset-to-Case 底层技术能力参考，但不得作为 EvieAi 资产入库主链：

- `shared_backend/intent_mapping.py`
- `shared_backend/execution_compiler.py`
- `shared_backend/schemas/validator.py`
- `apps/web-ui-service/app/services/workbench_generation_api/steps/structurer.py`
- `apps/web-ui-service/app/services/workbench_generation_compiler/**`

## 4. 替代方向

旧链中的“生成即可执行”流程，由 EvieAi 主链替代：

```text
AI 生成自然语言测试点
→ 统一资产入库
→ TestAsset / TestAssetVersion
→ 用户编辑和审核
→ 用户主动触发 Asset-to-Case
→ 资源绑定 / 质量门 / Compiler
→ TestCaseVersion.script_code
→ Runner
```

## 5. Phase 0 守卫要求

EvieAi Phase 0 的模型、Schema 和 Repository 必须通过架构守卫测试确认：

- 不依赖 `structurer`
- 不依赖 `execution_compiler`
- 不依赖 `ContractValidator`
- 不依赖 `resolve_explicit_step`
- 不导入旧 `TestPointAsset`
- TestAsset Schema 不包含机器执行字段
