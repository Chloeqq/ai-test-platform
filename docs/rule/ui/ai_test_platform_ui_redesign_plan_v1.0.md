# AI自动化测试平台 UI 重构方案 v1.0

**版本**：v1.0  
**目标**：重构信息架构、页面职责、用户路径、页面布局与前端代码结构，解决当前平台“入口重复、页面职责混乱、功能过载、不会用、难扩展”的问题。  
**适用范围**：企业 AI 测试平台 Web 控制台

---

# 1. 当前问题诊断

基于现有界面，当前平台的核心问题不是“UI 不好看”，而是**信息架构与用户路径失控**。

## 1.1 重复入口
当前 AI 相关入口分散在：
- AI编排 / 工作台
- AI编排 / 生成用例
- 工作台中的 AI 生成按钮

结果：
- 用户不知道从哪里开始
- 不同页面边界不清
- 同一动作有多个入口，维护成本高

## 1.2 页面职责过载
“工作台”同时承担：
- 用例列表
- YAML 编辑
- 运行执行
- 生成入口
- 历史查看

结果：
- 一个页面像拼装出来的 IDE
- 新用户无法理解主线
- 开发容易继续叠功能

## 1.3 生成页过重
生成页一次性暴露：
- URL
- PRD
- 用户故事
- Git Diff
- OpenAPI
- JSON
- 文件上传
- 高级参数

结果：
- 表单过载
- 没有默认路径
- 普通用户不知道必须填什么

## 1.4 菜单按“系统内部视角”组织，而不是按“用户任务流程”组织
当前更像：
- 功能堆叠
- 资源堆叠
- 配置堆叠

但用户真正想做的是：

```text
生成用例 → 审核编辑 → 执行运行 → 看结果 → 看质量分析 → 治理优化
```

---

# 2. 重构目标

UI 重构要实现以下目标：

1. **让新用户 3 分钟内知道从哪里开始**
2. **让每个页面只承担一个主任务**
3. **把 AI 生成从“功能集合”改成“引导流程”**
4. **把工作台从“万能页”改成“调试页”**
5. **让左侧导航按任务主线组织**
6. **让前端代码结构和页面职责一一对应**
7. **避免未来继续把功能堆进大页面**

---

# 3. 新的信息架构（IA）

## 3.1 顶层导航重构

建议重构为 6 个一级导航：

```text
1. 仪表盘
2. 用例中心
3. AI生成
4. 执行中心
5. 质量分析
6. 资产与配置
7. 系统管理
```

> 说明：如果你希望一级导航更少，可以把“资产与配置”合并进“系统管理”，但建议先分开，避免配置类内容过重。

---

## 3.2 新导航结构

```text
仪表盘
  - 平台概览
  - 本周重点
  - 待处理事项

用例中心
  - 用例列表
  - 待审核用例
  - 用例版本
  - 标签管理

AI生成
  - 生成用例（主入口）
  - 生成历史
  - Prompt 管理（高级/可选）

执行中心
  - 测试计划
  - 执行任务
  - 执行结果
  - 调试工作台

质量分析
  - Flaky 分析
  - 失败聚类
  - 趋势分析
  - 缺陷管理
  - 质量门禁

资产与配置
  - 页面对象
  - API 契约
  - 测试点资产
  - 数据模板

系统管理
  - 环境管理
  - 节点管理
  - 集成配置
  - 权限与角色
```

---

# 4. 核心用户路径设计

## 4.1 主路径（默认路径）

```text
AI生成 → 用例中心 → 执行中心 → 质量分析
```

用户理解方式：

1. 去 **AI生成** 生成候选用例
2. 到 **用例中心** 审核/编辑/发布
3. 到 **执行中心** 运行
4. 到 **质量分析** 看结果与治理建议

## 4.2 次路径（高级用户）
```text
资产与配置 → AI生成 → 用例中心 → 执行中心
```

适用对象：
- 测试负责人
- 平台管理员
- 高级工程师

## 4.3 调试路径
```text
用例中心 → 调试工作台 → 执行结果
```

适用对象：
- 编写 YAML 的测试工程师
- Debug case 的开发/QA

---

# 5. 页面结构图（线框级）

下面给出可直接用于原型或前端拆分的页面结构图。

---

# 5.1 仪表盘

