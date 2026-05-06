import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { batchUpdateTestCaseStatus, listTestCasesDb, type TestCasesDbListResponse } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function caseIdOf(item: Record<string, unknown>): string {
  return String(item.case_id || "").trim();
}

export function CasesReviewPage() {
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [pagination, setPagination] = useState<TestCasesDbListResponse["pagination"]>({});
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetPage = 1, targetProject = project, targetKeyword = keyword, targetStatus = status) {
    setLoading(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await listTestCasesDb({
        project_code: targetProject || "",
        q: targetKeyword.trim(),
        status: targetStatus.trim(),
        sort_field: "updated_at",
        sort_order: "desc",
        page: targetPage,
        page_size: 20,
      });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      setPagination(payload.pagination || {});
      const allowed = new Set(rows.map((item) => caseIdOf(item)).filter(Boolean));
      setSelectedCaseIds((prev) => prev.filter((id) => allowed.has(id)));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "待审核用例加载失败");
      setItems([]);
      setPagination({});
      setSelectedCaseIds([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          setProjectCodes(projectOptions(projects.codes));
        }
      } catch {
        // Ignore; page can still work with manual project input.
      }
      if (!cancelled) {
        await reload(1);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const allVisibleCaseIds = useMemo(() => items.map((item) => caseIdOf(item)).filter(Boolean), [items]);
  const selectedCount = selectedCaseIds.length;
  const allSelected = allVisibleCaseIds.length > 0 && selectedCount === allVisibleCaseIds.length;
  const pendingCount = items.filter((item) => {
    const lifecycle = String(item.lifecycle_status || item.status || "").toLowerCase();
    return lifecycle.includes("review") || lifecycle.includes("draft") || lifecycle.includes("pending");
  }).length;
  const highPriorityCount = items.filter((item) => String(item.priority || "").toUpperCase().includes("P0")).length;
  const failedCount = items.filter((item) => {
    const result = String(item.last_execution_result || item.last_result || "").toLowerCase();
    return result.includes("fail") || result.includes("失败");
  }).length;

  function toggleItem(caseId: string) {
    const normalized = String(caseId || "").trim();
    if (!normalized) {
      return;
    }
    setSelectedCaseIds((prev) => (prev.includes(normalized) ? prev.filter((item) => item !== normalized) : [...prev, normalized]));
  }

  function toggleAll() {
    setSelectedCaseIds((prev) => (allSelected ? prev.filter((id) => !allVisibleCaseIds.includes(id)) : [...new Set([...prev, ...allVisibleCaseIds])]));
  }

  async function applyStatus(nextStatus: string) {
    if (!selectedCaseIds.length || saving) {
      return;
    }
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await batchUpdateTestCaseStatus({
        case_ids: selectedCaseIds,
        status: nextStatus,
      });
      setFeedback(`已更新 ${Number(payload.updated_count || 0)} 条用例状态为 ${nextStatus}`);
      await reload(Number(pagination?.page || 1));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量审核更新失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>待审核用例</h1>
            <p className="muted">统一处理待审核用例、批量状态变更与版本入口。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to="/cases">
              用例总览
            </Link>
            <Link className="button secondary" to="/cases/tags">
              标签治理
            </Link>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card">
            <span>当前列表</span>
            <strong>{items.length}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>待审核</span>
            <strong>{pendingCount}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>P0 高优先级</span>
            <strong>{highPriorityCount}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>最近失败</span>
            <strong>{failedCount}</strong>
          </article>
        </section>

        <section className="asset-toolbar">
          <label>
            项目
            <select value={project} onChange={(event) => setProject(normalizeProjectCode(event.target.value))}>
              {projectCodes.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>
          <label className="grow">
            关键词
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="case_id / 名称 / 模块 / 页面" />
          </label>
          <label>
            状态
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">全部状态</option>
              <option value="draft">draft</option>
              <option value="review">review</option>
              <option value="active">active</option>
              <option value="blocked">blocked</option>
              <option value="deprecated">deprecated</option>
            </select>
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reload(1)}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setKeyword("");
                setStatus("");
                setSelectedCaseIds([]);
                void reload(1, DEFAULT_PROJECT_CODE, "", "");
              }}
            >
              重置全部
            </button>
          </div>
        </section>

        <section className="asset-toolbar">
          <p className="muted">已选 {selectedCount} 条用例</p>
          <div className="asset-actions">
            <button type="button" className="button secondary" onClick={() => void applyStatus("review")} disabled={!selectedCount || saving}>
              标记为 review
            </button>
            <button type="button" className="button secondary" onClick={() => void applyStatus("active")} disabled={!selectedCount || saving}>
              标记为 active
            </button>
            <button type="button" className="button secondary" onClick={() => void applyStatus("blocked")} disabled={!selectedCount || saving}>
              标记为 blocked
            </button>
          </div>
        </section>
        <p className="asset-hint">提示：先筛选再批量审核更稳妥；若失败请根据上方错误信息调整筛选或重试。</p>

        <section className="asset-table-wrap">
          {loading ? <p>正在加载待审核用例...</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
          {feedback ? <p>{feedback}</p> : null}
          {!loading && !errorText ? (
            <table>
              <thead>
                <tr>
                  <th>
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                  </th>
                  <th>Case ID</th>
                  <th>名称</th>
                  <th>优先级</th>
                  <th>状态</th>
                  <th>最近结果</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.length ? (
                  items.map((item, index) => {
                    const caseId = caseIdOf(item);
                    return (
                      <tr key={caseId || String(index)}>
                        <td>
                          <input type="checkbox" checked={selectedCaseIds.includes(caseId)} onChange={() => toggleItem(caseId)} />
                        </td>
                        <td className="mono">{text(caseId)}</td>
                        <td>{text(item.case_title || item.name)}</td>
                        <td>{text(item.priority)}</td>
                        <td>{text(item.lifecycle_status || item.status)}</td>
                        <td>{text(item.last_execution_result || item.last_result)}</td>
                        <td>{formatDateTime(item.updated_at)}</td>
                        <td>
                          <div className="asset-actions-inline">
                            <Link to={`/cases/${encodeURIComponent(caseId)}`}>详情</Link>
                            <Link to={`/cases/versions?case_id=${encodeURIComponent(caseId)}`}>版本</Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={8} className="asset-empty">
                      当前筛选下没有待审核用例。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : null}
        </section>

        <footer className="asset-footer">
          <span>第 {Number(pagination?.page || 1)} / {Number(pagination?.total_pages || 1)} 页</span>
          <span>总计 {Number(pagination?.total_items || items.length)} 条</span>
        </footer>
      </section>
    </main>
  );
}
