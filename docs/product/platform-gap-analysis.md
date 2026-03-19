# 平台差距分析文档

## 0. 阅读说明

这份文档的定位更接近“平台理想态与现实之间的差距分析”，不是当前事实总表。

阅读时请注意：

1. 这里保留了部分 `web-ui` 时代的描述，因此需要和当前 FastAPI/Web UI 主链分开理解。
2. 当前真实能力状态，优先参考：
   - [../architecture/current-architecture-and-flows.md](../architecture/current-architecture-and-flows.md)
   - [../architecture/project-inventory-and-risk-audit-2026-03-21.md](../architecture/project-inventory-and-risk-audit-2026-03-21.md)
   - [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](./url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)
3. 本文最有价值的部分是“差距仍然在哪里”，而不是“当前到底已经做到了什么”。

> 迁移标注（2026-03-19）  
> 本文档包含 `web-ui` 时代的阶段性描述。当前 Web UI 后端已经迁移到 `apps/web-ui-service/app/*`（FastAPI）。  
> 所有涉及 `web-ui/services/*` 的内容均为历史路径，仅用于回溯，不代表当前代码结构。

## 1. 目标平台定义

当前项目的目标平台链路更适合表述为：

`确定性底座 -> AI 辅助生成/解释 -> 自动执行 -> 报告/证据 -> 治理/门禁`

而不是把所有阶段都理解成“由 AI 主导”。

理想状态下，平台应同时具备以下能力：

- 多输入源理解需求
- 结构化测试点沉淀
- 多 Runner 统一执行
- 标准化证据采集
- 平台级测试报告
- 批量失败聚类与风险分析
- 受控自愈
- 发布门禁与质量治理

---

## 2. 当前已具备的能力

### 2.1 需求到 YAML 生成

当前已具备：

- 基于需求文本生成 YAML 用例
- 固定 smoke 风格约束
- 固定 page-object target 约束
- AI 生成只能复用现有 target

核心代码：

- [agents/test-design-agent/src/agent.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/test-design-agent/src/agent.py)

### 2.2 执行

当前已具备：

- pytest + Playwright 执行 YAML
- `ai-generated` 用例单独执行
- Allure 报告输出

核心代码：

- [runners/web-playwright-python/conftest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/conftest.py)
- [runners/web-playwright-python/runner/yaml_executor.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/yaml_executor.py)
- [runners/web-playwright-python/runner/test_case_loader.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/runners/web-playwright-python/runner/test_case_loader.py)

### 2.3 失败留痕

当前已具备：

- 截图
- HTML
- URL / Title
- 视频
- `analysis.txt`
- `suggestion.json`
- `self_healing_result.json`

补充现实：

- 当前更关键的主事实源已经在向 `execution_record + evidence_manifest` 收口。
- 因此“失败留痕”的核心不再只是文件存在，而是这些证据是否被标准化消费。

### 2.4 AI 分析与建议

当前已具备：

- AI 失败分析
- 自愈建议
- patch preview / apply / rollback
- 有条件的自动修复闭环

核心代码：

- [agents/failure-analysis-agent/analyze.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/failure-analysis-agent/analyze.py)
- [agents/self-healing-advisor-agent/suggest.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/suggest.py)
- [agents/self-healing-advisor-agent/self_healing_orchestrator.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/agents/self-healing-advisor-agent/self_healing_orchestrator.py)

### 2.5 展示层

当前已具备：

- 独立 Web UI
- 报告拆页
- 实时日志
- 失败分析展示
- 缺陷关联占位

核心代码：

- [apps/web-ui-service/app/main.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/main.py)

补充现实：

- 当前主展示层应优先理解为 `apps/web-ui-service`。
- [web-ui/app.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/app.py) 更适合作为兼容入口理解，而不是当前展示主链。

---

## 3. 差距分析

## 3.1 需求输入层差距

### 当前状态

- 主要输入仍是手工 requirement 文本
- 页面粒度依赖手工指定 `page`

### 差距

- 还没有真正接入：
  - PRD 文档解析
  - 原型图解析
  - OpenAPI 自动抽测试点
  - Git Diff 变更影响分析
  - 缺陷单/线上日志反向补测

### 影响

- 需求输入仍然偏人工
- AI 生成的覆盖面依赖输入质量
- 平台还不能真正做到“多输入源驱动”

