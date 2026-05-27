# OMS 订单设置页面 - UI 测试用例设计文档

> **页面 URL**: http://localhost:5173/#/oms/orderSetting
> **创建日期**: 2026-03-21
> **测试框架**: Playwright + YAML

---

## 📊 测试点提取

### 1. 页面加载测试

| 测试点 ID | 测试点名称 | 优先级 | 测试类型 |
|----------|-----------|--------|---------|
| TP-OS-001 | 页面正常加载 | P0 | Smoke |
| TP-OS-002 | 页面标题正确 | P0 | Smoke |
| TP-OS-003 | 菜单高亮正确 | P1 | UI |

### 2. 订单超时设置测试

| 测试点 ID | 测试点名称 | 优先级 | 测试类型 |
|----------|-----------|--------|---------|
| TP-OS-010 | 订单超时输入框显示 | P0 | UI |
| TP-OS-011 | 设置订单超时时间 - 有效值 | P0 | Functional |
| TP-OS-012 | 设置订单超时时间 - 边界值 | P1 | Boundary |
| TP-OS-013 | 设置订单超时时间 - 无效值 | P1 | Validation |
| TP-OS-014 | 订单超时单位显示 | P2 | UI |

### 3. 自动取消设置测试

| 测试点 ID | 测试点名称 | 优先级 | 测试类型 |
|----------|-----------|--------|---------|
| TP-OS-020 | 自动取消开关显示 | P0 | UI |
| TP-OS-021 | 切换自动取消开关 - 开启 | P0 | Functional |
| TP-OS-022 | 切换自动取消开关 - 关闭 | P0 | Functional |
| TP-OS-023 | 自动取消超时设置 | P1 | Functional |

### 4. 订单确认设置测试

| 测试点 ID | 测试点名称 | 优先级 | 测试类型 |
|----------|-----------|--------|---------|
| TP-OS-030 | 订单确认开关显示 | P0 | UI |
| TP-OS-031 | 切换订单确认开关 - 开启 | P0 | Functional |
| TP-OS-032 | 切换订单确认开关 - 关闭 | P0 | Functional |

### 5. 保存功能测试

| 测试点 ID | 测试点名称 | 优先级 | 测试类型 |
|----------|-----------|--------|---------|
| TP-OS-040 | 保存按钮显示 | P0 | UI |
| TP-OS-041 | 保存设置 - 成功 | P0 | Functional |
| TP-OS-042 | 保存设置 - 验证成功提示 | P0 | Assertion |
| TP-OS-043 | 重置按钮功能 | P2 | Functional |

---

## 📝 测试用例设计

### 用例 1: 页面加载测试

```yaml
version: v4
id: TC-OS-LOAD-001
title: 订单设置页面 - 页面加载测试
module: oms/order-setting
priority: P0
tags:
  - smoke
  - order-setting
  - page-load
owner: qa-team
status: automated
description: 验证订单设置页面可以正常加载

requirement:
  - 订单设置页面加载功能

data: {}

execution:
  runner: playwright
  page: order-setting
  variables: {}
  steps:
    - action: login

    - action: click
      target: order_setting_menu

    - action: wait_for
      target: order_timeout_section

    - action: assert_visible
      target: order_timeout_section

    - action: assert_visible
      target: auto_cancel_section

    - action: assert_visible
      target: order_confirm_section
```

### 用例 2: 订单超时设置 - 有效值

```yaml
version: v4
id: TC-OS-TIMEOUT-001
title: 订单设置 - 设置订单超时时间（有效值）
module: oms/order-setting
priority: P0
tags:
  - functional
  - order-setting
  - timeout
owner: qa-team
status: automated
description: 验证可以设置有效的订单超时时间

requirement:
  - 订单超时设置功能

data:
  timeout_values:
    - 30
    - 60
    - 120

execution:
  runner: playwright
  page: order-setting
  variables:
    timeout_value: "60"
  steps:
    - action: login

    - action: click
      target: order_setting_menu

    - action: wait_for
      target: order_timeout_input

    - action: fill
      target: order_timeout_input
      value: "{{timeout_value}}"

    - action: click
      target: save_button

    - action: wait_for
      target: success_message

    - action: assert_visible
      target: success_message
```

### 用例 3: 订单超时设置 - 边界值

```yaml
version: v4
id: TC-OS-TIMEOUT-002
title: 订单设置 - 设置订单超时时间（边界值）
module: oms/order-setting
priority: P1
tags:
  - boundary
  - order-setting
  - timeout
owner: qa-team
status: automated
description: 验证订单超时时间的边界值处理

requirement:
  - 订单超时设置功能

data: {}

execution:
  runner: playwright
  page: order-setting
  variables:
    min_value: "1"
    max_value: "1440"
  steps:
    - action: login

    - action: click
      target: order_setting_menu

    # 测试最小值
    - action: fill
      target: order_timeout_input
      value: "{{min_value}}"

    - action: click
      target: save_button

    - action: assert_visible
      target: success_message

    # 测试最大值
    - action: fill
      target: order_timeout_input
      value: "{{max_value}}"

    - action: click
      target: save_button

    - action: assert_visible
      target: success_message
```

