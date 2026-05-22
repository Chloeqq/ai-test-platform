# DSL 架构与用例执行卡点复盘

文档日期：2026-05-18

记录状态：探讨留档，不包含代码修复

适用范围：测试点资产生成用例、YAML DSL、用例中心落库、Runner 执行链路、页面对象定位链路

被测系统地址铁律：

```text
http://localhost:5174/#/login
```

任何 DSL 架构优化都不得把被测系统原始地址改写成平台自身地址、Docker 内部地址或其他代理地址。

## 1. 当前 DSL 总结构

当前系统使用的是一套 YAML 形式的业务脚本 DSL。

整体链路：

```text
测试点资产 / intent
  -> 生成 YAML DSL
  -> 同步到 test_cases / test_case_steps
  -> Runner YamlExecutor
  -> action_registry
  -> locator_resolver
  -> Playwright
```

当前典型 DSL：

```yaml
version: v1
id: mall-web-login-auth-fn-ai-0001
project: mall
module: login
title: 首次登录成功
priority: P0
tags:
  - ai-generated
owner: qa-team
status: automated
description: 首次登录成功 — 验证输入正确账号密码后可以成功登录并跳转至工作台首页
requirement:
  intent_id: intent-01
  title: 首次登录成功
  type: functional
  precondition: 用户未登录，处于登录页面
data: {}
execution:
  runner: playwright
  page: login
  page_url: http://localhost:5174/#/login
  variables: {}
  steps:
    - action: goto
      value: http://localhost:5174/#/login
      expected_result: 登录页面加载完成，显示账号输入框、密码输入框、登录按钮
    - action: input
      target: element:username_input
      locator_type: css
      locator_value: "input[name='username'], #username, #username-input"
      target_name: 用户名输入框
      value: admin
      expected_result: 用户名输入框内容显示为 admin
    - action: input
      target: element:password_input
      locator_type: css
      locator_value: "input[type='password'], input[name='password'], #password"
      target_name: 密码输入框
      value: macro123
      expected_result: 密码输入框内容以掩码形式显示
    - action: click
      target: element:login_button
      locator_type: role
      locator_value: 登录
      target_name: 登录按钮
      expected_result: 页面跳转至平台工作台首页，顶部展示当前登录用户名admin，左侧加载对应权限导航菜单
  selected_intent_ids:
    - intent-01
expected_result: 页面跳转至平台工作台首页，顶部展示当前登录用户名admin，左侧加载对应权限导航菜单
```

## 2. 当前 DSL 的特点

当前 DSL 能快速生成可运行脚本，原因是它把执行所需信息都放进了 YAML。

一个 step 同时包含：

- 业务动作：`action`
- 页面目标：`target`
- 定位方式：`locator_type`
- 定位值：`locator_value`
- 输入数据：`value`
- 人类可读名称：`target_name`
- 预期描述：`expected_result`

这种结构短期很直接，但它混合了三层语义：

```text
测试意图层：intent、title、expected_result
页面对象层：target、target_name、locator_type、locator_value
执行动作层：goto、input、click、assert
```

混合三层信息是当前系统容易产生执行卡点的核心原因。

## 3. 当前执行卡点

### 3.1 expected_result 只是文案，不是断言

当前 DSL 中 `expected_result` 主要作为说明文字存在。

Runner 会把它附加到 Allure step，但不会自动转成可执行断言。

风险：

- 点击成功不代表业务成功。
- 登录成功、错误提示、密码显隐、跳转结果都可能没有被真正验证。
- 报告会出现“步骤执行完了，但测试意图没有被证明”的空洞感。

典型问题：

```yaml
- action: click
  target: element:login_button
  expected_result: 页面跳转至平台工作台首页，顶部展示当前登录用户名admin
```

这只是文案，缺少：

```yaml
assert_url
assert_visible
assert_text
```

### 3.2 locator 被固化在 YAML 里

当前 step 直接包含：

```yaml
locator_type: css
locator_value: "input[name='username'], #username, #username-input"
```

风险：

- 页面对象治理后，YAML 仍可能使用旧 locator。
- 被测系统已经有真实 `data-testid`，但生成脚本仍可能继续使用 CSS、role、placeholder。
- 后续页面对象更新不能自动改善历史 DSL 的执行稳定性。

更理想的方式是 DSL 只引用：

```yaml
element: username_input
```

执行前再从页面对象库解析当前最稳定 locator。

### 3.3 precondition 是自然语言，Runner 无法执行

当前 precondition 例如：

```yaml
precondition: 用户未登录，处于登录页面
```

这对人可读，但 Runner 不知道如何执行。

复杂场景会因此失真：

- 已登录用户点击退出。
- 勾选记住密码后再次打开登录页。
- 已输入账号密码后模拟弱网。
- 登录按钮重复点击。

这些场景都需要结构化前置动作，而不是一句自然语言。

### 3.4 value 缺少数据类型

当前 `value` 是普通字符串。

因此会出现自然语言进入执行器：

```yaml
value: 最小长度的合法账号
value: 比最大长度多1位的账号
value: 包含非法字符的密码
value: 空格
value: 框
```

