import { deleteJson, getJson, postFormData, postJson, putJson } from "../lib/http";
import { DEFAULT_PROJECT_CODE } from "../config/projects";

export interface CasesListResponse {
  items?: Array<Record<string, unknown>>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
    has_prev?: boolean;
    has_next?: boolean;
  };
  filters?: Record<string, unknown>;
}

export interface WorkbenchTestCasesResponse {
  items?: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
  filters?: Record<string, unknown>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
    has_prev?: boolean;
    has_next?: boolean;
  };
}

export interface TestCaseGenerationFailuresResponse {
  items?: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
  filters?: Record<string, unknown>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
    has_prev?: boolean;
    has_next?: boolean;
  };
}

export interface DeleteWorkbenchTestCasesResponse {
  message?: string;
  project?: string;
  deleted_count?: number;
  deleted_case_ids?: string[];
  missing_case_ids?: string[];
  delete_all?: boolean;
}

export interface CaseDetailResponse {
  item?: Record<string, unknown>;
}

export interface TestCasesDbListResponse {
  items?: Array<Record<string, unknown>>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
    has_prev?: boolean;
    has_next?: boolean;
  };
  filters?: Record<string, unknown>;
  stats?: Record<string, unknown>;
  search_context?: Record<string, unknown>;
}

export interface TestCaseDbDetailResponse {
  basic?: Record<string, unknown>;
  governance?: Record<string, unknown>;
  script_code?: string;
  detail_content?: Record<string, unknown>;
  data_config?: Record<string, unknown>;
  defects?: Array<Record<string, unknown>>;
  executions?: Array<Record<string, unknown>>;
  versions?: Array<Record<string, unknown>>;
}

export interface CaseVersionCompareResponse {
  from_version?: number;
  to_version?: number;
  added_lines?: number;
  removed_lines?: number;
  diff_lines?: string[];
}

export interface CaseDictionariesResponse {
  items?: Record<string, unknown>;
}

export interface BatchTagsUpdatePayload {
  ids?: number[];
  case_ids?: string[];
  tags: string[];
  mode?: "replace" | "append";
}

export interface BatchStatusUpdatePayload {
  ids?: number[];
  case_ids?: string[];
  status: string;
}

export interface BatchUpdateResponse {
  updated_count?: number;
  status?: string;
}

export interface TestPointAssetsResponse {
  items?: Array<Record<string, unknown>>;
  selection_summary?: Record<string, unknown>;
  coverage_summary?: Record<string, unknown>;
}

export interface TestPointAssetDetailResponse {
  item?: Record<string, unknown>;
}

export interface TestPointCoverageMatrixResponse {
  item?: Record<string, unknown>;
}

export interface UpsertTestPointAssetPayload {
  project: string;
  asset_id: string;
  page: string;
  title?: string;
  priority?: string;
  requirement?: string;
  source_type?: string;
  points?: Array<Record<string, unknown>>;
  selected_candidates?: Array<Record<string, unknown>>;
}

export interface BatchDeleteTestPointAssetsResponse {
  deleted_count?: number;
  deleted_asset_ids?: string[];
  missing_count?: number;
  missing_asset_ids?: string[];
}

export interface BatchGenerateFromTestPointAssetsResponse {
  message?: string;
  count?: number;
  items?: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
}

export interface TestPointScriptPreviewResponse {
  item?: Record<string, unknown>;
}

export interface TestPointReviewsResponse {
  items?: Array<Record<string, unknown>>;
  summary?: Record<string, unknown>;
  filters?: Record<string, unknown>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
    has_prev?: boolean;
    has_next?: boolean;
  };
}

export interface BatchTestPointReviewResponse {
  message?: string;
  updated_count?: number;
  status?: string;
  affected_assets?: string[];
  missing?: Array<Record<string, unknown>>;
}

export interface PageObjectsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface PageObjectDetailResponse {
  item?: Record<string, unknown>;
}

export interface PageElementsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface PageElementDetailResponse {
  item?: Record<string, unknown>;
}

export interface PageElementVersionsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface PageObjectRefsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface PageObjectImportResponse {
  item?: Record<string, unknown>;
}

export interface CandidateGroupsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface CandidateElementsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface CandidateGroupDetailResponse {
  item?: Record<string, unknown>;
}

