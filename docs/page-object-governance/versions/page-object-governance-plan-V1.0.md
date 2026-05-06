# 页面对象治理落地方案 V1

## Summary
基于当前项目现状，页面对象链路从“录制结果直接写入正式 `page_elements`”调整为“录制候选 -> 治理归并 -> 正式页面对象 -> 测试点映射 -> 可执行步骤”。  
本方案采用两项已确认前提：

- 前端对关键页面、关键控件正式补 `data-testid` / `data-qa`
- 录制结果拆成“候选元素”和“正式元素”两层，不再直接入正式 PO

目标是让页面对象对项目有明确归属、对业务有稳定语义、对测试点有可解析映射、对执行器有可靠定位。

## Key Changes
### 1. 资产模型分层
新增“候选元素层”，保留现有 `page_objects` / `page_elements` 作为正式层。

- 正式层继续表示可执行资产：
  - `page_objects` 表示 `project_code + client + page_code` 唯一页面
  - `page_elements` 表示可被测试点和执行器引用的正式元素
- 新增候选层，推荐独立表而不是在 `page_elements` 上硬塞状态：
  - `page_object_candidate_elements`
  - `page_object_candidate_groups`
- 候选元素最少字段：
  - `project_code`
  - `client`
  - `page_code`
  - `session_id`
  - `candidate_key`
  - `raw_locator_type`
  - `raw_locator_value`
  - `raw_role`
  - `raw_text`
  - `dom_signature`
  - `route`
  - `step_hit_count`
  - `quality_score`
  - `quality_tier`
  - `risk_tags`
  - `recommended_action`
  - `candidate_status`
  - `proposed_element_code`
  - `proposed_element_name`
  - `group_key`
- 候选状态固定为：
  - `pending`
  - `reviewed`
  - `promoted`
  - `rejected`
- 正式元素新增语义字段：
  - `business_type`
  - `business_domain`
  - `aliases_json`
  - `semantic_tags_json`
  - `locator_source`
  - `match_strategy`
  - `stability_level`
  - `review_status`
  - `origin_candidate_key`
- 正式元素不再接受 path/index 风格编码作为长期资产；`element_code` 必须业务命名。

### 2. 录制链路改造
当前 `stop_recorder_session(... ingest_to_page_object=True)` 的行为改为默认只入候选池，不直接创建正式元素。

- 录制停止后输出：
  - `recorded_steps`
  - `element_candidates`
  - `candidate_groups`
  - `promotion_summary`
- `stop` 接口行为调整：
  - 默认 `ingest_to_page_object=false`
  - 新增 `save_as_candidates=true`
  - 不再把高分候选直接写入 `page_elements`
- 候选生成规则：
  - `data-testid` / `data-qa` 优先级最高
  - `role + accessible name` 次高
  - `placeholder` 再次
  - `id/name` 中等
  - `css/xpath/text` 只作为候选，不允许直接晋升 A 级正式资产
- 候选去重分两层：
  - 同一 session 内按 `locator identity + route + role` 去重
  - 跨 session 按 `group_key` 聚类，形成“同一业务元素的录制历史”
- 候选命名规则：
  - 录制时生成的是 `proposed_element_code`，不是正式 `element_code`
  - 例：`login_button`、`username_input`、`password_visibility_toggle`
  - 禁止 `*-path-*`、`*-nth-*`、`录制元素N` 进入正式层

### 3. 正式页面对象治理流
新增“候选提升为正式元素”的治理流程。

- 正式流程：
  1. 录制候选入池
  2. 平台按分组聚合
  3. 用户在元素列表页审核命名、语义、主定位方式
  4. 提升为正式元素
  5. 正式元素写入 `page_elements`
- 提升时必须校验：
  - 页面归属匹配 `project_code + client + page_code`
  - `element_code` 唯一
  - `element_name` 非空
  - 至少存在一个主定位器
  - `business_type` 已确定
  - `locator_source` 已确定
- 正式元素支持多定位器，但 V1 继续兼容现有单主定位字段：
  - 主表保留 `locator_type/locator_value/role`
  - 备选定位器放入新增 JSON 字段或新表 `page_element_locators`
- 关键业务语义枚举先固定一版：
  - `input`
  - `button`
  - `link`
  - `menu`
  - `tab`
  - `switch`
  - `checkbox`
  - `radio`
  - `dialog`
  - `table`
  - `metric_label`
  - `metric_value`
  - `password_toggle`
  - `container`
- 关键页面要求配置页面锚点：
  - `page_anchor_elements`
  - 如 `page_title`、`main_nav`、`core_table`
  - 用于校验页面对象与项目/页面实际匹配

### 4. 页面对象与项目匹配规则
把“页面对象是否属于当前项目/页面”的判断做成硬约束。

- 一个正式页面对象唯一键仍是：
  - `project_code + client + page_code`
- 但新增页面匹配上下文：
  - `route_pattern`
  - `page_anchor_assertions`
  - `environment_scope`
- 录制写候选时必须附带：
  - 启动 URL
  - 归一化 route
  - session page_code
- 提升为正式元素时校验：
  - 候选 route 与页面对象 route_pattern 匹配
  - 候选命中至少一个页面锚点上下文
  - 不允许跨项目、跨页面提升
