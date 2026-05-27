# URL 驱动一键全自动落地改造方案（2026-03-20）

## 0. 阅读说明

这份文档的定位是：**URL-first 改造的目标态方案文档**。

为了避免把“目标设计”误读成“当前已实现”，阅读时请同时遵守下面这几个边界：

1. 当前真实实现状态，优先看：
   - [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](./url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)
   - [../architecture/current-architecture-and-flows.md](../architecture/current-architecture-and-flows.md)
   - [../architecture/project-inventory-and-risk-audit-2026-03-21.md](../architecture/project-inventory-and-risk-audit-2026-03-21.md)
2. 本文里提到的 `PageAnalysisAgent`、`PageObjectAgent`、`PageSemanticModelV1` 等，有一部分仍属于目标抽象，不等于仓库里已经存在等名独立模块。
3. 本文里的“全自动”必须结合当前平台边界理解为：
   - 确定性底座优先
   - AI 辅助生成与解释
   - 高风险节点保留人工确认
4. 如果本文与代码现实冲突，先以架构审计文档和当前调用链文档为准。

当前更准确的现实定义不是“纯 URL 一键全自动平台”，而是：

**规则优先的 URL 驱动自动化 + AI 语义补充 + 条件式人工确认。**

## 1. 目标定义

目标链路：

`输入页面 URL -> 自动识别页面结构/业务语义 -> 自动生成测试点 -> 自动生成 Page Object -> 自动生成测试用例/YAML -> 自动生成测试代码 -> 自动执行 -> 自动产出测试报告 -> 失败分析/风险评估/自愈建议`

本方案的核心目标不是“再增加几个按钮”，而是把当前以 `requirement` 为主的半自动链路，升级为以 `URL + 页面分析` 为主的真正一键自动链路。

---

## 2. 当前真实现状

## 2.1 已具备的能力

1. Web UI 已有生成页和 `auto-run` 入口，前端可调用 `/api/workbench/auto-run`。
2. Web UI 后端已具备 URL 解析、页面 surface 抽取、Page Object 补齐、YAML 生成、执行、Allure 刷新能力。
3. orchestrator 已接入 8 个专业化 Agent 的编排顺序：
   - `requirement-parser-agent`
   - `test-design-agent`
   - `script-generation-agent`
   - `execution-planner-agent`
   - `risk-evaluation-agent`
   - `failure-analysis-agent`
   - `failure-triage-agent`
   - `self-healing-advisor-agent`
4. `case_id` 后端已支持自动生成，不是必须人工填写。
5. runner 已能执行 YAML，并能输出执行记录、失败证据、Allure 报告。
6. 当前体系更准确的描述不是“纯 URL 一键全自动”，而是“规则优先的 URL 驱动自动化 + AI 语义补充 + 条件式人工确认”。

## 2.2 当前还做不到的点

1. 纯 URL 驱动还不成立。
   - 现在没有 `requirement` 且没有多输入源时，`generate/auto-run` 会直接拦截。
2. 页面理解还停留在 surface 级，不是业务语义级。
   - 当前主要识别 placeholder、按钮文本、菜单标题、表格、表单、弹窗、iframe。
3. 测试点生成仍然严重依赖 requirement 文本。
   - 搜索、筛选、弹窗、审批等场景，很多仍靠 requirement 关键词触发。
4. Page Object 生成还是规则增强，不是完整的 AI 建模。
5. Web 主执行链仍然以 YAML 为准，脚本生成虽存在，但没有成为主执行物。
6. UI 没有把能力组织成“新手可直接操作的一键路径”。

## 2.3 当前能力判断

结论：

当前平台已经具备：

`URL + requirement -> 自动补 page object -> 自动生成 YAML -> 自动执行 -> 自动报告`

但还不具备：

`仅 URL -> 自动理解页面 -> 自动设计测试 -> 自动生成完整用例/代码 -> 自动执行 -> 自动报告`

