# 页面对象治理方案细化 V1.2

## Summary
在 V1.1 基础上，进一步把两块最关键的内容压实：

- 数据库表结构与字段定义
- 前端页面交互与审核操作流

目标是把“候选元素治理”真正落成一套闭环：录制得到候选，候选进入分组，分组在元素列表页审核，审核后提升为正式元素，正式元素再参与测试点映射和执行编译。

本版继续保持：

- 不改动现有执行器主结构
- 不自动重命名历史正式元素
- 不允许新链路回退到 raw locator 执行

## Database Design
### 1. 现有表保留并扩展
#### `page_objects`
继续作为页面主资产表，不拆表。

新增字段：

- `route_pattern`
  - `String(256)`，默认空
  - 用于声明页面对象匹配的主 route
- `anchor_config_json`
  - `JSON`
  - 页面锚点配置，如 `page_title/core_table/main_nav`
- `governance_status`
  - `String(20)`
  - 枚举：`draft`, `active`, `governing`, `retired`
- `testability_score`
  - `Integer`
  - 0-100，用于页面级可测试性评分
- `key_element_count`
  - `Integer`
  - 关键元素数量
- `approved_element_count`
  - `Integer`
  - 审核通过元素数量
- `candidate_pending_count`
  - `Integer`
  - 当前待审候选数量

说明：

- `status` 继续保留给现有页面对象状态
- `governance_status` 专门描述治理成熟度，避免和现有状态语义混淆

#### `page_elements`
继续作为正式元素表。

新增字段：

- `business_type`
  - `String(40)`
- `business_domain`
  - `String(40)`
  - 如 `auth`, `dashboard`, `table`, `form`
- `aliases_json`
  - `JSON`
  - 人工维护别名列表
- `semantic_tags_json`
  - `JSON`
  - 扩展语义标签
- `locator_source`
  - `String(20)`
  - 枚举：`testid`, `qa`, `role_name`, `placeholder`, `id`, `name`, `css`, `xpath`, `manual`
- `match_strategy`
  - `String(20)`
  - 枚举：`exact`, `alias`, `derived`, `composite`
- `stability_level`
  - `String(20)`
  - 枚举：`high`, `medium`, `low`
- `review_status`
  - `String(20)`
  - 枚举：`approved`, `pending`, `rejected`
- `origin_candidate_key`
  - `String(120)`
  - 首次提升来源候选 key
- `route_scope`
  - `String(256)`
- `anchor_required`
  - `Boolean`
  - 是否要求页面锚点上下文
- `is_key_element`
  - `Boolean`
  - 是否关键元素
- `testid_value`
  - `String(120)`
  - 前端可测试标识值
- `qa_value`
  - `String(120)`
  - 兼容 `data-qa`
- `governance_note`
  - `Text`
  - 审核说明

索引建议：

- `page_object_id + review_status`
- `page_object_id + business_type`
- `page_object_id + stability_level`
- `page_object_id + locator_source`
- `page_object_id + testid_value`

约束建议：

- 对关键元素，如果 `is_key_element=true`，则要求 `testid_value` 或 `qa_value` 至少一个非空
- 对新建正式元素，`review_status` 默认 `approved` 仅限人工审核提升；非审核链路写入默认 `pending`

### 2. 新增候选分组表
#### `page_object_candidate_groups`
用途：

- 跨 session 聚合同一业务元素候选
- 承担审核入口的主实体
- 批量提升、拒绝、合并时以组为单位操作

字段：

- `id`
- `project_code`
- `client`
- `page_code`
- `group_key`
- `proposed_element_code`
- `proposed_element_name`
- `business_type_guess`
- `business_domain_guess`
- `quality_tier`
- `max_score`
- `avg_score`
- `session_count`
- `candidate_count`
- `recommended_action`
- `promotion_status`
  - 枚举：`pending`, `partially_promoted`, `promoted`, `rejected`
- `route_scope`
- `top_locator_source`
- `top_locator_type`
- `top_locator_value`
- `top_role`
- `risk_tags_json`
- `sample_texts_json`
- `matched_existing_element_code`
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `latest_session_id`
- `created_at`
- `updated_at`

唯一键：

- `project_code + client + page_code + group_key`

索引：

- `project_code + client + page_code + promotion_status`
- `project_code + client + page_code + quality_tier`
- `matched_existing_element_code`

### 3. 新增候选明细表
#### `page_object_candidate_elements`
用途：

- 存储录制产生的每个候选明细
- 记录其来自哪次录制、为什么高分/低分、是否可提升

字段：

- `id`
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
  - 枚举：`ingest`, `review`, `skip`
- `candidate_status`
  - 枚举：`pending`, `reviewed`, `promoted`, `rejected`, `merged`
