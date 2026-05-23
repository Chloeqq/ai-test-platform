import { deleteJson, getJson, postJson, putJson } from "../lib/http";

export interface ProjectItem {
  project_code: string;
  project_name?: string;
  status?: string;
  source_roots?: string[];
  source_terms?: Record<string, string>;
}

export interface ListProjectsResponse {
  items: ProjectItem[];
  codes: string[];
}

export interface TestProjectPayload {
  project_code: string;
  project_name: string;
  description?: string;
  source_roots?: string[];
  source_terms?: Record<string, string>;
  created_by?: string;
}

export interface TestProjectUpdatePayload {
  project_name?: string;
  description?: string;
  source_roots?: string[];
  source_terms?: Record<string, string>;
  status?: string;
}

export interface TestProjectResponse {
  item?: ProjectItem & Record<string, unknown>;
}

export interface ExecutionTask {
  task_id: string;
  run_id?: string;
  case_id?: string;
  project_code?: string;
  status?: string;
  queue_status?: string;
  source?: string;
  created_at?: string;
  updated_at?: string;
  execution_record_path?: string;
  manifest_path?: string;
  evidence_health?: {
    status?: string;
  };
}

export interface ListExecutionTasksResponse {
  items: ExecutionTask[];
  summary?: {
    total_tasks?: number;
    queue_status_counts?: Record<string, number>;
    governance_risk_priority?: string;
  };
}

export interface TaskQuery {
  limit?: number;
  project_code?: string;
  status?: string;
  source?: string;
}

export interface GenerateCasePayload {
  project: string;
  page: string;
  requirement: string;
  title?: string;
  priority?: string;
  source?: string;
  preview_id?: string;
  selected_candidates?: Array<Record<string, unknown>>;
  selected_intent_ids?: string[];
}

export interface SaveTestPointAssetsResponse {
  message?: string;
  count?: number;
  item?: Record<string, unknown>;
  items?: Array<Record<string, unknown>>;
}

export interface PreviewTestPointsPayload {
  project: string;
  page: string;
  requirement: string;
  source?: string;
}

export interface PreviewTestPointsIntent {
  intent_id?: string;
  title?: string;
  intent_type?: string;
  priority?: string;
  steps_summary?: string;
  expected_result?: string;
  detail_url?: string;
}

export interface PreviewTestPointsResponse {
  item?: {
    preview_id?: string;
    page?: string;
    priority?: string;
    parse_confidence?: number;
    intent_count?: number;
    intent_type_distribution?: Record<string, number>;
    test_intents?: PreviewTestPointsIntent[];
    diagnostics_url?: string;
    output_contract?: Record<string, unknown>;
    quality_gate?: {
      decision?: string;
      stage?: string;
      blocker_count?: number;
      blockers?: Array<Record<string, unknown>>;
    };
    requirement_spec?: {
      page?: string;
      parse_confidence?: number;
      test_intents?: PreviewTestPointsIntent[];
      quality_gate?: {
        decision?: string;
        blockers?: Array<Record<string, unknown>>;
        metrics?: Record<string, unknown>;
      };
    };
  };
  [key: string]: unknown;
}

export interface PrecheckSelectedIntentsPayload {
  project: string;
  page: string;
  preview_id?: string;
  selected_intent_ids?: string[];
  selected_candidates: Array<Record<string, unknown>>;
}

export interface PrecheckSelectedIntentsItem {
  intent_id?: string;
  title?: string;
  status?: "ok" | "warn" | "block" | string;
  reasons?: string[];
  unknown_elements?: string[];
  can_generate?: boolean;
}

export interface PrecheckSelectedIntentsResponse {
  items?: PrecheckSelectedIntentsItem[];
  summary?: {
    total?: number;
    status_counts?: Record<string, number>;
    block_count?: number;
    warn_count?: number;
    ok_count?: number;
    project?: string;
    page?: string;
  };
}

export interface WorkbenchHistoryItem {
  timestamp?: string;
  action?: string;
  case_id?: string;
  run_id?: string;
  page?: string;
  status?: string;
  detail_summary?: string;
  project_code?: string;
}

