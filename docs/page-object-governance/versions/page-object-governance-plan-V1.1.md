# 页面对象治理方案细化 V1.1

## Summary
在当前仓库基础上，把页面对象链路正式收敛为：

`录制会话 -> 候选元素(candidate) -> 候选分组(group) -> 正式页面元素(page_elements) -> 测试点映射 -> 执行编译`

本版细化已经锁定以下关键决策：

- 候选层采用双表：`candidate_elements + candidate_groups`
- 正式元素采用分层语义枚举，不走自由标签
- 候选审核入口放在“元素列表页”
- 关键元素要求 `data-testid/data-qa` 与正式 `element_code` 一一对应
- 历史脏数据只做“待治理标记”，不自动改编码
- 测试点别名来源采用“正式维护 + 平台派生”，不直接吸纳录制原文

这份方案的目标是做到：实现人员不需要再决定数据边界、审核入口、编码契约、历史兼容策略。

## Data Model
### 1. 正式层保持现有主模型
沿用现有：

- `page_objects`
- `page_elements`
- `page_element_versions`
- `page_object_refs`
- `page_element_health_checks`
- `page_object_recorder_sessions`

但扩展 `page_elements` 字段，使其从“定位器记录”升级为“正式测试资产”。

### 2. 正式元素新增字段
`page_elements` 新增以下字段：

- `business_type`
  - 固定枚举，见下文语义目录
- `business_domain`
  - 例如 `auth`, `dashboard`, `table`, `form`
- `semantic_tags_json`
  - 辅助标签数组
- `aliases_json`
  - 人工维护别名数组
- `locator_source`
  - 枚举：`testid`, `qa`, `role_name`, `placeholder`, `id`, `name`, `css`, `xpath`, `manual`
- `match_strategy`
  - 枚举：`exact`, `alias`, `derived`, `composite`
- `stability_level`
  - 枚举：`high`, `medium`, `low`
- `review_status`
  - 枚举：`approved`, `pending`, `rejected`
- `origin_candidate_key`
  - 首次提升来源候选
- `route_scope`
  - 当前元素有效的 route 或 route pattern
- `anchor_required`
  - 是否要求页面锚点上下文存在

V1 保留现有 `locator_type/locator_value/role/backup_locator` 作为正式主定位结构，不重做执行器。

### 3. 候选层采用双表
新增 `page_object_candidate_groups`：

- 唯一键：`project_code + client + page_code + group_key`
- 核心字段：
  - `group_key`
  - `proposed_element_code`
  - `proposed_element_name`
  - `business_type_guess`
  - `quality_tier`
  - `max_score`
  - `session_count`
  - `candidate_count`
  - `promotion_status`
  - `recommended_action`
  - `route_scope`
  - `latest_session_id`

新增 `page_object_candidate_elements`：

- 唯一键：`session_id + candidate_key`
- 核心字段：
  - `project_code`
  - `client`
  - `page_code`
  - `session_id`
  - `candidate_key`
  - `group_key`
  - `raw_locator_type`
  - `raw_locator_value`
  - `raw_role`
  - `raw_text`
  - `dom_signature`
  - `route`
  - `step_hit_count`
  - `quality_score`
  - `quality_tier`
  - `risk_tags_json`
  - `recommended_action`
  - `candidate_status`
  - `proposed_element_code`
  - `proposed_element_name`
  - `probe_status`
  - `probe_visible`
  - `probe_interactable`
  - `ingest_block_reason`

### 4. 候选状态与正式状态
候选状态固定：

- `pending`
- `reviewed`
- `promoted`
- `rejected`
- `merged`

候选分组状态固定：

- `pending`
- `partially_promoted`
- `promoted`
- `rejected`

正式元素状态继续使用现有：

- `active`
- `inactive`
- `deprecated`

正式元素审核状态额外控制是否能被测试点引用：

- `approved` 才可用于新测试点映射
- `pending` 不参与新映射
- `rejected` 不参与映射

