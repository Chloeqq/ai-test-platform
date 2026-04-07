# 测试用例字段落库方案（2026-04-05）

> 文档版本：v1.0  
> 文档目标：确定测试用例管理层的字段落库方案，支撑 `case_id` 统一、项目隔离、AI 生成回写和 Excel 模板导出。  
> 适用范围：`apps/web-ui-service` 用例中心主链、关联表、迁移脚本、兼容 API

---

## 1. 设计前提

本方案严格遵循以下已确认决议：

1. 保留平台现有命名规范：`atp-web-ret-query-sm-ai-0001`
2. 不再新增第二套业务编号：`EC-ORD-CC-0001`
3. Excel 模板中的 `用例ID` 列直接映射平台 `case_id`
4. 数据库自增 `id` 继续仅作为内部主键，不对外展示为业务编号

关联文档：

- [测试用例模板映射表（2026-04-05）](./test-case-template-mapping-table-2026-04-05.md)
- [测试用例编号统一与实施优先级（2026-04-05）](./test-case-case-id-unification-priority-plan-2026-04-05.md)

---

## 2. 当前问题

当前主表定义见 `apps/web-ui-service/app/models/test_case.py`，核心问题如下：

| 问题 | 当前现状 | 影响 |
|---|---|---|
| 业务编号缺失 | `test_cases` 只有整数 `id`，没有标准 `case_id` | AI 生成链和管理链无法同主键对齐 |
| 项目维度缺失 | 没有 `project_code` / 项目注册表 | 无法管理多个项目的用例 |
| 统一编码维度缺失 | 缺 `client/page_code/module_code/case_type/source` | 无法稳定生成、回填和校验编号 |
| 模板字段缺失 | 当前只存 `name/module/priority/script_code` 等基础字段 | 无法按企业模板导出 |
| 运行时 schema 演进不规范 | 当前 `ensure_test_cases_schema_compatibility()` 直接在服务运行时 `ALTER TABLE` | 难以受控迁移和审计 |

---

## 3. 总体策略

### 3.1 方案选择

本阶段不新建 `test_cases_v2`，优先扩展现有 `test_cases` 主表。

原因：

1. 现有用例中心、版本、执行、缺陷关联都已依赖 `test_cases.id`
2. 扩表成本显著低于整链切到新表
3. 可以保留内部整数主键，逐步把外部业务访问迁到 `case_id`
4. 更适合当前“先打通主链，再做治理升级”的节奏

### 3.2 迁移原则

1. `id` 不动，继续作为内部主键和关联表外键
2. 新增 `case_id` 并建立唯一索引
3. 所有对外展示、导出、查询逐步转到 `case_id`
4. 模板字段先落到主表，复杂治理字段后续再拆治理子表
5. 数据库结构变更统一走 Alembic，不再依赖运行时自动 `ALTER TABLE`

---

## 4. 目标表结构

## 4.1 新增项目注册表

建议新增：`test_projects`

用途：

- 支撑“创建项目”“区分不同项目用例”
- 作为 `test_cases.project_code` 的合法值来源
- 为后续项目级筛选、导出、权限隔离做准备

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `BIGINT/INTEGER PK` | 内部主键 |
| `project_code` | `VARCHAR(20) UNIQUE NOT NULL` | 项目标识，默认种子 `atp` |
| `project_name` | `VARCHAR(100) NOT NULL` | 项目名称 |
| `description` | `TEXT` | 项目说明 |
| `status` | `VARCHAR(20)` | `active/inactive` |
| `created_by` | `VARCHAR(60)` | 创建人 |
| `created_at` | `TIMESTAMP` | 创建时间 |
| `updated_at` | `TIMESTAMP` | 更新时间 |

初始种子建议：

| project_code | project_name | 说明 |
|---|---|---|
| `atp` | `AI Test Platform` | 当前平台默认项目 |

补充说明：

- 现有 Workbench 文件态项目名 `default` 暂不直接作为 `case_id` 前缀
- Phase 1 先在管理链统一到 `project_code = atp`
- Workbench 的 `default` 目录概念在 Phase 2 通过映射或迁移方式并入 `project_code`

## 4.2 扩展主表 `test_cases`

保留现有字段：

- `id`
- `name`
- `product_line`
- `module`
- `priority`
- `test_type`
- `tags`
- `markers`
- `creator`
- `pytest_path`
- `status`
- `script_code`
- `data_config`
- `last_execution_result`
- `created_at`
- `updated_at`

新增字段分四组。

