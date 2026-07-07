import { startTransition, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getReportFailures, type ReportFailureItem } from "../api/report";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { ReportTabs } from "./ReportTabs";

function text(value: unknown): string {
  return String(value ?? "").trim();
}

/** 提取失败原因摘要 — 优先 likely_cause，其次 failure_source_reason，兜底 summary */
function failureReason(item: ReportFailureItem): string {
  return text(item.likely_cause) || text(item.failure_source_reason) || text(item.summary) || "-";
}

/** 失败分类颜色映射 */
function reasonClass(category: string | undefined): string {
  const c = (category ?? "").toLowerCase();
  if (c === "assertion" || c === "locator" || c === "element") return "reason-assertion";
  if (c === "timeout" || c === "network" || c === "environment") return "reason-timeout";
  if (c === "authentication" || c === "data") return "reason-auth";
  return "reason-generic";
}

interface FailureFilters {
  case_id: string;
  keyword: string;
  defect_status: string;
}

const DEFAULT_FILTERS: FailureFilters = {
  case_id: "",
  keyword: "",
  defect_status: "all",
};

function normalizeFilters(params: URLSearchParams): FailureFilters {
  const caseId = String(params.get("case_id") || "").trim();
  const keyword = String(params.get("keyword") || "").trim();
  const defectStatus = String(params.get("defect_status") || "").trim().toLowerCase();
  return {
    case_id: caseId,
    keyword,
    defect_status: defectStatus || "all",
  };
}

function buildGovernanceHref(item: ReportFailureItem): string {
  const impact = item.element_impact;
  const pageCode = String(impact?.page_code || "").trim();
  const elementCode = String(impact?.element_code || "").trim();
  if (!pageCode || !elementCode) {
    return "#";
  }
  const query = new URLSearchParams();
  const projectCode = String(impact?.project_code || "").trim();
  if (projectCode) {
    query.set("project", projectCode);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return `/assets/page-objects/${encodeURIComponent(pageCode)}/elements/${encodeURIComponent(elementCode)}${suffix}`;
}

export function ReportFailuresPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");
  const [rows, setRows] = useState<ReportFailureItem[]>([]);
  const [filters, setFilters] = useState<FailureFilters>(() => normalizeFilters(searchParams));

  useEffect(() => {
    setFilters(normalizeFilters(searchParams));
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const payload = await getReportFailures(filters);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setRows(Array.isArray(payload.items) ? payload.items : []);
        });
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "失败详情加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [filters]);

  const total = rows.length;
  const highRiskCount = useMemo(
    () => rows.filter((item) => String(item.risk_level || "").trim().toLowerCase() === "high").length,
    [rows],
  );

  // 失败分类统计
  const reasonStats = useMemo(() => {
    const cats: Record<string, number> = {};
    rows.forEach((item) => {
      const cat = text(item.failure_category) || "其他";
      cats[cat] = (cats[cat] || 0) + 1;
    });
    return Object.entries(cats).sort((a, b) => b[1] - a[1]);
  }, [rows]);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>失败详情</h1>
          <p className="muted">可按 case_id、关键词和缺陷关联状态筛选。</p>
        </div>
      </header>
      <ReportTabs />

      <FilterBar>
        <label>
          Case ID
          <input
            value={filters.case_id}
            placeholder="例如 atp-web-login-fn-ai-0001"
            onChange={(event) => setFilters((prev) => ({ ...prev, case_id: event.target.value }))}
          />
        </label>
        <label className="grow">
          关键词
          <input
            value={filters.keyword}
            placeholder="case_id / title / summary / defect_id"
            onChange={(event) => setFilters((prev) => ({ ...prev, keyword: event.target.value }))}
          />
        </label>
        <label>
          缺陷关联
          <select
            value={filters.defect_status}
            onChange={(event) => setFilters((prev) => ({ ...prev, defect_status: event.target.value }))}
          >
            <option value="all">全部</option>
            <option value="linked">已关联</option>
            <option value="unlinked">未关联</option>
          </select>
        </label>
        <div className="header-actions">
          <button
            type="button"
            className="button"
            onClick={() => {
              const next = new URLSearchParams();
              if (filters.case_id.trim()) {
                next.set("case_id", filters.case_id.trim());
              }
              if (filters.keyword.trim()) {
                next.set("keyword", filters.keyword.trim());
              }
              if (filters.defect_status.trim() && filters.defect_status !== "all") {
                next.set("defect_status", filters.defect_status.trim());
              }
              setSearchParams(next, { replace: true });
            }}
          >
            应用筛选
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setFilters(DEFAULT_FILTERS);
              setSearchParams(new URLSearchParams(), { replace: true });
            }}
          >
            重置
          </button>
        </div>
      </FilterBar>

      {/* 失败原因摘要模块 */}
      {!loading && total > 0 && (
        <section className="panel failure-reason-summary">
          <h2 className="failure-reason-title">失败原因概览</h2>
          <div className="failure-reason-stats">
            {reasonStats.map(([cat, count]) => (
              <span key={cat} className={`reason-chip ${reasonClass(cat)}`}>
                {cat} <strong>{count}</strong>
              </span>
            ))}
          </div>
          {highRiskCount > 0 && (
            <p className="failure-reason-highlight">
              {highRiskCount} 个高风险失败需要立即处理
            </p>
          )}
        </section>
      )}

      <DataTable
        title={`命中失败：${total}（高风险：${highRiskCount}）`}
        loading={loading}
        loadingText="正在加载失败详情..."
        errorText={errorText}
        actions={(
          <Link className="button secondary" to="/execution/results">
            返回总览
          </Link>
        )}
      >
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th className="col-failure-reason">失败原因</th>
                <th>来源</th>
                <th>影响元素</th>
                <th>风险</th>
                <th>建议动作</th>
                <th>缺陷</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((item) => (
                  <tr key={String(item.case_id || item.finished_at || Math.random())}>
                    <td className="mono">{item.case_id || "-"}</td>
                    <td className="col-failure-reason">
                      <span className={`failure-reason-text ${reasonClass(item.failure_category)}`}>
                        {failureReason(item)}
                      </span>
                      {item.failed_step?.action && (
                        <div className="failed-step-info">
                          步骤: {item.failed_step.action}
                          {item.failed_step.element_code ? ` → ${item.failed_step.element_code}` : ""}
                        </div>
                      )}
                    </td>
                    <td>{item.failure_source || "-"}</td>
                    <td>
                      {item.element_impact?.element_code ? (
                        <Link
                          className="link"
                          to={buildGovernanceHref(item)}
                        >
                          {item.element_impact.element_code}
                        </Link>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td>
                      <span className={`risk-badge risk-${text(item.risk_level).toLowerCase()}`}>
                        {item.risk_level || "-"}
                      </span>
                    </td>
                    <td>{item.recommended_action || "-"}</td>
                    <td>{item.defect_count ?? 0}</td>
                    <td>{formatDateTime(item.finished_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>
                    <EmptyState title="没有失败项" description="当前筛选条件下没有失败记录，可以调整筛选条件或返回报告总览查看整体质量。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