- `ingest_block_reason`
- `proposed_element_code`
- `proposed_element_name`
- `business_type_guess`
- `probe_status`
- `probe_match_count`
- `probe_visible`
- `probe_interactable`
- `merged_to_element_code`
- `promoted_element_code`
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `created_at`
- `updated_at`

唯一键：

- `session_id + candidate_key`

索引：

- `project_code + client + page_code + candidate_status`
- `group_key`
- `session_id`
- `quality_score`
- `recommended_action`

### 4. 新增正式元素定位器扩展表
#### `page_element_locators`
V1 执行器仍读主表主定位器，但为后续治理和人工兜底保留多定位器结构。

字段：

- `id`
- `page_element_id`
- `locator_type`
- `locator_value`
- `role`
- `locator_source`
- `priority`
- `is_primary`
- `health_status`
- `verification_status`
  - `unknown`, `ok`, `not_found`, `ambiguous`
- `last_verified_at`
- `created_by`
- `created_at`
- `updated_at`

唯一键：

- `page_element_id + locator_type + locator_value + role`

用途：

- 候选提升后保留备选定位器
- 后续元素修复时不覆盖历史主定位器信息

### 5. 新增前端标识契约表
#### `page_element_test_contracts`
V1 可以独立建表，也可以先并入 `page_elements`。为了减少 V1 改动，建议先不单建表。

本版选择：**先不单建表**，将 `testid_value/qa_value/is_key_element` 放到 `page_elements` 即可。

### 6. 新增审核操作日志表
#### `page_object_governance_logs`
用途：

- 记录候选审核、拒绝、合并、提升
- 支持后续审计与回溯

字段：

- `id`
- `project_code`
- `client`
- `page_code`
- `entity_type`
  - `candidate_element`, `candidate_group`, `page_element`, `page_object`
- `entity_key`
- `action`
  - `promote`, `reject`, `merge`, `edit`, `approve`, `mark_pending`
- `before_payload`
- `after_payload`
- `operator`
- `created_at`

## Data Rules
### 1. `group_key` 生成规则
按以下优先级：

1. `data-testid`
2. `data-qa`
3. `role + accessible name`
4. `placeholder`
5. `id`
6. `name`
7. 稳定 hash

格式不要求人工可读，但必须稳定。

### 2. 正式 `element_code` 规则
固定为 snake_case，且对关键元素要求与 `data-testid/data-qa` 一致。

规则：

- 小写字母、数字、下划线
- 禁止页面名前缀
- 禁止 path、index、nth、locator 类型词
- 长度建议 3-80

### 3. 语义枚举
`business_type` 固定：

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

`business_domain` 固定建议：

- `auth`
- `navigation`
- `dashboard`
- `search`
- `table`
- `form`
- `detail`
- `common`

### 4. 稳定性规则
`stability_level` 计算口径：

- `high`
  - 主定位来源为 `testid/qa`
  - 已审核通过
  - probe 成功
- `medium`
  - 主定位来源为 `role_name/placeholder/id/name`
  - 已审核通过或待审核
- `low`
  - 主定位来源为 `css/xpath/text`
  - 或历史脏数据
  - 或 probe 不稳定

### 5. 正式元素参与映射资格
必须同时满足：

- `status=active`
- `review_status=approved`
- `stability_level in (high, medium)`，low 默认不参与
- `page_code` 匹配当前页面对象

## Frontend Flow
### 1. 页面结构
保留现有两层入口：

- 页面对象列表页 `PageObjectsPage`
- 元素列表页 `PageObjectElementsPage`
- 录制页 `PageObjectRecorderPage`

V1 的治理入口统一放在元素列表页，不在录制页做完整审核。

### 2. 页面对象列表页
现有页面对象列表页保留，但新增治理指标列：

- 正式元素数
- 待审候选组数
- 关键元素覆盖率
- 可测试性评分
- 治理状态

操作区保留：

- 查看元素
- 编辑页面
- 删除页面对象

不在这里直接做候选审核。

### 3. 元素列表页结构
元素列表页拆成 3 个主 tab：

- `正式元素`
- `候选元素`
- `录制历史`

默认进入：

- `正式元素`

如果从录制停止页跳转过来，带 query：

- `?tab=candidates&session_id=...`

#### `正式元素` Tab
表格列：

- 元素编码
- 元素名称
- 业务类型
- 定位来源
- 稳定等级
- 审核状态
- 关键元素
- 引用次数
- 更新时间

行操作：

- 查看详情
- 编辑语义
- 编辑别名
- 查看定位器
- 查看引用
- 标记待治理

详情抽屉展示：

- 主定位器
- 备选定位器
- 别名
- 语义标签
- route_scope
- 前端标识契约
- 审核说明
- 来源候选

#### `候选元素` Tab
主视图先显示“候选分组表”，不是直接扔平铺候选明细。

分组表列：

- 候选编码建议
- 候选名称建议
- 业务类型猜测
- 质量等级
- 候选数
- 录制会话数
- 推荐动作
- 已匹配正式元素
- 状态
- 最近更新时间

