# 下一阶段建设路线图（按优先级排期）

## 0. 阅读说明

这份文档更接近“阶段路线图草案”，不是当前实时进度看板。

阅读时请注意：

1. 这里的 `P0/P1/P2` 主要表达建设顺序，不代表今天这些项都还未完成。
2. 其中 `execution_record`、`evidence_manifest`、URL-first review/gate/audit 等内容，当前仓库已不是“未开始”状态，不能再按最初草案理解。
3. 当前真实进度与优先级，优先看：
   - [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](./url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)
   - [../architecture/project-inventory-and-risk-audit-2026-03-21.md](../architecture/project-inventory-and-risk-audit-2026-03-21.md)
   - [../architecture/current-architecture-and-flows.md](../architecture/current-architecture-and-flows.md)

### 当前修正版优先级

结合当前仓库现实，更值得优先推进的是：

1. `data-generation-agent` 最小可用落地
2. 页面分析从“规则模块化”走向“独立编排能力”
3. 测试点依赖治理、低置信度继承和 execution gate 进一步收口
4. 失败来源分类与自愈边界治理

因此，本文后续章节更适合作为“为什么这些方向重要”的路线图背景，而不是直接当作当前 Sprint 排期表。

## 1. 路线图原则

下一阶段建设遵循以下原则：

- 先补平台短板，不重复堆界面
- 先统一模型，再扩功能
- 先让链路标准化，再追求全自动化
- 保持当前已跑通版本稳定

---

## 2. P0：必须优先完成

说明：本节保留的是路线图原始主张，其中一部分已经在当前仓库部分完成或完成，不应逐条理解为“仍未启动”。

## P0-1 结构化测试点中间层

### 目标

把：

`需求 -> YAML`

改成：

`需求 -> 测试点 -> YAML`

### 要做的事

- 定义 `test_point` 数据结构
- 新增测试点生成模块
- 支持从 requirement / OpenAPI / page 生成测试点
- 把 YAML 生成器改成“消费测试点”，而不是直接消费 requirement

### 价值

- 提升生成质量
- 支持覆盖矩阵
- 支持后续批量生成与风险驱动生成

---

## P0-2 统一执行记录模型

当前对齐说明：

- `execution_record` 已经落地并成为当前主链事实源之一。
- 后续重点不再是“是否定义它”，而是继续扩大消费面、减少兼容扫描、完善生命周期治理。

### 目标

不要让 pytest 直接承担平台执行状态中心。

### 要做的事

- 定义统一 `execution_record`
- 包含：
  - run_id
  - case_id
  - project
  - source
  - mode
  - status
  - started_at / finished_at
  - step summary
  - evidence index
- orchestrator / web-ui / report 都统一消费它

### 价值

- 降低对文件扫描的依赖
- 为后续调度、队列、并发做准备

---

## P0-3 统一证据模型

当前对齐说明：

- `evidence_manifest` 已经落地并进入主链。
- 后续重点不再是“是否定义它”，而是继续做 manifest-first 收口、跨 Runner 对齐与产物治理。

### 目标

把截图、HTML、video、analysis、suggestion、healing result 统一成一个 evidence schema。

### 要做的事

- 定义统一 `evidence_manifest`
- runner 直接写 manifest
- orchestrator 和 `web-ui` 直接消费 manifest
- 不再主要靠目录扫描推断证据

### 价值

- 提升稳定性
- 降低展示层复杂度
- 为历史分析做准备

---

## 3. P1：高价值增强

说明：本节里“多输入源、失败聚类、报告治理”依然有效，但优先级要服从当前状态总表，而不是脱离现实独立排序。

## P1-1 多输入源需求接入

### 目标

把需求输入从“手工文本”升级成“多源输入”。

### 要做的事

- OpenAPI 测试点抽取
- Git Diff 变更摘要输入
- 缺陷单输入
- 线上日志输入

### 价值

- 更接近真正的平台入口
- 生成更贴近真实变更和风险

---

## P1-2 失败聚类与风险分析

### 目标

从“单 case AI 分析”升级到“批量失败洞察”。

### 要做的事

- 按 failure category 聚类
- 按模块聚类
- 区分环境失败 / 用例失败 / 应用缺陷
- 风险排序
- flaky 初步识别

### 价值

- 真正支撑回归范围和发布决策

---

## P1-3 报告治理视图

### 目标

让报告更适合管理和决策。

### 要做的事

- run 级趋势页
- 项目级趋势页
- 缺陷闭环进度
- 自愈成功率
- 高风险 case 列表

### 价值

- 从“执行结果页”升级成“质量管理视图”

---

## 4. P2：可扩展能力

## P2-1 统一调度中心

### 要做的事

- 执行队列
- 并发控制
- 资源分配
- 环境池
- 失败重试策略

### 价值

- 真正支撑多项目、多任务执行

---

## P2-2 API / Mobile Runner 对齐

### 要做的事

- API Runner 统一接入
- Mobile Runner 统一接入
- 和 Web Runner 共用执行记录与证据模型

### 价值

- 让平台从 Web 扩展到全类型自动化

---

## P2-3 受治理的自动修复

### 要做的事

- 修复策略等级
- 自动修复白名单
- 修复审批机制
- 修复结果追踪

### 价值

- 让自愈从实验能力变成可管理能力

---

## 5. 推荐排期

说明：这一排期更适合作为历史阶段的建设分组参考；当前实际执行顺序请以状态文档中的“当前推荐优先级”为准。

### 阶段 A

- 测试点中间层
- 统一执行记录模型
- 统一证据模型

### 阶段 B

- OpenAPI / Git Diff 输入接入
- 失败聚类与风险分析
- 报告治理视图

### 阶段 C

- 统一调度中心
- API / Mobile Runner
- 可治理自动修复

---

## 6. 建议的下一步

如果只选一个最值得立刻开始的方向，建议优先做：

### `P0-1 结构化测试点中间层`

原因：

- 这是需求到执行之间最大的断层
- 不补这一层，后面的风险分析、批量生成、回归推荐都不稳

如果要选两个一起推进，建议是：

1. 结构化测试点中间层
2. 统一证据模型

这样可以同时把“生成端”和“执行端”都标准化。
