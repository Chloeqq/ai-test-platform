# 后端已实现但前端未体现的功能清单

**分析时间**: 2026-04-02  
**分析范围**: Web UI Service (FastAPI) vs 前端页面 (HTML/JS)

---

## 一、功能对比总览

| 类别 | 后端 API 数量 | 前端页面对应 | 未体现比例 |
|------|-------------|-------------|------------|
| 认证鉴权 | 4 个 | ✅ 完整 | 0% |
| 仪表盘 | 2 个 | ✅ 完整 | 0% |
| 工作台 | 40+ 个 | ✅ 大部分 | ~15% |
| 测试用例管理 | 12 个 | ✅ 完整 | 0% |
| 质量分析 | 8 个 | ⚠️ 部分 | ~40% |
| 执行门禁 | 4 个 | ❌ 缺失 | 100% |
| 调度中心 | 2 个 | ❌ 缺失 | 100% |
| 缺陷管理 | 3 个 | ❌ 缺失 | 100% |
| 测试点资产 | 6 个 | ❌ 缺失 | 100% |
| 健康检查 | 1 个 | N/A | - |

**总体评估**: 约 **25%** 的后端 API 功能在前端没有对应入口或界面

---

## 二、详细功能对比清单

### 2.1 完全缺失的功能 🔴

#### 1. 执行门禁管理 (Execution Gate)

**后端 API** (`workbench_gate.py`):
```python
GET  /api/workbench/execution-gate/config           # 获取门禁配置
POST /api/workbench/execution-gate/decisions        # 保存门禁决策
POST /api/workbench/execution-gate/decisions/approve # 批准门禁
POST /api/workbench/execution-gate/decisions/revoke  # 撤销门禁
```

**功能描述**:
- 配置门禁策略 (阻断阈值、风险阻断、双重审批等)
- 保存执行门禁决策 (allow/manual_review/block)
- 人工审批门禁决策
- 撤销已批准的门禁决策

**前端状态**: ❌ **完全缺失**
- 无对应 HTML 页面
- 无对应 JS 文件
- 仅在 `ui.py` 中有路由定义 `/gate` 但无实现

**影响**:
- 用户无法通过 UI 配置门禁策略
- 无法人工审批高风险执行
- 门禁决策无法可视化管理

**建议优先级**: 🔴 **P0**

---

#### 2. 调度中心 (Scheduler)

**后端 API** (`workbench_scheduler.py`):
```python
GET /api/workbench/scheduler/summary      # 获取调度摘要
GET /api/workbench/scheduler/dispatch-plan # 获取分发计划
```

**功能描述**:
- 查看任务调度摘要 (待执行/执行中/已完成)
- 查看任务分发计划 (资源分配/队列状态)
- 支持并发控制/环境池管理

**前端状态**: ❌ **完全缺失**
- 无对应 HTML 页面
- 无对应 JS 文件
- 仅在 `ui.py` 中有路由定义 `/settings/nodes` 但无实现

**影响**:
- 用户无法查看任务调度状态
- 无法手动调整执行队列
- 无法监控资源使用情况

**建议优先级**: 🟡 **P1**

---

#### 3. 缺陷管理 (Defect Management)

**后端 API** (`workbench_reporting.py` + `test_cases.py`):
```python
GET  /api/defects                        # 查询缺陷列表
POST /api/defects                        # 添加缺陷关联
POST /test-cases/{case_id}/defects       # 用例关联缺陷
```

**功能描述**:
- 查询缺陷列表 (支持按用例/状态筛选)
- 添加缺陷关联 (JIRA/缺陷单)
- 用例与缺陷双向关联
- 缺陷闭环追踪

**后端数据模型** (`test_cases.py`):
```python
class TestCaseDefect(Base):
    id: int
    case_id: int
    defect_key: str      # JIRA Key
    defect_url: str      # JIRA URL
    created_at: datetime
```

**前端状态**: ❌ **完全缺失**
- 无缺陷管理页面
- 无缺陷关联 UI
- 无缺陷闭环追踪视图

**影响**:
- 无法在平台内管理缺陷关联
- 无法追踪缺陷修复进度
- 无法统计缺陷密度/修复率

**建议优先级**: 🟡 **P1**