## 目标
让用户第一眼知道：
- 平台当前状态
- 待处理事项
- 本周重点
- 快捷入口

## 页面结构图

```text
┌────────────────────────────────────────────────────────────┐
│ Header: 企业AI测试平台 / 搜索 / 通知 / 个人菜单              │
├──────────────┬─────────────────────────────────────────────┤
│ Sidebar      │ 页面标题：平台概览                           │
│              ├─────────────────────────────────────────────┤
│ 一级导航      │ KPI 卡片区                                   │
│ 二级导航      │ [待审核用例] [失败任务] [质量风险] [今日执行]   │
│              ├─────────────────────────────────────────────┤
│              │ 本周重点                                     │
│              │ - 待处理高风险任务                            │
│              │ - 需要补齐 manifest                            │
│              │ - 运行异常回归链路                            │
│              ├─────────────────────────────────────────────┤
│              │ 快速开始                                      │
│              │ [生成用例] [查看待审核] [新建执行计划] [看结果] │
│              ├─────────────────────────────────────────────┤
│              │ 最近活动 / 最近执行 / 最近治理建议             │
└──────────────┴─────────────────────────────────────────────┘
```

---

# 5.2 AI生成（主入口页）

## 页面职责
只负责：
- 选择生成方式
- 输入必要信息
- 预览候选用例
- 提交为 Draft

**不负责**：
- 长期管理用例
- 调试执行
- 历史审计详情

## 改造成 4 步 Wizard

### Step 1：选择生成方式

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：AI生成用例                                        │
├────────────────────────────────────────────────────────────┤
│ Step 1 / 4  选择生成方式                                    │
│                                                            │
│ [URL 自动生成] [PRD文档生成] [API生成] [用户故事生成] [自定义] │
│                                                            │
│ 推荐默认：URL 自动生成                                      │
└────────────────────────────────────────────────────────────┘
```

### Step 2：输入内容（按方式动态渲染）

#### URL 模式
```text
┌────────────────────────────────────────────────────────────┐
│ Step 2 / 4 输入内容                                         │
├────────────────────────────────────────────────────────────┤
│ URL 列表（每行一个）                                         │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ /pms/product                                          │ │
│ │ /pms/addProduct                                       │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ 业务目标（可选）                                            │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ 例如：验证页面可访问、查询可用、关键流程可提交            │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ [下一步]                                                    │
└────────────────────────────────────────────────────────────┘
```

#### 高级输入（折叠）
```text
[展开高级输入]
- PRD
- 用户故事
- Git Diff
- OpenAPI
- 失败日志
- JSON 附加源
```

> 原则：**默认只露出必要字段，高级输入折叠。**

### Step 3：预览候选用例

```text
┌────────────────────────────────────────────────────────────┐
│ Step 3 / 4 预览候选用例                                     │
├────────────────────────────────────────────────────────────┤
│ 左侧：候选列表                                              │
│  - ATP-WEB-RET-ORD-SM-AI-0001                               │
│  - ATP-WEB-RET-SUBM-SM-AI-0002                              │
│                                                            │
│ 右侧：当前候选详情                                           │
│  - 标题                                                     │
│  - 页面 / 模块 / 类型 / 来源                                │
│  - 步骤                                                     │
│  - 预期结果                                                 │
│  - 标签                                                     │
│                                                            │
│ [编辑] [删除] [返回修改输入] [确认生成草稿]                  │
└────────────────────────────────────────────────────────────┘
```

### Step 4：生成完成

```text
┌────────────────────────────────────────────────────────────┐
│ Step 4 / 4 生成完成                                         │
├────────────────────────────────────────────────────────────┤
│ 已生成 8 条 Draft 用例                                      │
│                                                            │
│ [去用例中心审核] [继续生成] [查看生成历史]                    │
└────────────────────────────────────────────────────────────┘
```

---

# 5.3 用例中心 / 用例列表

## 页面职责
只负责：
- 查找用例
- 编辑用例
- 审核用例
- 发布用例
- 版本查看

## 页面结构图

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：用例中心                                          │
├────────────────────────────────────────────────────────────┤
│ 顶部筛选栏                                                  │
│ [项目] [页面] [模块] [类型] [来源] [状态] [标签] [搜索]      │
├────────────────────────────────────────────────────────────┤
│ 批量操作栏                                                  │
│ [批量审核] [批量打标] [批量废弃] [导出]                      │
├────────────────────────────────────────────────────────────┤
│ 主体两栏布局                                                │
│                                                            │
│ 左：用例列表                                                │
│ - case_id                                                  │
│ - 标题                                                     │
│ - 页面/模块                                                 │
│ - 类型/来源/优先级                                           │
│ - 更新时间                                                 │
│                                                            │
│ 右：详情抽屉 / 详情面板                                      │
│ - 基本信息                                                 │
│ - 步骤 / 预期                                              │
│ - YAML / 结构化数据                                         │
│ - 版本记录                                                 │
│ - 审核记录                                                 │
│                                                            │
│ 操作： [保存] [提交审核] [发布] [去调试工作台]               │
└────────────────────────────────────────────────────────────┘
```