export interface CandidateMutationResponse {
  item?: Record<string, unknown>;
}

export interface BatchPhysicalDeleteResponse {
  item?: Record<string, unknown>;
}

export interface PageObjectCreatePayload {
  project_code: string;
  client: string;
  page_code: string;
  page_name: string;
  page_url?: string;
  precondition_state?: string;
  module_id?: number;
  health_status?: number;
  description?: string;
  status?: string;
  created_by?: string;
}

export interface PageObjectUpdatePayload {
  page_name?: string;
  page_url?: string;
  precondition_state?: string;
  module_id?: number;
  health_status?: number;
  description?: string;
  status?: string;
}

export interface PageElementUpdatePayload {
  element_code?: string;
  element_name?: string;
  locator_type?: string;
  locator_value?: string;
  backup_locator?: string;
  business_type?: string;
  business_domain?: string;
  aliases_json?: unknown[];
  semantic_tags_json?: unknown[];
  locator_source?: string;
  match_strategy?: string;
  stability_level?: string;
  review_status?: string;
  origin_candidate_key?: string;
  route_scope?: string;
  anchor_required?: boolean;
  is_key_element?: boolean;
  testid_value?: string;
  qa_value?: string;
  governance_note?: string;
  health_status?: number;
  role?: string;
  status?: string;
  is_primary?: boolean;
  owner?: string;
  changed_by?: string;
  change_summary?: string;
}

export interface RecorderSessionResponse {
  item?: Record<string, unknown>;
}

export interface RecorderSessionsListResponse {
  items?: Array<Record<string, unknown>>;
  total?: number;
  filters?: Record<string, unknown>;
  pagination?: Record<string, unknown>;
}

export interface RecorderSessionPlaybackResponse {
  item?: Record<string, unknown>;
}

export interface RecorderStopResponse {
  [key: string]: unknown;
}

function toQuery(params: Record<string, unknown>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) {
      return;
    }
    const normalized = String(value).trim();
    if (normalized) {
      query.set(key, normalized);
    }
  });
  return query.toString();
}

export async function listWorkbenchCases(params?: {
  project?: string;
  page?: number;
  page_size?: number;
  focus_case_id?: string;
}): Promise<CasesListResponse> {
  const query = new URLSearchParams();
  if (params?.project) {
    query.set("project", params.project);
  }
  if (typeof params?.page === "number") {
    query.set("page", String(params.page));
  }
  if (typeof params?.page_size === "number") {
    query.set("page_size", String(params.page_size));
  }
  if (params?.focus_case_id) {
    query.set("focus_case_id", params.focus_case_id);
  }
  const qs = query.toString();
  return getJson<CasesListResponse>(qs ? `/api/workbench/cases?${qs}` : "/api/workbench/cases");
}

export async function getWorkbenchCase(caseId: string, project = DEFAULT_PROJECT_CODE): Promise<CaseDetailResponse> {
  return getJson<CaseDetailResponse>(`/api/workbench/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`);
}

export async function listWorkbenchTestCases(params?: {
  project?: string;
  page?: string;
  source_asset?: string;
  intent_type?: string;
  priority?: string;
  execution_status?: string;
  active_status?: string;
  keyword?: string;
  page_index?: number;
  page_size?: number;
}): Promise<WorkbenchTestCasesResponse> {
  const qs = toQuery(params || {});
  return getJson<WorkbenchTestCasesResponse>(qs ? `/api/workbench/test-cases?${qs}` : "/api/workbench/test-cases");
}

export async function listTestCaseGenerationFailures(params?: {
  project?: string;
  asset_id?: string;
  keyword?: string;
  page_index?: number;
  page_size?: number;
}): Promise<TestCaseGenerationFailuresResponse> {
  const qs = toQuery(params || {});
  return getJson<TestCaseGenerationFailuresResponse>(
    qs ? `/api/workbench/test-case-generation-failures?${qs}` : "/api/workbench/test-case-generation-failures",
  );
}

export async function getWorkbenchTestCase(caseId: string, project = DEFAULT_PROJECT_CODE): Promise<CaseDetailResponse> {
  return getJson<CaseDetailResponse>(`/api/workbench/test-cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`);
}

