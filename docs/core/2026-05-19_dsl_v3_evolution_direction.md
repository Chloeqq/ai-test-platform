# DSL V3.0 演进方向架构留档

文档日期：2026-05-19

记录状态：架构讨论留档，不包含代码实现

适用范围：测试点资产、生成用例 YAML DSL、执行编译器、Runner 执行链路、页面对象绑定、Allure 报告证据链

## 1. 背景与边界

本文件用于留存 DSL V3.0 演进方向。当前阶段只做架构判断和路线沉淀，不修改 runner、编译器、用例生成、页面对象、前端页面或历史 YAML。

当前仓库已有较多未提交变更，因此本次留档必须严格控制范围：只新增本文件，不顺手修复其他问题，不调整已有文档，不迁移历史用例。

被测系统地址铁律：

```text
http://localhost:5174/#/login
```

任何 DSL、Docker、Runner、页面对象导入或报告链路优化，都不得把被测系统原始地址改写成平台自身地址、Docker 内部地址、代理地址或其他临时地址。运行时如需适配容器网络，只能在运行配置层处理，不能写回 DSL 和页面对象资产。

## 2. 当前事实

当前平台主干仍以 `v1` 具体执行脚本为主。典型 YAML 直接在 `execution.steps` 中写入：

- `action`
- `target`
- `locator_type`
- `locator_value`
- `target_name`
- `value`
- `expected_result`

Runner 当前能稳定理解的是具体动作，而不是业务语义动作。已确认的执行动作包括：

- `goto`
- `input` / `fill` / `type`
- `click`
- `wait_for`
- `assert_visible`
- `assert_count`
- `assert_metric`
- `assert_url`
- `login`

当前 locator resolver 支持的定位类型包括：

- `placeholder`
- `text`
- `css`
- `id`
- `name`
- `xpath`
- `data-testid`
- `role`

这说明当前系统已经具备具体执行能力和页面对象治理基础，但还没有形成完整的“语义 DSL 直接执行”能力。

## 3. 用户 2.5 草案评估

用户提供的 `version: "2.5"` 草案具有很高参考价值。它把当前混在 `execution.steps` 里的信息拆成了更合理的结构：

- `identity`
- `requirement`
- `scenario`
- `data`
- `steps`
- `assertions`
- `execution`
- `evidence`

其中最有价值的设计包括：

- 使用 `requirement.source_asset_id` 绑定来源资产，支撑后续按 `source_asset_id + intent_id` 做幂等生成。
- 使用 `scenario.preconditions` 替代自然语言前置条件，让前置动作具备可编译空间。
- 使用 typed data 表达有效值、非法值、边界值和凭证类数据，避免把自然语言误当作输入值。
- 使用 `semantic_action` 表达业务动作，让测试人员不必关心 CSS、XPath 或 Playwright API。
- 使用 `semantic_assertion` 表达业务断言，让 `expected_result` 从说明文字升级为可执行目标。
- 使用 `evidence` 定义成功和失败时的证据采集策略。

但该草案不建议直接作为 runner 输入，也不建议直接定为最终 `2.5` 稳定版本。

原因是当前 runner 不能直接执行：

```yaml
semantic_action: input_username
semantic_assertion: login_success
```

如果不增加编译层，`semantic_action` 和 `semantic_assertion` 会从架构优化点变成新的执行卡点。

## 4. 版本命名建议

建议不要直接从当前 `v1` 跳到一个未定义边界的 `2.5`。更稳妥的方式是把草案拆入分阶段版本：

```text
V1.1：补齐身份追踪和幂等生成字段
V1.2：补齐结构化断言
V1.3：补齐结构化测试数据
V2.0：引入结构化 Source DSL
V2.5：引入语义编译器和页面对象动态绑定
V3.0：形成智能治理、自诊断、自愈建议和批量执行门禁
```

这样做的好处是：既能吸收草案的正确方向，又不破坏当前 `v1` 用例的可执行性。

## 5. DSL V3.0 总体目标

DSL V3.0 的目标不是简单换一种 YAML 写法，而是建立一套可追溯、可编译、可执行、可诊断的企业级测试 DSL。

核心目标：

- 业务可读：测试人员看到的是测试意图、场景、数据、步骤、断言，而不是 CSS 和 XPath。
- 执行稳定：元素定位从页面对象库动态解析，优先使用真实 `data-testid`。
- 生成可控：每条用例都绑定 `project + source_asset_id + intent_id`，避免重复生成和用例中心不同步。
- 断言可信：`expected_result` 不再只是文案，而要编译成可执行 assertion。
- 报告专业：Allure 报告能展示业务树、步骤、数据摘要、断言、证据和失败原因。
- 批量可治理：批量执行前能识别缺数据、缺元素、缺前置、缺断言、缺 runner 能力的用例。

