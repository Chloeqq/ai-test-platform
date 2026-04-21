# 项目目录分层

本文档只描述当前项目里最值得理解的主链目录，不把所有目录都写成同等重要。

## 当前主链目录

### `apps/ai-orchestrator/`

- 当前编排 API 服务。
- 负责 requirement 解析、脚本生成、执行计划、风险评估、失败分诊、自愈预览等接口。
- 真实入口优先看：
  - `src/app.py`
  - `src/orchestrator_service.py`

### `apps/web-ui-service/`

- 当前 Web UI 主服务，FastAPI + TypeScript/React。
- 负责 workbench、generate、history、report、auth、dashboard 等页面入口和 API。
- Workbench 的主编排收口在 `app/api/workbench/facade.py`（唯一编排中心）。
- 关键子目录：
  - `app/routers/`
  - `app/api/`
  - `app/core/`
  - `app/templates/react_app.html`（仅 React 壳）
  - `app/static/react/`（仅 React 构建产物）
  - `frontend/`（TypeScript + React 源码）
  - `app/models/`
  - `app/schemas/`

### `shared_backend/` (仓库根目录)

- 当前共享契约与归一化层（注意：位于仓库根目录，不是 `apps/` 下）。
- `schemas/contracts.py` 是 `PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1 / ExecutionRecordV1 / EvidenceManifestV1` 的关键事实源。
- `schemas/models.py` 定义了共享 Pydantic 模型（`TestPointV1` / `TestPointPlanV1` 等）。
- `schemas/validator.py` 提供 `ContractValidator` 层间校验。
- `execution_compiler.py` 是测试用例编译核心。

### `runners/`

- 执行器层。
- 当前真正成熟的主执行器是 `runners/web-playwright-python/`。
- 其他 Runner 目录存在，但不应等同理解为已同成熟度落地。

### `assets/`

- 当前测试资产主目录。
- 包含：
  - `page-objects/`
  - `test-cases/`
  - `api-contracts/`
  - `business-flows/`
  - `risk-rules/`
  - `test-data-templates/`

### `docs/`

- 当前知识库目录。
- 已按 `architecture / product / onboarding / conventions / testing / api / history` 分层。

## 兼容与运行态目录

### `apps/web-console/`（已退役）

- 历史 scaffold 控制台目录，主链已不再使用。
- 若本地仍有历史拷贝，仅作归档参考，不应作为运行入口。

### `web-ui/`

- 历史兼容与运行态目录。
- 主要承载旧状态、报告和兼容产物，不是当前源码主入口。
- 新功能不建议继续堆在这里。

### `web-ui/state/`

- 运行态状态与缓存目录。
- 包含 `history.json`、`runtime-runs.json`、`reporting/` 等。
- 这是运行产物层，不应当手工维护为长期业务真相。

### `agents/`

- AI Agent 子项目。目录使用连字符命名（`test-design-agent`）以保持 npm/repo 风格一致。
- Agent 内部 Python 包用下划线。运行时通过 `sys.path` 或 `PYTHONPATH` 桥接。
- 当前 Agent：`test-design-agent`、`script-generation-agent`、`data-generation-agent`、
  `self-healing-advisor-agent`、`requirement-parser-agent`。

## 当前理解原则

1. 先看 `apps/web-ui-service` + `apps/ai-orchestrator` + `shared_backend/`（仓库根）+ `runners/web-playwright-python`。
2. 再看 `assets/`，理解平台复用的测试资产。
3. 最后再看 `web-ui/`、`apps/web-console/` 这类兼容或归档层。

## 当前卡点

- 目录虽然逐步清晰，但“主链目录”和“兼容目录”仍共存，容易让新同学误判代码重心。
- `apps/ai-orchestrator/` 和 `apps/web-ui-service/` 中仍有部分目标拆分目录，不应被误读为全部高成熟度实现。

## 下一步优先级

- 保持新增能力优先进入主链目录，而不是继续散落到兼容层。
- 后续如果再做目录治理，优先收敛 `legacy_*` 路由和历史兼容入口，而不是大范围重命名主目录。
