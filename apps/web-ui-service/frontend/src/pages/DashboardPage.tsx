import { startTransition, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

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

export function DashboardPage() {
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
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setOverview(overviewPayload || {});
          setGovernance(governancePayload || {});
        });
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "仪表盘加载失败");
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

  const risk = overview.risk || {};
  const summary = overview.summary || {};
  const topFlaky = Array.isArray(overview.top_flaky) ? overview.top_flaky : [];
  const pendingIssues = Array.isArray(overview.pending_issues) ? overview.pending_issues : [];
  const governanceSummary = governance.summary || {};
  const highlights = Array.isArray((governance as Record<string, unknown>).highlights)
    ? ((governance as Record<string, unknown>).highlights as Array<Record<string, unknown>>)
    : [];
  const riskLevel = String(risk.level || "低").trim();
  const riskCardClass =
    riskLevel === "高" ? "risk-high" : riskLevel === "中" ? "risk-medium" : "risk-low";
  const updatedAt = formatDateTime(new Date().toISOString());

  return (
    <main className="shell">
      <section className="hero-card dashboard-shell">
        <section className="dashboard-hero">
          <div className="dashboard-hero-copy">
            <p className="breadcrumb">
              <span>首页</span>
              <span className="crumb-sep">/</span>
              <span>仪表盘</span>
            </p>
            <div className="hero-kicker">
              <span className="hero-pill hero-pill-primary">平台概览</span>
              <span className="hero-pill">本周重点</span>
              <span className="hero-pill">待处理事项</span>
            </div>
            <h1>仪表盘</h1>
            <p className="hero-description">聚焦当前风险、执行趋势和待处理事项。</p>
            <div className="hero-metrics">
              <div className="hero-metric">
                <span>数据更新时间</span>
                <strong>{updatedAt}</strong>
              </div>
              <div className="hero-metric">
                <span>当前风险级别</span>
                <strong>{text(risk.level)}</strong>
              </div>
              <div className="hero-metric">
                <span>首页职责</span>
                <strong>总览与提醒</strong>
              </div>
              <div className="hero-metric">
                <span>刷新策略</span>
                <strong>60s 自动刷新</strong>
              </div>
            </div>
          </div>

          <div className="dashboard-hero-side">
            <Link className={`dash-card risk-card ${riskCardClass}`} to="/quality/trends">
              <div className="dash-card-header">
                <div className="card-label-group">
                  <span className="card-eyebrow">平台概览</span>
                  <h2>风险评分</h2>
                </div>
                <span className="level-badge">{riskLevel || "低"}</span>
              </div>
              <div className="dash-metric-line">
                <strong>{numberValue(risk.score)}</strong>
                <span>风险分</span>
              </div>
              <p className="dash-note">{text(risk.summary)}</p>
              <div className="risk-metric-strip">
                <span>
                  <strong>{numberValue(summary.pass_rate_24h)}%</strong>
                  <em>24h 通过率</em>
                </span>
                <span>
                  <strong>{numberValue(summary.execution_count_24h)}</strong>
                  <em>24h 执行</em>
                </span>
                <span>
                  <strong>{numberValue(summary.pending_issues)}</strong>
                  <em>待处理</em>
                </span>
              </div>
              <span className="risk-hint">详细分析请进入趋势分析页</span>
            </Link>
          </div>
        </section>

        <article className="dash-card dashboard-section-card">
          <div className="dash-card-header">
            <div>
              <p className="card-eyebrow">平台概览</p>
              <h2>最近 24 小时执行概况</h2>
            </div>
            <div className="section-link-row">
              <Link className="section-link" to="/execution/results">
                执行结果
              </Link>
              <Link className="section-link" to="/quality/trends">
                趋势分析
              </Link>
            </div>
          </div>
          <section className="dashboard-kpi-grid">
            <article className="dash-card mini-card">
              <h2>最近24小时通过率</h2>
              <strong>{numberValue(summary.pass_rate_24h)}%</strong>
              <p className="dash-note">用于判断当前回归健康度。</p>
            </article>
            <article className="dash-card mini-card">
              <h2>最近24小时执行次数</h2>
              <strong>{numberValue(summary.execution_count_24h)}</strong>
              <p className="dash-note">覆盖自动化与门禁触发任务。</p>
            </article>
            <article className="dash-card mini-card">
              <h2>最近10次门禁拦截</h2>
              <strong>{numberValue((governanceSummary as Record<string, unknown>).gate_intercept_last_10)}</strong>
              <p className="dash-note">用于观察质量门禁压力和阻断密度。</p>
            </article>
            <article className="dash-card mini-card">
              <h2>待确认问题数</h2>
              <strong>{numberValue(summary.pending_issues)}</strong>
              <p className="dash-note">当前需要继续跟进的执行问题。</p>
            </article>
          </section>
          {loading ? <p className="dash-note">正在加载仪表盘...</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
        </article>

        <section className="dashboard-two-col dashboard-focus-grid">
          <article className="dash-card manager-summary-card">
            <div className="dash-card-header">
              <div>
                <p className="card-eyebrow">本周重点</p>
                <h2>管理者摘要</h2>
              </div>
              <div className="section-link-row">
                <Link className="section-link" to="/quality/trends">
                  趋势分析
                </Link>
                <Link className="section-link" to="/quality/flaky">
                  Flaky 分析
                </Link>
                <Link className="section-link" to="/quality/failure-clusters">
                  失败聚类
                </Link>
              </div>
            </div>
            <p className="dash-note">
              治理摘要：高风险任务 {numberValue((governanceSummary as Record<string, unknown>).high_risk_task_count)}，失败聚类{" "}
              {numberValue((governanceSummary as Record<string, unknown>).failure_cluster_count)}。
            </p>
            <ul className="pending-issues-list">
              {highlights.length ? (
                highlights.slice(0, 4).map((item, index) => (
                  <li key={String(item.title || index)}>{text(item.title || item.summary || item.label)}</li>
                ))
              ) : (
                <li>暂无本周重点。</li>
              )}
            </ul>
          </article>
        </section>

        <article className="dash-card dashboard-section-card">
          <div className="dash-card-header">
            <div>
              <p className="card-eyebrow">待处理事项</p>
              <h2>需要落到对应页面继续处理的任务</h2>
            </div>
            <div className="section-link-row">
              <Link className="section-link" to="/execution/runs">
                执行任务
              </Link>
              <Link className="section-link" to="/quality/gates">
                质量门禁
              </Link>
            </div>
          </div>
          <section className="dashboard-two-col dashboard-action-grid">
            <article className="dashboard-subsection">
              <h3>治理行动建议</h3>
              <ul className="pending-issues-list">
                {topFlaky.length ? (
                  topFlaky.slice(0, 5).map((item, index) => (
                    <li key={String(item.case_id || index)}>
                      {text(item.case_id)} · {text(item.name)} · flaky {numberValue(item.flaky_rate)}%
                    </li>
                  ))
                ) : (
                  <li>暂无治理行动建议。</li>
                )}
              </ul>
            </article>
            <article className="dashboard-subsection">
              <h3>待确认问题</h3>
              <ul className="pending-issues-list">
                {pendingIssues.length ? (
                  pendingIssues.slice(0, 6).map((item, index) => (
                    <li key={String(item.issue_key || index)}>
                      {text(item.issue_key)} · {text(item.title)} · {text(item.status)}
                    </li>
                  ))
                ) : (
                  <li>暂无待确认问题。</li>
                )}
              </ul>
            </article>
          </section>
        </article>
      </section>
    </main>
  );
}
