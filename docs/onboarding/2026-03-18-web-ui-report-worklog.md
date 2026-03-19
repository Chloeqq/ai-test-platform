# 2026-03-18 Web UI 与测试报告工作归档

> 迁移标注（2026-03-19）  
> 本文档是历史工作记录。文中出现的 `web-ui/services/*`、`web-ui/tests/*`、`apps/web-ui-service/src/*` 均为旧路径，当前已下线。  
> 当前生效实现请以 `apps/web-ui-service/app/*`（FastAPI）为准，`web-ui/app.py` 仅保留兼容入口。

## 今日目标

围绕 `web-ui` 和测试报告模块，完成以下几件事：

- 把原来过于集中的测试报告页面按内容拆分
- 保留完整 Allure 报告，但降低单页信息噪音
- 增强失败诊断、缺陷关联和报告导航体验
- 解决 `web-ui` 本地服务启动不稳定的问题

---

## 今日完成的主要工作

### 1. 新增独立 `web-ui` 模块并跑通基础链路

当前 `web-ui` 已作为独立 Flask 模块存在，核心能力包括：

- 项目选择
- AI 生成用例
- 在线编辑 YAML
- 触发 pytest 执行
- 实时日志展示
- 查看失败分析
- 一键修复
- 再运行验证

关键文件：

- [`web-ui/app.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/app.py)
- [`web-ui/services/asset_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/asset_service.py)
- [`web-ui/services/ai_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/ai_service.py)
- [`web-ui/services/report_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/report_service.py)
- [`web-ui/services/healing_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/healing_service.py)

---

### 2. 首页工作台完成度提升

首页已具备完整工作台形态：

- 新手 `Quick Start` 步骤区
- 项目选择与用例列表
- YAML 在线编辑
- `Run Test`
- `Realtime Logs`
- `Failure Analysis`
- `One-Click Heal`
- `Rerun`

并补充了：

- 中文小字说明
- 状态徽标
- 当前步骤高亮
- 首页直达各报告页导航卡

关键文件：

- [`web-ui/templates/index.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/index.html)

---

### 3. 测试报告从单页大杂烩拆分为 5 个页面

原来的 `/report` 内容过多，已经按内容类别拆分为：

