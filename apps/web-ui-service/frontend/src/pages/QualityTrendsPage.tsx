import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getDashboardGovernance, getDashboardOverview, type DashboardGovernanceResponse, type DashboardOverviewResponse } from "../api/governance";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function numberValue(value: unknown): string {
  if (typeof value === "number") {
    return String(value);
  }
  const normalized = String(value || "").trim();
  return normalized || "0";
}

export function QualityTrendsPage() {
  const [overview, setOverview] = useState<DashboardOverviewResponse>({});
  const [governance, setGovernance] = useState<DashboardGovernanceResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const [overviewPayload, governancePayload] = await Promise.all([
          getDashboardOverview(),
          getDashboardGovernance(),
        ]);
        if (!cancelled) {
          setOverview(overviewPayload || {});
          setGovernance(governancePayload || {});
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "趋势分析加载失败");
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

  const trend24h = Array.isArray(overview.trend_24h) ? overview.trend_24h : [];
  const govTrend = Array.isArray(governance.governance_trend?.items) ? governance.governance_trend?.items : [];
  const summary7d = governance.governance_trend?.summary_7d || {};

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>趋势分析（React + TypeScript）</h1>
          <p className="muted">观察 24h 执行走势与治理趋势。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/quality/flaky">
            Flaky 分析
          </Link>
          <Link className="button" to="/quality/failure-clusters">
            失败聚类
          </Link>
        </div>
      </header>

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">方向</span>
          <strong>{text((summary7d as Record<string, unknown>).direction)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">阻断总数(7d)</span>
          <strong>{numberValue((summary7d as Record<string, unknown>).blocked_total)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">人工复核(7d)</span>
          <strong>{numberValue((summary7d as Record<string, unknown>).manual_review_total)}</strong>
        </article>
      </section>

      <section className="panel table-panel">
        <div className="table-head">
          <strong>24h 执行趋势</strong>
        </div>
        {loading ? <p>正在加载趋势...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
          <table>
            <thead>
              <tr>
                <th>时间桶</th>
                <th>执行数</th>
                <th>通过率</th>
                <th>失败数</th>
              </tr>
            </thead>
            <tbody>
              {trend24h.length ? (
                trend24h.map((item, index) => (
                  <tr key={String(item.bucket || item.ts || index)}>
                    <td>{text(item.bucket || item.ts || item.hour)}</td>
                    <td>{numberValue(item.execution_count)}</td>
                    <td>{numberValue(item.pass_rate)}%</td>
                    <td>{numberValue(item.failed_count)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4}>暂无 24h 趋势数据。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="panel table-panel">
        <div className="table-head">
          <strong>治理趋势</strong>
        </div>
        {!loading && !errorText ? (
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>高风险任务</th>
                <th>门禁阻断</th>
                <th>人工复核</th>
              </tr>
            </thead>
            <tbody>
              {govTrend.length ? (
                govTrend.map((item, index) => (
                  <tr key={String(item.day || index)}>
                    <td>{text(item.day || item.date)}</td>
                    <td>{numberValue(item.high_risk_task_count)}</td>
                    <td>{numberValue(item.blocked_events)}</td>
                    <td>{numberValue(item.manual_review_count)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4}>暂无治理趋势数据。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}
