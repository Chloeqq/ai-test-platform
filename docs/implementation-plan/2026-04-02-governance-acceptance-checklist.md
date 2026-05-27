# 2026-04-02 治理能力人工验收清单

## 1. 页面入口

- 打开首页：[http://127.0.0.1:8013/](http://127.0.0.1:8013/)
- 确认首页可见以下治理区块：
  - `高风险治理任务`
  - `缺失 Manifest 任务`
  - `失败聚类数`
  - `需人工复核聚类`
  - `治理行动建议`
  - `Top 治理风险任务`
  - `治理趋势（14天）`

## 2. 页面跳转

- 点击 `高风险治理任务`，应进入执行记录页 `/executions`
- 点击 `缺失 Manifest 任务`，应进入报告性能页 `/report/performance`
- 点击 `失败聚类数`，应进入失败聚类页 `/quality/clusters`
- 点击 `需人工复核聚类`，应进入失败聚类页 `/quality/clusters`
- 点击 `7d 门禁阻断`，应进入失败聚类页 `/quality/clusters`
- 点击 `7d 风险阻断`，应进入趋势分析页 `/quality/trends`
- 点击 `7d 需复核`，应进入执行记录页 `/executions`
- 点击 `趋势方向`，应进入趋势分析页 `/quality/trends`

## 3. 接口验收

- 访问治理接口：[http://127.0.0.1:8013/api/dashboard/governance](http://127.0.0.1:8013/api/dashboard/governance)
- 确认返回字段存在：
  - `risk`
  - `summary`
  - `quality_gate`
  - `failure_clusters`
  - `top_governance_risks`
  - `action_items`
  - `trend_14d`
  - `trend_summary_7d`

## 4. 数据语义

- `summary.high_risk_task_count` 应等于 `critical + high` 总数
- `quality_gate.summary_24h` 应包含：
  - `blocked_events`
  - `block_rate`
  - `top_alert_code`
- `trend_14d` 每天应包含：
  - `quality_gate_block`
  - `risk_blocked_runs`
  - `review_required_runs`
  - `pressure_score`

## 5. 回归验收

- 执行全仓回归：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q
```

- 预期结果：

```text
189 passed, 1 skipped
```

- 执行 `web-ui-service` 回归：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q apps/web-ui-service/tests
```

- 预期结果：

```text
134 passed
```

## 6. 说明

- 如果首页仍显示旧样式，强制刷新浏览器缓存后重试。
- 如果治理接口返回为空但状态码正常，优先检查本地历史样本、执行记录与失败聚类数据是否存在。
