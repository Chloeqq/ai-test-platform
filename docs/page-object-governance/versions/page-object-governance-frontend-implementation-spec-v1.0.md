# 页面对象治理前端实现规格表 V1.0

## 文档目标

本文将页面对象治理高保真交互稿继续下沉为前端实现规格表，按组件逐项说明：

- 组件职责
- Props
- 本地状态
- 事件
- 接口字段依赖
- 渲染规则

适用范围：

- `PageObjectsPage`
- `PageObjectRecorderPage`
- `PageObjectElementsPage`

---

## 一、统一类型约定

### 1. 页面对象 `PageObjectViewModel`

```ts
interface PageObjectViewModel {
  id: number;
  project_code: string;
  client: string;
  page_code: string;
  page_name: string;
  page_url: string;
  route_pattern?: string;
  status: string;
  governance_status?: string;
  testability_score?: number;
  element_count?: number;
  key_element_count?: number;
  approved_element_count?: number;
  candidate_pending_count?: number;
  updated_at?: string;
  last_recorded_at?: string;
}
```

### 2. 正式元素 `FormalElementViewModel`

```ts
interface FormalElementViewModel {
  id: number;
  page_object_id: number;
  element_code: string;
  element_name: string;
  business_type?: string;
  business_domain?: string;
  locator_type: string;
  locator_value: string;
  locator_source?: string;
  role?: string;
  route_scope?: string;
  stability_level?: string;
  review_status?: string;
  is_key_element?: boolean;
  testid_value?: string;
  qa_value?: string;
  aliases_json?: string[];
  semantic_tags_json?: string[];
  origin_candidate_key?: string;
  governance_note?: string;
  reference_count?: number;
  updated_at?: string;
  locators?: ElementLocatorViewModel[];
}
```

### 3. 候选分组 `CandidateGroupViewModel`

```ts
interface CandidateGroupViewModel {
  group_key: string;
  proposed_element_code: string;
  proposed_element_name: string;
  business_type_guess?: string;
  business_domain_guess?: string;
  quality_tier?: string;
  max_score?: number;
  avg_score?: number;
  session_count?: number;
  candidate_count?: number;
  recommended_action?: string;
  promotion_status?: string;
  route_scope?: string;
  top_locator_source?: string;
  top_locator_type?: string;
  top_locator_value?: string;
  top_role?: string;
  risk_tags_json?: string[];
  sample_texts_json?: string[];
  matched_existing_element_code?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_note?: string;
  latest_session_id?: string;
  updated_at?: string;
}
```

### 4. 候选明细 `CandidateElementViewModel`

```ts
interface CandidateElementViewModel {
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
  risk_tags_json?: string[];
  recommended_action?: string;
  candidate_status?: string;
  proposed_element_code?: string;
  proposed_element_name?: string;
  business_type_guess?: string;
  probe_status?: string;
  probe_match_count?: number;
  probe_visible?: boolean;
  probe_interactable?: boolean;
}
```

### 5. 扩展定位器 `ElementLocatorViewModel`

```ts
interface ElementLocatorViewModel {
  id: number;
  locator_type: string;
  locator_value: string;
  role?: string;
  locator_source?: string;
  priority?: number;
  is_primary?: boolean;
  health_status?: string;
  verification_status?: string;
  last_verified_at?: string;
}
```

### 6. 治理摘要 `GovernanceSummaryViewModel`

```ts
interface GovernanceSummaryViewModel {
  formal_element_count: number;
  approved_element_count: number;
  pending_candidate_group_count: number;
  key_element_count: number;
  key_element_coverage: number;
  testability_score: number;
  governance_status: string;
}
```

### 7. 录制会话 `RecorderSessionViewModel`

```ts
interface RecorderSessionViewModel {
  session_id: string;
  status: string;
  page_code: string;
  page_name?: string;
  url?: string;
  script_path?: string;
  error_message?: string;
  started_at?: string;
  heartbeat_at?: string;
  stopped_at?: string;
  recorded_step_count?: number;
  candidate_count?: number;
  candidate_group_count?: number;
  promoted_count?: number;
  rejected_count?: number;
}
```

