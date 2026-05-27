# docs/rule/ui 当前对齐盘点（2026-04-03）

## 范围
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/ui_design_guidelines_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/ui_design_guidelines_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/list_page_ui_spec_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/list_page_ui_spec_v1.0.md)
- [/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/ai_test_platform_ui_redesign_plan_v1.0.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/rule/ui/ai_test_platform_ui_redesign_plan_v1.0.md)

## 结论
这一轮已经把 `docs/rule/ui` 里最该优先落地的部分真正收进项目里了，重点是：

- 全局导航从“系统内部视角”改成了“用户任务流视角”
- 关键页面都补齐了主操作、工具栏、筛选、刷新、空态、加载态和列表页底部骨架
- 质量分析、资产与配置、执行中心这些最关键页面不再只是各自长成自己的样子，而是开始共享一套 UI 语言和交互结构

当前最准确的判断是：
- 已完成：导航 IA 重组、关键治理页面布局统一、关键列表页工具栏/刷新/空态/分页骨架、页面命名统一第一版
- 已完成：关键治理列表页的高级筛选折叠与筛选条件保留
- 部分完成：所有列表页都使用统一组件、所有页面权限态/错误态一致化
- 未完成：真正的组件级抽象库、权限中心驱动的前端操作控制、全站级列表页批量操作统一实现

## 已做到

### 1. 导航 IA 已改成任务流视角
- 现在的一级导航已经调整为：
  - 仪表盘
  - 用例中心
  - AI生成
  - 执行中心
  - 质量分析
  - 资产与配置
  - 系统管理
- 实现位置：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/ui.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/ui.py)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/_layout.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/_layout.html)

### 2. 页面职责命名已统一第一版
- `工作台` 已明确转为 `调试工作台`
- `生成用例`、`生成历史`、`执行任务`、`执行结果`、`质量门禁` 等命名已和规则文档口径对齐
- `breadcrumb` 也同步切到新信息架构

### 3. 关键列表页布局已补齐
- 以下页面已经补上：
  - 页面标题 + 页面说明
  - 主操作按钮
  - 工具栏
  - 刷新与重置
  - 最后刷新时间
  - 空态 / 加载态 / 错误态
  - 表格底部分页骨架
- 页面包括：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_flaky.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_flaky.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_trends.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_trends.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/gate_console.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/gate_console.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/test_point_assets.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/test_point_assets.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/defects.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/defects.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/scheduler.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/scheduler.html)
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_clusters.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/quality_clusters.html)

### 4. 共享前端格式与分页工具已经成型
- 新增/增强：
  - 时间格式
  - `case_id` 展示格式
  - 统一刷新时间文案
  - 简单分页骨架
- 实现位置：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js)

### 5. 共享页面样式已进一步统一
- 新增了统一的：
  - `page-hero-actions`
  - `toolbar-meta`
  - `selection-bar`
  - `table-footer`
- 实现位置：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/governance_pages.css](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/governance_pages.css)

### 6. 高级筛选折叠与条件保留已落地到关键页面
- 以下页面现在已经支持“默认快捷筛选 + 折叠高级筛选”：
  - `quality_flaky`
  - `test_point_assets`
  - `defects`
  - `quality_trends`
  - `scheduler`
  - `gate_console`
- 同时已支持筛选条件保留：
  - 刷新页面后保留当前筛选
  - URL 查询参数与会话态同步
  - 重置时同时清理筛选状态
- 实现位置：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js)
  - 以及上述页面对应的模板与脚本

## 部分做到

### 1. 列表页统一交互
- 关键页面已经统一
- 但还不是所有列表页都完全收成同一个抽象组件

### 2. 批量操作
- 测试点资产、Flaky、缺陷页已经有选择条和复制类批量动作
- 但还没有把所有页面都补成统一的批量操作栏

### 3. 高级筛选折叠
- 关键治理列表页已经补齐
- 但还没有把所有列表页都统一收成共享组件

## 还没做到

### 1. 组件级 PageHeader / ListPageLayout / FilterBar 抽象
- 目前还是模板 + JS 复用为主
- 还不是严格意义上的组件库

