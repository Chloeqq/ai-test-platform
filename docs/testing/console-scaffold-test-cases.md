# Console Scaffold Test Cases

## 1. 文档目的

本文档列出 `Scaffold Console` 当前版本的核心测试场景，供手工测试、冒烟测试和后续自动化补充使用。

相关文档：

- [Console Scaffold Guide](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/console-scaffold-guide.md)
- [Console Scaffold PRD](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-prd.md)
- [Console Scaffold UX Spec](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-ux-spec.md)

## 2. 测试范围

覆盖范围：

- 模板加载
- 模板切换
- 表单自动填充
- 请求预览
- preflight 校验
- scaffold 创建成功
- scaffold 创建失败
- 历史记录
- 收藏和别名
- 路径复制和导出

不覆盖：

- 真实浏览器跨端兼容细节
- 服务端数据库持久化
- 用户登录鉴权

## 3. 前置条件

执行前需要：

1. 启动服务
2. 打开 `/console`
3. 浏览器允许 `localStorage`

启动命令：

```bash
cd /Users/bettyhuang/PycharmProjects/ai-test-platform
./.venv/bin/python apps/ai-orchestrator/src/main.py serve --host 127.0.0.1 --port 8000
```

## 4. 测试用例

### TC-CONSOLE-001 页面可访问

目标：

- 验证控制台页面可以正常打开

步骤：

1. 打开 [http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)

预期：

- 页面正常加载
- 可看到模板区、表单区和结果区

### TC-CONSOLE-002 模板列表加载成功

目标：

- 验证模板列表成功展示

步骤：

1. 打开控制台
2. 观察模板区

预期：

- 可看到至少一条模板记录
- 状态区出现已加载成功的提示

### TC-CONSOLE-003 选择模板后详情变化

目标：

- 验证点击模板后详情区同步更新

步骤：

1. 点击某个模板
2. 观察 `Template Detail`

预期：

- 详情区显示对应模板内容
- 当前模板卡片高亮

### TC-CONSOLE-004 自动填充推荐字段

目标：

- 验证模板选择后自动填充 `title` 和 `requirement`

步骤：

1. 清空 `Title`
2. 清空 `Requirement`
3. 点击一个模板

预期：

- `Title` 自动填入推荐值
- `Requirement` 自动填入推荐值

### TC-CONSOLE-005 手工修改后不被静默覆盖

目标：

- 验证用户已修改字段时，切换模板不会强制覆盖

步骤：

1. 手工修改 `Title`
2. 切换到另一个模板

预期：

- `Title` 保留手工输入值
- 提示区说明该字段被保留

### TC-CONSOLE-006 Create Scaffold 先进入预览

目标：

- 验证点击创建后先进入请求预览，而不是直接提交

步骤：

1. 填写基础字段
2. 点击 `Create Scaffold`

预期：

- 出现 `Request Preview`
- 未直接创建结果

### TC-CONSOLE-007 Request Preview 展示请求 JSON

目标：

- 验证请求体可见

步骤：

1. 填写表单
2. 点击 `Create Scaffold`

预期：

- 预览中能看到 JSON 请求体

### TC-CONSOLE-008 Request Preview 展示 diff

目标：

- 验证能看到与上一次请求的差异

步骤：

1. 成功创建一次 scaffold
2. 修改 `page` 或 `title`
3. 再次点击 `Create Scaffold`

预期：

- `Diff From Last Request` 区出现差异内容

### TC-CONSOLE-009 缺失必填字段时禁止确认

目标：

- 验证 preflight 拦截必填字段问题

步骤：

1. 清空 `Title`
2. 点击 `Create Scaffold`

预期：

- `Preflight Checks` 显示错误
- `Confirm Request` 不可点击

### TC-CONSOLE-010 非法 JSON 时不允许提交

目标：

- 验证 `Extra Elements JSON` 非法时提示错误

步骤：

1. 在 `Extra Elements JSON` 中输入非法 JSON
2. 点击 `Create Scaffold`

