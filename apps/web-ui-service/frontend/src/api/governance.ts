import { getJson, postJson } from "../lib/http";

export interface DashboardOverviewResponse {
  as_of?: string;
  risk?: {
    score?: number;
    level?: string;
    summary?: string;
  };
  summary?: {
    pass_rate_24h?: number;
    execution_count_24h?: number;
    intercepted_last10?: number;
    pending_issues?: number;
    as_of?: string;
  };
  trend_24h?: Array<Record<string, unknown>>;
  top_flaky?: Array<Record<string, unknown>>;
  gate_last10?: Array<Record<string, unknown>>;
  pending_issues?: Array<Record<string, unknown>>;
}

export interface DashboardGovernanceResponse {
  as_of?: string;
  risk?: {
    score?: number;
    level?: string;
    summary?: string;
  };
  summary?: Record<string, unknown>;
  flaky_analysis?: {
    items?: Array<Record<string, unknown>>;
  };
  failure_cluster_analysis?: Record<string, unknown>;
  governance_trend?: {
    items?: Array<Record<string, unknown>>;
    summary_7d?: Record<string, unknown>;
  };
}

export interface FailureClustersResponse {
  generated_at?: string;
  total_failed_reports?: number;
  total_clusters?: number;
  clusters?: Array<Record<string, unknown>>;
  error?: string;
}

export interface QualityGateSummaryResponse {
  item?: Record<string, unknown>;
}

export interface DefectsListResponse {
  items?: Array<Record<string, unknown>>;
}

export interface SchedulerSummaryResponse {
  item?: Record<string, unknown>;
}

export interface SchedulerDispatchPlanResponse {
  item?: Record<string, unknown>;
}

export async function getDashboardOverview(): Promise<DashboardOverviewResponse> {
  return getJson<DashboardOverviewResponse>("/api/dashboard/overview");
}

export async function getDashboardGovernance(): Promise<DashboardGovernanceResponse> {
  return getJson<DashboardGovernanceResponse>("/api/dashboard/governance");
}

export async function getFailureClusters(params?: {
  limit?: number;
  max_clusters?: number;
  queue?: string;
  failure_class?: string;
  severity?: string;
}): Promise<FailureClustersResponse> {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") {
    query.set("limit", String(params.limit));
  }
  if (typeof params?.max_clusters === "number") {
    query.set("max_clusters", String(params.max_clusters));
  }
  if (params?.queue) {
    query.set("queue", params.queue);
  }
  if (params?.failure_class) {
    query.set("failure_class", params.failure_class);
  }
  if (params?.severity) {
    query.set("severity", params.severity);
  }
  const qs = query.toString();
  const path = qs ? `/failures/clusters?${qs}` : "/failures/clusters";
  return getJson<FailureClustersResponse>(path);
}

export async function getQualityGateSummary(limit = 100): Promise<QualityGateSummaryResponse> {
  return getJson<QualityGateSummaryResponse>(`/api/workbench/quality-gates/summary?limit=${limit}`);
}

export async function getExecutionGateConfig(): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>("/api/workbench/execution-gate/config");
}

export async function saveExecutionGateDecision(payload: {
  project: string;
  run_id: string;
  page: string;
  case_id?: string;
  decision: string;
  note?: string;
}): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>>("/api/workbench/execution-gate/decisions", payload);
}

export async function approveExecutionGateDecision(payload: {
  project: string;
  run_id: string;
  page: string;
  note?: string;
}): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>>("/api/workbench/execution-gate/decisions/approve", payload);
}

export async function revokeExecutionGateDecision(payload: {
  project: string;
  run_id: string;
  page: string;
  note?: string;
}): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>>("/api/workbench/execution-gate/decisions/revoke", payload);
}

export async function listDefects(caseId = ""): Promise<DefectsListResponse> {
  const normalized = String(caseId || "").trim();
  const path = normalized ? `/api/defects?case_id=${encodeURIComponent(normalized)}` : "/api/defects";
  return getJson<DefectsListResponse>(path);
}

export async function addDefect(payload: {
  case_id: string;
  defect_id: string;
  defect_url?: string;
  system?: string;
  note?: string;
}): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>>("/api/defects", payload);
}

export async function getSchedulerSummary(limit = 100): Promise<SchedulerSummaryResponse> {
  return getJson<SchedulerSummaryResponse>(`/api/workbench/scheduler/summary?limit=${limit}`);
}

export async function getSchedulerDispatchPlan(limit = 200): Promise<SchedulerDispatchPlanResponse> {
  return getJson<SchedulerDispatchPlanResponse>(`/api/workbench/scheduler/dispatch-plan?limit=${limit}`);
}
