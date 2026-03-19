# risk-evaluation-agent

根据需求优先级、执行状态、失败分析、执行策略输出 `RiskReportV1`。

## 输出内容

- `risk_score`（0-100）
- `risk_level`（low/medium/high）
- `gate_decision`（allow/manual_review/block）
- `recommendation`
- `factors`（可解释风险因子）

## 快速使用

```bash
python -m src.index --input /tmp/risk_eval_payload.json
```