所以当前状态应定义为：

`半自动可跑通`，而非 `URL 驱动一键全自动`。

补充说明：

- URL 解析、DOM 提取、路由归一化、断言裁决应视为确定性能力。
- 页面语义分类、测试点提炼、风险解释可由 AI 参与，但必须带置信度和审核语义。
- 3 个确认点更适合按条件触发，而不是每次强制出现。

## 2.4 当前实现映射

为了避免“方案词汇”和“仓库模块名”错位，当前建议按下面理解：

| 方案中的能力名 | 当前仓库里的真实实现 |
|---|---|
| `PageAnalysisAgent` | 目前主要由 `apps/web-ui-service/app/core/page_analysis_rules.py` + `page_analysis_pipeline.py` + `legacy_workbench.py` 编排承载 |
| `PageObjectAgent` | 目前主要由 `legacy_workbench.py` 中的页面对象草稿生成与归一化逻辑承载 |
| `PageSemanticModelV1` | 仍以目标模型为主，当前更接近规则初判 + 语义补充，不是稳定独立契约 |
| `review_state` 三确认点 | 已落地，可持久化、回显、即时刷新 |
| `execution_gate` | 已落地，可持久化、人工覆盖、审批、撤销 |
| `risk-evaluation-agent` | 已落地，当前是 agent 优先、规则兜底，仍偏启发式 |
| `Generated Script` 主执行链 | 仍是目标态；当前默认主执行物仍然是 YAML |

---

## 3. 核心差距

## 3.1 产品层差距

1. 主流程不清晰，用户仍被要求理解 requirement、page、source、tags、多输入源。
2. 页面没有“只输 URL 即可启动”的新手模式。
3. 用户看不到系统内部已经具备的自动补齐、自动执行能力。

## 3.2 架构层差距

1. `legacy_workbench.py` 体量过大，URL 驱动逻辑、生成逻辑、执行逻辑、报告逻辑耦合严重。
2. URL 驱动主流程没有形成独立的版本化契约。
3. Page Surface、Page Object、Test Point、Generated Script 之间缺少稳定的中间模型。

## 3.3 Agent 层差距

1. Requirement Parser 还没有把 `URL/page surface` 作为正式输入源。
2. 缺少独立的 `Page Analysis / Page Object Agent`。
3. Test Design Agent 仍然主要从 requirement 出发，不是从页面模型出发。
4. Script Generation Agent 没有真正接入 Web UI 主执行链。
5. Execution Planner Agent 还没有成为 Web 一键执行的中心编排器。

## 3.4 执行层差距

1. 当前执行主物是 YAML，不是生成代码。
2. 缺少“YAML 执行 / 代码执行”双模式策略。
3. 缺少 URL 驱动链路的质量门禁。
4. 缺少当页面分析质量不足时的自动降级策略。

---

## 4. 目标架构

说明：

- 本节描述的是**目标架构**，不是当前已经完全落地的调用链。
- 当前已落地的是 `PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1 / PageAnalysisBundleV1 / review_state / execution_gate`。
- `PageSemanticModelV1`、独立 `PageAnalysisAgent`、独立 `PageObjectAgent` 更适合视为下一阶段要补齐的正式抽象。

推荐目标链路：

`URL Input -> Page Discovery -> Page Semantics -> Test Point Planning -> Page Object Build -> Case/YAML Build -> Script Build -> Execution Planning -> Runner Execute -> Evidence/Report -> Failure Analysis -> Risk Evaluation -> Self Healing`

建议新增和统一的契约：

1. `PageSurfaceV1`
   - 原始页面抽取结果
   - 包含字段、按钮、菜单、标题、表格、表单、弹窗、iframe、稳定性、认证状态
2. `PageSemanticModelV1`
   - 页面业务语义模型
   - 包含业务对象、核心动作、查询区、结果区、表单区、弹窗区、关键约束
