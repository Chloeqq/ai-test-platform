import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  batchDeleteTestPointAssets,
  batchGenerateCasesFromTestPointAssets,
  deleteTestPointAsset,
  getTestPointAsset,
  listTestPointAssets,
  updateTestPointAsset,
  upsertTestPointAsset,
} from "../api/assets";
import { BulkActionBar } from "../components/BulkActionBar";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { MetricCards } from "../components/MetricCards";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

interface AssetEditorState {
  assetId: string;
  title: string;
  page: string;
  priority: string;
  requirement: string;
  summary: string;
  stepsText: string;
  expected: string;
  involvedElementsText: string;
}

const EMPTY_EDITOR: AssetEditorState = {
  assetId: "",
  title: "",
  page: "",
  priority: "P1",
  requirement: "",
  summary: "",
  stepsText: "",
  expected: "",
  involvedElementsText: "",
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

function toStepTextList(steps: unknown): string[] {
  if (!Array.isArray(steps)) {
    return [];
  }
  const rows: string[] = [];
  steps.forEach((raw) => {
    if (typeof raw === "string") {
      const row = raw.trim();
      if (row) {
        rows.push(row);
      }
      return;
    }
    if (raw && typeof raw === "object") {
      const row = raw as Record<string, unknown>;
      const text = String(row.raw_text || row.value || row.description || row.action || "").trim();
      if (text) {
        rows.push(text);
      }
    }
  });
  return rows;
}

function splitElements(value: string): string[] {
  return String(value || "")
    .split(/[\n,，]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function suggestAssetId(projectCode: string): string {
  const normalizedProject = String(projectCode || DEFAULT_PROJECT_CODE)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "") || DEFAULT_PROJECT_CODE;
  const seq = String(Date.now() % 10000).padStart(4, "0");
  return `${normalizedProject}-web-common-core-fn-ai-${seq}`;
}

export function TestPointAssetsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [project, setProject] = useState<string>(() => normalizeProjectCode(searchParams.get("project")));
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectionSummary, setSelectionSummary] = useState<Record<string, unknown>>({});
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");
  const [editorOpen, setEditorOpen] = useState<boolean>(false);
  const [editing, setEditing] = useState<boolean>(false);
  const [editor, setEditor] = useState<AssetEditorState>(EMPTY_EDITOR);
  const [deleteTarget, setDeleteTarget] = useState<{ mode: "single" | "batch"; assetId?: string } | null>(null);

  function pickDefaultProject(codes: string[], currentProject = ""): string {
    const normalizedCurrent = String(currentProject || "").trim();
    if (normalizedCurrent) {
      return normalizedCurrent;
    }
    const preferred = codes.find((code) => String(code || "").trim() === DEFAULT_PROJECT_CODE);
    return normalizeProjectCode(preferred || codes[0]);
  }

  function changeProject(nextProject: string) {
    const normalized = String(nextProject || "").trim();
    setProject(normalized);
    const nextParams = new URLSearchParams(searchParams);
    if (normalized) {
      nextParams.set("project", normalized);
    } else {
      nextParams.delete("project");
    }
    setSearchParams(nextParams, { replace: true });
    void reload(normalizeProjectCode(normalized));
  }

  async function reload(targetProject = project) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listTestPointAssets({
        project: normalizeProjectCode(targetProject),
        keyword: keyword.trim(),
      });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      setSelectionSummary((payload.selection_summary || {}) as Record<string, unknown>);
      const rowAssetIds = rows
        .map((item) => String(item.asset_id || "").trim())
        .filter(Boolean);
      setSelectedAssetIds((prev) => prev.filter((item) => rowAssetIds.includes(item)));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "测试点资产加载失败");
      setItems([]);
      setSelectionSummary({});
      setSelectedAssetIds([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      let nextProject = normalizeProjectCode(project);
      try {
        const projects = await listProjects();
        if (!cancelled) {
          const codes = projectOptions(projects.codes);
          setProjectCodes(codes);
          if (codes.length && !project) {
            nextProject = pickDefaultProject(codes);
            setProject(nextProject);
            const nextParams = new URLSearchParams(searchParams);
            nextParams.set("project", nextProject);
            setSearchParams(nextParams, { replace: true });
          }
        }
      } catch {
        // Ignore project list errors.
      }
      if (!cancelled) {
        await reload(nextProject);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedCount = selectedAssetIds.length;
  const allAssetIds = useMemo(
    () => items.map((item) => String(item.asset_id || "").trim()).filter(Boolean),
    [items],
  );
  const allSelected = Boolean(allAssetIds.length && allAssetIds.every((assetId) => selectedAssetIds.includes(assetId)));

  function toggleSelection(assetId: string) {
    setSelectedAssetIds((prev) => {
      if (prev.includes(assetId)) {
        return prev.filter((item) => item !== assetId);
      }
      return [...prev, assetId];
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedAssetIds([]);
      return;
    }
    setSelectedAssetIds(allAssetIds);
  }

  function openCreateEditor() {
    setEditing(false);
    setEditor({
      ...EMPTY_EDITOR,
      assetId: suggestAssetId(normalizeProjectCode(project)),
      page: "",
      priority: "P1",
    });
    setEditorOpen(true);
    setActionText("");
  }

  async function openEditEditor(assetId: string) {
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const detailPayload = await getTestPointAsset(assetId, normalizeProjectCode(project));
      const item = (detailPayload.item || {}) as Record<string, unknown>;
      const plan = (item.plan || {}) as Record<string, unknown>;
      const points = Array.isArray(plan.points) ? plan.points : [];
      const firstPoint = (points[0] || {}) as Record<string, unknown>;
      setEditor({
        assetId: String(item.asset_id || assetId).trim(),
        title: String(item.title || "").trim(),
        page: String(item.page || "").trim(),
        priority: String(item.priority || "P1").trim() || "P1",
        requirement: Array.isArray(item.requirement) ? item.requirement.map((row) => String(row || "").trim()).filter(Boolean).join("\n") : "",
        summary: String(firstPoint.description || item.title || "").trim(),
        stepsText: toStepTextList(firstPoint.steps).join("\n"),
        expected: String(firstPoint.expected_result || "").trim(),
        involvedElementsText: Array.isArray(firstPoint.involved_elements)
          ? firstPoint.involved_elements.map((row) => String(row || "").trim()).filter(Boolean).join(", ")
          : "",
      });
      setEditing(true);
      setEditorOpen(true);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "测试点资产详情加载失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitEditor() {
    const normalizedAssetId = String(editor.assetId || "").trim();
    const normalizedPage = String(editor.page || "").trim();
    if (!normalizedAssetId) {
      setErrorText("asset_id 不能为空。");
      return;
    }
    if (!normalizedPage) {
      setErrorText("页面(page)不能为空。");
      return;
    }
    const steps = String(editor.stepsText || "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    const candidate = {
      intent_id: normalizedAssetId,
      title: String(editor.summary || editor.title || normalizedAssetId).trim(),
      summary: String(editor.summary || editor.title || normalizedAssetId).trim(),
      intent_type: "functional",
      priority: String(editor.priority || "P1").trim() || "P1",
      steps,
      expected: String(editor.expected || "").trim(),
      involved_elements: splitElements(editor.involvedElementsText),
    };
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const payload = {
        project: normalizeProjectCode(project),
        asset_id: normalizedAssetId,
        page: normalizedPage,
        title: String(editor.title || normalizedAssetId).trim(),
        priority: String(editor.priority || "P1").trim() || "P1",
        requirement: String(editor.requirement || editor.summary || editor.title || "").trim(),
        source_type: "manual",
        selected_candidates: [candidate],
      };
      if (editing) {
        await updateTestPointAsset(normalizedAssetId, payload);
      } else {
        await upsertTestPointAsset(payload);
      }
      setEditorOpen(false);
      setActionText(editing ? "测试点资产已更新。" : "测试点资产已创建。");
      await reload(normalizeProjectCode(project));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "测试点资产保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeOne(assetId: string) {
    setDeleteTarget({ mode: "single", assetId });
  }

  async function confirmRemoveOne(assetId: string) {
    if (!assetId) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      await deleteTestPointAsset(assetId, normalizeProjectCode(project));
      setActionText("测试点资产已删除。");
      setDeleteTarget(null);
      await reload(normalizeProjectCode(project));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemove() {
    if (!selectedAssetIds.length) {
      return;
    }
    setDeleteTarget({ mode: "batch" });
  }

  async function confirmBatchRemove() {
    if (!selectedAssetIds.length) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const response = await batchDeleteTestPointAssets({
        project: normalizeProjectCode(project),
        asset_ids: selectedAssetIds,
      });
      setActionText(`批量删除完成：删除 ${Number(response.deleted_count || 0)} 条。`);
      setDeleteTarget(null);
      await reload(normalizeProjectCode(project));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function generateOne(assetId: string) {
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const response = await batchGenerateCasesFromTestPointAssets({
        project: normalizeProjectCode(project),
        asset_ids: [assetId],
        source: "manual",
      });
      setActionText(`已从资产 ${assetId} 生成 ${Number(response.count || 0)} 条用例。`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "生成用例失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchGenerate() {
    if (!selectedAssetIds.length) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const response = await batchGenerateCasesFromTestPointAssets({
        project: normalizeProjectCode(project),
        asset_ids: selectedAssetIds,
        source: "manual",
      });
      setActionText(`批量生成完成：生成 ${Number(response.count || 0)} 条用例。`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量生成失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>测试点资产</h1>
          <p className="muted">统一管理测试点资产，支持审核、维护和生成自动化用例。</p>
        </div>
      </header>

      <FilterBar>
        <label>
          项目
          <select
            value={project}
            onChange={(event) => {
              const next = normalizeProjectCode(event.target.value);
              changeProject(next);
            }}
            disabled={busy}
          >
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          关键词
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="资产编码 / 标题 / 需求"
            disabled={busy}
          />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload(normalizeProjectCode(project))} disabled={busy}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              changeProject(pickDefaultProject(projectCodes));
              setKeyword("");
              void reload(pickDefaultProject(projectCodes));
            }}
            disabled={busy}
          >
            重置全部
          </button>
        </div>
      </FilterBar>

      <section className="panel">
        <div className="header-actions asset-action-row">
          <button type="button" className="button" onClick={openCreateEditor} disabled={busy}>
            新增资产
          </button>
          <BulkActionBar selectedCount={selectedCount}>
            <button type="button" className="button secondary" onClick={batchGenerate} disabled={busy || !selectedCount}>
              批量生成用例
            </button>
            <button type="button" className="button danger secondary" onClick={batchRemove} disabled={busy || !selectedCount}>
              批量删除
            </button>
          </BulkActionBar>
        </div>
        {actionText ? <p>{actionText}</p> : null}
      </section>

      {editorOpen ? (
        <section className="panel">
          <h2>{editing ? "编辑测试点资产" : "新增测试点资产"}</h2>
          <div className="form-grid">
            <label>
              资产编码
              <input
                value={editor.assetId}
                onChange={(event) => setEditor((prev) => ({ ...prev, assetId: event.target.value }))}
                disabled={busy || editing}
              />
            </label>
            <label>
              页面
              <input
                value={editor.page}
                onChange={(event) => setEditor((prev) => ({ ...prev, page: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label>
              优先级
              <select
                value={editor.priority}
                onChange={(event) => setEditor((prev) => ({ ...prev, priority: event.target.value }))}
                disabled={busy}
              >
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
              </select>
            </label>
            <label className="span-2">
              标题
              <input
                value={editor.title}
                onChange={(event) => setEditor((prev) => ({ ...prev, title: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              需求
              <textarea
                rows={4}
                value={editor.requirement}
                onChange={(event) => setEditor((prev) => ({ ...prev, requirement: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              测试点摘要
              <input
                value={editor.summary}
                onChange={(event) => setEditor((prev) => ({ ...prev, summary: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              步骤（每行一条）
              <textarea
                rows={5}
                value={editor.stepsText}
                onChange={(event) => setEditor((prev) => ({ ...prev, stepsText: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              预期结果
              <textarea
                rows={3}
                value={editor.expected}
                onChange={(event) => setEditor((prev) => ({ ...prev, expected: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label className="span-3">
              涉及元素（逗号分隔）
              <input
                value={editor.involvedElementsText}
                onChange={(event) => setEditor((prev) => ({ ...prev, involvedElementsText: event.target.value }))}
                disabled={busy}
              />
            </label>
          </div>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitEditor()} disabled={busy}>
              保存
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => setEditorOpen(false)}
              disabled={busy}
            >
              取消
            </button>
          </div>
        </section>
      ) : null}

      <MetricCards
        className="panel stat-grid"
        cardClassName="stat-card"
        items={[
          { label: "资产总数", value: numberValue(selectionSummary.total_assets) },
          { label: "就绪", value: numberValue(selectionSummary.ready_count), tone: "good" },
          { label: "待审核", value: numberValue(selectionSummary.needs_review_count), tone: "warn" },
          { label: "阻断", value: numberValue(selectionSummary.blocked_count), tone: "bad" },
        ]}
      />

      <DataTable loading={loading} loadingText="正在加载测试点资产..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
                </th>
                <th>资产编码</th>
                <th>标题</th>
                <th>页面</th>
                <th>来源</th>
                <th>点位数</th>
                <th>置信度</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item, index) => {
                  const assetId = String(item.asset_id || "").trim();
                  const selected = selectedAssetIds.includes(assetId);
                  return (
                    <tr key={assetId || String(index)} className={selected ? "is-active" : ""}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleSelection(assetId)}
                          disabled={busy || !assetId}
                        />
                      </td>
                      <td className="mono">{text(assetId)}</td>
                      <td>{text(item.title)}</td>
                      <td>{text(item.page)}</td>
                      <td>{text(item.source_type)}</td>
                      <td>{numberValue(item.point_count)}</td>
                      <td>{numberValue(item.confidence)}</td>
                      <td>{formatDateTime(item.updated_at)}</td>
                      <td>
                        <div className="header-actions">
                          <Link className="button secondary" to={`/assets/test-points/${encodeURIComponent(assetId)}?project=${encodeURIComponent(normalizeProjectCode(project))}`}>查看</Link>
                          <button type="button" className="button secondary" onClick={() => void openEditEditor(assetId)} disabled={busy || !assetId}>
                            编辑
                          </button>
                          <details className="action-menu">
                            <summary>更多</summary>
                            <button type="button" onClick={() => void generateOne(assetId)} disabled={busy || !assetId}>
                              生成用例
                            </button>
                            <button type="button" className="danger-text" onClick={() => void removeOne(assetId)} disabled={busy || !assetId}>
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
                  <td colSpan={9}>
                    <EmptyState
                      title="还没有测试点资产"
                      description="可以先从 AI 生成工作台提取测试点，或在这里手动新增资产。"
                      action={(
                        <button type="button" className="button" onClick={openCreateEditor} disabled={busy}>
                          新增测试点资产
                        </button>
                      )}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
      {deleteTarget ? (
        <ConfirmDialog
          title={deleteTarget.mode === "batch" ? "确认批量删除测试点资产" : "确认删除测试点资产"}
          description="该操作会物理删除资产记录，请确认当前资产不再需要继续治理或生成用例。"
          danger
          busy={busy}
          confirmText="确认删除"
          details={
            deleteTarget.mode === "batch"
              ? [`将删除 ${selectedAssetIds.length} 条测试点资产`, "删除后不会再出现在资产列表中"]
              : [`资产编码：${deleteTarget.assetId || "-"}`, "删除后不会再出现在资产列表中"]
          }
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            if (deleteTarget.mode === "batch") {
              void confirmBatchRemove();
            } else {
              void confirmRemoveOne(deleteTarget.assetId || "");
            }
          }}
        />
      ) : null}
    </main>
  );
}