---

#### 4. 测试点资产管理 (Test Point Assets)

**后端 API** (`workbench_assets.py`):
```python
GET /api/workbench/test-point-assets                  # 查询测试点资产
GET /api/workbench/test-point-assets/coverage-summary # 获取覆盖摘要
GET /api/workbench/test-point-assets/{asset_id}       # 获取测试点详情
GET /api/workbench/test-point-assets/{asset_id}/coverage-matrix # 覆盖矩阵
```

**功能描述**:
- 查询测试点资产列表 (支持多维度筛选)
- 查看测试点覆盖摘要
- 查看测试点详情 (依赖元素/置信度/评审状态)
- 查看覆盖矩阵 (需求→测试点→用例)

**后端数据模型** (基于文件存储):
```
web-ui/state/test-points/
├── default/
│   ├── TC-PRODUCT-001.json
│   ├── TC-ORDER-001.json
│   └── plans/
│       └── TC-PRODUCT-TP-001.json  # 测试点计划
```

**前端状态**: ❌ **完全缺失**
- 无测试点资产列表页
- 无覆盖矩阵视图
- 无测试点评审 UI

**影响**:
- 测试点资产无法可视化管理
- 覆盖矩阵无法查看
- 测试点评审流程无法执行

**建议优先级**: 🔴 **P0** (测试点中间层是核心缺口)

---

### 2.2 部分缺失的功能 🟡

#### 5. 质量分析 - Flaky 测试

**后端 API** (`dashboard.py` + `workbench_reporting.py`):
```python
GET /api/workbench/quality-gates/flaky-summary  # Flaky 摘要
GET /quality/flaky                              # Flaky 页面路由 (已定义)
```

**功能描述**:
- Flaky 测试检测 (失败率 > 10%)
- Flaky 测试列表 (按 Flaky 率排序)
- Flaky 原因分析 (超时/定位器/断言等)
- Flaky 修复建议

**前端状态**: ⚠️ **部分缺失**
- `ui.py` 有路由定义 `/quality/flaky`
- 但无对应 `quality_flaky.html` 模板
- 无对应 `quality_flaky.js` 文件

**影响**:
- 无法识别不稳定测试
- 无法优先修复 Flaky 用例
- 影响回归稳定性

**建议优先级**: 🟡 **P1**

---

#### 6. 质量分析 - 风险趋势

**后端 API** (`dashboard.py`):
```python
GET /api/dashboard/overview         # 仪表盘概览 (含风险趋势)
GET /quality/trends                 # 风险趋势页面路由 (已定义)
```

**功能描述**:
- 风险评分趋势图 (14 天)
- 各维度风险评分 (失败率/严重度/趋势/覆盖度/稳定性)
- 风险因素分析
- 发布建议生成

**前端状态**: ⚠️ **部分缺失**
- `ui.py` 有路由定义 `/quality/trends`
- 但无对应 `quality_trends.html` 模板
- 无对应 `quality_trends.js` 文件
- Dashboard 页面有链接但点击后 404

**影响**:
- 无法查看质量趋势
- 无法评估发布风险
- 无法追踪质量改进效果

**建议优先级**: 🟡 **P1**

---

#### 7. 失败聚类分析

**后端 API** (`legacy_console.py`):
```python
GET /failures/clusters              # 失败聚类列表
GET /failures/clusters/{cluster_id} # 聚类详情
```

**功能描述**:
- 失败聚类 (按错误模式/页面/模块)
- 聚类根因分析 (AI 辅助)
- 聚类影响评估 (受影响用例/页面)
- 聚类处理状态追踪

**前端状态**: ⚠️ **部分缺失**
- `quality_clusters.html` 和 `quality_clusters.js` **存在**
- 但功能不完整:
  - ✅ 聚类列表展示
  - ❌ 聚类详情钻取
  - ❌ 根因分析展示
  - ❌ 处理状态管理

**影响**:
- 无法查看聚类详情
- 无法追踪聚类修复进度
- 无法识别系统性问题

**建议优先级**: 🟡 **P1**

---

#### 8. 用例版本对比

**后端 API** (`test_cases.py`):
```python
GET /test-cases/{case_id}/versions/compare  # 版本对比
```

