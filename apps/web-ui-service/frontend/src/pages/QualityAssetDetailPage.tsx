import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { MetricCards } from "../components/MetricCards";
import { getQualityTimeline, type QualityTimelineItem } from "../api/quality";
import { DEFAULT_PROJECT_CODE } from "../config/projects";

const DECISION_LABELS: Record<string, string> = { PASS: "通过", REVIEW: "需审核", REJECT: "不可执行" };
const DECISION_TONES: Record<string, "good" | "warn" | "bad"> = { PASS: "good", REVIEW: "warn", REJECT: "bad" };

export function QualityAssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const [timeline, setTimeline] = useState<QualityTimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!assetId) return;
      setLoading(true);
      setErrorText("");
      try {
        const data = await getQualityTimeline(assetId, DEFAULT_PROJECT_CODE);
        if (!cancelled) setTimeline(data);
      } catch (e) {
        if (!cancelled) setErrorText(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [assetId]);

  if (loading) return <main className="shell"><section className="panel">加载中...</section></main>;
  if (errorText) return <main className="shell"><section className="panel error">{errorText}</section></main>;

  const latest = timeline.length > 0 ? timeline[timeline.length - 1] : null;

  return (
    <main className="shell">
      <header className="panel unified-topbar">
        <div>
          <h1>{assetId}</h1>
          <p className="muted">质量趋势</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/quality/dashboard">返回仪表盘</Link>
          <Link className="button secondary" to={`/react/assets/test-points/${encodeURIComponent(assetId || "")}?project=${DEFAULT_PROJECT_CODE}`}>
            查看资产详情
          </Link>
        </div>
      </header>

      {latest ? (
        <MetricCards
          items={[
            { label: "当前评分", value: `${latest.score}/100` },
            { label: "状态", value: DECISION_LABELS[latest.decision] || latest.decision, tone: DECISION_TONES[latest.decision] || "warn" },
            { label: "版本", value: `v${latest.version}` },
            { label: "更新时间", value: latest.at?.slice(0, 19) || "-" },
          ]}
        />
      ) : timeline.length === 0 ? (
        <section className="panel">
          <h2>暂无质量数据</h2>
          <p className="muted">该资产尚未生成 Quality Snapshot。请先保存资产以触发质量快照。</p>
        </section>
      ) : null}

      {/* ── Timeline ── */}
      {timeline.length > 0 ? (
        <section className="panel">
          <h2>评分趋势</h2>
          <table>
            <thead>
              <tr>
                <th>版本</th>
                <th>评分</th>
                <th>变化</th>
                <th>状态</th>
                <th>零断言</th>
                <th>未结构化</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((item) => (
                <tr key={item.version}>
                  <td>v{item.version}</td>
                  <td><strong>{item.score}</strong></td>
                  <td>
                    {item.delta_score > 0 ? <span style={{ color: "var(--color-success, green)" }}>↑ +{item.delta_score}</span>
                      : item.delta_score < 0 ? <span style={{ color: "var(--color-danger, red)" }}>↓ {item.delta_score}</span>
                      : "—"}
                  </td>
                  <td>{DECISION_LABELS[item.decision] || item.decision}</td>
                  <td>{item.zero_assertion_count}</td>
                  <td>{item.unprocessed_count}</td>
                  <td>{item.at?.slice(0, 19) || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {/* ── Issue Trend ── */}
      {timeline.length > 0 ? (
        <section className="panel">
          <h2>问题趋势</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "12px 40px" }}>
            {timeline.map((item) => (
              <div key={item.version} style={{ minWidth: 120 }}>
                <small className="muted">v{item.version}</small>
                <div>零断言: <strong>{item.zero_assertion_count}</strong></div>
                <div>未结构化: <strong>{item.unprocessed_count}</strong></div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
