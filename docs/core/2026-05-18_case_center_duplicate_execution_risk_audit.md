# 用例中心重复、执行成功率与新增代码风险审查报告

文档日期：2026-05-18

记录状态：审查留档，不包含代码修复

适用范围：`mall` 项目、`login` 页面、测试点资产生成用例链路、用例中心列表链路、Runner 执行链路、近期新增的生成状态隔离与幂等链路

被测系统地址铁律：

```text
http://localhost:5174/#/login
```

任何修复建议都不得把被测系统地址改成平台自身地址、Docker 内部地址或其他运行时代理地址。

## 1. 审查日期与范围

审查日期：2026-05-18

审查对象：

- 测试点资产：`mall-web-login-auth-fn-ai-0021`
- 页面：`login`
- 生成用例文件：`assets/test-cases/ai-generated/mall-web-login-auth-fn-ai-*.yaml`
- 用例中心数据库：`test_cases`、`test_case_steps`、`test_case_executions`
- 运行态状态目录：`web-ui/state/test-points`、`web-ui/state/generated-cases`
- Runner 关键链路：`goto`、`input/fill`、`click`、locator 解析

本次只聚焦“测试点资产生成用例 -> 用例中心 -> Runner 执行 -> 新增状态隔离/生成链路代码”。

本次不覆盖全量 dirty worktree 中的 UI、Allure、页面对象导入、前端样式等其他变更。

## 2. 当前事实快照

### 2.1 YAML 生成用例数量

当前 `mall` 登录生成用例 YAML 共 20 条：

```text
mall-web-login-auth-fn-ai-0001.yaml
mall-web-login-auth-fn-ai-0003.yaml
mall-web-login-auth-fn-ai-0004.yaml
...
mall-web-login-auth-fn-ai-0021.yaml
```

缺少：

```text
mall-web-login-auth-fn-ai-0002.yaml
```

### 2.2 源测试点资产状态

源测试点资产已恢复为聚合资产：

```text
asset_id = mall-web-login-auth-fn-ai-0021
source_type = selection_save
title = 登录页身份验证测试点集
page = login
point_count = 22
intent_count = 22
first_intent = intent-01
last_intent = intent-22
```

源资产中的 22 个测试点均已处于可用于生成的审核状态。

### 2.3 生成覆盖情况

当前实际生成 YAML 只覆盖 19 个唯一 intent。

已知缺口：

```text
intent-02
intent-09
intent-13
```

历史生成失败原因包括：

- `intent-02`：`execution_compiler_intent_coverage_failed`
- `intent-09`：`target_binding_failed`，input 被错误识别成 click target
- `intent-13`：input step 缺少明确 target

### 2.4 数据库用例中心状态

数据库中 `mall` 项目、`mall-web-login-auth-fn-ai-*` 用例共 20 条。

当前状态：

```text
status = inactive，数量 20
```

执行结果：

```text
mall-web-login-auth-fn-ai-0001 = failed
其余 19 条 = unknown
```

说明：

- 当前只有 `0001` 有落库执行记录。
- 其他用例尚未形成真实执行结果，不能把 `unknown` 理解为通过。
- 用例中心前端展示层把非 `deprecated` 都显示为“活跃”，但数据库原始状态仍是 `inactive`，这里存在语义不一致。

### 2.5 运行态状态隔离现状

当前已经存在独立生成快照目录：

```text
web-ui/state/generated-cases/mall
```

源测试点资产仍在：

```text
web-ui/state/test-points/mall
```

该隔离可以防止后续生成用例快照再次覆盖源测试点资产。

但历史已生成快照、源资产恢复记录、重复 YAML 仍需要后续清理与治理。

## 3. 重复用例判断

### 3.1 强重复用例

以下两条属于强重复：

```text
mall-web-login-auth-fn-ai-0001
mall-web-login-auth-fn-ai-0003
```

重复依据：

