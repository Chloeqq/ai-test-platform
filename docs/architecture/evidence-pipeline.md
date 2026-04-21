# Evidence Pipeline

本文档描述当前平台证据链的真实结构，重点是 `execution_record` 与 `evidence_manifest` 如何成为统一事实源。

## 当前定位

- 当前证据链不是“报告页面自己扫目录拼出来”，而是正在收口到 `execution_record + evidence_manifest`。
- 这条链是平台确定性的关键部分，因为它直接决定报告、失败分析、历史回显和风险评估是否可信。

## 当前主模型

### `execution_record`

- 版本：`ExecutionRecordV1`
- 作用：
  - 描述 run/case 的标准化运行事实
  - 记录状态、时间、step 摘要、证据索引摘要

### `evidence_manifest`

- 版本：`EvidenceManifestV1`
- 作用：
  - 描述截图、HTML、analysis、suggestion、video、自愈结果、execution record 等证据文件索引
  - 把“证据是什么”从目录扫描升级为结构化清单

两者的归一化入口在：

- [apps/shared_backend/schemas/contracts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/schemas/contracts.py)

## 当前生产者

### Runner

- [runners/web-playwright-python/conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)
  - 当前负责写出 `execution_record.json`
  - 当前负责写出 `evidence_manifest.json`
  - 自愈相关证据会落到 `self_healing_result.json` 并进入 manifest

### Orchestrator

- [apps/ai-orchestrator/src/orchestrator_service.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/src/orchestrator_service.py)
  - 对 runner 产物做补充、归一化和统一透传
  - 在风险评估、失败分诊、报告场景里消费这两类结构

## 当前消费者

### Web UI

- [apps/web-ui-service/app/api/workbench/facade.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/api/workbench/facade.py)
  - run 详情
  - 历史回显
  - 报告概览
  - 失败分析和风险决策

### 报告工具

- [runners/web-playwright-python/tools/report_summary.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/tools/report_summary.py)
  - 优先消费 `evidence_manifest`
  - 兼容缺 manifest 时的回退扫描

## 当前确定性边界

这条链路应完全按确定性系统理解：

- 证据文件生成
- 证据索引归类
- 运行记录版本化
- manifest 优先读取
- strict/compat 策略切换

AI 不应决定：

- 证据是否存在
- 运行状态是否通过
- 哪个文件属于哪类基础证据

## 当前卡点

1. 当前只有 `web-playwright-python` 这条证据链相对成熟，其他 Runner 还没有同等落地。
2. 兼容模式仍然存在，说明还有历史产物未完全收敛到 manifest-first。
3. 生命周期治理、清理策略、冷归档策略仍缺正式平台化文档和工具闭环。

## 下一步优先级

### P0

- 继续坚持 `execution_record + evidence_manifest` 为唯一主事实源。
- 禁止新功能再绕过 manifest 直接拼目录语义。

### P1

- 为 API/Mobile Runner 建立同构证据协议。
- 明确证据清理和保留策略。

### P2

- 做更强的 evidence 索引与检索能力，而不是继续堆散文件。

## 相关配置

- [apps/web-ui-service/app/core/config.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/core/config.py)
  - `EVIDENCE_MANIFEST_POLICY`
  - `EVIDENCE_MANIFEST_COMPAT_SCAN_ENABLED`

## 推荐阅读

1. [current-architecture-and-flows.md](./current-architecture-and-flows.md)
2. [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
3. [apps/shared_backend/schemas/contracts.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/shared_backend/schemas/contracts.py)
4. [runners/web-playwright-python/conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)
