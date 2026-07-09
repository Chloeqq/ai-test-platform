import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MetricCards } from "../components/MetricCards";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import {
  listEvalRuns,
  listEvalDatasets,
  createEvalRun,
  executeEvalRun,
  type EvalRunItem,
  type EvalDatasetItem,
} from "../api/qualityEval";
import { DEFAULT_PROJECT_CODE } from "../config/projects";
import { DIMENSION_LABELS, STATUS_LABELS } from "../constants/evaluation";

export function QualityEvalDashboardPage() {
  const [runs, setRuns] = useState<EvalRunItem[]>([]);
  const [datasets, setDatasets] = useState<EvalDatasetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newRunDataset, setNewRunDataset] = useState("");
  const [newRunModel, setNewRunModel] = useState("qwen3.5");
  const [submitting, setSubmitting] = useState(false);

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const [runList, dsList] = await Promise.all([
        listEvalRuns(DEFAULT_PROJECT_CODE),
        listEvalDatasets(DEFAULT_PROJECT_CODE),
      ]);
      setRuns(runList);
      setDatasets(dsList);
      if (dsList.length > 0 && !newRunDataset) {
        setNewRunDataset(dsList[0].dataset_id);
      }
    } catch (e) {
      setErrorText(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreateRun() {
    if (!newRunDataset) return;
    setSubmitting(true);
    try {
      const ds = datasets.find((d) => d.dataset_id === newRunDataset);
      const run = await createEvalRun({
        dataset_id: newRunDataset,
        project_code: DEFAULT_PROJECT_CODE,
        llm_model: newRunModel,
        task_type: ds?.task_type || "test_case_generation",
        eval_dimensions: ds?.eval_dimensions || [],
      });
      await executeEvalRun(run.run_id);
      setShowCreate(false);
      await reload();
    } catch (e) {
      setErrorText(e instanceof Error ? e.message : "创建评测失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main className="shell"><section className="panel">加载中...</section></main>;
  if (errorText) return <main className="shell"><section className="panel error">{errorText}</section></main>;

  const completedRuns = runs.filter((r) => r.status === "completed");
  const avgScore = completedRuns.length > 0
    ? Math.round(completedRuns.reduce((s, r) => s + r.overall_score, 0) / completedRuns.length)
    : 0;

  return (
    <main className="shell">
      <header className="panel unified-topbar">
        <div>
          <h1>AI 测试质量评估中心</h1>
          <p className="muted">度量 AI 生成测试资产的质量 — Coverage · Assertion · Executability</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button" onClick={() => setShowCreate(true)} disabled={datasets.length === 0}>
            新建评测
          </button>
        </div>
      </header>

      <MetricCards
        items={[
          { label: "评测运行", value: runs.length },
          { label: "数据集", value: datasets.length },
          { label: "综合均分", value: avgScore > 0 ? `${avgScore}/100` : "-" },
          { label: "幻觉率", value: completedRuns.length > 0
            ? `${Math.round(completedRuns.reduce((s, r) => s + r.hallucination_risk, 0) / completedRuns.length)}%`
            : "-"
          },
        ]}
      />

      {/* 新建评测对话框 */}
      {showCreate && (
        <section className="panel">
          <h2>新建评测运行</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 400 }}>
            <label>
              数据集：
              <select value={newRunDataset} onChange={(e) => setNewRunDataset(e.target.value)}>
                {datasets.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>{d.name}</option>
                ))}
              </select>
            </label>
            <label>
              LLM 模型：
              <select value={newRunModel} onChange={(e) => setNewRunModel(e.target.value)}>
                <option value="qwen3.5">qwen3.5</option>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="gpt-4o">gpt-4o</option>
              </select>
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="button" onClick={handleCreateRun} disabled={submitting}>
                {submitting ? "执行中..." : "创建并执行"}
              </button>
              <button className="button" onClick={() => setShowCreate(false)}>取消</button>
            </div>
          </div>
        </section>
      )}

      {/* 评测运行历史 */}
      <section className="panel">
        <h2>评测运行历史</h2>
        {runs.length === 0 ? (
          <EmptyState message="暂无评测运行，请先创建数据集并新建评测" />
        ) : (
          <DataTable
            columns={[
              { key: "run_id", label: "运行 ID", render: (_: unknown, row: Record<string, unknown>) => (
                <Link to={`/quality/eval/${row.run_id}`}>{(row.run_id as string).slice(0, 20)}...</Link>
              )},
              { key: "dataset_id", label: "数据集" },
              { key: "llm_model", label: "模型" },
              { key: "eval_dimensions", label: "维度", render: (_: unknown, row: Record<string, unknown>) => {
                const dims = (row.eval_dimensions as string[]) || [];
                return dims.map((d) => DIMENSION_LABELS[d] || d).join(" · ");
              }},
              { key: "overall_score", label: "综合评分", render: (_: unknown, row: Record<string, unknown>) => (
                <strong>{row.overall_score as number}/100</strong>
              )},
              { key: "status", label: "状态", render: (_: unknown, row: Record<string, unknown>) => (
                STATUS_LABELS[row.status as string] || row.status
              )},
              { key: "created_at", label: "创建时间" },
            ]}
            rows={runs.map((r) => ({ ...r, id: r.run_id }))}
          />
        )}
      </section>
    </main>
  );
}