## 6. 推荐架构分层

建议将未来 DSL 链路拆成四层。

### 6.1 Source DSL

Source DSL 面向测试人员和测试资产中心，强调业务可读和可维护。

它应表达：

- 用例身份
- 来源资产
- 测试意图
- 场景上下文
- 前置条件
- 测试数据
- 语义步骤
- 语义断言
- 证据策略

Source DSL 不应固化易过期的 CSS、XPath 或临时 locator。

### 6.2 Execution IR

Execution IR 是编译器产物，面向系统内部。

它应表达：

- 标准动作类型
- 页面编码
- 元素编码
- 数据引用
- 断言类型
- traceability
- compiler_status
- compiler_reason
- confidence

Execution IR 的职责是把业务语义变成可检查、可绑定、可渲染的中间结构。

### 6.3 Runner Script

Runner Script 面向当前 runner，保持与现有执行能力兼容。

它应表达：

- `goto`
- `input`
- `click`
- `wait_for`
- `assert_visible`
- `assert_url`
- `assert_count`
- `assert_metric`
- 编译后的 `locator_type`
- 编译后的 `locator_value`

Runner Script 是具体执行层，不应承担业务语义推理职责。

### 6.4 Runtime Record

Runtime Record 是执行后的事实记录。

它应记录：

- 实际执行步骤
- 实际使用 locator
- 实际输入数据摘要
- 耗时
- 截图
- 视频
- HTML
- console
- 失败 step
- 失败分类
- Allure 标签
- 报告链接

Runtime Record 用于复盘、报告、治理和后续自愈建议。

## 7. 对执行卡点的治理方向

### 7.1 身份追踪

当前重复生成和用例中心同步问题，根因之一是 source identity 不完整。

后续 DSL 必须稳定写入：

```yaml
requirement:
  source_asset_id: mall-web-login-auth-fn-ai-0021
  intent_id: intent-01

execution:
  selected_intent_ids:
    - intent-01
```

后续生成链路应以：

```text
project + source_asset_id + intent_id
```

作为幂等 Upsert 的核心身份。

### 7.2 结构化测试数据

自然语言数据不能直接进入 runner。

不应把以下文本直接作为输入值：

- `空格`
- `最小长度的合法账号`
- `比最大长度多1位的账号`
- `包含非法字符的密码`
- `框`

它们应先被转换为 typed data，再由数据生成器或数据池提供真实值。

建议数据结构表达：

```yaml
data:
  username:
    category: credential
    subtype: valid
    value: admin
  password:
    category: credential
    subtype: valid
    value: macro123
    sensitive: true
```

敏感数据在报告中必须脱敏。

### 7.3 结构化前置条件

自然语言前置条件只能作为说明，不能作为执行依据。

建议把：

```text
用户未登录，处于登录页面
```

转换为：

```yaml
preconditions:
  - type: clear_session
  - type: open_page
    page: login
```

复杂场景还需要支持登录态准备、数据准备、网络模式、浏览器存储清理等能力，但这些能力必须经过 runner 能力确认后再启用。

### 7.4 语义动作编译

`semantic_action` 不应直接交给 runner。

推荐流程：

```text
semantic_action: input_username
  -> compiler
  -> action: input
  -> element: username_input
  -> bind page object
  -> locator_type: data-testid
  -> locator_value: login-username-input
```

这样既保留业务可读性，又不破坏现有 runner 的具体动作模型。

### 7.5 语义断言编译

`semantic_assertion` 必须映射成具体断言组合。

例如：

```yaml
semantic_assertion: login_success
```

可以编译为：

- `assert_url`
- `assert_visible` 当前用户名
- `assert_visible` 左侧权限菜单

具体采用哪些断言，应由项目级断言配置或页面对象能力决定，不能只依赖自然语言 `expected_result`。

### 7.6 页面对象动态绑定

未来 Source DSL 中不应固化 locator。

推荐写法：

```yaml
steps:
  - action: input
    semantic_action: input_username
    element: username_input
    data_ref: username
```

执行前由页面对象库解析当前最稳定 locator。真实落地的 `data-testid` 应优先于 CSS、role、placeholder。

## 8. 分阶段演进路线

### V1.1：补齐身份追踪

目标：

- 所有生成用例补齐 `source_asset_id`。
- 所有生成用例补齐 `intent_id`。
- 所有生成用例补齐 `selected_intent_ids`。
- 生成链路按 `project + source_asset_id + intent_id` 做幂等判断。

价值：

- 减少重复用例。
- 提升测试资产中心与用例中心同步稳定性。

### V1.2：补齐结构化断言

目标：

- 从 `expected_result` 中抽取或生成可执行 assertions。
- 登录成功、登录失败、错误提示、跳转结果都必须有明确断言。

