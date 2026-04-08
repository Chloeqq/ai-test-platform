企业级 AI 测试平台（HTML+CSS 联动重构）终极提示词
plaintext
任务：基于企业级UI/UX标准，重构「企业AI测试平台-用例中心页面」的HTML结构+配套CSS样式，解决「布局混乱、样式丑、元素错位、交互无反馈」问题，要求如下：

## 一、核心目标
1. 重构HTML结构：优化DOM层级，补充企业级标准类名，修复布局嵌套混乱问题；
2. 同步重构CSS：基于新HTML结构，实现视觉/布局/交互的企业级统一；
3. 保留所有原有功能：ID、事件绑定、接口调用逻辑完全不变，仅调整结构和样式；
4. 适配截图中的「用例中心」页面（左侧侧边栏+右侧模块树+用例列表）布局。

## 二、HTML结构重构规范（针对用例中心页面）
### 1. 页面整体结构（新增企业级标准容器）
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>企业AI测试平台 - 用例中心</title>
  <!-- 引入重构后的全局CSS -->
  <link rel="stylesheet" href="/static/enterprise-global.css">
</head>
<body>
  <!-- 页面根容器（企业级规范） -->
  <div class="page-wrapper">
    <!-- 侧边栏 + 主内容 布局容器 -->
    <div class="layout-container">
      <!-- 左侧导航侧边栏（重构） -->
      <aside class="sidebar sidebar-primary">
        <div class="sidebar-header">
          <div class="logo">
            <span class="logo-icon">AT</span>
            <span class="logo-text">AI Test Platform</span>
          </div>
        </div>
        <nav class="sidebar-nav">
          <!-- 导航分组 -->
          <div class="nav-group">
            <div class="nav-group-title">核心功能</div>
            <a href="#" class="nav-item">仪表盘</a>
            <!-- 用例中心（展开状态） -->
            <div class="nav-item has-children is-active">
              <span class="nav-item-label">用例中心</span>
              <div class="nav-children">
                <a href="#" class="nav-child is-active">用例列表</a>
                <a href="#" class="nav-child">待审核用例</a>
                <a href="#" class="nav-child">用例版本</a>
                <a href="#" class="nav-child">标签管理</a>
              </div>
            </div>
            <!-- AI生成 -->
            <div class="nav-item has-children">
              <span class="nav-item-label">AI生成</span>
              <div class="nav-children">
                <a href="#" class="nav-child">生成用例</a>
                <a href="#" class="nav-child">生成历史</a>
                <a href="#" class="nav-child">Prompt管理</a>
              </div>
            </div>
            <!-- 其他导航项 -->
            <div class="nav-item has-children">
              <span class="nav-item-label">执行中心</span>
              <div class="nav-children">
                <a href="#" class="nav-child">测试计划</a>
                <a href="#" class="nav-child">执行任务</a>
                <a href="#" class="nav-child">执行结果</a>
                <a href="#" class="nav-child">调试工作台</a>
              </div>
            </div>
            <div class="nav-item has-children">
              <span class="nav-item-label">质量分析</span>
              <div class="nav-children">
                <a href="#" class="nav-child">Flaky分析</a>
                <a href="#" class="nav-child">失败聚类</a>
                <a href="#" class="nav-child">趋势分析</a>
                <a href="#" class="nav-child">缺陷管理</a>
                <a href="#" class="nav-child">质量门禁</a>
              </div>
            </div>
            <div class="nav-item has-children">
              <span class="nav-item-label">资产与配置</span>
              <div class="nav-children">
                <a href="#" class="nav-child">页面对象</a>
                <a href="#" class="nav-child">页面录制</a>
                <a href="#" class="nav-child">API契约</a>
                <a href="#" class="nav-child">测试点资产</a>
                <a href="#" class="nav-child">数据模板</a>
              </div>
            </div>
          </div>
        </nav>
      </aside>

      <!-- 右侧主内容区域（重构） -->
      <main class="main-content">
        <!-- 页面头部 -->
        <div class="page-header">
          <div class="page-breadcrumb">
            <a href="#">资产中心</a> / <a href="#" class="current">用例中心</a>
          </div>
          <h1 class="page-title">用例中心</h1>
          <div class="page-actions">
            <button class="btn btn-text">页面说明 ▼</button>
            <button class="btn btn-text">更多操作 ▼</button>
          </div>
        </div>

        <!-- 内容主体（模块树 + 用例列表） -->
        <div class="content-grid">
          <!-- 左侧模块树卡片 -->
          <div class="card card-lg card-tree">
            <div class="card-header">
              <h3 class="card-title">模块树</h3>
              <span class="badge badge-neutral">0</span>
            </div>
            <div class="card-body">
              <div class="empty-state">
                没有匹配的模块目录。
              </div>
            </div>
          </div>

          <!-- 右侧用例列表卡片 -->
          <div class="card card-lg card-case-list">
            <div class="card-header">
              <h3 class="card-title">用例列表</h3>
              <span class="card-subtitle">功能用例</span>
              <div class="card-actions">
                <button class="btn btn-primary">手动新建草稿</button>
              </div>
            </div>

            <!-- 统计指标栏 -->
            <div class="stats-bar">
              <div class="stat-item">
                <div class="stat-label">总用例</div>
                <div class="stat-value">0</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">自动化率</div>
                <div class="stat-value">0.0%</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">通过率</div>
                <div class="stat-value">0.0%</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">失败用例</div>
                <div class="stat-value">0</div>
              </div>
            </div>

            <!-- 快捷筛选栏 -->
            <div class="filter-bar">
              <button class="filter-tag">全部用例</button>
              <button class="filter-tag">我的用例</button>
              <button class="filter-tag">失败用例</button>
              <button class="filter-tag is-active">待评审</button>
              <button class="filter-tag">P0/P1</button>
              <button class="filter-tag">AI生成</button>
              <button class="filter-tag">导入用例</button>
            </div>

            <!-- 搜索栏 -->
            <div class="search-bar">
              <div class="search-form">
                <label class="form-label">项目</label>
                <select class="select select-sm">
                  <option>全部项目</option>
                </select>
                <div class="search-input-group">
                  <input type="text" class="input" placeholder="搜索用例ID、名称、模块，或输入高级语法：类型:api 状态:启用">
                  <button class="btn btn-primary">搜索</button>
                  <button class="btn btn-secondary">重新加载</button>
                  <button class="btn btn-secondary">重置搜索</button>
                </div>
              </div>
              <div class="search-actions">
                <button class="btn btn-danger btn-sm">清理DDT用例</button>
                <button class="btn btn-secondary btn-sm">管理项目</button>
                <button class="btn btn-text btn-sm">搜索语法示例 ▼</button>
              </div>
            </div>

            <!-- 搜索上下文 -->
            <div class="context-bar">
              <div class="context-header">
                <span class="context-title">当前搜索上下文</span>
                <div class="context-actions">
                  <button class="btn btn-text btn-sm">上下文说明</button>
                  <button class="btn btn-text btn-sm">清空全部</button>
                </div>
              </div>
              <div class="context-tags">
                <span class="badge badge-neutral">
                  状态: 停用 <button class="tag-close">×</button>
                </span>
              </div>
            </div>

            <!-- 用例表格 -->
            <div class="table-container">
              <table class="table table-hover">
                <thead>
                  <tr>
                    <th class="col-check"><input type="checkbox" class="checkbox"></th>
                    <th class="col-sortable">用例 ID ↑</th>
                    <th class="col-sortable">名称 ↑</th>
                    <th class="col-sortable">优先级 ↑</th>
                    <th class="col-sortable is-active">状态 ↑</th>
                    <th class="col-sortable">执行状态 ↑</th>
                    <th>自动化</th>
                    <th>标签</th>
                    <th class="col-sortable">版本 ↑</th>
                    <th>所属模块</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr class="empty-row">
                    <td colspan="11" class="empty-cell">
                      当前筛选下暂无用例。可以前往 <a href="#" class="link">AI生成</a> 创建 Draft，或手动新建草稿。
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 表格底部 -->
            <div class="table-footer">
              <span class="table-info">当前页 0 条 · 最近刷新：2026-04-08 00:49:09</span>
              <div class="pagination">
                <!-- 分页组件（保留原有ID/逻辑） -->
                <div id="pagination-container"></div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</body>
