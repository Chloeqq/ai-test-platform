# OMS 退货申请处理 - 用例设计与可执行性矩阵

> 页面 URL: [http://localhost:5173/#/oms/returnApply](http://localhost:5173/#/oms/returnApply)  
> 现有可用资产: [`/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml)

这份文档不再只写“应该测什么”，而是把“当前能不能测、怎么测、为什么会卡住”一起写清楚。

## 1. 页面现状

从代码看，页面包含这些筛选项：

- 服务单号
- 处理状态
- 申请时间
- 操作人员
- 处理时间

但是当前页面没有分页器，表格结果只显示接口返回的当前页数据。  
这意味着：

- 你可以验证“有没有筛到目标数据”
- 你不能直接靠 UI 验证“全部 21 条都展开”

页面实现位置：

- [`/Users/bettyhuang/IdeaProjects/mall-admin-web/src/views/oms/apply/index.vue`](/Users/bettyhuang/IdeaProjects/mall-admin-web/src/views/oms/apply/index.vue)

## 2. 当前框架能力

当前 Playwright YAML 执行器支持的动作只有：

- `login`
- `goto`
- `assert_url`
- `click`
- `fill`
- `wait_for`
- `assert_visible`

这意味着：

- 文本输入、按钮点击、可见性检查可以直接做
- 下拉选择、日期控件、复杂表格断言还需要人工配合或后续扩展

页面对象位置：

- [`/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web/returnapply.page-object.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web/returnapply.page-object.yaml)

## 3. 15 条用例的真实判断

| 用例 ID | 用例名称 | 当前状态 | 说明 |
|---|---|---|---|
| TC_RETURN_001 | 服务单号精确搜索 | 可自动 | 直接用 `search_input=3` 就能跑。 |
| TC_RETURN_002 | 服务单号模糊搜索 | 不支持 | 当前查询是按 `id` 精确查，不是模糊查。 |
| TC_RETURN_003 | 服务单号搜索 - 无结果 | 可自动 | `999` 是稳定的空结果样例。 |
| TC_RETURN_004 | 按处理状态筛选 - 已完成 | 可自动 | 已补页对象、浏览器 smoke 和可执行 YAML 样板。 |
| TC_RETURN_005 | 按处理状态筛选 - 退货中 | 需补交互 | 同上。 |
| TC_RETURN_006 | 按处理状态筛选 - 已拒绝 | 需补交互 | 同上。 |
| TC_RETURN_007 | 按处理状态筛选 - 待处理 | 数据不匹配 | 当前数据里 `status=0` 不止 1 条。 |
| TC_RETURN_008 | 按申请时间范围筛选 | 需人工/接口 | 页面有日期控件，但当前 UI 不直接展示总量。 |
| TC_RETURN_009 | 按处理时间范围筛选 | 可自动（浏览器 state 注入） | 页面公开日期控件的序列化仍不稳定，但可以通过浏览器级 state 稳定验收。 |
| TC_RETURN_010 | 按操作人员筛选 | 数据不匹配 | 当前数据里 `handleMan` 基本为空。 |
| TC_RETURN_011 | 多条件组合筛选 | 需补交互 | 理论可测，但需要完整状态下拉操作。 |
| TC_RETURN_012 | 重置筛选条件 | 需补交互 | 页面有重置按钮，但当前自动化没有把所有控件都接上。 |
| TC_RETURN_013 | 查询搜索 - 空条件 | 需接口辅助 | UI 不会把 21 条一次性铺满在屏幕上。 |
| TC_RETURN_014 | 服务单号搜索 - 特殊字符 | 可自动 | 重点看是否报错或有异常回显。 |
| TC_RETURN_015 | 服务单号搜索 - SQL 注入 | 可自动 | 重点看是否报错或有异常回显。 |

## 4. 当前可直接落地的自动化最小集

建议先跑这 5 条，把平台链路打通：

1. `TC_RETURN_001`
2. `TC_RETURN_003`
3. `TC_RETURN_004`
4. `TC_RETURN_014`
5. `TC_RETURN_015`

如果你想先看最直观的成功案例，就跑 `TC_RETURN_001`。

## 5. 建议的 YAML 结构

下面这个结构最适合当前框架：

```yaml
version: v4
id: TC_RETURN_001
title: 服务单号精确搜索
module: returnapply
priority: P0
owner: qa-team
status: automated
description: 验证服务单号精确查询可以返回目标记录。
tags:
  - ai-generated
  - smoke
  - returnapply

execution:
  runner: playwright
  page: returnapply
  steps:
    - action: login
    - action: goto
      value: http://localhost:5173/#/oms/returnApply
    - action: assert_url
      value: http://localhost:5173/#/oms/returnApply
    - action: wait_for
      target: search_input
    - action: fill
      target: search_input
      value: "3"
    - action: click
      target: search_button
    - action: wait_for
      target: returnapply_table
    - action: assert_visible
      target: returnapply_table
```

现成资产可以直接参考：

- [`/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml`](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3.yaml)

## 6. 如果你要手工跑页面，步骤如下

### 6.1 打开页面

打开：

```text
http://localhost:5173/#/oms/returnApply
```

### 6.2 先做一个最稳的检查

在“服务单号”输入框输入 `3`，点“查询搜索”。

你应该看到：

- 表格里出现服务单号 `3`
- 页面不报错

### 6.3 再做空结果检查

输入 `999`，点“查询搜索”。

你应该看到：

- 表格为空
- 出现空态提示

### 6.4 再做安全烟雾测试

分别输入：

- `<script>`
- `' OR '1'='1`

然后点“查询搜索”。

你要观察的不是“是不是证明绝对安全”，而是：

- 页面有没有崩
- 浏览器控制台有没有异常
- 有没有明显的恶意内容被直接执行

## 7. 结果怎么判

### 通过

- 页面能打开
- 点击查询后有正确结果
- `SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-3` 能稳定通过
- `TC_RETURN_004` 能稳定通过
- `SMOKE-RETURNAPPLY-SEARCH-SERVICE-NO-999` 能稳定返回空态

### 失败

- `BASE_URL is unreachable`
- `Connection refused`
- `请先选择用例`
- 表格不刷新
- 搜索后页面报错

### 不能直接下结论的情况

- 日期筛选
- 操作人员筛选
- 结果数量类断言
- 安全类断言

这些建议先当成“需要人工复核”而不是“平台已经全自动覆盖”。

## 8. 这页最值得先补的下一步

如果后面要把 `returnApply` 做得更完整，优先级建议是：

1. 补日期选择器的自动化定位
2. 给页面加分页器
3. 再把操作人员筛选补成可自动验收
4. 再把批量和组合筛选做成真正的回归集