- 标题相同：`首次登录成功`
- intent 相同：`intent-01`
- 页面相同：`login`
- 输入账号相同：`admin`
- 输入密码相同：`macro123`
- 步骤签名完全一致：

```text
goto http://localhost:5174/#/login
input username_input = admin
input password_input = macro123
click login_button
```

结论：

这两条不应同时作为有效用例长期存在。建议保留一条，另一条标记为重复或废弃，而不是物理删除后丢失审计。

### 3.2 步骤重叠但业务意图不同

`mall-web-login-auth-fn-ai-0012` 与登录成功用例步骤高度重叠：

```text
input username_input = admin
input password_input = macro123
click login_button
```

但业务意图是：

```text
勾选记住密码登录后再次打开登录页
```

当前脚本缺少关键动作：

- 未勾选 `remember_password_checkbox`
- 未关闭或重新打开登录页
- 未断言账号密码自动填充

结论：

这不是“完全重复”，而是“步骤不足导致意图未覆盖”。它不应被简单删除，应补齐场景步骤。

### 3.3 只有点击动作的高风险重叠

以下两条步骤都只包含打开登录页后点击登录按钮：

```text
mall-web-login-auth-fn-ai-0020 登录按钮重复点击
mall-web-login-auth-fn-ai-0021 登录时模拟弱网超时
```

问题：

- `0020` 没有输入正确账号密码，也没有重复点击动作。
- `0021` 没有输入正确账号密码，也没有弱网模拟能力。

结论：

这两条不是重复业务意图，但当前脚本步骤无法覆盖对应意图，执行成功概率极低。

### 3.4 重复根因

主要根因：

- 生成 YAML 中普遍缺少 `requirement.source_asset_id`。
- 幂等查重依赖 `source_asset_id + intent_id`，但历史生成脚本无法稳定提供 `source_asset_id`。
- 生成时曾发生状态命名空间覆盖，导致源资产与派生用例快照边界混乱。
- 重复生成前缺少“同源测试点已存在用例”的强校验和用户提示。

## 4. 执行成功概率评估

本节按“可执行条件成熟度”评估，不给虚假的精确百分比。没有实际执行的用例不能判定为通过。

### 4.1 高/中：登录成功类

用例：

```text
mall-web-login-auth-fn-ai-0001
mall-web-login-auth-fn-ai-0003
```

成功概率判断：中等偏高。

有利条件：

- 账号密码已修正为 `admin / macro123`。
- 被测系统地址可访问：`http://localhost:5174/#/login`。
- 页面对象中存在真实登录元素。
- 历史运行日志中曾出现通过记录。

风险卡点：

- 两条用例重复。
- 当前仍使用 CSS、placeholder、role 组合定位，未优先使用真实 `data-testid`。
- 历史失败包含 `Locator.fill Timeout`、`Locator.click Timeout`、`Page.goto Timeout`、浏览器崩溃等波动。
- 登录成功后缺少稳定的最终断言步骤，例如工作台、用户名、权限菜单的显式断言。

建议：

- 保留一条登录成功用例，另一条标记重复。
- 将登录页元素定位迁移到真实 `data-testid`：`login-username-input`、`login-password-input`、`login-submit-btn`。
- 补充登录后断言：URL、用户名 `admin`、左侧菜单或工作台标识。

### 4.2 中低：常规异常账号/密码类

用例：

```text
mall-web-login-auth-fn-ai-0008 输入系统不存在的账号登录
mall-web-login-auth-fn-ai-0009 输入正确账号、错误密码登录
```

成功概率判断：中低。

主要卡点：

- 依赖被测系统真实错误提示文本是否与期望一致。
- 错误密码或不存在账号可能触发后端限流、锁定、错误次数累计等状态副作用。
- 缺少明确断言动作，目前主要依赖步骤 expected_result 文案。

建议：

- 建立固定测试账号数据集。
- 执行前清理错误次数、锁定状态等副作用。
- 增加 toast/message 文本断言。

### 4.3 低：空输入、边界值、非法字符类

