# Web Playwright Python 测试框架 - 功能与使用指南

> 项目位置：`/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python`  
> 文档版本：v4  
> 更新时间：2026-03-17

---

## 📊 功能总览

```
┌────────────────────────────────────────────────────────────────────┐
│                     Web Playwright Python 测试框架                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ✅ YAML 驱动测试        用 YAML 编写测试用例，无需 Python 代码          │
│  ✅ 页面对象模式         YAML + Python 双模式页面对象                  │
│  ✅ 数据驱动测试        一组用例，多组数据自动展开                    │
│  ✅ AI 生成用例支持     专用测试文件执行 AI 生成的用例                  │
│  ✅ Action 插件系统     可扩展的动作注册机制                         │
│  ✅ 智能定位器解析       4 种定位器类型 (role/text/css/placeholder)   │
│  ✅ 变量替换系统        {{variable}} 语法支持                        │
│  ✅ 自动失败取证        失败时自动保存截图/HTML/元数据                │
│  ✅ 视频录制            自动录制测试执行视频                         │
│  ✅ CLI 工具集          命令行创建/管理测试资产                       │
│  ✅ Schema 校验         JSON Schema 验证用例格式                      │
│  ✅ 多层级测试标记       contract/integration/e2e/smoke/generated    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 核心架构

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│  测试用例层 (Test Cases)                                     │
│  ├── tests/test_yaml_smoke.py (人类编写的 smoke 测试)          │
│  ├── tests/test_yaml_ai_generated.py (AI 生成的测试)          │
│  └── tests/test_*_smoke.py (原生 Python 测试)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  执行引擎层 (Runner)                                         │
│  ├── YamlExecutor        YAML 用例执行器                     │
│  ├── ACTION_REGISTRY     动作注册表                         │
│  ├── LocatorResolver     定位器解析器                       │
│  ├── VariableResolver    变量解析器                         │
│  └── DataExpander        数据驱动展开器                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  资产层 (Assets)                                             │
│  ├── assets/test-cases/smoke/*.yaml      (smoke 用例)        │
│  ├── assets/test-cases/ai-generated/*.yaml (AI 用例)         │
│  └── assets/page-objects/web/*.yaml      (页面对象)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 已实现功能详解

### 1️⃣ YAML 驱动测试

**功能描述**: 使用 YAML 文件编写测试用例，无需编写 Python 代码。

**用例结构**:
```yaml
version: v4
id: TC-PRODUCT-001
title: 商品列表页面加载
module: product
priority: P0
tags: [smoke, product]
description: 登录后进入商品列表页面

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

**执行方式**:
```bash
# 运行所有 YAML smoke 测试
python -m pytest tests/test_yaml_smoke.py -v

# 运行 AI 生成的测试
python -m pytest tests/test_yaml_ai_generated.py -v

# 运行模式切换
RUN_MODE=smoke python -m pytest tests/test_yaml_smoke.py -v
RUN_MODE=ai python -m pytest tests/test_yaml_smoke.py -v
RUN_MODE=all python -m pytest tests/test_yaml_smoke.py -v
```

---

### 2️⃣ 页面对象模式 (YAML + Python 双模式)

**功能描述**: 支持 YAML 和 Python 两种页面对象定义方式。

#### YAML 页面对象

**位置**: `assets/page-objects/web/*.page-object.yaml`

**示例** (`product.page-object.yaml`):
```yaml
page: product

elements:
  product_menu:
    locator_type: role
    role: menuitem
    locator_value: 商品
    description: 商品菜单

  product_list_title:
    locator_type: text
    locator_value: 商品列表

  search_input:
    locator_type: css
    locator_value: input[placeholder*="商品"]

  product_table:
    locator_type: css
    locator_value: .el-table
```

#### Python 页面对象

**位置**: `pages/*.py`

**示例** (`login_page.py`):
```python
from playwright.sync_api import Page, expect

class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, base_url: str) -> None:
        self.page.goto(base_url)

    def login(self, username: str, password: str) -> None:
        self.page.get_by_placeholder("请输入用户名").fill(username)
        self.page.get_by_placeholder("请输入密码").fill(password)
        with self.page.expect_response(
            lambda resp: "/admin/login" in resp.url,
            timeout=10000
        ):
            self.page.get_by_role("button", name="登录").click()

    def assert_login_success(self) -> None:
        expect(self.page.get_by_role("menuitem", name="首页").first).to_be_visible()
```