预期：

- 状态区提示解析错误
- 不进入有效提交流程

### TC-CONSOLE-011 role 定位器缺 role 时被拦截

目标：

- 验证 preflight 对元素字段的约束

步骤：

1. 在 `Extra Elements JSON` 中输入：

```json
[
  {
    "name": "search_button",
    "locator_type": "role",
    "locator_value": "搜索"
  }
]
```

2. 点击 `Create Scaffold`

预期：

- `Preflight Checks` 显示错误
- `Confirm Request` 不可点击

### TC-CONSOLE-012 scaffold 创建成功

目标：

- 验证用户可以成功创建资产

步骤：

1. 使用合法表单
2. 点击 `Create Scaffold`
3. 在预览中点击 `Confirm Request`

预期：

- 状态区显示成功
- `Result Summary` 有内容
- `Generated Steps` 有内容
- `Page Elements` 有内容
- `Raw Response` 有内容

### TC-CONSOLE-013 成功后生成历史记录

目标：

- 验证创建成功后历史记录自动产生

步骤：

1. 成功创建一次 scaffold
2. 观察 `Recent Scaffolds`

预期：

- 新记录出现在列表中

### TC-CONSOLE-014 刷新后草稿可恢复

目标：

- 验证表单草稿持久化

步骤：

1. 填写表单但不提交
2. 刷新页面

预期：

- 表单值被恢复

### TC-CONSOLE-015 Reuse This 只回填不提交

目标：

- 验证 `Reuse This` 行为

步骤：

1. 先产生一条历史
2. 点击 `Reuse This`

预期：

- 表单被回填
- 不会直接发送请求

### TC-CONSOLE-016 Run Again 进入预览

目标：

- 验证 `Run Again` 行为

步骤：

1. 先产生一条历史
2. 点击 `Run Again`

预期：

- 进入 `Request Preview`
- 用户可再次确认提交

### TC-CONSOLE-017 Alias 生效

目标：

- 验证别名功能

步骤：

1. 先产生一条历史
2. 点击 `Alias`
3. 输入别名

预期：

- 列表中优先显示别名

### TC-CONSOLE-018 Favorite 置顶

目标：

- 验证收藏记录固定在顶部

步骤：

1. 先产生至少两条历史
2. 对其中一条点击 `Favorite`

预期：

- 该记录出现在 `Favorites`

### TC-CONSOLE-019 Copy Path 可用

目标：

- 验证路径复制动作可执行

步骤：

1. 在某条记录点击 `Copy Test Path`

预期：

- 状态区提示复制成功

### TC-CONSOLE-020 Export JSON 可用

目标：

- 验证历史记录可以导出

步骤：

1. 至少存在一条历史
2. 点击 `Export JSON`

预期：

- 浏览器下载 `scaffold-history.json`

### TC-CONSOLE-021 Delete 删除单条历史

目标：

- 验证单条删除功能

步骤：

1. 历史列表存在多条记录
2. 对一条点击 `Delete`

预期：

- 该记录消失

### TC-CONSOLE-022 Clear All 清空全部历史

目标：

- 验证全量清空功能

步骤：

1. 历史存在多条记录
2. 点击 `Clear All`

预期：

- 历史区显示空态

## 5. 建议执行顺序

建议手工回归按以下顺序走：

1. `TC-CONSOLE-001` 到 `TC-CONSOLE-005`
2. `TC-CONSOLE-006` 到 `TC-CONSOLE-012`
3. `TC-CONSOLE-013` 到 `TC-CONSOLE-018`
4. `TC-CONSOLE-019` 到 `TC-CONSOLE-022`

## 6. 与自动化测试的关系

当前仓库里已有的集成测试主要验证：

- 控制台静态入口是否可访问
- orchestrator API 是否可用
- OpenAPI 契约是否一致

相关文件：

- [test_orchestrate_endpoint.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py)
- [test_openapi_contract.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_openapi_contract.py)

本文档更偏向手工测试和产品验收测试。
