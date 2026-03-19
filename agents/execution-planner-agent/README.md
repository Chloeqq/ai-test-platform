# execution-planner-agent

根据生成的测试用例和执行配置，输出 `ExecutionPlanV1`。

## 输出内容

- 阶段拆分（prepare / runner / report）
- 预计耗时与重试策略
- 调度提示（queue、resource_profile）

## 快速使用

```bash
python -m src.index --input /tmp/execution_plan_payload.json
```