---

## 3.2 测试设计层差距

### 当前状态

- 需求会直接生成 YAML
- 已有较强稳定命名和 step 约束

### 差距

- 缺少独立的“测试点中间层”
- 没有测试点资产中心
- 没有覆盖矩阵
- 没有优先级/风险驱动生成策略
- 没有“为什么生成这些用例”的结构化解释

### 影响

- 需求到 YAML 跳跃过大
- 难以做真正的平台级测试设计管理

---

## 3.3 执行层差距

### 当前状态

- Web Runner 已可运行
- 通过 pytest + subprocess 驱动

### 差距

- 缺少统一任务模型
- 缺少队列和调度中心
- 缺少并发/资源分配
- 缺少 API / Mobile 同等级 Runner
- 缺少 step 级实时状态流

### 影响

- 当前更像“pytest 封装”
- 还不是统一执行平台

---

## 3.4 证据采集层差距

### 当前状态

- 失败证据比较完整
- Allure 和 artifacts 能保留主要文件
- `execution_record` 与 `evidence_manifest` 已开始成为主事实源

### 差距

- 网络请求证据还不够结构化
- 成功用例缺少足够的统计与沉淀
- 仍存在兼容扫描路径，未完全做到 manifest-first
- 缺少证据生命周期管理
- 缺少按 run / case / project 的统一索引

### 影响

- 留痕已经能用，但还不够平台化

---

## 3.5 报告层差距

### 当前状态

- 已有 `web-ui` 报告页
- 已拆成 overview / failures / context / performance / allure

### 差距

- 报告仍然主要是执行结果视图
- 缺少真正的平台级“批量洞察”
- 缺少跨 run 趋势看板
- 缺少管理者视角的稳定 KPI
- 缺少发布决策层直接可用的摘要结论

### 影响

- 适合排查
- 还不够适合治理和决策

---

## 3.6 AI 分析层差距

### 当前状态

- 已能生成 failure category / cause / risk / recommendation

### 差距

- 输入证据仍偏窄
- 缺少更强的来源解释与置信度依据
- 缺少跨 case 聚类
- 缺少批量风险排序
- 缺少 flaky / 环境问题 / 应用问题的系统性区分

### 影响

- 当前是“单 case 分析”
- 还不是“平台级故障分析”

---

## 3.7 自愈层差距

### 当前状态

- 已具备建议、patch、apply、rerun、rollback
- 有 target 和 confidence 安全约束

### 差距

- 修复能力仍然偏 YAML step / target
- 修复策略覆盖面窄
- 自动闭环默认不能放心大规模开启
- 缺少修复策略中心
- 缺少修复审批、修复治理与追踪

### 影响

- 当前是“受限自愈实验能力”
- 还不是“可治理的自动修复能力”

---

## 4. 最大短板总结

补充口径：

- 这几项短板依然成立，但它们现在要放在“确定性底座优先”的原则下理解。
- 当前最明确的新增 P0 缺口已经转为 `失败来源分类`、测试点中间层和页面语义收口，而不是继续把 `data-generation-agent` 当成空白点。

当前平台最关键的差距，不是单点功能缺失，而是以下三件事还不够强：

### 4.1 缺少结构化测试点中间层

现在更像：

`需求文本 -> YAML`

理想状态应该是：

`需求 / OpenAPI / Diff -> 测试点 -> 测试资产 -> 执行`

### 4.2 缺少统一执行与证据模型

当前：

- pytest
- Allure
- artifacts
- report_summary
- orchestrator report

这些能力都存在，但中间标准模型还不够强。

### 4.3 缺少跨 case、跨 run 的分析与治理层

当前更偏“单 case 可解释”  
未来要补成“批量失败洞察 + 风险决策支持”。

---

## 5. 结论

当前项目已经具备一条可运行的主链：

`需求文本 -> AI 生成 YAML -> pytest/Playwright 执行 -> 失败留痕 -> AI 分析 -> 自愈尝试`

但距离目标平台，还需要重点补强：

- 需求结构化
- 测试点中间层
- 统一执行模型
- 统一证据模型
- 跨 case 风险分析
- 可治理的自动修复

换句话说：

当前项目已经进入“平台雏形阶段”，但还没有进入“平台治理阶段”。
