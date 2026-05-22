# 前端详情页统一设计系统规范

更新时间：2026-05-09

适用范围：AI 自动化测试平台所有“下钻详情页”和“详情抽屉”，重点覆盖用例详情页、待审核用例详情页、页面对象详情页、测试点资产详情页。

关联规范：

- `docs/core/frontend_visual_typography_system.md`
- `docs/core/frontend_breadcrumb_rules.md`
- `docs/core/frontend_list_governance_rules.md`
- `apps/web-ui-service/frontend/src/styles.css`
- `apps/web-ui-service/frontend/src/pages/TestCaseDetailPage.tsx`
- `apps/web-ui-service/frontend/src/pages/CasesReviewPage.tsx`
- `apps/web-ui-service/frontend/src/pages/PageObjectElementsPage.tsx`
- `apps/web-ui-service/frontend/src/pages/TestPointAssetDetailPage.tsx`

## 1. 设计目标

详情页是平台里“看清事实、做出操作、追溯来源”的核心场景。当前多个模块已经具备详情能力，但存在类名分散、字体层级不一、卡片结构不一致的问题。

本规范的目标是建立一套可复用的详情页视觉系统：

- 用统一的 `.detail-page` 承载所有独立详情页。
- 用统一的 `.detail-hero` 承载标题、状态、来源、关键操作。
- 用统一的 `.detail-section` 承载业务信息分组。
- 用统一的 `.detail-field` 承载字段名和字段值。
- 用统一的 `.detail-code` / `.detail-table` 承载技术信息、脚本、日志、定位器。
- 让用例详情、待审核详情、页面对象详情、资产详情看起来像同一个企业级产品，而不是不同页面拼接。

## 2. 当前问题诊断

### 2.1 命名体系分散

当前已有命名包括：

- 用例详情：`case-hero-card`、`case-hero-title`、`case-info-grid`、`case-steps-table`
- 待审核详情：`review-detail-drawer`、`review-detail-card`、`review-detail-label`
- 页面对象详情：`element-detail-page`
- 测试点资产详情：`asset-detail-panel`、`asset-summary-strip`、`test-point-detail-table`

问题：

- 每个页面都在自己定义“标题卡片、字段卡片、表格、状态标签”。
- 后续改字体、间距、边框时需要多处维护。
- 用户在不同详情页之间切换时，视觉节奏会轻微跳变。

### 2.2 信息层级不统一

典型表现：

- 有的详情页把主标题放在 `h2`，有的直接在卡片内部用普通 `strong`。
- 字段名有时是 `12px / 700`，有时是普通正文。
- 技术字段有时用普通字体，有时用等宽字体。
- 操作按钮在不同页面的位置和优先级不一致。

### 2.3 详情页和详情抽屉缺少统一关系

待审核用例详情目前是抽屉，而用例详情、页面对象详情、资产详情是独立页面。两者形态不同，但内部信息结构应该一致：

- 都有标题区。
- 都有状态与来源。
- 都有关键字段。
- 都有内容分组。
- 都有技术字段或操作历史。

因此需要统一“内容结构”，再允许“容器形态”不同。

## 3. 设计原则

### 3.1 一页一主标题

每个详情页只允许一个视觉主标题，使用 `.detail-title`。

规范：

- 页面主标题：`20px / 700 / #141414`
- 详情页顶部的全局页面标题仍可保持 `24px / 700`
- 区块标题不超过 `18px / 600`

### 3.2 操作分层明确

顶部操作区必须分层：

- 主操作：执行用例、保存、生成用例、通过审核。
- 次操作：再次生成、查看资产、查看报告、返回列表。
- 危险操作：删除、废弃、驳回，默认不使用实心红，除非在确认弹窗中。

### 3.3 业务信息和技术信息分区

业务信息用 UI 字体，技术信息用等宽字体。

业务信息：

- 标题、前置条件、步骤说明、预期结果、审核状态。

技术信息：

