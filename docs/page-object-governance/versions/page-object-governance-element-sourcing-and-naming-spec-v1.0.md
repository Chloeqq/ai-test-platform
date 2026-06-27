# 页面元素获取策略与元素编码命名规范 V1.0

## 文档目标

针对当前被测系统 `mall-admin-web` 这类“无前端开发配合、无测试标识契约”的开源项目，明确两件事：

1. 页面元素应该如何获取，才能尽量准确地支撑自动化测试
2. 页面元素编码 `element_code` 应该如何命名，才能稳定映射测试点并生成可执行步骤

本文是独立规范，优先解决“先怎么做才可落地”。

---

## 一、先说结论

对于 `mall-admin-web` 这类现状，**不能只靠源码读取，也不能只靠 Playwright codegen 录制**。

推荐策略是：

- **主策略：源码解析 + 运行时页面探测的混合建模**
- **辅助策略：录制候选采集**
- **最终入库：人工审核后的正式元素**

换句话说：

- 源码读取适合拿“组件语义、字段含义、页面结构”
- codegen 录制适合拿“真实运行时可点击、可输入的定位线索”
- 这两者都不能直接等于正式页面元素
- 正式元素必须经过治理、命名、审核后才能进入资产库

---

## 二、为什么不能只靠一种方式

### 1. 只读源码的问题

如果只读 `mall-admin-web` 源码，会遇到这些问题：

- 能看到组件结构，但不一定知道最终渲染后的真实 DOM
- 很多 UI 框架组件会二次封装，源码里的字段名不等于浏览器里可定位的属性
- 条件渲染、权限渲染、异步加载后的元素，仅靠静态源码不一定能准确恢复
- 某些按钮、图标、弹层、表格操作列在源码里可读性也很差

所以源码适合回答：

- 这个元素业务上是什么
- 属于哪个页面、哪个模块
- 大概率对应什么字段或动作

但源码不一定能回答：

- 最终应该用什么 locator 才稳定

### 2. 只靠 Playwright codegen 的问题

如果只靠 codegen，会遇到你已经看到的典型问题：

- 拿到的是“操作轨迹定位器”，不是“业务资产”
- 经常出现 `css/xpath/nth/path/index/text` 这种脏定位
- codegen 倾向优先给出当前能工作的定位，而不是长期稳定、可治理的定位
- 同一业务元素在不同录制轮次下，候选定位可能完全不同
- 图标、指标、列表项、弹窗按钮容易录出一堆无业务语义的候选

所以 codegen 适合回答：

- 用户实际点到了哪个元素
- 当前运行时哪些元素是真可交互的
- 在真实浏览器里有哪些可观察的 role、text、placeholder、locator

但 codegen 不适合直接产出：

- 正式元素编码
- 最终资产级命名
- 测试点到执行步骤的一一映射标准

---

## 三、针对 mall-admin-web 的推荐策略

## 3.1 总原则

对 `mall-admin-web` 这类无前端配合项目，推荐采用四层链路：

1. 页面识别
2. 元素候选采集
3. 元素语义归并
4. 正式元素审核入库

### 3.2 页面识别层

页面识别优先依赖：

- 路由
- 页面标题
- 左侧菜单名称
- 页面主表格 / 主表单 / 页面核心锚点

目的不是精确定位所有元素，而是先确保：

- 当前候选归属哪个页面对象

### 3.3 元素候选采集层

候选来源分成三类：

#### A. 源码语义候选

从源码中提取：

- 表单字段 label
- 按钮文案
- 表格列名
- 菜单项
- 弹窗标题
- 组件字段名

适合生成：

- 建议元素名称
- 建议业务类型
- 建议业务域

#### B. 运行时探测候选

通过浏览器真实页面探测：

- role
- accessible name
- placeholder
- visible text
- id / name
- data-testid / data-qa

适合生成：

- 候选定位器
- probe 状态
- 可见性 / 可交互性

#### C. 录制行为候选

通过 Playwright codegen / 手工录制过程采集：

- 用户点过什么
- 输入过什么
- 打开过哪些弹层
- 点击路径经过哪些控件

