# 页面对象治理前端组件拆分与接口映射设计 V1.0

## 目标

把页面对象治理方案拆成前端组件层级，并明确每个组件依赖哪些接口、读写哪些字段、触发哪些交互。

---

## 1. 页面层级结构

### 1.1 页面对象列表页

- `PageObjectsPage`
  - `PageObjectsHeader`
  - `PageObjectsStats`
  - `PageObjectsFilters`
  - `PageObjectsTable`
  - `EditPageObjectModal`
  - `DeletePageObjectModal`

### 1.2 录制页

- `PageObjectRecorderPage`
  - `RecorderPageHeader`
  - `RecorderSessionPanel`
  - `RecorderHistoryTable`
  - `RecorderResultCard`
  - `RecorderPlaybackDrawer`
  - `RecorderLogDrawer`

### 1.3 元素列表页

- `PageObjectElementsPage`
  - `PageElementsHeader`
  - `GovernanceSummaryCards`
  - `ElementsTabs`
  - `FormalElementsTab`
    - `FormalElementsFilters`
    - `FormalElementsTable`
    - `FormalElementDetailDrawer`
    - `EditFormalElementModal`
  - `CandidateElementsTab`
    - `CandidateGroupsFilters`
    - `CandidateGroupsTable`
    - `CandidateGroupDetailPanel`
    - `PromoteCandidateModal`
    - `MergeCandidateModal`
    - `RejectCandidateModal`
  - `RecorderHistoryTab`
    - `RecorderHistoryFilters`
    - `RecorderHistoryTable`
    - `RecorderPlaybackDrawer`

---

## 2. 页面对象列表页组件与接口

### `PageObjectsPage`

职责：

- 加载页面对象列表
- 管理筛选条件
- 打开编辑/删除弹窗

依赖接口：

- `GET /api/page-objects`
- `PUT /api/page-objects/{page_code}`
- `DELETE /api/page-objects/{page_code}`

建议本地状态：

- `filters`
- `items`
- `loading`
- `selectedPageObject`
- `editModalOpen`
- `deleteModalOpen`

### `PageObjectsStats`

职责：

- 展示聚合指标卡

数据来源：

- 初期可由 `GET /api/page-objects` 结果本地聚合
- 后续可独立汇总接口

依赖字段：

- `approved_element_count`
- `candidate_pending_count`
- `testability_score`
- `governance_status`

### `PageObjectsTable`

职责：

- 展示页面对象列表
- 触发行操作

依赖字段：

- `page_code`
- `page_name`
- `page_url`
- `approved_element_count`
- `candidate_pending_count`
- `key_element_count`
- `element_count`
- `testability_score`
- `governance_status`
- `updated_at`

派生字段：

- `关键元素覆盖率 = key_element_count / approved_element_count`

---

## 3. 录制页组件与接口

### `PageObjectRecorderPage`

职责：

- 会话创建、轮询、停止
- 展示录制历史
- 展示停止后的候选摘要

依赖接口：

- `POST /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions/{session_id}`
- `POST /api/page-objects/recorder/sessions/{session_id}/heartbeat`
- `POST /api/page-objects/recorder/sessions/{session_id}/stop`
- `GET /api/page-objects/recorder/sessions/{session_id}/playback`
- `GET /api/page-objects/{page_code}/governance/summary`

建议本地状态：

- `activeSession`
- `sessionList`
- `stopResult`
- `playbackSessionId`
- `stderrSessionId`
- `pollingEnabled`

### `RecorderSessionPanel`

职责：

- 展示当前会话运行状态

依赖字段：

- `session_id`
- `status`
- `started_at`
- `heartbeat_at`
- `script_path`
- `error_message`

### `RecorderResultCard`

职责：

- 展示录制停止后的结果摘要
- 承接跳转到候选审核

依赖字段：

- `candidate_count`
- `candidate_group_count`
- `promotable_count`
- `page_match_status`
- `recorded_step_count`
- `session_id`

跳转行为：