3. `PageObjectDraftV1`
   - 页面对象草稿
   - 包含元素、定位器、来源、置信度、稳定性等级
4. `TestPointPlanV1`
   - 统一测试点计划
   - 应包含 `confidence / warnings / requires_review / dependent_elements`
5. `GeneratedCaseBundleV1`
   - 统一生成产物
   - 包含 YAML、脚本、page object、test points、source trace
6. `ExecutionRecordV1`
   - 统一执行状态
7. `EvidenceManifestV1`
   - 统一证据索引
8. `RiskReportV1`
   - 统一风险结论

---

## 5. 一键自动化主流程设计

## 5.1 用户视角主流程

用户输入：

1. 页面 URL
2. 可选补充信息：
   - 业务目标
   - 用户角色
   - 账号信息
   - 约束条件

系统自动完成：

1. 页面访问和登录
2. 页面 surface 抽取
3. 页面语义建模
4. 测试点生成
5. Page Object 生成/补齐
6. YAML 用例生成
7. Playwright 测试代码生成
8. 自动执行
9. 自动产出报告
10. 失败分析与建议

## 5.2 三种运行模式

建议提供三档模式：

1. `Quick Smoke`
   - 纯 URL 驱动
   - 自动生成访问、可见性、查询区、表格区、表单区基础 smoke
   - 用于“先跑起来”
2. `Semantic Auto`
   - URL + 页面语义分析
   - 自动生成核心业务场景、查询、详情、提交流程
   - 作为默认模式
3. `Goal Driven`
   - URL + 用户补充业务目标
   - 面向精确业务测试

默认先落地 `Quick Smoke` 和 `Semantic Auto`。

---

## 6. Agent 协作方案

说明：

- 本节里的 Agent 分工以目标态职责边界为主。
- 当前仓库里，部分职责仍由 `legacy_workbench.py`、`page_analysis_rules.py`、`page_analysis_pipeline.py` 和 orchestrator 共同承担。
- 阅读本节时，不应默认这些 Agent 都已按独立服务形态落地。

## 6.1 Requirement Parser Agent

职责升级：

当前：

- 主要处理 requirement / PRD / OpenAPI / Git Diff / 缺陷单 / 日志

改造后：

- 新增 `page_surface` 作为正式输入源
- 输出 `RequirementSpecV1 + PageSemanticHints`

必须补的能力：

1. 从 `PageSurfaceV1` 推断页面类型
   - 列表页
   - 表单页
   - 详情页
   - 审批页
   - 查询页
   - 弹窗操作页
2. 抽取业务动作
   - 查询
   - 新增
   - 编辑
   - 删除
   - 审批
   - 导出
   - 翻页
3. 抽取测试意图
   - 访问性
   - 查询正确性
   - 表单提交
   - 状态流转
   - 权限限制
4. 输出歧义和低置信度告警
5. 不把 URL 解析、DOM 提取、页面归一化这类工程事实作为 AI 推理项，而是作为确定性输入前置处理

新增输入示例：

```json
{
  "source_type": "page_surface",
  "content": {
    "url": "http://localhost:5173/#/oms/order",
    "page_title": "订单列表",
    "search_placeholder": "订单编号",
    "has_table": true,
    "has_form": false,
    "dialog_titles": []
  }
}
```

## 6.2 新增 Page Analysis Agent

这是 URL 驱动方案里的新增核心 Agent。

当前现实补充：

- 当前已经完成“规则优先页面分析模块化”，但还没完成“独立 PageAnalysisAgent 服务化”。
- 当前最接近它的实现是：
  - `apps/web-ui-service/app/core/page_analysis_rules.py`
  - `apps/web-ui-service/app/core/page_analysis_pipeline.py`

职责：

