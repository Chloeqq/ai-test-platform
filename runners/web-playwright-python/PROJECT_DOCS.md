# Web Playwright Python 测试框架文档

> 项目路径：`/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python`

---

## 📁 项目结构

```
web-playwright-python/
├── conftest.py                    # pytest 配置文件（fixtures）
├── pytest.ini                     # pytest 配置
├── requirements.txt               # Python 依赖
├── pages/                         # 页面对象类（Python）
│   ├── login_page.py
│   ├── product_page.py
│   └── order_page.py
├── actions/                       # 动作插件（Action Plugins）
│   ├── click.py
│   ├── fill.py
│   ├── wait_for.py
│   ├── assert_visible.py
│   └── login.py
├── runner/                        # YAML 测试执行器核心
│   ├── paths.py                   # 路径常量定义
│   ├── yaml_loader.py             # YAML 文件加载
│   ├── yaml_executor.py           # 测试用例执行器
│   ├── action_registry.py         # 动作注册表
│   ├── locator_resolver.py        # 定位器解析器
│   ├── variable_resolver.py       # 变量解析器
│   ├── data_expander.py           # 数据驱动用例展开
│   └── schema_validator.py        # JSON Schema 校验
├── schemas/                       # JSON Schema 定义
│   └── yaml_testcase.schema.json
├── tests/                         # pytest 测试文件
│   ├── test_yaml_smoke.py         # YAML 用例执行入口
│   ├── test_login_smoke.py        # 原生 Python 测试
│   └── ...
└── assets/                        # 运行时资源（符号链接）
    ├── test-cases/                # 测试用例 YAML
    └── page-objects/              # 页面对象 YAML
```

---