### 2. 权限态统一
- 规则文档里提到的查看 / 编辑 / 审核 / 删除权限态
- 当前没有在所有列表页完整前端化

### 3. 全站列表页完全一致
- 已经先把最高优先级页面统一了
- 但报告页、部分历史页还没有全部切换到同一交互骨架

## 本轮已执行

### U1. 重构导航信息架构
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/ui.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/routers/ui.py)
- 已将导航重组为任务流视角，而不是内部能力堆叠

### U2. 强化共享页面规范样式
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/governance_pages.css](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/governance_pages.css)

### U3. 强化共享格式与分页工具
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/platform_format.js)

### U4. 补齐关键治理页面的列表页骨架
- 更新：
  - `quality_flaky`
  - `quality_trends`
  - `gate_console`
  - `test_point_assets`
  - `defects`
  - `scheduler`
  - `quality_clusters`

### U5. 补 UI 集成回归
- 更新：
  - [/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py)
- 当前已覆盖：
  - 新导航 IA 文案
  - 关键页面 shell
  - 工具栏 / footer / selection bar 等共享骨架
  - 高级筛选折叠入口

## 执行清单

### P0 已执行
- [x] 扫描 `docs/rule/ui` 与当前实现差距
- [x] 调整全局导航 IA 到任务流视角
- [x] 统一关键页面命名与 breadcrumb
- [x] 为最高优先级列表页补齐工具栏、刷新、空态、加载态、分页骨架
- [x] 为关键列表页补齐主操作按钮
- [x] 为关键页面补齐共享样式与刷新时间文案
- [x] 增加 UI 集成回归断言
- [x] 为关键治理列表页补齐高级筛选折叠
- [x] 为关键治理列表页补齐筛选条件保留

### P1 下一步继续做
- [ ] 抽出真正的 `PageHeader / ListPageLayout / FilterBar / EmptyState / ConfirmDialog` 组件层
- [ ] 把报告页、历史页等剩余列表页也完全收进统一交互骨架
- [ ] 将角色权限控制落到前端操作层

### P2 暂不强推
- [ ] 真正的前端组件系统化重构
- [ ] 统一的前端权限中心
- [ ] 列表页全站批量操作矩阵

## 当前建议
就当前项目阶段而言，`docs/rule/ui` 里最值钱的部分已经收了：导航、页面职责、列表页主交互和关键治理页面布局。下一步更合适的方向不是继续做“页面换皮”，而是把这些共性抽成真正的前端组件和权限层。

## 2026-04-03 第二阶段补充

### 已完成
- 导航与页面归属继续收口，补齐了新版 IA 中缺失的高优先级入口：
  - 待审核用例
  - 用例版本
  - Prompt 管理
  - 测试计划
  - 权限与角色
- `AI生成` 主入口已改为 4 步式向导：
  - 第一步：选择方式
  - 第二步：输入内容
  - 第三步：预览候选
  - 第四步：生成完成
- `调试工作台` 继续保留为调试职责，旧 `/ai-orchestration` 已重定向到 `/workbench/generate`，避免重复入口。
- `用例中心` 主列表页已改为“左列表 + 右详情”结构，右侧统一展示脚本摘要、版本、执行与缺陷上下文。
- 新增共享管理页骨架 `management_console.html`，用于承接 `待审核用例 / 用例版本 / Prompt 管理 / 测试计划 / 权限与角色` 这些管理型页面，统一为“左列表 + 右详情”。
- 超阈值页面脚本已拆分：
  - `workbench_generate.js` 从超大单文件收敛为主编排 + shared + wizard 三段
  - `cases.js` 从超大单文件收敛为 cases_api + cases_dialog + cases 主编排三段

### 验证结果
- `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py`：`107 passed`
- `apps/web-ui-service/tests`：`156 passed`
- 全仓：`213 passed`

