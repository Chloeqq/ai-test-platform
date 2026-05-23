# DSL V1.1 script_code 唯一事实源收口验收文档

文档日期：2026-05-22

验收对象：DSL V1.1 阶段 `script_code` 唯一事实源收口

验收范围：

- `run_case` 执行入口是否 DB `script_code` 优先、文件 YAML 兜底。
- 用例详情展示是否能解析结构化 `requirement`。
- `script_code.execution.steps` 到 `test_steps/TestCaseStep` 的投影是否保留 DSL V1.1 字段。
- runner 单文件 `TEST_CASE_PATH` 是否执行 schema 校验。
- `TEST_CASE_ALLOWED_ROOTS` 是否不再按任意 `case_path.parent` 动态放宽。
- 流程图留档中的 P0/P1/P2 未完成项状态是否已收口。

不在本次验收范围：

- DSL V2/V3 schema 落地。
- 语义动作 `semantic_action` 编译器实现。
- 语义断言 `semantic_assertion` 编译器实现。
- 页面对象导入链路。
- Allure 报告 UI 品牌化。
- 真实浏览器页面手工点击验收。

被测系统地址铁律：

```text
http://localhost:5174/#/login
```

本次验收不得修改、替换或写回被测系统地址。

## 1. 核心验收结论

自动化验收结论：通过。

已确认：

- Python 语法编译通过。
- 流程图留档中不再残留 `未完成 / 待修 / 待完成 / 尚未 / 仍会 / 仍可能 / 偏宽` 等未收口状态词。
- `run_case` 使用 DB `script_code` 作为运行事实源的测试通过。
- 结构化 `requirement` 的详情 mapper 测试通过。
- 工作台用例详情接口从 `script_code.requirement` 兜底返回元数据的集成测试通过。
- `normalize_test_steps()` 保留 DSL V1.1 关键字段的测试通过。
- runner 单文件 schema 校验测试通过。
- 运行时路径白名单收紧测试通过。

仍需人工补充验收：

- 打开平台用例详情页，确认前置条件、来源资产、intent、步骤展示符合 `script_code`。
- 实际执行一条登录用例，确认运行态 YAML 来自 DB `script_code`，失败/成功报告与用例详情一致。
- 打开 Allure 或失败详情，确认报告中的步骤、参数、来源信息与本次 DSL V1.1 链路一致。

## 2. 验收项与结果

### 验收项 1：Python 语法编译

验收命令：

```bash
python3 -m py_compile \
  apps/web-ui-service/app/api/workbench/facade.py \
  apps/web-ui-service/app/services/test_case_data_service.py \
  apps/web-ui-service/app/services/test_case_mapper.py \
  apps/web-ui-service/app/services/workbench_runtime_service.py \
  runners/web-playwright-python/runner/test_case_loader.py \
  runners/web-playwright-python/runner/yaml_loader.py
```

验收结果：

- 2026-05-22 已执行。
- 结果通过，退出码为 `0`。

### 验收项 2：流程图留档状态收口

验收命令：

```bash
rg -n "未完成|待修|待完成|尚未|仍会|仍可能|偏宽" \
  docs/代码流程图/2026-05-22_DSL_V1.1_script_code唯一事实源流程图与代码评审.md
```

验收结果：

- 2026-05-22 已执行。
- 未检出未完成状态关键词。
- `rg` 返回退出码 `1`，表示没有匹配项，符合预期。

### 验收项 3：用例 ID 与运行事实源链路

验收命令：

```bash
.venv/bin/pytest apps/web-ui-service/tests/test_case_id_flow.py -q
```

验收结果：

- 2026-05-22 已执行。
- `12 passed in 0.60s`

覆盖重点：

- `run_case` 在 DB 有 `script_code` 时，不依赖源 YAML 文件。
- `script_code.execution.steps` 投影到 `test_steps` 时保留 `element_code / source_point_key / metric_rule` 等字段。
- 用例生成、更新、执行身份链路继续保持稳定。

### 验收项 4：用例详情结构化 requirement 展示

验收命令：

```bash
.venv/bin/pytest apps/web-ui-service/tests/unit/test_case_detail_content.py -q
```

验收结果：

- 2026-05-22 已执行。
- `4 passed in 0.09s`

非阻断提示：

- 本次 pytest 结束后出现一次临时目录清理 warning，内容为 `/private/var/folders/.../pytest-of-bettyhuang/garbage-* Directory not empty`。
- 该 warning 来自 pytest 临时目录清理，不影响业务测试断言结果。

