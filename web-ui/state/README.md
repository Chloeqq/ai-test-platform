# web-ui/state/ —— 运行态缓存

**此目录的所有内容都是可重建的。** 不应手动编辑，不应作为业务事实源。

## 各子目录说明

| 目录 | 角色 | 数据来源 | 可删除？ |
|------|------|---------|---------|
| `test-points/` | 测试点资产的运行态快照 | `upsert_test_point_asset()` 写入，从 DB page_objects + 用户输入派生 | 是，下次保存时会重建 |
| `generated-cases/` | AI 生成用例的本地缓存 | `save_case_state()` 写入，从 `run_generate_pipeline` 输出派生 | 是，下次生成时会重建 |
| `runs/` | 执行任务的运行日志和产物 | `execute_run()` 写入 | 是，但会丢失历史执行记录 |
| `default/` | 全局状态文件（history、runtime-runs 等） | `store.append_history()` 等写入 | 否（包含操作历史和运行态状态） |
| `reporting/` | 缺陷链接、审核决策、门禁决策 | API 写入 | 否（包含业务决策记录） |

## 硬规则

1. **DB 是主要事实源**。`test_cases.script_code` 是唯一可执行格式。
2. **`test-points/` 和 `generated-cases/` 是缓存**。数据可以从 DB 和用户输入重建。
3. **`default/` 和 `reporting/` 包含业务记录**（操作历史、审核决策），不可随意删除。
4. **永远不要手动编辑此目录下的文件**。所有写入必须通过 `store.*` 或 `state_store.*` 函数。