用例：

```text
mall-web-login-auth-fn-ai-0004 账号为空点击登录
mall-web-login-auth-fn-ai-0005 密码为空点击登录
mall-web-login-auth-fn-ai-0006 账号和密码都为空点击登录
mall-web-login-auth-fn-ai-0007 账号仅输入空格点击登录
mall-web-login-auth-fn-ai-0014 账号输入框最小长度边界值测试（min）
mall-web-login-auth-fn-ai-0015 账号输入框最小长度边界值测试（min - 1）
mall-web-login-auth-fn-ai-0016 账号输入框最大长度边界值测试（max）
mall-web-login-auth-fn-ai-0017 账号输入框最大长度边界值测试（max + 1）
mall-web-login-auth-fn-ai-0018 账号输入非法字符
mall-web-login-auth-fn-ai-0019 密码输入非法字符
```

成功概率判断：低。

主要卡点：

- 当前输入值存在自然语言占位，例如：

```text
框
空格
最小长度的合法账号
比最小长度少1位的账号
最大长度的合法账号
包含非法字符的账号
包含非法字符的密码
```

- 这些值不是明确、可执行、可复现的测试数据。
- 边界值缺少规则来源，例如最小长度和最大长度到底是多少。
- `0019` 标题是密码非法字符，但最后点击的是 `password_toggle`，不是登录按钮，动作与意图不一致。

建议：

- 将自然语言输入值替换为真实数据，例如空字符串、`" "`、明确长度的字符串、明确非法字符集。
- 从需求或前端校验规则中抽取 min/max 长度。
- `0019` 应点击登录按钮并断言密码非法提示，而不是点击密码显隐开关。

### 4.4 极低：复杂交互和环境模拟类

用例：

```text
mall-web-login-auth-fn-ai-0010 点击眼睛图标切换密码为明文
mall-web-login-auth-fn-ai-0011 再次点击眼睛图标切换密码为密文
mall-web-login-auth-fn-ai-0012 勾选记住密码登录后再次打开登录页
mall-web-login-auth-fn-ai-0013 登录用户点击退出登录
mall-web-login-auth-fn-ai-0020 登录按钮重复点击
mall-web-login-auth-fn-ai-0021 登录时模拟弱网超时
```

成功概率判断：极低到低。

主要卡点：

- `0011` 缺少先输入密码或先切换到明文的前置状态。
- `0012` 缺少勾选记住密码、登录、重新打开页面、断言自动填充。
- `0013` 从登录页直接点击退出，缺少先登录进入工作台的前置流程。
- `0020` 缺少账号密码输入，且没有重复点击。
- `0021` 缺少弱网模拟能力，且没有账号密码输入。

建议：

- 复杂场景必须支持前置步骤模板或复用登录成功流程。
- 弱网场景需要 Runner 支持网络条件模拟，不能只靠普通 click。
- 退出登录场景应先登录成功并定位到真实退出入口。

## 5. 新引入代码风险

### 5.1 生成快照隔离风险

新增 `generated-cases` 状态隔离可以防止再次覆盖源测试点资产，这是正确方向。

剩余风险：

- 历史生成快照仍与源资产恢复记录并存，需要明确治理策略。
- 旧代码或调试工具如果仍从 `test-points/{case_id}.json` 读取生成快照，会读不到新位置。
- 恢复后的源资产与已生成 YAML 之间仍有重复和缺口。

建议：

- 明确 `test-points` 只存源测试点资产。
- 明确 `generated-cases` 只存生成用例派生快照。
- 用例中心以数据库 `test_cases` 为主，不再依赖测试点资产目录反查生成用例。

### 5.2 幂等去重链路不完整

当前用例脚本中普遍缺少：

```yaml
requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
```

风险：

- `_existing_case_id_for_source_intent()` 很难稳定识别“同一个源测试点已经生成过用例”。
- 同一 `intent_id` 可能在不同资产中重复出现，仅靠裸 `intent-01` 不足以判重。
- 后续再次生成仍可能出现 `0001`、`0003` 这种重复。

