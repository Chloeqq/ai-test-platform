# 测试用例模板映射表（2026-04-05）

> 目标：将当前项目中的 `用例中心 DB`、`AI/Workbench YAML/State` 与你给出的 `Excel 用例模板` 做统一映射，遵循“去同存异”原则。  
> 去同存异原则：  
> 1. 同义字段合并为一个统一口径。  
> 2. 同名但不同义字段必须拆开，不能硬映射。  
> 3. 模板之外但平台治理必须保留的字段，继续作为系统元数据保留，不强行塞进模板列。  

---

## 1. 当前三套口径

### 1.1 Excel 模板口径

模板固定 23 列：

- 用例ID
- 用例标题
- 链路环节
- 域/服务
- 关联服务
- 优先级
- 测试类型
- 触发入口
- 注入点类型
- 注入点目标
- 注入参数
- 前置数据SQL
- 前置依赖状态
- 测试步骤
- 并发模型
- 重试策略
- 期望结果
- 断言SQL
- 事件断言
- 指标断言
- 回滚/清理脚本
- 产物链接
- 备注

### 1.2 当前项目口径 A：用例中心 DB

来源：`apps/web-ui-service/app/models/test_case.py`

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

关联表：

- `test_case_versions`
- `test_case_executions`
- `test_case_defects`

### 1.3 当前项目口径 B：AI / Workbench YAML + State

来源：`workbench_generation_service.py`、`workbench_asset_service.py`

稳定可见字段：

- YAML：`id`, `title`, `description`, `priority`, `module`, `requirement`, `execution.page`, `execution.steps`
- State：`asset_id`, `title`, `page`, `priority`, `requirement`, `source_type`, `source_ref`, `references`, `point_count`, `point_types`, `point_keys`

---

## 2. 统一映射表（模板 -> 当前项目 -> 统一口径）

| Excel 模板字段 | 模板语义 | 当前 DB 字段 | 当前 AI/Workbench 字段 | 统一口径字段 | 去同存异策略 | 结论 |
|---|---|---|---|---|---|---|
| 用例ID | 业务可读唯一编码 | `id` 仅为整数主键，不可直接映射 | `id` / `asset_id` 是字符串 ID，当前格式为 `atp-web-...` | `case_id` | `DB.id` 保留为内部主键；模板 `用例ID` 直接使用平台标准 `case_id`；不再新增第二套 `EC-...` 编码 | 复用现有标准 |
| 用例标题 | 一句话描述系统性质 | `name` | `title` | `case_title` | `name/title` 同义合并 | 直接合并 |
| 链路环节 | 下单/优惠/库存/支付/履约/售后 | 无 | `page`、`module` 只能部分推断 | `chain_stage` | 不能用 `product_line/module/page` 硬顶替；需新增业务链路字段 | 新增统一字段 |
| 域/服务 | 被测主服务，如 `order-service` | 无 | `module` 不是服务名 | `sut_service` | 当前 `module` 是业务模块，不是微服务名，必须拆开 | 新增统一字段 |
| 关联服务 | 依赖服务列表 | 无 | 无稳定字段 | `related_services[]` | 新增数组字段，导出时逗号拼接 | 新增统一字段 |
| 优先级 | P0/P1/P2 | `priority` | `priority` | `priority` | 同义合并 | 直接复用 |
| 测试类型 | 并发/重试/乱序/延迟/补偿/对账 | `test_type` 现含义是 `ui/api/mobile/database` | `case_type/tags` 也不是模板语义 | `scenario_types[]` | 同名异义，必须拆分；保留当前 `test_type` 作为执行载体类型 | 拆分新增 |
| 触发入口 | API/Job/MQ/DB | 无 | `source` 不是触发入口 | `trigger_entry` | 新增枚举字段 | 新增统一字段 |
| 注入点类型 | 超时/失败/断连/降级/乱序/重复投递/延迟 | 无 | 无 | `fault_injection_type` | 新增 | 新增统一字段 |
| 注入点目标 | 具体接口/消费者/Job | 无 | 无 | `fault_injection_target` | 新增 | 新增统一字段 |
| 注入参数 | `delay=8s fail=30%` | 无 | 无 | `fault_injection_params` | 新增文本字段 | 新增统一字段 |
| 前置数据SQL | SQL 块/脚本路径 | 无 | 无 | `setup_sql` | 新增多行文本字段 | 新增统一字段 |
| 前置依赖状态 | 测试前依赖状态描述 | 无 | `requirement` 不是前置状态 | `precondition_state` | 新增文本字段 | 新增统一字段 |
| 测试步骤 | 可执行步骤块 | `script_code` 是代码，不是步骤块 | `execution.steps` 是结构化步骤 | `test_steps` | 优先使用结构化步骤；`script_code` 保留为自动化实现，不反向硬解析为模板步骤 | 新增统一字段，保留脚本 |
| 并发模型 | `20 threads x 5s` | 无 | 无稳定字段 | `concurrency_model` | 新增文本字段 | 新增统一字段 |
| 重试策略 | `client retry 3...` | 无 | 无 | `retry_policy` | 新增文本字段 | 新增统一字段 |
| 期望结果 | 用户可见结果 + 系统状态 | 无 | `description`/`requirement` 不能等价替代 | `expected_result` | 新增多行文本字段 | 新增统一字段 |
| 断言SQL | SQL 块 | 无 | 无 | `assert_sql` | 新增多行文本字段 | 新增统一字段 |
| 事件断言 | Outbox/Inbox/Topic 断言 | 无 | 无 | `event_assertion` | 新增多行文本字段 | 新增统一字段 |
| 指标断言 | PromQL/指标描述 | 无 | 无 | `metric_assertion` | 新增多行文本字段 | 新增统一字段 |
| 回滚/清理脚本 | 清理 SQL | 无 | 无 | `cleanup_script` | 新增多行文本字段 | 新增统一字段 |
| 产物链接 | 日志/trace/报告链接 | `test_case_executions.report_url` 仅是执行记录 | `references/source_ref` 是内部引用，不等价 | `artifact_links` | 保留模板字段为案例级产物入口；运行态 `report_url` 作为默认补充来源 | 新增统一字段，兼容运行态 |
| 备注 | 风险/手工检查点 | 无 | `description` 不是备注 | `notes` | 新增文本字段 | 新增统一字段 |