---

# 5.4 用例审核页

## 页面职责
只负责审核，不承担完整编辑管理。

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：待审核用例                                        │
├────────────────────────────────────────────────────────────┤
│ 左：待审核列表                                              │
│ 右：审核详情                                                │
│  - AI 输入来源摘要                                           │
│  - 生成依据（URL/PRD/API）                                   │
│  - 结构化字段校验结果                                         │
│  - 差异视图（若是已有用例新版本）                              │
│                                                            │
│ 底部操作： [通过] [驳回] [退回修改] [标记需人工补全]          │
└────────────────────────────────────────────────────────────┘
```

---

# 5.5 调试工作台（重做后的 Workbench）

## 页面职责
只负责：
- 单条用例调试
- YAML 查看/编辑
- 执行 run
- 看当前执行日志与断言结果

**不负责**：
- 生成入口
- 大规模列表管理
- 历史总览

## 页面结构图

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：调试工作台 / 当前用例：ATP-WEB-RET-ORD-SM-AI-0001  │
├────────────────────────────────────────────────────────────┤
│ 顶部信息条                                                  │
│ case_id / 标题 / 页面 / 模块 / 版本 / 状态                   │
├───────────────────────┬────────────────────────────────────┤
│ 左侧：结构化信息        │ 右侧：YAML 编辑器                  │
│ - 步骤                 │ ---------------------------------- │
│ - 预期                 │ YAML内容                            │
│ - 标签                 │                                    │
│ - 最近运行结果摘要      │                                    │
│                        │                                    │
├───────────────────────┴────────────────────────────────────┤
│ 底部执行区                                                   │
│ [保存] [Run Test] [查看日志] [查看快照] [打开执行结果详情]    │
└────────────────────────────────────────────────────────────┘
```

---

# 5.6 执行中心 / 测试计划

## 页面职责
- 创建计划
- 绑定套件或用例
- 指定环境
- 发起执行

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：测试计划                                          │
├────────────────────────────────────────────────────────────┤
│ 左：计划列表                                                │
│ 右：计划详情                                                │
│ - 计划名称                                                 │
│ - 绑定套件 / 用例                                            │
│ - 环境                                                     │
│ - 执行策略（串行/并发/重试）                                 │
│                                                            │
│ 操作：[保存] [发布执行] [查看历史运行]                        │
└────────────────────────────────────────────────────────────┘
```

---

# 5.7 执行中心 / 执行任务

## 页面职责
- 看运行中的任务
- 过滤失败/超时
- 重试/取消

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：执行任务                                          │
├────────────────────────────────────────────────────────────┤
│ 筛选栏：[状态] [环境] [计划] [时间范围] [搜索 run_id]         │
├────────────────────────────────────────────────────────────┤
│ 表格                                                        │
│ run_id | 计划 | 状态 | 环境 | 开始时间 | 持续时间 | 操作       │
│                                                            │
│ 操作：[查看详情] [取消] [重试] [查看结果]                    │
└────────────────────────────────────────────────────────────┘
```

---

# 5.8 执行中心 / 执行结果详情

## 页面职责
- 看单次 run 的详细结果
- 查看步骤、断言、截图、日志
- 发起缺陷