---

## 二、页面对象列表页

页面：`PageObjectsPage`

### 1. `PageObjectsPage`

职责：

- 管理列表页整体数据流
- 维护筛选条件
- 承接编辑/删除弹窗

#### Props

- 无

#### 本地状态

```ts
type PageObjectsFiltersState = {
  project: string;
  client: string;
  module: string;
  status: string;
  governance_status: string;
  keyword: string;
};
```

```ts
const [filters, setFilters] = useState<PageObjectsFiltersState>(...);
const [items, setItems] = useState<PageObjectViewModel[]>([]);
const [loading, setLoading] = useState(false);
const [errorText, setErrorText] = useState("");
const [selectedPageObject, setSelectedPageObject] = useState<PageObjectViewModel | null>(null);
const [editOpen, setEditOpen] = useState(false);
const [deleteOpen, setDeleteOpen] = useState(false);
```

#### 事件

- `handleQuery()`
- `handleReset()`
- `handleOpenEdit(item)`
- `handleOpenDelete(item)`
- `handleConfirmDelete()`
- `handleConfirmEdit(payload)`
- `handleGoElements(item)`
- `handleGoRecorder(item)`

#### 接口依赖

- `GET /api/page-objects`
- `PUT /api/page-objects/{page_code}`
- `DELETE /api/page-objects/{page_code}`

#### 依赖字段

- `page_code`
- `page_name`
- `page_url`
- `route_pattern`
- `approved_element_count`
- `candidate_pending_count`
- `key_element_count`
- `testability_score`
- `governance_status`
- `updated_at`

### 2. `PageObjectsHeader`

职责：

- 展示标题、副标题、主按钮

#### Props

```ts
interface PageObjectsHeaderProps {
  onCreate: () => void;
}
```

#### 事件

- `onCreate`

### 3. `PageObjectsStats`

职责：

- 展示列表级摘要卡

#### Props

```ts
interface PageObjectsStatsProps {
  items: PageObjectViewModel[];
}
```

#### 派生值

- 页面总数
- 已治理页面数
- 待审候选组总数
- 平均可测试性评分

### 4. `PageObjectsFilters`

职责：

- 管理筛选输入

#### Props

```ts
interface PageObjectsFiltersProps {
  value: PageObjectsFiltersState;
  onChange: (next: PageObjectsFiltersState) => void;
  onQuery: () => void;
  onReset: () => void;
  loading?: boolean;
}
```

#### 事件

- `onChange`
- `onQuery`
- `onReset`

### 5. `PageObjectsTable`

职责：

- 渲染页面对象表格

#### Props

```ts
interface PageObjectsTableProps {
  items: PageObjectViewModel[];
  loading?: boolean;
  onViewElements: (item: PageObjectViewModel) => void;
  onStartRecorder: (item: PageObjectViewModel) => void;
  onEdit: (item: PageObjectViewModel) => void;
  onDelete: (item: PageObjectViewModel) => void;
}
```

#### 事件

- `onViewElements`
- `onStartRecorder`
- `onEdit`
- `onDelete`

#### 渲染规则

- `关键元素覆盖率 = key_element_count / approved_element_count`
- `governance_status` 转中文标签
- `candidate_pending_count > 0` 时橙色强调

### 6. `EditPageObjectModal`

#### Props

```ts
interface EditPageObjectModalProps {
  open: boolean;
  item: PageObjectViewModel | null;
  onCancel: () => void;
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
}
```

#### 提交字段

- `page_name`
- `page_url`
- `route_pattern`
- `description`
- `status`
- `governance_status`

### 7. `DeletePageObjectModal`

#### Props

```ts
interface DeletePageObjectModalProps {
  open: boolean;
  item: PageObjectViewModel | null;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}
```

---

## 三、页面对象录制页

