# 用例列表页企业化升级计划（含 AI 生成打通专项）

> 文档版本：v1.0  
> 日期：2026-04-05  
> 目标页面：`/cases`（测试用例列表管理页）

---

## 1. 关键结论

### 1.1 是否打通：AI 自动生成 vs 用例管理

结论：`半打通（UI 入口打通，数据主链未打通）`

- AI 生成链路会产出 YAML + state（资产层）
- 用例列表链路读取的是 `test_cases`（管理主表）
- 缺少“AI 生成后自动 upsert 到管理主表”的默认同步流程

代码证据：

- `apps/web-ui-service/app/services/workbench_generation_service.py`
- `apps/web-ui-service/app/services/workbench_asset_service.py`
- `apps/web-ui-service/app/services/test_case_service.py`
- `apps/web-ui-service/app/services/test_case_mapper.py`
- `apps/web-ui-service/app/static/cases_presenter.js`
- `apps/web-ui-service/app/templates/cases.html`

### 1.2 列表页核心短板

- 列表主键显示仍以自增 `id` 为主，缺标准 `case_id`
- 缺项目维度入口（项目选择、项目创建、项目隔离）  
- “状态 / 结果”混列，信息噪音高
- 缺负责人、来源、自动化状态、用例类型等治理关键字段
- 搜索依赖语法记忆，结构化筛选能力不完整
- 统计与趋势能力不足，无法支撑管理视角

---

## 2. 升级目标（企业级）

1. 统一身份：列表主显示 `case_id`，兼容保留 `id`
2. 统一项目：支持项目切换、项目创建、项目级统计与权限边界
2. 统一视图：状态、结果、优先级、来源、自动化、负责人可独立筛选
3. 统一效率：快捷筛选、批量操作、保存视图
4. 统一治理：统计卡片 + 趋势 + 质量评分入口
5. 统一链路：AI 生成后自动同步到用例管理主表

---

## 3. 需求台账（按你提供的问题清单收敛）

| 编号 | 类别 | 需求项 | 优先级 |
|---|---|---|---|
| 0 | 项目治理 | 项目选择器 + 新建项目入口 | P0 |
| 1 | 信息架构 | 标准用例 ID 显示（`case_id`） | P0 |
| 2 | 信息架构 | 优先级独立列 + 颜色编码 | P0 |
| 3 | 信息架构 | 状态/结果分列 | P0 |
| 4 | 信息架构 | 用例类型标识（sm/rg/fn/e2e） | P1 |
| 5 | 信息架构 | 负责人（Assignee） | P1 |
| 6 | 信息架构 | 自动化状态（Manual/Automated） | P1 |
| 7 | 筛选搜索 | 结构化筛选替代语法记忆 | P1 |
| 8 | 筛选搜索 | 快捷筛选 Tab | P0 |
| 9 | 筛选搜索 | 标签多选 + 排除 | P1 |
| 10 | 筛选搜索 | 时间范围筛选 | P1 |
| 11 | 筛选搜索 | 来源筛选（AI/手工） | P1 |
| 12 | 列表功能 | 批量操作增强 | P1 |
| 13 | 列表功能 | 列自定义（显示/隐藏/排序） | P2 |
| 14 | 列表功能 | 快速预览（抽屉/悬停） | P2 |
| 15 | 列表功能 | 执行历史趋势（迷你图） | P2 |
| 16 | 列表功能 | 覆盖关联（需求 ID） | P1 |
| 17 | 交互操作 | 操作按钮分级（主次分层） | P1 |
| 18 | 交互操作 | 键盘快捷键 | P2 |
| 19 | 交互操作 | 保存视图 | P2 |
| 20 | 交互操作 | 变更订阅/通知 | P3 |
| 21 | 数据统计 | 统计卡片区 | P1 |
| 22 | 数据统计 | 趋势图 | P2 |
| 23 | 数据统计 | 质量评分 | P2 |

---

## 4. 实施计划（并行于中台主计划）

### Phase A（1 天）P0 快速收口

- [ ] 新增项目选择器（当前项目上下文）
- [ ] 新增“创建项目”入口（最小可用：code/name）
- [ ] 显示 `case_id` 并保留 `id` 兼容
- [ ] 状态与结果拆列
- [ ] 优先级独立列和颜色
- [ ] 快捷筛选 Tab（全部/我的/失败/待评审/P0-P1/AI）

验收：

- 列表首屏可在 5 秒内完成风险用例定位

### Phase B（2-3 天）P1 核心体验

- [ ] 顶部统计卡片区
- [ ] 高级筛选（结构化）+ 标签包含/排除 + 时间范围
- [ ] 批量操作增强
- [ ] 自动化状态、来源、负责人字段
- [ ] 覆盖关联列（需求 ID）
- [ ] 项目级统计（当前项目总量、通过率、自动化率）

验收：

- 高频治理操作（筛选+批改+导出）可在 3 步内完成

### Phase C（3-5 天）P2 治理增强

- [ ] 执行趋势迷你图
- [ ] 列自定义
- [ ] 保存视图
- [ ] 快速预览
- [ ] 趋势图与质量评分

验收：

- 可识别 flaky 候选并输出治理清单

### Phase D（并行主线）AI 生成打通专项

- [ ] 建立 AI 生成资产到 `test_cases` 的自动同步服务（upsert）
- [ ] ID 统一策略：`case_id` 为跨域主键，`id` 仅内部兼容
- [ ] 增加来源字段 `source=ai/manual/...`
- [ ] 列表页支持 `source=ai` 的快速筛选与统计
- [ ] 同步时强制携带 `project`，禁止跨项目写入

验收：

- AI 生成完成后，可在 `/cases` 直接按 `case_id` 检索到该用例
- A 项目生成的用例不会出现在 B 项目列表

---

## 5. API 变更要点（列表页）

建议新增/扩展：

- `GET /api/v1/projects` / `POST /api/v1/projects`
- `GET /api/v1/case-management/cases`  
返回 `items + pagination + stats + filters`
- `GET /api/v1/case-management/cases/stats`  
返回统计卡片数据
- `POST /api/v1/case-management/views`  
保存筛选视图
- `POST /api/v1/case-management/cases/sync-from-ai`  
AI 资产同步入口（内部调用）

---

## 6. 验收指标

| 指标 | 目标 |
|---|---|
| 列表首屏加载 | P95 < 1.2s |
| 筛选响应 | P95 < 400ms |
| 批量操作完成率 | ≥ 99% |
| AI 生成同步成功率 | ≥ 99% |
| 数据一致性（AI 资产 vs 管理主表） | ≥ 99.9% |

---

## 7. 关联文档

- [test-case-management-core-execution-plan-spec-aligned-2026-04-05.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/test-case-management-core-execution-plan-spec-aligned-2026-04-05.md)
- [test-case-management-core-gap-tracking-2026-04-05.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/product/test-case-management-core-gap-tracking-2026-04-05.md)

---

## 8. 变更记录

| 日期 | 版本 | 变更内容 | 变更人 |
|---|---|---|---|
| 2026-04-05 | v1.0 | 首版：纳入 23 项列表问题与 AI 打通专项 | Codex |