### 4.2.1 统一编号与项目维度

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `case_id` | `VARCHAR(64)` | 是 | 无 | 平台唯一业务编号，唯一索引 |
| `project_code` | `VARCHAR(20)` | 是 | `atp` | 项目编码 |
| `client` | `VARCHAR(10)` | 是 | `web` | 客户端类型 |
| `page_code` | `VARCHAR(20)` | 是 | `common` | 页面编码 |
| `page_name` | `VARCHAR(100)` | 否 | 空 | 页面中文名 |
| `module_code` | `VARCHAR(20)` | 是 | `core` | 模块编码 |
| `module_name` | `VARCHAR(100)` | 否 | 空 | 模块中文名 |
| `case_type` | `VARCHAR(10)` | 是 | `fn` | `sm/rg/fn/ex/int/e2e` |
| `source` | `VARCHAR(10)` | 是 | `mn` | `ai/mn/cv/imp/fb` |

### 4.2.2 模板核心字段

| 字段 | 类型 | 必填 | 默认值 | 对应模板列 |
|---|---|---|---|---|
| `chain_stage` | `VARCHAR(120)` | 否 | 空 | 链路环节 |
| `sut_service` | `VARCHAR(120)` | 否 | 空 | 域/服务 |
| `related_services` | `JSON` | 否 | `[]` | 关联服务 |
| `scenario_types` | `JSON` | 否 | `[]` | 测试类型 |
| `trigger_entry` | `VARCHAR(40)` | 否 | 空 | 触发入口 |
| `fault_injection_type` | `VARCHAR(80)` | 否 | 空 | 注入点类型 |
| `fault_injection_target` | `VARCHAR(255)` | 否 | 空 | 注入点目标 |
| `fault_injection_params` | `TEXT` | 否 | 空 | 注入参数 |
| `setup_sql` | `TEXT` | 否 | 空 | 前置数据 SQL |
| `precondition_state` | `TEXT` | 否 | 空 | 前置依赖状态 |
| `test_steps` | `JSON` | 否 | `[]` | 结构化测试步骤 |
| `test_steps_text` | `TEXT` | 否 | 空 | 导出与人工编辑友好的步骤文本 |
| `concurrency_model` | `VARCHAR(120)` | 否 | 空 | 并发模型 |
| `retry_policy` | `TEXT` | 否 | 空 | 重试策略 |
| `expected_result` | `TEXT` | 否 | 空 | 期望结果 |
| `assert_sql` | `TEXT` | 否 | 空 | 断言 SQL |
| `event_assertion` | `TEXT` | 否 | 空 | 事件断言 |
| `metric_assertion` | `TEXT` | 否 | 空 | 指标断言 |
| `cleanup_script` | `TEXT` | 否 | 空 | 回滚/清理脚本 |
| `artifact_links` | `JSON` | 否 | `[]` | 产物链接 |
| `notes` | `TEXT` | 否 | 空 | 备注 |

### 4.2.3 管理与展示增强字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `assignee` | `VARCHAR(120)` | 否 | 空 | 当前负责人 |
| `automation_status` | `VARCHAR(20)` | 是 | `manual` | `manual/automated/partial` |
| `source_ref` | `VARCHAR(255)` | 否 | 空 | 上游生成来源引用 |
| `last_report_url` | `TEXT` | 否 | 空 | 最近一次执行报告链接缓存 |

### 4.2.4 审计与回写辅助字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `created_source` | `VARCHAR(40)` | 是 | `manual` | `manual/ai/workbench/import` |
| `last_synced_at` | `TIMESTAMP` | 否 | 空 | 最近一次与 YAML/Workbench 回写同步时间 |

---

## 5. 字段命名决策

### 5.1 保留 `name`，不在本阶段强制改名为 `title`

当前 `test_cases.name` 已被多处服务和前端使用，本阶段不做列重命名。

统一策略：

- 数据库层：继续使用 `name`
- API/导出层：对外映射为 `case_title`
- YAML/AI 生成层：`title -> name`

原因：

1. 减少热路径改动
2. 先解决主链统一问题
3. 列重命名可以放到后续治理阶段处理

### 5.2 保留 `module`，新增 `module_code/module_name`

当前 `module` 更接近“业务模块显示名”，不是标准编码。

统一策略：

- `module`：兼容旧 UI 和旧搜索
- `module_code`：参与 `case_id` 生成和统一治理
- `module_name`：用于页面展示与导出

---

## 6. 数据回填方案

## 6.1 回填范围

需要回填：

- 历史 `test_cases`
- 关联执行记录的 `last_report_url`
- 模板字段的初始默认值

## 6.2 回填规则

### 6.2.1 `case_id` 回填

对每条历史用例执行以下逻辑：

1. `project_code = atp`
2. `client` 根据 `test_type` 推断
3. `page_code/module_code/case_type/source` 使用 `shared_backend.case_ids.build_case_metadata(...)` 推断
4. 使用 `next_case_sequence(...)` 在同前缀下分配序号
5. 生成最终 `case_id`

回填示例：

