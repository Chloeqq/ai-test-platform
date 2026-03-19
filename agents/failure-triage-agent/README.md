# Failure Triage Agent (MVP)

`failure-triage-agent` 用于把失败归因结果转成可路由、可执行的分诊决策，输出 `FailureTriageV1`。

## 输入

- `failure_analysis`（来自失败归因 Agent）
- `execution_record`（统一执行记录）
- `evidence_manifest`（证据索引）

## 输出

- `triage_label`：分类标签（category:risk:status）
- `failure_class`：失败类型（locator/assertion/network/...）
- `severity`：分级（S0~S4）
- `owner_team`：建议处理团队
- `queue`：建议进入的处理队列
- `actions`：后续动作建议（建单、补证、阻断发布等）

## 本地运行

```bash
cd agents/failure-triage-agent
python3 -m src.index --input examples/input.json
```
