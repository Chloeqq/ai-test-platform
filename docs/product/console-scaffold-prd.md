# Console Scaffold PRD

## 0. 阅读说明

`Scaffold Console` 是一条**并行产品线**，不是当前 URL-first workbench 主链本身。

阅读时请注意：

1. 它的核心目标是“资产脚手架创建”，不是“页面 URL 驱动的一键分析、执行、治理”。
2. 它当前主要服务于 page object / smoke case scaffold 创建，不等于当前主 workbench 的 review/gate/audit 闭环。
3. 如果你要看 URL-first 主链，请优先转到：
   - [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)
   - [current-architecture-and-flows.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/architecture/current-architecture-and-flows.md)

## 1. 文档目的

本文档用于定义当前内置控制台 `Scaffold Console` 的产品目标、功能范围、交互流程和验收标准。

它服务于三个场景：

- 帮助新手快速理解当前控制台到底能做什么
- 帮助研发继续迭代时有统一的需求基线
- 帮助测试和产品评估当前版本是否达到可用标准

相关入口：

- 用户操作手册：[console-scaffold-guide.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/console-scaffold-guide.md)
- 控制台说明：[apps/web-console/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/README.md)
- 服务接口契约：[orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)
- 交互说明：[console-scaffold-ux-spec.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-ux-spec.md)
- 测试用例：[console-scaffold-test-cases.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/testing/console-scaffold-test-cases.md)
- 接口说明：[console-scaffold-api-spec.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/api/console-scaffold-api-spec.md)

## 2. 产品背景

补充边界：

- 这条控制台产品线更偏“模板驱动资产生产工具”。
- 当前不承担 URL-first 页面分析、低置信度确认点、风险决策或 execution gate。

当前项目已经具备一条最小可运行的测试资产生成链路：

- 通过模板创建 page object
- 通过模板生成 smoke test case
- 通过浏览器页面完成参数填写和结果查看

但如果没有一个可用的操作入口，新用户仍然需要：

- 直接调用 HTTP API
- 手工拼装 JSON
- 手工理解 page object / YAML 资产结构

这会抬高使用门槛。

因此需要一个最小可用控制台，把“模板选择 -> 参数填写 -> 请求预览 -> 资产创建 -> 历史复用”这一条链路串起来。

## 3. 产品目标

### 3.1 核心目标

让不了解代码结构的用户，也能在几分钟内完成一次 scaffold 创建。

### 3.2 具体目标

- 用户可以发现当前可用模板
- 用户可以基于模板快速生成测试资产
- 用户在提交前能看到请求内容并发现明显错误
- 用户在提交后能理解生成结果
- 用户可以复用历史记录减少重复填写

### 3.3 非目标

当前版本不追求：

- 独立前端工程
- 多人共享历史记录
- 服务端持久化收藏
- 权限体系
- 真正完整的资产编辑器
- 全量 YAML 可视化编辑
- URL-first 页面理解与自动执行闭环
- review_state / execution_gate / risk gate 治理

## 4. 目标用户

### 4.1 新手测试人员

特点：

- 不熟悉仓库结构
- 不熟悉 page object 和 YAML schema
- 需要一个页面级工具快速创建测试资产

主要诉求：

- 简单易用
- 能看懂结果
- 不容易误操作

### 4.2 研发或测试开发

特点：

- 已经理解部分平台结构
- 需要快速搭建页面测试骨架

主要诉求：

- 减少重复手工维护
- 快速复用模板和历史记录

### 4.3 平台维护者

特点：

- 关心接口是否稳定
- 关心资产生成流程是否可验证

主要诉求：

- 页面行为和接口契约一致
- 关键流程可测试

## 5. 当前版本范围

当前版本包含以下能力。

### 5.1 模板发现

- 查看 scaffold 模板列表
- 查看模板详情
- 显示模板推荐标题与需求文案

### 5.2 表单创建

- 填写页面基础信息
- 指定模板
- 可选填写额外元素 JSON

### 5.3 请求预览

- 展示即将发送的请求 JSON
- 和上一次成功请求做 diff
- 本地 preflight 校验
- 有错误时阻止提交

### 5.4 结果展示

- 展示生成摘要
- 展示生成步骤
- 展示页面元素
- 展示原始响应

### 5.5 本地工作台能力

- 保存表单草稿
- 保存最近创建记录
- 收藏常用记录
- 给记录设置别名
- 复用历史记录
- 重新执行历史记录
- 导出历史记录 JSON
- 复制生成文件路径

## 6. 用户故事

### 6.1 模板发现

作为一个第一次使用系统的测试人员，  
我希望看到当前有哪些模板可选，  
这样我不用猜页面骨架应该从哪里开始。

### 6.2 快速创建

作为一个需要给新页面补 smoke case 的测试开发，  
我希望通过一个简短表单就能创建 page object 和 test case，  
这样我不用手写 YAML 和 page object 文件。

### 6.3 提交前防错

作为一个不熟悉接口字段的人，  
我希望在发送前看到请求内容并获得本地校验提示，  
这样我能避免发出明显错误的请求。

### 6.4 结果理解

作为一个新手用户，  
我希望创建成功后能看到步骤、元素和路径，  
这样我知道系统到底帮我生成了什么。

### 6.5 历史复用

作为一个反复创建类似页面骨架的人，  
我希望保存并复用最近一次操作，  
这样我不用每次重新填写相同字段。

## 7. 功能需求

### 7.1 模板列表

系统应支持：

- 加载模板列表
- 显示模板名称和摘要
- 点击后高亮当前模板

验收要求：

- 页面加载后可以看到模板列表
- 点击某个模板后，右侧详情同步变化

### 7.2 模板详情

系统应支持：

