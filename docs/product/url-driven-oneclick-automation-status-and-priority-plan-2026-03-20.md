# URL 驱动一键自动化进度与优先级计划（2026-03-20）

## 0. 如何使用本文档

这份文档现在承担两种用途：

1. 给当前 URL-first 改造提供**执行总表**。
2. 给已经完成的工作提供**归档入口**。

建议阅读顺序：

1. 先看“执行总表”和“当前结论”
2. 再看“与防幻觉修正版原则的对齐情况”
3. 只有在需要追溯改动细节时，再看“详细进展记录”

如果要看目标方案而不是当前进度，请转到：

- [url-driven-oneclick-automation-plan-2026-03-20.md](./url-driven-oneclick-automation-plan-2026-03-20.md)
- [url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md](./url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md)

如果要看当前真实架构和风险审计，请转到：

- [../architecture/current-architecture-and-flows.md](../architecture/current-architecture-and-flows.md)
- [../architecture/project-inventory-and-risk-audit-2026-03-21.md](../architecture/project-inventory-and-risk-audit-2026-03-21.md)

### 0.1 进度记录规则（2026-03-21 起生效）

从现在开始，这份文档里的进度记录统一遵守下面两条：

1. 同一时间只冻结一个“当前下一优先项”，避免并行开太多战线。
2. 所有新增进度都必须带**绝对完成时间**，格式统一为：
   - `完成时间：YYYY-MM-DD HH:MM:SS TZ`

## 1. 执行总表

### 1.1 当前阶段

当前阶段建议定义为：

`P0.9：URL 驱动可运行 + 三模型已收口 + review/gate/audit 已落盘 + 页面分析规则已模块化`

它代表：

1. 已经不是“只有 demo 能跑”的早期形态。
2. 还不是“页面语义、执行门禁、失败治理都成熟”的企业级稳定态。

### 1.2 已完成

| 方向 | 当前状态 | 说明 |
|---|---|---|
| URL-first 入口 | 已完成 | 生成页支持 URL 启动，`requirement` 不再是唯一入口 |
| 三个确认点 | 已完成 | 元素、测试点、风险三个确认点都已落盘、回显、即时刷新 |
| 审计闭环 | 已完成 | 确认人、确认时间、历史筛选、深链跳转已具备 |
| 三模型契约 | 已完成 | `PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1 / PageAnalysisBundleV1` 已收口 |
| 页面分析规则模块化 | 已完成 | 规则优先逻辑已拆到独立模块，router 不再内联全部规则 |
| 页面分析独立编排最小收口 | 已完成 | `page_analysis_pipeline.py` 已统一承接三模型归一化、bundle context 与 review/risk/run-view 消费入口 |
| 分析服务第一片收口 | 已完成 | `workbench_analysis_service.py` 已接管 page analysis context、risk report、failure analysis、review section 的核心纯函数；router 只保留薄包装 |
| 风险/审计共享工具下沉 | 已完成 | `normalize_risk_factors / build_risk_evidence / build_semantic_risk_evidence / build_risk_factor_summary / reviewer_display_name` 已迁入分析服务 |
| 入口级分析 wrapper 下沉 | 已完成 | `_normalize_page_surface / _normalize_page_object_draft / _consume_model_bundle` 已直接委托分析服务 |
| surface 入口 wrapper 下沉 | 已完成 | `_build_surface_element_candidate / _build_surface_element_candidates / _surface_confidence_summary / _surface_inferred_elements / _build_surface_result_from_snapshot` 已直接委托分析服务 |
| test point 链条下沉 | 已完成 | `_steps_to_points / _annotate_test_point_plan_review / _surface_candidate_confidence_index / _inherit_test_point_confidence_from_surface / _build_test_point_review_items` 已直接委托分析服务 |
| page object quality 下沉 | 已完成 | `_requires_search_flow / _required_page_elements / _element_signature / _build_page_object_quality` 已直接委托分析服务 |
| 默认元素与安全键下沉 | 已完成 | `_default_page_elements / _safe_element_key` 已直接委托分析服务，`_ensure_page_object` 复用 service 默认元素 |
| test point 归一化下沉 | 已完成 | `_normalize_test_point_plan_payload` 已直接委托分析服务的 `normalize_test_point_plan` |
| execution_gate 基础治理 | 已完成 | 系统门禁、人工覆盖、审批、撤销、回显已落地 |
| Web Runner v4.1 最小多页面增强 | 已完成 | `step.page`、page object cache、step/page/target 级精确报错、VariableResolver 确定性增强已落地 |
| `data-generation-agent` 最小可用 | 已完成 | 确定性生成器、模板复用、registry、cleanup 标记和 CLI 已收口 |
| 企业级数据治理收口 | 已完成 | `registry / cleanup / template` 的治理摘要、保留期口径、迁移提示已形成最小只读闭环 |
| 失败来源分类 | 已完成 | 分类、证据、人工复核、聚合回显、校准样本闭环已完成 |
| 测试点中间层与追溯链路 | 已完成 | 独立资产层、run 追溯、回归筛选、execution_gate 资产兜底、coverage 聚合已收口 |
| 执行调度统一任务模型 + 证据治理 | 已完成 | 统一 task 读模型、证据新鲜度、治理风险、TopN 样本摘要已收口 |
| `test-design-agent` 企业级结构化约束接入 | 已完成 | `requirement_spec` 结构化约束、`technique_summary`、`design_only` 治理与报告回显已形成最小企业级收口 |
| 平台基础设施第一片升级 | 已完成 | PostgreSQL/Redis/ELK Docker 骨架、统一 JSON 日志、`X-Request-Id` 链路、readiness 探针、`workbench` 四类核心运行态数据库优先存储适配、Alembic 迁移骨架已形成最小可运行收口 |