- `case_id`
- `intent_id`
- `asset_id`
- `page_code`
- `element_code`
- `locator`
- URL
- YAML / JSON / Python / Playwright 脚本
- 日志和堆栈

### 3.4 详情页以“扫读”为第一目标

详情页不是文章页，而是管理系统的事实页。设计上应支持快速扫读：

- 字段名短、弱化。
- 字段值清晰、可复制、可换行。
- 关键状态用标签。
- 表格列不要过多高亮。
- 长脚本默认折叠或放在专门代码区。

## 4. 统一结构

### 4.1 独立详情页标准结构

```text
┌─ detail-page ─────────────────────────────────────────────────────┐
│ detail-toolbar                                                     │
│ ← 返回列表                                  [主操作] [次操作] [危险] │
│                                                                    │
│ detail-hero                                                        │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ detail-title-row                                                │ │
│ │ 主标题 20/700                                      [状态 Tag]    │ │
│ │ detail-subtitle / detail-meta 13/400 mono or muted              │ │
│ │ detail-description 14/400                                       │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ detail-grid                                                        │
│ ┌ detail-field ┐ ┌ detail-field ┐ ┌ detail-field ┐ ┌ detail-field ┐ │
│ │ 字段名 12/600│ │ 字段名       │ │ 字段名       │ │ 字段名       │ │
│ │ 字段值 14/600│ │ 字段值       │ │ 字段值       │ │ 字段值       │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                                    │
│ detail-section                                                     │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ 区块标题 18/600                                                  │ │
│ │ 正文、表格、步骤、代码、历史记录                                  │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### 4.2 详情抽屉标准结构

```text
┌─ detail-drawer ───────────────────────────────────────────────┐
│ detail-drawer-header                                           │
│ ← 返回列表 / 上一条下一条                         [× 关闭]       │
├────────────────────────────────────────────────────────────────┤
│ detail-drawer-body                                             │
│ detail-alert 可选                                              │
│ detail-action-card 可选                                        │
│ detail-hero compact                                            │
│ detail-section                                                 │
│ detail-section                                                 │
│ detail-code collapsible 可选                                   │
├────────────────────────────────────────────────────────────────┤
│ detail-drawer-footer                                           │
│ [次操作]                                      [主操作] [下一条] │
└────────────────────────────────────────────────────────────────┘
```

抽屉与独立页面的差异：

- 抽屉宽度建议 `min(920px, 92vw)`。
- 抽屉中的 `.detail-hero` 使用 compact 版本，减少高度。
- 抽屉底部可固定操作栏。
- 抽屉内容应避免过深嵌套，代码块默认折叠。

## 5. 统一 Class 设计

### 5.1 页面容器

```css
.detail-page
.detail-page--case
.detail-page--review
.detail-page--page-object
.detail-page--asset
```

用途：

- 所有独立详情页根容器。
- 控制页面最大宽度、上下间距、背景和阅读节奏。
- 业务类型修饰符只用于少量模块差异，不改变核心字体层级。

建议：

```css
.detail-page {
  display: grid;
  gap: 16px;
  max-width: 1440px;
  margin: 24px auto;
  padding: 0 16px 40px;
  color: var(--text-body);
  font-family: var(--font-ui);
}
```

### 5.2 顶部工具栏

```css
.detail-toolbar
.detail-toolbar-main
.detail-toolbar-actions
```

用途：

- 放返回、面包屑、主操作、辅助操作。
- 保证所有详情页操作位置一致。

规范：

- 工具栏高度不固定，由内容撑开。
- 返回按钮在左侧。
- 主操作靠右，并排在危险操作之前。
- 移动端操作自动换行。

### 5.3 标题卡片

```css
.detail-hero
.detail-hero--compact
.detail-title-row
.detail-title
.detail-subtitle
.detail-description
.detail-meta
```

用途：

- 展示当前对象的“身份”。
- 承载标题、编码、状态、来源、简短说明。

字体：

| 元素 | 字号 | 字重 | 颜色 | 说明 |
| --- | ---: | ---: | --- | --- |
| `.detail-title` | `20px` | `700` | `#141414` | 详情对象标题 |
| `.detail-subtitle` | `13px` | `400` | `#64748b` | 编码、版本、来源 |
| `.detail-description` | `14px` | `400` | `#475569` | 简短业务说明 |
| `.detail-meta` | `13px` | `400` | `#64748b` | 时间、创建人、项目 |