页面：`PageObjectRecorderPage`

### 1. `PageObjectRecorderPage`

职责：

- 管理当前页面录制流程
- 查询会话历史
- 展示停止结果

#### Props

- 无

#### 本地状态

```ts
const [pageObject, setPageObject] = useState<PageObjectViewModel | null>(null);
const [summary, setSummary] = useState<GovernanceSummaryViewModel | null>(null);
const [activeSession, setActiveSession] = useState<RecorderSessionViewModel | null>(null);
const [sessionList, setSessionList] = useState<RecorderSessionViewModel[]>([]);
const [stopResult, setStopResult] = useState<Record<string, unknown> | null>(null);
const [playbackSessionId, setPlaybackSessionId] = useState<string>("");
const [logSessionId, setLogSessionId] = useState<string>("");
const [loading, setLoading] = useState(false);
const [pollingEnabled, setPollingEnabled] = useState(true);
```

#### 事件

- `handleStartRecorder()`
- `handleStopRecorder()`
- `handleRefresh()`
- `handleOpenPlayback(sessionId)`
- `handleOpenLog(sessionId)`
- `handleGoCandidateReview(sessionId)`

#### 接口依赖

- `GET /api/page-objects/{page_code}`
- `GET /api/page-objects/{page_code}/governance/summary`
- `POST /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions/{session_id}`
- `POST /api/page-objects/recorder/sessions/{session_id}/stop`
- `GET /api/page-objects/recorder/sessions/{session_id}/playback`

### 2. `RecorderPageHeader`

#### Props

```ts
interface RecorderPageHeaderProps {
  pageObject: PageObjectViewModel | null;
  summary: GovernanceSummaryViewModel | null;
  activeSession: RecorderSessionViewModel | null;
  onBack: () => void;
  onRefresh: () => void;
  onStart: () => void;
  onStop: () => void;
}
```

#### 渲染规则

- 若 `activeSession.status === "active"`，主按钮显示 `停止录制`
- 否则主按钮显示 `开始录制`

### 3. `RecorderSessionPanel`

#### Props

```ts
interface RecorderSessionPanelProps {
  session: RecorderSessionViewModel | null;
  onStop: () => void;
}
```

#### 依赖字段

- `session_id`
- `status`
- `started_at`
- `heartbeat_at`
- `script_path`
- `error_message`

### 4. `RecorderHistoryTable`

#### Props

```ts
interface RecorderHistoryTableProps {
  items: RecorderSessionViewModel[];
  onPlayback: (sessionId: string) => void;
  onReview: (sessionId: string) => void;
  onLog: (sessionId: string) => void;
}
```

#### 依赖字段

- `session_id`
- `status`
- `started_at`
- `stopped_at`
- `candidate_count`
- `candidate_group_count`
- `promoted_count`
- `rejected_count`
- `recorded_step_count`

### 5. `RecorderResultCard`

#### Props

```ts
interface RecorderResultCardProps {
  result: {
    session_id?: string;
    candidate_count?: number;
    candidate_group_count?: number;
    promotable_count?: number;
    page_match_status?: string;
    recorded_step_count?: number;
    status?: string;
    error_message?: string;
  } | null;
  onReview: (sessionId: string) => void;
  onPlayback: (sessionId: string) => void;
  onRestart: () => void;
}
```

#### 事件

- `onReview`
- `onPlayback`
- `onRestart`

#### 渲染规则

- `status === "failed"` 时隐藏 `去元素列表审核`
- `status === "stopped"` 时突出显示 `去元素列表审核`

### 6. `RecorderPlaybackDrawer`

#### Props

```ts
interface RecorderPlaybackDrawerProps {
  open: boolean;
  sessionId: string;
  onClose: () => void;
}
```

#### 接口依赖

- `GET /api/page-objects/recorder/sessions/{session_id}/playback`

#### 依赖字段

- `url`
- `recorded_steps`
- `stderr_summary`
- `candidate_summary`

---