---

### 3️⃣ 数据驱动测试

**功能描述**: 一组测试用例，多组测试数据，自动展开执行。

**用例示例**:
```yaml
data:
  search_keyword:
    - 手机
    - 电脑
    - 图书

# 自动展开为 3 条用例:
# - search_keyword = "手机"
# - search_keyword = "电脑"
# - search_keyword = "图书"
```

**执行效果**:
```
test_yaml_smoke.py::test_yaml_smoke[chromium-验证商品搜索功能 -0] PASSED
test_yaml_smoke.py::test_yaml_smoke[chromium-验证商品搜索功能 -1] PASSED
test_yaml_smoke.py::test_yaml_smoke[chromium-验证商品搜索功能 -2] PASSED
```

---

### 4️⃣ Action 插件系统

**功能描述**: 可扩展的动作注册机制，支持自定义测试动作。

**已注册 Actions**:

| Action | 需要 Target | 功能 | 示例 |
|--------|-----------|------|------|
| `login` | ❌ | 执行登录流程 | `- action: login` |
| `click` | ✅ | 点击元素 | `- action: click, target: btn` |
| `fill` | ✅ | 填充输入框 | `- action: fill, target: input, value: 文本` |
| `wait_for` | ✅ | 等待元素可见 | `- action: wait_for, target: table` |
| `assert_visible` | ✅ | 断言元素可见 | `- action: assert_visible, target: table` |
| `assert_url` | ❌ | 断言 URL 包含 | `- action: assert_url, value: /product` |

**添加自定义 Action**:

1. 创建动作文件 `actions/hover.py`:
```python
def hover_action(page, locator, step, context, **kwargs):
    locator.hover()
```

2. 注册到 `runner/action_registry.py`:
```python
ACTION_DEFINITIONS = {
    # ... existing actions ...
    "hover": {"handler": hover_action, "requires_target": True},
}
```

---

### 5️⃣ 智能定位器解析

**功能描述**: 支持 4 种定位器类型，自动转换为 Playwright API。

| locator_type | Playwright API | 适用场景 |
|-------------|----------------|----------|
| `role` | `page.get_by_role(role, name)` | 语义化元素（按钮、菜单项） |
| `text` | `page.get_by_text()` | 文本内容匹配 |
| `css` | `page.locator()` | 复杂 CSS 选择器 |
| `placeholder` | `page.get_by_placeholder()` | 输入框 |

**示例**:
```yaml
# Role 定位器
login_btn:
  locator_type: role
  role: button
  locator_value: 登录

# Placeholder 定位器
username_input:
  locator_type: placeholder
  locator_value: 请输入用户名

# Text 定位器
page_title:
  locator_type: text
  locator_value: 商品列表

# CSS 定位器
table_body:
  locator_type: css
  locator_value: .el-table__body
```

---

### 6️⃣ 变量替换系统

**功能描述**: 使用 `{{variable}}` 语法在测试用例中引用变量。

**示例**:
```yaml
execution:
  variables:
    keyword: 手机
    expected_count: 10
  
  steps:
    - action: fill
      target: search_input
      value: "搜索：{{keyword}}"  # 替换为 "搜索：手机"
    
    - action: assert_url
      value: "/search?q={{keyword}}&count={{expected_count}}"
```

**数据驱动变量**:
```yaml
data:
  keyword:
    - 手机
    - 电脑

execution:
  variables:
    search_term: "{{keyword}}"  # 从 data 中引用

# 展开后:
# 用例 1: search_term = "手机"
# 用例 2: search_term = "电脑"
```

---

### 7️⃣ 自动失败取证

**功能描述**: 测试失败时自动保存截图、页面 HTML、元数据。

**取证内容**:
- 📸 全屏截图 (`failed.png`)
- 📄 页面 HTML (`page.html`)
- 📝 元数据 (`meta.txt` - URL, Title)

**存储位置**: `artifacts/{test_name}/`

**配置** (`conftest.py`):
```python
@pytest.fixture(autouse=True)
def capture_failure_artifacts(request, page: Page):
    yield
    if request.node.rep_call.failed:
        # 自动保存截图、HTML、元数据
        page.screenshot(path="failed.png")
        page.content().write_text("page.html")
```

