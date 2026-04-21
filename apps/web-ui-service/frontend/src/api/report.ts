import { getJson } from "../lib/http";

export interface ReportOverviewSummary {
  total_runs?: number;
  passed_runs?: number;
  failed_runs?: number;
  pass_rate?: number;
  health_score?: number;
  high_risk_failures?: number;
  actionable_suggestions?: number;
}

export interface ReportOverviewFailureItem {
  case_id?: string;
  case_title?: string;
  summary?: string;
  risk_level?: string;
  failure_source?: string;
  finished_at?: string;
  defect_count?: number;
}

export interface ReportOverviewResponse {
  summary?: ReportOverviewSummary;
  recent_failures?: ReportOverviewFailureItem[];
  execution_meta?: Record<string, unknown>;
}

export interface ReportFailureItem {
  case_id?: string;
  case_title?: string;
  finished_at?: string;
  summary?: string;
  failure_category?: string;
  failure_source?: string;
  failure_source_reason?: string;
  likely_cause?: string;
  risk_level?: string;
  recommended_action?: string;
  confidence?: number | string;
  defect_count?: number;
}

export interface ReportFailuresResponse {
  items?: ReportFailureItem[];
  evidence_meta?: Record<string, unknown>;
}

export interface ReportContextResponse {
  git?: {
    commit_id?: string;
    commit_message?: string;
    branch?: string;
  };
  build?: {
    build_version?: string;
    image_tag?: string;
    build_time?: string;
  };
  execution?: {
    base_url?: string;
    browser?: string;
    environment?: string;
    runner?: string;
    latest_run_id?: string;
    latest_execution_source?: string;
    execution_meta?: Record<string, unknown>;
  };
}

export interface ReportPerformanceSummary {
  average_duration_seconds?: number;
  max_duration_seconds?: number;
  latest_delta_seconds?: number;
  sample_count?: number;
}

export interface ReportPerformanceCaseItem {
  run_id?: string;
  case_id?: string;
  status?: string;
  duration_seconds?: number;
  finished_at?: string;
  source?: string;
}

export interface ReportPerformanceResponse {
  summary?: ReportPerformanceSummary;
  slow_cases?: ReportPerformanceCaseItem[];
  execution_meta?: Record<string, unknown>;
}

export interface ReportAllureResponse {
  allure_index?: string;
  available?: boolean;
  version?: number;
  summary?: Record<string, unknown>;
}

export interface ExecutionReportItem {
  execution_id?: number;
  case_id?: number;
  case_name?: string;
  status?: string;
  duration_ms?: number;
  report_url?: string;
  executed_at?: string;
}

export interface ExecutionReportDetailResponse {
  item?: ExecutionReportItem;
}

function toQuery(params: Record<string, string>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    const normalized = String(value || "").trim();
    if (normalized) {
      query.set(key, normalized);
    }
  });
  return query.toString();
}

export async function getReportOverview(): Promise<ReportOverviewResponse> {
  return getJson<ReportOverviewResponse>("/api/report/overview");
}

export async function getReportFailures(params: {
  case_id?: string;
  keyword?: string;
  defect_status?: string;
}): Promise<ReportFailuresResponse> {
  const query = toQuery({
    case_id: params.case_id || "",
    keyword: params.keyword || "",
    defect_status: params.defect_status || "",
  });
  const path = query ? `/api/report/failures?${query}` : "/api/report/failures";
  return getJson<ReportFailuresResponse>(path);
}

export async function getReportContext(): Promise<ReportContextResponse> {
  return getJson<ReportContextResponse>("/api/report/context");
}

export async function getReportPerformance(): Promise<ReportPerformanceResponse> {
  return getJson<ReportPerformanceResponse>("/api/report/performance");
}

export async function getReportAllure(): Promise<ReportAllureResponse> {
  return getJson<ReportAllureResponse>("/api/report/allure");
}

export async function getExecutionReportDetail(executionId: string): Promise<ExecutionReportDetailResponse> {
  const normalized = String(executionId || "").trim();
  return getJson<ExecutionReportDetailResponse>(`/api/report/executions/${encodeURIComponent(normalized)}`);
}
