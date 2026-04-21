import { startTransition, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getReportOverview, type ReportOverviewFailureItem, type ReportOverviewSummary } from "../api/report";
import { ReportTabs } from "./ReportTabs";

function summaryValue(value: number | string | undefined, suffix = ""): string {
  if (typeof value === "number") {
    return `${value}${suffix}`;
  }
  const text = String(value || "").trim();
  return text ? `${text}${suffix}` : "-";
}

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

export function ReportOverviewPage() {
  const [summary, setSummary] = useState<ReportOverviewSummary>({});
  const [recentFailures, setRecentFailures] = useState<ReportOverviewFailureItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const payload = await getReportOverview();
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setSummary(payload.summary || {});
          setRecentFailures(Array.isArray(payload.recent_failures) ? payload.recent_failures : []);
        });
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "执行结果总览加载失败");
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
          <h1>执行结果总览（React + TypeScript）</h1>
          <p className="muted">执行结果页面族已迁移到 React 主链。</p>
        </div>
      </header>
      <ReportTabs />

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">总运行次数</span>
          <strong>{summaryValue(summary.total_runs)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">通过率</span>
          <strong>{summaryValue(summary.pass_rate, "%")}</strong>
        </article>
        <article className="stat-card">
          <span className="label">健康度</span>
          <strong>{summaryValue(summary.health_score)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">高风险失败</span>
          <strong>{summaryValue(summary.high_risk_failures)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">可行动建议</span>
          <strong>{summaryValue(summary.actionable_suggestions)}</strong>
        </article>
      </section>

      <section className="panel table-panel">
        <div className="table-head">
          <strong>近期失败记录</strong>
          <Link className="button secondary" to="/execution/results/failures">
            查看失败详情
          </Link>
        </div>
        {loading ? <p>正在加载执行总览...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>标题</th>
                <th>摘要</th>
                <th>风险</th>
                <th>来源</th>
                <th>缺陷</th>
                <th>完成时间</th>
              </tr>
            </thead>
            <tbody>
              {recentFailures.length ? (
                recentFailures.map((item) => (
                  <tr key={String(item.case_id || item.finished_at || Math.random())}>
                    <td className="mono">{item.case_id || "-"}</td>
                    <td>{item.case_title || "-"}</td>
                    <td>{item.summary || "-"}</td>
                    <td>{item.risk_level || "-"}</td>
                    <td>{item.failure_source || "-"}</td>
                    <td>{item.defect_count ?? 0}</td>
                    <td>{formatDate(item.finished_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>暂无失败记录。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}