---

## 3. “同”字段：可以直接合并的

以下字段可以直接成为统一主字段，不需要双存：

| 统一字段 | 当前 DB | 当前 AI/Workbench | 模板列 | 处理方式 |
|---|---|---|---|---|
| `case_title` | `name` | `title` | 用例标题 | 统一为一个字段 |
| `priority` | `priority` | `priority` | 优先级 | 统一为一个字段 |

---

## 4. “同名异义”字段：必须拆开

这些是后续实现最容易踩坑的地方：

| 当前字段 | 当前含义 | 模板字段 | 模板含义 | 处理原则 |
|---|---|---|---|---|
| `id` | 数据库整数主键 | 用例ID | 平台标准编码，如 `atp-web-ret-query-sm-ai-0001` | 绝不能直接映射 |
| `test_type` | 执行载体或技术类型，如 `ui/api/mobile` | 测试类型 | 风险/验证类型，如 `并发/重试/补偿` | 必须拆成两个字段 |
| `module` | 页面/业务模块 | 域/服务 | 微服务/SUT，如 `order-service` | 必须拆开 |
| `product_line` | 产品线分类 | 链路环节 | 下单/优惠/库存/支付... | 不能混用 |
| `source` | 用例来源，如 `ai/manual/regression` | 触发入口 | API/Job/MQ/DB | 不能混用 |
| `script_code` | 自动化脚本实现 | 测试步骤 | 面向测试设计的步骤块 | 必须并存，不互相覆盖 |
| `report_url` / `references` | 某次运行或内部资产引用 | 产物链接 | 模板对外展示的证据入口 | 可以补充，但不能等价替代 |

---

## 5. 当前项目专有字段保留表（模板没有，但平台必须保留）

这些字段不在 Excel 模板里，但属于平台治理、执行、追踪必需信息，不建议为了导出模板而删除：

