# 测试点生成用例失败问题复盘与治理方案

文档日期：2026-05-18

记录状态：问题复盘与治理方案留档

适用范围：`mall` 项目测试点资产生成用例链路、用例中心列表链路、页面对象映射链路

关联接口：

- `POST /api/workbench/test-point-assets/batch/generate-cases`
- `GET /api/workbench/test-cases`
- `GET /api/workbench/test-point-assets/{asset_id}`

## 1. 背景

触发场景：

- 页面：测试点资产详情页
- 资产：`mall-web-login-auth-fn-ai-0021`
- 操作：点击“生成已通过用例”
- 接口：`POST /api/workbench/test-point-assets/batch/generate-cases`
- 请求：

```json
{
  "project": "mall",
  "asset_ids": ["mall-web-login-auth-fn-ai-0021"],
  "source": "ai"
}
```

实际现象：

- 用户已将测试资产中心测试点审核通过。
- 点击生成后，用例中心没有出现预期的新增列表。
- 接口曾出现 `500 Internal Server Error`。
- 后续明确返回 `422`，错误核心如下：

```json
{
  "code": "execution_compiler_intent_coverage_failed",
  "message": "compiled steps do not strictly match selected intents",
  "reason": "selected intent ids and compiled intent ids are inconsistent",
  "selected_intent_ids": ["intent-02"],
  "compiled_intent_ids": [],
  "missing_intent_ids": ["intent-02"]
}
```

## 2. 当前事实

### 2.1 审核通过不等于生成用例

`/api/workbench/test-point-reviews/batch` 只负责更新测试点审核状态。

它不会自动创建 `test_cases` 数据库记录。

因此，用例中心是否出现列表，取决于后续是否成功调用：

```text
POST /api/workbench/test-point-assets/batch/generate-cases
```

### 2.2 用例中心查询的是数据库用例

用例中心页面调用：

```text
GET /api/workbench/test-cases
```

该接口查询数据库表 `test_cases`。

因此，只有生成链路成功同步到数据库后，用例中心才会展示。

### 2.3 当前已有部分用例生成成功

实际验证中，列表接口可以返回 `mall` 项目下的用例：

```text
mall-web-login-auth-fn-ai-0001
mall-web-login-auth-fn-ai-0002
```

来源资产均为：

```text
mall-web-login-auth-fn-ai-0021
```

这说明“用例中心列表本身不可用”不是主因。主因在“再次生成/批量生成某些测试点”时失败。

## 3. 根因分析

### 3.1 直接根因：intent 覆盖校验失败

生成链路会对每个测试点的 `selected_intent_ids` 做严格覆盖校验。

当前失败点是：

```text
selected_intent_ids = ["intent-02"]
compiled_intent_ids = []
missing_intent_ids = ["intent-02"]
```

含义：

- 后端准备生成 `intent-02`。
- 编译器最终没有编译出任何属于 `intent-02` 的可执行步骤。
- 严格校验发现“选中的测试点没有被实际脚本覆盖”。
- 因此拒绝生成，避免生成一条看似成功、实际没有覆盖测试意图的假用例。

这是合理的质量门禁。

### 3.2 可能的业务原因

`intent-02` 无法编译出步骤，常见原因包括：

- 测试点步骤缺少可映射的页面元素。
- 测试点中的中文元素名与页面对象别名不匹配。
- 页面对象中缺少 `approved + high/medium + active` 的合格元素。
- 测试点只保留了自然语言描述，没有形成 `steps_hint` 或结构化步骤。
- 页面对象导入后元素编码为 `data-testid`，但测试点仍引用旧中文名或旧元素名。

### 3.3 次生根因：单个失败测试点拖垮整批生成

当前“生成已通过用例”会读取资产下所有已通过测试点。

如果其中某个测试点失败，例如 `intent-02`，可能导致本次生成整体失败或返回异常。

这会造成用户误解：

```text
我明明审核通过了所有测试点，为什么用例中心没有列表？
```

正确体验应是：

```text
可生成的测试点成功生成；
不可生成的测试点明确列出失败原因。
```

### 3.4 次生根因：业务 422 曾被 DB 连接异常污染成 500

日志中出现过：

```text
page_object_db_lookup_failed
reason = mall/web/login: OperationalError
server closed the connection unexpectedly
```