export async function deleteWorkbenchTestCase(caseId: string, project = DEFAULT_PROJECT_CODE): Promise<DeleteWorkbenchTestCasesResponse> {
  return deleteJson<DeleteWorkbenchTestCasesResponse>(
    `/api/workbench/test-cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`,
  );
}

export async function batchDeleteWorkbenchTestCases(payload: {
  project: string;
  case_ids?: string[];
  delete_all?: boolean;
  confirm_text?: string;
}): Promise<DeleteWorkbenchTestCasesResponse> {
  return postJson<DeleteWorkbenchTestCasesResponse>("/api/workbench/test-cases/batch/delete", payload);
}

export async function runWorkbenchCase(payload: {
  project: string;
  case_id: string;
  case_path?: string;
  source?: string;
}): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>>("/api/workbench/run", payload);
}

export async function getWorkbenchRun(runId: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`/api/workbench/runs/${encodeURIComponent(runId)}`);
}

export async function listTestCasesDb(params?: {
  q?: string;
  project_code?: string;
  source?: string;
  tag?: string;
  priority?: string;
  status?: string;
  creator?: string;
  last_result?: string;
  product_line?: string;
  module?: string;
  test_type?: string;
  sort_field?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}): Promise<TestCasesDbListResponse> {
  const qs = toQuery(params || {});
  return getJson<TestCasesDbListResponse>(qs ? `/api/test-cases?${qs}` : "/api/test-cases");
}

export async function getTestCaseDbDetail(caseId: string): Promise<TestCaseDbDetailResponse> {
  return getJson<TestCaseDbDetailResponse>(`/api/test-cases/${encodeURIComponent(caseId)}`);
}

export async function compareTestCaseVersions(
  caseId: string,
  params: {
    from_version: number;
    to_version: number;
  },
): Promise<CaseVersionCompareResponse> {
  const query = toQuery({
    from_version: params.from_version,
    to_version: params.to_version,
  });
  return getJson<CaseVersionCompareResponse>(`/api/test-cases/${encodeURIComponent(caseId)}/versions/compare?${query}`);
}

export async function batchUpdateTestCaseTags(payload: BatchTagsUpdatePayload): Promise<BatchUpdateResponse> {
  return postJson<BatchUpdateResponse>("/api/test-cases/batch/tags", payload);
}

export async function batchUpdateTestCaseStatus(payload: BatchStatusUpdatePayload): Promise<BatchUpdateResponse> {
  return postJson<BatchUpdateResponse>("/api/test-cases/batch/status", payload);
}

export async function getWorkbenchCaseDictionaries(): Promise<CaseDictionariesResponse> {
  return getJson<CaseDictionariesResponse>("/api/workbench/case-dictionaries");
}

export async function listTestPointAssets(params?: {
  project?: string;
  page?: string;
  keyword?: string;
  source_type?: string;
  coverage_status?: string;
  review_status?: string;
  gate_decision?: string;
  selection_state?: string;
}): Promise<TestPointAssetsResponse> {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    const normalized = String(value || "").trim();
    if (normalized) {
      query.set(key, normalized);
    }
  });
  const qs = query.toString();
  return getJson<TestPointAssetsResponse>(qs ? `/api/workbench/test-point-assets?${qs}` : "/api/workbench/test-point-assets");
}

export async function getTestPointAsset(assetId: string, project = DEFAULT_PROJECT_CODE): Promise<TestPointAssetDetailResponse> {
  return getJson<TestPointAssetDetailResponse>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`,
  );
}

export async function getTestPointAssetCoverageMatrix(assetId: string, project = DEFAULT_PROJECT_CODE): Promise<TestPointCoverageMatrixResponse> {
  return getJson<TestPointCoverageMatrixResponse>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}/coverage-matrix?project=${encodeURIComponent(project)}`,
  );
}

export async function upsertTestPointAsset(payload: UpsertTestPointAssetPayload): Promise<TestPointAssetDetailResponse> {
  return postJson<TestPointAssetDetailResponse>("/api/workbench/test-point-assets", payload);
}

