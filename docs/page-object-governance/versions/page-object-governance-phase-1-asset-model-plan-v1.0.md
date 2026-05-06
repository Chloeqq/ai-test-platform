# 阶段 1：资产模型纠偏开发计划 V1.0

## 阶段目标

建立页面对象治理所需的数据模型边界，确保系统能清晰区分：

- 页面对象
- 正式元素
- 候选分组
- 候选明细
- 扩展定位器
- 治理日志

本阶段不做完整前端治理页，也不接测试点映射链路。

---

## 一、开发范围

### 1. 后端模型

涉及文件：

- `apps/web-ui-service/app/models/page_object.py`
- `apps/web-ui-service/app/models/__init__.py`

要做：

- 扩展 `PageObject`
- 扩展 `PageElement`
- 新增 `PageObjectCandidateGroup`
- 新增 `PageObjectCandidateElement`
- 新增 `PageElementLocator`
- 新增 `PageObjectGovernanceLog`

### 2. 数据库迁移

涉及目录：

- `apps/web-ui-service/migrations/versions/`

要做：

- 新增 Alembic migration
- 添加字段
- 创建新表
- 创建索引和唯一键
- 兼容已有环境重复执行风险

### 3. 服务层最小改造

涉及文件：

- `apps/web-ui-service/app/services/page_object_service.py`

要做：

- 正式元素序列化补齐新增字段
- 页面对象序列化补齐新增字段
- 新增治理摘要的基础计算能力
- 不在本阶段实现完整候选提升流程

### 4. 测试

涉及文件：

- `apps/web-ui-service/tests/integration/test_page_objects_api.py`
- 可选新增单测文件

要做：

- 验证模型字段可写入
- 验证 migration 后表存在
- 验证页面对象接口返回新增治理字段
- 验证正式元素接口返回新增治理字段

---

## 二、page_objects 扩展字段

新增字段：

- `route_pattern`
- `anchor_config_json`
- `governance_status`
- `testability_score`
- `key_element_count`
- `approved_element_count`
- `candidate_pending_count`

默认值建议：

- `route_pattern`: `""`
- `anchor_config_json`: `{}`
- `governance_status`: `"draft"`
- `testability_score`: `0`
- `key_element_count`: `0`
- `approved_element_count`: `0`
- `candidate_pending_count`: `0`

索引建议：

- `governance_status`

纠偏意义：

- `status` 保留原有页面生命周期
- `governance_status` 专门表达治理成熟度

---

## 三、page_elements 扩展字段

新增字段：

- `business_type`
- `business_domain`
- `aliases_json`
- `semantic_tags_json`
- `locator_source`
- `match_strategy`
- `stability_level`
- `review_status`
- `origin_candidate_key`
- `route_scope`
- `anchor_required`
- `is_key_element`
- `testid_value`
- `qa_value`
- `governance_note`

默认值建议：

- `business_type`: `""`
- `business_domain`: `""`
- `aliases_json`: `[]`
- `semantic_tags_json`: `[]`
- `locator_source`: `""`
- `match_strategy`: `"exact"`
- `stability_level`: `"low"`
- `review_status`: `"pending"`
- `origin_candidate_key`: `""`
- `route_scope`: `""`
- `anchor_required`: `false`
- `is_key_element`: `false`
- `testid_value`: `""`
- `qa_value`: `""`
- `governance_note`: `""`

索引建议：

- `page_object_id + review_status`
- `page_object_id + business_type`
- `page_object_id + stability_level`
- `page_object_id + locator_source`
- `page_object_id + testid_value`

纠偏意义：

- 让正式元素具备审核状态、稳定等级和业务语义
- 后续测试点映射可以过滤不合格元素

---

## 四、新增表：page_object_candidate_groups

用途：

- 跨 session 聚合同一业务元素候选
- 作为候选审核入口主实体

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

默认值：

- `promotion_status`: `"pending"`
- `candidate_count`: `0`
- `session_count`: `0`

---

## 五、新增表：page_object_candidate_elements

用途：

- 存储每一次录制产生的候选明细

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
- `candidate_status`
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

默认值：

- `candidate_status`: `"pending"`
- `recommended_action`: `"review"`

---

## 六、新增表：page_element_locators

用途：