- 编译执行时只在当前页面对象空间内解析 target，不做跨页模糊匹配

### 5. 测试点到页面对象映射规则
测试点不直接映射 locator，只映射正式 `element_code`。

- 测试点资产中的 `involved_elements` 分为两层：
  - 原始自然语言元素
  - 解析后的 `involved_element_codes`
- 正式映射链路：
  1. 测试点提取原始业务描述
  2. 通过别名词典、语义词典、页面对象别名解析到 `element_code`
  3. 再由执行编译器把 `element_code` 解析成定位器
- `shared_backend/element_binding.py` 继续保留别名解析，但别名来源改为正式元素字段：
  - `element_code`
  - `element_name`
  - `aliases_json`
  - 派生别名
- V1 规则优先级固定：
  1. 明确 `element_code`
  2. 正式别名命中
  3. 元素名命中
  4. 角色派生别名命中
  5. 否则失败并返回待人工确认
- 不允许从测试点直接回退到原始 css/xpath 执行
- 特殊语义元素必须走专门业务类型：
  - `password_visibility_toggle` 不能当普通 icon
  - `metric_label` / `metric_value` 支持 `assert_metric`
  - 表格行内按钮后续通过 `row_action` 扩展，不在 V1 混入普通按钮解析

### 6. 前端与研发协作约束
正式引入可测试性标识契约。

- 关键页面和关键控件必须补：
  - `data-testid`
  - 或 `data-qa`
- 契约优先适用范围：
  - 登录页
  - 首页工作台
  - 菜单导航
  - 表单核心输入项
  - 主要提交按钮
  - 业务指标区域
- 治理标准：
  - 有 `data-testid` 的候选可直接进入高置信度审核流
  - 没有 `data-testid` 的 css/xpath 候选只能进入待审
- 平台侧要展示“可测试性覆盖率”：
  - 页面正式元素总数
  - 含测试标识的正式元素数量
  - 高稳定等级元素比例

### 7. API 与页面交互调整
保留现有页面对象页和录制页，但调整接口含义。

- 录制相关新增接口：
  - `GET /api/page-objects/{page_code}/candidate-elements`
  - `POST /api/page-objects/{page_code}/candidate-elements/promote`
  - `POST /api/page-objects/{page_code}/candidate-elements/reject`
  - `POST /api/page-objects/{page_code}/candidate-elements/merge`
- 现有 `stop_recorder_session` 返回值增加：
  - `candidate_count`
  - `candidate_groups`
  - `promotable_count`
  - `page_match_status`
- 页面对象列表页保持“页面视角”
- 元素列表页改成“正式元素 + 候选元素”双视图
- 默认入口逻辑：
  - 页面对象页看正式资产
  - 点“查看元素”进入元素列表页
  - 元素列表页再切换“正式元素/候选元素/录制历史”
- 录制历史页继续保留，并把回放与候选快照绑定

### 8. 迁移与兼容
现有历史 `page_elements` 不立即删除，但要做一次治理迁移。

- 给历史元素跑一次分类脚本：
  - 识别 `path/index/录制元素N` 风格编码
  - 标记为 `review_status=pending`
  - 计算 `stability_level=low`
- 历史元素不自动重命名为正式业务编码，避免破坏已有引用
- 对已有测试点与执行器：
  - 继续兼容读取老字段
  - 但新生成测试点只允许引用正式治理后的元素
- V1 默认行为：
  - 老元素可执行
  - 新元素必须走候选治理流

## Test Plan
### 后端
1. 录制停止后不直接写 `page_elements`，只写候选表。
2. 同一 locator 多次录制时进入同一 `candidate_group`。
3. `data-testid` 候选评分高于 css/xpath。
4. `password_toggle`、`metric_label`、`metric_value` 等语义元素可正确分类。
5. 候选提升为正式元素时，重复 `element_code` 会被阻断。
6. 测试点中的中文元素名可通过别名解析到正式 `element_code`。
7. 编译执行时仅允许正式元素参与 target 绑定。
8. 跨页面、跨项目候选提升必须失败。
9. 历史脏数据元素能被标记为低稳定等级，不影响已有读取。

### 前端
1. 录制页停止后展示候选元素列表、评分、建议动作、页面匹配状态。
2. 元素列表页可切换“正式元素/候选元素/录制历史”。
3. 候选元素支持提升、拒绝、合并。
4. 正式元素详情能看到业务类型、别名、定位来源、稳定等级。
5. 录制历史支持回放，并展示该次 session 产出的候选元素。

### 端到端
1. 研发已补 `data-testid` 的登录页，从录制到候选到正式提升，再到测试点映射，再到执行用例，全链路通过。
2. 无 `data-testid` 的页面录制后进入待审，不允许直接生成正式稳定资产。
3. `assert_metric` 场景使用正式语义元素成功编译和执行。

## Assumptions
- V1 不做完全自动提升，正式元素必须经过人工确认。
- V1 保留当前 `page_elements` 主定位字段结构，备选定位器以新增字段或子表扩展，不重做整个执行器。
- `data-testid` / `data-qa` 视为同等级稳定定位来源。
- 页面对象与测试点的连接键统一为正式 `element_code`。
- 录制器继续使用 Playwright codegen，但其产物仅作为候选来源，不作为最终资产。