## 交付验证文档
- 本轮 UI 重构的企业级交付验证结果、手动验证步骤、回滚清单与 lint/typecheck 补齐方案，已单独沉淀到：
  - [2026-04-03-ui-redesign-delivery-validation.md](/Users/bettyhuang/PycharmProjects/ai-test-platform/docs/implementation-plan/2026-04-03-ui-redesign-delivery-validation.md)

## 2026-04-04 `/cases` 单搜索框收敛补充

### 已完成
- `用例中心 / 用例列表` 工具栏进一步收敛为单一可见搜索框，符合“工具页主内容优先、筛选弱化”的页面目标。
- 列表页保留左侧模块树作为结构导航，不再把 `状态 / 优先级 / 测试类型 / 创建人 / 执行结果` 暴露为多组可见下拉筛选器。
- 单搜索框已支持：
  - 模糊搜索：用例 ID / 名称 / 模块 / 产品线 / 创建人
  - 结构化字段搜索：`类型:api`、`状态:启用`、`创建人:qa`、`结果:失败`
- `/cases` 列表新增轻量“当前搜索上下文”区，统一显示搜索框和树定位实际生效的条件，避免单搜索框方案下筛选状态不可见。
- “当前搜索上下文”标签已支持逐项移除，用户可直接点掉某个状态、类型、创建人、执行结果或树定位条件，而不需要手改整串搜索表达式。
- “当前搜索上下文”标题区已补一键清空动作，可直接清掉搜索表达式和树定位，适合复杂组合条件快速回退。
- 已补前端逻辑级自动化测试，覆盖搜索串重建、单项移除、树定位联动清理，以及上下文动作按钮渲染，降低后续 UI 微调时的回归风险。
- 已补最小浏览器级回归，真实验证 `/cases` 的结构化搜索、上下文渲染、树定位联动、树条件移除和一键清空链路。
- 页面层只负责搜索输入与树导航同步；结构化搜索解析下沉到 `app/services/test_case_search_service.py`，避免页面脚本承担业务解析逻辑。

## 2026-04-04 `/cases` 视觉收敛补充

### 已完成
- 工具栏继续去装饰化，移除了没有业务承载的“列表 / 脑图”视图 tabs，保留“单搜索框 + 刷新 + 重置搜索”的标准列表页节奏。
- 左侧模块树和右侧表格进一步减重：
  - 树选中态从高饱和紫色切换为更轻的蓝色定位态
  - 表格 hover、版本号、分页主色统一回到平台主蓝色
  - 行内操作按钮改为轻描边图标按钮，避免操作视觉强度压过主内容
- `状态 / 结果` 单元格由大面积 badge 收敛为“标签名 + 圆点状态”组合，更接近内部工具平台的状态字典表达。
- 浏览器级回归继续补强，已验证移除 `创建人 / 状态 / 执行结果` 搜索上下文后，搜索输入内容会按剩余条件重建，不需要手工回改整串表达式。

### 风险收敛说明
- 本轮只调整 `/cases` 局部模板与样式，没有变更 `/api/test-cases` 或搜索解析契约，后端影响面保持不变。
- `cases.list.css` 本轮同步删除已不再使用的 tabs / 高级筛选遗留样式，避免继续向超阈值样式文件堆积无效代码。

### 风险收敛说明
- 为避免继续膨胀 `test_case_service.py`，本轮没有把搜索语法直接堆入原服务，而是使用独立搜索解析服务承接单一职责。
- 产品线与模块筛选没有新增第二套入口，而是继续复用左树定位，符合“不新增重复入口”的 UI 约束。
- 旧 API 查询参数仍保持兼容；单搜索框解析结果只在未显式传参时补充对应过滤条件。

## 2026-04-03 第三阶段补充

### 已完成
- `失败聚类` 页面已按“一个页面只做一个主任务”继续收束：
  - 主体改为“聚类列表 + 详情 + 分页”
  - quality gate 从并列主表降为右侧辅助洞察
  - 补齐搜索、快捷筛选、排序、刷新、分页、批量复制、空态、加载态、折叠高级筛选
- `生成历史` 页面已从旧式工作台表格收敛为标准列表页：
  - 页面标题区
  - 工具栏
  - 批量操作栏
  - 列表区
  - 右侧详情区
  - 底部分页区