- `to=/assets/page-objects/{pageCode}/elements?project={project}&tab=candidates&session_id={sessionId}`

### `RecorderHistoryTable`

职责：

- 展示录制历史记录

依赖字段：

- `session_id`
- `status`
- `started_at`
- `stopped_at`
- `candidate_count`
- `candidate_group_count`
- `promoted_count`
- `rejected_count`
- `recorded_step_count`

---

## 4. 元素列表页公共组件与接口

### `PageObjectElementsPage`

职责：

- 统一承载正式元素、候选元素、录制历史
- 同步 URL query 到当前 tab 和筛选条件

依赖接口：

- `GET /api/page-objects/{page_code}`
- `GET /api/page-objects/{page_code}/governance/summary`

建议 URL query：

- `project`
- `tab`
- `session_id`
- `candidate_status`
- `quality_tier`

建议本地状态：

- `activeTab`
- `pageObject`
- `summary`
- `queryFilters`

### `GovernanceSummaryCards`

职责：

- 展示页面级治理摘要

依赖接口：

- `GET /api/page-objects/{page_code}/governance/summary`

依赖字段：

- `formal_element_count`
- `approved_element_count`
- `pending_candidate_group_count`
- `key_element_count`
- `key_element_coverage`
- `testability_score`

---

## 5. 正式元素 Tab 组件与接口

### `FormalElementsTab`

职责：

- 管理正式元素列表、筛选、详情、编辑

依赖接口：

- `GET /api/page-objects/{page_code}/elements`
- `GET /api/page-objects/{page_code}/elements/{element_code}`
- `PUT /api/page-objects/{page_code}/elements/{element_code}`
- `GET /api/page-objects/{page_code}/elements/{element_code}/refs`

### `FormalElementsTable`

依赖字段：

- `element_code`
- `element_name`
- `business_type`
- `business_domain`
- `locator_source`
- `stability_level`
- `review_status`
- `is_key_element`
- `reference_count`
- `updated_at`

### `FormalElementDetailDrawer`

依赖接口：

- `GET /api/page-objects/{page_code}/elements/{element_code}`
- 可选补充：在详情返回里内嵌扩展定位器与来源候选

依赖字段：

- 基本：`element_code`, `element_name`, `business_type`, `business_domain`
- 主定位：`locator_type`, `locator_value`, `locator_source`, `role`, `route_scope`
- 语义：`aliases_json`, `semantic_tags_json`, `is_key_element`, `testid_value`, `qa_value`
- 治理：`review_status`, `stability_level`, `origin_candidate_key`, `governance_note`
- 扩展：`locators[]`

### `EditFormalElementModal`

提交接口：

- `PUT /api/page-objects/{page_code}/elements/{element_code}`

提交字段：

- `element_name`
- `business_type`
- `business_domain`
- `aliases_json`
- `semantic_tags_json`
- `route_scope`
- `is_key_element`
- `testid_value`
- `qa_value`
- `governance_note`
- 必要时更新主定位器

---

## 6. 候选元素 Tab 组件与接口

### `CandidateElementsTab`

职责：

- 按候选分组治理
- 打开提升、合并、拒绝弹窗

依赖接口：