## 四、元素列表页

页面：`PageObjectElementsPage`

### 1. `PageObjectElementsPage`

职责：

- 管理三 Tab 结构
- 同步 query 参数
- 驱动页面级摘要与子组件刷新

#### Props

- 无

#### 本地状态

```ts
type ElementsPageTab = "formal" | "candidates" | "recorder-history";
```

```ts
const [pageObject, setPageObject] = useState<PageObjectViewModel | null>(null);
const [summary, setSummary] = useState<GovernanceSummaryViewModel | null>(null);
const [activeTab, setActiveTab] = useState<ElementsPageTab>("formal");
const [sessionIdFilter, setSessionIdFilter] = useState("");
const [loading, setLoading] = useState(false);
```

#### 事件

- `handleChangeTab(tab)`
- `handleRefreshAll()`
- `handleGoRecorder()`
- `handleApplySessionFilter(sessionId)`

#### 接口依赖

- `GET /api/page-objects/{page_code}`
- `GET /api/page-objects/{page_code}/governance/summary`

### 2. `PageElementsHeader`

#### Props

```ts
interface PageElementsHeaderProps {
  pageObject: PageObjectViewModel | null;
  onBack: () => void;
  onRefresh: () => void;
  onRecorder: () => void;
}
```

### 3. `GovernanceSummaryCards`

#### Props

```ts
interface GovernanceSummaryCardsProps {
  summary: GovernanceSummaryViewModel | null;
}
```

#### 依赖字段

- `formal_element_count`
- `approved_element_count`
- `pending_candidate_group_count`
- `key_element_count`
- `key_element_coverage`
- `testability_score`

### 4. `ElementsTabs`

#### Props

```ts
interface ElementsTabsProps {
  value: ElementsPageTab;
  pendingCandidateGroupCount?: number;
  onChange: (tab: ElementsPageTab) => void;
}
```

---

## 五、正式元素 Tab 规格

### 1. `FormalElementsTab`

职责：

- 加载正式元素列表
- 管理筛选、详情、编辑

#### Props

```ts
interface FormalElementsTabProps {
  projectCode: string;
  client: string;
  pageCode: string;
  onAfterMutation?: () => Promise<void> | void;
}
```

#### 本地状态

```ts
type FormalElementsFiltersState = {
  keyword: string;
  business_type: string;
  review_status: string;
  stability_level: string;
  locator_source: string;
  is_key_element: string;
};
```

```ts
const [filters, setFilters] = useState<FormalElementsFiltersState>(...);
const [items, setItems] = useState<FormalElementViewModel[]>([]);
const [selectedItem, setSelectedItem] = useState<FormalElementViewModel | null>(null);
const [detailOpen, setDetailOpen] = useState(false);
const [editOpen, setEditOpen] = useState(false);
```

#### 接口依赖

- `GET /api/page-objects/{page_code}/elements`
- `GET /api/page-objects/{page_code}/elements/{element_code}`
- `PUT /api/page-objects/{page_code}/elements/{element_code}`
- `GET /api/page-objects/{page_code}/elements/{element_code}/refs`

### 2. `FormalElementsFilters`

#### Props

```ts
interface FormalElementsFiltersProps {
  value: FormalElementsFiltersState;
  onChange: (next: FormalElementsFiltersState) => void;
  onQuery: () => void;
  onReset: () => void;
}
```

### 3. `FormalElementsTable`

#### Props

```ts
interface FormalElementsTableProps {
  items: FormalElementViewModel[];
  loading?: boolean;
  onDetail: (item: FormalElementViewModel) => void;
  onEdit: (item: FormalElementViewModel) => void;
  onViewLocators: (item: FormalElementViewModel) => void;
  onViewRefs: (item: FormalElementViewModel) => void;
  onMarkPending: (item: FormalElementViewModel) => void;
}
```

#### 依赖字段

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

### 4. `FormalElementDetailDrawer`

#### Props