- `workbench_history` 后端接口已补齐兼容式列表查询能力：
  - `keyword`
  - `sort`
  - `page`
  - `page_size`
  - 分页元信息回传
- 超阈值文件已继续拆分，避免继续堆叠：
  - `quality_clusters.js` 拆为 shared / gate / detail / list / main 编排
  - `workbench_history.js` 拆为 detail / support / main 编排
  - `workbench_history_service.py` 拆出 `workbench_quality_gate_summary_service.py`

### 本轮拆分说明
- `quality_clusters`：
  - 拆了哪些职责：
    - 页面通用工具：`quality_clusters.shared.js`
    - 门禁辅助洞察：`quality_clusters_gate.js`
    - 聚类详情与缺陷动作：`quality_clusters_detail.js`
    - 聚类列表、筛选、分页与批量：`quality_clusters_list.js`
    - 页面总编排：`quality_clusters.js`
  - 为什么这样拆：
    - 让主页面文件只保留编排职责
    - 避免“列表行为 / 详情渲染 / 门禁辅助分析”混在一个文件里
- `workbench_history`：
  - 拆了哪些职责：
    - 详情渲染：`workbench_history_detail.js`
    - 筛选状态与登录提示支撑：`workbench_history_support.js`
    - 页面主编排：`workbench_history.js`
    - quality gate 汇总服务：`workbench_quality_gate_summary_service.py`
  - 为什么这样拆：
    - 让历史页前后端都回到单一职责
    - 避免继续在 500+ 行文件上叠加搜索/排序/分页能力

### 继续可收敛方向
- 把 `quality_flaky / defects / scheduler / quality_trends` 进一步抽成真正共享的列表页组件层，而不只是模板 + JS 约定复用。
- 把 `workbench_history` 的动作枚举、筛选字典和排序选项继续沉淀为统一字典配置，减少页面内硬编码。

## 2026-04-03 第四阶段补充

### 已完成
- `用例中心 /cases` 按列表页统一规范继续补齐了可见的管理上下文：
  - 新增 `重置筛选`，支持一键回到默认筛选与默认排序
  - 新增选择态提示条，显示当前已选条数并支持清空选择
  - 新增列表底部元信息，显示当前页条数与最近刷新时间
  - 分页样式改为 `cases` 作用域内局部覆盖，避免共享分页组件被整站联动影响
- `批量废弃` 已补充二次确认，且明确提示“标记为废弃，不做物理删除”，与平台归档治理规则保持一致

### 本轮拆分说明
- `cases` 列表底部与分页样式未继续塞回原 `cases.list.css`
  - 拆了哪些职责：
    - `cases.list.css` 继续负责工具栏与左侧列表主视觉
    - `cases.pagination.css` 单独负责选择态条、列表底部元信息、分页局部覆盖
  - 为什么这样拆：
    - `cases.list.css` 已接近文件阈值
    - 把底部规范样式独立后，更容易继续在不影响列表主体的前提下微调分页和 footer