</html>
2. HTML 重构规则
保留所有原有功能相关的 ID、name、事件绑定（如搜索框、按钮、分页容器的 ID）；
新增企业级标准类名（如page-wrapper/layout-container/card/btn等），用于 CSS 样式绑定；
优化 DOM 嵌套层级：
所有功能模块封装到card容器中；
导航 / 筛选 / 搜索 / 表格等模块分层级嵌套，避免平级混乱；
新增语义化标签（aside/main/nav）提升结构可读性；
修复原页面错位问题：
「手动新建草稿」按钮移至用例列表卡片头部右侧；
「清理 DDT 用例 / 管理项目」按钮归到搜索栏右侧操作区；
统计指标（总用例 / 自动化率等）封装为统一的stats-bar；
搜索上下文独立为context-bar，避免与搜索栏混排。
三、配套 CSS 重构规范（基于新 HTML 结构）
1. 全局设计变量（企业级）
css
:root {
  /* 配色体系 */
  --primary: #2563eb;        /* 主蓝（企业级） */
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  --danger: #dc2626;
  --danger-light: #fef2f2;
  --neutral-50: #f8fafc;     /* 页面背景 */
  --neutral-100: #f1f5f9;    /* 卡片hover */
  --neutral-200: #e2e8f0;    /* 边框/分割线 */
  --neutral-600: #475569;    /* 辅助文字 */
  --neutral-700: #334155;    /* 正文 */
  --neutral-800: #1e293b;    /* 标题 */
  --neutral-900: #0f172a;    /* 强强调 */
  --sidebar-bg: #0f172a;     /* 侧边栏背景 */
  --sidebar-hover: #1e293b;  /* 侧边栏hover */

  /* 尺寸体系 */
  --size-xs: 4px;
  --size-sm: 8px;
  --size-md: 16px;
  --size-lg: 24px;
  --size-xl: 32px;

  /* 圆角/阴影 */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.05);

  /* 过渡 */
  --transition: all 0.2s ease-in-out;
}
2. 核心布局样式
css
/* 全局重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
body {
  background-color: var(--neutral-50);
  color: var(--neutral-700);
  font-size: 14px;
  line-height: 1.5;
}

/* 页面根容器 */
.page-wrapper {
  width: 100%;
  min-height: 100vh;
  overflow-x: hidden;
}