- 保存正式元素的多定位器结构
- V1 执行器仍优先读 `page_elements` 主定位器

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
- `last_verified_at`
- `created_by`
- `created_at`
- `updated_at`

唯一键：

- `page_element_id + locator_type + locator_value + role`

默认值：

- `priority`: `100`
- `is_primary`: `false`
- `verification_status`: `"unknown"`

纠偏意义：

- 后续合并候选时不覆盖正式元素主定位器

---

## 七、新增表：page_object_governance_logs

用途：

- 记录候选审核、拒绝、合并、提升等治理操作

字段：

- `id`
- `project_code`
- `client`
- `page_code`
- `entity_type`
- `entity_key`
- `action`
- `before_payload`
- `after_payload`
- `operator`
- `created_at`

索引：

- `project_code + client + page_code`
- `entity_type + entity_key`
- `action`

---

## 八、历史正式元素处理

本阶段只做标记，不做重命名。

推荐规则：

- 如果 `element_code` 命中脏命名模式，则：
  - `review_status = pending`
  - `stability_level = low`
  - `governance_note` 追加说明

脏命名模式：

- 包含 `css`
- 包含 `xpath`
- 包含 `path`
- 包含 `nth`
- 包含 `index`
- 包含 `text`
- 包含明显序号噪音

不做：

- 自动重命名
- 自动更新测试点引用
- 自动修改主定位器

---

## 九、阶段 1 接口影响

本阶段最小接口变化：

### `GET /api/page-objects`

返回新增字段：

- `route_pattern`
- `governance_status`
- `testability_score`
- `key_element_count`
- `approved_element_count`
- `candidate_pending_count`

### `GET /api/page-objects/{page_code}`

同上。

### `GET /api/page-objects/{page_code}/elements`

返回新增字段：

- `business_type`
- `business_domain`
- `aliases_json`
- `semantic_tags_json`
- `locator_source`
- `match_strategy`
- `stability_level`
- `review_status`
- `origin_candidate_key`
- `route_scope`
- `anchor_required`
- `is_key_element`
- `testid_value`
- `qa_value`
- `governance_note`

### 新增基础摘要接口

可在本阶段实现：

- `GET /api/page-objects/{page_code}/governance/summary`

返回：

- `formal_element_count`
- `approved_element_count`
- `pending_candidate_group_count`
- `key_element_count`
- `key_element_coverage`
- `testability_score`
- `governance_status`

---

## 十、不在阶段 1 做的事

为了避免阶段失控，本阶段明确不做：

- 录制停止写候选
- 候选分组聚合算法
- 候选提升为正式元素
- 候选合并
- 候选拒绝
- 前端三 Tab 治理页
- 测试点映射规则改造
- 执行器改造

这些进入后续阶段。

---

## 十一、阶段 1 验收清单

### 数据库验收

- `page_objects` 新字段存在
- `page_elements` 新字段存在
- `page_object_candidate_groups` 表存在
- `page_object_candidate_elements` 表存在
- `page_element_locators` 表存在
- `page_object_governance_logs` 表存在
- 关键唯一键与索引存在

### 后端模型验收

- ORM 模型可正常创建表
- 测试环境 `Base.metadata.create_all()` 不报错

### 接口验收

- 页面对象接口返回治理字段
- 页面元素接口返回治理字段
- 治理摘要接口可返回基础统计

### 纠偏验收

- 历史脏元素不会被自动重命名
- 新字段能标记其 `pending + low`

---

## 十二、风险点

### 1. 兼容已有数据库

风险：

- 本地和部署环境可能已有不同 schema 状态。

策略：

- migration 使用防御式添加字段和索引

### 2. JSON 字段兼容

风险：

- SQLite、PostgreSQL 对 JSON 行为不完全一致。

策略：

- ORM 使用 JSON 类型
- 默认值由应用层保证

### 3. 历史数据污染

风险：

- 历史正式元素很多已经是脏命名。

策略：

- 只标记，不修改引用

---

## 十三、完成后进入阶段 2 的条件

阶段 1 完成后，必须满足：

- 候选表已存在
- 正式元素有审核和稳定性字段
- 页面对象有治理摘要字段
- 基础 summary 接口可用

满足后才能进入：

- 阶段 2：录制链路纠偏