Runner 会照填这些文字，但这些不是稳定测试数据。

风险：

- 边界值不可复现。
- 空输入场景反而输入了文字。
- 非法字符场景没有明确非法字符集。
- 执行失败时很难判断是业务失败还是测试数据错误。

### 3.5 source identity 不完整

当前 YAML 中普遍缺少：

```yaml
requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
```

风险：

- 只靠 `intent_id` 无法全局唯一。
- 不同资产都可能有 `intent-01`。
- 生成链路难以按 `source_asset_id + intent_id` 做稳定幂等。
- 容易产生重复用例，例如 `0001` 与 `0003` 都覆盖 `intent-01`。

### 3.6 action 能力不足以表达复杂测试

当前 Runner 支持的动作集中在：

```text
goto
input / fill / type
click
wait_for
assert_visible
assert_url
assert_count
assert_metric
login
```

但实际测试场景需要更多能力：

- `assert_text`
- `assert_input_value`
- `assert_attribute`
- `assert_toast`
- `set_network`
- `double_click`
- `reload`
- `clear_storage`
- `remember_password`
- `login_as`
- `logout`

如果 DSL 没有这些语义，只能把复杂场景压扁成 click/input，导致执行成功率低。

## 4. DSL 架构优化方向

建议从“可运行脚本 DSL”演进为“稳定自动化测试 DSL”。

核心方向：分层。

建议分成：

```text
identity：身份与追溯
requirement：测试意图
scenario：前置条件与上下文
data：测试数据
steps：业务动作
assertions：可执行断言
evidence：证据与报告
execution：运行器配置
```

## 5. 建议目标 DSL 结构

建议演进方向：

```yaml
version: v2
id: mall-web-login-auth-fn-ai-0001
project: mall
module: login
title: 首次登录成功
priority: P0
tags:
  - ai-generated

requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
  intent_id: intent-01
  title: 首次登录成功
  type: functional
  precondition: 用户未登录，处于登录页面

scenario:
  page: login
  page_url: http://localhost:5174/#/login
  preconditions:
    - type: unauthenticated
    - type: open_page
      page: login

data:
  username:
    type: credential
    value: admin
  password:
    type: secret
    value: macro123

steps:
  - id: input_username
    action: input
    element: username_input
    value: ${username}

  - id: input_password
    action: input
    element: password_input
    value: ${password}

  - id: submit_login
    action: click
    element: login_button

assertions:
  - id: assert_dashboard_url
    type: url_contains
    value: /dashboard

  - id: assert_current_user
    type: text_visible
    element: current_user
    value: admin

execution:
  runner: playwright
  selected_intent_ids:
    - intent-01
```

这个结构的关键变化：

- `steps` 只描述“做什么”，不直接固化 locator。
- `element` 只引用页面对象编码。
- `data` 明确区分账号、密码、空值、边界值、非法字符。
- `scenario.preconditions` 可被 Runner 执行。
- `assertions` 是真正可执行的验证点。
- `requirement.source_asset_id + requirement.intent_id` 成为去重和追溯硬字段。

## 6. 分层职责建议

### 6.1 requirement 层

职责：说明测试来自哪里、覆盖哪个测试点。

必须字段：

```yaml
requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
  intent_id: intent-01
  title: 首次登录成功
  type: functional
```

收益：

- 支持幂等生成。
- 支持重复检测。
- 支持报告追溯。
- 支持用例中心按来源资产聚合。

### 6.2 scenario 层

职责：表达执行前置和场景上下文。

示例：

```yaml
scenario:
  page: login
  page_url: http://localhost:5174/#/login
  preconditions:
    - type: unauthenticated
    - type: clear_storage
    - type: open_page
      page: login
```

复杂场景示例：

```yaml
scenario:
  preconditions:
    - type: login_as
      username: admin
      password: macro123
    - type: open_user_menu
```

收益：

- 退出登录、记住密码、弱网、重复点击等场景不再靠自然语言。
- Runner 可以统一处理场景准备。

### 6.3 data 层

职责：管理测试数据，禁止自然语言占位进入执行。

示例：

```yaml
data:
  empty_username:
    type: empty
    value: ""
  blank_username:
    type: whitespace
    value: " "
  invalid_password:
    type: invalid_chars
    value: "abc<>!@#"
  max_length_username:
    type: boundary
    rule: username.max_length
    value: "aaaaaaaaaaaaaaaa"
```

收益：

- 空值、空格、非法字符、边界值都可复现。
- 批量执行前可做数据质量门禁。

### 6.4 steps 层

职责：描述业务动作。

建议只保留：

```yaml
action
element
value
```

不建议长期保留：

```yaml
locator_type
locator_value
```

示例：

```yaml
steps:
  - action: input
    element: username_input
    value: ${username}
```

执行时再动态解析：

```text
element -> Page Object Store -> best locator -> Playwright locator
```

收益：

- 页面对象治理可以持续提升历史用例稳定性。
- DSL 不再被旧 locator 污染。

### 6.5 assertions 层

职责：把预期结果变成可执行校验。

示例：

