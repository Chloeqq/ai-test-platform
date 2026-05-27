# Web 多页面 Runner 最小增强方案

> **适用范围**: `runners/web-playwright-python`
> **最后更新**: 2026-03-21
> **文档性质**: 当前可实施设计稿
> **目标版本**: `v4.1` 渐进增强

---

## 1. 目标

当前 Web Runner 的真实短板不是“缺少统一大 Schema”，而是：

- 一个 YAML 用例只能绑定一个 `execution.page`
- 一条业务流如果跨多个页面，只能拆成多条 case，或者勉强把所有 target 塞进一个 page object

因此，这份方案只解决一个问题：

**在保持当前 `v4` 主契约稳定的前提下，让单条 Web YAML 用例支持最小跨页面执行。**

不在本次范围内：

- 用例间依赖 `depends_on`
- API + UI 混合执行
- 调度拓扑排序
- `flow` DSL
- 多 Runner 统一执行协议

---

## 2. 当前现实依据

当前执行链路由以下代码决定：

- `runners/web-playwright-python/runner/yaml_executor.py`
- `runners/web-playwright-python/schemas/yaml_testcase.schema.json`
- `runners/web-playwright-python/runner/page_object_validator.py`
- `runners/web-playwright-python/runner/locator_resolver.py`

当前限制的直接来源：

1. `execution.page` 是唯一页面入口
2. `YamlExecutor.execute(...)` 只加载一次 page object
3. 后续所有步骤都共享这一份 page object

当前逻辑本质上是：

```text
execution.page -> load one page object -> all steps use same elements
```

这也是为什么当前跨页面业务流不自然。

---

## 3. 最小设计原则

本次增强必须遵守：

1. 保持向后兼容
   - 现有 `v4` YAML 无需修改即可继续执行
2. 保持强确定性
   - 仍由 Page Object + Playwright + 断言决定结果
3. 只做最小扩展
   - 不引入 `flow`、`pages`、`depends_on`
4. 错误定位要更清楚
   - 要明确报出“哪个 step、哪个 page、哪个 target”有问题

---

## 4. 建议的 `v4.1` 扩展方式

### 4.1 继续保留 `execution.page`

`execution.page` 继续作为默认页面：

```yaml
execution:
  runner: playwright
  page: product
  variables: {}
  steps:
    - action: login
    - action: click
      target: product_menu
```

### 4.2 仅新增 `step.page`

在步骤级别允许可选的 `page` 覆盖：

```yaml
execution:
  runner: playwright
  page: product
  variables: {}
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: click
      target: first_product
    - action: wait_for
      page: product/detail
      target: add_to_cart_button
    - action: assert_visible
      page: product/detail
      target: detail_title
```

语义规则：

- 如果 step 没写 `page`，默认使用 `execution.page`
- 如果 step 写了 `page`，该 step 用对应 page object 解析 target
- 所有步骤仍运行在同一个 Playwright `page` 实例中

这意味着本次增强的是“页面对象上下文切换”，不是“浏览器上下文切换”。

---

## 5. 为什么先选 `step.page`

相比 `execution.pages + flow`，`step.page` 更适合当前项目阶段：

- schema 改动最小
- 执行器改动最小
- 不需要额外 DSL
- 更容易回归验证
- 更符合“确定性先行”的原则

不选 `flow` 的原因：

- `flow` 会同时引入状态机、导航语义、成功回调、期望分支
- 当前 Runner 还没有这套抽象，直接引入会让不确定性升高

不选 `depends_on` 的原因：

- 那是编排层问题，不该先落到单 YAML 用例

---

## 6. 执行器改造方案

### 6.1 目标行为

把当前：

```text
load one page object once
```

改成：

```text
resolve step page -> load/cached page object -> execute step
```

### 6.2 建议改造点

#### A. `yaml_testcase.schema.json`

在 step 对象里增加可选字段：

```json
"page": {
  "type": "string",
  "minLength": 1
}
```

仍保持：

- `execution.page` 必填
- `runner=playwright` 不变

#### B. `YamlExecutor`

建议增加 page object 缓存：