### 1.3 进行中

| 方向 | 当前状态 | 主要缺口 |
|---|---|---|
| 当前无新增冻结主线 | 已暂停 | 最近冻结主线 `test-design-agent 企业级结构化约束接入` 已于 `2026-03-22 14:08:42 CST` 收口；下一单一主优先项尚未重新冻结 |
| 平台基础设施骨架 | 已启动并完成第二片 | PostgreSQL 配置切换、Redis/ELK 接入、日志标准化、前后端 request id 透传已于 `2026-03-23 13:26:09 CST` 完成最小闭环；`workbench` 四类核心运行态数据库优先存储适配已于 `2026-03-23 14:19:37 CST` 完成；Alembic 迁移骨架与 Docker 启动前自动迁移已于 `2026-03-23 15:54:23 CST` 完成；SQLite + PostgreSQL 的真实迁移执行验证与旧库 bootstrap 过渡链路已于 `2026-03-23 16:37:32 CST` 完成；`defect-links / failure-source-calibrations` 第二批运行态切库、迁移版本 `20260323_170800`、单测+集成回归已于 `2026-03-23 17:27:21 CST` 完成，后续剩余主任务是进一步去文件化与 API/查询层全面切库 |

### 1.4 明确未完成

| 方向 | 当前状态 | 说明 |
|---|---|---|
| 独立 `PageSemanticModelV1` 稳定契约 | 未完成 | 当前更接近规则初判 + 语义补充 |
| Script 进入主执行链 | 未完成 | 当前默认主执行物仍是 YAML |
| Self-healing 边界完全收口 | 未完成 | 仍需继续压实到 locator/timeout/backup selector |
| 风险依据透明化 | 未完成 | 当前 `risk_report` 已可用，但风险因子解释和治理视图仍可继续增强 |

### 1.5 当前推荐优先级

| 优先级 | 当前建议 | 原因 |
|---|---|---|
| P0 | 待重新冻结 | 当前按要求已暂停开发，下一步应先选定新的单一主优先项，再继续推进 |
| P1 | 独立 `PageSemanticModelV1` 稳定契约 | 当前仍偏规则初判 + 语义补充，适合在治理主线后继续推进 |
| P2 | Script 进入主执行链 | 当前默认主执行物仍是 YAML，适合在治理与边界继续稳定后推进 |