技术类 subtitle 需加 `.detail-mono`。

### 5.4 字段网格

```css
.detail-field-grid
.detail-field-grid--2
.detail-field-grid--3
.detail-field-grid--4
.detail-field
.detail-field--wide
.detail-field-label
.detail-field-value
.detail-field-help
```

用途：

- 展示页面、类型、优先级、状态、版本、创建时间、更新时间、测试地址等结构化字段。

规范：

- 默认四列。
- 中等屏幕降为两列。
- 小屏幕降为一列。
- URL、locator、脚本 ID 等长值必须允许换行。

字体：

| 元素 | 字号 | 字重 | 颜色 |
| --- | ---: | ---: | --- |
| `.detail-field-label` | `12px` | `600` | `#64748b` |
| `.detail-field-value` | `14px` | `600` | `#141414` |
| `.detail-field-help` | `13px` | `400` | `#64748b` |

### 5.5 内容区块

```css
.detail-section
.detail-section-header
.detail-section-title
.detail-section-desc
.detail-section-actions
.detail-section-body
```

用途：

- 前置条件、操作步骤、预期结果、涉及元素、执行历史、审核历史、脚本源码、覆盖矩阵等。

规范：

- 区块标题：`18px / 600`
- 区块说明：`13px / 400`
- 区块正文：`14px / 400`
- 区块之间间距：`12px` 到 `16px`
- 不同区块使用统一边框、圆角、背景。

### 5.6 技术文本

```css
.detail-mono
.detail-code
.detail-code-header
.detail-code-body
.detail-url
.detail-locator
.detail-id
```

用途：

- 承载编码、URL、locator、脚本源码、日志。

规范：

- 字体：`var(--font-mono)`
- 字号：`13px`
- 字重：`400`
- 行高：`1.5`
- 背景：`#f6f8fa`
- 边框：`#e1e4e8`
- 圆角：`8px`
- 代码块内边距：`16px`

### 5.7 表格

```css
.detail-table-wrap
.detail-table
.detail-table--steps
.detail-table--elements
.detail-table--history
```

用途：

- 操作步骤表。
- 元素绑定表。
- 执行历史表。
- 审核历史表。

规范：

- 表头：`12px / 600 / #475569`
- 表格正文：`14px / 400 / #262626`
- 编码和定位器列：`13px / 400 / var(--font-mono)`
- 表头背景：`#f8fbff`
- 分割线：`#edf2fa`
- 行高：`44px` 到 `52px`

### 5.8 状态与提示

```css
.detail-status
.detail-status--success
.detail-status--warning
.detail-status--danger
.detail-status--neutral
.detail-alert
.detail-alert--warning
.detail-alert--danger
.detail-empty
```

状态标签规范：

- 字号：`12px`
- 字重：`600`
- 圆角：`999px`
- 内边距：`4px 10px`
- 使用浅底深字。

提示区规范：

- 警告：浅黄底。
- 阻断/危险：浅红底。
- 成功：浅绿底。
- 普通说明：浅蓝灰底。

## 6. 四类详情页映射

### 6.1 用例详情页

页面定位：查看单条自动化用例的完整信息、步骤、脚本源码、执行历史。

统一结构：

