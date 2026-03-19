# Runners

本文档描述当前仓库里的执行器层现实，而不是“所有 Runner 都已企业级完成”的目标态。

## 当前 Runner 格局

### 已相对成熟

- `runners/web-playwright-python/`
  - 当前最核心、最可落地的执行器。
  - 负责 YAML 驱动的 Web 自动化执行、证据产出、失败分析接入、报告产出。

### 目录存在但成熟度不足

- `runners/api-pytest/`
- `runners/api-restassured/`
- `runners/mobile-appium/`
- `runners/shared-runner-sdk/`

这些目录可以视作扩展方向或预留层，不能按与 `web-playwright-python` 同成熟度理解。

## `web-playwright-python` 当前职责

### 执行动作

- `actions/`
  - `goto`
  - `fill`
  - `click`
  - `assert_visible`
  - `assert_url`
  - `wait_for`
  - `login`

### 执行与注册

- `runner/action_registry.py`
  - 当前动作注册与执行映射入口。

### 证据与报告

- `conftest.py`
  - 执行记录
  - 证据 manifest
  - 失败产物
  - 自愈结果落盘
- `tools/report_summary.py`
  - 汇总报告和证据读取

### 契约

- `schemas/yaml_testcase.schema.json`
  - YAML 用例基础契约

## 当前确定性边界

Runner 层应被视为强确定性系统：

- Playwright 执行
- step 调用
- assertion 裁决
- 超时与重试
- execution record / manifest 落盘

AI 在这一层不应直接负责：

- 决定断言是否通过
- 决定页面是否成功交互
- 改写业务断言逻辑

AI 在当前更适合参与：

- 生成前的脚本建议
- 执行后的失败解释
- 严格受限的 locator/timeout/self-healing 建议

## 当前卡点

1. 多 Runner 生态并未真正统一，当前平台实质上还是“Web Runner 优先”。
2. API 与 Mobile Runner 还不足以承担与 Web 同级别的主链责任。
3. 产物目录较重，生命周期治理仍需要继续加强。

## 下一步优先级

### P0

- 继续把 `web-playwright-python` 当作回归测试主执行器稳住。
- 不要在 API/Mobile Runner 还未成型前，假设平台已经是多执行器对等架构。

### P1

- 为其他 Runner 对齐最小契约：
  - 执行输入
  - execution record
  - evidence manifest
  - 失败分类接口

### P2

- 再做跨 Runner 统一调度和能力矩阵。

## 推荐阅读

1. [current-architecture-and-flows.md](./current-architecture-and-flows.md)
2. [project-inventory-and-risk-audit-2026-03-21.md](./project-inventory-and-risk-audit-2026-03-21.md)
3. [runners/web-playwright-python/PROJECT_DOCS.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/PROJECT_DOCS.md)