- 查看模板完整详情
- 展示推荐标题
- 展示推荐需求文案

验收要求：

- 选择模板后，详情区不为空

### 7.3 自动填充

系统应支持：

- 选择模板后自动填入推荐 `title`
- 选择模板后自动填入推荐 `requirement`
- 如果用户已经手工改过字段，则不强制覆盖

验收要求：

- 首次选择模板时自动填充
- 字段被用户手改后，再切模板不会静默覆盖

### 7.4 Scaffold 表单

系统应支持以下基础字段：

- `page`
- `title`
- `requirement`
- `template`
- `description`
- `priority`
- `elements`

验收要求：

- 用户能通过表单成功构造 scaffold 请求

### 7.5 请求预览

系统应支持：

- 点击 `Create Scaffold` 后先进入预览
- 展示请求 JSON
- 展示相对上一次请求的 diff
- 展示 preflight 检查结果

验收要求：

- 提交前一定先看到预览
- 用户可以取消预览

### 7.6 本地 preflight 校验

系统应至少检查：

- `page` 非空
- `title` 非空
- `requirement` 非空
- `elements` 必须是 JSON 数组
- 元素项必须是对象
- 元素必须有 `name`
- 元素必须有 `locator_type`
- 元素必须有 `locator_value`
- 当 `locator_type=role` 时必须有 `role`
- `smoke_role` 只能是 `menu` 或 `assert`

验收要求：

- 任何本地校验失败时，`Confirm Request` 必须禁用

### 7.7 结果展示

系统应支持展示：

- test case id
- page 名
- 元素数量
- 步骤数量
- page object 路径
- test case 路径
- 具体步骤
- 具体元素
- 原始 JSON 响应

验收要求：

- scaffold 成功后，结果区各区域必须有内容

### 7.8 历史记录

系统应支持：

- 保存最近记录
- 展示最近记录
- 删除单条
- 清空全部
- 导出 JSON

验收要求：

- 用户刷新页面后仍能看到本地记录

### 7.9 收藏和别名

系统应支持：

- 收藏记录
- 收藏记录固定在顶部
- 给记录设置本地别名

验收要求：

- 收藏后记录出现在 `Favorites`
- 别名设置后列表显示优先使用别名

### 7.10 历史复用与重跑

系统应支持：

- `Reuse This`
- `Run Again`

差异要求：

- `Reuse This`
  - 只回填表单
- `Run Again`
  - 直接进入请求预览，可再次提交

验收要求：

- 两个动作行为必须有明确区别

## 8. 交互流程

### 8.1 首次创建流程

1. 用户打开 `/console`
2. 系统加载模板列表
3. 用户选择一个模板
4. 系统自动填充推荐字段
5. 用户填写 `page` 等信息
6. 用户点击 `Create Scaffold`
7. 系统展示 `Request Preview`
8. 系统执行本地 preflight 检查
9. 用户确认无误后点击 `Confirm Request`
10. 系统调用 `POST /assets/scaffold`
11. 系统展示结果摘要、步骤、元素、原始响应
12. 系统把本次结果写入本地历史

### 8.2 历史复用流程

1. 用户在 `Recent Scaffolds` 里选择 `Reuse This`
2. 系统将该条记录回填到表单
3. 用户可修改后再次提交

### 8.3 历史重跑流程

1. 用户在 `Favorites` 或 `Recent Scaffolds` 中选择 `Run Again`
2. 系统将该条记录构造成请求
3. 系统进入请求预览
4. 用户确认后再次发送

## 9. 异常流程

### 9.1 模板加载失败

系统应：

- 在状态区显示错误信息
- 不使页面崩溃

### 9.2 请求构造失败

例如：

- `Extra Elements JSON` 非法

系统应：

- 直接在状态区提示错误
- 不发送请求

### 9.3 本地 preflight 失败

系统应：

- 在 `Preflight Checks` 中列出问题
- 禁用 `Confirm Request`

### 9.4 后端返回错误

系统应：

- 在状态区显示错误消息
- 保留当前表单内容

## 10. 数据与状态要求

当前版本使用浏览器本地存储，不使用服务端持久化。

应保存的数据包括：

- 当前表单草稿
- 最近历史记录
- 上一次成功请求

用途：

- 表单恢复
- 历史记录展示
- diff 对比

## 11. 技术边界

当前版本的边界如下：

- 静态页面由 `ai-orchestrator` 直接托管
- 不引入独立前端框架
- 不引入服务端数据库
- 不做多人协作同步
- 不做鉴权

## 12. 验收标准

当前版本可视为验收通过，至少应满足以下条件：

### 12.1 功能验收

- 用户可打开 `/console`
- 用户可看到模板列表
- 用户可成功创建 scaffold
- 用户可在提交前看到请求预览
- 用户可在预览中看到 diff 和 preflight 检查
- 用户可在成功后看到结果摘要、步骤和元素
- 用户可使用历史记录的 `Reuse This`
- 用户可使用历史记录的 `Run Again`
- 用户可收藏、别名、导出和删除记录

### 12.2 稳定性验收

- 控制台脚本语法检查通过
- orchestrator 集成测试通过
- 根级默认测试通过

当前验证入口：

- `make check-console`
- `make test`

## 13. 后续迭代建议

如果继续演进，建议优先做这些：

### 13.1 短期

- 收藏记录单独支持自定义排序
- 支持把历史记录导入回控制台
- 支持更友好的 `elements` 表单编辑，而不是只写 JSON

### 13.2 中期

- 把控制台拆成更清晰的模块化前端结构
- 增加更完整的字段级错误提示
- 增加结果 diff 和文件预览

### 13.3 长期

- 接入服务端持久化
- 接入用户体系
- 接入更完整的资产编辑能力
