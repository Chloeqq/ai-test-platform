# API

这一目录放 API 规格和平台接口约定。

## 先分清接口来源

当前接口并不只来自一套系统：

- `Scaffold Console` / orchestrator 资产脚手架接口
- URL-first workbench / report / review / gate 接口

因此，这个目录里的“已写成人类说明文档的 API”和“当前真实主链 API”不是完全同一集合。

## 推荐阅读顺序

1. [console-scaffold-api-spec.md](./console-scaffold-api-spec.md)
2. 当前主链接口源码入口：
   - [legacy_workbench.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/legacy_workbench.py)
   - [app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/app.py)
   - [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

## 当前口径

- 当前这目录里唯一完整的人类 API 说明文档是 `console-scaffold-api-spec.md`，它对应的是并行的 Scaffold Console 产品线。
- URL-first 主链 API 目前更适合直接以源码和架构文档为准，尤其是：
  - `/api/workbench/auto-run`
  - `/api/workbench/runs/*`
  - `/api/workbench/reviews`
  - `/api/workbench/execution-gate/*`
  - `/api/report/*`
  - `/requirements/parse`
  - `/scripts/generate`
  - `/execution/plan`
  - `/risk/evaluate`
  - `/failures/triage`
- 如果后续平台 API 逐渐稳定，建议优先补一份“URL-first / workbench API 总表”，而不是继续让读者只靠路由源码理解。