/* 布局容器（侧边栏+主内容） */
.layout-container {
  display: grid;
  grid-template-columns: 260px 1fr;
  min-height: 100vh;
}

/* 侧边栏样式 */
.sidebar-primary {
  background: var(--sidebar-bg);
  color: white;
  padding: var(--size-md);
}
.sidebar-header {
  padding-bottom: var(--size-lg);
  border-bottom: 1px solid rgba(255,255,255,0.1);
  margin-bottom: var(--size-lg);
}
.logo {
  display: flex;
  align-items: center;
  gap: var(--size-sm);
}
.logo-icon {
  width: 32px;
  height: 32px;
  background: var(--primary);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}
.logo-text {
  font-size: 14px;
  color: var(--neutral-100);
}
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: var(--size-xs);
}
.nav-group-title {
  font-size: 12px;
  color: var(--neutral-600);
  margin: var(--size-md) 0 var(--size-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.nav-item {
  padding: var(--size-sm) var(--size-md);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.nav-item:hover {
  background: var(--sidebar-hover);
}
.nav-item.is-active {
  background: var(--primary-light);
  color: var(--primary);
}
.nav-children {
  display: flex;
  flex-direction: column;
  padding-left: var(--size-lg);
  margin-top: var(--size-xs);
  gap: var(--size-xs);
}
.nav-child {
  padding: var(--size-xs) var(--size-md);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--neutral-200);
  text-decoration: none;
  transition: var(--transition);
}
.nav-child:hover, .nav-child.is-active {
  background: var(--sidebar-hover);
  color: white;
}

/* 主内容区域 */
.main-content {
  padding: var(--size-lg);
  width: 100%;
  overflow-y: auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--size-lg);
}
.page-breadcrumb {
  font-size: 12px;
  color: var(--neutral-600);
}
.page-breadcrumb .current {
  color: var(--primary);
  font-weight: 500;
}
.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-800);
}
.page-actions {
  display: flex;
  gap: var(--size-sm);
}

