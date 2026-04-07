# 测试用例 Excel 导出实现方案（2026-04-05）

> 文档版本：v1.0  
> 文档目标：基于用户提供的 Excel 模板，实现测试用例下载导出，并确保 `用例ID` 输出平台标准 `case_id`。  
> 适用范围：`apps/web-ui-service` 导出接口、导出服务、模板文件、测试用例字段映射

---

## 1. 设计前提

本方案遵循以下已确认决议：

1. 模板 `用例ID` 直接输出平台 `case_id`
2. 数据库自增 `id` 不进入模板导出
3. 导出格式以用户上传模板为准，不再输出第二套业务编号

关联文档：

- [测试用例模板映射表（2026-04-05）](./test-case-template-mapping-table-2026-04-05.md)
- [测试用例字段落库方案（2026-04-05）](./test-case-field-persistence-plan-2026-04-05.md)
- [测试用例编号统一与实施优先级（2026-04-05）](./test-case-case-id-unification-priority-plan-2026-04-05.md)

---

## 2. 模板实物核查结果

已对 `/docs/用例模版示例.xlsx` 做实际结构核查。

核查结果：

1. 工作簿只有一个 sheet：`用例示例`
2. 模板固定 23 列，范围为 `A:W`
3. 第 1 行为固定表头
4. 首行已冻结
5. 列宽已配置
6. 示例数据从第 2 行开始
7. 多个字段为长文本、多行文本，不能退化成简单 CSV 思路

固定表头如下：

1. 用例ID
2. 用例标题
3. 链路环节
4. 域/服务
5. 关联服务
6. 优先级
7. 测试类型
8. 触发入口
9. 注入点类型
10. 注入点目标
11. 注入参数
12. 前置数据SQL
13. 前置依赖状态
14. 测试步骤
15. 并发模型
16. 重试策略
17. 期望结果
18. 断言SQL
19. 事件断言
20. 指标断言
21. 回滚/清理脚本
22. 产物链接
23. 备注

结论：

- 导出必须生成真正的 `.xlsx`
- 不适合继续沿用当前 `csv/json` 逻辑直接替代
- 最稳方案是“读取模板 -> 清空示例数据 -> 写入实际数据 -> 输出”

---

## 3. 当前导出链路问题

当前导出实现在：

- `apps/web-ui-service/app/routers/test_cases.py`
- `apps/web-ui-service/app/services/test_case_mapper.py`

当前问题：

| 问题 | 当前现状 | 影响 |
|---|---|---|
| 导出格式不足 | 仅支持 `csv/json` | 不能按模板下载 Excel |
| 导出字段不对 | 当前首列是 `id` | 与模板 `用例ID = case_id` 冲突 |
| 缺少模板字段 | 当前只导出基础管理字段 | 模板 23 列无法补齐 |
| 缺少样式保留 | 当前纯文本导出 | 无法保留模板列宽、冻结首行、多行文本表现 |

---

## 4. 总体实现策略

### 4.1 方案选择

推荐方案：`模板驱动导出`

实现方式：

1. 读取模板文件 `docs/用例模版示例.xlsx`
2. 打开工作表 `用例示例`
3. 保留第 1 行表头、列宽、冻结首行等模板属性
4. 删除或清空第 2 行开始的示例数据
5. 将真实用例映射为 23 列模板行
6. 输出新的 `.xlsx`

### 4.2 技术选型

推荐依赖：

- `openpyxl>=3.1,<4.0`

原因：

1. 能读取现有模板
2. 能保留工作表基础格式
3. 能处理多行文本
4. 适合做样式复制

不推荐：

- 继续用 `csv`
- 只生成 XML 或伪 Excel
- 用 `xlsxwriter` 从零重绘模板

原因：

- `xlsxwriter` 适合新建工作簿，不适合复用现有模板样式

---

## 5. 目标导出接口

## 5.1 接口策略

在现有批量导出接口上扩展：

- 路径：`POST /api/test-cases/batch/export`

扩展 `format`：

- `json`
- `csv`
- `xlsx`

建议文件名：

- `test-cases-template.xlsx`

## 5.2 入参建议

过渡期建议支持：

```json
{
  "ids": [1, 2, 3],
  "case_ids": ["atp-web-ret-query-sm-ai-0001"],
  "format": "xlsx"
}
```