---

### 8️⃣ 视频录制

**功能描述**: 自动录制测试执行视频，便于问题排查。

**配置** (`conftest.py`):
```python
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "record_video_dir": "test-results/videos",
        "record_video_size": {"width": 1440, "height": 900},
    }
```

**视频位置**: `test-results/videos/*.webm`

---

### 9️⃣ CLI 工具集

**功能描述**: 命令行工具创建和管理测试资产。

**工具位置**: `tools/asset_cli.py`

**可用命令**:

#### 创建页面对象
```bash
# 创建新的页面对象文件
python tools/asset_cli.py init-page-object --page checkout --description "结账页面"

# 添加元素
python tools/asset_cli.py add-page-element \
  --page checkout \
  --name submit_btn \
  --locator-type role \
  --locator-value "提交订单" \
  --role button \
  --description "提交订单按钮"

# 列出元素
python tools/asset_cli.py list-page-elements --page checkout
```

#### 创建测试用例
```bash
# 创建 smoke 测试用例
python tools/asset_cli.py init-test-case \
  --kind smoke \
  --page checkout \
  --id TC-CHECKOUT-001 \
  --title "结账流程测试" \
  --description "验证用户可以完成结账" \
  --requirement "结账功能" \
  --priority P0

# 同步测试用例步骤（根据页面对象自动推断）
python tools/asset_cli.py sync-test-case \
  --file assets/test-cases/smoke/checkout-smoke.yaml
```

---

### 🔟 Schema 校验

**功能描述**: 使用 JSON Schema 验证测试用例格式。

**Schema 文件**: `schemas/yaml_testcase.schema.json`

**校验规则**:
- ✅ 必填字段：`version`, `id`, `title`, `module`, `execution`
- ✅ `execution` 必填：`runner`, `page`, `steps`
- ✅ `steps[].action` 必填
- ✅ 类型校验（string, array, object）

**自动校验时机**:
- 加载 YAML 文件时
- CLI 创建/修改用例时
- 测试执行前

---

### 1️⃣1️⃣ 多层级测试标记

**功能描述**: 使用 pytest markers 分类测试。

**标记类型** (`pytest.ini`):
```ini
markers =
    contract:    稳定的契约/Schema/不变量检查
    integration: 跨模块集成测试
    e2e:         端到端浏览器测试
    smoke:       人工维护的冒烟测试
    generated:   AI 生成的测试
```

**使用示例**:
```python
# tests/test_yaml_smoke.py
pytestmark = [pytest.mark.e2e, pytest.mark.smoke]

# tests/test_asset_contracts.py
pytestmark = [pytest.mark.contract]
```

**运行特定标记**:
```bash
# 只运行 smoke 测试
python -m pytest -m smoke -v

# 只运行 AI 生成的测试
python -m pytest -m generated -v

# 排除 contract 测试
python -m pytest -m "not contract" -v
```

---

## 📁 项目结构

```
web-playwright-python/
├── conftest.py                      # pytest 配置 (fixtures, 失败取证，视频录制)
├── pytest.ini                       # pytest 配置 (markers, 测试路径)
├── requirements.txt                 # Python 依赖
│
├── pages/                           # Python 页面对象
│   ├── login_page.py                # 登录页
│   ├── product_page.py              # 商品页
│   └── order_page.py                # 订单页
│
├── actions/                         # Action 插件
│   ├── click.py                     # 点击动作
│   ├── fill.py                      # 填充动作
│   ├── wait_for.py                  # 等待动作
│   ├── assert_visible.py            # 可见性断言
│   ├── assert_url.py                # URL 断言
│   └── login.py                     # 登录动作
│
├── runner/                          # 执行引擎核心
│   ├── paths.py                     # 路径常量
│   ├── yaml_executor.py             # YAML 执行器 ⭐
│   ├── action_registry.py           # 动作注册表
│   ├── locator_resolver.py          # 定位器解析器
│   ├── variable_resolver.py         # 变量解析器
│   ├── data_expander.py             # 数据驱动展开器
│   ├── test_case_loader.py          # 测试用例加载器
│   ├── asset_toolkit.py             # 资产工具集 (CLI 后端)
│   ├── yaml_loader.py               # YAML 加载器
│   ├── schema_validator.py          # Schema 校验器
│   └── page_object_validator.py     # 页面对象校验器
│
├── schemas/                         # JSON Schema 定义
│   └── yaml_testcase.schema.json
│
├── tests/                           # 测试入口
│   ├── test_yaml_smoke.py           # YAML smoke 测试
│   ├── test_yaml_ai_generated.py    # AI 生成测试
│   ├── test_login_smoke.py          # Python 登录测试
│   ├── test_product_smoke.py        # Python 商品测试
│   ├── test_product_quick.py        # 快速商品测试
│   └── test_order_smoke.py          # Python 订单测试
│
├── tools/                           # CLI 工具
│   └── asset_cli.py                 # 测试资产管理 CLI
│
└── assets/ (符号链接)                # 测试资产
    ├── test-cases/
    │   ├── smoke/                   # 人类编写的 smoke 用例
    │   ├── ai-generated/            # AI 生成的用例
    │   └── regression/              # 回归测试用例
    ├── page-objects/
    │   ├── web/                     # Web 页面对象
    │   └── mobile/                  # Mobile 页面对象
    ├── business-flows/              # 业务流程定义 (空)
    ├── risk-rules/                  # 风险规则 (空)
    ├── tags/                        # 标签定义 (空)
    ├── component-objects/           # 组件对象
    └── test-data-templates/         # 测试数据模板
```

