# AI 自动化测试平台学习记录（Day 1）

**日期：2026-03-15**

------------------------------------------------------------------------

# 一、学习目标

今天的目标是从 **0 → 1 搭建 AI
自动化测试平台的基础框架**，完成一个可以真实运行的 Web 自动化测试底座。

核心目标：

-   搭建 Playwright 自动化测试环境
-   建立项目目录结构
-   实现登录自动化
-   实现多个 Smoke Test
-   接入环境变量
-   初步设计 YAML 测试资产
-   实现 YAML 驱动执行的 Runner

------------------------------------------------------------------------

# 二、项目目录结构

当前项目结构：

    ai-test-platform
    │
    ├── .env
    ├── .env.example
    │
    ├── agents
    │
    ├── assets
    │   ├── page-objects
    │   │   └── web
    │   │       ├── login.page-object.yaml
    │   │       ├── product.page-object.yaml
    │   │       └── order.page-object.yaml
    │   │
    │   └── test-cases
    │       └── smoke
    │           ├── login-smoke.yaml
    │           ├── product-smoke.yaml
    │           └── order-smoke.yaml
    │
    ├── runners
    │   └── web-playwright
    │       ├── src
    │       │   ├── hooks
    │       │   ├── pages
    │       │   │   ├── login.page.ts
    │       │   │   ├── product.page.ts
    │       │   │   └── order.page.ts
    │       │   │
    │       │   ├── runner
    │       │   │   ├── yaml-loader.ts
    │       │   │   ├── locator-resolver.ts
    │       │   │   └── yaml-executor.ts
    │       │   │
    │       │   └── tests
    │       │       ├── smoke
    │       │       │   ├── login.smoke.spec.ts
    │       │       │   ├── product.smoke.spec.ts
    │       │       │   └── order.smoke.spec.ts
    │       │       │
    │       │       └── yaml-smoke-v2.spec.ts
    │       │
    │       └── playwright.config.ts
    │
    └── README.md

------------------------------------------------------------------------

# 三、完成的核心功能

## 1 Playwright 自动化环境搭建

安装依赖：

``` bash
npm install
npx playwright install
```

运行测试：

``` bash
npx playwright test
```

------------------------------------------------------------------------

# 四、实现 Smoke Test

当前已经实现 3 条核心 Smoke Test：

  用例            功能
  --------------- --------------
  login smoke     登录验证
  product smoke   商品列表页面
  order smoke     订单列表页面

运行结果：

    3 passed

------------------------------------------------------------------------

# 五、登录自动化实现

核心逻辑：

1.  打开登录页
2.  输入用户名密码
3.  点击登录
4.  验证接口返回成功
5.  验证首页元素出现

关键代码示例：

``` ts
await page.getByPlaceholder('请输入用户名').fill(username)
await page.getByPlaceholder('请输入密码').fill(password)
await page.getByRole('button', { name: '登录' }).click()
```

------------------------------------------------------------------------

# 六、环境变量配置

项目使用 `.env` 管理测试配置。

示例：

    BASE_URL=http://localhost:5173/login#/login
    TEST_USERNAME=admin
    TEST_PASSWORD=macro123
    API_BASE_URL=http://localhost:8080

Playwright 配置加载：

``` ts
import dotenv from 'dotenv'

dotenv.config()
```

------------------------------------------------------------------------

# 七、Page Object 模式

为了提高可维护性，项目使用 Page Object 模式。

示例：

    LoginPage
    ProductPage
    OrderPage

每个页面封装：

-   页面元素
-   页面动作
-   页面断言

------------------------------------------------------------------------

# 八、YAML 测试资产设计

测试用例不再写死在代码里，而是放在 YAML 文件。

示例：

``` yaml
id: TC-PRODUCT-001
title: 商品列表页面加载

steps:
  - action: login
  - action: click_menu
    target: product_menu
  - action: assert_text
    target: product_list_title
```

------------------------------------------------------------------------

# 九、YAML Runner 设计

实现了 YAML → 自动执行流程：

    YAML Test Case
          ↓
    YAML Runner
          ↓
    Playwright 执行

核心模块：

  模块               功能
  ------------------ --------------
  yaml-loader        读取 YAML
  locator-resolver   解析 locator
  yaml-executor      执行步骤

------------------------------------------------------------------------

# 十、当前平台能力

当前框架已经具备：

    Playwright Runner
    Page Object
    Smoke Tests
    YAML 测试资产
    YAML Runner
    环境变量管理

框架能力等级：

    自动化测试框架（可运行）

------------------------------------------------------------------------

# 十一、下一步计划

下一阶段重点：

## 1 扩展 YAML 执行动作

支持：

    fill
    click
    assert_url
    wait
    select
    upload

------------------------------------------------------------------------

## 2 AI 生成测试用例

目标实现：

    PRD / 需求
         ↓
    AI 分析
         ↓
    生成 YAML Test Case
         ↓
    自动执行

------------------------------------------------------------------------

## 3 AI 自动化测试平台架构

最终目标：

    需求 → AI生成测试 → 自动执行 → 报告分析

------------------------------------------------------------------------

# 十二、今日总结

今天完成了 AI 自动化测试平台 **第一阶段核心基础设施**：

-   自动化框架搭建完成
-   Smoke 测试跑通
-   YAML 资产模型设计完成
-   YAML Runner 初版实现
-   平台架构基础建立

当前阶段：

    AI Test Platform – Foundation Ready

下一阶段：

    AI Test Design Agent
    YAML Runner v3
    测试平台服务化

------------------------------------------------------------------------

**学习阶段：Day 1 完成**