### 本轮验证结果
- `node --check apps/web-ui-service/app/static/cases.js`：通过
- `node --check apps/web-ui-service/app/static/cases_presenter.js`：通过
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_ui_route_compatibility.py apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py::test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language -q`：`5 passed`

### 后续还能继续收敛的点
- 如果后续继续优化 `/cases`，优先方向应是：
  - 把工具栏快捷筛选、选择态条、分页 footer 抽成共享管理页局部组件
  - 为列表页补真正的“当前筛选上下文 pills”，减少高级筛选折叠后的信息丢失
- 当前不建议做的事：
  - 不建议现在把共享 `pagination.component.css` 做全局大改
  - 不建议把 `cases` 的局部交互继续塞回页面模板，避免再次把页面入口变重

## 2026-04-03 第五阶段补充

### 背景
- 基于参考截图复核后发现，`/cases` 的核心差距已经不是颜色或控件，而是页面主结构不同：
  - 目标参考图是“左侧模块树 + 右侧表格列表”的资产管理页
  - 旧版 `/cases` 仍是“左列表 + 右详情”的工作台式结构
- 如果只继续改样式，无法把页面观感收敛到目标图附近，因此本轮先做骨架换形，再做局部贴近。

### 已完成
- `/cases` 主结构已由“左列表 + 右详情”切换为“左树导航 + 右表格列表”：
  - 左侧模块树支持产品线 / 模块层级
  - 右侧列表区支持表格列展示、批量选择、分页与行内操作
  - 用例详情回归独立详情页 `/cases/{case_id}`
- `/api/test-cases/tree` 已补齐真实计数，支持左树更接近参考图的“分组 + 数量”形态
- `/api/test-cases` 列表项已补齐 `latest_version_no`，用于右表格中的版本列展示
- 搜索已兼容按用例 ID 或名称查询，贴近参考图右上角“根据 ID / 名称搜索”的交互

### 本轮拆分说明
- 页面样式继续拆分，避免重新堆回单文件：
  - `cases.layout.css`：页面头部、左右布局与右侧工作区骨架
  - `cases.tree.css`：左侧模块树、搜索与“更多操作”
  - `cases.list.css`：右侧工具栏、视图 tabs 与高级筛选
  - `cases.panel.css`：表格、状态标签、版本列与行内操作
  - `cases.pagination.css`：选择态条、footer 与分页
- 页面脚本继续拆分，避免主编排文件回涨：
  - `cases.js`：状态、筛选、数据加载与页面编排
  - `cases.table_actions.js`：表格勾选、批量动作、行内标签/废弃动作
  - `cases_presenter.js`：左树与表格渲染

### 为什么这样拆
- 这样拆之后：
  - 主模板 [cases.html](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/templates/cases.html) 保持页面骨架职责
  - 主编排 [cases.js](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/web-ui-service/app/static/cases.js) 维持在 337 行，回到编排文件阈值内
  - 左树、工具栏、表格、分页的 CSS 边界明确，后续继续“贴截图”时可以只动局部

### 本轮验证结果
- `node --check apps/web-ui-service/app/static/cases.js`：通过
- `node --check apps/web-ui-service/app/static/cases_presenter.js`：通过
- `node --check apps/web-ui-service/app/static/cases.table_actions.js`：通过
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_test_case_bootstrap_service.py apps/web-ui-service/tests/unit/test_test_case_mapper.py apps/web-ui-service/tests/integration/test_test_cases_data_config.py apps/web-ui-service/tests/integration/test_ui_route_compatibility.py apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py::test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language -q`：`13 passed`

### 后续还能怎么继续收敛
- 如果继续往参考图靠近，下一步最值的不是再改结构，而是：
  - 把右表格表头排序箭头、列宽和 hover 反馈再细抠
  - 把左树的层级缩进、计数色值和激活态再贴近参考图
  - 为表格补“更多操作”菜单或列设置，而不是再加第二个详情区

## 2026-04-03 第六阶段补充

### 本轮问题定位
- 用户提供当前效果图后复核发现，页面“还是不像”的一个直接原因不是布局方向错了，而是局部样式串掉了：
  - `cases.list.css` 中 `cases-toolbar-advanced summary` 样式块缺少闭合
  - 直接导致工具栏后续规则异常串联，表现为排序框、搜索框、高级搜索入口的层级和宽度失衡

### 本轮已修复
- 修复 `cases.list.css` 样式块闭合问题，并重新收紧工具栏：
  - 排序下拉恢复固定宽度
  - 搜索框恢复右侧主搜索位置
  - `高级搜索` 改为更接近参考图的轻入口样式，而不是厚按钮
- 调整左树文字节奏：
  - 主标题与说明改为上下两行
  - 模块项文字更清晰，避免看起来只剩“模块内用例”这类辅助文案
- 为左树渲染补兼容兜底：
  - 即使 `tree` 接口返回旧式 `modules: ["模块A"]` 结构，也能正确渲染模块名和 fallback 计数
- 补静态资源版本号递增，减少浏览器缓存导致的“代码已修，页面仍像旧版”问题