export async function updateTestPointAsset(assetId: string, payload: UpsertTestPointAssetPayload): Promise<TestPointAssetDetailResponse> {
  return putJson<TestPointAssetDetailResponse>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}`,
    payload,
  );
}

export async function deleteTestPointAsset(assetId: string, project = DEFAULT_PROJECT_CODE): Promise<Record<string, unknown>> {
  return deleteJson<Record<string, unknown>>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`,
  );
}

export async function batchDeleteTestPointAssets(payload: {
  project: string;
  asset_ids: string[];
}): Promise<BatchDeleteTestPointAssetsResponse> {
  return postJson<BatchDeleteTestPointAssetsResponse>("/api/workbench/test-point-assets/batch/delete", payload);
}

export async function batchGenerateCasesFromTestPointAssets(payload: {
  project: string;
  asset_ids: string[];
  intent_ids?: string[];
  source?: string;
}): Promise<BatchGenerateFromTestPointAssetsResponse> {
  return postJson<BatchGenerateFromTestPointAssetsResponse>("/api/workbench/test-point-assets/batch/generate-cases", payload);
}

export async function listTestPointReviews(params?: {
  project?: string;
  page?: string;
  keyword?: string;
  status?: string;
  intent_type?: string;
  priority?: string;
  can_generate?: string;
  page_index?: number;
  page_size?: number;
}): Promise<TestPointReviewsResponse> {
  const qs = toQuery(params || {});
  return getJson<TestPointReviewsResponse>(qs ? `/api/workbench/test-point-reviews?${qs}` : "/api/workbench/test-point-reviews");
}

export async function batchReviewTestPoints(payload: {
  project: string;
  decisions: Array<{ asset_id: string; intent_id: string }>;
  status: string;
  note?: string;
  reviewed_by?: string;
}): Promise<BatchTestPointReviewResponse> {
  return postJson<BatchTestPointReviewResponse>("/api/workbench/test-point-reviews/batch", payload);
}

export async function getTestPointScriptPreview(params: {
  project: string;
  asset_id: string;
  intent_id: string;
}): Promise<TestPointScriptPreviewResponse> {
  const qs = toQuery(params);
  return getJson<TestPointScriptPreviewResponse>(`/api/workbench/preview-script?${qs}`);
}

export async function listPageObjects(params?: {
  project_code?: string;
  client?: string;
  status?: string;
}): Promise<PageObjectsResponse> {
  const query = new URLSearchParams();
  if (params?.project_code) {
    query.set("project_code", params.project_code);
  }
  if (params?.client) {
    query.set("client", params.client);
  }
  if (params?.status) {
    query.set("status", params.status);
  }
  const qs = query.toString();
  return getJson<PageObjectsResponse>(qs ? `/api/page-objects?${qs}` : "/api/page-objects");
}

export async function previewPageObjectImport(payload: {
  project_code: string;
  client?: string;
  source_type?: string;
  page_code?: string;
  data_testid_guidelines: File;
  runtime_dom_selectors?: File | null;
}): Promise<PageObjectImportResponse> {
  const form = new FormData();
  form.set("project_code", payload.project_code || DEFAULT_PROJECT_CODE);
  form.set("client", payload.client || "web");
  form.set("source_type", payload.source_type || "data_testid_guidelines");
  if (payload.page_code) {
    form.set("page_code", payload.page_code);
  }
  form.set("data_testid_guidelines", payload.data_testid_guidelines);
  if (payload.runtime_dom_selectors) {
    form.set("runtime_dom_selectors", payload.runtime_dom_selectors);
  }
  return postFormData<PageObjectImportResponse>("/api/page-objects/imports/preview", form);
}

export async function getPageObjectImport(importId: string): Promise<PageObjectImportResponse> {
  return getJson<PageObjectImportResponse>(`/api/page-objects/imports/${encodeURIComponent(importId)}`);
}

export async function applyPageObjectImport(
  importId: string,
  params?: { auto_approve?: boolean; upsert_policy?: string; operator?: string },
): Promise<PageObjectImportResponse> {
  const query = new URLSearchParams();
  query.set("auto_approve", String(params?.auto_approve ?? true));
  query.set("upsert_policy", params?.upsert_policy || "upgrade_existing");
  query.set("operator", params?.operator || "admin");
  return postJson<PageObjectImportResponse>(`/api/page-objects/imports/${encodeURIComponent(importId)}/apply?${query.toString()}`, {});
}