## Semantics And Naming
### 1. 正式 `element_code` 规则
正式 `element_code` 统一采用业务语义 snake_case，且与关键前端 `data-testid/data-qa` 一一对应。

规则：

- 仅允许小写字母、数字、下划线
- 不包含页面前缀
- 不包含 locator 类型
- 不包含 path/index/nth/order
- 不允许 `recorded_*`、`element_*`、`*-path-*` 风格

示例：

- `username_input`
- `password_input`
- `login_button`
- `password_visibility_toggle`
- `weekly_sales_metric_label`
- `weekly_sales_metric_value`
- `order_search_button`

### 2. `data-testid/data-qa` 契约
关键元素要求：

- `data-testid` 或 `data-qa` 必须存在其一
- 值与正式 `element_code` 完全一致
- 页面对象正式主定位优先读取该标识

V1 关键元素范围：

- 登录页全部核心输入和按钮
- 首页导航和关键 KPI 区
- 列表页核心筛选项、搜索按钮、表格主区域
- 表单页必填项、提交按钮、取消按钮
- 表格行操作中稳定可测试的主操作按钮

### 3. 正式语义枚举
V1 固定语义目录：

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
- `container`
- `metric_label`
- `metric_value`
- `password_toggle`

V1 不开放自由语义字符串；允许 `semantic_tags_json` 做补充。

### 4. 别名来源规则
测试点映射只认正式资产别名，不直接吃录制原文。

别名来源顺序固定：

1. `element_code`
2. `element_name`
3. `aliases_json`
4. role 派生别名
   - 如 `登录按钮`
   - `用户名输入框`
   - `密码输入框`

不采用：

- 候选录制时抓到的原始全文本
- 动态文本
- path 片段
- css/xpath 内容本身

## Recorder And Promotion Flow
### 1. 录制停止接口改造
`POST /api/page-objects/recorder/sessions/{session_id}/stop`

V1 行为调整：

- 默认不写正式 `page_elements`
- 默认写候选表
- 返回候选明细、分组、推荐动作、页面匹配状态

请求语义调整为：

- `save_as_candidates=true`
- `ingest_to_page_object=false`
- `verify_locators` 保留

返回体新增：

- `candidate_count`
- `candidate_groups`
- `page_match_status`
- `promotable_count`
- `rejected_count`

### 2. 候选分组规则
`group_key` 生成规则固定为：

- 优先：`testid/qa-id` 值
- 其次：`role + accessible name`
- 再次：`placeholder`
- 再次：`id/name`
- 最后：稳定 hash 兜底

跨 session 只要 `project_code + client + page_code + group_key` 一致，即归入同一候选分组。

### 3. 元素列表页审核流
审核入口固定放在“元素列表页”，分三栏或三 tab：

- 正式元素
- 候选元素
- 录制历史

候选元素区需要支持：

- 查看候选明细
- 查看所属分组
- 修改 `proposed_element_code`
- 修改 `proposed_element_name`
- 选择 `business_type`
- 提升为正式元素
- 拒绝候选
- 合并候选到已有正式元素

录制页只负责：

- 启动录制
- 停止录制
- 看回放
- 跳转到元素列表页继续治理

### 4. 提升规则
候选提升为正式元素时必须满足：

- 所属页面对象存在
- `proposed_element_code` 合规
- `proposed_element_name` 非空
- `business_type` 已选择
- 候选或页面已有 route 与 `page_code` 匹配
- 主定位来源不是被阻断的动态 text
- 若前端是关键元素，必须存在 `data-testid/data-qa`

提升策略：

- 如果正式元素不存在：创建新 `page_element`
- 如果目标正式元素已存在：作为候选合并，不新增重复正式元素
- 提升成功后：
  - 候选状态改 `promoted`
  - 分组状态更新
  - 正式元素记录 `origin_candidate_key`

## Matching And Execution
### 1. 页面对象与项目匹配
页面对象唯一键继续是：

- `project_code + client + page_code`

但匹配校验新增两层约束：

- `route_scope`
- 页面锚点上下文