```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：执行结果详情                                      │
├────────────────────────────────────────────────────────────┤
│ 顶部摘要：通过数 / 失败数 / 跳过数 / flaky 提示               │
├────────────────────────────────────────────────────────────┤
│ 左：结果树                                                  │
│ - case 1                                                   │
│ - case 2                                                   │
│                                                            │
│ 右：当前用例结果                                            │
│ - 执行步骤                                                 │
│ - 断言结果                                                 │
│ - 错误消息                                                 │
│ - 截图 / DOM / Trace                                       │
│                                                            │
│ [创建缺陷] [加入待分析] [复制 trace_id]                      │
└────────────────────────────────────────────────────────────┘
```

---

# 5.9 质量分析

## 页面职责
- 聚合，不做执行
- 给治理建议，不做编辑

建议拆为 4 个页面：
- Flaky 分析
- 失败聚类
- 趋势分析
- 质量门禁

### Flaky 页面结构
```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：Flaky 分析                                        │
├────────────────────────────────────────────────────────────┤
│ KPI：Top Flaky 数 / 影响模块数 / 最近7天波动                │
├────────────────────────────────────────────────────────────┤
│ 左：Top Flaky 列表                                          │
│ 右：趋势图 + 建议动作                                       │
│                                                            │
│ 动作：[查看相关用例] [加入治理任务] [进入执行记录]            │
└────────────────────────────────────────────────────────────┘
```

### 失败聚类页面结构
```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题：失败聚类                                          │
├────────────────────────────────────────────────────────────┤
│ 聚类卡片：人工复核数 / 热点原因 / 待确认数                   │
├────────────────────────────────────────────────────────────┤
│ 左：聚类列表                                                │
│ 右：聚类详情                                                │
│ - 错误共性                                                 │
│ - 关联 run                                                 │
│ - 关联 case                                                │
│ - 建议归因                                                 │
└────────────────────────────────────────────────────────────┘
```

---

# 5.10 资产与配置

这里建议按“资产中心”统一风格做管理页，不再像散落的资源页。

## 共用布局模板
```text
┌────────────────────────────────────────────────────────────┐
│ 页面标题                                                    │
├────────────────────────────────────────────────────────────┤
│ 顶部筛选 + 搜索 + 新建                                      │
├────────────────────────────────────────────────────────────┤
│ 左：对象列表                                                │
│ 右：对象详情 / 编辑                                          │
└────────────────────────────────────────────────────────────┘
```

适用于：
- 页面对象
- API 契约
- 测试点资产
- 数据模板

---

# 6. 页面职责矩阵

| 页面 | 主职责 | 不负责 |
|------|--------|--------|
| 仪表盘 | 总览、入口 | 深度编辑 |
| AI生成 | 生成 Draft | 执行、长期管理 |
| 用例中心 | 管理/审核/发布 | 执行编排 |
| 调试工作台 | 单用例调试 | 批量管理、生成 |
| 测试计划 | 编排计划 | 结果分析 |
| 执行任务 | 任务监控 | 深度编辑 |
| 执行结果 | 看运行结果 | 管理资产 |
| 质量分析 | 聚合分析 | 直接修改用例 |
| 资产与配置 | 管理基础资产 | 执行运行 |

---

# 7. UI 交互原则（必须执行）

## 7.1 一页一主任务
每个页面只能有一个主动作，不能再“顺便”承担别的流程。

## 7.2 默认路径优先
默认场景优先展示，专家功能折叠。

## 7.3 渐进式披露
高级参数、专家配置、附加输入都必须折叠，不能首屏全开。

## 7.4 统一右侧详情面板模式
管理型页面统一采用：
- 左列表
- 右详情

## 7.5 统一状态样式
统一颜色语义：
- Draft：灰
- Review：黄
- Ready：绿
- Deprecated：浅灰
- Failed：红
- Running：蓝
- Warning：橙

## 7.6 统一空状态
每页必须有明确空状态，带下一步引导：
- 去生成
- 去审核
- 去创建计划
- 去配置环境

---

# 8. 前端代码结构（重构后）

以下代码结构是与 UI 结构一一对应的。

