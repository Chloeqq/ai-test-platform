import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import {
  approveExecutionGateDecision,
  getExecutionGateConfig,
  getQualityGateSummary,
  revokeExecutionGateDecision,
  saveExecutionGateDecision,
} from "../api/governance";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { listProjects, listWorkbenchHistory, type WorkbenchHistoryItem } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

interface GateForm {
  project: string;
  run_id: string;
  page: string;
  case_id: string;
  decision: string;
  note: string;
}

const DEFAULT_FORM: GateForm = {
  project: DEFAULT_PROJECT_CODE,
  run_id: "",
  page: "",
  case_id: "",
  decision: "manual_review",
  note: "",
};

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

export function QualityGatesPage() {
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [qualitySummary, setQualitySummary] = useState<Record<string, unknown>>({});
  const [historyItems, setHistoryItems] = useState<WorkbenchHistoryItem[]>([]);
  const [form, setForm] = useState<GateForm>(DEFAULT_FORM);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const [configPayload, summaryPayload, historyPayload] = await Promise.all([
        getExecutionGateConfig(),
        getQualityGateSummary(200),
        listWorkbenchHistory({ limit: 120, sort: "timestamp_desc" }),
      ]);
      const rows = (Array.isArray(historyPayload.items) ? historyPayload.items : []).filter((item) =>
        String(item.action || "").startsWith("execution_gate_"),
      );
      setConfig(configPayload || {});
      setQualitySummary((summaryPayload.item || {}) as Record<string, unknown>);
      setHistoryItems(rows);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "质量门禁加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadProjectOptions() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          setProjectCodes(projectOptions(projects.codes));
        }
      } catch {
        // Keep default option.
      }
    }
    void loadProjectOptions();
    void reload();
    return () => {
      cancelled = true;
    };
  }, []);

  const summary24h = (qualitySummary.summary_24h as Record<string, unknown>) || {};

  async function runAction(action: "save" | "approve" | "revoke") {
    if (submitting) {
      return;
    }
    if (!form.run_id.trim() || !form.page.trim()) {
      setFeedback("run_id 和 page 为必填。");
      return;
    }
    setSubmitting(true);
    setFeedback("正在提交...");
    try {
      if (action === "save") {
        await saveExecutionGateDecision({
          project: normalizeProjectCode(form.project),
          run_id: form.run_id.trim(),
          page: form.page.trim(),
          case_id: form.case_id.trim(),
          decision: form.decision.trim() || "manual_review",
          note: form.note.trim(),
        });
      } else if (action === "approve") {
        await approveExecutionGateDecision({
          project: normalizeProjectCode(form.project),
          run_id: form.run_id.trim(),
          page: form.page.trim(),
          note: form.note.trim(),
        });
      } else {
        await revokeExecutionGateDecision({
          project: normalizeProjectCode(form.project),
          run_id: form.run_id.trim(),
          page: form.page.trim(),
          note: form.note.trim(),
        });
      }
      setFeedback(`已完成：${action}`);
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>质量门禁</h1>
          <p className="muted">统一查看门禁配置、阻断统计和审批历史。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/quality/trends">
            趋势分析
          </Link>
          <Link className="button" to="/execution/results/failures">
            失败详情
          </Link>
        </div>
      </header>

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">阈值</span>
          <strong>{numberValue(config.block_missing_required_threshold)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">24h 阻断</span>
          <strong>{numberValue(summary24h.blocked_events)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">24h 阻断率</span>
          <strong>{numberValue(summary24h.block_rate)}%</strong>
        </article>
        <article className="stat-card">
          <span className="label">Top 告警码</span>
          <strong>{text(summary24h.top_alert_code)}</strong>
        </article>
      </section>

      <section className="panel form-grid">
        <label>
          项目
          <select value={form.project} onChange={(event) => setForm((prev) => ({ ...prev, project: normalizeProjectCode(event.target.value) }))}>
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label>
          Run ID
          <input value={form.run_id} onChange={(event) => setForm((prev) => ({ ...prev, run_id: event.target.value }))} />
        </label>
        <label>
          Page
          <input value={form.page} onChange={(event) => setForm((prev) => ({ ...prev, page: event.target.value }))} />
        </label>
        <label>
          Case ID
          <input value={form.case_id} onChange={(event) => setForm((prev) => ({ ...prev, case_id: event.target.value }))} />
        </label>
        <label>
          Decision
          <select value={form.decision} onChange={(event) => setForm((prev) => ({ ...prev, decision: event.target.value }))}>
            <option value="manual_review">manual_review</option>
            <option value="allow">allow</option>
            <option value="block">block</option>
          </select>
        </label>
        <label className="span-3">
          Note
          <input value={form.note} onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))} />
        </label>
      </section>

      <section className="panel header-actions">
        <button type="button" className="button secondary" onClick={() => void runAction("save")} disabled={submitting}>
          保存决策
        </button>
        <button type="button" className="button" onClick={() => void runAction("approve")} disabled={submitting}>
          审批通过
        </button>
        <button type="button" className="button secondary" onClick={() => void runAction("revoke")} disabled={submitting}>
          撤销审批
        </button>
      </section>

      <section className="panel">
        {loading ? <p>正在加载门禁数据...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {feedback ? <p>{feedback}</p> : null}
      </section>

      <DataTable title="门禁历史" loading={loading} loadingText="正在加载门禁历史..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>Run ID</th>
                <th>Page</th>
                <th>状态</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              {historyItems.length ? (
                historyItems.map((item, index) => (
                  <tr key={String(item.timestamp || item.run_id || index)}>
                    <td>{formatDateTime(item.timestamp)}</td>
                    <td>{text(item.action)}</td>
                    <td className="mono">{text(item.run_id)}</td>
                    <td>{text(item.page)}</td>
                    <td>{text(item.status)}</td>
                    <td>{text(item.detail_summary)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="暂无门禁历史" description="当执行门禁被保存、审批或撤销时，会在这里记录审计轨迹。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