### 用例 4: 自动取消开关切换

```yaml
version: v4
id: TC-OS-AUTOCANCEL-001
title: 订单设置 - 自动取消开关切换
module: oms/order-setting
priority: P0
tags:
  - functional
  - order-setting
  - auto-cancel
owner: qa-team
status: automated
description: 验证自动取消开关可以正常切换

requirement:
  - 自动取消设置功能

data: {}

execution:
  runner: playwright
  page: order-setting
  variables: {}
  steps:
    - action: login

    - action: click
      target: order_setting_menu

    - action: wait_for
      target: auto_cancel_switch

    # 开启自动取消
    - action: click
      target: auto_cancel_switch

    - action: wait_for_timeout
      time_ms: 500

    # 保存设置
    - action: click
      target: save_button

    - action: assert_visible
      target: success_message

    # 关闭自动取消
    - action: click
      target: auto_cancel_switch

    - action: click
      target: save_button

    - action: assert_visible
      target: success_message
```

### 用例 5: 保存设置 - 完整流程

```yaml
version: v4
id: TC-OS-SAVE-001
title: 订单设置 - 保存完整配置
module: oms/order-setting
priority: P0
tags:
  - smoke
  - order-setting
  - save
owner: qa-team
status: automated
description: 验证可以保存完整的订单设置配置

requirement:
  - 订单设置保存功能

data: {}

execution:
  runner: playwright
  page: order-setting
  variables:
    timeout_value: "90"
  steps:
    - action: login

    - action: click
      target: order_setting_menu

    - action: wait_for
      target: order_timeout_input

    # 设置订单超时
    - action: fill
      target: order_timeout_input
      value: "{{timeout_value}}"

    # 开启自动取消
    - action: click
      target: auto_cancel_switch

    # 开启订单确认
    - action: click
      target: order_confirm_switch

    # 保存设置
    - action: click
      target: save_button

    - action: wait_for
      target: success_message

    # 验证成功提示
    - action: assert_visible
      target: success_message

    # 验证设置已保存（重新加载页面）
    - action: reload_page

    - action: wait_for
      target: order_timeout_input
```

---

## 🚀 执行命令

### 1. 执行单个测试用例

```bash
# 执行页面加载测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "TC-OS-LOAD-001" \
  --headed \
  --video=on \
  --screenshot=on

# 执行订单超时测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "TC-OS-TIMEOUT" \
  --headed
```

### 2. 执行所有订单设置测试

```bash
# 执行 OMS 订单设置所有测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "order-setting" \
  --headed \
  --video=on \
  --screenshot=on \
  --html=test-reports/order-setting-report.html
```

### 3. 执行 Smoke 测试

```bash
# 执行 Smoke 测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -m "smoke and order-setting" \
  --headed
```

---

## 📊 测试报告

### 预期输出

```
Test Session Summary
====================

Total Tests: 5
Passed: 5
Failed: 0
Skipped: 0

Test Results:
-------------
✓ TC-OS-LOAD-001 - 订单设置页面 - 页面加载测试 (2.3s)
✓ TC-OS-TIMEOUT-001 - 订单设置 - 设置订单超时时间（有效值） (1.8s)
✓ TC-OS-TIMEOUT-002 - 订单设置 - 设置订单超时时间（边界值） (2.1s)
✓ TC-OS-AUTOCANCEL-001 - 订单设置 - 自动取消开关切换 (1.5s)
✓ TC-OS-SAVE-001 - 订单设置 - 保存完整配置 (3.2s)

Duration: 10.9s
```

---

## ⚠️ 前置条件

1. **环境准备**
   ```bash
   # 安装依赖
   make install-dev
   
   # 安装 Playwright 浏览器
   .venv/bin/playwright install chromium
   ```

2. **测试环境配置**
   ```bash
   # 设置环境变量
   export BASE_URL=http://localhost:5173
   export TEST_USERNAME=admin
   export TEST_PASSWORD=admin123
   ```

3. **Page Object 准备**
   - ✅ order-setting.page-object.yaml 已创建
   - 需要确保元素定位器与实际页面匹配

---

## 🔧 维护说明

### 元素定位器更新

如果页面元素变更，需要更新：
```yaml
# assets/page-objects/web/oms/order-setting.page-object.yaml
elements:
  element_name:
    locator_type: css  # 或 role/text/xpath
    locator_value: ".new-selector"
```

### 测试数据更新

测试数据在 YAML 的 `data` 部分定义，可以根据需要修改。

---

*文档版本：1.0*
*创建日期：2026-03-21*
*维护团队：QA Team*