```python
self._page_object_cache: dict[str, dict] = {}
```

增加方法：

```python
def _resolve_step_page_name(self, execution_page: str, step: dict) -> str:
    return str(step.get("page") or execution_page).strip()
```

执行逻辑改为：

1. 读取 `execution.page` 作为默认页
2. 遍历 steps
3. 对每个 step 解析 `step_page`
4. 按 `step_page` 加载或复用 page object
5. 用该 page object 校验 target 并执行 step

#### C. 错误消息增强

当前建议统一成这种风格：

- `Step 3 references missing target 'detail_title' on page 'product/detail'`
- `Page object not found for step 4: assets/page-objects/web/product/detail.page-object.yaml`
- `Unsupported action at step 2: hover`

#### D. Page Object 路径兼容

当前仓库已经存在：

- `assets/page-objects/web/product.page-object.yaml`
- `assets/page-objects/web/product/list.page-object.yaml`

这说明 page 名称允许带 `/`，因此本方案可以直接沿用：

- `page: product/detail`
- 对应文件：`assets/page-objects/web/product/detail.page-object.yaml`

不需要为了多页面额外发明新的 page 注册结构。

---

## 7. 契约示例

### 7.1 现有单页面 YAML

```yaml
version: v4
id: tc-product-001
title: 商品列表页面加载
module: product
priority: P0
tags:
  - smoke
  - product
owner: qa-team
status: automated
description: 登录后进入商品列表页面
requirement:
  - 商品列表展示
data: {}
execution:
  runner: playwright
  page: product
  variables: {}
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: wait_for
      target: product_list_title
    - action: assert_visible
      target: product_list_title
```

### 7.2 `v4.1` 最小跨页面示例

```yaml
version: v4
id: tc-product-DETAIL-001
title: 商品列表进入详情页
module: product
priority: P1
tags:
  - regression
  - product
owner: qa-team
status: automated
description: 验证从商品列表进入详情页后详情标题可见
requirement:
  - 商品详情页访问
data: {}
execution:
  runner: playwright
  page: product
  variables: {}
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: click
      target: first_product
    - action: wait_for
      page: product/detail
      target: detail_title
    - action: assert_visible
      page: product/detail
      target: detail_title
```

---

## 8. 需要补的测试

### 8.1 Schema 级测试

- step 带 `page` 时可通过 schema
- step 的 `page` 不是字符串时被拒绝

### 8.2 执行器单测

- 默认不写 `step.page` 时继续走 `execution.page`
- 写 `step.page` 时切换 page object
- 多个步骤重复使用同一个 `step.page` 时复用缓存
- 跨页面 target 缺失时报错信息正确

### 8.3 资产契约测试

建议补一条跨页面 fixture：

- `product -> product/detail`

校验：

- page object 文件存在
- target 可解析
- 步骤级 page 覆盖有效

---

## 9. 验收标准

第一阶段完成的标准应是：

- 所有现有 v4 YAML 无需修改即可继续执行
- `step.page` 已被 schema 和执行器正式支持
- 单条 YAML 用例可以稳定跑 2-3 个页面
- 报错能准确定位到 step/page/target
- 不引入 `depends_on`、`flow`、`api_ref`

---

## 10. 本阶段明确不做

- 不做 `execution.pages`
- 不做 `flow`
- 不做 run-level 状态编排
- 不做 API + UI phase
- 不做多 Runner 抽象
- 不做 `v5` 迁移器

这些都应在当前最小多页面能力稳定后，再由编排层或多 Runner 契约层继续推进。

---

## 11. 后续衔接

如果 `step.page` 版本稳定，再考虑：

1. `v4.2`
   - 增强 step 级错误分类
   - 增强证据中的 page 维度
2. 编排层
   - 把依赖调度放回 execution planner / orchestrator
3. 远期蓝图
   - 再评估是否真的需要 `flow` 或 `yaml-schema-v5`

---

## 12. 一句话结论

当前最合理的多页面 Runner 实现，不是上 `v5`，而是：

**在 `v4` 上做一个最小、确定、可回归的 `step.page` 增强。**