1. 打开目标 URL
2. 处理登录态
3. 抽取页面原始 surface
4. 识别页面结构分区
5. 生成 `PageSurfaceV1`
6. 生成 `PageSemanticModelV1`
7. 输出稳定性评分和下一步建议
8. 规则优先抽取 page surface，AI 仅用于业务语义和置信度补充

必须实现的能力：

1. DOM 抽取
2. iframe 抽取
3. 弹窗检测
4. 列表/表单/详情/树/分页识别
5. 元素置信度评分
6. SSRF 防护和域名白名单
7. 登录失败/路由偏移/页面未稳定的诊断输出

## 6.3 新增 Page Object Agent

当前现实补充：

- 当前已经完成 `PageObjectDraftV1` 契约收口和页面对象质量归一化。
- 但页面对象生成与合并逻辑仍主要由 workbench 编排层消费，不是独立 Agent 进程。

职责：

1. 消费 `PageSurfaceV1 + PageSemanticModelV1`
2. 自动生成 `PageObjectDraftV1`
3. 与现有 page object 合并
4. 标记：
   - 自动推断元素
   - 默认元素
   - 高风险元素
   - 待人工确认元素
5. 仅允许 locator、timeout、备用 selector 这类自愈修正，不允许改业务断言和业务流程

必须补的能力：

1. 列表页标准元素模板
   - 查询输入框
   - 查询按钮
   - 表格
   - 分页
2. 表单页标准元素模板
   - 字段输入
   - 保存按钮
   - 取消按钮
3. 弹窗页标准元素模板
4. 生成元素描述与来源追踪
5. 生成元素稳定性评分

## 6.4 Test Design Agent

改造方向：

当前：

- 主要从 requirement 文本生成 case/YAML

目标：

- 主要从 `RequirementSpecV1 + PageSemanticModelV1 + PageObjectDraftV1` 生成 `TestPointPlanV1`

必须补的能力：

1. 支持 URL 场景的默认测试点模板
   - 页面可访问
   - 核心区域可见
   - 查询区工作正常
   - 表格结果可见
   - 表单提交可触发
2. 支持按页面类型选择模板
3. 对页面分析低置信度场景输出 coverage gap
4. 输出测试点优先级与依赖关系

## 6.5 Script Generation Agent

职责不变，但要真正进入主流程。

当前现实补充：

- 当前脚本生成能力已经存在，但主执行链默认仍走 YAML。
- 因此这里的重点不是“从零新增脚本生成”，而是“让脚本生成正式成为 URL-first 主流程的一等产物”。

必须补的能力：

1. 消费 `GeneratedCaseBundleV1`
2. 生成 Playwright Python 测试代码
3. 代码与 YAML 一一对应
4. 支持 Web UI 展示：
   - YAML 预览
   - 测试代码预览
   - 当前执行模式

执行策略建议：

1. 默认继续执行 YAML，保证稳定
2. 同时生成脚本并落盘
3. 第二阶段增加“执行生成脚本”开关

## 6.6 Execution Planner Agent

目标：

从“附属信息”升级为“一键执行中心”。

当前现实补充：

- 当前门禁和运行策略已经部分落到 `execution_gate`、`ExecutionPlanV1.gate_check` 和 workbench 编排链里。
- 但还没有完全收束成独立的 Execution Planner 主编排中心。

职责：

1. 决定运行模式
   - yaml-driven
   - script-driven
2. 决定重试策略、超时策略、并发度
3. 根据页面分析质量决定是否允许继续执行
4. 给出执行门禁：
   - allow
   - allow_with_warning
   - manual_review
   - block

## 6.7 Risk Evaluation Agent

职责：

1. 基于执行结果、页面分析质量、测试点覆盖缺口、失败类型、历史缺陷给出风险结论
2. 区分：
   - 页面分析风险
   - 定位器风险
   - 脚本生成风险
   - 业务覆盖风险

## 6.8 Failure Analysis / Failure Triage / Self-Healing

URL 驱动场景下要补的重点：