export async function getPageObject(pageCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageObjectDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<PageObjectDetailResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}?${query.toString()}`);
}

export async function listPageElements(pageCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageElementsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<PageElementsResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}/elements?${query.toString()}`);
}

export async function getPageElement(pageCode: string, elementCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageElementDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<PageElementDetailResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/elements/${encodeURIComponent(elementCode)}?${query.toString()}`,
  );
}

export async function updatePageElement(
  pageCode: string,
  elementCode: string,
  payload: PageElementUpdatePayload,
  params?: { project_code?: string; client?: string },
): Promise<PageElementDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return putJson<PageElementDetailResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/elements/${encodeURIComponent(elementCode)}?${query.toString()}`,
    payload,
  );
}

export async function batchDeletePageElements(
  pageCode: string,
  payload: { element_codes: string[] },
  params?: { project_code?: string; client?: string },
): Promise<BatchPhysicalDeleteResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<BatchPhysicalDeleteResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/elements/batch/delete?${query.toString()}`,
    payload,
  );
}

export async function listPageElementVersions(pageCode: string, elementCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageElementVersionsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<PageElementVersionsResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/elements/${encodeURIComponent(elementCode)}/versions?${query.toString()}`,
  );
}

export async function listPageObjectRefs(pageCode: string, elementCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageObjectRefsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<PageObjectRefsResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/elements/${encodeURIComponent(elementCode)}/refs?${query.toString()}`,
  );
}

export async function listCandidateGroups(pageCode: string, params?: {
  project_code?: string;
  client?: string;
  promotion_status?: string;
  quality_tier?: string;
  session_id?: string;
}): Promise<CandidateGroupsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  if (params?.promotion_status) {
    query.set("promotion_status", params.promotion_status);
  }
  if (params?.quality_tier) {
    query.set("quality_tier", params.quality_tier);
  }
  if (params?.session_id) {
    query.set("session_id", params.session_id);
  }
  return getJson<CandidateGroupsResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups?${query.toString()}`);
}

export async function listCandidateElements(pageCode: string, params?: {
  project_code?: string;
  client?: string;
  group_key?: string;
  session_id?: string;
  candidate_status?: string;
}): Promise<CandidateElementsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  if (params?.group_key) {
    query.set("group_key", params.group_key);
  }
  if (params?.session_id) {
    query.set("session_id", params.session_id);
  }
  if (params?.candidate_status) {
    query.set("candidate_status", params.candidate_status);
  }
  return getJson<CandidateElementsResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}/candidate-elements?${query.toString()}`);
}

export async function getCandidateGroup(pageCode: string, groupKey: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<CandidateGroupDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return getJson<CandidateGroupDetailResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups/${encodeURIComponent(groupKey)}?${query.toString()}`,
  );
}

export async function promoteCandidateGroup(pageCode: string, groupKey: string, payload: Record<string, unknown>, params?: {
  project_code?: string;
  client?: string;
}): Promise<CandidateMutationResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<CandidateMutationResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups/${encodeURIComponent(groupKey)}/promote?${query.toString()}`,
    payload,
  );
}

export async function mergeCandidateGroup(pageCode: string, groupKey: string, payload: Record<string, unknown>, params?: {
  project_code?: string;
  client?: string;
}): Promise<CandidateMutationResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<CandidateMutationResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups/${encodeURIComponent(groupKey)}/merge?${query.toString()}`,
    payload,
  );
}

export async function rejectCandidateGroup(pageCode: string, groupKey: string, payload: Record<string, unknown>, params?: {
  project_code?: string;
  client?: string;
}): Promise<CandidateMutationResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<CandidateMutationResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups/${encodeURIComponent(groupKey)}/reject?${query.toString()}`,
    payload,
  );
}

export async function rejectCandidateElement(pageCode: string, candidateKey: string, payload: Record<string, unknown>, params?: {
  project_code?: string;
  client?: string;
}): Promise<CandidateMutationResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<CandidateMutationResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-elements/${encodeURIComponent(candidateKey)}/reject?${query.toString()}`,
    payload,
  );
}

