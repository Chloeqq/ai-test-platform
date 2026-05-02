import { useEffect, useState } from "react";
import { formatDateTime } from "../lib/datetime";

import { getReportPerformance, type ReportPerformanceCaseItem, type ReportPerformanceSummary } from "../api/report";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ReportTabs } from "./ReportTabs";

function summaryValue(value: number | string | undefined, suffix = ""): string {
  if (typeof value === "number") {
    return `${value}${suffix}`;
  }
  const text = String(value || "").trim();
  return text ? `${text}${suffix}` : "-";
}

export function ReportPerformancePage() {
  const [summary, setSummary] = useState<ReportPerformanceSummary>({});
  const [rows, setRows] = useState<ReportPerformanceCaseItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const payload = await getReportPerformance();
        if (!cancelled) {
          setSummary(payload.summary || {});
          setRows(Array.isArray(payload.slow_cases) ? payload.slow_cases : []);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "性能数据加载失败");
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
  }, []);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>性能耗时</h1>
          <p className="muted">展示平均耗时、最大耗时与慢用例 Top10。</p>
        </div>
      </header>
      <ReportTabs />

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">平均耗时</span>
          <strong>{summaryValue(summary.average_duration_seconds, "s")}</strong>
        </article>
        <article className="stat-card">
          <span className="label">最大耗时</span>
          <strong>{summaryValue(summary.max_duration_seconds, "s")}</strong>
        </article>
        <article className="stat-card">
          <span className="label">最新差值</span>
          <strong>{summaryValue(summary.latest_delta_seconds, "s")}</strong>
        </article>
        <article className="stat-card">
          <span className="label">样本数</span>
          <strong>{summaryValue(summary.sample_count)}</strong>
        </article>
      </section>

      <DataTable loading={loading} loadingText="正在加载性能数据..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Case ID</th>
                <th>状态</th>
                <th>耗时(s)</th>
                <th>来源</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((item) => (
                  <tr key={String(item.run_id || item.case_id || Math.random())}>
                    <td className="mono">{item.run_id || "-"}</td>
                    <td className="mono">{item.case_id || "-"}</td>
                    <td>{item.status || "-"}</td>
                    <td>{summaryValue(item.duration_seconds)}</td>
                    <td>{item.source || "-"}</td>
                    <td>{formatDateTime(item.finished_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="暂无性能样本" description="执行完成后会在这里展示用例耗时和性能波动。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
