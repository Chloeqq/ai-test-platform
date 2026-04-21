import { getJson, postJson } from "../lib/http";

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

export interface CaseDetailResponse {
  item?: Record<string, unknown>;
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

export interface PageObjectsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface PageObjectDetailResponse {
  item?: Record<string, unknown>;
}

export interface PageElementsResponse {
  items?: Array<Record<string, unknown>>;
}

export interface RecorderSessionResponse {
  item?: Record<string, unknown>;
}

export interface RecorderStopResponse {
  [key: string]: unknown;
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

export async function getWorkbenchCase(caseId: string, project = "default"): Promise<CaseDetailResponse> {
  return getJson<CaseDetailResponse>(`/api/workbench/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`);
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

export async function getTestPointAsset(assetId: string, project = "default"): Promise<TestPointAssetDetailResponse> {
  return getJson<TestPointAssetDetailResponse>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`,
  );
}

export async function getTestPointAssetCoverageMatrix(assetId: string, project = "default"): Promise<TestPointCoverageMatrixResponse> {
  return getJson<TestPointCoverageMatrixResponse>(
    `/api/workbench/test-point-assets/${encodeURIComponent(assetId)}/coverage-matrix?project=${encodeURIComponent(project)}`,
  );
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

export async function getPageObject(pageCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageObjectDetailResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || "atp");
  query.set("client", params?.client || "web");
  return getJson<PageObjectDetailResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}?${query.toString()}`);
}

export async function listPageElements(pageCode: string, params?: {
  project_code?: string;
  client?: string;
}): Promise<PageElementsResponse> {
  const query = new URLSearchParams();
  query.set("project_code", params?.project_code || "atp");
  query.set("client", params?.client || "web");
  return getJson<PageElementsResponse>(`/api/page-objects/${encodeURIComponent(pageCode)}/elements?${query.toString()}`);
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

export async function stopRecorderSession(
  sessionId: string,
  payload?: {
    ingest_to_page_object?: boolean;
    cascade_elements?: boolean;
    verify_locators?: boolean;
    verify_timeout_ms?: number;
    changed_by?: string;
  },
): Promise<RecorderStopResponse> {
  return postJson<RecorderStopResponse>(`/api/page-objects/recorder/sessions/${encodeURIComponent(sessionId)}/stop`, payload || {});
}
