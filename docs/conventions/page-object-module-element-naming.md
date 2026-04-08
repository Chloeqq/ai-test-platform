# 页面对象 / 元素 / 模块命名规范

本文档用于统一平台内页面对象、元素、模块相关字段的命名方式，适用于：

- 页面对象管理 UI
- 页面录制器
- page-object YAML 资产
- 用例生成与执行链路
- 人工录入、AI 生成、批量导入、评审发布

目标：

- 命名稳定，可长期复用
- 语义清晰，专业测试人员一眼可读
- 与当前后端真实校验规则一致
- 减少 AI、录制器、手工维护之间的命名漂移

## 1. 优先级与事实来源

命名规则冲突时，按以下优先级执行：

1. 当前运行时代码校验
2. 数据模型唯一约束
3. 本文档的团队推荐写法
4. 旧文档或历史示例

说明：

- 历史文档里存在 `LoginPage`、`usernameInput` 一类示例，这类写法不再作为新增标准。
- 当前新增资产必须优先遵守后端真实校验规则和本文档推荐格式。

运行时约束来源：

- [page_object_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/page_object_service.py)
- [page_object_recorder_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/services/page_object_recorder_service.py)
- [page_object.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/schemas/page_object.py)
- [page_object.py model](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/models/page_object.py)

## 2. 总体原则

- 全部编码字段统一使用小写英文语义编码。
- 不使用中文、空格、全角字符、特殊符号。
- 不依赖后端“自动清洗”帮你改名，提交前就应该是规范值。
- 编码表达业务语义，不表达临时状态。
- 名称尽量稳定，不把版本号、日期、负责人写进编码。
- 同一层级内保持唯一，避免“一物多名”。

推荐风格：

- `project_code`、`module_code`、`page_code`：优先 `kebab-case`
- `element_code`：优先 `snake_case`
- 中文展示名：直接写业务可读名称

这样划分的原因：

- 页面和模块编码更常出现在 URL、筛选、标识字段中，`kebab-case` 可读性更好。
- 元素编码会直接进入 runner target、page-object YAML 和脚本引用，当前资产主流风格是 `snake_case`，应继续保持一致。

## 3. 字段规范总表

| 字段 | 当前系统强校验 | 推荐写法 | 唯一范围 | 示例 |
|---|---|---|---|---|
| `project_code` | 2-20 位，仅字母数字，自动转小写 | 短小、稳定、业务明确 | 全局/租户内 | `atp` `mallweb` |
| `client` | 2-10 位，当前按业务枚举使用 | 固定短值，小写 | `project_code` 下 | `web` `app` |
| `module_id` | 整数，`>= 0` | 系统分配，不手写发明 | 系统内 | `0` `12` |
| `module_code` | 当前页面对象表未强校验 | 推荐 `kebab-case`，2-20 位 | `project_code` 下 | `order-center` |
| `module_name` | 当前页面对象表未强校验 | 中文业务名，简洁直白 | `project_code` 下 | `订单中心` |
| `page_code` | 2-40 位，仅字母数字 `_` `-`，自动转小写 | 推荐 `kebab-case` | `project_code + client` 下 | `refund-query` |
| `page_name` | 1-120 位 | 中文业务名，不加冗余前后缀 | 展示字段 | `退货查询页` |
| `element_code` | 2-80 位，仅字母数字 `_` `-`，自动转小写 | 推荐 `snake_case` | `page_code` 下 | `search_input` |
| `element_name` | 1-120 位 | 中文业务名，直接表达控件含义 | 展示字段 | `查询输入框` |

## 4. 模块命名规范

### 4.1 字段定义

- `module_id`：模块树或模块中心中的数字主键
- `module_code`：模块英文编码，便于筛选、导出、跨系统对齐
- `module_name`：模块中文展示名

当前页面对象表只强制存 `module_id`，但团队侧必须同步维护 `module_code / module_name` 映射，避免不同页面写出不同别名。

### 4.2 推荐格式

`module_code` 推荐格式：

- 使用 `kebab-case`
- 结构建议：`业务域-功能域`
- 长度建议控制在 2 到 20 位

正例：

- `order`
- `order-center`
- `refund`
- `member-center`
- `promotion-engine`

反例：