说明页面对象 DB 查询或请求收尾阶段遇到 PostgreSQL 连接断开。

原本应返回的业务错误是 `422`，但在 FastAPI 依赖会话关闭或 rollback 时，连接异常再次抛出，最终被用户看到为：

```text
500 Internal Server Error
```

这不是生成规则本身的业务错误，而是错误处理链路不够稳健导致的错误污染。

## 4. 冲突范围

### 4.1 受影响功能

- 测试点资产详情页“生成已通过用例”
- 待审核用例详情页“生成用例”
- 用例中心列表刷新
- 测试点到脚本的编译链路
- 页面对象治理与元素映射链路

### 4.2 受影响数据

- `test_points` 或测试点资产 JSON 中的审核状态
- `assets/test-cases/ai-generated/*.yaml`
- 数据库表 `test_cases`
- 数据库表 `test_case_steps`
- 数据库表 `test_case_versions`
- 页面对象表 `page_objects`
- 页面元素表 `page_elements`

### 4.3 不应影响的范围

以下内容不应被本问题修复改动：

- 被测系统原始地址，例如 `http://localhost:5174/#/login`
- 已存在用例的业务 ID
- 已存在测试点的 `intent_id`
- 页面对象中已审核通过的真实 `data-testid`
- Allure 报告历史产物
- 用例执行器的实际运行目标地址

## 5. 解决方案

### 5.1 保留严格 intent 覆盖校验

不要关闭：

```text
execution_compiler_intent_coverage_failed
```

原因：

- 这是防止“空脚本”“错脚本”“覆盖错测试点”的关键质量门禁。
- 如果关闭该校验，平台可能生成看似成功但没有覆盖测试点的伪用例。
- 对企业级测试资产而言，宁可明确失败，也不能生成不可信用例。

### 5.2 批量生成改为单测试点隔离

将资产内 approved 测试点拆成单个 intent 逐条生成：

```text
intent-01 -> 独立生成
intent-02 -> 独立生成
intent-03 -> 独立生成
```

预期行为：

- `intent-01` 成功则立即落库。
- `intent-02` 失败只记录到 skipped。
- 其他测试点不受影响。
- 接口最终返回“成功数量 + 失败明细”。

这样可以避免一个坏测试点拖垮整包资产。

### 5.3 对页面对象 DB 查询增加连接异常兜底

页面对象解析 `resolve_page_object` 查询数据库时，应对 `OperationalError` 做一次重试。

建议策略：

- 第一次 DB 查询失败，记录 warning。
- 重新打开新的 SQLAlchemy Session 再查一次。
- 第二次仍失败，则返回明确的 `page_object_db_lookup_failed`。
- 不把连接异常伪装成“页面对象不存在”。

这样可以区分两类问题：

- 业务问题：页面对象没治理好。
- 基础设施问题：数据库连接中断。

### 5.4 业务错误返回前安全处理 DB 会话

当生成接口准备返回 `422` 时，如果当前 Session 已经可能被下游异常污染，应先执行安全 rollback。

如果 rollback 本身失败，则 invalidate 当前连接。

目标：

- 保留真实业务错误 `422`。
- 避免在请求收尾阶段被二次异常覆盖成 `500`。
- 前端能展示可读的失败原因，而不是 `Internal Server Error`。

### 5.5 前端展示部分成功与失败明细

生成接口返回应能表达：

```json
{
  "count": 1,
  "items": [],
  "summary": {
    "skipped": [
      {
        "asset_id": "mall-web-login-auth-fn-ai-0021",
        "intent_id": "intent-02",
        "reason": "execution_compiler_intent_coverage_failed"
      }
    ]
  }
}
```

前端提示应从：

```text
生成已通过用例失败
```

升级为：

```text
已生成 1 条用例；1 条测试点未生成：intent-02 缺少可编译步骤。
```

## 6. 为什么这样解决

### 6.1 不自动把审核通过等同于生成

审核是质量确认动作。

生成是资产生产动作。

两者应保持独立，否则用户只想“审核测试点”时，系统可能隐式生成大量用例，带来不可控的数据膨胀。

### 6.2 不放松 intent 覆盖校验

当前错误虽然影响体验，但校验本身是正确的。

真正要修的是：

- 哪个测试点失败要说清楚。
- 其他测试点不能被连坐。
- 业务错误不能变成 500。