| 当前字段 | 来源 | 建议统一口径 | 是否进模板 | 说明 |
|---|---|---|---|---|
| `id` | DB | `internal_id` | 否 | 内部主键 |
| `product_line` | DB | `product_line` | 否 | 平台分类维度，保留 |
| `module` | DB | `business_module` | 否 | 业务模块，不等于服务名 |
| `tags` | DB | `tags[]` | 否 | 筛选/检索维度 |
| `markers` | DB | `markers[]` | 否 | 自动化标记 |
| `creator` | DB | `created_by` | 否 | 审计必需 |
| `pytest_path` | DB | `script_path` | 否 | 自动化脚本绑定 |
| `status` | DB | `lifecycle_status` | 否 | 生命周期状态 |
| `last_execution_result` | DB | `latest_run_result` | 否 | 最新执行结果 |
| `data_config` | DB | `data_config` | 否 | 数据驱动配置 |
| `script_code` | DB | `automation_script` | 否 | 自动化实现正文 |
| `test_case_versions` | DB | `version_history` | 否 | 版本快照 |
| `test_case_executions` | DB | `execution_history` | 否 | 执行历史 |
| `test_case_defects` | DB | `linked_defects` | 否 | 缺陷关联 |
| `project` | Workbench | `project_code` | 否 | 多项目隔离必备 |
| `page` | Workbench | `page_code` | 否 | 页面维度 |
| `source_type/source_ref/references` | Workbench | `asset_references` | 否 | 资产追溯能力 |
| `point_count/point_types/point_keys` | Workbench | `test_point_summary` | 否 | 测试点治理能力 |

---

## 6. 推荐统一字段模型（最小闭环）

建议后续统一成两层：

### 6.1 模板导出层（面向 Excel）

严格对齐 23 列：

- `case_id`
- `case_title`
- `chain_stage`
- `sut_service`
- `related_services`
- `priority`
- `scenario_types`
- `trigger_entry`
- `fault_injection_type`
- `fault_injection_target`
- `fault_injection_params`
- `setup_sql`
- `precondition_state`
- `test_steps`
- `concurrency_model`
- `retry_policy`
- `expected_result`
- `assert_sql`
- `event_assertion`
- `metric_assertion`
- `cleanup_script`
- `artifact_links`
- `notes`

### 6.2 平台治理层（模板外保留）

- `internal_id`
- `project_code`
- `product_line`
- `business_module`
- `page_code`
- `execution_surface_type`（当前 `test_type`）
- `tags`
- `markers`
- `created_by`
- `lifecycle_status`
- `script_path`
- `automation_script`
- `data_config`
- `latest_run_result`
- `version_history`
- `execution_history`
- `linked_defects`
- `asset_references`
- `test_point_summary`

---

## 7. 最终映射结论

### 7.1 可以直接复用的

- `用例标题 <- name/title`
- `优先级 <- priority`

### 7.2 必须新增的模板字段

- `chain_stage`
- `sut_service`
- `related_services`
- `scenario_types`
- `trigger_entry`
- `fault_injection_type`
- `fault_injection_target`
- `fault_injection_params`
- `setup_sql`
- `precondition_state`
- `test_steps`
- `concurrency_model`
- `retry_policy`
- `expected_result`
- `assert_sql`
- `event_assertion`
- `metric_assertion`
- `cleanup_script`
- `artifact_links`
- `notes`

### 7.3 必须保留但不进模板的系统字段

- `internal_id`
- `product_line`
- `business_module`
- `execution_surface_type(test_type)`
- `tags`
- `markers`
- `created_by`
- `lifecycle_status`
- `script_path`
- `automation_script`
- `data_config`
- `latest_run_result`
- `version_history`
- `execution_history`
- `linked_defects`
- `project_code`
- `asset_references`
- `test_point_summary`

---

## 8. 一句话口径

后续实现时应采用下面这条总原则：

**Excel 模板负责“测试设计与故障验证表达”，平台现有字段继续负责“治理、执行、审计与追踪”；两者通过统一 case 主体关联，但不互相覆盖语义。**

补充决策（2026-04-05）：

- 模板中的 `用例ID` 列，统一使用平台现有标准：`atp-web-ret-query-sm-ai-0001`
- 不再引入第二套 `EC-{域}-{类型}-{序号}` 编码
- 系统内部仍保留 `id:int` 作为数据库主键，但它只做内部兼容，不对业务用户充当主编号