```text
detail-page detail-page--case
├─ detail-toolbar
├─ detail-hero
│  ├─ detail-title: 用例标题
│  ├─ detail-subtitle detail-mono: case_id / version
│  ├─ detail-status: 活跃 / 已废弃
│  └─ detail-description: 用例说明
├─ detail-field-grid
│  ├─ 页面
│  ├─ 测试地址
│  ├─ 类型
│  ├─ 优先级
│  ├─ 来源资产
│  ├─ 创建时间
│  ├─ 更新时间
│  └─ 上次执行
├─ detail-section: 测试步骤与预期
├─ detail-section: 涉及元素绑定
├─ detail-section: 执行历史
└─ detail-section: 脚本源码
```

关键视觉要求：

- `case_id`、版本号、测试地址使用 `.detail-mono`。
- “执行用例”是主操作。
- “废弃用例”是危险操作，默认描边或二次确认后实心。
- 脚本源码默认折叠，展开后使用 `.detail-code`。

### 6.2 待审核用例详情

页面定位：审核者快速查看单个测试点完整信息，并做通过/驳回。

统一结构：

```text
detail-drawer detail-page--review
├─ detail-drawer-header
├─ detail-alert: 阻断信息，可选
├─ detail-action-card: 通过 / 驳回 / 上一条 / 下一条
├─ detail-hero detail-hero--compact
│  ├─ detail-title: 测试点标题
│  ├─ detail-subtitle detail-mono: intent_id
│  └─ detail-status: 待审核 / 已通过 / 已驳回
├─ detail-field-grid
│  ├─ 所属资产
│  ├─ 页面
│  ├─ 类型
│  └─ 优先级
├─ detail-section: 前置条件
├─ detail-section: 操作步骤
├─ detail-section: 预期结果
├─ detail-section: 涉及元素绑定
├─ detail-section: 审核历史
└─ detail-section: 生成脚本预览，可选
```

关键视觉要求：

- 抽屉顶部和底部均可放审核操作，但主操作位置保持靠右。
- 阻断信息使用 `.detail-alert--warning` 或 `.detail-alert--danger`。
- “测试点未审核通过”属于流程阻断，使用 warning。
- “页面 URL 未配置 / 元素缺失”属于生成阻断，使用 danger 或 warning，视是否可通过补配置解决。

### 6.3 页面对象详情页

页面定位：查看页面对象与元素资产，维护 URL、正式元素、候选元素、别名、定位器和引用关系。

统一结构：

```text
detail-page detail-page--page-object
├─ detail-toolbar
├─ detail-hero
│  ├─ detail-title: page_code / 页面名称
│  ├─ detail-subtitle detail-mono: project/client/page_code
│  ├─ detail-status: URL 已配置 / 未配置 URL
│  └─ detail-description: 页面对象说明
├─ detail-field-grid
│  ├─ 项目
│  ├─ 客户端
│  ├─ 页面 URL
│  ├─ 元素数量
│  ├─ 已审核元素
│  └─ 最后更新
├─ detail-section: 正式元素
├─ detail-section: 候选元素
├─ detail-section: 元素语义与别名
└─ detail-section: 引用关系
```

关键视觉要求：

- `page_code`、`element_code`、locator 使用 `.detail-mono`。
- 页面 URL 未配置时，在 `.detail-hero` 内显示警告状态。
- 元素表格的 locator 列允许换行，并使用等宽字体。
- 页面对象详情必须支持从列表页独立下钻，不使用隐藏弹窗替代详情页。

### 6.4 测试点资产详情页

页面定位：查看测试点资产包全貌、审核状态、覆盖矩阵和生成入口。

统一结构：

```text
detail-page detail-page--asset
├─ detail-toolbar
├─ detail-hero
│  ├─ detail-title: 资产标题
│  ├─ detail-subtitle detail-mono: asset_id
│  ├─ detail-status: 资产状态 / 生成状态
│  └─ detail-description: 来源需求和生成说明
├─ detail-field-grid
│  ├─ 项目
│  ├─ 页面
│  ├─ 测试点总数
│  ├─ 待审核
│  ├─ 已通过
│  ├─ 已驳回
│  └─ 可生成数量
├─ detail-section: 测试点明细
├─ detail-section: 覆盖矩阵
├─ detail-section: 生成结果
└─ detail-section: 资产元数据
```