覆盖重点：

- `requirement` 为 object 时，详情 mapper 能展示 `intent_id / source_asset_id / precondition / title`。
- 旧格式 requirement 仍保持兼容。

### 验收项 5：运行时路径白名单

验收命令：

```bash
.venv/bin/pytest apps/web-ui-service/tests/unit/test_workbench_runtime_service.py -q
```

验收结果：

- 2026-05-22 已执行。
- `11 passed in 0.03s`

覆盖重点：

- runtime YAML 位于 `runtime-cases/{run_id}` 下时允许执行。
- 不再把任意普通 `case_path.parent` 加入 `TEST_CASE_ALLOWED_ROOTS`。

### 验收项 6：runner 单文件 schema 校验

验收命令：

```bash
.venv/bin/pytest runners/web-playwright-python/tests/test_ai_generated_loader.py -q
```

验收结果：

- 2026-05-22 已执行。
- `5 passed in 0.53s`

非阻断提示：

- 存在既有 warning：`PytestUnknownMarkWarning: Unknown pytest.mark.contract`。
- 该 warning 表示 runner 测试工程未注册 `contract` mark，不影响本次测试通过结论。

覆盖重点：

- `TEST_CASE_PATH` 单文件加载也会执行 schema 校验。
- 缺少必填字段的运行态 YAML 会在 loader 阶段失败，而不是拖到 executor 阶段。

### 验收项 7：工作台用例生成与详情集成点

验收命令：

```bash
.venv/bin/pytest \
  apps/web-ui-service/tests/integration/test_workbench_assets_api.py::test_workbench_test_cases_links_generated_case_to_source_asset_by_selected_intents \
  apps/web-ui-service/tests/integration/test_workbench_assets_api.py::test_workbench_test_case_detail_uses_structured_requirement_metadata \
  -q
```

验收结果：

- 2026-05-22 已执行。
- `2 passed in 0.15s`

覆盖重点：

- 生成用例能通过 selected intents 关联来源资产。
- `/api/workbench/test-cases/{case_id}` 能从 `script_code.requirement` 返回 `precondition / source_asset_id / source_asset_title / intent_type`。

## 3. 验收风险与观察项

### 风险 1：页面手工验收尚未执行

当前自动化测试已覆盖核心代码链路，但尚未在浏览器中验证用例详情页、执行结果页和报告页真实展示。

建议下一步：

- 启动后端和前端。
- 打开用例中心详情页。
- 对一条 DSL V1.1 用例执行一次真实运行。
- 对比页面展示、运行记录、失败证据和 Allure 报告是否一致。

### 风险 2：历史脏数据仍可能影响页面观感

本次 DSL V1.1 收口保证新链路以 `script_code` 为事实源，但历史用例如果缺少 `script_code` 或含有旧格式 YAML，仍会走文件兜底或 legacy 兼容逻辑。

建议下一步：

- 对用例中心做只读诊断，列出 `script_code` 为空的用例。
- 对缺少 `requirement.source_asset_id / intent_id` 的用例单独治理。
- 不允许页面投影字段反向覆盖 `script_code`。

### 风险 3：runner contract mark warning 尚未治理

`runners/web-playwright-python/tests/test_ai_generated_loader.py` 存在 `pytest.mark.contract` 未注册 warning。

建议下一步：

- 在 runner pytest 配置中注册 `contract` mark。
- 该项属于测试工程规范，不阻断 DSL V1.1 功能验收。

## 4. 人工验收清单

建议进入页面验收时逐项确认：

- 用例详情页能展示来源资产、intent、前置条件、步骤。
- 前置条件与步骤来自 `script_code`，不是旧 `metadata.selected_candidates` 或旧 YAML 文件。
- 点击执行后，runtime YAML 内容与 DB `script_code` 一致。
- 如果源 YAML 文件缺失但 DB `script_code` 存在，用例仍可进入执行。
- 执行失败时，失败详情中的步骤、locator、来源资产与用例详情一致。
- Allure 报告中的业务标签、步骤和运行结果不与用例详情冲突。
- 被测系统地址仍是 `http://localhost:5174/#/login`。

## 5. 最终判定

自动化验收判定：通过。

页面人工验收判定：待执行。

DSL V1.1 第一阶段代码层收口状态：可以进入页面级人工验收与真实用例执行验收。