处理优先级：

1. 若传 `case_ids`，优先按 `case_ids` 导出
2. 否则按 `ids` 兼容导出

---

## 6. 导出字段映射

## 6.1 模板字段到数据库字段

| Excel 列 | 输出字段 | 来源 | 说明 |
|---|---|---|---|
| 用例ID | `case_id` | `test_cases.case_id` | 业务编号 |
| 用例标题 | `case_title` | `test_cases.name` | 当前阶段由 `name` 提供 |
| 链路环节 | `chain_stage` | `test_cases.chain_stage` | 模板字段 |
| 域/服务 | `sut_service` | `test_cases.sut_service` | 模板字段 |
| 关联服务 | `related_services` | `test_cases.related_services` | 数组转逗号 |
| 优先级 | `priority` | `test_cases.priority` | 直接输出 |
| 测试类型 | `scenario_types` | `test_cases.scenario_types` | 数组转逗号 |
| 触发入口 | `trigger_entry` | `test_cases.trigger_entry` | 直接输出 |
| 注入点类型 | `fault_injection_type` | `test_cases.fault_injection_type` | 直接输出 |
| 注入点目标 | `fault_injection_target` | `test_cases.fault_injection_target` | 直接输出 |
| 注入参数 | `fault_injection_params` | `test_cases.fault_injection_params` | 直接输出 |
| 前置数据SQL | `setup_sql` | `test_cases.setup_sql` | 多行文本 |
| 前置依赖状态 | `precondition_state` | `test_cases.precondition_state` | 多行文本 |
| 测试步骤 | `test_steps_text` | `test_cases.test_steps_text` | 优先文本 |
| 并发模型 | `concurrency_model` | `test_cases.concurrency_model` | 直接输出 |
| 重试策略 | `retry_policy` | `test_cases.retry_policy` | 多行文本 |
| 期望结果 | `expected_result` | `test_cases.expected_result` | 多行文本 |
| 断言SQL | `assert_sql` | `test_cases.assert_sql` | 多行文本 |
| 事件断言 | `event_assertion` | `test_cases.event_assertion` | 多行文本 |
| 指标断言 | `metric_assertion` | `test_cases.metric_assertion` | 多行文本 |
| 回滚/清理脚本 | `cleanup_script` | `test_cases.cleanup_script` | 多行文本 |
| 产物链接 | `artifact_links` | `test_cases.artifact_links` | 多链接换行 |
| 备注 | `notes` | `test_cases.notes` | 多行文本 |

## 6.2 导出默认值策略

建议统一如下：

| 字段类型 | 默认值策略 |
|---|---|
| 业务编号、标题、优先级 | 不允许空，缺值视为数据问题 |
| 不适用类字段 | 输出 `N/A` |
| 长文本说明类字段 | 输出空字符串 |
| 数组类字段 | 空数组导出为空字符串 |
| 产物链接 | 若无案例级链接，则回退最近一次 `report_url` |

### 6.2.1 建议使用 `N/A` 的字段

- 注入点类型
- 注入点目标
- 注入参数
- 并发模型
- 重试策略

仅当明确“不适用”时输出 `N/A`，不要把所有空字段都写成 `N/A`。

### 6.2.2 `测试步骤` 的降级策略

推荐优先级：

1. `test_steps_text`
2. 根据 `test_steps` 结构化 JSON 渲染
3. 根据 AI/Workbench 执行步骤渲染
4. 仍无数据则空字符串

结构化步骤渲染示例：

```text
Step1 登录系统
Step2 打开退货申请页面
Step3 输入服务单号
Step4 点击查询
Step5 校验结果列表可见
```

### 6.2.3 `产物链接` 的降级策略

推荐优先级：

1. `artifact_links`
2. `last_report_url`
3. 最近一次执行记录 `report_url`

多个链接使用换行拼接，不用逗号，便于在 Excel 单元格中阅读。

---

## 7. 实现拆分建议

## 7.1 新增服务

建议新增：

- `apps/web-ui-service/app/services/test_case_export_service.py`

职责：

1. 加载模板
2. 组装导出数据
3. 映射模板行
4. 生成 `.xlsx` 二进制内容

建议拆分函数：

