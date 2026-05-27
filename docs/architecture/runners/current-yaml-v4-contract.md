# 当前 YAML v4 生效契约

> **适用 Runner**: `runners/web-playwright-python`
> **最后更新**: 2026-03-21
> **文档性质**: 当前真实生效契约，不是目标态蓝图

---

## 1. 这份文档解决什么问题

当前仓库里已经存在多份 Runner 设计稿，但真正生效的 YAML 契约仍然是 `web-playwright-python` 这一条主链上的 `v4`。这份文档的目标是把“现在到底支持什么、不支持什么、哪些校验是真正生效的”写清楚，作为后续 `v4.1` 或多页面增强的基线。

当前主要证据来自：

- `runners/web-playwright-python/schemas/yaml_testcase.schema.json`
- `runners/web-playwright-python/runner/yaml_executor.py`
- `runners/web-playwright-python/runner/test_case_loader.py`
- `runners/web-playwright-python/runner/data_expander.py`
- `runners/web-playwright-python/runner/variable_resolver.py`
- `runners/web-playwright-python/runner/page_object_validator.py`
- `runners/web-playwright-python/runner/locator_resolver.py`
- `runners/web-playwright-python/tests/test_asset_contracts.py`

---

## 2. 当前生效范围

### 2.1 当前支持的执行模式

- 单 runner：仅支持 `playwright`
- 单页面执行：仅支持 `execution.page`
- 单浏览器上下文：所有步骤运行在同一个 Playwright `page`
- YAML 用例执行
- 数据驱动展开
- 变量替换
- Page Object 解析

### 2.2 当前不支持的能力

下面这些能力目前都**不是 v4 生效契约的一部分**：

- 多页面 `pages`
- 页面流转 `flow`
- 用例依赖 `depends_on`
- API 测试 `api_ref`
- 全局配置 `global_config`
- 执行配置 `execution_config`
- 并发控制 `concurrency`
- 数据工厂 `data_factories`
- 混合 API + UI 执行

如果在 YAML 中直接加入这些字段，当前 schema 校验会拒绝，或者执行器根本不会消费。

---

## 3. 当前测试用例契约

### 3.1 顶层结构

当前 JSON Schema 要求的顶层字段：

```yaml
version: v4
id: TC-LOGIN-REG-001
title: 管理员登录回归验证
module: auth
priority: P1
tags:
  - regression
  - auth
owner: qa-team
status: automated
description: 回归验证管理员登录成功后能看到首页菜单
requirement:
  - 管理员登录功能
data: {}
execution:
  runner: playwright
  page: login
  variables: {}
  steps:
    - action: login
    - action: assert_visible
      target: home_menu
```

### 3.2 必填字段

必须存在：

- `version`
- `id`
- `title`
- `module`
- `execution`

其中 `execution` 里必须存在：

- `runner`
- `page`
- `steps`

### 3.3 当前允许字段

顶层允许：

- `version`
- `id`
- `title`
- `module`
- `priority`
- `tags`
- `owner`
- `status`
- `description`
- `requirement`
- `data`
- `execution`

注意：顶层 `additionalProperties=false`，所以任何未声明字段都会被 schema 拒绝。

---

## 4. `execution` 字段契约

### 4.1 当前支持结构

```yaml
execution:
  runner: playwright
  page: product
  variables:
    search_keyword: "{{keyword}}"
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: fill
      target: search_input
      value: "{{search_keyword}}"
    - action: click
      target: search_button
    - action: wait_for
      target: product_table
```

### 4.2 字段说明

- `runner`
  - 当前只能是 `playwright`
- `page`
  - 字符串
  - 对应仓库根目录下的 `assets/page-objects/web/{page}.page-object.yaml`
- `variables`
  - 可选对象
  - 在执行前与 `_data` 合并，供步骤里的 `{{var}}` 替换使用
- `steps`
  - 至少 1 步
  - 每一步都必须有 `action`

### 4.3 当前动作集合

当前只支持这 7 个动作：

- `login`
- `click`
- `fill`
- `wait_for`
- `assert_visible`
- `assert_url`
- `goto`

其中：

- `click / fill / wait_for / assert_visible` 必须有 `target`
- `fill / assert_url / goto` 必须有 `value`
- `login` 不要求 `target` 和 `value`

---

## 5. 当前动作的确定性边界

### 5.1 `login`

- 由 `actions/login.py` 驱动
- 使用共享登录逻辑
- 在稳定 smoke 基线里要求是裸步骤：

```yaml
- action: login
```

### 5.2 `click / fill / wait_for / assert_visible`

- 都依赖当前页面的 page object target
- target 必须在 `elements` 中存在
- `fill` 会消费 `value`
- `assert_visible` 是确定性断言，不是 AI 判断

### 5.3 `assert_url`

- 不需要 target
- 需要 `value`
- 用于 URL 级断言

### 5.4 `goto`

- 不需要 target
- 需要 `value`
- 执行导航动作

---

## 6. Page Object 契约

### 6.1 当前结构

