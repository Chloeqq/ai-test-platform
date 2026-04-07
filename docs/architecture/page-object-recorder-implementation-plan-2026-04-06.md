# 页面对象录制化实施方案（2026-04-06）

> 文档类型：实施计划（Implementation Plan）  
> 版本：v1.0  
> 目标：将“页面对象获取方式”统一为录制驱动，禁止手工自由录入定位器，保障可执行、可治理、可审计。  
> 适用范围：Web UI Service / AI Orchestrator / Runner 资产工具链

---

## 1. 目标理解

当前平台存在页面对象能力但仍以 YAML 编辑和工具接口为主，尚未形成“录制优先、治理闭环”的企业级能力。  
本计划聚焦落地以下结果：

1. 页面对象必须通过录制流程生成（默认路径）。
2. 定位器选择由系统策略引擎决定，不允许普通用户手工输入原始定位器。
3. 页面对象进入版本化、可追溯、可巡检的治理体系。
4. 不破坏现有主流程：`生成 -> 审核 -> 管理 -> 执行 -> 分析`。

---

## 2. 范围与边界

### 2.1 本期范围（Phase A，2 周）

1. 录制会话管理（创建、心跳、结束、中断恢复）。
2. 元素捕获与候选定位器生成。
3. 定位器评分与推荐策略（稳定性优先）。
4. 录制确认入库（页面、元素、版本）。
5. 执行层按 `element_code` 引用页面对象（不在用例存定位器）。

### 2.2 非本期范围（Phase B 以后）

1. Mobile 全量录制（本期只覆盖 Web）。
2. 可视化拖拽式页面对象设计器。
3. 复杂跨域 iframe 自动探测修复。
4. 全局自愈自动提交（本期仅建议，不自动改生产对象）。

---

## 3. 分层与目录归属

### 3.1 分层职责

1. 页面层：录制入口、候选预览、确认入库，不做定位器决策。
2. 应用编排层：录制会话状态机、提交流程编排。
3. 领域逻辑层：定位器策略评分、冲突检测、版本规则。
4. 基础设施层：Playwright 录制执行、数据库持久化、审计日志。
5. AI/治理层：后续接健康巡检、失败归因联动。

### 3.2 建议目录落位

1. `apps/web-ui-service/app/routers/page_objects_recorder.py`
2. `apps/web-ui-service/app/services/page_object_recorder_service.py`
3. `apps/web-ui-service/app/services/page_object_locator_strategy_service.py`
4. `apps/web-ui-service/app/models/page_object.py`
5. `apps/web-ui-service/app/schemas/page_object_recorder.py`
6. `apps/web-ui-service/app/static/page_object_recorder*.js`
7. `apps/web-ui-service/app/templates/page_object_recorder.html`

---

## 4. 两周执行排期（MVP）

## Week 1

### Day 1：模型与契约基线

1. 落 `page_objects/page_elements/page_element_versions/recorder_sessions` 数据模型。
2. 落 schema（DTO）与状态字典（session status、element status）。
3. 补 migration 草案与兼容策略（SQLite/PostgreSQL）。

交付标准：

- 能创建录制会话记录和空页面对象记录。

### Day 2：录制会话 API

1. `POST /api/page-objects/recorder/sessions`（创建会话）
2. `POST /api/page-objects/recorder/sessions/{id}/heartbeat`（心跳）
3. `POST /api/page-objects/recorder/sessions/{id}/stop`（结束会话）
4. `GET /api/page-objects/recorder/sessions/{id}`（查询状态）

交付标准：

- 会话超时、异常中断、重复 stop 具备幂等行为。

### Day 3：Playwright 捕获通道

1. 启动录制浏览器上下文（临时隔离 profile）。
2. 注入前端捕获脚本，回传元素上下文（tag/id/class/text/role/data-testid）。
3. 保存原始候选池（只进临时表，不入正式元素表）。

交付标准：

- 前端点击页面元素后可实时看到候选定位器列表。

### Day 4：定位器策略引擎

