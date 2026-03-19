# Web Console

> 边界说明：
> 当前 `apps/web-console` 对应的是 `Scaffold Console` 这条并行产品线。
> 它主要负责模板驱动的测试资产 scaffold 创建，不等同于 `apps/web-ui-service` 下的 URL-first workbench 主链。

当前 `apps/web-console` 不是完整的前端工程，而是一个由 `ai-orchestrator` 直接托管的静态控制台。

目录说明：

- [index.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/static/index.html)
  控制台页面入口
- [styles.css](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/static/styles.css)
  控制台样式
- [app.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-console/static/app.js)
  模板浏览、scaffold 表单、最近记录、收藏和导出逻辑

## 使用方式

从仓库根目录启动 orchestrator：

```bash
./.venv/bin/python apps/ai-orchestrator/src/main.py serve --host 127.0.0.1 --port 8000
```

然后打开：

- [http://127.0.0.1:8000/console](http://127.0.0.1:8000/console)

如果你是第一次使用，先看：

- [Console Scaffold Guide](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/onboarding/console-scaffold-guide.md)

## 当前能力

- 浏览 scaffold 模板列表和详情
- 自动填充推荐 `title` / `requirement`
- 创建 page object + smoke case scaffold
- 预览生成步骤、页面元素和原始响应
- 请求预览、diff 对比和本地 preflight 校验
- 保存本地表单草稿
- 保存最近记录、收藏、导出 JSON
- 从历史记录直接复用或重新执行 scaffold

## 不负责的能力

- URL 访问后的页面分析
- review_state 三确认点
- execution_gate / 风险决策
- run 历史、失败分析、报告治理主链

## 静态检查

仓库根目录提供最小前端语法检查：

```bash
make check-console
```

等价于：

```bash
node --check apps/web-console/static/app.js
```

## 边界

- 当前没有打包器、TypeScript、组件框架或独立 dev server
- 静态资源由 `ai-orchestrator` 的 [app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/app.py) 直接挂载
- 如果后续要演进成独立前端应用，需要再引入正式构建链路