```ts
interface FormalElementDetailDrawerProps {
  open: boolean;
  pageCode: string;
  projectCode: string;
  client: string;
  elementCode: string;
  onClose: () => void;
  onEdit: (item: FormalElementViewModel) => void;
}
```

#### 本地状态

```ts
const [detail, setDetail] = useState<FormalElementViewModel | null>(null);
const [loading, setLoading] = useState(false);
```

#### 接口依赖

- `GET /api/page-objects/{page_code}/elements/{element_code}`

### 5. `EditFormalElementModal`

#### Props

```ts
interface EditFormalElementModalProps {
  open: boolean;
  item: FormalElementViewModel | null;
  onCancel: () => void;
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
}
```

#### 提交字段

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

#### 本地校验

- `is_key_element = true` 时，`testid_value` 或 `qa_value` 至少一个非空

---

## 六、候选元素 Tab 规格

### 1. `CandidateElementsTab`

职责：

- 渲染候选分组主界面
- 驱动分组详情、提升、合并、拒绝

#### Props

```ts
interface CandidateElementsTabProps {
  projectCode: string;
  client: string;
  pageCode: string;
  initialSessionId?: string;
  onAfterMutation?: () => Promise<void> | void;
}
```

#### 本地状态

```ts
type CandidateFiltersState = {
  keyword: string;
  promotion_status: string;
  quality_tier: string;
  recommended_action: string;
  business_type_guess: string;
  session_id: string;
  only_unmatched: boolean;
};
```

```ts
const [filters, setFilters] = useState<CandidateFiltersState>(...);
const [groups, setGroups] = useState<CandidateGroupViewModel[]>([]);
const [selectedGroupKey, setSelectedGroupKey] = useState("");
const [selectedGroupDetail, setSelectedGroupDetail] = useState<{
  group: CandidateGroupViewModel;
  candidates: CandidateElementViewModel[];
} | null>(null);
const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
const [promoteOpen, setPromoteOpen] = useState(false);
const [mergeOpen, setMergeOpen] = useState(false);
const [rejectOpen, setRejectOpen] = useState(false);
const [rejectMode, setRejectMode] = useState<"group" | "candidate">("group");
const [activeCandidateKey, setActiveCandidateKey] = useState("");
```

#### 接口依赖