### 1.5.1 当前冻结的下一优先项

自 `2026-03-22 14:08:42 CST` 起，上一单一优先项已收口；当前状态为：

`未冻结新的单一优先项（按要求暂停）`

当前状态更新：

1. 上一冻结项 `test-design-agent 企业级结构化约束接入（确定性优先）` 已于 `2026-03-22 14:08:42 CST` 完成最小收口，可视为 `100%`
2. 当前没有继续冻结新的主项，避免在暂停阶段无边界扩张
3. 下一步如继续，必须先重新指定单一主优先项，再进入新的实现闭环
4. 暂停期间只做：
   - 进度同步
   - 文档纠偏
   - 事实核对
5. 暂停期间明确不做：
   - 未冻结主项的代码扩张
   - 多主线并行推进
   - 以“顺手优化”为名继续叠加功能

### 1.6 当前不建议优先做

1. 再回头给 `execution_gate` 继续加外围 UI。
2. 直接把 `data-generation-agent` 做成 LLM-first 生成器。
3. 在失败来源分类还未稳定前，同时展开多个平台级大改。

## 2. 当前结论

当前项目不需要推翻重做，但需要从“边做边补”切换成“按防幻觉修正版计划推进”。

已经完成的部分，主要集中在：

1. URL 驱动链路的 Web 入口和主流程串联
2. 三个确认点的可视化、持久化、回显、即时刷新
3. 风险评估 agent 优先、规则兜底
4. 审计闭环：确认人、历史、筛选、时间线、深链导航
5. 登录态接入与匿名确认拦截
6. 分析服务第一片收口：page analysis context、risk report、failure analysis、review section 已从 router 下沉到 `workbench_analysis_service.py`

还没有真正完成的部分，主要集中在：

1. 页面分析规则模块进一步沉淀（从模块化走向可独立编排）
2. 测试点与元素依赖追踪的体系化深化（含低置信度继承）
3. 执行门禁与覆盖缺口治理的正式编排
4. Self-healing 边界治理与失败来源分类闭环

---

## 3. 详细进展记录

详细进展已拆分到独立归档文档，避免主计划文档继续膨胀：

- [url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md](./url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md)

主文档现在只保留：

1. 当前阶段判断
2. 已完成 / 未完成 / 推荐优先级
3. 防幻觉修正版对齐情况
4. 下一步执行建议

## 4. 与“防幻觉修正版原则”的对齐情况

## 4.1 已对齐

1. 高风险决策保留人工确认
2. 风险评估不是 AI 最终裁判
3. 结果验证仍以确定性执行状态和断言为主
4. 审计、确认、拒绝都有确定性记录
5. Web UI 继续沿用 FastAPI template + 原生 JS，没有切 Vue

## 4.2 部分对齐，但还未完全收口

1. 页面分析已拆到规则模块，但还没有形成可独立编排的 `PageAnalysisAgent`
2. Page Object 与 Test Point 仍主要由 `legacy_workbench.py` 编排，不是独立 agent
3. Test Point 已接入“低置信度元素向测试点置信度传递”主链路，但权重策略与业务分层仍需细化
4. 执行门禁已形成 `ExecutionGateV1` 并落盘回显，但还未升级为独立 Execution Planner 主编排器

## 4.3 尚未对齐

1. `PageSurfaceV1 / PageObjectDraftV1 / TestPointPlanV1` 已收口，页面分析也已模块化；但还没完成“规则模块 -> 独立编排 Agent”升级
2. 测试点依赖追踪虽已落基础字段，但还没有完成“低置信度元素向测试点置信度传递”的深化治理
3. 失败来源还没有稳定区分：
   - 页面分析错误
   - Page Object 错误
   - 用例设计错误
   - 应用真实 bug
4. Self-healing 还没有完全收束到：
   - locator 更新
   - timeout 调整
   - 备用 selector

