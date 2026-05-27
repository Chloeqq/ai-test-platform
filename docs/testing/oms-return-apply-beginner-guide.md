# OMS 退货申请处理页面 - 新手执行指南

> 页面 URL: [http://localhost:5173/#/oms/returnApply](http://localhost:5173/#/oms/returnApply)  
> 工作台 URL: [http://127.0.0.1:8013/workbench](http://127.0.0.1:8013/workbench)

这份文档是给第一次接触平台的小白准备的。你只要按步骤做，就能在当前平台里完成 `returnApply` 页面的基础验收，并知道哪些用例是“现在就能跑”，哪些是“当前框架还差一步”。

## 先看结论

- 这个页面当前可以稳定验证 `服务单号 = 3` 的精确查询、无结果查询，以及部分安全烟雾测试。
- `处理状态` 已经可以自动筛选并验收；`处理时间` 现在也能通过浏览器级 state 注入自动验收，但公开日期控件本身的提交序列化仍有已知偏差；`申请时间`、`操作人员` 仍需要继续收口。
- 页面本身没有分页器，所以不要用“第 2 页”“共 21 条都展示在表格里”这种预期来验收，当前只能看接口返回和表格首屏数据。

## 你需要准备什么

1. 前端页面已启动，能打开 [http://localhost:5173/#/oms/returnApply](http://localhost:5173/#/oms/returnApply)。
2. 测试平台已启动，能打开 [http://127.0.0.1:8013/workbench](http://127.0.0.1:8013/workbench)。
3. 你知道工作台账号和退货申请页的登录账号。
4. 如果你遇到 `请先选择用例`，说明你只是把 YAML 放进编辑器了，但还没有选中一个实际的用例行。

## 最短操作路径

### 1. 打开工作台

在浏览器打开：

```text
http://127.0.0.1:8013/workbench
```

### 2. 选择项目

在页面顶部选择当前项目。通常保持默认即可。

### 3. 选择一个现成用例

在“用例列表”里找到下面这个已经能直接跑的用例：

```text
SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3
```

如果没有显示，先点一次“刷新用例”。

### 4. 确认 YAML 已载入

选中用例后，右侧 `YAML 编辑` 区会出现内容，底部“当前用例”也会变成对应的 ID。

如果这里还是显示“未选择”，不要直接点运行，先重新点一次用例行。

### 5. 点击运行

点右上角的 `Run Test`。

### 6. 看实时日志

左下角 `Realtime Logs` 应该先出现类似下面的内容：

```text
[run] id=...
[run] case=...
[run] command=python3 -m pytest ...
```

如果这里直接报错，优先看是不是：

- `请先选择用例`
- `BASE_URL is unreachable`
- `Connection refused`

### 7. 看结果

运行结束后，状态会落到：

- `passed`：通过
- `failed`：断言失败或业务失败
- `broken`：框架、数据或环境问题

### 8. 下载日志和看失败分析

如果失败了，继续看：

- `Failure Analysis`
- `Download Log`
- 运行产物目录

`Allure CLI not found` 不是这条主链的第一优先级问题。它影响的是报告生成，不应阻断你判断这次测试有没有真正跑起来。

## 小白版操作清单

你可以直接照着这 8 步做：

1. 打开前端页面和工作台。
2. 登录工作台。
3. 在用例列表里选中 `SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3`。
4. 确认右侧 YAML 已载入。
5. 点 `Run Test`。
6. 观察 `Realtime Logs` 是否持续输出。
7. 看最终状态是不是 `passed`。
8. 如果失败，去 `Failure Analysis` 里看原因。

## 15 条用例怎么理解

下面这张表不是“理论上的理想值”，而是按当前页面、当前框架、当前数据三者合在一起的真实可执行性来分的。

| 用例 ID | 用例名称 | 当前结论 | 说明 |
|---|---|---|---|
| TC_RETURN_001 | 服务单号精确搜索 | 可自动执行 | `id=3` 是当前最稳定的正向样例。 |
| TC_RETURN_002 | 服务单号模糊搜索 | 不支持当前后端行为 | 当前查询是按 `id` 精确查，不是模糊搜索。 |
| TC_RETURN_003 | 服务单号搜索 - 无结果 | 可自动执行 | `999` 会返回空结果，适合验证空态。 |
| TC_RETURN_004 | 按处理状态筛选 - 已完成 | 可自动 | 已有浏览器 smoke 和可执行 YAML 样板。 |
| TC_RETURN_005 | 按处理状态筛选 - 退货中 | 需补交互定位 | 数据可对上，但需要更完整的下拉选择步骤。 |
| TC_RETURN_006 | 按处理状态筛选 - 已拒绝 | 需补交互定位 | 数据可对上，但需要更完整的下拉选择步骤。 |
| TC_RETURN_007 | 按处理状态筛选 - 待处理 | 数据不匹配 | 当前数据里 `status=0` 不止 1 条。 |
| TC_RETURN_008 | 按申请时间范围筛选 | 需人工/接口校验 | 页面有日期控件，但当前 UI 没有分页器，也没有直接展示总量。 |
| TC_RETURN_009 | 按处理时间范围筛选 | 可自动（浏览器 state 注入） | 页面公开日期控件的序列化仍不稳定，但浏览器级验收可稳定命中 1 条结果。 |
| TC_RETURN_010 | 按操作人员筛选 | 数据不匹配 | 当前数据里 `handleMan` 基本为空。 |
| TC_RETURN_011 | 多条件组合筛选 | 需补交互定位 | 逻辑上可测，但需要状态选择器可被自动化稳定操作。 |
| TC_RETURN_012 | 重置筛选条件 | 需补交互定位 | 页面有重置按钮，但目前自动化只覆盖最基础输入。 |
| TC_RETURN_013 | 查询搜索 - 空条件 | 需接口辅助判断 | 页面不会把 21 条全部展开在屏幕上，首屏只有分页查询结果。 |
| TC_RETURN_014 | 服务单号搜索 - 特殊字符 | 可自动执行 | 适合做安全烟雾测试，重点看页面是否报错。 |
| TC_RETURN_015 | 服务单号搜索 - SQL 注入 | 可自动执行 | 同样是烟雾测试，重点看是否有异常或明显注入回显。 |

## 这页当前真正能直接跑的最小闭环

如果你只想先让平台“跑起来”，建议先做这 5 个：

1. `TC_RETURN_001`
2. `TC_RETURN_003`
3. `TC_RETURN_004`
4. `TC_RETURN_014`
5. `TC_RETURN_015`

这 5 个用例里，前 4 个都不依赖复杂的日期选择器，最适合先把执行链路跑通；`TC_RETURN_004` 则是状态筛选的首个可自动样板。

## 适合先人工看一遍的用例

下面这些更适合先人工检查一次页面和数据，再决定是否补自动化：

- `TC_RETURN_004`
- `TC_RETURN_005`
- `TC_RETURN_006`
- `TC_RETURN_008`
- `TC_RETURN_009`
- `TC_RETURN_011`
- `TC_RETURN_012`

## 当前页面的真实限制

- 页面没有分页器。
- 自动化动作目前只有 `click`、`fill`、`wait_for`、`assert_visible`、`login`、`assert_url`、`goto`。
- 日期控件和下拉控件没有专门的 action 封装。
- `returnApply` 页面目前能说明“页面可以查”，并且 `处理状态`、`处理时间` 这两项已经可以自动验收，但还不能说明“所有筛选都已经平台化自动跑通”。

## 你应该怎么判断结果是对的

### 通过

- 页面能正常打开。
- 点击 `Run Test` 后，`Realtime Logs` 持续输出。
- 最终状态是 `passed`。
- 对于 `TC_RETURN_001`，表格只显示服务单号 `3` 的记录。
- 对于 `TC_RETURN_003`，表格为空并出现空态提示。

### 失败

- `BASE_URL is unreachable`
- `Connection refused`
- `请先选择用例`
- `assert_visible` 失败
- 页面报白屏或接口错误

### 需要人工复核

- 安全类用例：`TC_RETURN_014`、`TC_RETURN_015`
- 日期类筛选
- 结果数量不能直接在 UI 看到的用例

## 已知可用的用例资产

当前最稳的现成资产是：

- [`/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml)
- [`/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/TC_RETURN_004.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/TC_RETURN_004.yaml)

它可以作为你后续复制新用例的模板。