```yaml
assertions:
  - type: toast_visible
    value: 请输入账号

  - type: input_type
    element: password_input
    value: text

  - type: url_contains
    value: /dashboard

  - type: text_visible
    value: admin
```

收益：

- Allure 报告有真实业务验证。
- 执行成功才代表测试意图被验证。

### 6.6 evidence 层

职责：定义失败和成功时要采集的证据。

示例：

```yaml
evidence:
  on_failure:
    - screenshot
    - html
    - console
    - network
  on_success:
    - screenshot
```

收益：

- 报告专业度提升。
- 失败原因更容易定位。

## 7. 对当前执行卡点的改善效果

### 7.1 重复生成

通过：

```yaml
requirement.source_asset_id
requirement.intent_id
```

可以按：

```text
project + source_asset_id + intent_id
```

做唯一性约束或幂等复用。

### 7.2 定位不稳定

通过：

```yaml
element: username_input
```

而不是：

```yaml
locator_type: css
locator_value: ...
```

可以让 Runner 执行前从页面对象库拿最新 locator。

### 7.3 自然语言数据

通过 data 层类型化，可以在生成阶段拦截：

```text
最小长度的合法账号
包含非法字符的密码
框
```

这些不可执行值。

### 7.4 复杂场景缺前置

通过 scenario.preconditions，可以表达：

```yaml
- type: login_as
- type: set_network
- type: clear_storage
- type: reopen_page
```

Runner 可以明确执行，而不是猜测自然语言。

### 7.5 报告空洞

通过 assertions 层，报告中每个业务预期都有对应验证步骤。

这能避免“脚本跑完但没有验证”的伪成功。

## 8. 短期演进建议

### 8.1 v1.1：不破坏现有 YAML，补关键字段

短期先不推翻 v1。

优先补：

```yaml
requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
  intent_id: intent-01
execution:
  selected_intent_ids:
    - intent-01
```

目标：

- 解决重复生成。
- 提升追溯能力。
- 降低实现风险。

### 8.2 v1.2：增加 assertions

保留 `expected_result`，但新增结构化断言：

```yaml
assertions:
  - type: toast_visible
    value: 请输入账号
```

Runner 执行顺序：

```text
steps -> assertions
```

目标：

- 先解决“执行了但没验证”的问题。
- 让报告更可信。

### 8.3 v1.3：增加 data 类型

新增：

```yaml
data:
  username:
    type: credential
    value: admin
```

并增加生成前校验：

- 禁止自然语言占位。
- 边界值必须给出真实值。
- 空输入必须明确是 `""` 或跳过 input step。

### 8.4 v1.4：element 动态解析 locator

允许 step 只写：

```yaml
element: username_input
```

执行前从页面对象库解析：

```text
element_code -> data-testid / role / placeholder / css
```

目标：

- 让页面对象治理成果真正影响执行稳定性。
- 减少 YAML 固化旧 locator。

### 8.5 v2：正式分层 DSL

长期目标是完整切换到：

```text
requirement + scenario + data + steps + assertions + evidence + execution
```

v2 应保留 v1 兼容转换器。

## 9. 风险与注意事项

### 9.1 不要一次性推翻 v1

当前系统已有大量 v1 YAML、数据库字段和 Runner 行为。

建议：

- 先做 v1.1 / v1.2 增量扩展。
- Runner 同时兼容 v1 和 v2。
- 后端生成器逐步输出更结构化 DSL。

### 9.2 locator 不应完全从 YAML 消失得太快

短期可以保留 locator 作为编译产物或 fallback。

建议策略：

```text
优先 element 动态解析
其次使用 YAML locator
最后报明确绑定失败
```

### 9.3 弱网等能力要和 Runner 能力匹配

DSL 可以表达：

```yaml
- type: set_network
```

但 Runner 必须真的支持网络模拟。

否则应在生成阶段标记：

```text
requires_runner_capability: network_emulation
```

并阻止进入自动化执行。

### 9.4 data-testid 输入容器需要特殊处理

被测系统文档说明：

```text
page.getByTestId('login-username-input').locator('input').fill('admin')
```

因此 DSL 与 Runner 都要支持子定位。

不能简单认为：

```text
data-testid = input 本身
```

## 10. 推荐结论

当前 DSL 是“可运行脚本 DSL”，还不是“稳定自动化测试 DSL”。

它的问题不是字段太少，而是层次混在一起：

```text
测试意图、测试数据、页面对象定位、执行动作、业务断言
```

都压在 `execution.steps` 中。

推荐演进路线：

```text
v1.1 补 source_asset_id / intent_id，解决重复生成
v1.2 补 assertions，解决伪成功
v1.3 补 typed data，解决自然语言测试数据
v1.4 支持 element 动态解析 locator，解决定位老化
v2 完整分层 DSL，支撑复杂业务场景
```

优先级最高的是：

1. `source_asset_id + intent_id`
2. 结构化断言
3. 类型化测试数据
4. 页面对象动态绑定
5. 结构化前置条件

这几个点落地后，当前用例执行卡点会从“脚本质量不可控”转向“明确可诊断、可治理、可批量执行”。