1. 能区分失败来源：
   - 页面对象错误
   - 页面分析错误
   - 用例设计错误
   - 应用真实缺陷
2. Self-Healing 优先修：
   - 定位器漂移
   - 页面标题变化
   - 查询按钮文案变化
3. 不自动修：
   - 业务流程改变
   - 权限规则改变
   - 核心断言逻辑不成立

---

## 7. 分阶段实施方案

说明：

- 本节是目标推进路线，不是当前进度回放。
- 当前哪些项已经完成、进行到哪一步，请以状态文档为准：
  [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](./url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)

## Phase 0：主流程收口（1 周）

目标：

把“需要输入 requirement”改造成“URL 可直接启动”。

改造项：

1. 生成页删掉 `用例ID`
2. `page`、`title`、`tags` 收到高级模式
3. `requirement` 改为可选
4. 当只有 URL 时，系统自动生成 `system_requirement`
5. 页面顶部增加一键说明：
   - 输入页面 URL
   - 点击一键自动测试
   - 等待测试点、用例、执行、报告自动完成

验收：

1. 仅输入 URL 可以启动 auto-run
2. 后端不再因为 requirement 为空直接报错
3. case_id 自动生成且用户无感

## Phase 1：Page Analysis / Page Object 双 Agent 落地（1-2 周）

目标：

让 URL 输入真正变成高质量页面理解，而不是简单 DOM 扫描。

改造项：

1. 新增 `PageAnalysisAgent`
2. 新增 `PageObjectAgent`
3. 引入 `PageSurfaceV1 / PageSemanticModelV1 / PageObjectDraftV1`
4. 将现有 `_extract_page_surface`、`_enhance_page_object_from_surface` 下沉为 Agent 可复用能力

验收：

1. 列表页、表单页、弹窗页能被正确识别
2. 自动生成的 page object 与页面真实元素匹配度 > 85%
3. 页面分析结果具备置信度和告警字段

## Phase 2：测试点改为页面语义驱动（1 周）

目标：

摆脱 requirement 关键词依赖。

改造项：

1. Requirement Parser 接入 `page_surface`
2. Test Design Agent 改为消费 `RequirementSpecV1 + PageSemanticModelV1`
3. 支持页面类型模板化测试点生成

验收：

1. 不输入 requirement 时也能生成有意义的测试点
2. 搜索页能自动生成查询/结果校验测试点
3. 表单页能自动生成输入/保存/提交测试点

## Phase 3：脚本生成纳入主链路（1 周）

目标：

真正满足“自动生成测试代码”。

改造项：

1. Web UI 展示 `generated_script`
2. 生成结果保存 `GeneratedCaseBundleV1`
3. 增加执行模式：
   - `yaml`
   - `script`
4. 保持默认走 YAML，脚本作为并行产物

验收：

1. 每次生成后都有脚本产物
2. Web UI 可查看脚本
3. 支持脚本试运行

## Phase 4：Execution Planner 成为主编排器（1 周）

目标：

真正统一 URL 驱动的一键调度逻辑。

改造项：

1. 将执行参数、超时、重试、并发统一交给 Execution Planner
2. 将页面分析质量纳入执行门禁
3. 将 coverage gap 纳入最终状态

验收：

1. 执行状态只认 `ExecutionRecordV1`
2. 低质量页面分析可被自动标记 `manual_review` 或 `coverage_gap`
3. Web UI 能看到计划、状态、告警

## Phase 5：风险、失败、自愈治理（持续）

目标：

从“能跑”升级到“可信、可治理”。

改造项：

1. 风险报告引入页面分析质量和覆盖缺口
2. 失败归因区分生成侧失败和应用侧失败
3. 自愈优先处理定位器漂移类问题

验收：

1. 报告可以说明失败是“平台生成问题”还是“应用真实问题”
2. 自愈建议有明确适用范围

---

## 8. Web UI 改造建议

## 8.1 新手模式

