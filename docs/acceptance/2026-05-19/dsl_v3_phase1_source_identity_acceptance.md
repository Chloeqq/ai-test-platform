# DSL V3.0 第一阶段 source identity 幂等修复验收文档

文档日期：2026-05-19

验收对象：用例生成链路 `source_asset_id + intent_id` 幂等复用修复

验收范围：

- 测试点资产批量生成用例接口
- Workbench 生成用例同步到用例中心逻辑
- `upsert_test_case_from_workbench` 的重复用例复用行为
- 用例中心按来源资产筛选展示结果

不在本次验收范围：

- DSL V2/V3 新 schema 实现
- Runner 执行动作扩展
- 语义动作 `semantic_action` 编译
- 语义断言 `semantic_assertion` 编译
- 页面对象导入逻辑
- Allure 报告 UI 品牌化

## 1. 背景

本次代码修复属于 DSL V3.0 演进路线的第一阶段：先补齐生成链路的 source identity，解决重复用例和用例中心同步不稳定的问题。

目标不是直接实现 DSL V3.0，而是先保证同一个测试点资产中的同一个测试意图不会被反复生成成多条重复用例。

被测系统地址铁律：

```text
http://localhost:5174/#/login
```

本次修复不得修改被测系统地址。任何验收中发现 DSL、页面对象、Docker 或执行配置把该地址改写为平台地址、Docker 内部地址或其他临时地址，都应判定为不通过。

## 2. 核心验收结论

预期结论：

- 同一 `project + source_asset_id + intent_id` 只对应一条用例中心记录。
- 如果生成链路给出新的 `case_id`，但来源资产和 intent 与已有用例一致，应复用并更新已有用例。
- 例如已有 `mall-web-login-auth-fn-ai-0001` 绑定 `mall-web-login-auth-fn-ai-0021 + intent-01` 时，再生成同一来源和意图，即使临时生成编号为 `0003`，最终也应更新 `0001`，不应新增重复用例。

## 3. 验收项

### 验收项 1：代码静态检查

验收命令：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
python3 -m py_compile apps/web-ui-service/app/services/test_case_service.py apps/web-ui-service/tests/test_case_id_flow.py
```

通过标准：

- 命令退出码为 `0`。
- 无 Python 语法错误。

当前记录：

- 2026-05-19 已在 Codex 本地环境执行，结果通过。

### 验收项 2：单元测试验证

验收命令：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
python -m pytest apps/web-ui-service/tests/test_case_id_flow.py -k "reuses_case_by_source_asset_and_intent or creates_and_updates_case"
```

通过标准：

- `test_upsert_test_case_from_workbench_reuses_case_by_source_asset_and_intent` 通过。
- `test_upsert_test_case_from_workbench_creates_and_updates_case` 通过。
- 测试中同一 `source_asset_id + intent_id` 复用已有 `case_id`，数据库中不新增重复 `TestCase`。

当前环境限制：

- 2026-05-19 Codex 本地 Python 环境缺少 `pytest` 和 `sqlalchemy`，无法在本地直接执行该测试。
- 该项需要在 Docker 后端容器、项目虚拟环境或已安装依赖的 CI 环境中验收。

### 验收项 3：接口重复生成验证

前置条件：

- 后端服务可访问：`http://127.0.0.1:8013`
- 当前登录用户具备生成用例权限。
- 测试点资产 `mall-web-login-auth-fn-ai-0021` 存在。
- 资产内至少存在已审核通过的 `intent-01`。

验收命令示例：

```bash
curl 'http://127.0.0.1:8013/api/workbench/test-point-assets/batch/generate-cases' \
  -H 'authorization: Bearer <token>' \
  -H 'content-type: application/json' \
  --data-raw '{"project":"mall","asset_ids":["mall-web-login-auth-fn-ai-0021"],"source":"ai"}'
```

操作步骤：

1. 对同一资产执行第一次生成。
2. 记录返回的 `items[].case_id`。
3. 对同一资产执行第二次生成。
4. 再次记录返回的 `items[].case_id`。
5. 对比同一 `intent_id` 是否生成了新的重复用例。

通过标准：

- 第二次生成不应为同一 `source_asset_id + intent_id` 新增重复用例。
- 已存在用例应被复用或更新。
- `intent-01 / 首次登录成功` 不应同时出现 `0001` 和 `0003` 两条有效用例。
- 接口不应返回 `execution_compiler_intent_coverage_failed`。
- 接口不应返回 500。