---

## 🚀 快速开始

### 环境准备

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 配置环境变量

创建 `.env` 文件：
```bash
BASE_URL=http://localhost:5173/login#/login
TEST_USERNAME=admin
TEST_PASSWORD=macro123
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行 smoke 测试
python -m pytest tests/test_yaml_smoke.py -v

# 运行 AI 生成测试
python -m pytest tests/test_yaml_ai_generated.py -v

# 运行原生 Python 测试
python -m pytest tests/test_login_smoke.py -v

# 带浏览器界面运行（调试用）
python -m pytest tests/test_yaml_smoke.py --headed -v

# 生成 Allure 报告
python -m pytest tests/ --alluredir=./allure-results
allure serve ./allure-results
```

---

## 📝 使用场景

### 场景 1: 添加新的 Smoke 测试

**步骤 1**: 确认页面对象已存在
```bash
# 检查页面对象
cat assets/page-objects/web/product.page-object.yaml
```

**步骤 2**: 创建测试用例
```bash
python tools/asset_cli.py init-test-case \
  --kind smoke \
  --page product \
  --id TC-PRODUCT-002 \
  --title "商品搜索测试" \
  --description "验证商品搜索功能" \
  --requirement "商品搜索" \
  --priority P1
```

**步骤 3**: 编辑生成的 YAML 文件
```yaml
# assets/test-cases/smoke/product-smoke.yaml
execution:
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: fill
      target: search_input
      value: "手机"
    - action: click
      target: search_button
    - action: assert_visible
      target: product_table
```

**步骤 4**: 运行测试
```bash
python -m pytest tests/test_yaml_smoke.py -v
```

---

### 场景 2: 添加新的页面对象

**步骤 1**: 创建页面对象
```bash
python tools/asset_cli.py init-page-object \
  --page checkout \
  --description "结账页面"
```

**步骤 2**: 添加元素
```bash
python tools/asset_cli.py add-page-element \
  --page checkout \
  --name submit_btn \
  --locator-type role \
  --locator-value "提交订单" \
  --role button

python tools/asset_cli.py add-page-element \
  --page checkout \
  --name total_amount \
  --locator-type css \
  --locator-value ".total-amount" \
  --description "订单总金额"
```

**步骤 3**: 验证元素
```bash
python tools/asset_cli.py list-page-elements --page checkout
```

---

### 场景 3: 数据驱动测试

**用例文件**:
```yaml
# TC-SEARCH-001.yaml
data:
  keyword:
    - 手机
    - 电脑
    - 图书
  expected_min_count:
    - 1
    - 1
    - 1

execution:
  variables:
    search_term: "{{keyword}}"
  
  steps:
    - action: login
    - action: click
      target: product_menu
    - action: fill
      target: search_input
      value: "{{search_term}}"
    - action: click
      target: search_button
    - action: assert_visible
      target: product_table
```