分组行操作：

- 查看候选
- 提升为正式元素
- 合并到已有正式元素
- 批量拒绝组内候选
- 编辑建议编码/名称/语义

点击“查看候选”后打开右侧详情面板，列出组内候选明细：

- locator_type
- locator_value
- role
- route
- step_hit_count
- score
- risk_tags
- probe 状态
- 来源 session

候选级操作：

- 单条拒绝
- 标记保留
- 替换为该候选作为主定位器
- 合并到正式元素

#### `录制历史` Tab
保留当前回放能力，增强关联展示：

- session 基本信息
- 回放按钮
- 本次录制候选数
- 本次录制生成的候选组
- 已提升数量
- 已拒绝数量

操作：

- 查看回放
- 跳转候选元素 tab 并过滤该 session
- 查看 stderr/脚本

### 4. 录制页交互
录制页职责收敛为：

- 创建会话
- 停止会话
- 看录制回放
- 跳转去治理

停止录制后结果卡片显示：

- 会话状态
- 候选数
- 候选组数
- 推荐可提升数
- 页面匹配状态
- “去元素列表审核”按钮

不在录制页直接提供“提升为正式元素”的完整入口，避免同一流程在两处维护。

### 5. 审核操作流
#### 提升新正式元素
1. 用户在候选分组点击“提升”
2. 弹出审核对话框
3. 用户确认：
   - `element_code`
   - `element_name`
   - `business_type`
   - `business_domain`
   - 是否关键元素
   - 主定位器
4. 系统校验：
   - 编码规则
   - 编码唯一
   - 关键元素 `testid/qa` 契约
   - route_scope 匹配
5. 成功后：
   - 创建正式元素
   - 候选状态改 `promoted`
   - 分组状态改 `promoted` 或 `partially_promoted`
   - 记录治理日志

#### 合并到已有正式元素
1. 用户在候选分组点击“合并”
2. 弹出正式元素选择器
3. 系统只列出当前页面同 `business_type` 或近似类型的正式元素
4. 合并后：
   - 候选状态改 `merged`
   - 候选 locator 可写入 `page_element_locators`
   - 分组记录 `matched_existing_element_code`

#### 拒绝候选
1. 支持候选级拒绝和分组级批量拒绝
2. 必填 `review_note`
3. 状态改为 `rejected`
4. 不删除记录，保留审计和后续分析

## APIs
### 新增接口
- `GET /api/page-objects/{page_code}/candidate-groups`
- `GET /api/page-objects/{page_code}/candidate-elements`
- `GET /api/page-objects/{page_code}/candidate-groups/{group_key}`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/promote`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/merge`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/reject`
- `POST /api/page-objects/{page_code}/candidate-elements/{candidate_key}/reject`
- `GET /api/page-objects/{page_code}/governance/summary`

### 现有接口语义调整
- `stop_recorder_session`
  - 默认写候选，不写正式元素
- `list_page_elements`
  - 默认只返回正式元素
- `get_recorder_session_playback`
  - 增加候选摘要字段
- `deduplicate_page_elements`
  - 只处理正式元素，不碰候选层

## Migration
### 1. 历史正式元素迁移
迁移脚本只做标记：

- 识别编码或定位器脏模式
- 写入：
  - `review_status=pending`
  - `stability_level=low`
  - `locator_source`
  - `governance_note`

不做：

- 自动重命名
- 自动改别名
- 自动更新测试点引用

### 2. 新老链路兼容
- 旧正式元素仍可供老用例执行
- 新测试点映射默认只用 `approved + high/medium`
- 老元素若被人工重新审核，可恢复进入新映射链路

## Test Plan
1. 新录制停止后产生候选组和候选明细，但不新增正式元素。
2. 候选分组列表能按页面、状态、质量等级、session 过滤。
3. 候选提升时若关键元素缺少 `testid/qa`，提升失败。
4. 候选提升成功后正式元素完整写入新增字段。
5. 候选合并到已有正式元素后生成 `page_element_locators` 备选定位器记录。
6. 元素列表页三个 tab 的数据边界互不混淆。
7. 录制历史 tab 可回放并跳转到候选 tab。
8. 历史脏数据迁移后状态正确，但旧引用不破坏。
9. 测试点映射只使用审核通过的正式元素。
10. `password_toggle`、`metric_label` 在前端审核时能选择正确语义类型。

## Assumptions
- V1 不单独建设“治理任务工作台”，审核入口先集中在元素列表页。
- V1 的审核交互采用现有前端页面风格，使用表格 + 右侧详情/对话框，不做全新工作流页面。
- `anchor_config_json` 先作为页面对象配置存储，V1 不做复杂可视化配置器。
- `page_element_locators` 先用于治理存储，执行器仍优先读 `page_elements` 主定位器。
- 文档目录约定为 `docs/page-object-governance/`。