价值：

- 避免“动作执行了但业务没有被证明”。
- 提升 Allure 报告可信度。

### V1.3：补齐结构化数据

目标：

- 将自然语言测试数据转为 typed data。
- 引入数据池、边界值生成、非法值生成和敏感数据脱敏。

价值：

- 提升边界类、异常类用例可执行性。
- 降低批量执行失败率。

### V2.0：引入结构化 Source DSL

目标：

- 引入 `identity / requirement / scenario / data / steps / assertions / execution / evidence` 结构。
- 继续编译为当前 runner 可执行脚本。
- 保持 `v1` YAML 兼容。

价值：

- 让 DSL 从执行脚本升级为可维护资产。

### V2.5：引入语义编译器

目标：

- 支持 `semantic_action` 编译。
- 支持 `semantic_assertion` 编译。
- 支持页面对象动态绑定。
- 支持编译前能力检查。

价值：

- 将测试人员关注点从 locator 和 Playwright 动作转移到业务语义。

### V3.0：智能治理与自愈建议

目标：

- 执行前评估成功概率。
- 批量执行前做门禁。
- 失败后自动归因。
- 基于运行证据给出 locator、数据、前置、断言修复建议。
- 将执行结果反哺测试点、用例和页面对象质量评分。

价值：

- 从“能跑脚本”升级为“可治理的测试工程平台”。

## 9. 风险点

### 9.1 语义动作不能直接给 runner

当前 runner 不理解 `semantic_action`。如果直接把用户草案作为执行 YAML，会导致执行失败。

规避方式：

- 保留语义层。
- 增加编译层。
- runner 继续执行具体动作。

### 9.2 网络模拟能力未确认

草案中的：

```yaml
network:
  mode: slow_3g
```

属于合理方向，但当前不能默认认为 runner 已具备完整网络模拟能力。

规避方式：

- 先作为声明字段留存。
- 编译前做 runner capability check。
- 不支持时提前阻断或标记 manual/unsupported。

### 9.3 自然语言数据不可执行

如果 typed data 没有落地，边界值和异常值仍会被自然语言污染。

规避方式：

- 数据必须进入 `category / subtype / value / generator / pool` 模型。
- 缺少真实值时，编译失败优于带病执行。

### 9.4 断言规则缺失会导致报告不可信

如果只有 `expected_result` 文案，没有 assertion，报告仍然会空洞。

规避方式：

- `semantic_assertion` 必须可解析到具体断言。
- 无法解析时，编译器应给出明确错误。

### 9.5 过早迁移会破坏 v1 兼容

当前已有大量 `v1` 用例和执行链路，不能一次性切换。

规避方式：

- V2/V3 作为新增能力引入。
- 旧用例继续走兼容执行。
- 新生成用例逐步启用结构化 DSL。

### 9.6 被测系统地址可能再次被误改

历史问题表明，被测系统地址容易被 Docker、平台地址或运行时地址混淆。

规避方式：

- DSL 和页面对象中保留原始业务地址。
- 运行时映射只能存在于 runner 配置层。
- 文档、校验和测试中持续写明地址铁律。

## 10. 验收标准

未来进入实现阶段时，至少应满足以下标准：

- `v1` YAML 仍可执行。
- 新 DSL 不直接修改被测系统地址。
- 同一 `project + source_asset_id + intent_id` 不再重复生成多个用例。
- `semantic_action` 不直接进入 runner，而是先编译为具体动作。
- `semantic_assertion` 能编译为至少一个可执行断言。
- 登录成功用例不仅点击登录，还要验证跳转、用户信息或菜单加载。
- 页面对象绑定优先使用真实 `data-testid`。
- 敏感数据在报告中脱敏。
- 批量执行前能识别缺数据、缺元素、缺前置、缺断言、缺能力的用例。
- Allure 报告能展示业务层级、步骤、断言和证据。

## 11. 后续执行建议

建议后续不要从 V3.0 直接开工，而是按风险最低的顺序推进：

1. 先补齐 `source_asset_id + intent_id` 幂等身份。
2. 再补登录主链路的结构化断言。
3. 再治理自然语言测试数据。
4. 然后引入结构化 Source DSL。
5. 最后建设语义编译器和智能治理能力。

这个顺序能优先解决当前真实痛点：重复用例、用例中心同步、执行不可信、报告空洞和批量执行失败率高。

## 12. Assumptions

- 本文件只做架构留档，不代表立即启动 DSL V3.0 代码实现。
- 当前 `v1` DSL 仍是生产可执行主链路，必须保持兼容。
- 页面对象库和真实 `data-testid` 是未来执行稳定性的核心基础。
- DSL V3.0 的重点是语义表达、编译治理和执行证据打通，而不是简单增加 YAML 字段。