**执行结果**:
```
test_yaml_smoke.py::test_yaml_smoke[chromium-商品搜索 -0] PASSED  # keyword=手机
test_yaml_smoke.py::test_yaml_smoke[chromium-商品搜索 -1] PASSED  # keyword=电脑
test_yaml_smoke.py::test_yaml_smoke[chromium-商品搜索 -2] PASSED  # keyword=图书
```

---

### 场景 4: 调试失败的测试

**步骤 1**: 带界面运行
```bash
python -m pytest tests/test_yaml_smoke.py::test_yaml_smoke[chromium-商品列表页面加载] --headed
```

**步骤 2**: 查看失败取证
```bash
# 截图
ls artifacts/test_yaml_smoke_chromium_商品列表页面加载/failed.png

# 页面 HTML
cat artifacts/test_yaml_smoke_chromium_商品列表页面加载/page.html

# 元数据
cat artifacts/test_yaml_smoke_chromium_商品列表页面加载/meta.txt
```

**步骤 3**: 查看录制的视频
```bash
ls test-results/videos/
```

---

## 🔧 高级功能

### 1. 自定义运行模式

```bash
# 只运行 smoke 用例
RUN_MODE=smoke python -m pytest tests/test_yaml_smoke.py -v

# 只运行 AI 生成用例
RUN_MODE=ai python -m pytest tests/test_yaml_smoke.py -v

# 运行所有用例
RUN_MODE=all python -m pytest tests/test_yaml_smoke.py -v
```

### 2. 运行单个测试用例

```bash
# 通过用例 ID 过滤
TEST_CASE_ID=TC-PRODUCT-001 python -m pytest tests/test_yaml_smoke.py -v

# 通过文件路径运行
TEST_CASE_PATH=assets/test-cases/smoke/product-smoke.yaml \
  python -m pytest tests/test_yaml_smoke.py -v
```

### 3. 并行执行

```bash
# 使用 pytest-xdist 并行执行
python -m pytest tests/test_yaml_smoke.py -n 4 -v
```

---

## 📊 测试资产统计

### 测试用例

| 类型 | 数量 | 位置 |
|------|------|------|
| Smoke | 4 | `assets/test-cases/smoke/` |
| AI Generated | 1 | `assets/test-cases/ai-generated/` |
| Regression | 3 (空) | `assets/test-cases/regression/` |

### 页面对象

| 页面 | 位置 |
|------|------|
| login | `assets/page-objects/web/login.page-object.yaml` |
| home | `assets/page-objects/web/home.page-object.yaml` |
| product | `assets/page-objects/web/product.page-object.yaml` |
| order | `assets/page-objects/web/order.page-object.yaml` |
| permission | `assets/page-objects/web/permission.page-object.yaml` |
| payment | `assets/page-objects/web/payment.page-object.yaml` |
| profile | `assets/page-objects/web/profile.page-object.yaml` |

### Action 插件

| Action | 文件 |
|--------|------|
| login | `actions/login.py` |
| click | `actions/click.py` |
| fill | `actions/fill.py` |
| wait_for | `actions/wait_for.py` |
| assert_visible | `actions/assert_visible.py` |
| assert_url | `actions/assert_url.py` |

---

## 🐛 常见问题

### Q1: `Element not found in page object`

**原因**: 测试用例中的 `target` 在页面对象中不存在

**解决**:
```bash
# 检查页面对象中的元素
python tools/asset_cli.py list-page-elements --page product

# 添加缺失的元素
python tools/asset_cli.py add-page-element --page product --name xxx ...
```

---

### Q2: `Timeout 30000ms exceeded`

**原因**: 元素定位器无法匹配到页面上的元素

**解决**:
1. 用浏览器开发者工具验证选择器
2. 检查 `locator_type` 是否正确
3. 添加 `wait_for` 步骤等待元素加载

---

### Q3: 变量未解析 `{{xxx}}` 保持原样

**原因**: 变量未在 `variables` 或 `_data` 中定义

**解决**:
```yaml
execution:
  variables:
    keyword: 手机   # 确保变量已定义
```

---

## 📚 相关文档

- `PROJECT_DOCS.md` - 详细技术文档（字段说明、代码逻辑）
- `schemas/yaml_testcase.schema.json` - 测试用例 Schema 定义
- `pytest.ini` - pytest 配置说明

---

*文档生成时间：2026-03-17*  
*框架版本：v4*