1. 规则优先级：`id > data-testid > name > role+name > css > xpath`
2. 风险降权：动态 class、nth-child、长 xpath。
3. 输出 `confidence/stability/reason` 三元组。

交付标准：

- 同一元素重复录制 3 次，推荐定位器一致率 >= 90%（基础页面）。

### Day 5：录制确认入库

1. `POST /api/page-objects/recorder/sessions/{id}/confirm`
2. 系统生成 `element_code`，写 `page_elements`。
3. 写 `page_element_versions` 首版快照。

交付标准：

- 禁止普通用户提交“手工定位器文本”绕过策略引擎。

## Week 2

### Day 6：管理页与详情页

1. 页面对象列表页接真实数据。
2. 元素详情页显示来源、推荐策略、版本信息。
3. 增加引用关系（被哪些 case 使用）。

交付标准：

- 能从 UI 查看元素版本与最近变更人。

### Day 7：执行层联动（最小）

1. Runner 读取 `element_code -> locator` 映射执行。
2. 用例步骤改为语义引用（不持有 locator）。
3. 回退路径：若映射缺失，标记阻塞并给出提示。

交付标准：

- 新录制页面对象可被至少 1 条用例成功执行。

### Day 8：审计与权限

1. 审计事件：创建会话、确认入库、发布版本。
2. 角色权限：录制员可提交，管理员可覆盖修订。
3. 非法操作审计（越权、无效会话）。

交付标准：

- 全链路操作可追溯到用户与时间。

### Day 9：自动化测试补齐

1. 集成测试：会话生命周期、确认入库、幂等 stop。
2. 策略单测：评分、降权、推荐稳定性。
3. UI 冒烟：录制 -> 确认 -> 列表可见。

交付标准：

- 关键用例全部通过；lint/typecheck 通过。

### Day 10：灰度发布与验收

1. 选 1-2 个项目灰度（登录/下单主链路）。
2. 对比录制前后失败率、定位器失效率。
3. 输出验收报告与 Phase B backlog。

交付标准：

- 灰度项目可稳定使用录制页面对象，不影响现有主流程。

---

## 5. API 契约草案（MVP）

## 5.1 创建录制会话

`POST /api/page-objects/recorder/sessions`

请求：

```json
{
  "project_code": "mall",
  "page_code": "login",
  "page_name": "登录页",
  "url": "https://test.example.com/login",
  "client": "web"
}
```

响应：

```json
{
  "item": {
    "session_id": "rec_20260406_0001",
    "status": "active",
    "ws_channel": "/ws/recorder/rec_20260406_0001",
    "expires_at": "2026-04-06T10:30:00+08:00"
  }
}
```

## 5.2 上报元素捕获

`POST /api/page-objects/recorder/sessions/{session_id}/captures`

请求：

```json
{
  "dom_context": {
    "tag": "button",
    "id": "login-btn",
    "class_name": "btn btn-primary",
    "text": "登录",
    "role": "button",
    "data_testid": "login-submit"
  }
}
```

响应：

```json
{
  "item": {
    "capture_id": "cap_001",
    "candidates": [
      {"locator_type": "id", "locator_value": "#login-btn", "score": 0.98},
      {"locator_type": "data-testid", "locator_value": "[data-testid='login-submit']", "score": 0.95},
      {"locator_type": "role", "locator_value": "button[name='登录']", "score": 0.82}
    ],
    "recommended": {"locator_type": "id", "locator_value": "#login-btn"}
  }
}
```

## 5.3 确认入库

`POST /api/page-objects/recorder/sessions/{session_id}/confirm`

请求：

```json
{
  "captures": [
    {
      "capture_id": "cap_001",
      "element_name": "登录按钮",
      "element_key": "login_submit_button"
    }
  ],
  "publish": false
}
```

响应：

```json
{
  "item": {
    "page_object_id": 1001,
    "saved_elements": 1,
    "version": 1
  }
}
```

---

## 6. 数据结构草案（MVP）

## 6.1 `page_objects`

