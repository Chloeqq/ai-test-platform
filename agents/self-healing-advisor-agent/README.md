# Self Healing Advisor Agent

该模块用于为失败用例输出“修复建议”，并在受控条件下支持对 `ai-generated` YAML 做单次自动修复尝试。

当前能力：

- 读取失败分析结果
- 输出结构化修复建议
- 建议类型包括：
  - `locator_update`
  - `assertion_update`
  - `wait_strategy`
  - `data_adjustment`
  - `environment_check`
  - `no_change`

当前边界：

- 只允许修改 `assets/test-cases/ai-generated/*`
- 不允许修改 `smoke` 用例
- 不自动写回 `assets/page-objects/*`
- 自动修复只允许单次尝试，最多 1 次
- `confidence` 必须严格大于 `0.7`
- rerun 失败会自动回滚

最小运行方式：

```bash
python3 -m agents.self-healing-advisor-agent.src.index --input payload.json
```

阶段 9/10 工具：

```bash
python3 agents/self-healing-advisor-agent/apply_fix.py preview --case /abs/path/to/case.yaml --suggestion /abs/path/to/suggestion.json
python3 agents/self-healing-advisor-agent/apply_fix.py apply --plan /abs/path/to/patch-plan.json --confirm APPLY
python3 agents/self-healing-advisor-agent/apply_fix.py rollback --receipt /abs/path/to/receipt.json --confirm ROLLBACK
python3 agents/self-healing-advisor-agent/apply_fix.py auto-heal --case /abs/path/to/case.yaml --artifacts /abs/path/to/artifacts/case-dir
```