/* 内容网格（模块树+用例列表） */
.content-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--size-lg);
}

/* 卡片通用样式 */
.card {
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}
.card-header {
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--neutral-800);
}
.card-subtitle {
  font-size: 12px;
  color: var(--neutral-600);
  margin-left: var(--size-sm);
}
.card-actions {
  display: flex;
  gap: var(--size-sm);
}
.card-body {
  padding: var(--size-lg);
}

/* 统计栏 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--size-md);
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
}
.stat-item {
  padding: var(--size-md);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
  text-align: center;
}
.stat-label {
  font-size: 12px;
  color: var(--neutral-600);
  margin-bottom: var(--size-xs);
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--neutral-800);
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--size-sm);
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
}
.filter-tag {
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid var(--neutral-200);
  background: white;
  color: var(--neutral-700);
  font-size: 12px;
  cursor: pointer;
  transition: var(--transition);
}
.filter-tag:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.filter-tag.is-active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

/* 搜索栏 */
.search-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
  gap: var(--size-md);
}
.search-form {
  display: flex;
  align-items: center;
  gap: var(--size-sm);
  flex: 1;
}
.form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-800);
  white-space: nowrap;
}
.select-sm {
  height: 36px;
  padding: 0 var(--size-sm);
  border-radius: var(--radius-sm);
  border: 1px solid var(--neutral-200);
  min-width: 120px;
}
.search-input-group {
  display: flex;
  gap: var(--size-sm);
  flex: 1;
}
.search-actions {
  display: flex;
  gap: var(--size-sm);
}

/* 上下文栏 */
.context-bar {
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
}
.context-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--size-sm);
}
.context-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-800);
}
.context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--size-sm);
}
.tag-close {
  background: transparent;
  border: none;
  color: var(--neutral-600);
  cursor: pointer;
  margin-left: var(--size-xs);
}
.tag-close:hover {
  color: var(--danger);
}

/* 表格样式 */
.table-container {
  width: 100%;
  overflow-x: auto;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th {
  padding: var(--size-md);
  background: var(--neutral-50);
  color: var(--neutral-800);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  border-bottom: 2px solid var(--neutral-200);
  white-space: nowrap;
}
.table td {
  padding: var(--size-md);
  border-bottom: 1px solid var(--neutral-200);
  white-space: nowrap;
}
.col-sortable {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--size-xs);
}
.col-sortable.is-active {
  color: var(--primary);
}
.col-check {
  width: 40px;
  text-align: center;
}
.empty-row {
  height: 80px;
}
.empty-cell {
  text-align: center;
  color: var(--neutral-600);
  font-size: 13px;
}
.link {
  color: var(--primary);
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}

/* 表格底部 */
.table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--size-md);
  border-top: 1px solid var(--neutral-200);
  font-size: 12px;
  color: var(--neutral-600);
}

