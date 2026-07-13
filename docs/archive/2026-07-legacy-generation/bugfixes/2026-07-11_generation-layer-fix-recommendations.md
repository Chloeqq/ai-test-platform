# 2026-07-11 生成层修复建议（dev）

配套排查记录：`2026-07-11_generation-layer-reinvestigation.md`。

## 已完成修复（2026-07-12）

- 空 `assert_text` value：已拒绝。
- 空 `assert_metric` rule：已拒绝。
- `=>` 分隔符：已改为长分隔符优先。
- alias 冲突：不同 element code 使用同一 alias 时已拒绝。
- `role=button` 且 `business_type` 为空的 `assert_text`：已拒绝。

最近一次 shared backend 定向回归测试：`43 passed`。

## P0：使 Registry 注入在手工测试点生产链可达

### 最小修改范围

- `apps/web-ui-service/app/api/workbench/facade_helpers.py`

### 建议

1. 让 `_manual_point_from_candidate()` 接收已有的数据库会话。
2. 调用 `_steps_from_candidate(candidate, db=...)`。
3. 在调用 Registry 前，保证 `candidate.page_code` 来自当前生成上下文，不能依赖 AI 是否自行提供该字段。
4. Registry 返回 assertion 后，仅追加模板中明确配置的 target/value；没有匹配模板时保留 `assertion_missing`，不得从 expected 文本猜测。

### 验收

- login negative：模板返回 `assert_text:login-username-error=<登记值>`。
- login functional：模板返回已配置的成功态 assertion。
- 无模板：不生成猜测 assertion，测试点保留待审核标记。

## P1：更新测试到实际模块边界

### 最小修改范围

- `apps/web-ui-service/tests/unit/test_workbench_generation_service.py`

### 建议

1. 将 page object 解析、执行步骤格式化、URL 信任校验等测试的 monkeypatch/import 指向：
   - `runtime/generate_pipeline_orchestrate.py`
   - `runtime/generate_pipeline_format.py`
2. 保留 `generate_pipeline.py` 测试仅覆盖其公开编排入口，不再测试已迁移的私有 helper。

### 验收

- 移除因旧模块属性不存在导致的 `AttributeError`。
- 测试覆盖的行为和实际实现模块一致。

## P1：调整 assertion 测试边界

### 最小修改范围

- `apps/web-ui-service/tests/unit/test_workbench_generation_service.py`
- 必要时新增 facade helper 的定向单测。

### 建议

1. structurer 测试只验证：自然语言步骤结构化、显式 hint 保留、无 assertion 时返回计数 `0`。
2. Registry assertion 测试改为验证 `_steps_from_candidate(..., db=...)` 或等价的生产调用点。
3. 使用固定 Registry 模板 fixture；断言 target、value 均应来自模板，不来自 AI expected 文本。

### 验收

- negative/boundary/function/security 的 assertion 测试通过 Registry fixture 验证。
- 不再要求 structurer 独立猜测 `assert_text` / `assert_url` / `assert_visible`。

## 不建议的修复

- 不恢复 `_build_expected_assertions()` 的关键词猜测。
- 不允许用最后一次 click target 作为 `assert_text` target。
- 不为通过测试而将 `assertion_missing` 静默降级为成功。