- 总览页：
  - [`/report`](http://127.0.0.1:8013/report)
- 失败详情页：
  - [`/report/failures`](http://127.0.0.1:8013/report/failures)
- 资产与集成页：
  - [`/report/context`](http://127.0.0.1:8013/report/context)
- 性能与耗时页：
  - [`/report/performance`](http://127.0.0.1:8013/report/performance)
- 完整 Allure 页：
  - [`/report/allure`](http://127.0.0.1:8013/report/allure)

对应模板文件：

- [`web-ui/templates/report.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report.html)
- [`web-ui/templates/report_failures.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_failures.html)
- [`web-ui/templates/report_context.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_context.html)
- [`web-ui/templates/report_performance.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_performance.html)
- [`web-ui/templates/report_allure.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_allure.html)

---

### 4. 报告内容完成四层结构整理

当前报告已基本按“四层结构”组织：

#### 核心概览层

- 执行摘要
- 通过率
- 健康度看板
- 高风险失败数
- 可修复建议数

#### 失败详情与诊断层

- 失败 case 列表
- 失败详情
- 截图预览
- HTML 预览
- 视频预览
- AI 分析文本
- 自愈建议 JSON

#### 资产与集成层

- Git Commit ID
- Commit Message
- Build Version
- Image Tag
- Base URL
- Browser
- 执行环境

#### 性能与耗时层

- 平均耗时
- 最大耗时
- 历史耗时差值
- Top 10 最慢用例

相关数据汇总逻辑主要在：

- [`web-ui/services/report_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/report_service.py)

---

### 5. 完整 Allure 报告保留并内嵌

没有删掉 Allure，而是把它保留为独立页面：

- [`/report/allure`](http://127.0.0.1:8013/report/allure)

同时继续直接服务：

- [`/allure/`](http://127.0.0.1:8013/allure/)

这样：

- 管理摘要和结构化信息走 `web-ui`
- 原始趋势图和完整附件继续看 Allure

---

### 6. 缺陷关联能力落地

在失败详情页中已加入本地缺陷关联能力：

- 可手工关联 `JIRA / TAPD / Manual`
- 支持 `Case ID / Defect ID / URL / Note`
- 缺陷信息会保存到本地 JSON

持久化文件：

- [`web-ui/state/reporting/defect-links.json`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/state/reporting/defect-links.json)

接口：

- `GET /api/defects`
- `POST /api/defects`

失败用例列表已支持：

- 显示 `Defects N`
- 显示前 2 个缺陷标签
- `All / Linked / Unlinked` 筛选
- 按 case / feature / defect id 搜索

---

### 7. 统一报告导航和页面说明

5 个报告页已经统一成一套顶部 tabs：

- `Overview`
- `Failures`
- `Context`
- `Performance`
- `Allure`

并为每个 tab 增加了中文说明。  
同时每个页面标题下方也增加了 `本页说明 / What To Check Here` 提示卡，用来告诉用户：

- 这页重点看什么
- 什么场景应该进入这页

---

### 8. 修复 `web-ui` 本地服务不稳定问题

问题现象：

- 浏览器访问 `127.0.0.1:8013` 时偶发 `ERR_CONNECTION_REFUSED`

根因：

- `web-ui/app.py` 以前使用 `debug=True`
- Flask reloader 在后台启动时容易导致父子进程分叉，服务表面看似启动，实际未稳定监听端口

处理方式：

- 默认关闭 `debug`
- 默认关闭 `use_reloader`
- 仅在显式设置 `WEB_UI_DEBUG=true` 时启用调试模式

相关文件：

- [`web-ui/app.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/app.py)

---

## 今日新增或重点修改的文件

### `web-ui` 模块

- [`web-ui/app.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/app.py)
- [`web-ui/README.md`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/README.md)
- [`web-ui/requirements.txt`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/requirements.txt)

### 首页与工作台

- [`web-ui/templates/index.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/index.html)
- [`web-ui/templates/generate.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/generate.html)
- [`web-ui/templates/preview.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/preview.html)
- [`web-ui/templates/history.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/history.html)
- [`web-ui/templates/case_detail.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/case_detail.html)

### 报告相关

- [`web-ui/templates/report.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report.html)
- [`web-ui/templates/report_failures.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_failures.html)
- [`web-ui/templates/report_context.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_context.html)
- [`web-ui/templates/report_performance.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_performance.html)
- [`web-ui/templates/report_allure.html`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/templates/report_allure.html)
- [`web-ui/services/report_service.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/services/report_service.py)

### 测试

- [`web-ui/tests/test_app.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/tests/test_app.py)
- [`web-ui/tests/web_ui_test_helpers.py`](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/tests/web_ui_test_helpers.py)

---

## 今日验证结果

执行过的核心验证：

```bash
python3 -m py_compile web-ui/app.py web-ui/tests/test_app.py
./.venv/bin/python -m pytest -q web-ui/tests/test_app.py
```

结果：

- `8 passed`

在线访问已验证：

- [`http://127.0.0.1:8013/`](http://127.0.0.1:8013/)
- [`http://127.0.0.1:8013/report`](http://127.0.0.1:8013/)
- [`http://127.0.0.1:8013/report/failures`](http://127.0.0.1:8013/report/failures)
- [`http://127.0.0.1:8013/report/context`](http://127.0.0.1:8013/report/context)
- [`http://127.0.0.1:8013/report/performance`](http://127.0.0.1:8013/report/performance)
- [`http://127.0.0.1:8013/report/allure`](http://127.0.0.1:8013/report/allure)

---

## 当前状态总结

今天的工作完成后，`web-ui` 已经从一个“能跑通功能的页面集合”，提升成了一个更完整的浏览器工作台：

- 首页负责操作流
- 报告总览页负责管理层概览
- 各拆分页负责不同维度的排查与追溯
- Allure 继续保留完整趋势和原始附件

整体上已经具备：

- 操作台
- 报告台
- 失败诊断页
- 缺陷关联页
- 性能观察页
- 完整 Allure 入口

---

## 后续建议

下一步优先建议：

1. 给每个报告页增加右上角的统一“返回首页 / 返回总览 / 打开 Allure 新标签”快捷入口
2. 给失败详情页补“按模块聚类失败用例”
3. 给性能页补简单趋势小图，而不只是数值和列表
4. 如果后续接 Jira/TAPD API，再把本地缺陷关联升级成真实缺陷系统同步