---

## 5. 当前真实阶段判断

当前阶段应定义为：

`P0.9：URL 驱动可运行 + 三个核心中间模型已收口 + 页面分析规则模块化 + 治理链路模型消费化`

不是：

`P1：页面语义模型与执行门禁已稳定`

更不是：

`完整的 URL 驱动企业级全自动平台`

换句话说，当前已经把“用户可用”和“企业审计可追溯”这两层搭起来了，并且已完成三模型收口与页面分析规则模块化；但页面分析独立编排、低置信度依赖传递深化、以及执行治理主编排还没有完全收口。

---

## 6. 是否需要重新梳理优先级和计划存档

结论：需要。

原因不是方向错了，而是当前实现已经连续推进了很多“链路补齐”工作：

1. 审计已经明显超前于中间模型治理
2. 页面分析、Page Object、Test Point 还没有按统一契约收口
3. 如果不重新冻结优先级，后面容易继续在 UI/审计层加功能，而把真正的 P0 中间模型建设拖后

因此建议从现在开始，把后续计划冻结成：

`先收中间模型和规则抽取，再收依赖追踪和执行门禁，最后再继续平台治理增强。`

---

## 7. 修正版优先级

### P0：必须先完成

目标：把“规则优先的页面分析中间模型”收口

包含任务：

1. `PageSurfaceV1` 正式定稿
   - 状态：已完成
   - 元素
   - 结构分区
   - 认证状态
   - 稳定性
   - confidence / warnings / requires_review
2. `PageObjectDraftV1` 正式定稿
   - 状态：已完成
   - 元素来源
   - 定位器风险
   - 缺失 required
   - defaults / inferred / backup
3. `TestPointPlanV1` 正式定稿
   - 状态：已完成
   - 测试点
   - confidence
   - warnings
   - requires_review
   - review_summary
4. 页面分析逻辑改成：
   - DOM/role/placeholder/data-testid/aria 规则抽取优先
   - AI 只做语义命名和业务分类补充
   - 状态：已完成（规则模块已拆分，后续补独立编排）
5. 低置信度元素确认点继续沿现有 UI，但数据源切到正式模型
   - 状态：已完成（确认点与风险治理入口已消费三模型）

### P1：紧接着完成

目标：把“测试点与元素依赖、执行门禁”收口

包含任务：

1. 测试点 - 元素依赖追踪
2. 低置信度元素向测试点置信度传递
3. 测试点确认面板正式绑定依赖追踪结果
4. 执行门禁收口：
   - 页面分析质量不足是否允许继续
   - 关键元素缺失是否 block
   - 覆盖缺口是否 allow_with_warning
5. run 记录里补 gate decision 与 gate reasons

### P2：治理增强

目标：把失败归因、自愈边界、人工反馈闭环做好

包含任务：

1. 失败来源分类
2. Self-healing 严格限制边界
3. 人工修正反馈回流
4. 风险评估依据展示增强

---

## 8. 下一阶段建议执行顺序

建议从这里继续：

### 第一步

继续把页面分析规则模块推进为可独立编排组件，并深化“低置信度元素 -> 测试点置信度”传递治理。

### 第二步

把 `legacy_workbench.py` 内现有页面分析逻辑拆成“规则抽取优先”的独立模块，哪怕暂时还不拆成真正独立 agent，也先把职责拆干净。

### 第三步

把现有确认点 UI 改成真正消费这三个模型，而不是继续从临时 dict 结构拼。

### 第四步

补测试点 - 元素依赖追踪和执行门禁。

---

## 9. 执行原则

后续实现默认遵守以下边界：

1. 工程事实：
   - 规则和校验器优先
2. 业务推理：
   - AI 辅助
3. 高风险决策：
   - 人工兜底
4. Self-healing：
   - 只允许 locator / timeout / backup selector
   - 不允许改业务断言和业务流程

---

## 10. 当前建议

建议立即按本文件进入下一阶段，不再继续优先加新的审计展示层功能。