### 6.3 逐 intent 生成更符合批量任务语义

批量生成不是事务型“全成功或全失败”。

它更像任务队列：

- 单项成功就产出。
- 单项失败就记录。
- 最后汇总给用户。

这种方式对测试资产平台更稳定，也更适合后续批量执行、批量报告和批量重试。

### 6.4 DB 断连重试是基础设施韧性，不改变业务规则

增加一次重试只处理瞬时连接问题。

它不会绕过页面对象治理，也不会生成缺失元素的脚本。

## 7. 风险点

### 7.1 部分成功可能让用户误以为全部成功

风险：

- 用户只看到“生成成功”，忽略 skipped 明细。

控制：

- 前端必须展示成功数量和失败数量。
- 失败明细必须可展开查看。

### 7.2 重复点击可能继续生成重复用例

风险：

- 如果 Upsert 规则不完善，多次点击会继续新增 `mall-web-login-auth-fn-ai-0002`、`0003`。

控制：

- 后续必须以 `source_asset_id + intent_id` 做幂等 Upsert。
- 已存在同来源测试点用例时，更新脚本和版本，不新增记录。

### 7.3 失败测试点被长期忽略

风险：

- 部分成功后，失败的 `intent-02` 可能被跳过没人处理。

控制：

- 生成结果中保留 skipped 明细。
- 测试点列表增加“生成失败原因”或“最近生成状态”。

### 7.4 DB 重试掩盖基础设施问题

风险：

- 如果数据库频繁断连，一次重试可能让问题不明显。

控制：

- 第一次失败必须记录 warning。
- 第二次失败仍返回明确错误。
- 监控 `page_object_db_lookup_failed` 次数。

### 7.5 前端筛选导致“看不到”

风险：

- 用例已经生成，但被 `project`、`active_status`、`source_asset`、`page` 过滤掉。

控制：

- 用例中心默认 `project=mall`。
- 生成成功后的跳转携带正确 `project` 和 `source_asset`。
- 空列表时展示当前过滤条件。

## 8. 验证方法

### 8.1 验证资产审核状态

检查测试点资产详情：

- `intent-01` 是否 approved。
- `intent-02` 是否 approved。
- 是否仍存在生成阻断。

接口：

```text
GET /api/workbench/test-point-assets/mall-web-login-auth-fn-ai-0021?project=mall
```

### 8.2 验证生成接口返回

调用：

```bash
curl 'http://127.0.0.1:8013/api/workbench/test-point-assets/batch/generate-cases' \
  -H 'content-type: application/json' \
  --data-raw '{"project":"mall","asset_ids":["mall-web-login-auth-fn-ai-0021"],"source":"ai"}'
```

预期：

- 不应返回 `500`。
- 如果仍有坏测试点，应返回 `422` 或部分成功响应。
- 错误中应明确指出 `intent_id` 和失败原因。

### 8.3 验证用例中心列表

调用：

```text
GET /api/workbench/test-cases?project=mall&page_index=1&page_size=20&active_status=active
```

预期：

- 能看到 `source_asset_id=mall-web-login-auth-fn-ai-0021` 的用例。
- `summary.total` 大于 0。
- 页面上不应因为筛选条件误显示为空。

### 8.4 验证数据库落库

查询 `test_cases`：

```sql
select
  case_id,
  project_code,
  page_code,
  status,
  name,
  source_ref,
  updated_at
from test_cases
where project_code = 'mall'
order by updated_at desc;
```

预期：

- 生成成功的用例存在。
- `project_code=mall`。
- `page_code=login`。
- `status` 不是 `deprecated`。

### 8.5 验证失败测试点可诊断

对 `intent-02` 单独生成：

```json
{
  "project": "mall",
  "asset_ids": ["mall-web-login-auth-fn-ai-0021"],
  "intent_ids": ["intent-02"],
  "source": "ai"
}
```

预期：

- 如果失败，应稳定返回 `execution_compiler_intent_coverage_failed`。
- 不应返回 `500`。
- 错误原因应能指向缺失步骤、缺失元素映射或页面对象治理问题。

### 8.6 验证页面对象治理

检查 `mall / web / login` 页面对象：

- 页面对象存在。
- `page_url` 保持原始被测系统地址。
- 登录相关元素为 `approved + high/medium + active`。
- 元素别名能覆盖测试点中使用的中文元素名。