```text
src/
  app/
    router/
      routes.tsx
    layout/
      AppShell.tsx
      Sidebar.tsx
      Topbar.tsx
    providers/
      QueryProvider.tsx
      AuthProvider.tsx

  pages/
    dashboard/
      DashboardPage.tsx

    cases/
      CaseListPage.tsx
      CaseReviewPage.tsx
      CaseVersionPage.tsx

    ai-generation/
      AIGenerationPage.tsx
      GenerationHistoryPage.tsx
      PromptManagePage.tsx

    execution/
      PlanListPage.tsx
      RunListPage.tsx
      ResultDetailPage.tsx
      WorkbenchPage.tsx

    quality/
      FlakyPage.tsx
      FailureClusterPage.tsx
      TrendPage.tsx
      QualityGatePage.tsx

    assets/
      PageObjectPage.tsx
      ApiContractPage.tsx
      TestPointPage.tsx
      DataTemplatePage.tsx

    system/
      EnvironmentPage.tsx
      NodePage.tsx
      IntegrationPage.tsx
      RolePermissionPage.tsx

  modules/
    cases/
      components/
        CaseFilterBar.tsx
        CaseListTable.tsx
        CaseDetailPanel.tsx
        CaseStatusTag.tsx
        CaseReviewActions.tsx
      hooks/
        useCaseFilters.ts
        useCaseList.ts
        useCaseDetail.ts
        useCaseReview.ts
      services/
        case.api.ts
        case.service.ts
        case.mapper.ts
      schemas/
        case.schema.ts
      types/
        case.types.ts
      constants/
        case.constants.ts
      store/
        case.store.ts

    ai-generation/
      components/
        GenerationMethodSelector.tsx
        GenerationInputForm.tsx
        GenerationAdvancedPanel.tsx
        GenerationPreviewList.tsx
        GenerationPreviewDetail.tsx
        GenerationWizardFooter.tsx
      hooks/
        useGenerationWizard.ts
        useGenerationInput.ts
        useGenerationPreview.ts
      services/
        generation.api.ts
        generation.service.ts
        generation.mapper.ts
      schemas/
        generation.schema.ts
      types/
        generation.types.ts
      constants/
        generation.constants.ts
      store/
        generation.store.ts

    execution/
      components/
        PlanTable.tsx
        RunTable.tsx
        ResultTree.tsx
        ResultSummaryCard.tsx
        WorkbenchHeader.tsx
        WorkbenchYamlEditor.tsx
        WorkbenchRunPanel.tsx
      hooks/
        usePlanList.ts
        useRunList.ts
        useResultDetail.ts
        useWorkbench.ts
      services/
        execution.api.ts
        execution.service.ts
        execution.mapper.ts
      schemas/
        execution.schema.ts
      types/
        execution.types.ts
      constants/
        execution.constants.ts
      store/
        execution.store.ts

    quality/
      components/
        FlakyList.tsx
        FlakyTrendChart.tsx
        FailureClusterList.tsx
        GovernanceSuggestionCard.tsx
      hooks/
        useFlakyAnalysis.ts
        useFailureClusters.ts
        useQualityTrend.ts
      services/
        quality.api.ts
        quality.service.ts
        quality.mapper.ts
      schemas/
        quality.schema.ts
      types/
        quality.types.ts

    assets/
      components/
        AssetListPanel.tsx
        AssetDetailPanel.tsx
        AssetSearchBar.tsx
      hooks/
        useAssets.ts
      services/
        assets.api.ts
        assets.service.ts
      schemas/
        assets.schema.ts
      types/
        assets.types.ts

  components/
    common/
      PageHeader.tsx
      EmptyState.tsx
      StatusTag.tsx
      SearchInput.tsx
      FilterBar.tsx
      DetailDrawer.tsx
      ConfirmDialog.tsx

    charts/
      TrendLineChart.tsx
      DistributionChart.tsx

  services/
    http/
      client.ts
      errorHandler.ts
      request.ts

  schemas/
    common/
      pagination.schema.ts
      response.schema.ts

  types/
    common/
      api.types.ts
      ui.types.ts

  utils/
    formatDate.ts
    buildQuery.ts
    downloadFile.ts

  constants/
    route.constants.ts
    status.constants.ts
    color.constants.ts
```

---

# 9. 页面与模块映射关系

| 页面 | 主要模块 |
|------|----------|
| DashboardPage | dashboard |
| CaseListPage | cases |
| CaseReviewPage | cases |
| AIGenerationPage | ai-generation |
| GenerationHistoryPage | ai-generation |
| PlanListPage | execution |
| RunListPage | execution |
| ResultDetailPage | execution |
| WorkbenchPage | execution |
| FlakyPage | quality |
| FailureClusterPage | quality |
| TrendPage | quality |
| PageObjectPage | assets |
| ApiContractPage | assets |