关键视觉要求：

- 资产详情页是高密度表格页，表格主体保持 `14px / 400`。
- 测试点标题列可使用 `14px / 600`。
- 审核状态和可生成状态使用统一 `.detail-status`。
- `intent_id`、`asset_id` 使用 `.detail-mono`。

## 7. 视觉原型稿

### 7.1 通用独立详情页

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ detail-toolbar                                               ┃
┃ ← 返回列表                                      [主操作] [更多] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-hero                                                  ┃
┃ ┌──────────────────────────────────────────────────────────┐ ┃
┃ │ 首次登录成功                                  [活跃]       │ ┃
┃ │ TC-LOGIN-0007 / v1                                      │ ┃
┃ │ 验证输入正确账号密码后可以成功登录并跳转至工作台首页          │ ┃
┃ └──────────────────────────────────────────────────────────┘ ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-field-grid                                            ┃
┃ ┌────────────┬────────────┬────────────┬────────────┐       ┃
┃ │ 页面        │ 类型        │ 优先级      │ 测试地址     │       ┃
┃ │ login      │ 功能        │ P0         │ http://... │       ┃
┃ └────────────┴────────────┴────────────┴────────────┘       ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-section                                               ┃
┃ 测试步骤与预期                                                ┃
┃ ┌──┬────────────────────┬──────────┬──────────────┐          ┃
┃ │1 │ 打开登录页面          │ goto     │ http://...    │          ┃
┃ │2 │ 在用户名输入框输入     │ input    │ test001       │          ┃
┃ │3 │ 点击登录按钮          │ click    │ login_button  │          ┃
┃ └──┴────────────────────┴──────────┴──────────────┘          ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-section                                               ┃
┃ 脚本源码                                           [展开]      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 7.2 通用详情抽屉

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ← 返回待审核列表                    [× 关闭] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-alert                                 ┃
┃ ⚠ 生成阻断：请到页面对象管理补齐页面 URL       ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-action-card                            ┃
┃ [驳回]                         [通过] [下一条] ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-hero compact                           ┃
┃ 登录时模拟弱网超时                 [待审核]    ┃
┃ intent-22 / 登录页身份验证测试点集             ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-field-grid                             ┃
┃ 页面 login | 类型 交互异常 | 优先级 P2         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ detail-section 前置条件                        ┃
┃ detail-section 操作步骤                        ┃
┃ detail-section 预期结果                        ┃
┃ detail-section 涉及元素绑定                    ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ [关闭]                         [通过] [下一条] ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## 8. 字体与间距规范

### 8.1 字体层级

| 场景 | Class | 字号 | 字重 | 颜色 |
| --- | --- | ---: | ---: | --- |
| 详情主标题 | `.detail-title` | `20px` | `700` | `#141414` |
| 详情副标题 | `.detail-subtitle` | `13px` | `400` | `#64748b` |
| 详情说明 | `.detail-description` | `14px` | `400` | `#475569` |
| 区块标题 | `.detail-section-title` | `18px` | `600` | `#141414` |
| 字段名 | `.detail-field-label` | `12px` | `600` | `#64748b` |
| 字段值 | `.detail-field-value` | `14px` | `600` | `#141414` |
| 正文 | `.detail-section-body` | `14px` | `400` | `#262626` |
| 辅助说明 | `.detail-field-help` | `13px` | `400` | `#64748b` |
| 技术字段 | `.detail-mono` | `13px` | `400` | `#475569` |
| 状态标签 | `.detail-status` | `12px` | `600` | 状态色 |

### 8.2 间距

| Token | 建议值 | 用途 |
| --- | ---: | --- |
| `--detail-gap-xs` | `6px` | 字段内部间距 |
| `--detail-gap-sm` | `8px` | 标签与值、按钮间距 |
| `--detail-gap-md` | `12px` | 卡片内部模块间距 |
| `--detail-gap-lg` | `16px` | 区块之间间距 |
| `--detail-gap-xl` | `24px` | 顶部大区块间距 |

