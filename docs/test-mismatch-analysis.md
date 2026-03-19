# 测试用例与实际应用不匹配问题

## 问题描述

测试用例通过了 schema 验证，但执行失败，原因是：

**测试用例中的元素定义** ≠ **mall-admin-web 实际元素结构**

## 当前测试用例期望的元素

```yaml
# product-smoke.yaml
- action: click
  target: product_menu      # 期望：menuitem role="商品"
- action: wait_for
  target: product_list_title # 期望：heading "商品列表"
```

## mall-admin-web 实际结构

### 登录页面 (`/normal/login`)
- 表单类名：`login-form-layout`
- 标题：`mall-admin-web`
- 用户名输入：placeholder="请输入用户名"
- 密码输入：placeholder="请输入密码"
- 登录按钮：需要查找

### 首页 (`/home`)
- 使用 ECharts 图表
- 显示订单统计卡片
- 没有 "商品列表" heading

### 导航菜单
需要查看 `layout` 目录结构确认菜单元素

## 解决方案

### 方案 1: 更新 Page Object 匹配实际应用 (推荐)

修改 `/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web/` 下的文件，使其匹配 mall-admin-web 的实际元素。

需要：
1. 查看 mall-admin-web 的实际 HTML 结构（使用浏览器开发者工具）
2. 更新 page-object.yaml 文件
3. 可能需要修改测试用例步骤

### 方案 2: 创建匹配测试用例的 Mock 页面

在 ai-test-platform 中创建一个简单的测试页面，专门用于验证测试框架。

### 方案 3: 使用 Playwright 代码生成器

```bash
cd /Users/bettyhuang/IdeaProjects/mall-admin-web
npx playwright codegen http://localhost:5173
```

通过录制实际用户操作，自动生成准确的定位器和测试代码。

## 下一步建议

1. **先验证登录功能** - 登录测试已通过，说明基础框架正常
2. **使用 Codegen 录制** - 录制实际业务流程，生成准确的定位器
3. **更新 Page Object** - 根据录制结果更新元素定义

## 快速验证命令

```bash
# 使用 Codegen 录制
npx playwright codegen http://localhost:5173

# 查看当前运行的应用
open http://localhost:5173
```
