# OMS 退货原因设置 + SMS 优惠券 + 品牌管理 - UI 测试用例设计

> **创建日期**: 2026-03-21

---

## 1. 退货原因设置 (http://localhost:5173/#/oms/returnReason)

### 测试点

| ID | 测试点 | 优先级 |
|----|--------|--------|
| TP-RR-001 | 页面加载 | P0 |
| TP-RR-002 | 添加退货原因 | P0 |
| TP-RR-003 | 编辑退货原因 | P1 |
| TP-RR-004 | 删除退货原因 | P1 |
| TP-RR-005 | 退货原因列表展示 | P0 |

### 测试用例

```yaml
version: v4
id: TC-RR-ADD-001
title: 退货原因 - 添加退货原因
module: oms/return-reason
priority: P0
tags:
  - functional
  - return-reason
owner: qa-team
status: automated
description: 验证可以添加新的退货原因

execution:
  runner: playwright
  page: returnreason
  variables:
    reason_text: "商品质量问题测试"
  steps:
    - action: login
    - action: click
      target: return_reason_menu
    - action: click
      target: add_button
    - action: fill
      target: reason_input
      value: "{{reason_text}}"
    - action: click
      target: confirm_button
    - action: assert_visible
      target: success_message
```

---

## 2. 优惠券管理 (http://localhost:5173/#/sms/coupon)

### 测试点

| ID | 测试点 | 优先级 |
|----|--------|--------|
| TP-CN-001 | 页面加载 | P0 |
| TP-CN-002 | 添加优惠券 | P0 |
| TP-CN-003 | 优惠券列表展示 | P0 |
| TP-CN-004 | 优惠券搜索 | P1 |
| TP-CN-005 | 优惠券编辑 | P1 |
| TP-CN-006 | 优惠券删除 | P1 |
| TP-CN-007 | 优惠券发放 | P2 |

### 测试用例

```yaml
version: v4
id: TC-CN-ADD-001
title: 优惠券 - 添加优惠券
module: sms/coupon
priority: P0
tags:
  - functional
  - coupon
owner: qa-team
status: automated
description: 验证可以添加新的优惠券

execution:
  runner: playwright
  page: coupon
  variables:
    coupon_name: "测试优惠券"
    coupon_amount: "50"
  steps:
    - action: login
    - action: click
      target: coupon_menu
    - action: click
      target: add_coupon_button
    - action: fill
      target: coupon_name_input
      value: "{{coupon_name}}"
    - action: fill
      target: coupon_amount_input
      value: "{{coupon_amount}}"
    - action: click
      target: save_button
    - action: assert_visible
      target: success_message
```

---

## 3. 品牌管理 (http://localhost:5173/#/sms/brand)

### 测试点

| ID | 测试点 | 优先级 |
|----|--------|--------|
| TP-BR-001 | 页面加载 | P0 |
| TP-BR-002 | 添加品牌 | P0 |
| TP-BR-003 | 品牌列表展示 | P0 |
| TP-BR-004 | 品牌搜索 | P1 |
| TP-BR-005 | 品牌编辑 | P1 |
| TP-BR-006 | 品牌删除 | P1 |
| TP-BR-007 | 品牌显示状态切换 | P2 |

### 测试用例

```yaml
version: v4
id: TC-BR-ADD-001
title: 品牌管理 - 添加品牌
module: sms/brand
priority: P0
tags:
  - functional
  - brand
owner: qa-team
status: automated
description: 验证可以添加新的品牌

execution:
  runner: playwright
  page: brand
  variables:
    brand_name: "测试品牌"
  steps:
    - action: login
    - action: click
      target: brand_menu
    - action: click
      target: add_brand_button
    - action: fill
      target: brand_name_input
      value: "{{brand_name}}"
    - action: click
      target: save_button
    - action: assert_visible
      target: success_message
```

---

## 📊 测试执行汇总

### 执行所有测试

```bash
# 执行 OMS 模块测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "oms" \
  --headed \
  --video=on \
  --html=test-reports/oms-report.html

# 执行 SMS 模块测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "sms" \
  --headed \
  --video=on \
  --html=test-reports/sms-report.html

# 执行所有测试
.venv/bin/python -m pytest \
  runners/web-playwright-python/tests \
  -k "order-setting or return-apply or return-reason or coupon or brand" \
  --headed \
  --video=on \
  --screenshot=on \
  --html=test-reports/full-report.html
```

### 预期测试报告

```
Test Session Summary
====================

Total Tests: 35
Passed: 32
Failed: 2
Skipped: 1

By Module:
----------
OMS 订单设置：5/5 ✓
OMS 退货申请：8/8 ✓
OMS 退货原因：4/4 ✓
SMS 优惠券：10/9 ✓ (1 failed)
SMS 品牌管理：8/7 ✓ (1 failed, 1 skipped)

Duration: 2m 15s
```

---

## 📁 文件结构

```
assets/
├── page-objects/web/
│   ├── oms/
│   │   ├── order-setting.page-object.yaml
│   │   ├── return-apply.page-object.yaml
│   │   └── return-reason.page-object.yaml
│   └── sms/
│       ├── coupon.page-object.yaml
│       └── brand.page-object.yaml
└── test-cases/smoke/
    ├── oms/
    │   ├── order-setting-smoke.yaml
    │   ├── return-apply-smoke.yaml
    │   └── return-reason-smoke.yaml
    └── sms/
        ├── coupon-smoke.yaml
        └── brand-smoke.yaml

docs/testing/
├── oms-order-setting-test-cases.md
├── oms-return-apply-test-cases.md
└── sms-coupon-brand-test-cases.md
```

---

*文档版本：1.0*
*创建日期：2026-03-21*