适合生成：

- step_hit_count
- 操作频率
- 当前测试意图下高相关候选

### 3.4 正式入库层

只有同时满足以下条件的元素，才允许入正式资产库：

- 页面归属明确
- 业务语义明确
- 编码符合命名规范
- 定位来源可解释
- 审核通过

这一步非常关键。

因为对你这个平台来说，真正有价值的不是“采集到了多少 locator”，而是：

- 有多少元素能稳定映射成测试步骤

---

## 四、在当前阶段，源码读取和 codegen 谁优先

当前如果要尽快落地，我建议优先级是：

### 优先级 1：先保留 codegen 作为候选采集入口

原因：

- 你现在的平台已经有录制链路
- 已经能拿到运行时真实可交互元素
- 改造成本最低
- 可以快速验证治理方案

但是必须明确：

- codegen 只负责采候选
- 不负责直接生成正式元素

### 优先级 2：逐步补源码语义增强

原因：

- `mall-admin-web` 没有测试标识契约
- 单靠运行时 locator，业务语义不足
- 需要源码里的字段名、文案、模块结构来增强命名与归类

源码增强优先提取的内容：

- 页面 route
- 表单 label
- 按钮文案
- 菜单文案
- 表格列标题
- 组件字段 key

### 优先级 3：治理后形成正式元素库

只有这一步完成，平台才真正知道：

- `密码显隐按钮` 不是普通图标，而是 `password_toggle`
- `销售额 12345` 这种 text 不是静态文案，而是 `metric_value`

---

## 五、正式元素编码命名规范

## 5.1 总原则

正式元素编码 `element_code` 必须满足：

- 业务语义优先
- 页面无关
- UI 实现无关
- 位置无关
- 序号无关
- 可被测试点稳定引用

一句话：

- 编码表达“它是什么”，不是“它长什么样”。

---

## 5.2 基础语法

统一采用：

- `kebab-case`（连字符分隔），格式 `{page}-{semantic}-{type_suffix}`

允许字符：

- 小写字母 `a-z`
- 数字 `0-9`
- 连字符 `-`

长度建议：

- `3-80`

禁止：

- 大写字母
- 下划线 `_`（仅用于旧语义码向后兼容）
- 空格
- 中文
- locator 噪音词

> **注意：** 本文 V1.0 原推荐 `snake_case`（下划线），现已统一为标准 `kebab-case`。
> 旧码（`username_input`）在 `element_naming.resolve_legacy_code()` 中保留兼容，
> 但新元素编码必须使用 `kebab-case`。

---

## 5.3 命名结构

统一结构：

- **`{page}-{semantic}-{type_suffix}`**

三段式，以连字符分隔：

1. `page` — 页面标识（如 `login`、`product`、`order`）
2. `semantic` — 业务语义（如 `username`、`password`、`submit`）
3. `type_suffix` — 元素类型后缀（见 5.5 节）

示例：

- `login-username-input` — 登录页用户名输入框
- `login-password-input` — 登录页密码输入框
- `login-submit-btn` — 登录页提交按钮
- `login-password-toggle-btn` — 登录页密码显隐按钮
- `product-search-input` — 商品页搜索输入框
- `order-table` — 订单列表表格
- `order_table`
- `order_no_column`
- `order_status_filter`
- `save_button`
- `cancel_button`
- `confirm_dialog`

不强制必须是两段，但必须能看出业务语义。

---

## 5.4 命名优先级

生成 `element_code` 时，优先从以下信息取语义：

1. 测试点中已出现的业务词
2. 页面文案中的字段名 / 按钮名 / 菜单名
3. 源码字段名
4. 录制中的 role + 文案
5. 最后才允许人工补充命名

例如：

- 页面显示“用户名”
- 测试点里也写“账号输入框”
- 则优先归一成 `username_input`

---

## 5.5 后缀规范

建议固定后缀集合。

### 输入类

- `_input`
- `_textarea`
- `_select`
- `_date_picker`
- `_search_input`

示例：

- `username_input`
- `remark_textarea`
- `status_select`

