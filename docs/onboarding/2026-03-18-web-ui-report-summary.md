# 2026-03-18 Web UI 与测试报告一页式总结

> 迁移标注（2026-03-19）  
> 本文档为历史总结。若你看到 `web-ui/services/*` 或 `web-ui/tests/*` 相关描述，请按“历史信息”理解。  
> 当前后端以 `apps/web-ui-service/app/*`（FastAPI + SQLite + JWT）为准。

## 今日完成

### 1. `web-ui` 独立工作台可用

已完成浏览器内操作闭环：

- 选择项目
- 查看用例
- 在线编辑 YAML
- 触发 pytest 执行
- 实时查看日志
- 查看失败分析
- 一键修复
- 再运行验证

入口：

- [http://127.0.0.1:8013/](http://127.0.0.1:8013/)

---

### 2. 测试报告按类型拆分

原来过于集中的测试报告页已拆成 5 个页面：

- 总览：
  - [http://127.0.0.1:8013/report](http://127.0.0.1:8013/report)
- 失败详情：
  - [http://127.0.0.1:8013/report/failures](http://127.0.0.1:8013/report/failures)
- 资产与集成：
  - [http://127.0.0.1:8013/report/context](http://127.0.0.1:8013/report/context)
- 性能与耗时：
  - [http://127.0.0.1:8013/report/performance](http://127.0.0.1:8013/report/performance)
- 完整 Allure：
  - [http://127.0.0.1:8013/report/allure](http://127.0.0.1:8013/report/allure)

收益：

- 降低单页信息噪音
- 管理视角和排查视角分离
- 保留 Allure 全量趋势图和附件能力

---

### 3. 报告结构完成四层整理

当前报告已按 4 层组织：

- 核心概览层
  - 执行摘要、通过率、健康度看板
- 失败详情与诊断层
  - 失败 case、截图、HTML、视频、AI 分析、自愈建议
- 资产与集成层
  - Git、Build、环境、执行上下文
- 性能与耗时层
  - 平均耗时、最大耗时、最慢用例

---

### 4. 缺陷关联能力落地

失败详情页已支持本地缺陷关联：

- `JIRA / TAPD / Manual`
- `Case ID / Defect ID / URL / Note`
- 缺陷信息持久化到本地 JSON

持久化文件：

- [defect-links.json](/Users/bettyhuang/PycharmProjects/ai-test-platform/web-ui/state/reporting/defect-links.json)

并支持：

- 已关联/未关联筛选
- 缺陷标签展示
- 失败列表搜索

---

### 5. 报告导航和说明体验增强

报告页已补齐：

- 顶部统一 tabs
- 中英双语说明
- 每页“本页说明”提示卡

收益：

- 用户知道当前页该看什么
- 拆页后不会迷路

---

### 6. 解决 `web-ui` 服务不稳定问题

问题：

- 本地访问 `127.0.0.1:8013` 偶发 `ERR_CONNECTION_REFUSED`

根因：

- Flask `debug + reloader` 导致后台启动不稳定

处理：

- 默认关闭 `debug`
- 默认关闭 `use_reloader`
- 仅在 `WEB_UI_DEBUG=true` 时启用调试模式

---

## 今日结果

- `web-ui` 已可稳定访问
- 报告模块已完成拆分
- Allure 与结构化报告已并行保留
- 失败诊断和缺陷闭环能力已具备基础形态

---

## 已验证

```bash
python3 -m py_compile web-ui/app.py web-ui/tests/test_app.py
./.venv/bin/python -m pytest -q web-ui/tests/test_app.py
```

结果：

- `8 passed`

---

## 下一步建议

1. 给失败详情页增加“按模块聚类失败 case”
2. 给性能页增加简单趋势图
3. 接真实 Jira / TAPD API，替换本地缺陷占位