**功能描述**:
- 对比用例不同版本
- 显示步骤差异 (新增/删除/修改)
- 显示脚本差异 (diff 视图)
- 显示变更历史

**前端状态**: ⚠️ **部分缺失**
- `case_detail.html` 存在
- 但无版本对比功能
- 无 diff 视图
- 无变更历史时间线

**影响**:
- 无法追溯用例变更
- 无法审计修改记录
- 无法回滚到历史版本

**建议优先级**: 🟢 **P2**

---

### 2.3 功能完整度评估

| 模块 | 后端 API | 前端页面 | 完整度 | 说明 |
|------|----------|----------|--------|------|
| 认证鉴权 | 4 个 | ✅ 完整 | 100% | 登录/注册/Token/用户信息 |
| 仪表盘 | 2 个 | ✅ 完整 | 100% | 概览/治理视图 |
| 工作台 - 生成 | 3 个 | ✅ 完整 | 100% | 生成/预览/自动运行 |
| 工作台 - 评审 | 1 个 | ✅ 完整 | 100% | 元素/测试点/风险评审 |
| 工作台 - 门禁 | 4 个 | ❌ 缺失 | 0% | **完全缺失** |
| 工作台 - 报告 | 10 个 | ✅ 完整 | 90% | 概览/失败/上下文/性能/Allure |
| 工作台 - 历史 | 1 个 | ✅ 完整 | 100% | 操作历史 |
| 工作台 - 运行 | 6 个 | ✅ 完整 | 90% | 执行/重跑/日志/分析/自愈 |
| 工作台 - 资产 | 6 个 | ⚠️ 部分 | 40% | 用例管理完整，测试点资产缺失 |
| 工作台 - 调度 | 2 个 | ❌ 缺失 | 0% | **完全缺失** |
| 测试用例管理 | 12 个 | ✅ 完整 | 95% | 版本对比部分缺失 |
| 质量分析 - Flaky | 1 个 | ❌ 缺失 | 0% | **完全缺失** |
| 质量分析 - 聚类 | 2 个 | ⚠️ 部分 | 60% | 列表有，详情缺失 |
| 质量分析 - 趋势 | 1 个 | ❌ 缺失 | 0% | **完全缺失** |
| 缺陷管理 | 3 个 | ❌ 缺失 | 0% | **完全缺失** |
| 健康检查 | 1 个 | N/A | - | 运维用，无需 UI |

---

## 三、缺失功能优先级排序

### P0 - 立即实现 (1-2 周)

| # | 功能 | 后端 API | 前端工作量 | 业务价值 |
|---|------|----------|------------|----------|
| 1 | 测试点资产管理 | 4 个 | 5 天 | 测试点中间层闭环 |
| 2 | 执行门禁管理 | 4 个 | 3 天 | 发布决策支持 |

### P1 - 短期实现 (2-4 周)

| # | 功能 | 后端 API | 前端工作量 | 业务价值 |
|---|------|----------|------------|----------|
| 3 | 缺陷管理 | 3 个 | 4 天 | 缺陷闭环追踪 |
| 4 | 调度中心 | 2 个 | 3 天 | 任务调度可视化 |
| 5 | Flaky 测试分析 | 1 个 | 3 天 | 稳定性提升 |
| 6 | 风险趋势分析 | 1 个 | 3 天 | 质量趋势追踪 |
| 7 | 失败聚类详情 | 1 个 | 2 天 | 系统性问题识别 |

### P2 - 中期实现 (1-2 月)

| # | 功能 | 后端 API | 前端工作量 | 业务价值 |
|---|------|----------|------------|----------|
| 8 | 用例版本对比 | 1 个 | 3 天 | 变更追溯/审计 |
| 9 | 测试点覆盖矩阵 | 1 个 | 4 天 | 覆盖度可视化 |
| 10 | 自愈审批 UI | 2 个 | 3 天 | 自愈治理 |

---

## 四、前端页面缺失清单

### 4.1 完全缺失的页面