export interface WorkbenchHistoryResponse {
  items?: WorkbenchHistoryItem[];
  summary?: Record<string, unknown>;
  pagination?: {
    page?: number;
    page_size?: number;
    total_items?: number;
    total_pages?: number;
  };
  meta?: Record<string, unknown>;
}

export interface HistoryQuery {
  limit?: number;
  page?: number;
  page_size?: number;
  project_code?: string;
  keyword?: string;
  sort?: string;
  action?: string;
  actor?: string;
  status?: string;
  risk_gate_decision?: string;
  self_healing_status?: string;
}

function toQuery(params: TaskQuery): string {
  return toLooseQuery({
    limit: typeof params.limit === "number" ? String(params.limit) : "",
    project_code: params.project_code || "",
    status: params.status || "",
    source: params.source || "",
  });
}

function toLooseQuery(params: Record<string, string>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    const text = String(value || "").trim();
    if (text) {
      query.set(key, text);
    }
  });
  return query.toString();
}

export async function listProjects(): Promise<ListProjectsResponse> {
  return getJson<ListProjectsResponse>("/api/workbench/projects");
}

export async function listTestProjects(): Promise<{ items?: Array<ProjectItem & Record<string, unknown>> }> {
  return getJson<{ items?: Array<ProjectItem & Record<string, unknown>> }>("/api/test-projects");
}

export async function createTestProject(payload: TestProjectPayload): Promise<TestProjectResponse> {
  return postJson<TestProjectResponse>("/api/test-projects", payload);
}

export async function updateTestProject(projectCode: string, payload: TestProjectUpdatePayload): Promise<TestProjectResponse> {
  return putJson<TestProjectResponse>(`/api/test-projects/${encodeURIComponent(projectCode)}`, payload);
}

export async function deleteTestProject(projectCode: string): Promise<Record<string, unknown>> {
  return deleteJson<Record<string, unknown>>(`/api/test-projects/${encodeURIComponent(projectCode)}`);
}

export async function listExecutionTasks(params: TaskQuery): Promise<ListExecutionTasksResponse> {
  const query = toQuery(params);
  const path = query ? `/api/workbench/tasks?${query}` : "/api/workbench/tasks";
  return getJson<ListExecutionTasksResponse>(path);
}

export async function saveTestPointAssets(payload: GenerateCasePayload): Promise<SaveTestPointAssetsResponse> {
  return postJson<SaveTestPointAssetsResponse>("/api/workbench/test-point-assets/save", payload);
}

export async function previewTestPoints(payload: PreviewTestPointsPayload): Promise<PreviewTestPointsResponse> {
  return postJson<PreviewTestPointsResponse>("/api/workbench/preview-test-points", payload);
}

export async function getPreviewTestPointDiagnostics(previewId: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`/api/workbench/preview-test-points/${encodeURIComponent(previewId)}/diagnostics`);
}

export async function precheckSelectedIntents(
  payload: PrecheckSelectedIntentsPayload,
): Promise<PrecheckSelectedIntentsResponse> {
  return postJson<PrecheckSelectedIntentsResponse>("/api/workbench/precheck-selected-intents", payload);
}

export async function listWorkbenchHistory(params: HistoryQuery): Promise<WorkbenchHistoryResponse> {
  const query = toLooseQuery({
    limit: typeof params.limit === "number" ? String(params.limit) : "",
    page: typeof params.page === "number" ? String(params.page) : "",
    page_size: typeof params.page_size === "number" ? String(params.page_size) : "",
    project_code: params.project_code || "",
    keyword: params.keyword || "",
    sort: params.sort || "",
    action: params.action || "",
    actor: params.actor || "",
    status: params.status || "",
    risk_gate_decision: params.risk_gate_decision || "",
    self_healing_status: params.self_healing_status || "",
  });
  const path = query ? `/api/workbench/history?${query}` : "/api/workbench/history";
  return getJson<WorkbenchHistoryResponse>(path);
}