### 8.7 验证日志

关注日志关键字：

```text
execution_compiler_intent_coverage_failed
page_object_db_lookup_failed
OperationalError
server closed the connection unexpectedly
```

预期：

- 业务错误不再被二次污染成 500。
- DB 断连有 warning 日志。
- 页面对象治理失败有明确 reason。

## 9. 后续治理建议

### 9.1 增加生成前预检

在点击“生成已通过用例”前，先返回每个测试点的可生成状态：

```text
intent-01 可生成
intent-02 缺少可编译步骤
intent-03 页面对象缺少元素
```

### 9.2 增加生成结果面板

生成后展示：

- 成功生成数量
- 更新用例数量
- 跳过测试点数量
- 每个 skipped 的 intent_id、标题、原因和修复入口

### 9.3 完成来源测试点 Upsert

以如下字段作为幂等键：

```text
project_code + source_asset_id + intent_id
```

目标：

- 第一次生成：创建用例。
- 再次生成：更新同一用例并版本 +1。
- 用例中心永远只显示该测试点的一条当前有效用例。

### 9.4 为 intent 覆盖失败提供修复入口

当出现：

```text
execution_compiler_intent_coverage_failed
```

页面应引导用户检查：

- 测试点步骤是否结构化。
- 页面对象是否缺少对应元素。
- 元素别名是否覆盖测试点描述。
- 是否需要重新导入最新 `data-testid-guidelines.md`。

## 10. 结论

本问题不是单纯的“用例中心列表为空”。

真实链路是：

```text
审核通过成功
-> 生成接口处理 approved 测试点
-> intent-02 编译覆盖失败
-> 部分情况下 DB 连接异常把业务 422 污染成 500
-> 用户看到生成失败或用例中心不符合预期
```

正确治理方向：

- 保留严格 intent 覆盖校验。
- 批量生成按测试点隔离，允许部分成功。
- 业务失败稳定返回可读 422。
- DB 断连做一次安全重试和会话失效处理。
- 前端展示成功与失败明细。
- 后续补齐 `source_asset_id + intent_id` Upsert，彻底解决重复生成和列表混乱。

## 11. 2026-05-18 修复执行记录

本次已按上述方案完成第一轮代码修复。

已落地内容：

- 批量生成从“按 20 条候选成组生成”调整为“按单个 intent 隔离生成”。
- 单个 intent 生成失败后，记录到 `summary.skipped`，不再阻断后续 intent。
- skipped 明细增加 `intent_id`，便于前端和测试人员定位失败测试点。
- 当全部 intent 都失败时，接口仍返回 `422`，并保留真实业务失败原因。
- 返回 `422` 前对当前 DB Session 做安全 rollback；rollback 失败时 invalidate 连接，避免业务错误被二次污染成 `500`。
- 页面对象 DB 查询遇到 `OperationalError` 时重试一次，降低瞬时断连导致生成失败的概率。
- 测试点资产详情页生成后展示“成功数量 + 未生成数量 + 失败摘要”，避免用户误以为全部成功或完全失败。
- 新增集成测试用例，覆盖 `intent-02` 失败时 `intent-01`、`intent-03` 继续生成的部分成功场景。
- 生成前增加 `source_asset_id + intent_id` 查询，发现已有用例时复用原 `case_id`，让后续同步走更新版本而不是新增编号。
- 新增集成测试用例，覆盖同一来源测试点重复生成时复用已有 `case_id`。

本次未改变内容：

- 未把“审核通过”改成自动生成用例。
- 未关闭 `execution_compiler_intent_coverage_failed` 严格校验。
- 未修改被测系统地址。
- 未修改既有 `intent_id` 或已生成用例 ID。

验证记录：

- `python3 -m py_compile apps/web-ui-service/app/api/workbench/facade.py apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py` 通过。
- `npm run build` 通过，前端静态产物已重新生成。
- 宿主机无法执行 pytest：当前 Python 环境缺少 `pytest`。
- Docker 容器内无法执行相关 pytest：当前镜像缺少 `httpx`，`starlette.testclient` 无法加载。

运行验证补充：