### 按钮类

- `_button`
- `_submit_button`
- `_search_button`

示例：

- `login_button`
- `save_button`
- `search_submit_button`

### 选择类

- `_checkbox`
- `_radio`
- `_switch`

示例：

- `remember_me_checkbox`
- `enable_status_switch`

### 导航类

- `_tab`
- `_menu`
- `_link`

示例：

- `order_tab`
- `system_menu`
- `logout_link`

### 容器 / 展示类

- `_table`
- `_dialog`
- `_drawer`
- `_section`
- `_card`

示例：

- `order_table`
- `edit_dialog`
- `user_detail_drawer`

### 指标类

- `_metric_label`
- `_metric_value`

示例：

- `order_total_metric_label`
- `order_total_metric_value`

---

## 5.6 特殊语义规范

### 密码显隐

统一命名为：

- `password_toggle`

不要命名成：

- `eye_icon`
- `show_password_icon`
- `login_css_i_path_3`

因为业务语义是“密码显隐切换”，不是“一个眼睛图标”。

### 指标值

动态数字类元素统一按业务意义命名，不按 text 内容命名。

例如页面上显示：

- `总订单数 1024`
- `销售额 ¥23,000`

应该命名为：

- `order_total_metric_value`
- `sales_amount_metric_value`

而不是：

- `text_1024`
- `sales_text`

### 指标标题

标签类命名为：

- `order_total_metric_label`
- `sales_amount_metric_label`

### 表格列

表格列头建议命名为：

- `order_no_column`
- `order_status_column`
- `member_name_column`

### 表格行操作按钮

若是通用操作按钮，不建议用位置命名。

应优先命名成：

- `edit_button`
- `delete_button`
- `view_detail_button`

若必须加上下文，则：

- `order_edit_button`
- `product_delete_button`

---

## 六、禁止词清单

正式元素编码中，默认禁止出现以下词：

- `css`
- `xpath`
- `path`
- `index`
- `idx`
- `nth`
- `text`
- `button1`
- `input1`
- `icon1`
- `div`
- `span`
- `el`
- `node`
- `temp`
- `tmp`

也禁止出现：

- 纯数字后缀作为主要区分方式
- 页面名前缀

例如禁止：

- `login_username_input`
- `page_login_button`
- `css_path_3`
- `button_1`
- `text_2`

---

## 七、页面名前缀为什么禁止

禁止 `login_username_input` 这类命名，原因是：

- 页面归属本来就在 `page_object_id` 上
- 编码里再加页面前缀会冗余
- 后续跨页面复用、别名匹配、业务抽象都会变差

所以：

- 页面归属放在页面对象
- 元素编码只表达元素本体语义

---

## 八、候选命名与正式命名的区别

候选层允许存在“建议编码”，但正式层必须严格。

### 候选层

允许：

- `proposed_element_code`
- 来源可能不稳定
- 可由录制和源码共同猜测

### 正式层

必须：

- 符合本规范
- 人工审核通过
- 能稳定映射测试点

也就是说：

- 候选命名可以猜
- 正式命名不能乱

---

## 九、针对 mall-admin-web 的落地建议

## 9.1 第一阶段

保留现有 Playwright codegen 录制能力，但角色改成：

- 只产出候选

不允许：

- 直接生成正式元素编码
- 直接进入执行资产

## 9.2 第二阶段

补一层源码语义增强，重点从 `mall-admin-web` 抽：

- 页面路由
- 菜单标题
- 表单 label
- 按钮文本
- 表格列名

用于增强：

- `proposed_element_name`
- `business_type_guess`
- `business_domain_guess`
- `proposed_element_code`

## 9.3 第三阶段

在审核页提升时，正式执行这套命名规范：

- 编码正则校验
- 禁止词校验
- 页面前缀校验
- 关键语义类型校验

---

## 十、建议增加的平台校验规则

平台后续应增加以下自动校验：

### 10.1 编码格式校验

正则建议：

- `^[a-z][a-z0-9_]{2,79}$`

### 10.2 禁止词校验

