import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { batchUpdateTestCaseTags, listTestCasesDb } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function caseIdOf(item: Record<string, unknown>): string {
  return String(item.case_id || "").trim();
}

function normalizeTags(value: string): string[] {
  return value
    .split(/[,，\s]+/g)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function CaseTagsPage() {
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [tagFilter, setTagFilter] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [mode, setMode] = useState<"replace" | "append">("append");
  const [tagsInput, setTagsInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetProject = project, targetKeyword = keyword, targetTagFilter = tagFilter) {
    setLoading(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await listTestCasesDb({
        project_code: targetProject || "",
        q: targetKeyword.trim(),
        tag: targetTagFilter.trim(),
        sort_field: "updated_at",
        sort_order: "desc",
        page: 1,
        page_size: 80,
      });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      const visible = new Set(rows.map((item) => caseIdOf(item)).filter(Boolean));
      setSelectedCaseIds((prev) => prev.filter((id) => visible.has(id)));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例标签数据加载失败");
      setItems([]);
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
        // Ignore.
      }
      if (!cancelled) {
        await reload();
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const allVisibleCaseIds = useMemo(() => items.map((item) => caseIdOf(item)).filter(Boolean), [items]);
  const allSelected = allVisibleCaseIds.length > 0 && selectedCaseIds.length === allVisibleCaseIds.length;
  const uniqueTagCount = new Set(
    items.flatMap((item) => (Array.isArray(item.tags) ? item.tags.map((tag) => String(tag || "").trim()).filter(Boolean) : [])),
  ).size;

  function toggleItem(caseId: string) {
    const normalized = String(caseId || "").trim();
    if (!normalized) {
      return;
    }
    setSelectedCaseIds((prev) => (prev.includes(normalized) ? prev.filter((id) => id !== normalized) : [...prev, normalized]));
  }

  function toggleAll() {
    setSelectedCaseIds((prev) => (allSelected ? prev.filter((id) => !allVisibleCaseIds.includes(id)) : [...new Set([...prev, ...allVisibleCaseIds])]));
  }

  async function applyBatchTags() {
    if (saving) {
      return;
    }
    const tags = normalizeTags(tagsInput);
    if (!selectedCaseIds.length) {
      setErrorText("请先选择至少一条用例。");
      return;
    }
    if (!tags.length) {
      setErrorText("请至少输入一个标签。");
      return;
    }
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await batchUpdateTestCaseTags({
        case_ids: selectedCaseIds,
        mode,
        tags,
      });
      setFeedback(`标签更新完成：${Number(payload.updated_count || 0)} 条`);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量更新标签失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>标签治理中心</h1>
            <p className="muted">统一批量追加或替换标签，确保用例标签体系一致。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to="/cases">
              用例中心
            </Link>
            <Link className="button secondary" to="/cases/review">
              待审核队列
            </Link>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card">
            <span>可治理用例</span>
            <strong>{items.length}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>已选用例</span>
            <strong>{selectedCaseIds.length}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>标签总类</span>
            <strong>{uniqueTagCount}</strong>
          </article>
          <article className="asset-kpi-card">
            <span>当前模式</span>
            <strong>{mode}</strong>
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
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="case_id / 名称 / 模块" />
          </label>
          <label>
            标签过滤
            <input value={tagFilter} onChange={(event) => setTagFilter(event.target.value)} placeholder="按标签筛选（可选）" />
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reload()}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setKeyword("");
                setTagFilter("");
                setSelectedCaseIds([]);
                setTagsInput("");
                setMode("append");
                void reload(DEFAULT_PROJECT_CODE, "", "");
              }}
            >
              重置全部
            </button>
          </div>
        </section>

        <section className="asset-toolbar">
          <label className="grow">
            批量标签（逗号分隔）
            <input value={tagsInput} onChange={(event) => setTagsInput(event.target.value)} placeholder="如：smoke, login, regression" />
          </label>
          <label>
            更新模式
            <select value={mode} onChange={(event) => setMode((event.target.value || "append") as "replace" | "append")}>
              <option value="append">append</option>
              <option value="replace">replace</option>
            </select>
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void applyBatchTags()} disabled={saving}>
              执行批量更新
            </button>
          </div>
        </section>
        <p className="asset-hint">提示：append 会保留旧标签，replace 会覆盖旧标签；执行前建议先筛选并勾选目标用例。</p>

        <section className="asset-table-wrap">
          {loading ? <p>正在加载标签治理数据...</p> : null}
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
                  <th>当前标签</th>
                  <th>模块</th>
                  <th>状态</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                {items.length ? (
                  items.map((item, index) => {
                    const caseId = caseIdOf(item);
                    const tags = Array.isArray(item.tags) ? item.tags : [];
                    return (
                      <tr key={caseId || String(index)}>
                        <td>
                          <input type="checkbox" checked={selectedCaseIds.includes(caseId)} onChange={() => toggleItem(caseId)} />
                        </td>
                        <td className="mono">{text(caseId)}</td>
                        <td>{text(item.case_title || item.name)}</td>
                        <td>
                          <div className="asset-pill-strip">
                            {tags.length ? (
                              tags.map((tag, tagIndex) => (
                                <span key={`${caseId}-tag-${tagIndex}`} className="asset-pill">
                                  {text(tag)}
                                </span>
                              ))
                            ) : (
                              <span className="muted">-</span>
                            )}
                          </div>
                        </td>
                        <td>{text(item.module || item.business_module)}</td>
                        <td>{text(item.lifecycle_status || item.status)}</td>
                        <td>{formatDateTime(item.updated_at)}</td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={7} className="asset-empty">
                      当前筛选下暂无数据。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : null}
        </section>
      </section>
    </main>
  );
}