- 重启 web/nginx 后，`GET /api/workbench/test-cases?project=mall&page_index=1&page_size=20&active_status=active` 可返回用例中心数据。
- 再次调用生成接口后，接口返回 `200`，成功生成部分用例，并把失败测试点放入 `summary.skipped`。
- 本次人工验证调用在修复 Upsert 前曾生成 `mall-web-login-auth-fn-ai-0003` 至 `mall-web-login-auth-fn-ai-0021`，后续重复生成应复用同来源测试点已有用例，不再继续新增编号。

## 11. 2026-05-18 补充：生成用例状态文件覆盖源测试点资产

### 11.1 问题现象

在第一轮修复后，批量生成接口已可以做到“部分成功、部分跳过”。但实测时发现一个新的高风险问题：

- 源测试点资产 ID：`mall-web-login-auth-fn-ai-0021`
- 批量生成过程中新增了同名生成用例：`mall-web-login-auth-fn-ai-0021`
- 生成链路把该用例的状态文件写入了测试点资产目录：

```text
web-ui/state/test-points/mall/mall-web-login-auth-fn-ai-0021.json
web-ui/state/test-points/mall/plans/mall-web-login-auth-fn-ai-0021.json
```

结果是：原本包含多个 intent 的源测试点资产，被生成用例 `intent-22` 的单点计划覆盖。后续再按源资产生成 `intent-01` 时，系统只能看到被覆盖后的单点资产，因此返回：

```json
{
  "code": "selected_intents_not_approved_or_missing",
  "message": "所选测试点未通过审核或不存在，无法生成"
}
```

### 11.2 根因

生成用例链路复用了测试点资产的文件命名空间。

原有写入路径：

```text
web-ui/state/test-points/{project}/{case_id}.json
web-ui/state/test-points/{project}/plans/{case_id}.json
```

这套路径同时承担了两类完全不同的数据：

- 测试点资产：测试人员审核、维护、作为生成来源的资产。
- 生成用例快照：由生成链路派生出来的 case 状态与计划。

当 `generated case_id == source asset_id` 时，后者会覆盖前者。这不是单个 intent 编译失败，而是资产存储边界设计错误。

### 11.3 冲突范围

高风险范围：

- `POST /api/workbench/test-point-assets/batch/generate-cases`
- 生成链路中的 `save_case_state`
- 生成链路中的 `save_test_point_plan`
- `web-ui/state/test-points/{project}` 下的源测试点资产 JSON
- `web-ui/state/test-points/{project}/plans` 下的源测试点计划 JSON

可能受影响的用户体验：

- 源资产详情页只剩下单个 intent。
- 已审核测试点消失或变成“未通过/不存在”。
- 用例中心能看到生成用例，但测试点资产中心读到的源资产已不可信。
- 再次生成时出现 `selected_intents_not_approved_or_missing`。

不应受影响的范围：

- 被测系统地址，例如 `http://localhost:5174/#/login`。
- 已生成 YAML 用例文件本身。
- 数据库中已成功落库的 `test_cases` 记录。
- `execution_compiler_intent_coverage_failed` 的严格校验规则。

### 11.4 修复方案

将“生成用例运行态快照”从测试点资产命名空间中移出，单独写入：

```text
web-ui/state/generated-cases/{project}/{case_id}.json
web-ui/state/generated-cases/{project}/plans/{case_id}.json
web-ui/state/generated-cases/{project}/versions/{case_id}/0001.json
```

测试点资产继续保留在：

```text
web-ui/state/test-points/{project}/{asset_id}.json
web-ui/state/test-points/{project}/plans/{asset_id}.json
```

落地动作：

- 在 `workbench_state_store` 中新增 `GENERATED_CASES_STATE_ROOT`。
- `ensure_dirs()` 创建 `web-ui/state/generated-cases`。
- `build_workbench_runtime_context()` 中，生成链路绑定的 `save_case_state` 写入 `GENERATED_CASES_STATE_ROOT`。
- `build_workbench_runtime_context()` 中，生成链路绑定的 `save_test_point_plan` 也写入 `GENERATED_CASES_STATE_ROOT`。
- 测试点资产保存链路继续显式使用 `TEST_POINTS_ROOT`，不迁移。

### 11.5 为什么这样解决

这个方案把“源资产”和“派生产物”从存储模型上隔离：

