# Console Scaffold Guide

> 入口边界说明：
> 这份手册对应的是 `Scaffold Console`，用于快速创建 page object 和 smoke scaffold。
> 如果你要体验当前主 workbench 的 URL-first 生成、确认点、风险决策与历史回显，请改看 `/workbench` 相关文档，而不是 `/console`。

本文档面向第一次接触项目的人，说明如何通过内置控制台创建测试资产，并理解今天已经实现的主要功能。

如果你需要更正式的需求定义版本，见：

- [Console Scaffold PRD](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-prd.md)

## 1. 这是什么

当前项目内置了一个最小可用的 Web Console，用来帮助你完成两件事：

- 浏览可用的测试资产模板
- 一键创建 page object 和 smoke test case 骨架

它和当前 URL-first 主链的关系是：

- `/console`：偏模板驱动的资产 scaffold 工具
- `/workbench` / `generate`：偏页面分析、生成、执行、治理闭环

它不是一个完整前端系统，而是由 `ai-orchestrator` 直接托管的静态页面。

入口：

- 控制台页面：[http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

相关代码：

- [app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/app.py)
- [asset_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/asset_service.py)
- [index.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/static/index.html)
- [app.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/static/app.js)

## 2. 它能帮你做什么

今天已经实现的能力包括：

- 查看 scaffold 模板列表
- 查看模板详情和推荐字段
- 自动填充 `title` 和 `requirement`
- 创建 page object 和 smoke case
- 在发送前预览请求内容
- 和上一次请求做 diff 对比
- 在本地做 preflight 校验，阻止明显错误提交
- 查看生成结果摘要、步骤预览、元素预览、原始响应
- 在浏览器本地保存最近创建记录
- 收藏常用记录
- 给记录设置本地别名
- 直接复用历史记录重新填写表单
- 直接 `Run Again` 重新发起一次 scaffold 请求
- 导出本地历史记录 JSON
- 复制生成文件路径

## 3. 先准备什么

### 3.1 安装依赖

在项目根目录执行：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
make install-dev
```

### 3.2 启动服务

执行：

```bash
./.venv/bin/python apps/ai-orchestrator/src/main.py serve --host 127.0.0.1 --port 8000
```

如果你不用根目录 `.venv`，也可以用系统 Python：

```bash
python3 apps/ai-orchestrator/src/main.py serve --host 127.0.0.1 --port 8000
```

### 3.3 打开页面

浏览器访问：

- [http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)

如果打不开，先访问：

- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

如果 `health` 也打不开，说明服务没有启动成功。

## 4. 页面上每个区域是干什么的

### 4.1 Templates

这里会列出当前支持的资产模板，例如：

- `catalog`
- `list`
- `detail`

点击模板后：

- 右侧会显示模板详情
- 表单里的 `Template` 会自动带入
- 推荐的 `title` 和 `requirement` 会自动填充

### 4.2 Template Detail

这里展示模板的结构化信息，帮助你理解：

- 这个模板适合什么页面
- 推荐标题是什么
- 推荐需求文案是什么
- 预置了哪些元素模板

### 4.3 Scaffold Request

这里是创建测试资产的主表单。

常用字段说明：

- `Page`
  - 页面标识，建议使用英文小写，例如 `catalog`
- `Title`
  - 页面中文名称，例如 `商品目录`
- `Requirement`
  - 这条 smoke case 对应的业务需求，例如 `商品目录页面展示`
- `Template`
  - 可选，通常从模板点击后自动填入
- `Description`
  - 可选，用来说明这次创建目的
- `Priority`
  - 用例优先级，默认 `P1`
- `Extra Elements JSON`
  - 可选，用来额外声明页面元素

### 4.4 Request Preview

点击 `Create Scaffold` 后，不会直接发请求，而是先进入预览区。

这里会展示三类信息：

- 请求 JSON
- 和上一次请求相比的 diff
- 本地 preflight 校验结果

如果这里出现错误，`Confirm Request` 会被禁用。

### 4.5 Result / Generated Steps / Page Elements

创建成功后，这几个区域会展示：

- 生成的 test case ID
- page object 对应页面名
- 生成了多少元素
- 生成了多少步骤
- smoke steps 的具体动作
- page object 的元素定义

### 4.6 Favorites / Recent Scaffolds

这是本地历史记录区，数据保存在当前浏览器里。

它不会上传到服务器。

你可以：

- 收藏常用 scaffold
- 删除不需要的历史
- 导出 JSON
- 给历史记录起别名
- 一键重新运行

## 5. 最简单的操作流程

适合第一次使用的人：

1. 打开控制台
2. 在 `Templates` 里点击 `catalog`
3. 观察 `Title` 和 `Requirement` 已自动填充
4. 在 `Page` 输入 `catalog`
5. 可选填写 `Description`
6. 点击 `Create Scaffold`
7. 在 `Request Preview` 里确认没有报错
8. 点击 `Confirm Request`
9. 在 `Result` 区查看生成结果
10. 在 `Recent Scaffolds` 查看本次记录

## 6. 一个完整示例

### 6.1 表单填写示例

- `Page`: `catalog`
- `Title`: `商品目录`
- `Requirement`: `商品目录页面展示`
- `Template`: `catalog`
- `Description`: `创建目录页骨架`
- `Priority`: `P1`

### 6.2 提交后会发生什么

服务端会：

1. 根据模板组装 page object 元素
2. 生成标准 smoke case
3. 把资产写入仓库
4. 返回创建结果给控制台

默认会产生两类文件：

- page object：
  - `assets/page-objects/web/<page>.page-object.yaml`
- smoke case：
  - `assets/test-cases/smoke/TC-<PAGE>-001.yaml`

例如：

- [assets/page-objects/web](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/page-objects/web)
- [assets/test-cases/smoke](/Users/bettyhuang/PycharmProjects/ai-test-platform/assets/test-cases/smoke)

## 7. Extra Elements JSON 怎么填

如果你需要给页面额外增加元素，可以在 `Extra Elements JSON` 中填写数组。

示例：

```json
[
  {
    "name": "catalog_search_input",
    "locator_type": "css",
    "locator_value": "input[name='keyword']",
    "description": "商品搜索框"
  },
  {
    "name": "catalog_search_button",
    "locator_type": "role",
    "role": "button",
    "locator_value": "搜索",
    "description": "搜索按钮",
    "smoke_role": "assert"
  }
]
```

字段说明：

- `name`
  - 元素名称
- `locator_type`
  - 支持例如 `css`、`role`
- `locator_value`
  - 定位值
- `role`
  - 当 `locator_type` 是 `role` 时必填
- `description`
  - 可选说明
- `smoke_role`
  - 可选，支持：
    - `menu`
    - `assert`

用途：

- `menu`
  - 表示生成 smoke case 时，这个元素适合用作点击入口
- `assert`
  - 表示生成 smoke case 时，这个元素适合用作等待或断言目标

## 8. Request Preview 怎么看

### 8.1 Request JSON

这是即将发送给后端的请求体。  
如果你想确认是否真的把字段填对了，先看这里。

### 8.2 Diff From Last Request

这里会显示这次请求和上一次成功请求之间的变化。  
适合反复试不同模板或不同页面时查看差异。

### 8.3 Preflight Checks

这是本地校验区，主要用来提前发现明显问题。

当前会检查：

- `page` 是否为空
- `title` 是否为空
- `requirement` 是否为空
- `Extra Elements JSON` 是否是合法数组
- 元素对象是否缺必要字段
- `locator_type=role` 时是否缺 `role`
- `smoke_role` 是否只用了 `menu` 或 `assert`

如果有错误：

- `Confirm Request` 会变成不可点击

## 9. 历史记录怎么用

### 9.1 Favorites

适合存放你反复使用的 scaffold 参数组合。

支持：

- `Favorited`
  - 固定到顶部
- `Alias`
  - 起一个你自己看得懂的名字
- `Run Again`
  - 直接再次发送 scaffold 请求

### 9.2 Recent Scaffolds

适合查看最近操作过的记录。

支持：

- `Reuse This`
  - 回填到表单，但不直接发送
- `Run Again`
  - 不经过重新填写，直接进入预览并可再次提交
- `Copy Test Path`
  - 复制 test case 文件路径
- `Copy Page Object Path`
  - 复制 page object 文件路径
- `Delete`
  - 删除单条历史
- `Clear All`
  - 清空全部本地历史
- `Export JSON`
  - 导出本地历史到文件

## 10. 新手推荐用法

如果你完全不熟悉这个项目，建议按这个顺序操作：

1. 先只使用内置模板，不要填 `Extra Elements JSON`
2. 先成功创建一条最简单的 `catalog` scaffold
3. 看懂生成出来的 page object 和 smoke case 路径
4. 再尝试增加 1 到 2 个额外元素
5. 需要重复创建时，用 `Reuse This` 或 `Run Again`
6. 确认一套参数稳定后，把它 `Favorite`

## 11. 常见问题

### 11.1 页面打不开

优先检查：

- 服务是否已经启动
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) 是否可访问

### 11.2 点了 Create Scaffold 没法提交

说明 `Request Preview` 里的 `Preflight Checks` 发现了错误。  
先修正错误，再提交。

### 11.3 Extra Elements JSON 一填就报错

优先检查：

- 是否是合法 JSON
- 最外层是否是数组 `[]`
- 每个元素是否都带了 `name`
- 是否带了 `locator_type`
- 是否带了 `locator_value`
- `locator_type=role` 时是否带了 `role`

### 11.4 收藏和历史记录为什么换浏览器就没了

因为这些记录保存在当前浏览器的 `localStorage`，不是服务器数据库。

### 11.5 Run Again 和 Reuse This 有什么区别

- `Reuse This`
  - 只是把历史记录回填到表单
- `Run Again`
  - 直接拿这条记录重新发起一次请求

## 12. 对小白最重要的结论

你可以把这个控制台理解成一个“测试资产生成助手”：

- 模板负责给你一套起步骨架
- 表单负责补充页面信息
- 预览负责防止你乱提交
- 历史记录负责减少重复劳动

如果你只记住一条操作路径，记这个就够了：

1. 启动服务
2. 打开 `/console`
3. 选模板
4. 填 `Page`
5. 点 `Create Scaffold`
6. 看预览
7. 点 `Confirm Request`
8. 记录成功后在历史里复用
