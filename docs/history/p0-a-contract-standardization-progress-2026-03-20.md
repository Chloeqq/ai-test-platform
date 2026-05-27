# P0-A 模型标准化与契约收口进度（2026-03-20）

## 目标
将 `test_points / execution_record / evidence_manifest` 从“各处自由结构”收口为统一的 V1 契约，并在 orchestrator / web-ui / runner 三端落地校验与兼容。

## 已完成
- 共享契约模块落地：`apps/shared_backend/schemas/contracts.py`
  - `TestPointPlanV1`
  - `ExecutionRecordV1`
  - `EvidenceManifestV1`
  - 兼容保留旧字段：`schema_version`（例如 `evidence-manifest.v1`）
- orchestrator 接入共享契约
  - `test_points` 输出统一归一化
  - `execution_record` 生成与加载后统一归一化
  - `evidence_manifest` 生成后统一归一化
  - `risk/evaluate`、`failures/triage` 入参先归一化再处理
- web-ui 接入共享契约
  - `test_points` 持久化文件改为 `TestPointPlanV1`
  - 失败信息聚合改为“manifest 优先读取”
  - 无 manifest 时降级为目录扫描，并记录告警日志（兼容路径）
  - 从 `execution_record.json` 读取时统一归一化
  - `runtime-runs.json` 改为 `execution_record` 主体模型（同时保留旧平铺字段兼容旧前端）
  - `/api/workbench/runs*` 返回统一携带 `execution_record: ExecutionRecordV1`
- runner 接入共享契约
  - `execution_record.json` 输出包含 `ExecutionRecordV1`
  - `evidence_manifest.json` 输出包含 `EvidenceManifestV1`（同时保留 legacy `schema_version`）
  - `report_summary` 读取 manifest 时支持新版 `version` + 旧版 `schema_version`

## 验证结果
- `make test-orchestrator`：`62 passed`
- `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py`：`8 passed`
- `runners/web-playwright-python/tests/test_failure_artifact_config.py` + `test_report_summary.py`：`29 passed`

## 当前收口状态（P0-A）
- 契约定义：`100%`
- 三端接入：`96%`
- 兼容降级与告警：`93%`
- 文档与回归：`96%`

## 剩余工作（建议下一步）
- 在 CI 增加 `EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false` 的严格校验任务，提前发现无 manifest 产物。
- 收敛 `report/latest` 与 `workbench/runs` 的证据读取路径一致性检查，避免多入口语义漂移。

## 当日补齐（2026-03-20 晚间）
- web-ui 报告失败列表新增证据来源可视化
  - `/api/report/failures` 每条记录新增：
    - `evidence_source`：`manifest` / `compat_scan`
    - `manifest_path`：manifest 路径（兼容扫描时为空）
  - `/api/report/failures` 新增 `evidence_meta`：
    - `compat_scan_enabled`
    - `manifest_entry_count`
    - `compat_scan_entry_count`
    - `compat_scan_used_count`
    - `compat_scan_skipped_count`
    - `invalid_manifest_count`
    - `missing_manifest_count`
  - 前端 `report_failures` 页面新增来源标签展示，支持快速识别主路径与回退路径。
  - 新增兼容扫描开关：`EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED`（默认 `true`）。
  - 新增严格校验命令：`make test-webui-manifest-strict`（以 `EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED=false` 运行）。
  - 新增 orchestrator 严格校验命令：`make test-orchestrator-manifest-strict`（以 `EXECUTION_RECORD_COMPAT_BUILDER_ENABLED=false` 运行）。
  - `make test-contracts` 已纳入严格校验，CI 的 `make test` 路径会自动执行该 guardrail。
  - orchestrator 报告新增 `execution_record_meta`，用于标记 execution_record 来源与 strict 违例状态。
- OpenAPI 契约命名收口为 `*V1`
  - `OrchestrationResult.test_points` -> `TestPointPlanV1`
  - `OrchestrationResult.execution_record` -> `ExecutionRecordV1`
  - `ExecutionReport.execution_record` -> `ExecutionRecordV1`
  - `ExecutionReport.evidence` -> `EvidenceManifestV1`
  - 保留 `TestPointPlan / ExecutionRecord / ExecutionEvidenceSummary` 作为兼容别名（ref 到 V1）。