---

# 10. 关键组件拆分建议

## 10.1 AI 生成页必须拆分
不能再用一个页面组件装所有表单。

建议至少拆为：

```text
AIGenerationPage
  ├─ GenerationMethodSelector
  ├─ GenerationInputForm
  ├─ GenerationAdvancedPanel
  ├─ GenerationPreviewList
  ├─ GenerationPreviewDetail
  └─ GenerationWizardFooter
```

## 10.2 工作台必须拆分
```text
WorkbenchPage
  ├─ WorkbenchHeader
  ├─ WorkbenchYamlEditor
  ├─ WorkbenchRunPanel
  ├─ ResultSummaryCard
  └─ RunLogDrawer
```

## 10.3 用例页必须拆分
```text
CaseListPage
  ├─ CaseFilterBar
  ├─ CaseListTable
  ├─ CaseDetailPanel
  ├─ CaseReviewActions
  └─ CaseVersionTimeline
```

---

# 11. 路由建议

```ts
/dashboard

/cases
/cases/review
/cases/:caseId/versions

/ai-generation
/ai-generation/history
/ai-generation/prompts

/execution/plans
/execution/runs
/execution/results/:runId
/execution/workbench/:caseId

/quality/flaky
/quality/failure-clusters
/quality/trends
/quality/gates

/assets/page-objects
/assets/api-contracts
/assets/test-points
/assets/data-templates

/system/environments
/system/nodes
/system/integrations
/system/roles
```

---

# 12. 状态管理建议

## 12.1 页面局部状态
放在页面 hook 中：
- 当前筛选项
- 当前 tab
- 展开/收起
- 当前选中记录

## 12.2 业务共享状态
放在模块 store 中：
- 当前生成草稿缓存
- 当前 case 详情缓存
- 执行结果当前树节点
- 质量分析筛选上下文

## 12.3 不建议全局 store 堆叠所有页面状态
避免再次形成“大一统页面状态垃圾场”。

---

# 13. 重构实施顺序（建议）

## Phase 1：先改 IA 和导航
目标：
- 重构菜单
- 合并重复入口
- 统一页面命名

优先级：最高

## Phase 2：先重做 AI生成页
目标：
- 改成 4 步向导
- 高级参数折叠
- 结果预览拆分

优先级：最高

## Phase 3：瘦身工作台
目标：
- 去掉生成能力
- 只保留调试相关

## Phase 4：重做用例中心
目标：
- 管理/审核分层
- 右侧详情面板统一

## Phase 5：统一执行中心与质量分析页样式
目标：
- 左列表右详情
- 统一状态标签
- 统一空态与操作栏

---

# 14. 最小可用版本（MVP）

如果你不想一次性大改，建议先做这 4 个动作：

1. **合并 AI 入口，只保留“AI生成”一个一级入口**
2. **把生成页改成 4 步向导**
3. **把工作台降级为“调试工作台”**
4. **把用例库改名为“用例中心”，增加审核页**

只做这 4 件事，体验就会明显改善。

---

# 15. 给 Codex / 前端团队的执行规则

```text
1. 不允许再新增重复入口。
2. 一个页面只允许一个主任务。
3. AI生成页必须使用分步式向导，不允许把所有输入一次性铺开。
4. 工作台只做调试，不做生成。
5. 管理类页面统一采用“左列表 + 右详情”结构。
6. 所有高级参数默认折叠。
7. 页面与模块目录必须一一对应，不允许跨层堆逻辑。
8. 新页面必须先标注页面职责，再开始实现。
9. 单页面文件超过 300 行必须拆分。
10. UI 重构必须先改信息架构，再改视觉样式。
```

---

# 16. 最终结论

当前平台最核心的问题不是“组件不好看”，而是：

- 信息架构按系统内部组织，而不是按用户任务组织
- 页面边界混乱
- 生成、管理、调试、执行被揉在一起
- 高级能力直接暴露给普通用户
- 前端代码结构很容易继续跟着页面混乱一起失控

这次 UI 重构的关键不是换个皮肤，而是：

1. **按用户路径重构导航**
2. **按主任务重构页面职责**
3. **按模块边界重构前端目录**
4. **按可维护性拆分组件与 hooks**

只有这样，UI 才会真正“清楚、能用、能扩展”。

---

**文档结束**
