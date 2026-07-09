import { getJson, postJson } from "../lib/http";

// ── Dataset ─────────────────────────────────────────────────

export interface EvalDatasetItem {
  dataset_id: string;
  project_code: string;
  name: string;
  description: string;
  task_type: string;
  eval_dimensions: string[];
  item_count: number;
  version: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface EvalItemDetail {
  item_id: string;
  requirement_text: string;
  expected_coverage: string[];
  expected_assertions: Record<string, unknown>[];
  expected_page_codes: string[];
  known_issues: string[];
}

export interface EvalDatasetDetail extends EvalDatasetItem {
  items: EvalItemDetail[];
}

export function listEvalDatasets(project = "atp", taskType = ""): Promise<EvalDatasetItem[]> {
  const params = new URLSearchParams({ project });
  if (taskType) params.set("task_type", taskType);
  return getJson<EvalDatasetItem[]>(`/api/quality-eval/datasets?${params.toString()}`);
}

export function getEvalDataset(datasetId: string): Promise<EvalDatasetDetail> {
  return getJson<EvalDatasetDetail>(`/api/quality-eval/datasets/${encodeURIComponent(datasetId)}`);
}

export function createEvalDataset(body: Record<string, unknown>): Promise<EvalDatasetItem> {
  return postJson<EvalDatasetItem>("/api/quality-eval/datasets", body);
}

export function deleteEvalDataset(datasetId: string): Promise<{ status: string }> {
  return postJson<{ status: string }>(`/api/quality-eval/datasets/${encodeURIComponent(datasetId)}`, { _method: "DELETE" });
}

// ── Run ─────────────────────────────────────────────────────

export interface EvalRunItem {
  run_id: string;
  dataset_id: string;
  project_code: string;
  agent_version: string;
  llm_model: string;
  prompt_version: string;
  gate_rule_version: string;
  task_type: string;
  eval_dimensions: string[];
  status: string;
  total_items: number;
  completed_items: number;
  overall_score: number;
  coverage_score: number;
  assertion_score: number;
  executability_score: number;
  consistency_score: number;
  robustness_score: number;
  hallucination_risk: number;
  created_at: string | null;
  finished_at: string | null;
}

export interface EvalResultItem {
  result_id: string;
  run_id: string;
  item_id: string;
  requirement_text: string;
  coverage_score: number;
  coverage_detail: Record<string, unknown>;
  assertion_score: number;
  assertion_detail: Record<string, unknown>;
  executability_score: number;
  executability_detail: Record<string, unknown>;
  consistency_score: number;
  robustness_score: number;
  hallucination_flags: string[];
  hallucination_score: number;
  weighted_score: number;
  latency_ms: number;
  error_message: string;
}

export interface EvalRunReport {
  run_id: string;
  dataset_name: string;
  task_type: string;
  agent_version: string;
  llm_model: string;
  status: string;
  overall_score: number;
  dimension_scores: Record<string, number>;
  issue_breakdown: Record<string, number>;
  compared_to_previous: Record<string, unknown> | null;
  worst_items: Record<string, unknown>[];
}

export function listEvalRuns(project = "atp", datasetId = ""): Promise<EvalRunItem[]> {
  const params = new URLSearchParams({ project });
  if (datasetId) params.set("dataset_id", datasetId);
  return getJson<EvalRunItem[]>(`/api/quality-eval/runs?${params.toString()}`);
}

export function createEvalRun(body: Record<string, unknown>): Promise<EvalRunItem> {
  return postJson<EvalRunItem>("/api/quality-eval/runs", body);
}

export function executeEvalRun(runId: string): Promise<{ status: string; overall_score: number }> {
  return postJson<{ status: string; overall_score: number }>(`/api/quality-eval/runs/${encodeURIComponent(runId)}/execute`, {});
}

export function getEvalRun(runId: string): Promise<EvalRunItem> {
  return getJson<EvalRunItem>(`/api/quality-eval/runs/${encodeURIComponent(runId)}`);
}

export function getEvalRunResults(runId: string): Promise<EvalResultItem[]> {
  return getJson<EvalResultItem[]>(`/api/quality-eval/runs/${encodeURIComponent(runId)}/results`);
}

export function getEvalRunReport(runId: string): Promise<EvalRunReport> {
  return getJson<EvalRunReport>(`/api/quality-eval/runs/${encodeURIComponent(runId)}/report`);
}

export function deleteEvalRun(runId: string): Promise<{ status: string }> {
  return postJson<{ status: string }>(`/api/quality-eval/runs/${encodeURIComponent(runId)}`, { _method: "DELETE" });
}