- `GET /api/page-objects/{page_code}/candidate-groups`
- `GET /api/page-objects/{page_code}/candidate-groups/{group_key}`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/promote`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/merge`
- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/reject`
- `POST /api/page-objects/{page_code}/candidate-elements/{candidate_key}/reject`
- `GET /api/page-objects/{page_code}/elements`

### 2. `CandidateGroupsFilters`

#### Props

```ts
interface CandidateGroupsFiltersProps {
  value: CandidateFiltersState;
  onChange: (next: CandidateFiltersState) => void;
  onQuery: () => void;
  onReset: () => void;
}
```

### 3. `CandidateGroupsTable`

#### Props

```ts
interface CandidateGroupsTableProps {
  items: CandidateGroupViewModel[];
  selectedGroupKey?: string;
  selectedKeys: string[];
  loading?: boolean;
  onSelectGroup: (groupKey: string) => void;
  onSelectKeys: (keys: string[]) => void;
  onPromote: (item: CandidateGroupViewModel) => void;
  onMerge: (item: CandidateGroupViewModel) => void;
  onReject: (item: CandidateGroupViewModel) => void;
}
```

#### 依赖字段

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

### 4. `CandidateGroupDetailPanel`

#### Props

```ts
interface CandidateGroupDetailPanelProps {
  loading?: boolean;
  detail: {
    group: CandidateGroupViewModel;
    candidates: CandidateElementViewModel[];
  } | null;
  onPromote: () => void;
  onMerge: () => void;
  onRejectGroup: () => void;
  onRejectCandidate: (candidateKey: string) => void;
}
```

#### 依赖字段

- `group.group_key`
- `group.proposed_element_code`
- `group.proposed_element_name`
- `group.business_type_guess`
- `group.business_domain_guess`
- `group.quality_tier`
- `group.recommended_action`
- `group.promotion_status`
- `group.top_locator_source`
- `group.top_locator_type`
- `group.top_locator_value`
- `group.top_role`
- `group.route_scope`
- `group.risk_tags_json`
- `group.matched_existing_element_code`
- `candidates[]`

### 5. `CandidateDetailTable`

#### Props

```ts
interface CandidateDetailTableProps {
  items: CandidateElementViewModel[];
  onReject: (candidateKey: string) => void;
}
```

#### 依赖字段

- `candidate_key`
- `raw_locator_type`
- `raw_locator_value`
- `raw_role`
- `route`
- `step_hit_count`
- `quality_score`
- `probe_status`
- `session_id`
- `candidate_status`

### 6. `PromoteCandidateModal`

#### Props

```ts
interface PromoteCandidateModalProps {
  open: boolean;
  group: CandidateGroupViewModel | null;
  candidates: CandidateElementViewModel[];
  onCancel: () => void;
  onSubmit: (payload: {
    element_code: string;
    element_name: string;
    business_type: string;
    business_domain: string;
    is_key_element: boolean;
    testid_value?: string;
    qa_value?: string;
    route_scope?: string;
    primary_candidate_key?: string;
    review_note?: string;
  }) => Promise<void>;
}
```

#### 本地状态

```ts
const [form, setForm] = useState({
  element_code: "",
  element_name: "",
  business_type: "",
  business_domain: "",
  is_key_element: false,
  testid_value: "",
  qa_value: "",
  route_scope: "",
  primary_candidate_key: "",
  review_note: "",
});
```

#### 本地校验状态

```ts
type PromoteValidationState = {
  codeFormatValid: boolean;
  codeUniqueValid: boolean;
  keyContractValid: boolean;
  locatorStableEnough: boolean;
};
```

#### 接口依赖

- `POST /api/page-objects/{page_code}/candidate-groups/{group_key}/promote`

### 7. `MergeCandidateModal`

#### Props

```ts
interface MergeCandidateModalProps {
  open: boolean;
  group: CandidateGroupViewModel | null;
  candidateKeys: string[];
  formalElements: FormalElementViewModel[];
  onCancel: () => void;
  onSubmit: (payload: {
    target_element_code: string;
    merge_candidate_keys?: string[];
    review_note?: string;
    keep_primary_locator?: boolean;
  }) => Promise<void>;
}
```

#### 本地状态

```ts
const [targetElementCode, setTargetElementCode] = useState("");
const [reviewNote, setReviewNote] = useState("");
const [keepPrimaryLocator, setKeepPrimaryLocator] = useState(true);
```

### 8. `RejectCandidateModal`

#### Props

```ts
interface RejectCandidateModalProps {
  open: boolean;
  mode: "group" | "candidate";
  targetKey: string;
  onCancel: () => void;
  onSubmit: (payload: {
    reason_code: string;
    review_note: string;
  }) => Promise<void>;
}
```

#### 本地状态

```ts
const [reasonCode, setReasonCode] = useState("");
const [reviewNote, setReviewNote] = useState("");
```

#### 本地校验

- `review_note` 必填

---

## 七、录制历史 Tab 规格

### 1. `RecorderHistoryTab`

职责：

- 展示当前页面录制历史
- 回放和跳转治理

#### Props

```ts
interface RecorderHistoryTabProps {
  projectCode: string;
  client: string;
  pageCode: string;
  onReviewSession: (sessionId: string) => void;
}
```

#### 本地状态

```ts
type RecorderHistoryFiltersState = {
  session_id: string;
  status: string;
  date_from: string;
  date_to: string;
};
```

```ts
const [filters, setFilters] = useState<RecorderHistoryFiltersState>(...);
const [items, setItems] = useState<RecorderSessionViewModel[]>([]);
const [playbackSessionId, setPlaybackSessionId] = useState("");
```

#### 接口依赖

- `GET /api/page-objects/recorder/sessions`
- `GET /api/page-objects/recorder/sessions/{session_id}/playback`

### 2. `RecorderHistoryFilters`

#### Props

```ts
interface RecorderHistoryFiltersProps {
  value: RecorderHistoryFiltersState;
  onChange: (next: RecorderHistoryFiltersState) => void;
  onQuery: () => void;
  onReset: () => void;
}
```

### 3. `RecorderHistoryTable`

#### Props

```ts
interface RecorderHistoryTableProps {
  items: RecorderSessionViewModel[];
  loading?: boolean;
  onPlayback: (sessionId: string) => void;
  onReview: (sessionId: string) => void;
  onViewLog: (sessionId: string) => void;
  onViewScript: (sessionId: string) => void;
}
```

### 4. `RecorderPlaybackDrawer`

#### Props

```ts
interface RecorderPlaybackDrawerProps {
  open: boolean;
  sessionId: string;
  onClose: () => void;
}
```

---

## 八、页面级事件流

### 1. 录制完成进入候选治理

事件流：

1. `PageObjectRecorderPage.handleStopRecorder()`
2. stop 接口返回 `session_id`
3. 用户点击 `去元素列表审核`
4. 跳转到：
   - `/assets/page-objects/{pageCode}/elements?project={project}&tab=candidates&session_id={sessionId}`
5. `PageObjectElementsPage` 读取 query
6. 激活 `CandidateElementsTab`
7. `CandidateElementsTab` 自动带 `session_id` 查询

### 2. 候选提升成功

事件流：

1. `PromoteCandidateModal.onSubmit()`
2. 成功后关闭 modal
3. `CandidateElementsTab.reloadGroups()`
4. `CandidateElementsTab.reloadDetail()`
5. `PageObjectElementsPage.handleRefreshAll()`
6. 正式元素统计与候选统计同步刷新

### 3. 候选拒绝成功

事件流：

1. `RejectCandidateModal.onSubmit()`
2. 成功后关闭 modal
3. 刷新当前 group detail
4. 刷新 group list
5. 刷新顶部摘要

---

## 九、建议的目录拆分

```text
frontend/src/pages/
  PageObjectsPage.tsx
  PageObjectRecorderPage.tsx
  PageObjectElementsPage.tsx

