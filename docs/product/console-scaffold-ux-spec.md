# Console Scaffold UX Spec

> 状态：归档（2026-04）
> `apps/web-console` 与 `/console` 入口已退役。本文件仅保留历史 UX 设计背景，不再代表当前运行实现。

## 0. 阅读说明

这份 UX 文档描述的是 `Scaffold Console` 的独立交互，不是 URL-first workbench 的页面规范。

阅读时请注意：

1. `/console` 这条入口用于模板发现、请求预览和资产 scaffold 创建。
2. 它不等同于 `apps/web-ui-service` 下的 workbench / generate / history / report 主链页面。
3. 如果要看 URL-first 主链交互，应优先看 URL 改造方案和 Web UI 当前实现。

## 1. 文档目的

本文档描述 `Scaffold Console` 当前版本的页面结构、核心交互、状态变化和用户操作反馈。

适用对象：

- 产品经理
- 研发
- 测试
- 第一次接手该控制台的维护者

相关文档：

- [Console Scaffold Guide](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/console-scaffold-guide.md)
- [Console Scaffold PRD](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/console-scaffold-prd.md)
- [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

## 2. 页面入口（历史）

- 历史地址：`/console`（已退役）
- 历史托管：`apps/ai-orchestrator/src/app.py` 静态托管（已下线）

补充边界：

- 这是 orchestrator 托管的静态控制台入口。
- 它不是 `apps/web-ui-service` 的 workbench 入口，也不消费 review_state / execution_gate 这套治理状态。

静态资源（历史）：

- `apps/web-console/static/*`（已删除）

## 3. 页面结构

页面由以下区块组成：

1. Hero 区
2. Templates 区
3. Template Detail 区
4. Scaffold Request 表单区
5. Request Preview 区
6. Result / Status 区
7. Favorites 区
8. Recent Scaffolds 区
9. Generated Steps 区
10. Page Elements 区
11. Raw Response 区

## 4. 交互说明

### 4.1 首次进入页面

默认行为：

- 页面加载后自动请求模板列表
- 状态区显示 `Loading templates...`
- 加载成功后展示模板卡片
- 如果列表非空，自动选中第一条模板

反馈要求：

- 用户不需要先点任何按钮就能看到模板

### 4.2 点击模板

触发行为：

- 当前模板卡片高亮
- `Template` 字段自动带入模板名
- 详情区加载模板 JSON
- 推荐的 `title` 和 `requirement` 自动写入表单

保护规则：

- 如果用户已经手工改过 `title` 或 `requirement`，模板切换不应静默覆盖

用户反馈：

- `autofill hint` 区显示哪些字段被自动更新，哪些字段被保留

### 4.3 填写表单

关键字段：

- `page`
- `title`
- `requirement`
- `template`
- `description`
- `priority`
- `elements`

约束：

- 表单内容变更后自动保存到本地
- 刷新页面后自动恢复

### 4.4 点击 Create Scaffold

触发行为：

- 不直接发送请求
- 先构造 payload
- 显示 `Request Preview`

如果 payload 构造失败：

- 状态区显示错误
- 不发送请求

### 4.5 Request Preview

该区域必须包含：

- 请求来源
- 变更字段数
- 本地 preflight 检查
- 请求 JSON
- 与上一次请求的 diff
- `Confirm Request`
- `Cancel`

行为要求：

- `Confirm Request` 只有在 preflight 通过时才可点击
- `Cancel` 会关闭预览面板

### 4.6 Confirm Request

触发行为：

- 调用 `POST /assets/scaffold`
- 状态区显示发送中
- 成功后更新结果区和历史区

### 4.7 Scaffold 成功

成功后必须更新：

- `Result Summary`
- `Generated Steps`
- `Page Elements`
- `Raw Response`
- `Recent Scaffolds`
- `last request`

### 4.8 Scaffold 失败

失败时：

- 状态区显示错误
- 已填写表单内容不丢失
- 当前预览内容保留，方便用户修正

## 5. 历史记录区交互

### 5.1 Favorites

展示收藏记录。

每条记录支持：

- `Run Again`
- `Alias`
- `Favorited`
- `Copy Test Path`
- `Copy Page Object Path`
- `Delete`

### 5.2 Recent Scaffolds

展示非收藏记录。

每条记录支持：

- `Reuse This`
- `Run Again`
- `Alias`
- `Favorite`
- `Copy Test Path`
- `Copy Page Object Path`
- `Delete`

### 5.3 历史记录动作差异

- `Reuse This`
  - 回填表单
  - 不直接提交
- `Run Again`
  - 直接生成预览
  - 用户确认后可再次提交

## 6. 视觉和状态约束

### 6.1 模板选中态

- 当前模板卡片必须有明确高亮

### 6.2 收藏态

- 收藏卡片需要明显区别于普通历史

### 6.3 错误态

- preflight 错误项使用错误色块
- 状态区文本必须可读

### 6.4 空态

当没有内容时，相关区块必须显示空态文案，例如：

- `No favorite scaffolds yet.`
- `No scaffold history yet.`
- `No generated steps yet.`
- `No generated elements yet.`

## 7. 本地状态

当前页面使用浏览器 `localStorage` 维护本地状态。

包括：

- 表单草稿
- 最近记录
- 上一次成功请求

这些状态只在当前浏览器中可见。

## 8. 关键风险

### 8.1 Extra Elements JSON 易错

当前仍然要求用户手工输入 JSON，出错概率较高。

### 8.2 历史记录不是服务端共享

换浏览器或清缓存后，历史会消失。

### 8.3 当前仍是单文件脚本

虽然已可用，但后续功能继续增加时，维护成本会升高。

## 9. UX 验收重点

### 9.1 可发现性

- 用户进入页面后能立即理解下一步该做什么

### 9.2 防错

- 用户在点击最终提交前能看到风险和错误

### 9.3 可恢复

- 用户刷新页面后不会丢失表单草稿

### 9.4 可复用

- 用户能从历史记录快速开始下一次 scaffold