### 本轮验证结果
- `node --check apps/web-ui-service/app/static/cases_presenter.js`：通过
- `node --check apps/web-ui-service/app/static/cases.js`：通过
- `node --check apps/web-ui-service/app/static/cases.table_actions.js`：通过
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_test_case_bootstrap_service.py apps/web-ui-service/tests/unit/test_test_case_mapper.py apps/web-ui-service/tests/integration/test_test_cases_data_config.py apps/web-ui-service/tests/integration/test_ui_route_compatibility.py apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py::test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language -q`：`13 passed`

### 验证结果
- `apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py + test_ui_route_compatibility.py`：`113 passed`
- `apps/web-ui-service/tests`：`159 passed`
- 全仓：`216 passed`

## 2026-04-05 `/cases` 工具栏与左右权重收敛补充

### 本轮问题定位
- 上一轮虽然已完成单搜索框和状态轻量化，但工具栏仍有常显帮助文案，顶部厚度偏大。
- 左侧树面板在宽屏下占比略高，列表主内容的第一视觉焦点仍然不够稳定。

### 本轮已修复
- `/cases` 搜索语法提示改为默认折叠：
  - 工具栏只保留主动作（搜索、刷新、重置）
  - 语法示例改为 `details` 展开块，符合“高级能力默认折叠”
- 左右布局继续收敛到“主内容优先”：
  - 左树列宽从 `minmax(280px, 320px)` 收敛为 `minmax(248px, 288px)`
  - 中等宽度断点同步收敛为 `minmax(232px, 272px)`
- 左树视觉进一步减重：
  - 树工具区右对齐，减少空置噪声
  - 树面板最小高度下调，避免少量数据时出现大块空白

### 本轮验证结果
- `node --check apps/web-ui-service/app/static/cases.js`：通过
- `node --check apps/web-ui-service/app/static/cases_support.js`：通过
- `node --check apps/web-ui-service/app/static/cases_presenter.js`：通过
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_cases_frontend_support.py -q`：`4 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py -k test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language -q`：`1 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_cases_browser_interactions.py -q`：`1 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_test_case_search_service.py apps/web-ui-service/tests/integration/test_test_cases_data_config.py -q`：`8 passed`

## 2026-04-05 回归修复与静态质量状态补充

### 本轮问题修复
- 修复 `test_case_service` 对外导出回归：
  - 恢复 `get_module_tree_items` 与 `normalize_report_url` 的服务层可见性，避免路由层调用丢失。
- 修复 `workbench_generation.py` 的未使用变量回归：
  - 删除 `case_yaml` 的无效声明与赋值，消除新增 `F841`。

### 本轮验证结果
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_test_cases_data_config.py -q`：`6 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_cases_browser_interactions.py -q`：`1 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_workbench_multisource_endpoints.py -k test_cases_page_removes_duplicate_ai_entry_and_uses_archive_language -q`：`1 passed, 109 deselected`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_cases_frontend_support.py -q`：`4 passed`
- `.venv/bin/python -m pytest apps/web-ui-service/tests/unit/test_test_case_search_service.py -q`：`2 passed`
- `node --check apps/web-ui-service/app/static/cases.js`：通过
- `node --check apps/web-ui-service/app/static/cases_support.js`：通过
- `node --check apps/web-ui-service/app/static/cases_presenter.js`：通过

### 工具链现状（已安装，仍有存量问题）
- `.venv/bin/python -m ruff --version`：`ruff 0.15.9`
- `.venv/bin/python -m mypy --version`：`mypy 1.20.0 (compiled: yes)`
- `.venv/bin/python -m ruff check apps/web-ui-service/app apps/web-ui-service/tests`：`All checks passed!`
- `.venv/bin/python -m mypy apps/web-ui-service/app`：`603 errors in 26 files`

