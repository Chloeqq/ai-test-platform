# Contributing

## 测试要求

提交代码前，至少执行：

```bash
make install-dev
make test
```

如果改动跨越 `apps/agents/runners` 多模块，建议额外执行：

```bash
make static-baseline
```

本地快速迭代时可以先运行：

```bash
make static-baseline-fast
```

说明：当前 CI 在 `pull_request/push` 默认执行 `make static-baseline`，本地提前执行可避免命令口径不一致导致的回归。

如果改动涉及以下内容，要求额外检查：

- `assets/test-cases/`
- `assets/page-objects/`
  - 提交前会由 pre-commit 自动执行资产契约测试
- `apps/ai-orchestrator/src/app.py`
- `apps/ai-orchestrator/src/orchestrator_service.py`
- `apps/ai-orchestrator/openapi/orchestrator-openapi.yaml`
  - 需要确保 HTTP 实现、README、OpenAPI 契约保持一致

## Orchestrator API 变更规则

如果修改了 `GET /health` 或 `POST /orchestrate` 的以下任意内容：

- 请求字段
- 返回字段
- 状态码
- 错误码

必须同步更新：

1. [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)
2. [apps/ai-orchestrator/README.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/README.md)
3. `apps/ai-orchestrator/tests/integration/` 下对应的 pytest 测试

不允许只改实现、不改 OpenAPI 契约。

## E2E 测试规则

默认开发流程不要求每次都跑 E2E。

推荐策略：

- 改静态资产、schema、契约：跑 `make test`
- 改真实页面交互：跑 `make test-e2e-smoke`
- 改 AI 生成链路：跑 `make test-e2e-generated`
