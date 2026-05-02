import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  createPageObject,
  deletePageObject,
  listPageObjects,
  updatePageObject,
} from "../api/assets";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { BulkActionBar } from "../components/BulkActionBar";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { MetricCards } from "../components/MetricCards";
import { StatusPill, statusLabel } from "../components/StatusPill";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

interface PageObjectEditorState {
  pageCode: string;
  pageName: string;
  pageUrl: string;
  preconditionState: string;
  moduleId: string;
  description: string;
  status: string;
}

const EMPTY_EDITOR: PageObjectEditorState = {
  pageCode: "",
  pageName: "",
  pageUrl: "",
  preconditionState: "",
  moduleId: "0",
  description: "",
  status: "draft",
};

const PAGE_OBJECT_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  review: "评审中",
  published: "已发布",
  retired: "已下线",
};

const GOVERNANCE_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  active: "已可用",
  governing: "治理中",
  retired: "已下线",
};

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function pageObjectStatusText(value: unknown): string {
  return statusLabel(value, PAGE_OBJECT_STATUS_LABELS);
}

function numberValue(value: unknown): string {
  if (typeof value === "number") {
    return String(value);
  }
  const normalized = String(value || "").trim();
  return normalized || "0";
}

function numberOf(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(String(value || "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentValue(value: unknown): number {
  const normalized = Math.max(0, Math.min(100, numberOf(value)));
  return Math.round(normalized);
}

function scoreTone(value: unknown): "good" | "warn" | "bad" {
  const score = percentValue(value);
  if (score >= 80) {
    return "good";
  }
  if (score >= 60) {
    return "warn";
  }
  return "bad";
}

function buildElementsLink(pageCode: string, projectCode: string): string {
  const query = new URLSearchParams();
  const normalizedProject = String(projectCode || "").trim();
  if (normalizedProject) {
    query.set("project", normalizedProject);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return `/assets/page-objects/${encodeURIComponent(pageCode)}/elements${suffix}`;
}

function buildRecorderLink(item: Record<string, unknown>, projectCode: string): string {
  const query = new URLSearchParams();
  const normalizedProject = String(projectCode || item.project_code || "").trim();
  const pageCode = String(item.page_code || "").trim();
  const pageName = String(item.page_name || "").trim();
  const pageUrl = String(item.page_url || item.route_pattern || "").trim();
  if (normalizedProject) {
    query.set("project", normalizedProject);
  }
  if (pageCode) {
    query.set("page_code", pageCode);
  }
  if (pageName) {
    query.set("page_name", pageName);
  }
  if (pageUrl) {
    query.set("url", pageUrl);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return `/assets/page-objects/recorder${suffix}`;
}

export function PageObjectsPage() {
  const [projectCode, setProjectCode] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectedPageCodes, setSelectedPageCodes] = useState<string[]>([]);
  const [keyword, setKeyword] = useState<string>("");
  const [moduleFilter, setModuleFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [governanceFilter, setGovernanceFilter] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");
  const [editorOpen, setEditorOpen] = useState<boolean>(false);
  const [editing, setEditing] = useState<boolean>(false);
  const [editor, setEditor] = useState<PageObjectEditorState>(EMPTY_EDITOR);
  const [deleteTarget, setDeleteTarget] = useState<{ mode: "single" | "batch"; pageCode?: string } | null>(null);

  const allPageCodes = useMemo(
    () => items.map((item) => String(item.page_code || "").trim()).filter(Boolean),
    [items],
  );
  const allSelected = Boolean(allPageCodes.length && allPageCodes.every((code) => selectedPageCodes.includes(code)));
  const filteredItems = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return items.filter((item) => {
      const status = String(item.status || "").trim().toLowerCase();
      const governanceStatus = String(item.governance_status || "").trim().toLowerCase();
      if (statusFilter && status !== statusFilter) {
        return false;
      }
      if (governanceFilter && governanceStatus !== governanceFilter) {
        return false;
      }
      if (moduleFilter.trim() && String(item.module_id || "0").trim() !== moduleFilter.trim()) {
        return false;
      }
      if (!normalizedKeyword) {
        return true;
      }
      return [item.page_code, item.page_name, item.page_url, item.route_pattern]
        .map((value) => String(value || "").toLowerCase())
        .some((value) => value.includes(normalizedKeyword));
    });
  }, [governanceFilter, items, keyword, moduleFilter, statusFilter]);
  const summary = useMemo(() => {
    const pageCount = items.length;
    const governedCount = items.filter((item) => String(item.governance_status || "").trim().toLowerCase() === "active").length;
    const pendingCandidateCount = items.reduce((total, item) => total + numberOf(item.candidate_pending_count), 0);
    const averageTestability = pageCount
      ? Math.round(items.reduce((total, item) => total + numberOf(item.testability_score), 0) / pageCount)
      : 0;
    return { pageCount, governedCount, pendingCandidateCount, averageTestability };
  }, [items]);

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listPageObjects({ project_code: projectCode, client: "web" });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      const rowCodes = rows.map((item) => String(item.page_code || "").trim()).filter(Boolean);
      setSelectedPageCodes((prev) => prev.filter((item) => rowCodes.includes(item)));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象加载失败");
      setItems([]);
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
          const codes = projectOptions(projects.codes);
          setProjectCodes(codes);
          if (codes.length && !codes.includes(projectCode)) {
            setProjectCode(codes[0]);
          }
        }
      } catch {
        // Keep default option.
      }
    }
    void loadProjectOptions();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectCode]);

  function openCreateEditor() {
    setEditing(false);
    setEditor(EMPTY_EDITOR);
    setEditorOpen(true);
    setActionText("");
  }

  function openEditEditor(item: Record<string, unknown>) {
    setEditing(true);
    setEditor({
      pageCode: String(item.page_code || "").trim(),
      pageName: String(item.page_name || "").trim(),
      pageUrl: String(item.page_url || "").trim(),
      preconditionState: String(item.precondition_state || "").trim(),
      moduleId: String(item.module_id || "0").trim() || "0",
      description: String(item.description || "").trim(),
      status: String(item.status || "draft").trim() || "draft",
    });
    setEditorOpen(true);
    setActionText("");
  }

  async function submitEditor() {
    const pageCode = String(editor.pageCode || "").trim();
    const pageName = String(editor.pageName || "").trim();
    if (!pageCode) {
      setErrorText("页面编码不能为空。");
      return;
    }
    if (!pageName) {
      setErrorText("页面名称不能为空。");
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      if (editing) {
        await updatePageObject(
          pageCode,
          {
            page_name: pageName,
            page_url: String(editor.pageUrl || "").trim(),
            precondition_state: String(editor.preconditionState || "").trim(),
            module_id: Number(editor.moduleId || 0) || 0,
            description: String(editor.description || "").trim(),
            status: String(editor.status || "draft").trim() || "draft",
          },
          { project_code: projectCode, client: "web" },
        );
      } else {
        await createPageObject({
          project_code: projectCode,
          client: "web",
          page_code: pageCode,
          page_name: pageName,
          page_url: String(editor.pageUrl || "").trim(),
          precondition_state: String(editor.preconditionState || "").trim(),
          module_id: Number(editor.moduleId || 0) || 0,
          description: String(editor.description || "").trim(),
          status: String(editor.status || "draft").trim() || "draft",
          created_by: "web-ui",
        });
      }
      setEditorOpen(false);
      setActionText(editing ? "页面对象已更新。" : "页面对象已创建。");
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象保存失败");
    } finally {
      setBusy(false);
    }
  }

  function toggleSelection(pageCode: string) {
    setSelectedPageCodes((prev) => {
      if (prev.includes(pageCode)) {
        return prev.filter((item) => item !== pageCode);
      }
      return [...prev, pageCode];
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedPageCodes([]);
      return;
    }
    setSelectedPageCodes(allPageCodes);
  }

  async function removeOne(pageCode: string) {
    setDeleteTarget({ mode: "single", pageCode });
  }

  async function confirmRemoveOne(pageCode: string) {
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      await deletePageObject(pageCode, { project_code: projectCode, client: "web", cascade_elements: true });
      setActionText("页面对象已删除。");
      setDeleteTarget(null);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemove() {
    if (!selectedPageCodes.length) {
      return;
    }
    setDeleteTarget({ mode: "batch" });
  }

  async function confirmBatchRemove() {
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      let deletedCount = 0;
      for (const pageCode of selectedPageCodes) {
        await deletePageObject(pageCode, { project_code: projectCode, client: "web", cascade_elements: true });
        deletedCount += 1;
      }
      setActionText(`批量删除完成：删除 ${deletedCount} 个页面对象。`);
      setDeleteTarget(null);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量删除失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>页面对象</h1>
          <p className="muted">统一管理页面资产、录制过程与元素治理状态。</p>
        </div>
        <div className="header-actions">
          <button type="button" className="button" onClick={openCreateEditor} disabled={busy}>
            新建页面对象
          </button>
        </div>
      </header>

      <MetricCards
        items={[
          { label: "页面总数", value: summary.pageCount, hint: "当前项目页面对象总量" },
          { label: "已治理页面", value: summary.governedCount, hint: "治理状态为已可用" },
          {
            label: "待审候选组",
            value: summary.pendingCandidateCount,
            hint: "当前项目待处理候选总量",
            tone: summary.pendingCandidateCount > 0 ? "warn" : "",
          },
          {
            label: "平均可测试性",
            value: summary.averageTestability,
            hint: "页面级可测试性评分均值",
            tone: scoreTone(summary.averageTestability),
          },
        ]}
      />

      <FilterBar>
        <label>
          项目
          <select value={projectCode} onChange={(event) => setProjectCode(normalizeProjectCode(event.target.value))} disabled={busy}>
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label>
          端类型
          <select value="web" disabled>
            <option value="web">web</option>
          </select>
        </label>
        <label>
          模块
          <select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)} disabled={busy}>
            <option value="">全部</option>
            {Array.from(new Set(items.map((item) => String(item.module_id || "0").trim()).filter(Boolean))).map((moduleId) => (
              <option key={moduleId} value={moduleId}>
                {moduleId === "0" ? "默认模块" : `模块 ${moduleId}`}
              </option>
            ))}
          </select>
        </label>
        <label>
          页面状态
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} disabled={busy}>
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="review">评审中</option>
            <option value="published">已发布</option>
            <option value="retired">已下线</option>
          </select>
        </label>
        <label>
          治理状态
          <select value={governanceFilter} onChange={(event) => setGovernanceFilter(event.target.value)} disabled={busy}>
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="active">已可用</option>
            <option value="governing">治理中</option>
            <option value="retired">已下线</option>
          </select>
        </label>
        <label className="grow">
          关键词
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索页面编码、页面名称或 URL" disabled={busy} />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload()} disabled={busy}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
                  setKeyword("");
                  setModuleFilter("");
                  setStatusFilter("");
                  setGovernanceFilter("");
                }}
            disabled={busy}
          >
            重置
          </button>
          <BulkActionBar selectedCount={selectedPageCodes.length}>
            <button type="button" className="button danger secondary" onClick={batchRemove} disabled={busy || !selectedPageCodes.length}>
              批量删除
            </button>
          </BulkActionBar>
          <Link className="subtle-link" to="/system/projects">项目管理</Link>
          <Link className="subtle-link" to="/system/source-config">源码管理</Link>
        </div>
      </FilterBar>

      {editorOpen ? (
        <section className="panel">
          <h2>{editing ? "编辑页面对象" : "新增页面对象"}</h2>
          <div className="form-grid">
            <label>
              页面编码（page_code）
              <input
                value={editor.pageCode}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageCode: event.target.value }))}
                disabled={busy || editing}
              />
            </label>
            <label>
              页面名称（page_name）
              <input
                value={editor.pageName}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageName: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label>
              状态
              <select
                value={editor.status}
                onChange={(event) => setEditor((prev) => ({ ...prev, status: event.target.value }))}
                disabled={busy}
              >
                <option value="draft">草稿</option>
                <option value="review">评审中</option>
                <option value="published">已发布</option>
                <option value="retired">已下线</option>
              </select>
            </label>
            <label className="span-2">
              页面地址（page_url）
              <input
                value={editor.pageUrl}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageUrl: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label>
              模块
              <input
                value={editor.moduleId}
                onChange={(event) => setEditor((prev) => ({ ...prev, moduleId: event.target.value }))}
                placeholder="默认模块可填 0"
                disabled={busy}
              />
            </label>
            <label className="span-3">
              前置状态（precondition_state）
              <textarea
                rows={3}
                value={editor.preconditionState}
                onChange={(event) => setEditor((prev) => ({ ...prev, preconditionState: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              说明（description）
              <textarea
                rows={3}
                value={editor.description}
                onChange={(event) => setEditor((prev) => ({ ...prev, description: event.target.value }))}
                disabled={busy}
              />
            </label>
          </div>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitEditor()} disabled={busy}>
              保存
            </button>
            <button type="button" className="button secondary" onClick={() => setEditorOpen(false)} disabled={busy}>
              取消
            </button>
          </div>
        </section>
      ) : null}

      {actionText ? <section className="panel">{actionText}</section> : null}
      {loading ? <section className="panel">正在加载页面对象...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}

      {!loading && !errorText ? (
        <DataTable title={`页面对象列表：${filteredItems.length}`}>
          <table>
            <thead>
              <tr>
                <th>
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
                </th>
                <th>页面编码</th>
                <th>页面名称</th>
                <th>页面地址 / Route</th>
                <th>正式元素数</th>
                <th>待审候选组</th>
                <th>关键元素覆盖率</th>
                <th>可测试性评分</th>
                <th>治理状态</th>
                <th>最近录制时间</th>
                <th>页面状态</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length ? (
                filteredItems.map((item, index) => {
                  const pageCode = String(item.page_code || "").trim();
                  const selected = selectedPageCodes.includes(pageCode);
                  const pendingCount = numberOf(item.candidate_pending_count);
                  const keyCount = numberOf(item.key_element_count);
                  const formalCount = numberOf(item.element_count);
                  const coverage = formalCount > 0 ? percentValue((keyCount / formalCount) * 100) : 0;
                  return (
                    <tr key={String(item.id || index)} className={selected ? "is-active" : ""}>
                      <td>
                        <input type="checkbox" checked={selected} onChange={() => toggleSelection(pageCode)} disabled={busy || !pageCode} />
                      </td>
                      <td className="mono">{text(pageCode)}</td>
                      <td>
                        {pageCode ? (
                          <Link className="link-strong" to={buildElementsLink(pageCode, projectCode)}>
                            {text(item.page_name)}
                          </Link>
                        ) : (
                          text(item.page_name)
                        )}
                      </td>
                      <td className="compact-cell">
                        <span>{text(item.page_url || item.route_pattern)}</span>
                        {item.route_pattern ? <small>{text(item.route_pattern)}</small> : null}
                      </td>
                      <td>{numberValue(item.element_count)}</td>
                      <td>{pendingCount > 0 ? <span className="count-badge warn">{pendingCount}</span> : <span className="muted">0</span>}</td>
                      <td>
                        <div className={`mini-progress tone-${scoreTone(coverage)}`}>
                          <span>{coverage}%</span>
                          <em><i style={{ width: `${coverage}%` }} /></em>
                        </div>
                      </td>
                      <td>
                        <div className={`mini-progress tone-${scoreTone(item.testability_score)}`}>
                          <span>{numberValue(item.testability_score)}</span>
                          <em><i style={{ width: `${percentValue(item.testability_score)}%` }} /></em>
                        </div>
                      </td>
                      <td>
                        <StatusPill prefix="governance" value={item.governance_status} labels={GOVERNANCE_STATUS_LABELS} />
                      </td>
                      <td>{formatDateTime(item.latest_recorded_at)}</td>
                      <td>{pageObjectStatusText(item.status)}</td>
                      <td>{formatDateTime(item.updated_at)}</td>
                      <td>
                        <div className="header-actions">
                          {pageCode ? (
                            <Link className="button secondary table-action-primary" to={buildElementsLink(pageCode, projectCode)}>
                              查看元素
                            </Link>
                          ) : (
                            <button type="button" className="button secondary" disabled>
                              查看元素
                            </button>
                          )}
                          <Link className="button secondary" to={buildRecorderLink(item, projectCode)}>
                            开始录制
                          </Link>
                          <details className="action-menu">
                            <summary>更多</summary>
                            <button type="button" onClick={() => openEditEditor(item)} disabled={busy || !pageCode}>
                              编辑页面
                            </button>
                            <button type="button" className="danger-text" onClick={() => void removeOne(pageCode)} disabled={busy || !pageCode}>
                              删除
                            </button>
                          </details>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={13}>
                    <EmptyState
                      title="还没有页面对象"
                      description="建议先创建页面对象，再开始录制和治理元素资产。"
                      action={(
                        <button type="button" className="button" onClick={openCreateEditor} disabled={busy}>
                          新建页面对象
                        </button>
                      )}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTable>
      ) : null}
      {deleteTarget ? (
        <ConfirmDialog
          title={deleteTarget.mode === "batch" ? "确认批量删除页面对象" : "确认删除页面对象"}
          description="该操作会物理删除页面对象，并级联删除关联元素资产。"
          danger
          busy={busy}
          confirmText="确认删除"
          details={
            deleteTarget.mode === "batch"
              ? [`将删除 ${selectedPageCodes.length} 个页面对象`, "关联正式元素、候选和录制资产可能同步受影响"]
              : [`页面编码：${deleteTarget.pageCode || "-"}`, "关联元素会一并删除"]
          }
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            if (deleteTarget.mode === "batch") {
              void confirmBatchRemove();
            } else {
              void confirmRemoveOne(deleteTarget.pageCode || "");
            }
          }}
        />
      ) : null}
    </main>
  );
}