frontend/src/components/page-objects/
  PageObjectsHeader.tsx
  PageObjectsStats.tsx
  PageObjectsFilters.tsx
  PageObjectsTable.tsx
  EditPageObjectModal.tsx
  DeletePageObjectModal.tsx

frontend/src/components/page-object-recorder/
  RecorderPageHeader.tsx
  RecorderSessionPanel.tsx
  RecorderHistoryTable.tsx
  RecorderResultCard.tsx
  RecorderPlaybackDrawer.tsx

frontend/src/components/page-object-elements/
  PageElementsHeader.tsx
  GovernanceSummaryCards.tsx
  ElementsTabs.tsx
  FormalElementsTab.tsx
  FormalElementsFilters.tsx
  FormalElementsTable.tsx
  FormalElementDetailDrawer.tsx
  EditFormalElementModal.tsx
  CandidateElementsTab.tsx
  CandidateGroupsFilters.tsx
  CandidateGroupsTable.tsx
  CandidateGroupDetailPanel.tsx
  CandidateDetailTable.tsx
  PromoteCandidateModal.tsx
  MergeCandidateModal.tsx
  RejectCandidateModal.tsx
  RecorderHistoryTab.tsx
  RecorderHistoryFilters.tsx
```

---

## 十、最终建议

实现时最容易失控的地方不是样式，而是状态联动。

因此建议前端落地时坚持两条：

1. 页面级组件只管数据流与联动，不直接塞太多渲染细节
2. 提升、合并、拒绝这三个动作的成功回调统一走 `onAfterMutation`

这样后面无论扩字段还是调交互，都不会把页面状态缠成一团。