V1 页面锚点采用正式元素中的一部分元素标记实现，不单独建复杂 DSL。至少支持：

- `page_title`
- `main_nav`
- `core_table`
- `primary_form`

### 2. 测试点映射规则
测试点映射链路固定：

1. 提取原始 `involved_elements`
2. 使用正式页面对象别名映射到 `element_code`
3. 编译器用 `element_code` 绑定正式定位器

V1 失败策略固定：

- 找不到正式元素时，不回退 raw locator
- 编译阶段阻断，并返回缺失 target 列表
- 前端展示“待补元素映射”

### 3. 正式元素参与编译的资格
只有满足以下条件的正式元素能进入新用例编译：

- `status=active`
- `review_status=approved`
- `stability_level != low`，或明确人工放行
- 所属页面匹配当前 `page_code`

### 4. 特殊语义处理
V1 特殊处理项固定：

- `password_toggle`
  - 可映射到“密码显隐切换”类步骤
- `metric_label`
  - 可作为 `assert_metric` 标签 target
- `metric_value`
  - 仅作为展示语义，不直接被普通 click/fill 使用
- `table`
  - 作为可见性或加载锚点
- `container`
  - 只作为锚点或结构断言，不作为主要操作 target

## Migration, APIs, And UI
### 1. 历史数据迁移
现有 `page_elements` 不做自动改编码。

迁移脚本只做标记：

- 命中以下模式的元素标记为 `review_status=pending`
  - `录制元素N`
  - `*-path-*`
  - `*-nth-*`
  - locator 明显依赖索引
- `stability_level=low`
- `locator_source` 按现有 locator 推断

旧元素仍可被老用例执行，但默认不进入新测试点映射候选。

### 2. 新增接口
V1 新增接口集合：

- `GET /api/page-objects/{page_code}/candidate-groups`
- `GET /api/page-objects/{page_code}/candidate-elements`
- `POST /api/page-objects/{page_code}/candidate-elements/promote`
- `POST /api/page-objects/{page_code}/candidate-elements/reject`
- `POST /api/page-objects/{page_code}/candidate-elements/merge`
- `POST /api/page-objects/{page_code}/candidate-groups/batch-promote`
- `POST /api/page-objects/{page_code}/candidate-groups/batch-reject`

现有接口保留，但语义调整：

- `list_page_elements` 默认只返回正式元素
- 候选元素不混在正式元素列表里
- 录制 stop 返回候选信息，但不直接落正式元素

### 3. 文档归档约定
方案文档后续统一归档到：

- `docs/page-object-governance/`

建议目录内容：

- `overview.md`
- `data-model.md`
- `promotion-flow.md`
- `naming-contract.md`
- `test-point-mapping.md`
- `migration-plan.md`

当前不创建目录，只把它作为后续文档落点约定。

## Test Plan
1. 录制停止后只产生候选元素，不新增正式元素。
2. 同一元素跨两次录制进入同一 `candidate_group`。
3. 含 `data-testid` 的候选评分显著高于同功能 css/xpath 候选。
4. 元素列表页可完成候选提升、拒绝、合并三种操作。
5. 正式元素 `element_code` 与 `data-testid` 不一致时，关键元素提升失败。
6. 历史脏数据元素被标记为 `pending + low`，但老用例仍可执行。
7. 测试点使用中文别名时能稳定解析到正式 `element_code`。
8. 找不到正式元素时，生成用例编译阻断，不回退 raw locator。
9. `password_toggle` 和 `metric_label` 能按特殊语义进入对应编译流程。

## Assumptions
- V1 不做全自动候选提升，正式元素必须人工审核。
- V1 不要求一次性覆盖所有页面，只先覆盖关键页面和关键控件。
- `data-testid` 与 `data-qa` 视作同级定位来源，二选一即可。
- V1 先在现有执行器字段结构上扩展，不重构 runner 的整体定位模型。
- 后续若需要复杂多定位器或页面锚点 DSL，再作为 V2 单独设计。