只保留：

1. 页面 URL
2. 可选业务目标
3. 一键自动测试

## 8.2 高级模式

收纳：

1. 项目
2. page
3. source
4. tags
5. PRD/OpenAPI/Git Diff/缺陷单/日志
6. 执行模式

## 8.3 结果面板

不要先给黑框日志，先给分步骤状态卡：

1. 页面分析：完成/告警
2. Page Object：完成/缺口
3. 测试点：完成/数量
4. YAML：完成
5. 脚本：完成
6. 执行：通过/失败/覆盖缺口
7. 报告：查看链接

原始日志放折叠区。

---

## 9. 需要优先修改的代码区域

## 9.1 Web UI

1. `apps/web-ui-service/app/templates/workbench_generate.html`
2. `apps/web-ui-service/app/static/workbench_generate.js`
3. `apps/web-ui-service/app/static/workbench.css`

## 9.2 Workbench Router

1. `apps/web-ui-service/app/routers/legacy_workbench.py`

优先拆分：

1. URL 输入处理
2. 页面分析
3. Page Object 生成
4. 生成链路
5. 执行链路
6. 报告链路

## 9.3 Orchestrator

1. `apps/ai-orchestrator/src/orchestrator_service.py`
2. `agents/requirement-parser-agent/src/*`
3. `agents/test-design-agent/src/*`
4. `agents/script-generation-agent/src/*`
5. `agents/execution-planner-agent/src/*`
6. `agents/risk-evaluation-agent/src/*`

---

## 10. 优先级建议

说明：

- 这里是这份方案形成时的原始优先级判断。
- 经过后续实现后，部分 P0 项已经完成或部分完成，当前执行优先级应结合状态文档和风险审计重新判断。

## P0：必须先做

1. requirement 从必填改为可选
2. 仅 URL 可启动 auto-run
3. 删除前端 `用例ID`
4. Web UI 改为新手一键模式
5. 补独立 `PageAnalysisAgent`
6. 补独立 `PageObjectAgent`

理由：

这是“URL 驱动”是否成立的最低前提。

## P1：紧接着做

1. Test Design 改为页面语义驱动
2. 脚本生成进入主链路
3. Execution Planner 接管主执行策略

理由：

这是“自动生成完整用例和代码”是否成立的关键。

## P2：平台治理增强

1. 风险评估增强
2. 批量失败聚类
3. 自愈闭环治理

理由：

这是从“自动化工具”走向“企业级平台”的关键。

---

## 11. 最终判断

如果只做 UI 调整，不改 Agent 和中间模型，平台仍然只能是：

`看起来更易用的半自动平台`

而不是：

`真正 URL 驱动的一键全自动测试平台`

要真正做到你的目标，必须补齐三件事：

1. `URL -> PageSemanticModel` 的正式链路
2. `PageSemanticModel -> TestPointPlan` 的正式链路
3. `Generated Script` 进入主执行链路

只有这样，系统才会从：

`输入 requirement 辅助 URL`

升级到：

`输入 URL，系统自动理解页面并完成测试`

---

## 12. 建议的下一步

如果需要看“现在应该继续做什么”，不应只看本节，而应同时参考：

1. [url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md](./url-driven-oneclick-automation-status-and-priority-plan-2026-03-20.md)
2. [../architecture/project-inventory-and-risk-audit-2026-03-21.md](../architecture/project-inventory-and-risk-audit-2026-03-21.md)

建议按以下顺序推进：

1. 先做 P0：
   - requirement 改可选
   - 用例 ID 自动化
   - 生成页改成新手一键模式
   - 仅 URL 可启动
2. 再做 Page Analysis Agent + Page Object Agent
3. 然后改 Test Design Agent 为页面语义驱动
4. 最后把 Script Generation 和 Execution Planner 真正接进主执行链

这是成本最低、收益最高、也最符合当前代码现状的落地路径。