### 本轮静态质量补充
- 已完成 `legacy_workbench.py` 的未使用导入清理，同时保留跨路由复用的 `subprocess` 导出，避免行为回归。
- 已对 `sys.path` 引导导入的测试文件和 `legacy_workbench.py` 增加 `E402` 文件级豁免，明确只在该场景使用。
- `mypy` 低风险收敛已完成一轮：`positive_ids`、`test_case_service` 与 `dashboard` 的 `list/Sequence` 不匹配已修复，基线从 `622 errors in 31 files` 收敛到 `603 errors in 26 files`。

## 2026-04-05 静态质量推进（第二轮）

### 本轮新增修复范围
- `workbench_task_service.py`：新增 `_dict_value/_list_value`，集中修复执行任务视图/汇总路径的大量 `union-attr` 与迭代类型问题。
- `workbench_generation_service.py`：去除重复类型别名，收敛 `dict/list` 访问，放宽异常类注入类型签名以匹配 HTTPException 构造方式。
- `ui_shell_service.py`、`ui_management_console_service.py`：补齐导航与配置聚合的显式类型，清理 `object` 推断误差。
- `page_analysis_pipeline.py`、`workbench_reviews.py`、`apps/shared_backend/case_dictionary.py`、`apps/shared_backend/observability/ai_trace.py`：修复低风险可空结构访问与字典展开类型问题。
- 类型桩补齐：安装 `types-python-jose`、`types-passlib`、`types-PyYAML`。

### 本轮验证快照
- `.venv/bin/python -m ruff check apps/web-ui-service/app apps/web-ui-service/tests`：`All checks passed!`
- `.venv/bin/python -m mypy apps/web-ui-service/app`：`448 errors in 14 files`

### 收敛结果说明
- 本轮将全量 mypy 基线从 `603 errors in 26 files` 进一步收敛到 `448 errors in 14 files`。
- 剩余错误主要集中在：`shared_backend/schemas/contracts.py`、`core/page_analysis_rules.py`、`workbench_analysis_service.py`、`workbench_asset_service.py` 等高复杂度文件，后续建议按“文件分片 + 统一收敛辅助函数”继续推进，避免一次性大改。

## 2026-04-05 静态质量推进（第三轮）

### 本轮新增修复范围
- `apps/shared_backend/schemas/contracts.py`：统一引入 `_dict/_list/_dict_copy`，清理大批量 `union-attr/index/dict-item` 报错。
- `apps/web-ui-service/app/services/workbench_analysis_service.py`：异常类型签名对齐、`exc.detail` 安全访问、测试点/页面对象路径的可空集合收敛。
- `apps/web-ui-service/app/services/workbench_governance_service.py`、`workbench_reporting_service.py`、`workbench_review_service.py`、`workbench_runtime_service.py`：统一 `dict/list` 数据收敛并修复参数类型不匹配。
- `apps/web-ui-service/app/core/pagination.py`、`redis_client.py`、`workbench_orchestrator_service.py`、`workbench_quality_gate_summary_service.py`、`test_case_bootstrap_service.py`：清理剩余小簇类型与 lint 问题。
- `apps/web-ui-service/tests` 的 6 个测试文件：仅修复测试侧类型注解兼容问题，不改变断言语义。

### 本轮验证快照
- `.venv/bin/python -m ruff check apps/shared_backend apps/web-ui-service/app apps/web-ui-service/tests`：`All checks passed!`
- `.venv/bin/python -m mypy apps/web-ui-service/app apps/web-ui-service/tests`：`Success: no issues found in 81 source files`
- `.venv/bin/python -m mypy apps/shared_backend --exclude 'apps/shared_backend/tests'`：`Success: no issues found in 10 source files`

### 收敛结果说明（更新）
- `apps/web-ui-service/app` 的 mypy 已从第二轮的 `448 errors in 14 files` 收敛到 `0 errors`。
- 当前目标范围内 lint/typecheck 均已通过，可作为后续功能迭代的静态质量新基线。

### 回归验证补充
- `.venv/bin/python -m pytest apps/web-ui-service/tests -q`：`170 passed`
- `.venv/bin/python -m pytest -q`：`221 passed`
- `.venv/bin/python -m mypy --explicit-package-bases apps/shared_backend`：`Success: no issues found in 11 source files`