## 🏗️ 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    测试用例层 (YAML)                         │
│  assets/test-cases/smoke/*.yaml                             │
│  - 测试步骤定义                                               │
│  - 数据驱动配置                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    执行引擎层 (Runner)                        │
│  runner/yaml_executor.py                                    │
│  - 加载 YAML 用例                                             │
│  - 解析页面对象                                               │
│  - 调度 Action 插件                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    动作插件层 (Actions)                       │
│  actions/*.py                                               │
│  - click, fill, wait_for, assert_visible, login             │
│  - 调用 Playwright API                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 执行流程

```
pytest 启动
    │
    ├─→ conftest.py 初始化 fixtures
    │   ├─ base_url (从 .env 读取)
    │   ├─ test_username (从 .env 读取)
    │   └─ test_password (从 .env 读取)
    │
    └─→ 执行 tests/test_yaml_smoke.py
            │
            ├─ load_yaml_files() 加载所有 YAML 用例
            │   └─ validate_testcase_schema() 校验格式
            │
            ├─ data_expander.expand_test_case() 展开数据驱动用例
            │   └─ data: {keyword: [手机，电脑]} → 2 条用例
            │
            └─ YamlExecutor.execute(test_case)
                    │
                    ├─ _load_page_object(page_name)
                    │   └─ 加载 assets/page-objects/web/{page}.page-object.yaml
                    │
                    ├─ _build_context(variables, _data)
                    │   └─ 合并变量和数据上下文
                    │
                    └─ for step in steps:
                            │
                            ├─ resolve_locator(page, element)
                            │   ├─ locator_type: placeholder → page.get_by_placeholder()
                            │   ├─ locator_type: text → page.get_by_text()
                            │   ├─ locator_type: css → page.locator()
                            │   └─ locator_type: role → page.get_by_role()
                            │
                            └─ ACTION_REGISTRY[action](...)
                                ├─ click_action → locator.click()
                                ├─ fill_action → locator.fill(value)
                                ├─ wait_for_action → locator.wait_for(state="visible")
                                ├─ assert_visible_action → expect(locator).to_be_visible()
                                └─ login_action → LoginPage.login()
```

---

## 🛠️ 资产工具链

当前已提供一个资产 CLI，用于减少手工维护 YAML / page object：

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py --help
```

### 初始化 page object

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  init-page-object \
  --page catalog \
  --description "商品目录页"
```

### 给 page object 增加元素

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  add-page-element \
  --page catalog \
  --name catalog_menu \
  --locator-type role \
  --role menuitem \
  --locator-value 商品目录
```

### 列出页面元素

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  list-page-elements \
  --page product
```

### 生成标准 YAML 用例模板

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  init-test-case \
  --kind smoke \
  --page product \
  --id tc-product-NEW-001 \
  --title "商品页面加载" \
  --description "验证商品页面可以正常打开" \
  --requirement "商品页面展示"
```

### 同步已有 YAML 用例步骤

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  sync-test-case \
  --file assets/test-cases/smoke/product-smoke.yaml
```

### 一次性生成 page object + smoke case 骨架

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  scaffold-assets \
  --page catalog \
  --title "商品目录" \
  --requirement "商品目录页面展示" \
  --template catalog
```

也可以列出内置模板：

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  list-scaffold-templates
```

查看模板说明：

```bash
PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  list-scaffold-templates --verbose

PYTHONPATH=runners/web-playwright-python .venv/bin/python runners/web-playwright-python/tools/asset_cli.py \
  describe-scaffold-template --template catalog
```

说明：

- `init-test-case` 会尝试根据 page object 自动推断 `*_menu` 和 `*_title/*_table/*_list` 目标
- `sync-test-case` 会重写 `execution.steps`，但保留标题、描述、标签、requirement 等元数据
- `scaffold-assets` 会同时创建 page object 和 smoke case；`elements-file` 支持 YAML/JSON 数组
- `--template` 支持复用内置模板，当前提供 `catalog`、`list`、`detail`
- `list-scaffold-templates --verbose` 会输出模板类型和摘要
- `describe-scaffold-template` 会输出推荐标题、推荐需求和元素明细
- `elements[].smoke_role` 可选 `menu` / `assert`，用于显式指定 smoke 用例的点击目标和断言目标
- `--template` 和 `--elements-file` 可以同时使用，后者会在模板基础上追加或覆盖同名元素
- 如果推断失败，需要显式传 `--menu-target` / `--assert-target`
- 工具生成出的资产会立即经过 schema 校验

---

## 🧾 失败留痕

当前 Python Runner 在用例失败时会自动保存：

- 失败截图：`failed.png`
- 页面 HTML：`page.html`
- 页面信息：`meta.txt`
- AI 失败分析：`analysis.txt`
- AI 修复建议：`suggestion.json`
- 如果通过 `pytest --alluredir <dir>` 启用 Allure，还会自动把这些失败产物附加到 Allure 报告

`meta.txt` 中包含：

- `NodeID`
- `CapturedAt`
- `URL`
- `Title`
- 截图路径
- HTML 路径

`analysis.txt` 中包含：

- `Summary`
- `Failure Category`
- `Likely Cause`
- `Risk Level`
- `Recommended Action`
- `Confidence`
- `Evidence Used`
- 一份完整 JSON 结果，便于后续平台读取

`suggestion.json` 中包含：

- `summary`
- `advice_type`
- `target`
- `suggestion`
- `confidence`
- `fix_candidates`

如果要进入人工修复阶段，当前支持这条只读到可确认写入的链路：

```text
suggestion.json
  -> patch_generator.py
  -> diff 预览
  -> apply_patch.py --confirm APPLY
  -> 备份原 YAML
  -> 写入 ai-generated YAML
  -> rollback.py --confirm ROLLBACK
```

当前约束：

- 只允许修改 `assets/test-cases/ai-generated`
- 明确拒绝修改稳定 smoke 用例
- 只能替换成现有 page-object target
- 预览后的 YAML 如果被人改过，拒绝继续 apply
- rollback 只恢复最近一次人工确认后写入的版本

推荐统一 CLI：

```bash
python /Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/apply_fix.py preview \
  --case /Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/ai-generated/tc-product-SEARCH-001.yaml \
  --suggestion /path/to/suggestion.json \
  --output /tmp/patch-plan.json

python /Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/apply_fix.py apply \
  --plan /tmp/patch-plan.json \
  --confirm APPLY

python /Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/apply_fix.py rollback \
  --receipt /path/to/receipt.json \
  --confirm ROLLBACK
```

当前约束：

- 只输出建议
- 不自动修改 YAML
- `target` 只能来自现有 page-object
- `confidence < 0.5` 时不输出实际建议

默认目录：

- 失败产物目录：`runners/web-playwright-python/artifacts/`
- 视频目录：`runners/web-playwright-python/test-results/videos/`

Allure 使用示例：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python
python -m pytest tests/test_yaml_ai_generated.py --alluredir=allure-results
```

说明：

- Allure 接入不改变现有执行逻辑
- 只有在安装了 `allure-pytest` 且运行时传入 `--alluredir` 时，才会生成 Allure 结果
- 当前会自动补充 Allure 元数据：
  - 标题：YAML `title`
  - `feature`：页面名 `execution.page`
  - `story` / `case_id` 标签：YAML `id`
  - `tag`：YAML `tags`
- 失败时会自动附加：
  - `failed.png`
  - `page.html`
  - `meta.txt`
  - `analysis.txt`
- 同时会额外附加一份 `ai-failure-analysis` 文本附件，直接展示 AI 失败分析内容
- 同时会额外附加一份 `failure-context` 文本附件，直接展示 URL / Title / 产物路径等失败上下文
- 如果失败视频在 teardown 阶段已生成，还会额外附加 `failure-video`

推荐统一入口：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make test-e2e-generated-allure
make allure-summary
make allure-generate
make allure-open
```

如果你希望“执行完测试后直接打开报告”，可以直接用：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make test-open-report
make test-e2e-generated-open-report
```

也支持：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make test-e2e-smoke-open-report
make test-e2e-open-report
```

其中 `make test-open-report` 默认等价于当前推荐入口：

```bash
make test-e2e-smoke-open-report
```

如果你当前就在 runner 目录下，也可以直接用本地入口：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python
make test-open-report
make test-e2e-generated-open-report
```

也支持：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python
make test-e2e-smoke-open-report
make test-e2e-open-report
```

也可以查看当前 Allure CLI 和目录配置：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make allure-info
```

推荐顺序：

1. `make test-e2e-generated-allure`
2. `make allure-summary`
3. `make allure-generate`
4. `make allure-open`

说明：

- `make allure-summary` 会优先读取每个失败目录下的 `evidence_manifest.json`（`analysis_files` / `suggestion_files`），并在缺失时回退到 `analysis.txt` 扫描，生成：
  - `runners/web-playwright-python/artifacts/report_summary.txt`

## 📊 汇总报告

当前提供一个离线汇总脚本，用于从失败产物目录汇总生成整体分析报告（manifest-first，兼容 legacy analysis 扫描）：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
python runners/web-playwright-python/tools/report_summary.py
```

默认输出：

- `runners/web-playwright-python/artifacts/report_summary.txt`

也可以指定目录和输出文件：

```bash
python runners/web-playwright-python/tools/report_summary.py \
  --artifacts-dir runners/web-playwright-python/artifacts \
  --output runners/web-playwright-python/artifacts/report_summary.txt
```

汇总内容包括：

- 已发现分析文件总数（manifest + legacy）
- 失败类别统计
- 风险等级统计
- 每个失败用例的摘要、原因、建议、置信度和来源文件路径

失败目录结构示例：

```text
runners/web-playwright-python/artifacts/
└── tests_test_yaml_ai_generated_py__test_yaml_ai_generated[Verify_Product_Search_Function]/
    ├── failed.png
    ├── page.html
    ├── meta.txt
    ├── evidence_manifest.json
    └── analysis.txt
```

说明：

- 每个失败用例会生成一个独立目录
- 目录名来自 pytest `nodeid` 的安全化结果
- `evidence_manifest.json` 用于统一描述截图/HTML/analysis/suggestion/execution_record/video 等证据文件
- `analysis.txt` 会在截图、HTML、meta 文件生成后自动产出

可通过环境变量覆盖：

```bash
export PLAYWRIGHT_ARTIFACTS_DIR=custom-artifacts
export PLAYWRIGHT_VIDEO_DIR=custom-videos
```

---

## 📋 YAML 测试用例字段详解

### 完整示例

```yaml
version: v4                          # ① 用例格式版本
id: tc-product-001                   # ② 用例唯一标识
title: 商品列表页面加载                # ③ 用例标题
module: product                      # ④ 所属模块
priority: P0                         # ⑤ 优先级 (P0/P1/P2/P3)
tags:                                # ⑥ 标签列表
  - smoke
  - product
owner: qa-team                       # ⑦ 负责人
status: automated                    # ⑧ 状态 (automated/manual)
description: 登录后进入商品列表页面     # ⑨ 用例描述
requirement:                         # ⑩ 关联需求
  - 商品列表展示
data: {}                             # ⑪ 测试数据（数据驱动用）
execution:                           # ⑫ 执行配置
  runner: playwright                 # ⑬ 执行引擎
  page: product                      # ⑭ 页面对象文件名（不含扩展名）
  variables:                         # ⑮ 变量定义
    keyword: 手机
  steps:                             # ⑯ 步骤列表
    - action: login                  # ⑰ 动作类型
      target: null                   # ⑱ 目标元素（可选）
      value: null                    # ⑲ 动作值（可选）
    - action: click
      target: product_menu
    - action: wait_for
      target: product_list_title
    - action: assert_visible
      target: product_list_title
```

---

### 字段详细说明

| 字段 | 层级 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|------|
| `version` | 根 | string | ✅ | 用例格式版本号，用于兼容性管理 | `v4` |
| `id` | 根 | string | ✅ | 用例唯一标识符，命名规范：`TC-{MODULE}-{NUM}` | `TC-PRODUCT-001` |
| `title` | 根 | string | ✅ | 用例标题，简洁描述测试目的 | `商品列表页面加载` |
| `module` | 根 | string | ✅ | 所属业务模块，对应页面对象目录 | `product`, `order`, `auth` |
| `priority` | 根 | string | ❌ | 优先级，P0 最高 | `P0`, `P1`, `P2` |
| `tags` | 根 | array | ❌ | 标签列表，用于分类和筛选 | `["smoke", "product"]` |
| `owner` | 根 | string | ❌ | 用例负责人/团队 | `qa-team` |
| `status` | 根 | string | ❌ | 用例状态 | `automated`, `manual`, `deprecated` |
| `description` | 根 | string | ❌ | 详细描述，说明测试场景 | `验证管理员可以成功登录系统` |
| `requirement` | 根 | array | ❌ | 关联的需求列表 | `["管理员登录功能"]` |
| `data` | 根 | object | ❌ | 数据驱动测试数据，支持多组数据展开 | 见下方示例 |
| `execution` | 根 | object | ✅ | 执行配置块 | - |
| `execution.runner` | execution | string | ✅ | 执行引擎类型 | `playwright` |
| `execution.page` | execution | string | ✅ | 页面对象文件名（不含 `.page-object.yaml`） | `product`, `login` |
| `execution.variables` | execution | object | ❌ | 变量定义，支持 `{{var}}` 引用 | `{"keyword": "手机"}` |
| `execution.steps` | execution | array | ✅ | 步骤列表，按顺序执行 | - |
| `steps[].action` | step | string | ✅ | 动作类型，必须在 `ACTION_REGISTRY` 中注册 | `click`, `fill`, `login` |
| `steps[].target` | step | string/null | ❌ | 目标元素名称，对应页面对象中的 key | `product_menu` |
| `steps[].value` | step | any/null | ❌ | 动作值，fill 动作为输入文本 | `{{keyword}}` |

---

### 数据驱动示例

```yaml
# 单条用例，多组数据
data:
  search_keyword:
    - 手机
    - 电脑
    - 图书

# 展开后生成 3 条用例:
# tc-product-SEARCH-001-0: search_keyword = "手机"
# tc-product-SEARCH-001-1: search_keyword = "电脑"
# tc-product-SEARCH-001-2: search_keyword = "图书"
```

```yaml
# 多参数组合
data:
  username:
    - admin
    - user1
  password:
    - pass123
    - pass456

# 展开后生成 2 条用例:
# - username="admin", password="pass123"
# - username="user1", password="pass456"
```

---

## 📄 YAML 页面对象字段详解

### 完整示例

```yaml
page: product                          # ① 页面标识

elements:                              # ② 元素定义块
  product_menu:                        # ③ 元素名称（测试用例中 target 引用）
    locator_type: role                 # ④ 定位器类型
    role: menuitem                     # ⑤ role 定位器专用
    locator_value: 商品                 # ⑥ 定位器值
    description: 商品菜单               # ⑦ 元素描述（可选）
  
  product_list_title:
    locator_type: text
    locator_value: 商品列表
  
  search_input:
    locator_type: css
    locator_value: input[placeholder*="商品"]
  
  search_button:
    locator_type: role
    role: button
    locator_value: 查询
  
  product_table:
    locator_type: css
    locator_value: .el-table
```

---

### 字段详细说明

| 字段 | 层级 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|------|
| `page` | 根 | string | ✅ | 页面标识，与 `execution.page` 对应 | `product`, `login` |
| `elements` | 根 | object | ✅ | 元素定义集合 | - |
| `elements.{name}` | elements | object | ✅ | 元素名称，测试用例中 `target` 引用的值 | `product_menu` |
| `locator_type` | element | string | ✅ | 定位器类型，决定使用哪个 Playwright API | `role`, `text`, `css`, `placeholder` |
| `locator_value` | element | string | ✅ | 定位器值，具体的选择器内容 | `商品`, `.el-table` |
| `role` | element | string | 条件 | 当 `locator_type: role` 时必填 | `button`, `menuitem`, `textbox` |
| `description` | element | string | ❌ | 元素描述，便于理解用途 | `商品菜单（父菜单，需要展开）` |

---

### 定位器类型对照表

| locator_type | 对应 Playwright API | 适用场景 | 示例 |
|--------------|---------------------|----------|------|
| `role` | `page.get_by_role(role, name)` | 语义化元素（按钮、输入框、菜单项） | `role: button, locator_value: 登录` |
| `text` | `page.get_by_text()` | 文本内容匹配 | `locator_value: 商品列表` |
| `css` | `page.locator()` | 复杂 CSS 选择器 | `locator_value: .el-table__body` |
| `placeholder` | `page.get_by_placeholder()` | 输入框（通过占位符） | `locator_value: 请输入用户名` |

---

## 🔌 Action 插件说明

### 注册表 (`runner/action_registry.py`)

```python
ACTION_REGISTRY = {
    "click": click_action,
    "fill": fill_action,
    "wait_for": wait_for_action,
    "assert_visible": assert_visible_action,
    "login": login_action,
}
```

### 动作签名

所有 Action 插件遵循统一签名：

```python
def xxx_action(
    page: Page,           # Playwright Page 对象
    locator: Locator,     # 已解析的定位器（可能为 None）
    step: dict,           # 当前步骤的完整配置
    context: dict,        # 变量上下文
    **kwargs              # 额外参数（username, password, base_url 等）
) -> None:
    pass
```

---

### 各 Action 详解

#### 1. `click`

```yaml
- action: click
  target: product_menu
```

**功能**: 点击元素

**参数**:
- `target`: 元素名称（必填）

**实现**: `locator.click()`

---

#### 2. `fill`

```yaml
- action: fill
  target: search_input
  value: "{{keyword}}"
```

**功能**: 填充输入框

**参数**:
- `target`: 元素名称（必填）
- `value`: 要填充的文本，支持 `{{var}}` 变量（必填）

**实现**: `locator.fill(value)`

---

#### 3. `wait_for`

```yaml
- action: wait_for
  target: product_table
```

**功能**: 等待元素可见

**参数**:
- `target`: 元素名称（必填）

**实现**: `locator.wait_for(state="visible")`

---

#### 4. `assert_visible`

```yaml
- action: assert_visible
  target: product_table
```

**功能**: 断言元素可见

**参数**:
- `target`: 元素名称（必填）

**实现**: `expect(locator).to_be_visible(timeout=10000)`

---

#### 5. `login`

```yaml
- action: login
```

**功能**: 执行登录流程（特殊动作，不需要 target）

**参数**: 无（从 fixtures 获取 username, password, base_url）

**实现**:
1. 打开登录页面
2. 填充用户名和密码
3. 点击登录按钮
4. 等待登录 API 响应
5. 断言登录成功（首页菜单可见）

---

## 🛠️ 核心模块代码逻辑

### 1. `conftest.py` - Pytest Fixtures

```python
# 会话级 fixture，只初始化一次
@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:5173/login#/login")

@pytest.fixture(scope="session")
def test_username() -> str:
    return os.getenv("TEST_USERNAME", "admin")

@pytest.fixture(scope="session")
def test_password() -> str:
    return os.getenv("TEST_PASSWORD", "macro123")

# 每个测试自动执行，清除认证状态
@pytest.fixture(autouse=True)
def clear_auth_state(page: Page, context, base_url: str):
    context.clear_cookies()           # 清除 cookies
    page.goto(base_url)               # 打开登录页
    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
```

---

### 2. `runner/yaml_loader.py` - YAML 加载

```python
def load_yaml_files(dir_path: Path) -> list[Any]:
    cases = []
    for file_path in dir_path.iterdir():
        if file_path.suffix not in [".yaml", ".yml"]:
            continue
        
        parsed = load_yaml_file(file_path)
        
        # 跳过空 YAML 文件
        if parsed is None:
            print(f"⚠️ Skip empty YAML: {file_path}")
            continue
        
        # JSON Schema 校验
        validate_testcase_schema(parsed)
        
        cases.append(parsed)
    
    return cases
```

---

### 3. `runner/data_expander.py` - 数据驱动展开

```python
def expand_test_case(test_case: dict) -> list[dict]:
    data = test_case.get("data")
    
    # 没有 data 字段，返回原用例
    if not data:
        return [test_case]
    
    # 笛卡尔积展开
    keys = list(data.keys())
    values = list(data.values())
    cases = []
    
    for i in range(len(values[0])):  # 假设所有数组长度相同
        new_case = deepcopy(test_case)
        new_case["_data"] = {}
        
        for key in keys:
            new_case["_data"][key] = data[key][i]
        
        cases.append(new_case)
    
    return cases
```

---

### 4. `runner/yaml_executor.py` - 执行器核心

```python
def execute(self, test_case: dict) -> None:
    execution = test_case.get("execution")
    page_name = execution.get("page")
    steps = execution.get("steps", [])
    variables = execution.get("variables", {})
    data_context = test_case.get("_data", {})
    
    # 1. 构建变量上下文
    resolved_context = self._build_context(variables, data_context)
    
    # 2. 加载页面对象
    page_object = self._load_page_object(page_name)
    
    # 3. 执行步骤
    for step in steps:
        self._execute_step(step, page_object, resolved_context)
```

---

### 5. `runner/locator_resolver.py` - 定位器解析

```python
def resolve_locator(page: Page, element: dict):
    locator_type = element.get("locator_type")
    locator_value = element.get("locator_value")
    role = element.get("role")
    
    if locator_type == "placeholder":
        return page.get_by_placeholder(locator_value)
    
    if locator_type == "text":
        return page.get_by_text(locator_value)
    
    if locator_type == "css":
        return page.locator(locator_value)
    
    if locator_type == "role":
        if not role:
            raise ValueError("role locator requires role field")
        return page.get_by_role(role, name=locator_value)
    
    raise ValueError(f"Unsupported locator_type: {locator_type}")
```

---

### 6. `runner/variable_resolver.py` - 变量解析

```python
VAR_PATTERN = re.compile(r"\{\{(.*?)\}\}")

def resolve_variables(value: str, context: dict):
    if not isinstance(value, str):
        return value
    
    matches = VAR_PATTERN.findall(value)
    
    for m in matches:
        key = m.strip()
        if key not in context:
            continue
        value = value.replace(f"{{{{{key}}}}}", str(context[key]))
    
    return value
```

**示例**:
- 输入：`"搜索：{{keyword}}"`
- 上下文：`{"keyword": "手机"}`
- 输出：`"搜索：手机"`

---

## 📊 测试用例执行示例

### 命令

```bash
# 运行所有 smoke 测试
python -m pytest tests/test_yaml_smoke.py -v

# 运行特定测试（通过 ID 过滤）
python -m pytest tests/test_yaml_smoke.py -k "login" -v

# 运行并生成 Allure 报告
python -m pytest tests/test_yaml_smoke.py --alluredir=./allure-results
allure serve ./allure-results
```

### 输出示例

```
tests/test_yaml_smoke.py::test_yaml_smoke[chromium-管理员登录验证] PASSED
tests/test_yaml_smoke.py::test_yaml_smoke[chromium-商品列表页面加载] PASSED
tests/test_yaml_smoke.py::test_yaml_smoke[chromium-订单列表页面加载] PASSED
tests/test_yaml_smoke.py::test_yaml_smoke[chromium-权限管理页面加载] PASSED
```

---

## 🔧 扩展指南

### 添加新的 Action

1. 在 `actions/` 目录下创建新文件：

```python
# actions/hover.py
def hover_action(page, locator, step, context, **kwargs):
    locator.hover()
```

2. 在 `runner/action_registry.py` 中注册：

```python
from actions.hover import hover_action

ACTION_REGISTRY = {
    # ... existing actions ...
    "hover": hover_action,
}
```

3. 在 YAML 用例中使用：

```yaml
steps:
  - action: hover
    target: menu_item
```

---

### 添加新的定位器类型

修改 `runner/locator_resolver.py`：

```python
def resolve_locator(page: Page, element: dict):
    # ... existing types ...
    
    if locator_type == "label":
        return page.get_by_label(locator_value)
    
    if locator_type == "alt_text":
        return page.get_by_alt_text(locator_value)
```

---

### 添加新的页面对象

1. 在 `assets/page-objects/web/` 目录下创建文件：

```yaml
# payment.page-object.yaml
page: payment

elements:
  pay_button:
    locator_type: role
    role: button
    locator_value: 立即支付
  
  amount_display:
    locator_type: css
    locator_value: .payment-amount
```

2. 在 YAML 用例中引用：

```yaml
execution:
  page: payment
  steps:
    - action: click
      target: pay_button
```

---

## 📝 最佳实践

### 1. 页面对象命名规范

```yaml
# ✅ 好的命名
elements:
  product_menu          # 名词 + 类型
  search_input          # 功能 + 类型
  submit_btn            # 动作 + 类型
  user_table            # 对象 + 类型

# ❌ 避免
elements:
  button1               # 无语义
  the_thing             # 模糊
  click_here            # 动作而非名词
```

---

### 2. 步骤编排原则

```yaml
# ✅ 推荐：等待元素后再操作
steps:
  - action: login
  - action: wait_for
    target: sidebar_menu
  - action: click
    target: product_menu

# ❌ 避免：直接操作可能未加载的元素
steps:
  - action: login
  - action: click
    target: product_menu    # 可能侧边栏还没加载
```

---

### 3. 变量使用

```yaml
# ✅ 推荐：使用变量提高可维护性
execution:
  variables:
    search_keyword: 手机
  steps:
    - action: fill
      target: search_input
      value: "{{search_keyword}}"

# ❌ 避免：硬编码
steps:
  - action: fill
    target: search_input
    value: 手机
```

---

### 4. 数据驱动

```yaml
# ✅ 推荐：边界值测试
data:
  search_keyword:
    - ""              # 空字符串
    - "a"             # 单字符
    - "手机"           # 正常值
    - "非常长的搜索关键词超过正常范围"  # 超长值
```

---

## 🐛 常见问题排查

### 问题 1: `Element not found in page object`

**原因**: 测试用例中的 `target` 在页面对象中不存在

**解决**:
1. 检查 `execution.page` 是否正确
2. 检查页面对象 YAML 中是否有对应的元素定义
3. 检查拼写是否一致

---

### 问题 2: `Timeout 30000ms exceeded`

**原因**: 元素定位器无法匹配到页面上的元素

**解决**:
1. 检查定位器类型是否正确
2. 使用浏览器开发者工具验证选择器
3. 考虑添加 `wait_for` 步骤等待元素加载

---

### 问题 3: 变量未解析 `{{xxx}}` 保持原样

**原因**: 变量未在 `variables` 或 `_data` 中定义

**解决**:
```yaml
execution:
  variables:
    keyword: 手机   # 确保变量已定义
```

---

## 📚 相关文件

| 文件 | 用途 |
|------|------|
| `conftest.py` | pytest fixtures 配置 |
| `pytest.ini` | pytest 运行配置 |
| `requirements.txt` | Python 依赖清单 |
| `schemas/yaml_testcase.schema.json` | YAML 用例 JSON Schema |
| `.env` | 环境变量（BASE_URL, TEST_USERNAME, TEST_PASSWORD）|

---

*文档生成时间：2026-03-17*
*项目版本：v4*
