import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MetricCards } from "../components/MetricCards";
import { getQualitySummary, getQualityRanking, getQualityIssues, type QualitySummaryResponse, type QualityRankingItem, type QualityIssuesResponse } from "../api/quality";
import { DEFAULT_PROJECT_CODE } from "../config/projects";

const DECISION_LABELS: Record<string, string> = { PASS: "通过", REVIEW: "需审核", REJECT: "不可执行", UNKNOWN: "未知" };
const DECISION_TONES: Record<string, "good" | "warn" | "bad"> = { PASS: "good", REVIEW: "warn", REJECT: "bad", UNKNOWN: "warn" };
const ISSUE_LABELS: Record<string, string> = {
  zero_assertion_count: "零断言",
  candidate_step_count: "占位步骤",
  unprocessed_count: "未结构化",
  quality_warning_count: "质量警告",
  data_warning_count: "数据补充",
};

export function QualityDashboardPage() {
  const [summary, setSummary] = useState<QualitySummaryResponse | null>(null);
  const [ranking, setRanking] = useState<QualityRankingItem[]>([]);
  const [issues, setIssues] = useState<QualityIssuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErrorText("");
      try {
        const [s, r, i] = await Promise.all([
          getQualitySummary(DEFAULT_PROJECT_CODE),
          getQualityRanking(DEFAULT_PROJECT_CODE, 10),
          getQualityIssues(DEFAULT_PROJECT_CODE),
        ]);
        if (!cancelled) { setSummary(s); setRanking(r); setIssues(i); }
      } catch (e) {
        if (!cancelled) setErrorText(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  if (loading) return <main className="shell"><section className="panel">加载中...</section></main>;
  if (errorText) return <main className="shell"><section className="panel error">{errorText}</section></main>;

  return (
    <main className="shell">
      <header className="panel unified-topbar">
        <div>
          <h1>质量仪表盘</h1>
          <p className="muted">Snapshot 数据 · 实时质量趋势</p>
        </div>
      </header>

      {summary ? (
        <>
          {/* ── 概览指标 ── */}
          <MetricCards
            items={[
              { label: "资产总数", value: summary.asset_count },
              { label: "平均评分", value: `${summary.avg_score}/100` },
              ...Object.entries(summary.decision_summary)
                .filter(([, c]) => c > 0)
                .map(([d, c]) => ({
                  label: DECISION_LABELS[d] || d,
                  value: c,
                  tone: DECISION_TONES[d] || "warn" as const,
                  hint: d,
                })),
            ]}
          />

          {/* ── 问题分布 ── */}
          {issues ? (
            <section className="panel">
              <h2>问题分布</h2>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 20px" }}>
                {Object.entries(issues.issue_summary)
                  .filter(([, c]) => c > 0)
                  .map(([k, c]) => (
                    <span key={k}>
                      {ISSUE_LABELS[k] || k}: <strong>{c}</strong>
                    </span>
                  ))}
              </div>
            </section>
          ) : null}

          {/* ── 最低分资产 ── */}
          {ranking.length > 0 ? (
            <section className="panel">
              <h2>最低质量资产</h2>
              <table>
                <thead>
                  <tr>
                    <th>资产 ID</th>
                    <th>评分</th>
                    <th>状态</th>
                    <th>版本</th>
                    <th>更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.slice(0, 10).map((item) => (
                    <tr key={item.asset_id}>
                      <td>
                        <Link to={`/quality/assets/${encodeURIComponent(item.asset_id)}`}>
                          {item.asset_id}
                        </Link>
                      </td>
                      <td>{item.score}</td>
                      <td>{DECISION_LABELS[item.decision] || item.decision}</td>
                      <td>{item.version}</td>
                      <td>{item.updated_at?.slice(0, 19) || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