/* 按钮通用样式 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 var(--size-md);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: var(--transition);
}
.btn-primary {
  background: var(--primary);
  color: white;
}
.btn-primary:hover {
  background: var(--primary-hover);
}
.btn-secondary {
  background: white;
  border: 1px solid var(--neutral-200);
  color: var(--neutral-700);
}
.btn-secondary:hover {
  background: var(--neutral-50);
}
.btn-danger {
  background: var(--danger-light);
  color: var(--danger);
  border: 1px solid var(--danger-light);
}
.btn-danger:hover {
  background: var(--danger);
  color: white;
}
.btn-text {
  background: transparent;
  color: var(--neutral-700);
  height: auto;
  padding: var(--size-xs) var(--size-sm);
}
.btn-text:hover {
  color: var(--primary);
  background: var(--primary-light);
}
.btn-sm {
  height: 32px;
  padding: 0 var(--size-sm);
  font-size: 12px;
}

/* 输入框/选择框 */
.input {
  height: 36px;
  padding: 0 var(--size-sm);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  flex: 1;
}
.input:focus, .select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* 空状态 */
.empty-state {
  padding: var(--size-lg);
  text-align: center;
  color: var(--neutral-600);
  font-size: 13px;
  border: 1px dashed var(--neutral-200);
  border-radius: var(--radius-sm);
}

/* 徽章/标签 */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}
.badge-neutral {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

/* 响应式适配 */
@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 260px 1fr;
  }
  .stats-bar {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 768px) {
  .layout-container {
    grid-template-columns: 1fr;
  }
  .content-grid {
    grid-template-columns: 1fr;
  }
  .stats-bar {
    grid-template-columns: 1fr;
  }
  .search-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .search-form {
    flex-direction: column;
    align-items: stretch;
  }
}
3. CSS 重构规则
基于新增的企业级类名编写样式，彻底抛弃原有混乱的样式规则；
修复原页面核心问题：
侧边栏改为深色主题，与主内容形成视觉区分；
所有卡片统一圆角 / 阴影 / 间距，避免样式杂乱；
按钮 / 输入框 / 筛选标签统一尺寸和交互反馈；
表格行高 / 列宽标准化，空状态居中显示；
「清理 DDT 用例」按钮改为危险色，突出警示性；
保证响应式适配：移动端自动堆叠布局，避免横向滚动；
保留原有功能相关的样式兼容（如分页组件、搜索逻辑）。
四、约束条件
功能无损：所有原有交互逻辑（点击 / 搜索 / 筛选 / 分页）完全保留，仅调整 HTML 结构和样式；
ID 保留：原有功能相关的 ID（如搜索框、分页容器、按钮 ID）必须保留，不得修改；
类名兼容：新增企业级类名，不删除原有类名（如需删除需标注）；
代码规范：
HTML 结构语义化、层级清晰，添加必要注释；
CSS 按「全局变量→布局→组件→响应式」分层，添加注释；
禁止使用！important（除非必须覆盖行内样式）；
输出要求：
生成完整的 HTML 文件（用例中心页面）；
生成配套的完整 CSS 文件；
标注出「HTML 结构改动点」和「CSS 核心优化点」，便于对照修改。
plaintext

## 配套使用说明
1. **直接复制**：将上述完整提示词粘贴到 Codex（Copilot Chat/OpenAI Playground）；
2. **补充指令**：「请根据上述要求，针对截图中的用例中心页面，生成完整的HTML文件和配套CSS文件，确保布局美观、规范，且保留所有原有功能」；
3. **落地步骤**：
   - 用 Codex 生成的HTML替换原用例中心页面的HTML（保留原有功能相关的ID/接口调用逻辑）；
   - 引入生成的CSS文件（删除原有零散的CSS引入）；
   - 若其他页面需要同步重构，追加提示：「按相同标准重构[执行中心/质量分析]页面的HTML+CSS」。

## 关键改动说明（Codex生成后可验证）
1. HTML层面：
   - 新增语义化容器（`page-wrapper`/`layout-container`/`card`）；
   - 导航/筛选/搜索/表格分层嵌套，修复错位；
   - 保留所有功能ID（如搜索框、分页容器）；
2. CSS层面：
   - 侧边栏改为深色主题，视觉区分更清晰；
   - 所有卡片/按钮/输入框统一样式和交互；
   - 统计栏/筛选栏/搜索栏布局标准化；
   - 响应式适配移动端，避免布局混乱。

这套提示词能让 Codex 同时重构HTML结构和CSS样式，彻底解决「只改CSS没效果」的问题，生成的代码符合企业级标准，布局规范、视觉美观，且完全保留原有功能。