export async function batchDeleteCandidateGroups(
  pageCode: string,
  payload: { group_keys: string[] },
  params?: { project_code?: string; client?: string },
): Promise<BatchPhysicalDeleteResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<BatchPhysicalDeleteResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-groups/batch/delete?${query.toString()}`,
    payload,
  );
}

export async function batchDeleteCandidateElements(
  pageCode: string,
  payload: { candidate_keys: string[] },
  params?: { project_code?: string; client?: string },
): Promise<BatchPhysicalDeleteResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<BatchPhysicalDeleteResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}/candidate-elements/batch/delete?${query.toString()}`,
    payload,
  );
}

export async function createPageObject(payload: PageObjectCreatePayload): Promise<PageObjectDetailResponse> {
  return postJson<PageObjectDetailResponse>("/api/page-objects", payload);
}

export async function updatePageObject(
  pageCode: string,
  payload: PageObjectUpdatePayload,
  params?: { project_code?: string; client?: string },
): Promise<PageObjectDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return putJson<PageObjectDetailResponse>(
    `/api/page-objects/${encodeURIComponent(pageCode)}?${query.toString()}`,
    payload,
  );
}

export async function deletePageObject(
  pageCode: string,
  params?: { project_code?: string; client?: string; cascade_elements?: boolean },
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  query.set("cascade_elements", String(Boolean(params?.cascade_elements)));
  return deleteJson<Record<string, unknown>>(
    `/api/page-objects/${encodeURIComponent(pageCode)}?${query.toString()}`,
  );
}

export async function createRecorderSession(payload: {
  project_code: string;
  client: string;
  page_code: string;
  page_name: string;
  url: string;
  started_by?: string;
}): Promise<RecorderSessionResponse> {
  return postJson<RecorderSessionResponse>("/api/page-objects/recorder/sessions", payload);
}

export async function heartbeatRecorderSession(sessionId: string, payload?: {
  heartbeat_by?: string;
}): Promise<RecorderSessionResponse> {
  return postJson<RecorderSessionResponse>(`/api/page-objects/recorder/sessions/${encodeURIComponent(sessionId)}/heartbeat`, payload || {});
}

export async function listRecorderSessions(params?: {
  project_code?: string;
  client?: string;
  page_code?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<RecorderSessionsListResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  if (params?.page_code) {
    query.set("page_code", params.page_code);
  }
  if (params?.status) {
    query.set("status", params.status);
  }
  if (typeof params?.limit === "number") {
    query.set("limit", String(params.limit));
  }
  if (typeof params?.offset === "number") {
    query.set("offset", String(params.offset));
  }
  return getJson<RecorderSessionsListResponse>(`/api/page-objects/recorder/sessions?${query.toString()}`);
}

export async function getRecorderSessionPlayback(sessionId: string): Promise<RecorderSessionPlaybackResponse> {
  return getJson<RecorderSessionPlaybackResponse>(`/api/page-objects/recorder/sessions/${encodeURIComponent(sessionId)}/playback`);
}

export async function replayRecorderSession(
  sessionId: string,
  payload?: {
    timeout_seconds?: number;
  },
): Promise<RecorderSessionPlaybackResponse> {
  return postJson<RecorderSessionPlaybackResponse>(
    `/api/page-objects/recorder/sessions/${encodeURIComponent(sessionId)}/replay`,
    payload || {},
  );
}

export async function batchDeleteRecorderSessions(
  payload: { session_ids: string[]; delete_artifacts?: boolean },
  params?: { project_code?: string; client?: string },
): Promise<BatchPhysicalDeleteResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || DEFAULT_PROJECT_CODE);
  query.set("client", params?.client || "web");
  return postJson<BatchPhysicalDeleteResponse>(
    `/api/page-objects/recorder/sessions/batch/delete?${query.toString()}`,
    payload,
  );
}

export async function stopRecorderSession(
  sessionId: string,
  payload?: {
    cascade_elements?: boolean;
    verify_locators?: boolean;
    verify_timeout_ms?: number;
    changed_by?: string;
  },
): Promise<RecorderStopResponse> {
  return postJson<RecorderStopResponse>(`/api/page-objects/recorder/sessions/${encodeURIComponent(sessionId)}/stop`, payload || {});
}