若命中禁止词，则阻断提升。

### 10.3 关键类型校验

例如：

- `password_toggle` 不允许被保存成 `eye_icon`
- `metric_value` 不允许被保存成纯文本数字编码

### 10.4 推荐命名提示

提升弹窗内可提示：

- 推荐编码：`password_toggle`
- 不建议编码：`login_css_i_path_3`

---

## 十一、正反例

### 推荐命名

- `username_input`
- `password_input`
- `login_button`
- `password_toggle`
- `remember_me_checkbox`
- `search_keyword_input`
- `search_submit_button`
- `order_table`
- `order_no_column`
- `order_status_filter`
- `sales_amount_metric_value`
- `sales_amount_metric_label`

### 不推荐命名

- `login-css-i-path-3`
- `button_1`
- `text_2`
- `page_login_username`
- `div_node_1`
- `show_password_icon`
- `css_input_4`
- `xpath_btn_login`

---

## 十二、最终建议

对 `mall-admin-web` 这种没有前端测试契约的项目，最务实的路线不是二选一，而是：

- **录制拿运行时线索**
- **源码拿业务语义**
- **治理页做人审归一**
- **正式元素严格按命名规范入库**

如果只靠录制，你会得到一堆能点但没法治理的 locator。

如果只靠源码，你会得到一堆看起来有语义、但不一定能稳定执行的元素。

---

## 十三、附录 A：element_naming 中心模块

> 版本：V1.1（2026-06-27 新增）

为解决 element_code 的命名一致性，统一了 `shared_backend/element_naming.py` 作为唯一的编码推导入口。
所有代码中不应再硬编码 element_code 的 if-else 映射，改为调用此模块。

### A.1 核心函数

| 函数 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `element_data_key(ec)` | `login-username-input` | `username` | 推导 DSL data 段 key |
| `element_variable_name(ec, page)` | `ec`, page=`login` | `login_username` | 推导 execution.variables 变量名 |
| `element_display_name(ec, meta?)` | `login-submit-btn` | `提交按钮` | 推导中文展示名（有页面对象时优先 name 字段）|
| `resolve_legacy_code(v)` | `username_input` | `login-username-input` | 旧语义码→规范码，用于存量过渡 |

### A.2 推导规则

从 `element_code` 本身推导，不依赖硬编码映射表：

1. 按 `-` 拆分为三段：`{page}`-`{semantic}`-`{type_suffix}`
2. `data_key` = `semantic`（中间段）
3. `variable_name` = `{page}_{semantic}`（页面前缀 + 语义）
4. `display_name` = 查 `_TYPE_SUFFIX_DISPLAY` 表（如 `input→输入框`、`btn→按钮`）

### A.3 向后兼容

旧语义码（`username_input`, `password_input`, `login_button` 等）通过 `_LEGACY_TO_CANONICAL` 映射表自动转换。
新代码应直接使用规范码，旧映射仅用于存量数据解析。

### A.4 使用示例

```python
from shared_backend.element_naming import element_data_key, element_variable_name

# data key
assert element_data_key("login-username-input") == "username"
assert element_data_key("product-search-input") == "search"

# variable name
assert element_variable_name("login-username-input", page="login") == "login_username"
assert element_variable_name("login-submit-btn", page="login") == "login_submit"

# display name (with page object metadata)
from shared_backend.element_naming import element_display_name
assert element_display_name("login-username-input") == "用户名输入框"
```

### A.5 旧码→规范码对照表

| 旧语义码 | 规范码 | 说明 |
|---------|--------|------|
| `username_input` | `login-username-input` | 用户名输入框 |
| `password_input` | `login-password-input` | 密码输入框 |
| `login_button` | `login-submit-btn` | 登录按钮 |
| `home_menu` | `home-page` | 首页容器 |
| `username` | `login-username-input` | AI 生成简称 |
| `password` | `login-password-input` | AI 生成简称 |
| `loginButton` | `login-submit-btn` | AI 生成 camelCase |

只有把这两者结合起来，页面对象资产才会真正可用于测试点映射和可执行用例生成。
