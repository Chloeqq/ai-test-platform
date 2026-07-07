import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { addDefect, listDefects } from "../api/governance";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";

interface DefectForm {
  case_id: string;
  defect_id: string;
  defect_url: string;
  system: string;
  note: string;
}

const DEFAULT_FORM: DefectForm = {
  case_id: "",
  defect_id: "",
  defect_url: "",
  system: "manual",
  note: "",
};

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

export function DefectsPage() {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [caseFilter, setCaseFilter] = useState<string>("");
  const [form, setForm] = useState<DefectForm>(DEFAULT_FORM);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");

  async function reload(caseId = caseFilter) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listDefects(caseId);
      setItems(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "缺陷列表加载失败");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitForm() {
    if (submitting) {
      return;
    }
    if (!form.case_id.trim() || !form.defect_id.trim()) {
      setFeedback("case_id 与 defect_id 为必填。");
      return;
    }
    setSubmitting(true);
    setFeedback("正在提交...");
    try {
      await addDefect({
        case_id: form.case_id.trim(),
        defect_id: form.defect_id.trim(),
        defect_url: form.defect_url.trim(),
        system: form.system.trim() || "manual",
        note: form.note.trim(),
      });
      setFeedback(`已新增关联：${form.defect_id.trim()}`);
      setForm(DEFAULT_FORM);
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "新增关联失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>缺陷管理</h1>
          <p className="muted">统一管理缺陷关联与执行结果闭环。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/execution/results/failures">
            失败详情
          </Link>
          <Link className="button" to="/quality/failure-clusters">
            失败聚类
          </Link>
        </div>
      </header>

      <FilterBar>
        <label>
          按 case_id 查询
          <input value={caseFilter} onChange={(event) => setCaseFilter(event.target.value)} placeholder="例如 atp-web-login-fn-ai-0001" />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload(caseFilter)}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setCaseFilter("");
              void reload("");
            }}
          >
            重置
          </button>
        </div>
      </FilterBar>

      <section className="panel form-grid">
        <label>
          case_id
          <input value={form.case_id} onChange={(event) => setForm((prev) => ({ ...prev, case_id: event.target.value }))} />
        </label>
        <label>
          defect_id
          <input value={form.defect_id} onChange={(event) => setForm((prev) => ({ ...prev, defect_id: event.target.value }))} />
        </label>
        <label>
          system
          <input value={form.system} onChange={(event) => setForm((prev) => ({ ...prev, system: event.target.value }))} />
        </label>
        <label className="span-2">
          defect_url
          <input value={form.defect_url} onChange={(event) => setForm((prev) => ({ ...prev, defect_url: event.target.value }))} />
        </label>
        <label className="span-3">
          note
          <input value={form.note} onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))} />
        </label>
      </section>

      <section className="panel header-actions">
        <button type="button" className="button" onClick={() => void submitForm()} disabled={submitting}>
          新增关联
        </button>
        {feedback ? <span>{feedback}</span> : null}
      </section>

      <DataTable title={`缺陷记录：${items.length}`} loading={loading} loadingText="正在加载缺陷列表..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Defect ID</th>
                <th>System</th>
                <th>URL</th>
                <th>Note</th>
                <th>Linked At</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item, index) => (
                  <tr key={String(item.defect_id || index)}>
                    <td className="mono">{text(item.case_id)}</td>
                    <td className="mono">{text(item.defect_id)}</td>
                    <td>{text(item.system)}</td>
                    <td>{text(item.defect_url)}</td>
                    <td>{text(item.note)}</td>
                    <td>{formatDateTime(item.linked_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="暂无缺陷记录" description="可以在上方为失败用例新增缺陷关联，便于后续质量追踪。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