- `OrderCenter`
- `订单中心`
- `order_center`
- `order-center-v2`
- `temp-module`

### 4.3 中文名规则

`module_name` 推荐：

- 使用业务通用中文名
- 避免“模块管理模块”“订单中心功能模块”这类重复描述
- 不带项目名、端名、环境名

正例：

- `订单中心`
- `退款中心`
- `会员中心`

反例：

- `Mall 订单中心 WEB 模块`
- `订单中心功能模块`

## 5. 页面对象命名规范

### 5.1 唯一性规则

页面对象在数据库中的唯一键是：

- `project_code + client + page_code`

也就是说：

- 同一项目、同一端下，`page_code` 不能重复
- 不同项目之间可以复用相同 `page_code`
- `web` 和 `app` 也可以各自拥有同名页面

对应约束见：

- [page_object.py model](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/models/page_object.py#L10)

### 5.2 `page_code` 推荐格式

`page_code` 推荐格式：

- 全小写
- 优先 `kebab-case`
- 结构建议：`业务语义-页面语义`
- 不要带 `page`、`view`、`ui` 这类无信息后缀，除非业务上确实需要区分

正例：

- `login`
- `home`
- `refund-query`
- `order-list`
- `member-profile`
- `promotion-detail`

反例：

- `LoginPage`
- `refund query`
- `退款查询页`
- `page1`
- `refund-query-v202604`
- `new_page`

### 5.3 `page_name` 推荐格式

`page_name` 用中文表达真实业务页面名称，建议：

- 直接可读
- 与产品、研发、测试日常叫法一致
- 避免过度技术化

正例：

- `登录页`
- `订单列表页`
- `退款查询页`
- `会员资料页`

反例：

- `订单列表页面对象`
- `用于订单查询的页面`

### 5.4 页面命名模板

常见推荐模板：

- 单页：`login`
- 列表页：`order-list`
- 详情页：`order-detail`
- 编辑页：`order-edit`
- 弹窗页：`refund-dialog`
- 向导页：`publish-wizard`

如果一个业务域下有多端差异，端信息不要写进 `page_code`，而应通过 `client` 区分。

推荐：

- `project_code=mall`, `client=web`, `page_code=order-list`
- `project_code=mall`, `client=app`, `page_code=order-list`

不推荐：

- `page_code=order-list-web`
- `page_code=order-list-app`

## 6. 元素命名规范

### 6.1 唯一性规则

元素在数据库中的唯一键是：

- `page_object_id + element_code`

也就是说：

- 同一页面下不能有两个同名元素
- 不同页面下可以复用同一个 `element_code`

对应约束见：

- [page_object.py model](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/models/page_object.py#L37)

### 6.2 为什么 `element_code` 推荐 `snake_case`

当前稳定资产、runner target 和测试用例引用更接近 `snake_case` 风格，例如：

- `username_input`
- `login_button`
- `home_menu`
- `search_input`

相关现有资产：

- [login.page-object.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web/login.page-object.yaml)
- [order.page-object.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web/order.page-object.yaml)

因此团队新增元素建议继续保持 `snake_case`，避免：

- YAML 中一套风格
- UI 录入一套风格
- AI 生成另一套风格

### 6.3 `element_code` 推荐格式

推荐格式：

- 全小写
- 使用 `snake_case`
- 结构建议：`[区域_]语义主体_[动作或类型]`

常见后缀建议：

- 输入框：`_input`
- 按钮：`_button`
- 菜单：`_menu`
- 标签：`_tag`
- 表格：`_table`
- 标题：`_title`
- 弹窗：`_dialog`
- 复选框：`_checkbox`
- 单选项：`_radio`
- 链接：`_link`
- 页签：`_tab`
- 开关：`_switch`

正例：

- `username_input`
- `password_input`
- `login_button`
- `home_menu`
- `search_input`
- `submit_button`
- `status_tag`
- `result_table`
- `header_user_menu`
- `filter_reset_button`

反例：

- `usernameInput`
- `SearchBtn`
- `查询按钮`
- `button1`
- `login-button`
- `refund-query-search-button`

说明：

- 元素命名默认不要重复页面前缀，因为它的唯一范围本来就在页面内。
- 只有在做跨页导出、离线上下文传递或多页面合并展示时，才考虑补页面前缀。

### 6.4 `element_name` 推荐格式

`element_name` 使用中文业务名称，建议与页面 UI 文案或测试语义保持一致。

正例：

- `用户名输入框`
- `登录按钮`
- `首页菜单`
- `查询输入框`
- `结果表格`

反例：

- `locator-1`
- `元素A`
- `测试按钮`

## 7. 推荐命名模板

### 7.1 模块

- `module_code`: `业务域-功能域`
- `module_name`: 中文业务模块名

示例：

- `order-center` / `订单中心`
- `member-center` / `会员中心`
- `refund-center` / `退款中心`

### 7.2 页面对象

- `page_code`: `业务语义-页面语义`
- `page_name`: 中文页面名

示例：

- `order-list` / `订单列表页`
- `order-detail` / `订单详情页`
- `refund-query` / `退款查询页`

### 7.3 元素

- `element_code`: `[区域_]语义主体_[动作或类型]`
- `element_name`: 中文控件名

示例：

- `search_input` / `查询输入框`
- `submit_button` / `提交按钮`
- `status_tag` / `状态标签`
- `header_user_menu` / `头部用户菜单`

## 8. 从中文到编码的转换规则

### 8.1 页面对象

中文名：

- `登录页`
- `订单列表页`
- `退款查询页`

推荐编码：

- `login`
- `order-list`
- `refund-query`

### 8.2 元素

中文名：

- `用户名输入框`
- `查询按钮`
- `结果表格`

推荐编码：

- `username_input`
- `search_button`
- `result_table`

### 8.3 不建议直接拼音化

不推荐：

- `dengluye`
- `dingdanliebiao`
- `tuikuanchaxun`

优先使用团队统一英文业务词表；如果确实没有统一英文，再由模块负责人补充约定后再落库。

## 9. AI 生成与录制器补充约束

- AI 自动生成的 `page_code`、`element_code` 必须复用已有命名体系，不允许临时发明风格。
- 录制器自动生成的编码只作为初稿，发布前应人工校正到团队规范。
- 不要把 locator 类型、随机截断文本、时间戳当成长期正式编码。
- 自动生成时，优先命中已有英文语义词表；未命中时，生成可读短语，不生成无意义缩写。

## 10. 评审检查清单

新增或修改页面对象 / 元素时，评审至少检查以下项：

- [ ] `project_code` 是否为稳定项目编码
- [ ] `page_code` 是否全小写、语义清晰、长度合规
- [ ] `page_code` 是否没有混入端、环境、版本等冗余信息
- [ ] `element_code` 是否采用 `snake_case`
- [ ] `element_code` 是否表达控件语义，而不是临时实现细节
- [ ] `element_name` / `page_name` 是否为统一中文叫法
- [ ] `module_id` 是否绑定到正确模块
- [ ] 如涉及模块编码映射，`module_code / module_name` 是否已同步

## 11. 建议沉淀的团队词表

为了避免同一语义出现多种写法，建议在团队内持续维护统一词表，例如：

| 中文 | 推荐英文 |
|---|---|
| 登录 | `login` |
| 首页 | `home` |
| 查询 | `query` / `search` |
| 列表 | `list` |
| 详情 | `detail` |
| 提交 | `submit` |
| 重置 | `reset` |
| 结果 | `result` |
| 状态 | `status` |
| 会员 | `member` |
| 订单 | `order` |
| 退款 | `refund` |

注意：

- 同一语义只保留一套主写法。
- 比如“查询”如果页面级统一用 `query`，元素级按钮可约定统一用 `search_button`，但不要同一项目同时出现 `query_button`、`search_btn`、`searchButton` 三套并存。

## 12. 当前结论

团队统一建议如下：

- 模块：`module_code` 用 `kebab-case`，`module_name` 用中文业务名
- 页面对象：`page_code` 用 `kebab-case`，`page_name` 用中文页面名
- 元素：`element_code` 用 `snake_case`，`element_name` 用中文控件名
- `module_id` 是数字主键，不是命名字段
- 不依赖后端自动清洗，不新增历史风格命名

如果后续需要把这份规范升级成可执行校验，可以在前端录入、导入校验、AI 生成后处理和 CI 静态检查里同步接入。
