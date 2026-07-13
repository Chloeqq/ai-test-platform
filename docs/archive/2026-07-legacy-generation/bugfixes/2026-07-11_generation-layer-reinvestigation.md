# 2026-07-11 生成层重新排查结果（dev）

## 基线

- 分支：`dev`
- 基线提交：`4de89e9 fix(ci): quote step name to unbreak tests.yml workflow parsing`
- 执行命令：

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -q \
    apps/web-ui-service/tests/unit/test_workbench_generation_service.py
  ```

- 结果：`27 failed, 25 passed`。

## 完整排查调用链（dev）

```text
需求 / 已审核测试点资产
  -> POST /api/workbench/test-point-assets/batch/generate-cases
  -> workbench_generation_service.py
  -> runtime/generate_pipeline_steps.py::run_generate_pipeline()

Step 1：AI / 已选 candidate 解析
  -> _build_direct_candidate_orchestrator_result()
  -> shared_backend/intent_mapping.py::resolve_explicit_step()
  -> shared_backend/element_binding.py::resolve_element_code()

Step 2：测试点规范化与范围收敛
  -> shared_backend/schemas/contracts.py::normalize_test_point_plan_v1()

Step 3：契约校验与执行 DSL 编译
  -> shared_backend/schemas/validator.py::ContractValidator
  -> shared_backend/execution_compiler.py::compile_execution_steps()
     -> normalize_test_points()
     -> normalize_test_points_to_actions()
     -> build_execution_ir()
     -> bind_targets()
     -> render_execution_steps()

Step 4：可执行用例格式化
  -> _format_product_case_yaml()
  -> _format_product_execution_steps()

Step 5：用例与测试点计划保存
  -> write_case_yaml()
  -> save_case_state()
  -> save_test_point_plan()

共享工具
  -> shared_backend/type_utils.py::{str_value, dict_value, list_value}
```

### 入口、编排与保存明细

```text
HTTP 入口
apps/web-ui-service/app/routers/workbench_assets.py
  batch_generate_cases_from_test_point_assets() [110]
  -> facade.generate_cases_from_test_point_assets(..., db)

测试点资产业务入口
apps/web-ui-service/app/api/workbench/facade_test_point_assets.py
  generate_cases_from_test_point_assets() [1193]
  -> Generation API service
  -> workbench_generation_service.build_generated_case_payload()

生成服务
apps/web-ui-service/app/services/workbench_generation_service.py
  build_generated_case_payload() [451]
  -> runtime/generate_pipeline_steps.run_generate_pipeline()

运行时编排
apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline_steps.py
  run_generate_pipeline() [738]
  -> _call_orchestrator_and_parse() [153]
  -> _normalize_and_scope_test_points() [249]
  -> _validate_and_compile_steps() [324]
  -> _allocate_and_format_case_id() [444]
  -> 持久化阶段：write_case_yaml() / save_case_state() / save_test_point_plan()
```

### Part A — candidate 到结构化测试点

```text
generate_pipeline_steps._call_orchestrator_and_parse()
  -> generate_pipeline_orchestrate._build_direct_candidate_orchestrator_result() [409]
     （selected_candidate / candidate_snapshot 的直接编译路径）
  -> generate_pipeline._normalize_candidate_snapshot() [478]
  -> generate_pipeline._candidate_identity() [508]
  -> 对 candidate.steps_hint 逐条调用：
     -> shared_backend.intent_mapping.resolve_explicit_step() [56]
        -> _normalize_action() [10]
        -> _split_payload() [35]
        -> _resolve_target_code() [46]
           -> shared_backend.element_binding.resolve_element_code() [83]
  -> 输出：point.steps（action / target / value / raw_text）
```

Part A 的职责是：把候选测试点的显式 `steps_hint` 解析为结构化步骤；`raw_text` 保留自然语言步骤，`target` 必须解析为当前页面对象的 element code。

### Part B — 结构化测试点到 Runner DSL

```text
generate_pipeline_steps._normalize_and_scope_test_points()
  -> shared_backend.schemas.contracts.normalize_test_point_plan_v1() [639]
  -> 输出：规范化 test_points

generate_pipeline_steps._validate_and_compile_steps()
  -> shared_backend.schemas.validator.ContractValidator [49]
  -> shared_backend.execution_compiler.compile_execution_steps() [899]
     -> normalize_test_points() [150]
     -> normalize_test_points_to_actions() [334]
     -> build_execution_ir() [495]
     -> bind_targets() [611]
        -> resolve_element_code()（target 别名兜底）
        -> _is_business_type_allowed_for_action()（action/assertion 与 business_type 兼容性）
     -> render_execution_steps() [738]
  -> 输出：runner 可执行 execution steps
```

Part B 的职责是：校验测试点契约、将 action 标准化、绑定真实 locator、拒绝不兼容 target，并输出 Runner action。

### Part C — 跨层通用契约

```text
shared_backend/type_utils.py
  dict_value() [7]
  list_value() [12]
  str_value() [33]

shared_backend/schemas/contracts.py
  normalize_test_point_plan_v1() [639]

shared_backend/schemas/validator.py
  ContractValidator [49]
