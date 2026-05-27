# 2026-05-25 DSL V1.1 断言时序规则落地记录

## 1. 结论

本次确认并落地以下产品语义：

- 步骤内断言（`execution.steps` 中的 `assert_*`）是步骤验收标准，必须按原顺序立即执行。
- 顶层断言（`test_case.assertions`）是最终验收标准，只在所有步骤执行后统一执行。
- 顶层断言不能改变步骤时序，也不能替代步骤内断言。
- 同一断言不重复出现在步骤内与顶层。

## 2. 原问题

`generate_pipeline.py` 中原有逻辑会把步骤内 `assert_*` 提升到顶层 `assertions`，导致：

- 步骤时序被破坏，中间状态无法在发生时立即验证。
- 报告中的失败定位变模糊，难以精确归因到具体步骤。

## 3. 代码改动（最小范围）

文件：

- `apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py`
- `apps/web-ui-service/tests/test_workbench_generation_service.py`

改动要点：

1. `_normalize_dsl_v1_1_assertions()` 只做顶层断言标准化与去重，不再移除 `execution.steps` 中的断言步骤。
2. 去重策略改为“以步骤断言为准”：若顶层断言与步骤断言签名一致，顶层自动跳过。
3. AI 自动化用例断言门禁改为统计“步骤断言 + 顶层断言”总量，不再只依赖顶层断言。
4. `assert_text` 纳入生成器可识别断言集合，保持与 Runner schema 能力一致。
5. 测试基线更新为“登录成功最终断言保留在步骤中”，并新增回归用例锁定去重与时序。

## 4. 执行顺序定义（正式）

执行顺序固定为：

`preconditions -> steps(含步骤内 assert_*) -> top_level_assertions`

步骤内断言失败时：

- 该步骤立即失败并记录失败上下文。
- 后续步骤是否继续执行由执行策略决定（当前默认中断）。

顶层断言失败时：

- 用例最终判定为失败。

## 5. 验收标准

- 步骤内断言不会被迁移到顶层。
- 顶层断言在全部步骤执行后才执行。
- 顶层与步骤断言重复时，只保留步骤断言执行职责。
- AI 自动化用例至少存在一个可执行断言（步骤或顶层任一位置）。
- 不改写被测地址铁律：`http://localhost:5174/#/login`。