```yaml
page: login

elements:
  username_input:
    locator_type: placeholder
    locator_value: 请输入用户名

  password_input:
    locator_type: placeholder
    locator_value: 请输入密码

  login_button:
    locator_type: role
    role: button
    locator_value: 登录

  home_menu:
    locator_type: role
    role: menuitem
    locator_value: 首页
```

### 6.2 当前支持的 locator 类型

- `placeholder`
- `text`
- `css`
- `role`

其中 `role` 类型额外要求：

- `role` 字段必须存在

### 6.3 当前 page object 校验

当前不仅做 JSON Schema 校验，还会验证：

- `page_object.page == execution.page`
- 对应文件存在
- 引用的 target 在 `elements` 中存在

---

## 7. 数据驱动契约

### 7.1 当前支持方式

```yaml
data:
  keyword:
    - 手机
    - 电脑
    - 图书

execution:
  runner: playwright
  page: product
  variables:
    search_keyword: "{{keyword}}"
  steps:
    - action: login
    - action: fill
      target: search_input
      value: "{{search_keyword}}"
```

### 7.2 当前展开规则

由 `runner/data_expander.py` 决定：

- `data` 每个字段都必须是 list
- 每个 list 都不能为空
- 所有 list 长度必须一致
- 每一组同索引的数据会展开成一条独立 case
- 展开后的运行时上下文写入 `_data`

### 7.3 当前限制

- 不支持笛卡尔积展开
- 不支持嵌套对象组合策略
- 不支持条件性数据集选择

---

## 8. 变量替换契约

### 8.1 当前语法

支持 `{{variable}}` 形式：

```yaml
variables:
  expected_name: "{{keyword}}"
```

### 8.2 当前规则

由 `runner/variable_resolver.py` 决定：

- 只处理字符串
- 只做简单字符串替换
- 如果变量不存在，不报错，保留原值
- 不支持表达式求值
- 不支持过滤器、函数、默认值语法

这意味着它是一个“简单变量替换器”，不是模板引擎。

---

## 9. 当前加载与目录约束

### 9.1 当前真实资产路径

当前生效资产位于仓库根目录：

- `assets/test-cases/smoke/`
- `assets/test-cases/ai-generated/`
- `assets/page-objects/web/`

### 9.2 当前加载模式

由 `runner/test_case_loader.py` 决定：

- `RUN_MODE=smoke`：读取 `assets/test-cases/smoke`
- `RUN_MODE=ai`：读取 `assets/test-cases/ai-generated`
- `RUN_MODE=all`：两者都读取

### 9.3 当前路径安全限制

当通过 `TEST_CASE_PATH` 指定单文件时：

- `RUN_MODE=ai` 只能读取 `ai-generated` 目录下的文件
- `RUN_MODE=smoke` 只能读取 `smoke` 目录下的文件

这是当前已生效的防误读边界。

---

## 10. 当前已生效的更强约束

除了 schema 和执行器，仓库里还有一层更强的契约测试：

- `runners/web-playwright-python/tests/test_asset_contracts.py`

这层测试额外约束了：

- 所有 YAML 用例必须能通过 schema 校验
- 所有用例引用的 page object 必须存在
- 所有步骤 target 必须存在于对应 page object
- 稳定 smoke 集合是冻结的
- 稳定 smoke 的步骤基线是冻结的
- 稳定 smoke 页面对象的关键 target 集合是冻结的

这说明当前回归主链的稳定性，不仅依赖 schema，还依赖“冻结基线 + 资产契约测试”。

---

## 11. 当前不确定性边界

这部分非常重要：当前 `v4` 契约的确定性是高的，但不是“结构正确 = 业务正确”。

### 11.1 当前确定的部分

- YAML 结构是否合法
- action 是否支持
- target 是否存在
- page object 是否存在
- locator 类型是否合法
- Playwright 是否真正完成点击、输入、等待、断言

### 11.2 当前不确定的部分

- 用例是否真的覆盖了正确业务目标
- AI 生成用例是否符合稳定业务基线
- 某个 target 是否“存在但不够稳”
- 某条断言是否“足够有业务价值”

这些问题不属于 Runner 自己解决，而属于：

- 页面分析
- 测试设计
- 风险评估
- 人工确认点

所以 Runner 文档必须和上游 Agent 文档分开理解。

---

## 12. 后续演进建议

基于当前契约，最合理的下一步不是直接跳到 `v5`，而是：

1. `v4.1`：最小多页面增强
   - 支持步骤级 `page`
   - 保持单 runner
2. `v4.2`：更清晰的断言与错误信息
   - 明确 step 级失败分类
   - 明确 page/target/action 报错位置
3. 编排层增强
   - 把 `depends_on` 放到运行计划，不先塞进单 YAML
4. 多 Runner 最小契约
   - 先统一 execution record / evidence manifest，再谈 schema 大统一

---

## 13. 一句话结论

当前 YAML v4 契约已经足够支撑稳定的 Web 回归主链，但它是一个**单 runner、单页面、强确定性、有限动作集**的现实契约。后续所有增强都应该在这个基线之上渐进演进，而不是直接假设平台已经进入 `v5` 或多 Runner 时代。