### 8.3 圆角、边框、阴影

| 对象 | 圆角 | 边框 | 阴影 |
| --- | ---: | --- | --- |
| `.detail-hero` | `14px` | `#e5ecf8` | `0 8px 24px rgba(15, 76, 129, 0.06)` |
| `.detail-section` | `12px` | `#e5ecf8` | 轻阴影或无阴影 |
| `.detail-field` | `12px` | `#e7eef9` | 无 |
| `.detail-code` | `8px` | `#e1e4e8` | 无 |
| `.detail-drawer` | `16px 0 0 16px` | `#dce6f4` | `0 12px 32px rgba(15, 23, 42, 0.12)` |

## 9. 交互规范

### 9.1 返回与下钻

- 所有列表操作中的“详情”“编辑”必须下钻到独立页面或明确详情抽屉，不允许只用临时悬浮面板承载关键信息。
- 独立详情页左上角必须有返回入口。
- 来源资产、来源测试点、页面对象、用例中心之间的跳转必须使用链接样式，不使用普通文本伪装。

### 9.2 主操作

- 主操作按钮最多两个。
- 危险操作必须二次确认。
- 成功后应给出明确反馈，并保持当前详情数据刷新。

### 9.3 折叠与展开

建议默认折叠：

- 脚本源码。
- JSON/YAML 原始数据。
- 完整日志。
- 长审核历史。

建议默认展开：

- 基本信息。
- 操作步骤。
- 预期结果。
- 关键阻断信息。

### 9.4 空态

详情页空态必须提供下一步引导。

示例：

```text
暂无执行历史
点击上方「执行用例」按钮，开始第一次测试运行。
[立即执行]
```

## 10. 响应式规范

### 10.1 桌面端

- `.detail-page` 最大宽度：`1440px`
- `.detail-field-grid--4` 默认四列
- 操作区靠右
- 表格横向空间充足

### 10.2 中屏

当宽度小于 `1280px`：

- 字段网格四列降为两列。
- 顶部操作允许换行。
- 代码区保持横向滚动。

### 10.3 小屏

当宽度小于 `768px`：

- 字段网格降为一列。
- `.detail-toolbar` 变为上下结构。
- `.detail-title-row` 状态标签换行显示。
- 表格使用横向滚动，不压缩到不可读。
- 抽屉宽度使用 `100vw`。

## 11. 建议 CSS 骨架

后续实施时建议在 `styles.css` 增加以下骨架，再逐步迁移旧 class。

```css
.detail-page {
  display: grid;
  gap: 16px;
  max-width: 1440px;
  margin: 24px auto;
  padding: 0 16px 40px;
  color: var(--text-body);
  font-family: var(--font-ui);
}

.detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.detail-toolbar-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-hero,
.detail-section {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-panel);
  background: var(--surface-panel);
  box-shadow: var(--shadow-panel);
}

.detail-hero {
  padding: 18px 20px;
}

.detail-hero--compact {
  padding: 14px 16px;
}

.detail-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--title-md);
  font-weight: var(--weight-bold);
  line-height: var(--leading-tight);
}

.detail-subtitle,
.detail-meta {
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: var(--weight-regular);
  line-height: var(--leading-normal);
}

.detail-description {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-md);
  line-height: var(--leading-relaxed);
}

.detail-field-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.detail-field {
  min-width: 0;
  display: grid;
  gap: 5px;
  border: 1px solid #e7eef9;
  border-radius: var(--radius-card);
  padding: 11px 12px;
  background: #fbfdff;
}

.detail-field--wide {
  grid-column: span 2;
}

.detail-field-label {
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
}

.detail-field-value {
  min-width: 0;
  color: var(--text-primary);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.detail-section {
  padding: 16px;
}

.detail-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-section-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--title-sm);
  font-weight: var(--weight-semibold);
  line-height: var(--leading-tight);
}

.detail-section-desc {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.detail-mono,
.detail-id,
.detail-url,
.detail-locator {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: var(--weight-regular);
}

.detail-code {
  margin: 0;
  overflow-x: auto;
  border: 1px solid #e1e4e8;
  border-radius: 8px;
  background: var(--surface-code);
  padding: 16px;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: var(--leading-code);
}

.detail-status {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  border: 1px solid var(--neutral-border);
  background: var(--neutral-bg);
  color: var(--neutral-text);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  line-height: 1;
  white-space: nowrap;
}

.detail-status--success {
  border-color: var(--success-border);
  background: var(--success-bg);
  color: var(--success-text);
}

.detail-status--warning {
  border-color: var(--warning-border);
  background: var(--warning-bg);
  color: var(--warning-text);
}

.detail-status--danger {
  border-color: var(--danger-border);
  background: var(--danger-bg);
  color: var(--danger-text);
}

@media (max-width: 1280px) {
  .detail-field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .detail-page {
    margin: 16px auto;
    padding: 0 12px 32px;
  }

  .detail-field-grid {
    grid-template-columns: 1fr;
  }

  .detail-field--wide {
    grid-column: auto;
  }

  .detail-title-row,
  .detail-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
```