- `GET /api/page-objects/{page_code}/candidate-groups`
- `GET /api/page-objects/{page_code}/candidate-groups/{group_key}`
- `GET /api/page-objects/{page_code}/candidate-elements`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/promote`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/merge`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/reject`
- `POST /api/page-objects/{page_code}/candidate-elements/{candidate_key}/reject`
- `GET /api/page-objects/{page_code}/elements`

建议本地状态：

- `groups`
- `selectedGroupKey`
- `selectedGroupDetail`
- `selectedCandidateKeys`
- `promoteModalOpen`
- `mergeModalOpen`
- `rejectModalOpen`

### `CandidateGroupsTable`

依赖字段：

- `group_key`
- `proposed_element_code`
- `proposed_element_name`
- `business_type_guess`
- `quality_tier`
- `candidate_count`
- `session_count`
- `recommended_action`
- `matched_existing_element_code`
- `promotion_status`
- `updated_at`

### `CandidateGroupDetailPanel`

依赖接口：

- `GET /api/page-objects/{page_code}/candidate-groups/{group_key}`

依赖字段：

- 分组：`group_key`, `proposed_element_code`, `proposed_element_name`
- 语义：`business_type_guess`, `business_domain_guess`
- 定位：`top_locator_source`, `top_locator_type`, `top_locator_value`, `top_role`, `route_scope`
- 风险：`risk_tags_json`, `recommended_action`, `matched_existing_element_code`
- 明细：`candidates[]`

明细字段：

- `candidate_key`
- `raw_locator_type`
- `raw_locator_value`
- `raw_role`
- `route`
- `step_hit_count`
- `quality_score`
- `quality_tier`
- `probe_status`
- `session_id`
- `candidate_status`

### `PromoteCandidateModal`

依赖接口：

- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/promote`

建议请求体：

- `element_code`
- `element_name`
- `business_type`
- `business_domain`
- `is_key_element`
- `testid_value`
- `qa_value`
- `route_scope`
- `primary_candidate_key` 或 `primary_locator`
- `review_note`

成功后联动刷新：

- 候选分组列表
- 分组详情
- 正式元素列表
- 治理摘要

### `MergeCandidateModal`

依赖接口：

- `GET /api/page-objects/{page_code}/elements`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/merge`

建议请求体：

- `target_element_code`
- `merge_candidate_keys`
- `review_note`
- `keep_primary_locator`

### `RejectCandidateModal`

支持两种模式：

- 分组级拒绝
- 候选级拒绝

依赖接口：

- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/reject`
- `POST /api/page-objects/{page_code}/candidate-elements/{candidate_key}/reject`

建议请求体：

- `review_note`
- `reason_code`

---

## 7. 录制历史 Tab 组件与接口

### `RecorderHistoryTab`

职责：

- 展示当前页面录制历史
- 查看回放
- 跳转去候选审核

依赖接口：

- `GET /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions/{session_id}/playback`

### `RecorderPlaybackDrawer`

依赖字段：

- `session_id`
- `url`
- `recorded_steps`
- `stderr_summary`
- `candidate_summary`

---

## 8. 建议的前端数据类型

### `GovernanceSummary`

```ts
interface GovernanceSummary {
  formal_element_count: number;
  approved_element_count: number;
  pending_candidate_group_count: number;
  key_element_count: number;
  key_element_coverage: number;
  testability_score: number;
  governance_status: string;
}
```

### `CandidateGroup`

```ts
interface CandidateGroup {
  group_key: string;
  proposed_element_code: string;
  proposed_element_name: string;
  business_type_guess: string;
  business_domain_guess?: string;
  quality_tier: string;
  max_score?: number;
  avg_score?: number;
  session_count: number;
  candidate_count: number;
  recommended_action: string;
  promotion_status: string;
  route_scope?: string;
  top_locator_source?: string;
  top_locator_type?: string;
  top_locator_value?: string;
  top_role?: string;
  risk_tags_json?: string[];
  matched_existing_element_code?: string;
  updated_at?: string;
}
```

### `CandidateElement`

```ts
interface CandidateElement {
  candidate_key: string;
  group_key: string;
  session_id: string;
  raw_locator_type: string;
  raw_locator_value: string;
  raw_role?: string;
  raw_text?: string;
  route?: string;
  step_hit_count?: number;
  quality_score?: number;
  quality_tier?: string;
  recommended_action?: string;
  candidate_status: string;
  probe_status?: string;
}
```

---

## 9. 推荐实现顺序

1. 先搭页面壳子和 Tab 结构
2. 再补正式元素列表与治理摘要
3. 然后补候选分组表与详情面板
4. 再做提升/合并/拒绝弹窗
5. 最后补录制历史和回放抽屉

这样实现风险最低，也最容易阶段验收。