| 历史数据 | 回填结果示例 |
|---|---|
| `name=商品搜索结果展示` | `atp-web-prod-query-fn-mn-0001` |
| `name=订单创建基础流程` | `atp-web-ord-subm-fn-mn-0001` |

### 6.2.2 模板字段回填

初次回填时按以下策略：

| 字段 | 回填策略 |
|---|---|
| `chain_stage` | 先空置，由人工或 AI 二次补齐 |
| `sut_service` | 先空置 |
| `related_services` | `[]` |
| `scenario_types` | 若 `tags` 包含 `smoke/regression` 则转入，否则空 |
| `trigger_entry` | `ui` 类型映射 `UI`，`api` 类型映射 `API`，其余空 |
| `test_steps` | 若已有结构化执行步骤则写 JSON，否则 `[]` |
| `test_steps_text` | 优先根据结构化步骤渲染，否则空 |
| `artifact_links` | 优先写入最近一次 `report_url` |
| 其他长文本字段 | 空字符串 |

### 6.2.3 `automation_status` 回填

建议规则：

- `pytest_path` 或 `script_code` 非空：`automated`
- 否则：`manual`

---

## 7. API 兼容策略

## 7.1 过渡期原则

过渡期保留 `id`，新增 `case_id`，所有响应双字段返回。

示例：

```json
{
  "id": 12,
  "case_id": "atp-web-ret-query-sm-ai-0001",
  "name": "退货申请查询基础冒烟"
}
```

## 7.2 查询与路由切换顺序

推荐顺序：

1. Service 支持按 `case_id` 查找
2. API 新增 `case_id` 字段返回
3. 前端主显示切到 `case_id`
4. Router 路径从整数 `id` 逐步切到字符串 `case_id`
5. 最后缩减外部对整数 `id` 的依赖

## 7.3 批量接口兼容

过渡期建议：

- 保留：`ids: list[int]`
- 新增：`case_ids: list[str]`

服务端处理优先级：

1. 如果传 `case_ids`，按 `case_ids` 处理
2. 否则按 `ids` 兼容处理

---

## 8. 与 AI 生成 / Workbench 的打通策略

## 8.1 当前断点

当前 AI 生成与 Workbench 主要落在 YAML/State，而不是统一主表。

## 8.2 本阶段打通目标

本阶段不要求彻底替代 YAML/State，但至少做到：

1. AI 生成结果拥有标准 `case_id`
2. 生成成功后可选择回写 `test_cases`
3. 回写记录保留 `source=ai`、`created_source=workbench`
4. 若已存在相同 `case_id`，进入版本更新或审核队列，而不是重复造新主记录

建议回写主键策略：

- 主去重键：`case_id`
- 版本演进：仍走 `test_case_versions`

---

## 9. 数据库迁移实施顺序

推荐迁移顺序：

1. 新建 `test_projects`
2. 为 `test_cases` 增加新增字段
3. 建立 `case_id` 唯一索引
4. 写数据回填脚本
5. 执行历史数据回填
6. 修改 ORM Model
7. 修改 Service/Mapper/Schema
8. 修改前端展示
9. 修改导出链路

补充约束：

- 不再继续扩大运行时 `ensure_test_cases_schema_compatibility()` 的职责
- 新字段迁移全部转 Alembic 管理

---

## 10. 风险与应对

| 风险 | 说明 | 应对 |
|---|---|---|
| 历史数据推断不准 | 旧用例没有足够语义字段 | 首次回填允许人工修订，保留回填日志 |
| Workbench 项目名与 `project_code` 不一致 | 当前有 `default` 目录概念 | 通过映射策略过渡，不直接写入旧目录名 |
| 长文本字段过多 | 模板字段大量是多行 SQL/步骤 | 使用 `TEXT` 和 `JSON` 混合存储，避免单字段语义过载 |
| UI 一次切换过大 | 旧前端广泛依赖 `id` | 采用双字段兼容过渡 |

---

## 11. 验收标准

字段落库方案实施完成后，应满足：

1. `test_cases` 每条记录都有唯一 `case_id`
2. 用例可按 `project_code` 区分和筛选
3. Excel 导出不再依赖数据库整数 `id`
4. AI 生成、Workbench、用例中心可共享同一 `case_id`
5. 旧关联表仍可通过内部 `id` 正常工作

---

## 12. 推荐优先级

优先级排序如下：

1. `P0` 新建 `test_projects` 并扩展 `test_cases`
2. `P0` 历史数据回填与 `case_id` 唯一化
3. `P1` API 与 UI 改为主显示 `case_id`
4. `P1` Excel 导出接入模板字段
5. `P1` AI/Workbench 回写打通

---

## 13. 变更记录

| 日期 | 版本 | 变更内容 |
|---|---|---|
| 2026-04-05 | v1.0 | 首版字段落库方案，明确扩表策略、项目表方案、回填规则与兼容策略 |