建议：

- 生成 YAML 时强制写入 `requirement.source_asset_id`。
- 数据库层建议沉淀显式字段或 metadata：`source_asset_id`、`source_intent_id`。
- 生成前按 `project + source_asset_id + source_intent_id` 做唯一性检查。

### 5.3 用例状态语义不一致

`upsert_test_case_from_workbench()` 当前固定写入：

```python
status = "inactive"
```

但用例中心前端将非 `deprecated` 显示为“活跃”。

风险：

- 数据库原始状态与用户看到的状态不一致。
- 批量执行、筛选、统计如果直接使用 `status`，可能把这些生成用例排除在外。
- 用户会误解“审核通过后为什么用例中心没有对应列表”或“为什么列表显示活跃但 DB 是 inactive”。

建议：

- 区分资产生命周期状态和展示状态。
- 对自动生成且可执行的用例，状态建议落为 `active` 或明确引入 `review_status/generated_status`。
- 前端展示应同时保留 `raw_status` 和业务态说明。

### 5.4 定位策略未对齐真实 data-testid

被测系统真实已添加的登录页 `data-testid` 包括：

```text
login-username-input
login-password-input
login-submit-btn
login-form
login-page
```

当前生成脚本仍主要使用：

```text
placeholder / css / role
```

风险：

- placeholder、role、CSS 后续更容易受 UI 文案和组件结构影响。
- `data-testid` 输入类元素可能是容器，实际 input 需要链式定位：`getByTestId(...).locator("input")`。
- Runner 当前 `locator_type=data-testid` 只返回 `get_by_test_id(locator_value)`，还缺少容器内 input 的链式策略。

建议：

- 页面对象中保留 `data-testid` 为高可信主定位。
- 对输入型 `data-testid` 支持 `locator_value=login-username-input >> input` 或在 Runner 中支持子定位。
- 生成器优先使用真实 `data-testid`，无法使用时才回退 placeholder/role/css。

### 5.5 步骤与断言不足

当前多个用例只有动作，没有显式断言动作。

风险：

- Runner 可能点击成功就结束，但没有验证业务结果。
- 报告会显示步骤执行完成，但测试意图并未真正被验证。
- Allure 报告可能继续出现“信息空洞”的问题。

建议：

- 生成脚本必须补充最终断言步骤。
- expected_result 不能只作为文案，应转化为可执行断言。
- 对 toast、URL、用户名、菜单、密码框 type 属性等建立断言模板。

## 6. 解决方案优先级

### P0：去重与 source identity

目标：防止继续生成重复用例。

动作：

- 生成 YAML 强制写入 `requirement.source_asset_id`。
- 生成 YAML 强制写入 `requirement.intent_id` 与 `execution.selected_intent_ids`。
- 用例中心或生成服务按 `project + source_asset_id + intent_id` 判断已有用例。
- 对 `0001/0003` 建立重复治理记录，保留一条有效用例，另一条标记重复或废弃。

### P0：恢复可执行数据

目标：避免自然语言占位值进入 Runner。

动作：

- 空账号用例应输入空字符串或直接跳过输入步骤。
- 空密码用例应输入空字符串或直接跳过密码输入步骤。
- 空格用例使用真实 `" "`。
- 边界值用例使用明确长度字符串。
- 非法字符用例使用明确非法字符样例。

### P1：补齐前置步骤与断言

目标：让脚本真的验证测试意图。

动作：

- 登录成功后断言工作台、用户名、权限菜单。
- 错误输入断言 toast/message。
- 密码显隐断言 input type。
- 记住密码补齐勾选、登录、重新打开、自动填充断言。
- 退出登录补齐先登录。
- 重复点击补齐连续点击。
- 弱网超时补齐网络模拟能力，否则标记为暂不可自动化。

### P1：用例状态语义统一