- 源测试点资产是输入，不应被生成过程覆盖。
- 生成用例状态是输出，应允许重跑、覆盖、升级，但只能影响自己的派生命名空间。
- 即使未来 case_id 与 asset_id 重名，也只会在 `generated-cases` 下更新生成快照，不会污染 `test-points`。
- 用例中心主列表查询数据库 `test_cases`，不依赖 `test-points` 中的生成快照，因此隔离不会阻断已生成用例展示。

### 11.6 历史数据恢复策略

本次代码修复只能阻止后续覆盖，不能自动还原已经被覆盖的源资产。

对已覆盖的 `mall-web-login-auth-fn-ai-0021`，建议按以下顺序恢复：

1. 优先从历史归档恢复源资产。

```text
web-ui/state/test-points/mall/legacy-selection-save-archive-20260503171346/
```

2. 如果历史归档只包含旧的拆分资产，则根据 manifest 中的合并信息重新生成聚合资产。

```text
new_asset_id = mall-web-login-auth-fn-ai-0021
new_title = 登录页身份验证测试点集
archived_asset_ids = mall-web-login-auth-fn-ai-0001 ... mall-web-login-auth-fn-ai-0020
```

3. 如果当前业务已扩展到 `intent-21`、`intent-22`，需要从最近一次预览文件或用户重新保存的测试点资产中补齐，不能凭空推断。

4. 恢复时只写回 `web-ui/state/test-points`，不要修改被测系统地址，不要覆盖已生成 YAML 用例。

### 11.7 风险点

- 如果有旧页面仍把 `web-ui/state/test-points` 当作“生成用例快照列表”，隔离后这些旧页面不应再依赖该目录展示生成用例。
- 如果某些调试工具依赖 `test-points/{case_id}.json` 反查 YAML 路径，需要改为优先读数据库或 `assets/test-cases/ai-generated/{case_id}.yaml`。
- 已被覆盖的源资产不会因本次代码修复自动恢复，需要单独执行数据恢复。
- 当前已经生成的重复用例不应在未确认引用关系前物理删除。

### 11.8 验证方法

代码验证：

```bash
python3 -m py_compile \
  apps/web-ui-service/app/services/workbench_state_store.py \
  apps/web-ui-service/app/services/workbench_generation_api/context.py \
  apps/web-ui-service/app/api/workbench/facade.py \
  apps/web-ui-service/app/services/workbench_generation_compiler/runtime/generate_pipeline.py
```

单测验证：

```bash
python3 -m pytest apps/web-ui-service/tests/unit/test_generation_runtime_bindings.py
```

接口验证：

```bash
curl 'http://127.0.0.1:8013/api/workbench/test-point-assets/mall-web-login-auth-fn-ai-0021?project=mall'
```

验收点：

- 源资产仍显示多 intent 测试点集，而不是单个 `intent-22`。
- 再次生成同名 case_id 后，`web-ui/state/test-points/mall/mall-web-login-auth-fn-ai-0021.json` 不再变化。
- 新的生成快照出现在 `web-ui/state/generated-cases/mall/`。
- 用例中心仍可通过数据库看到已生成用例。
- 被测系统地址仍保持 `http://localhost:5174/#/login`。

### 11.9 本次恢复执行记录

执行日期：2026-05-18

已执行动作：

- 新增代码隔离：生成用例运行态快照改写入 `web-ui/state/generated-cases`。
- 创建恢复备份目录：

```text
web-ui/state/test-points/mall/recovery-backup-20260518-generation-overwrite
```

- 将已存在的 `generate_chain` 生成快照复制到：

```text
web-ui/state/generated-cases/mall/
```

- 从历史归档恢复 `intent-01` 至 `intent-20`：

```text
web-ui/state/test-points/mall/legacy-selection-save-archive-20260503171346/
```

- 从已保留的生成快照补齐 `intent-21`、`intent-22`。
- 将源资产 `mall-web-login-auth-fn-ai-0021` 恢复为：

```text
source_type = selection_save
title = 登录页身份验证测试点集
page = login
point_count = 22
intent_count = 22
page_url = http://localhost:5174/#/login
```

本地文件验证结果：

```text
web-ui/state/test-points/mall/mall-web-login-auth-fn-ai-0021.json
source_type = selection_save
title = 登录页身份验证测试点集
point_count = 22
intent_count = 22
```

接口验证说明：

- 未携带有效登录态直接访问资产详情接口会返回 `401`。
- 登录后应通过页面或带有效 token 的接口确认源资产详情展示 22 个测试点。