| 函数 | 职责 |
|---|---|
| `load_export_template()` | 加载模板工作簿 |
| `build_template_row(case)` | 将单条用例映射为 23 列 |
| `render_steps_text(case)` | 渲染测试步骤文本 |
| `render_artifact_links(case)` | 渲染产物链接 |
| `build_export_workbook(cases)` | 生成最终工作簿 |

## 7.2 Mapper 调整策略

当前 `test_case_mapper.py` 仍可保留：

- `build_export_csv(...)`
- `build_export_json(...)`

新的 `xlsx` 逻辑不建议继续塞入 Mapper，建议下沉到独立 Export Service。

原因：

1. Excel 导出是独立的模板处理逻辑
2. 样式、模板、二进制输出超出 Mapper 职责

---

## 8. 模板写入细节

## 8.1 样式保留策略

推荐实现：

1. 读取模板后，拿第 2 行作为“数据样式参考行”
2. 在删除示例数据前，缓存第 2 行每个单元格样式
3. 删除第 2 行及之后所有旧示例数据
4. 写入实际数据时，对每个单元格复制参考样式

保留内容：

- 列宽
- 冻结首行
- 数据行对齐与换行样式

## 8.2 多行文本策略

以下字段按多行文本输出：

- 前置数据SQL
- 前置依赖状态
- 测试步骤
- 重试策略
- 期望结果
- 断言SQL
- 事件断言
- 指标断言
- 回滚/清理脚本
- 产物链接
- 备注

要求：

1. 写入真实换行符 `\n`
2. 单元格启用 `wrap_text`
3. 不把多行内容折成单行

## 8.3 工作表行为

需要保证：

1. sheet 名称保持 `用例示例`
2. 表头不变
3. 示例数据不会残留
4. 导出文件打开后首行仍冻结

---

## 9. 测试方案

## 9.1 单元测试

建议新增导出测试，覆盖：

1. 模板表头不变
2. `用例ID` 输出 `case_id`
3. 多行字段保留换行
4. 数组字段正确序列化
5. 空字段按策略回退

## 9.2 集成测试

建议覆盖：

1. `/api/test-cases/batch/export` 返回 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
2. 文件名正确
3. 导出后工作簿可正常打开
4. 第一行 23 列与模板完全一致
5. 第二行开始写入真实用例数据

## 9.3 回归检查

需要回归：

1. 原 `csv/json` 导出不受影响
2. 批量导出仍支持现有批量选择流程
3. 中文、SQL、长文本不乱码

---

## 10. 依赖与文件变更清单

建议变更如下：

### 10.1 依赖

`apps/web-ui-service/requirements.txt`

新增：

```txt
openpyxl>=3.1,<4.0
```

### 10.2 新增文件

建议新增：

- `apps/web-ui-service/app/services/test_case_export_service.py`

### 10.3 修改文件

建议修改：

- `apps/web-ui-service/app/routers/test_cases.py`
- `apps/web-ui-service/app/schemas/test_case.py`
- `apps/web-ui-service/app/services/test_case_service.py`

如果需要前端显式下载提示，再补：

- `apps/web-ui-service/app/static/cases_api.js`
- `apps/web-ui-service/app/static/*`

---

## 11. 推荐实施顺序

推荐顺序如下：

1. 完成字段落库
2. 补齐模板字段与回填策略
3. 接入 `openpyxl`
4. 新增导出服务
5. 扩展 `format=xlsx`
6. 补单元测试和集成测试
7. 前端接入下载按钮或批量导出入口

---

## 12. 验收标准

导出实现完成后，应满足：

1. 用户可下载与模板一致的 `.xlsx`
2. `用例ID` 列输出平台 `case_id`
3. 模板 23 列全部可输出
4. 多行 SQL/步骤/备注字段在 Excel 中可读
5. 不再把数据库 `id` 当业务编号导出

---

## 13. 推荐优先级

本专项优先级如下：

1. `P0` 字段落库完成
2. `P1` Excel 导出实现
3. `P1` 前端下载入口与批量导出联动
4. `P2` 模板字段智能补全优化

---

## 14. 变更记录

| 日期 | 版本 | 变更内容 |
|---|---|---|
| 2026-04-05 | v1.0 | 首版 Excel 导出实现方案，明确模板驱动导出、字段映射、依赖、接口与测试策略 |