目标：解决 DB `inactive` 与前端“活跃”的混乱。

动作：

- 明确生成用例默认状态策略。
- 如果自动化脚本已生成且可执行，落库为 `active`。
- 如果仍需人工复核，使用单独复核状态，不要复用 `inactive` 表达。

### P2：定位策略迁移到 data-testid

目标：提高执行稳定性。

动作：

- 登录页生成脚本优先使用 `login-username-input`、`login-password-input`、`login-submit-btn`。
- Runner 支持 data-testid 容器内 input 的链式定位。
- 页面对象导入后的中文名称和正式元素治理结果参与生成器绑定。

### P2：历史快照清理

目标：减少状态目录混乱。

动作：

- 保留 `web-ui/state/test-points` 为源资产命名空间。
- 保留 `web-ui/state/generated-cases` 为派生快照命名空间。
- 为历史重复、覆盖、恢复动作建立治理日志。
- 不直接物理删除已生成 YAML，先标记重复或废弃。

## 7. 验证方法

### 7.1 YAML 静态去重检查

检查维度：

- `source_asset_id + intent_id`
- `title + steps`
- `step signature`

验收：

- `intent-01` 只保留一条有效用例。
- 不再出现同一源测试点重复生成多个 case。

### 7.2 DB 一致性检查

建议查询：

```sql
select case_id, name, page_code, priority, status, last_execution_result, source_ref, updated_at
from test_cases
where project_code = 'mall'
  and case_id like 'mall-web-login-auth-fn-ai-%'
order by case_id;
```

```sql
select status, count(*)
from test_cases
where project_code = 'mall'
group by status
order by status;
```

验收：

- 用例数量与 YAML 数量、去重策略一致。
- 状态语义明确，不再让用户误解 `inactive`。

### 7.3 执行记录检查

建议查询：

```sql
select tc.case_id,
       count(*) as execution_count,
       array_agg(tce.status order by tce.executed_at desc nulls last, tce.id desc) as statuses,
       max(tce.executed_at) as latest
from test_cases tc
left join test_case_executions tce on tce.case_id = tc.id
where tc.project_code = 'mall'
  and tc.case_id like 'mall-web-login-auth-fn-ai-%'
group by tc.case_id
order by tc.case_id;
```

验收：

- 不把 `unknown` 当作通过。
- 每条用例执行后都有执行记录、报告入口和失败原因。

### 7.4 Runner 可执行性检查

检查项：

- `goto` 使用 `http://localhost:5174/#/login`。
- input 步骤有真实目标和真实值。
- click 步骤有稳定 locator。
- 场景有必要前置步骤。
- expected_result 已转成可执行断言。

验收：

- 单条登录成功用例能稳定通过。
- 异常用例能稳定捕获错误提示。
- 复杂场景不可自动化时明确标记，而不是生成伪脚本。

### 7.5 批量执行前置门禁

批量执行前必须检查：

- 无强重复用例。
- 无自然语言占位测试数据。
- 无缺失前置的复杂场景。
- 无弱网等 Runner 暂不支持能力的自动化用例。
- 源资产和生成快照命名空间未混用。

验收：

- 批量执行不会因为大量低质量脚本造成长时间等待。
- 失败能被归类为真实业务失败、定位失败、数据失败、环境失败或能力未支持。

## 8. 结论

当前用例中心已经有 20 条 `mall` 登录用例，但不应直接进入批量执行。

最紧急的问题不是“用例中心没有数据”，而是：

- 有强重复用例。
- 有 3 个源测试点未生成成功。
- 多数用例缺少真实测试数据、前置步骤或断言。
- 数据库状态 `inactive` 与前端“活跃”展示存在语义错位。
- 幂等去重缺少稳定的 `source_asset_id`。
- 定位策略尚未充分使用真实 `data-testid`。

建议先完成 P0 去重、source identity、测试数据修复，再进行小批量执行验证。批量执行应在高质量脚本比例提升后再开启。
