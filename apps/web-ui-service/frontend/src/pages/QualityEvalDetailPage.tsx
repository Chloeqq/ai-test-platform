import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { MetricCards } from "../components/MetricCards";
import {
  getEvalRun,
  getEvalRunReport,
  getEvalRunResults,
  type EvalRunItem,
  type EvalRunReport,
  type EvalResultItem,
} from "../api/qualityEval";
import { DIMENSION_LABELS } from "../constants/evaluation";

type Tab = "overview" | "results" | "hallucination";

export function QualityEvalDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<EvalRunItem | null>(null);
  const [report, setReport] = useState<EvalRunReport | null>(null);
  const [results, setResults] = useState<EvalResultItem[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErrorText("");
      try {
        const [r, rpt, res] = await Promise.all([
          getEvalRun(runId!),
          getEvalRunReport(runId!).catch(() => null),
          getEvalRunResults(runId!),
        ]);
        if (!cancelled) {
          setRun(r);
          setReport(rpt);
          setResults(res);
        }
      } catch (e) {
        if (!cancelled) setErrorText(e instanceof Error ? e.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [runId]);

  if (loading) return <main className="shell"><section className="panel">加载中...</section></main>;
  if (errorText) return <main className="shell"><section className="panel error">{errorText}</section></main>;
  if (!run) return <main className="shell"><section className="panel">评测运行不存在</section></main>;

  const dimensions = run.eval_dimensions || [];
  const dimScores = report?.dimension_scores || {};

  return (
    <main className="shell">
      <header className="panel unified-topbar">
        <div>
          <h1>评测详情</h1>
          <p className="muted">{report?.dataset_name || run.dataset_id} · {run.llm_model || "未知模型"} · {run.status}</p>
        </div>
      </header>

      {/* 概览指标 */}
      <MetricCards
        items={[
          { label: "综合评分", value: `${run.overall_score}/100` },
          ...dimensions.map((d) => ({
            label: DIMENSION_LABELS[d] || d,
            value: dimScores[d] !== undefined ? `${dimScores[d]}` : "-",
          })),
        ]}
      />

      {/* 与上次运行对比 */}
      {report?.compared_to_previous && (
        <section className="panel">
          <h2>版本对比</h2>
          <p>
            上次运行（{report.compared_to_previous.previous_run_id as string}）评分：
            {report.compared_to_previous.previous_overall_score as number}/100
            {"  "}→{"  "}
            <strong style={{ color: (report.compared_to_previous.delta as string).startsWith("+") ? "#16a34a" : "#dc2626" }}>
              {report.compared_to_previous.delta as string}
            </strong>
          </p>
        </section>
      )}

      {/* Tabs */}
      <section className="panel">
        <nav style={{ display: "flex", gap: 16, marginBottom: 16, borderBottom: "1px solid #e5e7eb", paddingBottom: 8 }}>
          {(["overview", "results", "hallucination"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                fontWeight: tab === t ? 700 : 400,
                color: tab === t ? "#1a56db" : "#666",
                border: "none",
                background: "none",
                cursor: "pointer",
                fontSize: 14,
                padding: "4px 0",
                borderBottom: tab === t ? "2px solid #1a56db" : "2px solid transparent",
              }}
            >
              {{ overview: "评分概览", results: "逐条结果", hallucination: "幻觉分析" }[t]}
            </button>
          ))}
        </nav>

        {/* Tab: 概览 */}
        {tab === "overview" && (
          <div>
            {/* 维度评分条形图 */}
            <h3>维度评分</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 500 }}>
              {dimensions.map((d) => {
                const score = dimScores[d] || 0;
                return (
                  <div key={d} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 80, fontSize: 13 }}>{DIMENSION_LABELS[d] || d}</span>
                    <div style={{ flex: 1, height: 16, background: "#f3f4f6", borderRadius: 4, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${score}%`,
                          height: "100%",
                          background: score >= 80 ? "#16a34a" : score >= 60 ? "#f59e0b" : "#dc2626",
                          borderRadius: 4,
                          transition: "width 0.3s",
                        }}
                      />
                    </div>
                    <span style={{ width: 40, fontSize: 13, fontWeight: 600 }}>{score}</span>
                  </div>
                );
              })}
            </div>

            {/* 问题分布 */}
            {report?.issue_breakdown && Object.keys(report.issue_breakdown).length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3>问题分布</h3>
                <DataTable
                  columns={[
                    { key: "issue", label: "问题类型" },
                    { key: "count", label: "数量" },
                  ]}
                  rows={Object.entries(report.issue_breakdown).map(([k, v]) => ({
                    id: k,
                    issue: k,
                    count: v,
                  }))}
                />
              </div>
            )}

            {/* 最差条目 */}
            {report?.worst_items && report.worst_items.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3>最差条目 Top 5</h3>
                <DataTable
                  columns={[
                    { key: "item_id", label: "条目 ID" },
                    { key: "score", label: "评分" },
                  ]}
                  rows={report.worst_items.map((w) => ({
                    id: w.result_id as string,
                    item_id: w.item_id,
                    score: `${w.score}/100`,
                  }))}
                />
              </div>
            )}
          </div>
        )}

        {/* Tab: 逐条结果 */}
        {tab === "results" && (
          <DataTable
            columns={[
              { key: "item_id", label: "条目" },
              { key: "requirement_text", label: "需求文本", render: (_: unknown, row: Record<string, unknown>) => (
                <span title={row.requirement_text as string}>{(row.requirement_text as string).slice(0, 50)}...</span>
              )},
              { key: "coverage_score", label: "覆盖率" },
              { key: "assertion_score", label: "断言" },
              { key: "executability_score", label: "可执行" },
              { key: "weighted_score", label: "加权分", render: (_: unknown, row: Record<string, unknown>) => (
                <strong>{row.weighted_score as number}/100</strong>
              )},
            ]}
            rows={results.map((r) => ({ ...r, id: r.result_id }))}
          />
        )}

        {/* Tab: 幻觉分析 */}
        {tab === "hallucination" && (
          <div>
            <h3>幻觉标记明细</h3>
            {results.filter((r) => (r.hallucination_flags || []).length > 0).length === 0 ? (
              <p className="muted">未检测到幻觉问题</p>
            ) : (
              <DataTable
                columns={[
                  { key: "item_id", label: "条目" },
                  { key: "requirement_text", label: "需求", render: (_: unknown, row: Record<string, unknown>) => (
                    <span>{(row.requirement_text as string).slice(0, 40)}...</span>
                  )},
                  { key: "flags", label: "幻觉标记", render: (_: unknown, row: Record<string, unknown>) => {
                    const flags = (row.hallucination_flags as string[]) || [];
                    return (
                      <span style={{ color: flags.length > 0 ? "#dc2626" : "#16a34a" }}>
                        {flags.length > 0 ? flags.join(" · ") : "无幻觉"}
                      </span>
                    );
                  }},
                  { key: "hallucination_score", label: "评分" },
                ]}
                rows={results
                  .filter((r) => (r.hallucination_flags || []).length > 0)
                  .map((r) => ({ ...r, id: r.result_id, flags: r.hallucination_flags }))}
              />
            )}
          </div>
        )}
      </section>
    </main>
  );
}