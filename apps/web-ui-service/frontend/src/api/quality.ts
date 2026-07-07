import { getJson } from "../lib/http";

export interface QualitySummaryResponse {
  project: string;
  generated_at: string;
  asset_count: number;
  snapshot_coverage: number;
  fallback_count: number;
  avg_score: number;
  decision_summary: Record<string, number>;
  issue_summary: Record<string, number>;
}

export interface QualityRankingItem {
  asset_id: string;
  score: number;
  decision: string;
  version: number;
  updated_at: string;
  source: string;
}

export interface QualityIssuesResponse {
  project: string;
  generated_at: string;
  asset_count: number;
  issue_summary: Record<string, number>;
}

export interface QualityTimelineItem {
  version: number;
  at: string;
  score: number;
  decision: string;
  zero_assertion_count: number;
  unprocessed_count: number;
  delta_score: number;
}

export function getQualitySummary(project = "mall"): Promise<QualitySummaryResponse> {
  return getJson<QualitySummaryResponse>(`/api/workbench/quality/summary?project=${encodeURIComponent(project)}`);
}

export function getQualityRanking(project = "mall", limit = 10): Promise<QualityRankingItem[]> {
  return getJson<QualityRankingItem[]>(`/api/workbench/quality/ranking?project=${encodeURIComponent(project)}&limit=${limit}`);
}

export function getQualityIssues(project = "mall"): Promise<QualityIssuesResponse> {
  return getJson<QualityIssuesResponse>(`/api/workbench/quality/issues?project=${encodeURIComponent(project)}`);
}

export function getQualityTimeline(assetId: string, project = "mall"): Promise<QualityTimelineItem[]> {
  return getJson<QualityTimelineItem[]>(`/api/workbench/quality/timeline/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`);
}