下一步的真正 P0 任务应当是：

1. 把页面分析进一步拆成规则优先模块
2. 让“确认点 1：元素确认”正式消费 `PageSurfaceV1`
3. 让页面对象相关展示和治理正式消费 `PageObjectDraftV1`
4. 让测试点相关展示和治理正式消费 `TestPointPlanV1`
5. 再进入低置信度依赖传递和执行门禁

这会比继续加外围 UI 功能更符合你刚刚确认的“防幻觉修正版”。

---

## 11. 最新进展补充（2026-03-21 起）

逐条里程碑与带时间戳的详细进展已迁移到归档文档：

- [url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md](./url-driven-oneclick-automation-progress-log-2026-03-20-to-2026-03-22.md)

后续新增进度继续遵守：

1. 同一时间只冻结一个主优先项
2. 每条进度必须带绝对完成时间
3. 主文档只同步当前结论，详细流水写入归档

### 11.1 平台基础设施主线增量进展（2026-03-23）

完成时间：`2026-03-23 17:27:21 CST`

本次在“平台基础设施骨架”主线补齐了第二批运行态切库最小闭环：

1. `workbench_state_store` 已把 `defect-links` 与 `failure-source-calibrations` 纳入数据库优先策略（读库优先、首读回填、文件镜像兼容）。
2. 新增 Alembic 迁移版本 `20260323_170800`，正式创建：
   - `workbench_defect_links`
   - `workbench_failure_source_calibrations`
3. 增加单测覆盖这两类状态在 DB 模式下的回填与写入替换行为，避免只“有接口”但无回归保护。
4. 迁移验证结果：
   - SQLite：`alembic upgrade head` 成功到 `20260323_170800`
   - PostgreSQL：`alembic upgrade head` 成功到 `20260323_170800`
5. 接口级回归补充：
   - 新增 `/api/defects` 在 DB 模式下的集成测试，覆盖写入/去重/查询/文件镜像
   - `test_workbench_multisource_endpoints.py` 全量回归：`85 passed`

### 11.2 Docker 启动链路热修复（2026-03-23）

完成时间：`2026-03-23 22:12:03 CST`

本次补充了一条数据库兼容迁移，解决容器在 PostgreSQL 旧表结构下启动失败的问题：

1. 新增迁移 `20260323_221200_fix_users_password_column`，将历史 `users.password_hash` 自动兼容为当前模型所需的 `users.hashed_password`（仅在存在列名漂移时执行）。
2. `web` 服务重建后，`bootstrap_database.py` + `alembic upgrade head` 可正常通过，服务可完成启动。
3. 一键验收脚本期望迁移版本已同步到 `20260323_221200`，整体验收 `PASS: 7 / FAIL: 0`。

### 11.3 ReturnApply 容器联通修复与执行链路验收（2026-03-26）

完成时间：`2026-03-26 17:02:11 CST`

本次按“先跑通再固化”原则完成了 ReturnApply 的容器联通修复与最小验收闭环：

1. 临时联通配置已生效（`ai-test-platform` 仓）：
   - `docker-compose.yml` 中 `web.environment.BASE_URL` 已切换为  
     `http://192.168.65.254:5173/login#/login`
2. 容器内预检查通过：
   - `check_base_url.py --base-url "http://192.168.65.254:5173/login#/login"` 返回可达
   - 环境变量核对通过：`BASE_URL` 与 `TEST_USERNAME=admin` 生效
3. 平台执行链路验收通过（连通性维度）：
   - 触发 run：`c2fa81b29d0a488ca02348ab1cf640d0`
   - 状态流转：`queued -> running -> failed`
   - `Realtime Logs`（SSE）持续输出 pytest 日志，链路可观测
4. 失败类型已从“前置联通错误”转为“业务/UI 执行阶段问题”：
   - 当前失败为登录阶段响应等待超时：`Timeout 10000ms exceeded while waiting for event "response"`
   - 本次 run 日志不再出现：
     - `Connection refused`
     - `BASE_URL is unreachable`
     - `Forbidden`