1. `id` bigint pk
2. `project_code` varchar(32) not null
3. `client` varchar(16) not null default `web`
4. `page_code` varchar(64) not null
5. `page_name` varchar(128) not null
6. `url` text not null
7. `status` varchar(20) not null default `draft`
8. `created_by` varchar(64) not null
9. `updated_by` varchar(64) not null
10. `created_at/updated_at` timestamp

唯一键：

- `(project_code, client, page_code)`

## 6.2 `page_elements`

1. `id` bigint pk
2. `page_object_id` bigint fk
3. `element_code` varchar(128) not null
4. `element_name` varchar(128) not null
5. `locator_type` varchar(32) not null
6. `locator_value` text not null
7. `selector_confidence` decimal(5,4) not null
8. `selector_stability_score` decimal(5,4) not null
9. `health_status` varchar(20) not null default `unknown`
10. `source` varchar(20) not null default `recorder`
11. `created_by/updated_by` varchar(64)
12. `created_at/updated_at` timestamp

唯一键：

- `(page_object_id, element_code)`

## 6.3 `page_element_versions`

1. `id` bigint pk
2. `page_element_id` bigint fk
3. `version_no` int not null
4. `locator_type/locator_value` snapshot
5. `change_reason` text
6. `changed_by` varchar(64)
7. `created_at` timestamp

唯一键：

- `(page_element_id, version_no)`

## 6.4 `recorder_sessions`

1. `id` bigint pk
2. `session_id` varchar(64) unique
3. `project_code/page_code/client/url`
4. `status` varchar(20) (`active/stopped/expired/failed`)
5. `started_by` varchar(64)
6. `started_at/heartbeat_at/stopped_at`
7. `error_message` text

---

## 7. 验证方案

## 7.1 自动化验证结果（验收口径）

1. 会话 API：创建/心跳/停止/重复停止幂等，全部 PASS。
2. 策略引擎：定位器评分与推荐一致性测试，全部 PASS。
3. 入库链路：confirm 后 `page_objects/page_elements/versions` 写入一致，PASS。
4. 执行联动：按 `element_code` 执行通过最小冒烟，PASS。
5. 工程校验：`ruff + mypy + pytest` 关键集通过。

## 7.2 手动验证步骤（路径 / 预期 / 验证目标）

| 路径 | 预期结果 | 验证目标 |
|---|---|---|
| 页面对象录制页 -> 开始录制 | 生成 active 会话并打开目标页 | 会话链路可用 |
| 点击元素 -> 候选列表 | 出现推荐定位器与评分 | 策略引擎输出可见 |
| 确认入库 | 元素进入列表且生成 version=1 | 入库与版本可追踪 |
| 引用该元素的用例执行 | 执行成功或给出明确阻塞提示 | 执行层联动可用 |

---

## 8. 回滚方案

1. 保留旧 YAML 读取逻辑作为兼容路径（只读）。
2. 录制能力走特性开关：`PAGE_OBJECT_RECORDER_ENABLED=false` 可快速关闭。
3. 回滚粒度：
   - API 层回滚：禁用 recorder 路由注册
   - 数据层回滚：保留表，不删数据，只停写
   - 执行层回滚：切回原 locator 解析逻辑

---

## 9. 风险与补齐建议

1. 风险：复杂 iframe/shadow DOM 场景录制成功率波动。  
建议：MVP 先覆盖主文档流，复杂场景进入白名单迭代。

2. 风险：前端样式频繁变更导致定位器稳定性下降。  
建议：优先鼓励 `data-testid`，并在 CI 中加入元素健康巡检告警。

3. 风险：录制结果与用例语义不一致。  
建议：提交确认页必须填写业务语义名，且与 `element_code` 规范校验联动。

---

## 10. 下一步（Phase B 入口）

1. 每日巡检任务 + 健康看板 + 告警。
2. 元素变更影响分析（关联用例、关联失败趋势）。
3. 页面对象发布审批（draft -> review -> active）。
4. AI 生成与页面对象的强绑定校验（缺元素即阻断生成发布）。