```

Part C 的职责是：统一空值/类型处理，规范化测试点计划，并在进入编译器前报告跨层字段与 target 一致性问题。

### 已更正的模块归属

- `run_generate_pipeline()`：`runtime/generate_pipeline_steps.py:738`，不是 `generate_pipeline.py`。
- `_build_direct_candidate_orchestrator_result()`：`runtime/generate_pipeline_orchestrate.py:409`。
- `_normalize_candidate_snapshot()`：`runtime/generate_pipeline.py:478`，不是 orchestrate 模块。
- `_candidate_identity()`：`runtime/generate_pipeline.py:508`，不是 orchestrate 模块。

## 失败分组

| 根因 | 数量 | 证据文件 | 结论 |
| --- | ---: | --- | --- |
| Assertion 期望与 structurer 当前职责不一致 | 8 | `steps/structurer.py:130,305-320`；`test_workbench_generation_service.py` | `_build_expected_assertions()` 仍被调用，但固定返回 `0`。直接测试 structurer 的断言生成因此失败。 |
| point builder 路径未接入 Registry assertion | 2 | `compilation/point_builder.py:47-67`；`steps/structurer.py:130,305-320` | point builder 直接调用 structurer；structurer 返回 `0` assertion，导致旧测试期望的成功/重定向断言缺失。 |
| 生成管线测试仍 monkeypatch 已迁移的 helper 旧位置 | 17 | `runtime/generate_pipeline_orchestrate.py:379,587,660,923`；`runtime/generate_pipeline_format.py:160,219`；`test_workbench_generation_service.py` | 被测 helper 已从 `generate_pipeline.py` 拆至 `generate_pipeline_orchestrate.py` / `generate_pipeline_format.py`，测试仍引用旧模块属性，收集后直接 `AttributeError`。 |

## 断言链现状

```text
candidate.expected
  -> structured_steps_from_candidate()
  -> _build_expected_assertions() = 0
  -> facade_helpers._steps_from_candidate()
  -> 仅 db 非空时 resolve_and_compile()
```

`resolve_and_compile()` 已存在于 `app/services/assertion_resolver.py:103`，但当前 `_manual_point_from_candidate()` 未提供 `db`，因此 Registry 分支不可达。

该不可达问题是生产风险；它不与上表的 27 个测试失败重复计数。

## 已确认的非问题

- `shared_backend/intent_mapping.py` 已拒绝空 `assert_text` value（`4e81060`）。
- `shared_backend/intent_mapping.py` 已拒绝空 `assert_metric` rule（`4a7b8ae`）。
- `shared_backend/intent_mapping.py` 已修复 `=>` 被 `=` 提前匹配的问题（`f396502`）。
- `shared_backend/element_binding.py` 已拒绝不同 element code 使用同一 alias（`f396502`）。
- `execution_compiler.py` 已拒绝 `business_type` 为空、但 `role=button` 的 `assert_text` target（`f396502`）。

## 已解决问题（截至 2026-07-12）

| 问题 | 修复状态 | 验证 |
| --- | --- | --- |
| `assert_text` 空 value 被允许 | 已解决 | 空 value 明确抛出 `ValueError`；正常 value 保留。 |
| `assert_metric` 空 rule 自动补 `number` | 已解决 | 空 rule 明确抛出 `ValueError`；正常 rule 保留。 |
| `field=>value` value 被解析为 `>value` | 已解决 | 长分隔符 `=>` 优先于 `=`。 |
| alias 冲突静默绑定第一个 element | 已解决 | 不同 element code 使用同 alias 时抛出 `ValueError`。 |
| `role=button` 且 business type 为空的文本断言未被拒绝 | 已解决 | `bind_targets()` 将 role 传入兼容性校验，仅作为 business type 缺失时的 `assert_text` 兜底。 |

上述 shared backend 定向回归测试最近一次结果：`43 passed`。

## 仍遗留问题（截至 2026-07-12）

| 优先级 | 文件 | 问题 |
| --- | --- | --- |
| P0 | `app/api/workbench/facade_helpers.py` | 手工测试点路径调用 `_steps_from_candidate()` 时未传入 `db`，Behavior Registry assertion 注入分支不可达。 |
| P1 | `runtime/generate_pipeline_steps.py`、`steps/structurer.py`、`compilation/point_builder.py` | structurer 固定返回 `0` assertion，point builder 路径没有等价的 Registry 注入；对应 10 个断言预期失败仍未处理。 |
| P1 | `tests/unit/test_workbench_generation_service.py` | 17 个测试仍 monkeypatch 已迁移出 `generate_pipeline.py` 的 helper，导致 `AttributeError`。 |
| P1 | `runtime/generate_pipeline_orchestrate.py:513,516` | direct candidate 路径固定写入 `quality_gate.decision="allow"`。 |
| P2 | `runtime/generate_pipeline.py:509` | 缺失 `intent_id` / `key` 时固定使用 `manual-intent`，存在 identity 冲突风险。 |
| P2 | `shared_backend/intent_mapping.py:18-19` | 通用 `assert` 当前固定映射为 `assert_visible`。 |

## 风险

- 当前生成结果可能带有 `assertion_missing`，或完全没有可执行 assertion。
- 将旧 structurer 单元测试直接恢复为“自动猜测 assertion”会重新引入错误 target 和 AI 推测 value 的风险。