## 12. 迁移计划

### 阶段 1：新增统一样式，不破坏旧页面

动作：

- 在 `styles.css` 中新增 `.detail-*` 样式。
- 暂不删除旧 `case-*`、`review-detail-*`、`asset-*` class。
- 新增页面优先使用 `.detail-*`。

验收：

- 不影响现有页面功能。
- 新样式可以独立挂到任意详情页。

### 阶段 2：用例详情页迁移

原因：

- 用例详情页结构最完整，包含 hero、字段、步骤、元素、历史、脚本，是最佳样板。

动作：

- `case-hero-card` 迁移为 `.detail-hero`。
- `case-info-grid` 迁移为 `.detail-field-grid`。
- `case-steps-table` 迁移为 `.detail-table detail-table--steps`。
- 脚本源码迁移为 `.detail-code`。

### 阶段 3：待审核详情抽屉迁移

动作：

- `review-detail-card` 迁移为 `.detail-section`。
- `review-detail-label` 迁移为 `.detail-field-label` 或 `.detail-section-title`。
- 阻断警告迁移为 `.detail-alert`。
- 底部固定栏使用 `.detail-drawer-footer`。

### 阶段 4：页面对象详情和资产详情迁移

动作：

- `element-detail-page` 迁移为 `.detail-page detail-page--page-object`。
- `asset-detail-panel` 迁移为 `.detail-page detail-page--asset` 或 `.detail-section`。
- 高密度表格统一使用 `.detail-table`。

## 13. 验收清单

详情页上线或迁移后逐项检查：

- 是否存在 `.detail-page` 或 `.detail-drawer` 作为根容器。
- 是否使用 `.detail-hero` 承载标题、状态、说明和来源。
- 是否使用 `.detail-field-grid` 与 `.detail-field` 展示结构化字段。
- 是否使用 `.detail-section` 承载内容分组。
- `case_id`、`intent_id`、`asset_id`、`element_code`、URL、locator 是否使用 `.detail-mono`。
- 状态是否使用 `.detail-status`，且为浅底深字。
- 是否还有详情页新增 `fontSize/fontWeight/fontFamily` 内联样式。
- 危险操作是否二次确认。
- 代码块是否默认等宽字体、浅灰背景、可横向滚动。
- 125% 浏览器缩放下字段和表格仍可读。

## 14. 最终设计效果

完成后，详情页将形成统一体验：

- 从列表页点击详情后，用户能立刻识别“标题、状态、来源、关键字段、内容分组”。
- 不同模块详情页切换时，字体、间距、卡片、字段结构保持一致。
- 技术信息不再混在普通正文里，脚本和 locator 更容易扫描。
- 设计侧有统一稿，开发侧有统一 class，后续页面不再各写一套详情样式。