| 页面路径 | 对应后端 API | 优先级 |
|----------|-------------|--------|
| `/gate` | `workbench_gate.py` | P0 |
| `/quality/flaky` | `dashboard.py` | P1 |
| `/quality/trends` | `dashboard.py` | P1 |
| `/settings/scheduler` | `workbench_scheduler.py` | P1 |
| `/defects` | `workbench_reporting.py` | P1 |
| `/assets/test-points` | `workbench_assets.py` | P0 |
| `/assets/test-points/{id}` | `workbench_assets.py` | P0 |
| `/assets/test-points/{id}/matrix` | `workbench_assets.py` | P2 |

### 4.2 需要增强的页面

| 页面 | 缺失功能 | 优先级 |
|------|----------|--------|
| `quality_clusters.html` | 聚类详情/根因分析/状态追踪 | P1 |
| `case_detail.html` | 版本对比/变更历史/diff 视图 | P2 |
| `workbench_history.html` | 自愈审批历史 | P2 |
| `dashboard.html` | 风险趋势图/Flaky 摘要 | P1 |

---

## 五、建议实施计划

### Week 1-2: 测试点资产管理
1. 创建 `test_points.html` 模板
2. 创建 `test_points.js` 前端逻辑
3. 实现测试点列表/详情/评审 UI
4. 实现覆盖矩阵视图

### Week 3-4: 执行门禁 + 缺陷管理
1. 创建 `gate.html` 模板
2. 实现门禁配置/审批/撤销 UI
3. 创建 `defects.html` 模板
4. 实现缺陷关联/追踪 UI

### Week 5-6: 质量分析增强
1. 创建 `quality_flaky.html` 模板
2. 创建 `quality_trends.html` 模板
3. 增强 `quality_clusters.html` 详情功能
4. 增强 `dashboard.html` 风险趋势图

### Week 7-8: 调度中心 + 版本对比
1. 创建 `scheduler.html` 模板
2. 实现调度摘要/分发计划 UI
3. 增强 `case_detail.html` 版本对比功能

---

## 六、技术建议

### 6.1 前端架构

**当前架构**:
```
apps/web-ui-service/app/
├── templates/          # HTML 模板 (Jinja2)
└── static/             # 静态资源 (CSS/JS)
    ├── dashboard.js
    ├── workbench.js
    └── quality_clusters.js
```

**建议**:
- 保持当前架构 (简单直接)
- 新增页面遵循现有模式
- 复用现有组件 (pagination/dashboard cards)

### 6.2 API 调用规范

**现有模式**:
```javascript
// 1. 获取数据
async function fetchOverview() {
  const res = await fetch('/api/dashboard/overview');
  return res.json();
}

// 2. 渲染页面
function renderOverview(data) {
  document.getElementById('summary-pass-rate').textContent = data.pass_rate;
}

// 3. 定时刷新
setInterval(() => {
  fetchOverview().then(renderOverview);
}, 60000);
```

**建议**:
- 新增页面遵循现有模式
- 统一错误处理
- 统一 loading 状态管理

### 6.3 组件复用

**可复用组件**:
- `dashboard-kpi-grid` - KPI 卡片网格
- `dash-card` - 通用卡片
- `pagination` - 分页组件
- `risk-level-badge` - 风险等级徽章

**建议**:
- 提取公共组件到 `components/` 目录
- 建立组件库文档

---

## 七、总结

### 核心发现

1. **约 25% 的后端 API 功能在前端没有对应入口**
2. **最关键的缺口**: 测试点资产管理、执行门禁、缺陷管理
3. **部分功能有路由定义但无实现**: `/quality/flaky`, `/quality/trends`, `/gate`

### 业务影响

- **测试点中间层无法闭环**: 后端已支持 TestPointPlanV1，但前端无法查看/评审
- **发布决策缺乏可视化**: 门禁决策无法通过 UI 管理
- **缺陷追踪断裂**: 无法在平台内关联和追踪缺陷
- **质量趋势不可见**: 无法评估质量改进效果

### 建议行动

1. **立即启动 P0 任务**: 测试点资产管理 + 执行门禁 (2 周)
2. **本月完成 P1 任务**: 缺陷管理 + 调度中心 + 质量分析 (4 周)
3. **本季度完成 P2 任务**: 版本对比 + 覆盖矩阵 (4 周)

---

**文档维护**: 每次前端更新后同步此文档  
**最后更新**: 2026-04-02  
**下次回顾**: 2026-05-02
