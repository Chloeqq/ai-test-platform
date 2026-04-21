import { startTransition, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getReportFailures, type ReportFailureItem } from "../api/report";
import { ReportTabs } from "./ReportTabs";

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

function formatDate(value: string | undefined): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

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

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>失败详情（React + TypeScript）</h1>
          <p className="muted">可按 case_id、关键词和缺陷关联状态筛选。</p>
        </div>
      </header>
      <ReportTabs />

      <section className="panel filters">
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
      </section>

      <section className="panel table-panel">
        <div className="table-head">
          <strong>命中失败：{total}（高风险：{highRiskCount}）</strong>
          <Link className="button secondary" to="/execution/results">
            返回总览
          </Link>
        </div>
        {loading ? <p>正在加载失败详情...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>失败摘要</th>
                <th>来源</th>
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
                    <td>{item.summary || "-"}</td>
                    <td>{item.failure_source || "-"}</td>
                    <td>{item.risk_level || "-"}</td>
                    <td>{item.recommended_action || "-"}</td>
                    <td>{item.defect_count ?? 0}</td>
                    <td>{formatDate(item.finished_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>当前筛选条件下没有失败项。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}