失败判定：

- 同一 `source_asset_id + intent_id` 生成多条不同 `case_id`。
- 用例中心筛选来源资产后看不到生成结果。
- 接口返回 500。
- 生成结果缺失 `requirement.source_asset_id` 或 `execution.selected_intent_ids`。

### 验收项 4：用例中心页面验证

验收入口：

```text
用例中心 / Workbench Test Cases
```

筛选条件：

```text
project = mall
source_asset = mall-web-login-auth-fn-ai-0021
```

通过标准：

- 能看到来源资产 `mall-web-login-auth-fn-ai-0021` 对应的用例。
- 同一个 `intent_id` 只对应一条用例。
- `intent-01 / 首次登录成功` 不出现重复有效用例。
- 重复点击生成后，用例内容可更新，但 `case_id` 不应跳成新的重复编号。

重点观察：

- `source_asset_id`
- `source_asset_title`
- `intent_id`
- `case_id`
- 用例标题
- 最近更新时间

### 验收项 5：YAML 内容验证

检查目标：

```text
assets/test-cases/ai-generated/*.yaml
```

通过标准：

- 新生成或同步后的 YAML 中包含结构化来源信息。

示例：

```yaml
requirement:
  intent_id: intent-01
  title: 首次登录成功
  type: functional
  source_asset_id: mall-web-login-auth-fn-ai-0021
execution:
  selected_intent_ids:
    - intent-01
```

失败判定：

- 只有 `intent_id`，缺少 `source_asset_id`。
- 只有自然语言 requirement，无法稳定解析来源资产。
- 同一个 intent 被写入多个不同 case YAML 且都在用例中心有效。

## 4. 数据库辅助核查

如果可以进入数据库，可用以下思路核查。

核查目标：

- 同一项目下，绑定同一来源资产和 intent 的用例数量应为 1。
- 若历史存在重复，应确认后续再次生成不会继续增加重复数量。

建议核查字段：

- `test_cases.case_id`
- `test_cases.project_code`
- `test_cases.script_code`
- `test_cases.name`
- `test_cases.updated_at`

核查重点：

- 从 `script_code.requirement.source_asset_id` 解析来源资产。
- 从 `script_code.requirement.intent_id` 或 `script_code.execution.selected_intent_ids` 解析 intent。
- 判断同一 `project_code + source_asset_id + intent_id` 是否出现多条有效记录。

## 5. 回归风险

### 风险 1：历史脏数据仍存在

本次修复阻止后续继续新增重复用例，但不自动删除历史重复数据。

处理建议：

- 先验收后续生成不再新增重复。
- 再单独制定历史重复用例清理方案。

### 风险 2：多 intent 用例暂不按 source identity 复用

本次只对单 intent 用例执行 `source_asset_id + intent_id` 复用。

原因：

- 多 intent 用例涉及组合覆盖，不能简单按单个 intent 覆盖已有用例。

验收标准：

- 单 intent 场景必须幂等。
- 多 intent 场景暂不纳入本次通过条件。

### 风险 3：缺少 source_asset_id 的旧 YAML 无法稳定复用

如果历史 YAML 没有 `source_asset_id`，系统无法可靠判断来源资产。

处理建议：

- 后续补一个历史 YAML source identity 回填任务。
- 本次只验收新生成和已具备来源字段的用例。

### 风险 4：本地依赖不完整导致测试不能直接跑

Codex 本地环境缺少 `pytest` 和 `sqlalchemy`。

处理建议：

- 在 Docker 后端容器或项目虚拟环境中执行完整单测。
- Codex 本地只完成语法检查和代码审查。

## 6. 最终通过标准

本次修复可判定通过，当且仅当满足以下条件：

- 代码静态检查通过。
- 单元测试在具备依赖的环境中通过。
- 同一资产重复调用生成接口后，同一 intent 不新增重复用例。
- 用例中心按来源资产筛选能看到对应用例。
- `intent-01 / 首次登录成功` 不再同时新增多个有效 case。
- YAML 中保留 `source_asset_id` 与 `selected_intent_ids`。
- 被测系统地址仍为 `http://localhost:5174/#/login`，未被任何生成或同步流程改写。

## 7. 当前验收状态

截至 2026-05-19：

- 已完成：语法检查。
- 待完成：依赖完整环境中的单元测试。
- 待完成：Docker/后端服务环境中的接口重复生成验证。
- 待完成：用例中心页面筛选验证。
- 待完成：生成 YAML 内容抽查。