5. 失败留痕可用：
   - 产物目录包含 `failed.png`、`page.html`、`analysis.txt`、`suggestion.json`、`execution_record.json`
6. 非阻断已知项：
   - `Allure CLI not found in PATH` 仍存在，但不阻断主执行链路验收

固化待办（跨仓）：

1. `mall-admin-web` 仓库需在 `vite.config.*` 增加 `server.allowedHosts` 包含 `host.docker.internal`。
2. 前端重启后将 `BASE_URL` 切回 `http://host.docker.internal:5173/login#/login`，再次执行 `check_base_url.py` 验证。
3. 当前复验结果表明：`host.docker.internal` 仍会返回 `403 Forbidden`，符合 `allowedHosts` 未放行预期。

### 11.4 ReturnApply 主链路回归收口与 login/product 语义修正（2026-03-26）

完成时间：`2026-03-26 19:30:16 CST`

本次是在 11.3 的连通性基础上，继续把“能连上”推进到“能稳定执行主链路”：

1. 容器启动依赖补齐：
   - `apps/ai-orchestrator/requirements.txt` 新增 `starlette`
   - `orchestrator` 服务可从 `ModuleNotFoundError: No module named 'starlette'` 恢复启动
2. E2E 前置等待收紧：
   - `runners/web-playwright-python/conftest.py` 中 `clear_auth_state` 改为 `wait_until="domcontentloaded"`
   - `runners/web-playwright-python/pages/login_page.py` 中登录页跳转也改为 `domcontentloaded`
   - 目的：避免外部静态资源/图片拖住 `page.goto(..., wait_until="load")`
3. 页面语义对齐：
   - `assets/page-objects/web/product.page-object.yaml` 将 `product_menu` 的定位从 `商品列表` 修正为 `商品`
   - 与现网侧边栏真实文案对齐，避免点击错误菜单项
4. 验证结果：
   - `check_base_url.py --base-url "http://192.168.65.254:5173/login#/login"` 继续可达
   - 精确用例 `tests/test_yaml_ai_generated.py::test_yaml_ai_generated[chromium-AI Generated Product Case4]` 已通过
   - 这条主链路已经从“登录超时 / 菜单错位”收敛到稳定通过
5. 当前未处理项：
   - `Allure CLI not found in PATH` 已在后续 11.5 收口
   - `host.docker.internal` 的永久放行仍需在 `mall-admin-web` 仓库完成

这一步的结论是：当前平台已经不只是“网络可达”，而是恢复了一个可复现的主回归样例。下一步如果继续，只应切到新的冻结主项，不再围绕这条链路做无边界优化。

### 11.5 Allure CLI 容器化收口与报告生成恢复（2026-03-26）

完成时间：`2026-03-26 19:39:01 CST`

本次完成了 Allure CLI 的容器化补齐，并把报告生成链路恢复为可执行状态：

1. `web` 镜像新增 Allure 运行时依赖：
   - 安装 `openjdk-17-jre-headless`
   - 从 Maven 官方仓库下载 `allure-commandline-2.29.0`
   - 在镜像内创建 `/usr/local/bin/allure`
2. `manage_allure.py` 的 CLI 发现逻辑增强：
   - 先查 `ALLURE_HOME/bin/allure`
   - 再查 `/opt/allure/bin/allure`
   - 最后回退到 PATH
3. 容器内验证通过：
   - `java` 可用
   - `allure --version` 输出 `2.29.0`
   - `python /app/runners/web-playwright-python/tools/manage_allure.py info` 已能解析到 `/opt/allure/bin/allure`
4. 报告生成通过：
   - `python /app/runners/web-playwright-python/tools/manage_allure.py generate`
   - 结果：`Report successfully generated to /app/runners/web-playwright-python/allure-report`
5. 这意味着：
   - 运行链路不再因为 `Allure CLI not found in PATH` 中断
   - 失败时的报告生成步骤已恢复为可执行收口
