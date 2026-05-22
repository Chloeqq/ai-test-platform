import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  batchGenerateCasesFromTestPointAssets,
  batchReviewTestPoints,
  getTestPointScriptPreview,
  listTestPointReviews,
  type TestPointReviewsResponse,
} from "../api/assets";
import { listProjects } from "../api/workbench";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { TablePagination } from "../components/TablePagination";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

type ReviewStatus = "pending" | "approved" | "rejected";
type SortDirection = "asc" | "desc";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function rawText(value: unknown): string {
  return String(value || "").trim();
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function reviewKeyOf(item: Record<string, unknown>): string {
  const assetId = rawText(item.asset_id);
  const intentId = rawText(item.intent_id);
  return assetId && intentId ? `${assetId}::${intentId}` : "";
}

function decisionFromKey(key: string): { asset_id: string; intent_id: string } | null {
  const [assetId, intentId] = String(key || "").split("::");
  if (!assetId || !intentId) {
    return null;
  }
  return { asset_id: assetId, intent_id: intentId };
}

function intentSortValue(value: unknown): number {
  const normalized = rawText(value);
  const matched = normalized.match(/(\d+)$/u);
  return matched ? Number(matched[1]) : Number.MAX_SAFE_INTEGER;
}

function sortReviewItems(rows: Array<Record<string, unknown>>, sortDirection: SortDirection): Array<Record<string, unknown>> {
  const direction = sortDirection === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const leftValue = intentSortValue(left.intent_id);
    const rightValue = intentSortValue(right.intent_id);
    if (leftValue !== rightValue) {
      return (leftValue - rightValue) * direction;
    }
    return rawText(left.intent_id).localeCompare(rawText(right.intent_id), "zh-Hans-CN") * direction;
  });
}

function reviewStatusOf(item: Record<string, unknown>): ReviewStatus {
  const normalized = rawText(item.review_status).toLowerCase();
  if (normalized === "approved") {
    return "approved";
  }
  if (normalized === "rejected") {
    return "rejected";
  }
  return "pending";
}

function reviewStatusLabel(value: unknown): string {
  const normalized = rawText(value).toLowerCase();
  const labels: Record<string, string> = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已驳回",
  };
  return labels[normalized] || "待审核";
}

function reviewStatusDisplay(value: unknown): string {
  const normalized = rawText(value).toLowerCase();
  if (normalized === "approved") {
    return "✅ 已通过";
  }
  if (normalized === "rejected") {
    return "❌ 已驳回";
  }
  return "🟡 待审核";
}

function intentTypeLabel(value: unknown): string {
  const normalized = rawText(value).toLowerCase();
  const labels: Record<string, string> = {
    functional: "功能",
    positive: "正向",
    negative: "异常",
    business_exception: "业务异常",
    security: "安全",
    boundary: "边界",
    format: "格式",
    interaction_exception: "交互异常",
  };
  return labels[normalized] || text(value);
}

function bindingLabel(value: unknown): string {
  const normalized = rawText(value).toLowerCase();
  const labels: Record<string, string> = {
    bound: "已绑定",
    partial: "部分绑定",
    missing: "缺失元素",
    not_required: "无需元素",
  };
  return labels[normalized] || "待检查";
}

function blockerList(item: Record<string, unknown>): string[] {
  if (reviewStatusOf(item) === "rejected") {
    return [];
  }
  return asList(item.generation_blockers);
}

function blockerText(item: Record<string, unknown>): string {
  const blockers = blockerList(item);
  return blockers.length ? blockers.join("；") : "满足生成条件";
}

function stepActionLabel(value: unknown): string {
  const normalized = rawText(value);
  if (/点击/u.test(normalized)) {
    return "点击";
  }
  if (/输入|填写/u.test(normalized)) {
    return "输入";
  }
  if (/打开|访问|跳转|进入/u.test(normalized)) {
    return "导航";
  }
  if (/刷新/u.test(normalized)) {
    return "刷新";
  }
  if (/开启|模拟|设置/u.test(normalized)) {
    return "操作";
  }
  return "步骤";
}

function elementBindingRows(item: Record<string, unknown>): Array<Record<string, unknown>> {
  const bindings = asRecordList(item.element_bindings);
  if (bindings.length) {
    return bindings;
  }
  const elements = asList(item.involved_elements);
  const codes = asList(item.involved_element_codes);
  return elements.map((elementName, index) => ({
    element_name: elementName,
    binding_status: codes[index] ? "bound" : "missing",
    element_code: codes[index] || "",
    locator_type: "",
    locator_value: "",
    blocker: codes[index] ? "" : "元素未在 Page Object 注册或未审核通过",
  }));
}

function reviewHistoryRows(item: Record<string, unknown>): Array<Record<string, unknown>> {
  const history = asRecordList(item.review_history);
  if (history.length) {
    return history;
  }
  const reviewedAt = rawText(item.reviewed_at);
  if (!reviewedAt) {
    return [];
  }
  return [
    {
      reviewed_at: reviewedAt,
      reviewed_by: rawText(item.reviewed_by) || "admin",
      status: reviewStatusOf(item),
      note: rawText(item.review_note),
    },
  ];
}

export function CasesReviewPage() {
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [pageFilter, setPageFilter] = useState<string>("");
  const [keyword, setKeyword] = useState<string>("");
  const [status, setStatus] = useState<string>("pending");
  const [intentType, setIntentType] = useState<string>("");
  const [priority, setPriority] = useState<string>("");
  const [canGenerate, setCanGenerate] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [pagination, setPagination] = useState<TestPointReviewsResponse["pagination"]>({});
  const [pageSize, setPageSize] = useState<number>(20);
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");
  const [reviewTarget, setReviewTarget] = useState<{ keys: string[]; status: ReviewStatus; title: string } | null>(null);
  const [reviewNote, setReviewNote] = useState<string>("");
  const [detailItem, setDetailItem] = useState<Record<string, unknown> | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState<boolean>(false);
  const [scriptExpanded, setScriptExpanded] = useState<boolean>(false);
  const [blockersExpanded, setBlockersExpanded] = useState<boolean>(false);
  const [scriptPreview, setScriptPreview] = useState<string>("");
  const [scriptPreviewLoading, setScriptPreviewLoading] = useState<boolean>(false);
  const [scriptPreviewError, setScriptPreviewError] = useState<string>("");
  const [generatedTarget, setGeneratedTarget] = useState<{ assetId: string; count: number } | null>(null);

  const sortedItems = useMemo(() => {
    return sortReviewItems(items, sortDirection);
  }, [items, sortDirection]);

  const visibleKeys = useMemo(() => sortedItems.map((item) => reviewKeyOf(item)).filter(Boolean), [sortedItems]);
  const allSelected = Boolean(visibleKeys.length && visibleKeys.every((key) => selectedKeys.includes(key)));
  const selectedCount = selectedKeys.length;
  const pendingCount = Number(summary.pending_count || 0);
  const approvedCount = Number(summary.approved_count || 0);
  const rejectedCount = Number(summary.rejected_count || 0);
  const canGenerateCount = Number(summary.can_generate_count || 0);

  async function reload(
    targetPage = 1,
    targetProject = project,
    targetPageFilter = pageFilter,
    targetKeyword = keyword,
    targetStatus = status,
    targetIntentType = intentType,
    targetPriority = priority,
    targetCanGenerate = canGenerate,
    targetPageSize = pageSize,
  ): Promise<Array<Record<string, unknown>>> {
    setLoading(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await listTestPointReviews({
        project: targetProject || DEFAULT_PROJECT_CODE,
        page: targetPageFilter.trim(),
        keyword: targetKeyword.trim(),
        status: targetStatus.trim(),
        intent_type: targetIntentType.trim(),
        priority: targetPriority.trim(),
        can_generate: targetCanGenerate.trim(),
        page_index: targetPage,
        page_size: targetPageSize,
      });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      setSummary(payload.summary || {});
      setPagination(payload.pagination || {});
      const allowed = new Set(rows.map((item) => reviewKeyOf(item)).filter(Boolean));
      setSelectedKeys((prev) => prev.filter((key) => allowed.has(key)));
      setDetailItem((prev) => {
        if (!prev) {
          return null;
        }
        const currentKey = reviewKeyOf(prev);
        return rows.find((row) => reviewKeyOf(row) === currentKey) || prev;
      });
      return rows;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "待审核测试点加载失败");
      setItems([]);
      setSummary({});
      setPagination({});
      setSelectedKeys([]);
      return [];
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
        // Keep default option.
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

  function toggleItem(key: string) {
    const normalized = rawText(key);
    if (!normalized || saving) {
      return;
    }
    setSelectedKeys((prev) => (prev.includes(normalized) ? prev.filter((item) => item !== normalized) : [...prev, normalized]));
  }

  function toggleAll() {
    if (saving || !visibleKeys.length) {
      return;
    }
    setSelectedKeys((prev) => (allSelected ? prev.filter((key) => !visibleKeys.includes(key)) : Array.from(new Set([...prev, ...visibleKeys]))));
  }

  function openDetail(item: Record<string, unknown>) {
    setDetailItem(item);
    setHistoryExpanded(false);
    setScriptExpanded(false);
    setBlockersExpanded(false);
    setScriptPreview("");
    setScriptPreviewError("");
  }

  function detailIndex(): number {
    if (!detailItem) {
      return -1;
    }
    const key = reviewKeyOf(detailItem);
    return sortedItems.findIndex((item) => reviewKeyOf(item) === key);
  }

  async function moveDetail(offset: number) {
    const index = detailIndex();
    const next = sortedItems[index + offset];
    if (next) {
      openDetail(next);
      return;
    }
    const currentPage = Number(pagination?.page || 1);
    if (offset > 0 && pagination?.has_next) {
      const rows = await reload(currentPage + 1);
      const nextRows = sortReviewItems(rows, sortDirection);
      if (nextRows.length) {
        openDetail(nextRows[0]);
      }
      return;
    }
    if (offset < 0 && pagination?.has_prev) {
      const rows = await reload(Math.max(1, currentPage - 1));
      const prevRows = sortReviewItems(rows, sortDirection);
      if (prevRows.length) {
        openDetail(prevRows[prevRows.length - 1]);
      }
    }
  }

  function refreshDetailPatch(keys: string[], nextStatus: ReviewStatus, note: string) {
    const affected = new Set(keys);
    const reviewedAt = new Date().toISOString();
    setItems((prev) => prev.map((item) => {
      if (!affected.has(reviewKeyOf(item))) {
        return item;
      }
      const nextBlockers = asList(item.generation_blockers).filter((blocker) => !blocker.includes("测试点未审核通过"));
      return {
        ...item,
        review_status: nextStatus,
        review_note: note,
        reviewed_at: reviewedAt,
        reviewed_by: "admin",
        generation_blockers: nextStatus === "approved" ? nextBlockers : [],
        can_generate: nextStatus === "approved" && nextBlockers.length === 0,
        review_history: [
          ...reviewHistoryRows(item),
          {
            reviewed_at: reviewedAt,
            reviewed_by: "admin",
            status: nextStatus,
            note,
          },
        ],
      };
    }));
    setDetailItem((prev) => {
      if (!prev || !affected.has(reviewKeyOf(prev))) {
        return prev;
      }
      const nextBlockers = asList(prev.generation_blockers).filter((blocker) => !blocker.includes("测试点未审核通过"));
      return {
        ...prev,
        review_status: nextStatus,
        review_note: note,
        reviewed_at: reviewedAt,
        reviewed_by: "admin",
        generation_blockers: nextStatus === "approved" ? nextBlockers : [],
        can_generate: nextStatus === "approved" && nextBlockers.length === 0,
        review_history: [
          ...reviewHistoryRows(prev),
          {
            reviewed_at: reviewedAt,
            reviewed_by: "admin",
            status: nextStatus,
            note,
          },
        ],
      };
    });
  }

  async function applyReview(keys: string[], nextStatus: ReviewStatus, note = "") {
    const decisions = keys.map(decisionFromKey).filter((item): item is { asset_id: string; intent_id: string } => Boolean(item));
    if (!decisions.length || saving) {
      setReviewTarget(null);
      return;
    }
    const normalizedNote = note.trim();
    setSaving(true);
    setErrorText("");
    setFeedback("");
    setGeneratedTarget(null);
    try {
      const payload = await batchReviewTestPoints({
        project,
        decisions,
        status: nextStatus,
        note: normalizedNote,
        reviewed_by: "admin",
      });
      refreshDetailPatch(keys, nextStatus, normalizedNote);
      const firstAffected = detailItem && keys.includes(reviewKeyOf(detailItem)) ? detailItem : null;
      const remainingBlockers = firstAffected
        ? asList(firstAffected.generation_blockers).filter((blocker) => !blocker.includes("测试点未审核通过"))
        : [];
      const blockerSuffix = nextStatus === "approved" && remainingBlockers.length
        ? ` 当前仍有生成阻断：${remainingBlockers.join("；")}。`
        : "";
      setFeedback(`已${nextStatus === "approved" ? "通过" : "驳回"} ${Number(payload.updated_count || 0)} 条测试点。${blockerSuffix}`);
      setSelectedKeys([]);
      setReviewTarget(null);
      setReviewNote("");
      void reload(Number(pagination?.page || 1));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "批量审核更新失败");
    } finally {
      setSaving(false);
    }
  }

  async function generateFromDetail() {
    if (!detailItem || generating || !detailItem.can_generate) {
      return;
    }
    const assetId = rawText(detailItem.asset_id);
    const intentId = rawText(detailItem.intent_id);
    if (!assetId) {
      setErrorText("缺少来源资产，无法生成用例。");
      return;
    }
    if (!intentId) {
      setErrorText("缺少测试点 ID，无法生成用例。");
      return;
    }
    setGenerating(true);
    setErrorText("");
    setFeedback("");
    setGeneratedTarget(null);
    try {
      const response = await batchGenerateCasesFromTestPointAssets({
        project,
        asset_ids: [assetId],
        intent_ids: [intentId],
        source: "ai",
      });
      setFeedback(`已生成 ${Number(response.count || 0)} 条用例，可前往用例中心查看。`);
      setGeneratedTarget({ assetId, count: Number(response.count || 0) });
      void reload(Number(pagination?.page || 1));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "生成用例失败");
    } finally {
      setGenerating(false);
    }
  }

  async function toggleScriptPreview() {
    if (scriptExpanded) {
      setScriptExpanded(false);
      return;
    }
    setScriptExpanded(true);
    if (!detailItem || scriptPreviewLoading || scriptPreview) {
      return;
    }
    const assetId = rawText(detailItem.asset_id);
    const intentId = rawText(detailItem.intent_id);
    if (!assetId || !intentId) {
      setScriptPreviewError("缺少资产或测试点 ID，无法预览脚本。");
      return;
    }
    setScriptPreviewLoading(true);
    setScriptPreviewError("");
    try {
      const response = await getTestPointScriptPreview({
        project,
        asset_id: assetId,
        intent_id: intentId,
      });
      const item = response.item || {};
      setScriptPreview(rawText(item.script_code));
    } catch (error) {
      setScriptPreviewError(error instanceof Error ? error.message : "脚本预览加载失败");
    } finally {
      setScriptPreviewLoading(false);
    }
  }

  function openReviewConfirm(itemOrKeys: Record<string, unknown> | string[], nextStatus: ReviewStatus) {
    const keys = Array.isArray(itemOrKeys) ? itemOrKeys : [reviewKeyOf(itemOrKeys)].filter(Boolean);
    if (!keys.length) {
      return;
    }
    setReviewNote(Array.isArray(itemOrKeys) ? "" : rawText(itemOrKeys.review_note));
    setReviewTarget({
      keys,
      status: nextStatus,
      title: Array.isArray(itemOrKeys) ? `所选 ${keys.length} 条测试点` : text(itemOrKeys.title || itemOrKeys.intent_id),
    });
  }

  const detailStatus = detailItem ? reviewStatusOf(detailItem) : "pending";
  const detailBlockers = detailItem ? blockerList(detailItem) : [];
  const visibleDetailBlockers = blockersExpanded ? detailBlockers : detailBlockers.slice(0, 4);
  const currentDetailIndex = detailIndex();
  const hasPrevDetail = currentDetailIndex > 0 || Boolean(pagination?.has_prev);
  const hasNextDetail = (currentDetailIndex >= 0 && currentDetailIndex < sortedItems.length - 1) || Boolean(pagination?.has_next);
  const detailCanGenerate = Boolean(detailItem?.can_generate);
  const showScriptSection = detailStatus === "approved";
  const detailBlockerText = detailBlockers.length ? detailBlockers.join("；") : "";
  const detailPage = rawText(detailItem?.page);
  const pageObjectLink = detailPage
    ? `/assets/page-objects/${encodeURIComponent(detailPage)}/elements?project=${encodeURIComponent(project)}`
    : `/assets/page-objects?project=${encodeURIComponent(project)}`;
  const caseCenterLink = generatedTarget?.assetId
    ? `/cases?project=${encodeURIComponent(project)}&source_asset=${encodeURIComponent(generatedTarget.assetId)}`
    : `/cases?project=${encodeURIComponent(project)}`;

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>待审核用例</h1>
            <p className="muted">管理所有从需求解析出的测试点，逐条审核通过后可生成独立自动化用例。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(project)}`}>
              测试点资产
            </Link>
            <Link className="button secondary" to={`/cases?project=${encodeURIComponent(project)}`}>
              用例中心
            </Link>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card metric-tone-info">
            <span>当前列表</span>
            <strong>{Number(summary.total || items.length)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-warning">
            <span>待审核</span>
            <strong>{pendingCount}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>已通过</span>
            <strong>{approvedCount}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>可生成</span>
            <strong>{canGenerateCount}</strong>
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
          <label>
            页面
            <input value={pageFilter} onChange={(event) => setPageFilter(event.target.value)} placeholder="login" />
          </label>
          <label className="grow">
            关键词
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="资产标题 / 意图标题 / intent_id / 阻断原因" />
          </label>
          <label>
            审核状态
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">全部状态</option>
              <option value="pending">待审核</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
            </select>
          </label>
          <label>
            类型
            <select value={intentType} onChange={(event) => setIntentType(event.target.value)}>
              <option value="">全部类型</option>
              <option value="functional">功能</option>
              <option value="negative">异常</option>
              <option value="boundary">边界</option>
              <option value="format">格式</option>
              <option value="security">安全</option>
              <option value="interaction_exception">交互异常</option>
            </select>
          </label>
          <label>
            优先级
            <select value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">全部优先级</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
              <option value="P3">P3</option>
            </select>
          </label>
          <label>
            可生成状态
            <select value={canGenerate} onChange={(event) => setCanGenerate(event.target.value)}>
              <option value="">全部</option>
              <option value="ready">可生成</option>
              <option value="blocked">阻断</option>
            </select>
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reload(1)} disabled={loading || saving}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setPageFilter("");
                setKeyword("");
                setStatus("pending");
                setIntentType("");
                setPriority("");
                setCanGenerate("");
                setSelectedKeys([]);
                void reload(1, DEFAULT_PROJECT_CODE, "", "", "pending", "", "", "");
              }}
              disabled={loading || saving}
            >
              重置
            </button>
          </div>
        </section>

        <section className="asset-toolbar">
          <p className="muted">
            已选 {selectedCount} 条测试点 ｜ 已驳回 {rejectedCount} 条
          </p>
          <div className="asset-actions">
            <button type="button" className="button secondary" onClick={() => openReviewConfirm(selectedKeys, "approved")} disabled={!selectedCount || saving}>
              批量通过
            </button>
            <button type="button" className="button danger secondary" onClick={() => openReviewConfirm(selectedKeys, "rejected")} disabled={!selectedCount || saving}>
              批量驳回
            </button>
          </div>
        </section>
        <p className="asset-hint">提示：通过只更新审核状态；生成用例会基于资产中已通过且可生成的测试点执行。</p>

        <section className="asset-table-wrap">
          {loading ? <p>正在加载待审核测试点...</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
          {feedback ? (
            <p>
              {feedback}
              {generatedTarget ? (
                <>
                  {" "}
                  <Link to={caseCenterLink}>前往用例中心查看</Link>
                </>
              ) : null}
            </p>
          ) : null}
          {!loading && !errorText ? (
            <table className="workbench-list-table review-list-table">
              <thead>
                <tr>
                  <th>
                    <input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!visibleKeys.length || saving} />
                  </th>
                  <th>
                    <button
                      type="button"
                      className="table-sort-button"
                      onClick={() => setSortDirection((value) => (value === "desc" ? "asc" : "desc"))}
                    >
                      意图ID {sortDirection === "desc" ? "↓" : "↑"}
                    </button>
                  </th>
                  <th>意图标题</th>
                  <th>来源资产</th>
                  <th>页面</th>
                  <th>类型</th>
                  <th>优先级</th>
                  <th>审核状态</th>
                  <th>可生成状态</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {sortedItems.length ? (
                  sortedItems.map((item, index) => {
                    const key = reviewKeyOf(item);
                    const blockers = blockerText(item);
                    const assetId = rawText(item.asset_id);
                    const rowStatus = reviewStatusOf(item);
                    return (
                      <tr key={key || String(index)}>
                        <td>
                          <input type="checkbox" checked={selectedKeys.includes(key)} onChange={() => toggleItem(key)} disabled={!key || saving} />
                        </td>
                        <td>
                          <span className="mono">{text(item.intent_id)}</span>
                        </td>
                        <td>
                          <button type="button" className="link-button strong-link" onClick={() => openDetail(item)}>
                            {text(item.title || item.summary)}
                          </button>
                        </td>
                        <td>
                          {assetId ? (
                            <Link to={`/assets/test-points/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`}>
                              {text(item.asset_title)}
                            </Link>
                          ) : (
                            text(item.asset_title)
                          )}
                        </td>
                        <td>{text(item.page)}</td>
                        <td>{intentTypeLabel(item.intent_type)}</td>
                        <td>{text(item.priority)}</td>
                        <td>
                          <span className={`review-status-badge review-${rowStatus}`}>
                            {reviewStatusDisplay(rowStatus)}
                          </span>
                        </td>
                        <td title={blockers}>
                          {item.can_generate ? <span className="count-badge success">✅ 可生成</span> : <span className="count-badge warn">⚠ {bindingLabel(item.element_binding_status)}</span>}
                        </td>
                        <td>{formatDateTime(item.updated_at || item.reviewed_at)}</td>
                        <td>
                          <div className="asset-actions-inline">
                            {rowStatus === "pending" ? (
                              <>
                                <button type="button" className="link-button success-text" disabled={saving || !key} onClick={() => openReviewConfirm(item, "approved")}>
                                  通过
                                </button>
                                <button type="button" className="link-button danger-text" disabled={saving || !key} onClick={() => openReviewConfirm(item, "rejected")}>
                                  驳回
                                </button>
                              </>
                            ) : null}
                            <button type="button" className="link-button" onClick={() => openDetail(item)}>
                              详情
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={11} className="asset-empty">
                      当前筛选下没有测试点评审数据。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : null}
        </section>

        <TablePagination
          page={Number(pagination?.page || 1)}
          pageSize={pageSize}
          total={Number(pagination?.total_items || items.length)}
          onPageChange={(nextPage) => void reload(nextPage)}
          onPageSizeChange={(nextPageSize) => {
            setPageSize(nextPageSize);
            void reload(1, project, pageFilter, keyword, status, intentType, priority, canGenerate, nextPageSize);
          }}
        />
      </section>

      {detailItem ? (
        <section className="review-detail-backdrop" role="dialog" aria-modal="true" aria-label="测试点详情">
          <div className="review-detail-drawer detail-drawer detail-page--review">
            <header className="review-detail-topbar detail-drawer-header">
              <button type="button" className="link-button" onClick={() => setDetailItem(null)}>
                ← 返回待审核列表
              </button>
              <button type="button" className="button secondary" onClick={() => setDetailItem(null)}>
                × 关闭
              </button>
            </header>

            <div className="review-detail-scroll detail-drawer-body">
              {detailBlockers.length ? (
                <section className="review-blocker-card detail-alert">
                  <strong>⚠ 生成阻断</strong>
                  <ul>
                    {visibleDetailBlockers.map((blocker, index) => (
                      <li key={`${blocker}-${index}`}>{blocker}</li>
                    ))}
                  </ul>
                  {detailBlockers.length > 4 ? (
                    <button type="button" className="link-button" onClick={() => setBlockersExpanded((value) => !value)}>
                      {blockersExpanded ? "收起阻断原因" : `展开全部 ${detailBlockers.length} 条`}
                    </button>
                  ) : null}
                </section>
              ) : null}

              <section className="review-detail-actions-card detail-action-card">
                <div className="asset-actions">
                  <button type="button" className="button danger secondary" disabled={saving || detailStatus === "rejected"} onClick={() => openReviewConfirm(detailItem, "rejected")}>
                    {detailStatus === "rejected" ? "已驳回" : "驳回"}
                  </button>
                  <button type="button" className="button success" disabled={saving || detailStatus === "approved"} onClick={() => openReviewConfirm(detailItem, "approved")}>
                    {detailStatus === "rejected" ? "重新通过" : detailStatus === "approved" ? "✅ 已通过" : "通过"}
                  </button>
                </div>
                <div className="asset-actions">
                  <button type="button" className="button secondary" disabled={!hasPrevDetail} onClick={() => void moveDetail(-1)}>
                    ← 上一条
                  </button>
                  <button type="button" className="button secondary" disabled={!hasNextDetail} onClick={() => void moveDetail(1)}>
                    下一条 →
                  </button>
                </div>
              </section>

              <section className="review-detail-card detail-hero detail-hero--compact">
                <p className="review-detail-label detail-field-label">测试点标题</p>
                <h2 className="detail-title">
                  {text(detailItem.title || detailItem.summary)}
                  <span className="page-title-code detail-mono"> / {text(detailItem.intent_id)}</span>
                </h2>
                <p className="detail-subtitle">
                  所属资产：
                  {detailItem.asset_id ? (
                    <a
                      href={`/react/assets/test-points/${encodeURIComponent(String(detailItem.asset_id))}?project=${encodeURIComponent(project)}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {text(detailItem.asset_title)} ↗
                    </a>
                  ) : (
                    text(detailItem.asset_title)
                  )}
                </p>
                <div className="review-info-grid detail-field-grid">
                  <div className="detail-field">
                    <span className="detail-field-label">页面</span>
                    <strong className="detail-field-value">{text(detailItem.page)}</strong>
                  </div>
                  <div className="detail-field">
                    <span className="detail-field-label">类型</span>
                    <strong className="detail-field-value">{intentTypeLabel(detailItem.intent_type)}</strong>
                  </div>
                  <div className="detail-field">
                    <span className="detail-field-label">优先级</span>
                    <strong className="detail-field-value">{text(detailItem.priority)}</strong>
                  </div>
                  <div className="detail-field">
                    <span className="detail-field-label">审核状态</span>
                    <strong className="detail-field-value">{reviewStatusDisplay(detailStatus)}</strong>
                  </div>
                </div>
              </section>

              <section className="review-detail-card detail-section">
                <h3 className="detail-section-title">前置条件</h3>
                <p className="detail-section-body">{text(detailItem.precondition)}</p>
              </section>

              <section className="review-detail-card detail-section">
                <h3 className="detail-section-title">操作步骤</h3>
                <table className="review-steps-table detail-table detail-table--steps">
                  <thead>
                    <tr>
                      <th>序号</th>
                      <th>步骤描述</th>
                      <th>动作类型</th>
                    </tr>
                  </thead>
                  <tbody>
                    {asList(detailItem.steps).length ? (
                      asList(detailItem.steps).map((step, index) => (
                        <tr key={`${step}-${index}`}>
                          <td>{index + 1}</td>
                          <td>{step}</td>
                          <td>{stepActionLabel(step)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={3}>暂无操作步骤。</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </section>

              <section className="review-detail-card detail-section">
                <h3 className="detail-section-title">预期结果</h3>
                <p className="detail-section-body">{text(detailItem.expected)}</p>
              </section>

              <section className="review-detail-card detail-section">
                <h3 className="detail-section-title">涉及元素绑定</h3>
                <table className="review-element-table detail-table detail-table--elements">
                  <thead>
                    <tr>
                      <th>元素名称</th>
                      <th>绑定结果</th>
                      <th>定位器</th>
                      <th>元素编码</th>
                    </tr>
                  </thead>
                  <tbody>
                    {elementBindingRows(detailItem).length ? (
                      elementBindingRows(detailItem).map((row, index) => {
                        const statusValue = rawText(row.binding_status);
                        const locator = [rawText(row.locator_type), rawText(row.locator_value)].filter(Boolean).join("=");
                        return (
                          <tr key={`${rawText(row.element_name)}-${index}`}>
                            <td>{text(row.element_name)}</td>
                            <td>{statusValue === "bound" ? "✅ 已绑定" : statusValue === "not_required" ? "无需元素" : "❌ 元素缺失"}</td>
                            <td className="mono">{locator || text(row.blocker)}</td>
                            <td className="mono">{text(row.element_code)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={4}>暂无涉及元素。</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </section>

              <section className="review-detail-card detail-section">
                <button type="button" className="review-collapse-button" onClick={() => setHistoryExpanded((value) => !value)}>
                  {historyExpanded ? "▼ 收起审核历史" : "▶ 展开审核历史"}
                </button>
                {historyExpanded ? (
                  <table className="review-history-table detail-table detail-table--history">
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>审核人</th>
                        <th>动作</th>
                        <th>备注</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reviewHistoryRows(detailItem).length ? (
                        reviewHistoryRows(detailItem).map((row, index) => (
                          <tr key={`${rawText(row.reviewed_at)}-${index}`}>
                            <td>{formatDateTime(row.reviewed_at)}</td>
                            <td>{text(row.reviewed_by)}</td>
                            <td>{reviewStatusLabel(row.status)}</td>
                            <td>{text(row.note)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4}>暂无审核历史。</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                ) : null}
              </section>

              {showScriptSection ? (
                <section className="review-detail-card detail-section">
                  {detailCanGenerate ? (
                    <>
                      <button type="button" className="review-collapse-button" onClick={() => void toggleScriptPreview()}>
                        {scriptExpanded ? "▼ 收起生成脚本预览" : "▶ 点击展开预览生成的 pytest 脚本"}
                      </button>
                      {scriptExpanded ? (
                        <>
                          {scriptPreviewLoading ? <p className="muted">正在生成脚本预览...</p> : null}
                          {scriptPreviewError ? <p className="error">{scriptPreviewError}</p> : null}
                          {!scriptPreviewLoading && !scriptPreviewError ? (
                            <pre className="detail-code">{scriptPreview || "暂无脚本预览。"}</pre>
                          ) : null}
                        </>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <h3>生成脚本预览</h3>
                      <p className="asset-hint warning">
                        当前测试点已通过审核，但还不能生成脚本。请先解除阻断：{detailBlockerText || "生成条件未满足"}。
                      </p>
                      <div className="asset-actions">
                        <Link className="button secondary" to={pageObjectLink}>
                          去页面对象管理补齐
                        </Link>
                      </div>
                    </>
                  )}
                </section>
              ) : null}
            </div>

            <footer className="review-detail-footer detail-drawer-footer">
              <button type="button" className="button danger secondary" disabled={saving || detailStatus === "rejected"} onClick={() => openReviewConfirm(detailItem, "rejected")}>
                {detailStatus === "rejected" ? "已驳回" : "驳回"}
              </button>
              <div className="asset-actions">
                {detailCanGenerate ? (
                  <button type="button" className="button" disabled={generating} onClick={() => void generateFromDetail()}>
                    {generating ? "生成中..." : "生成用例"}
                  </button>
                ) : detailStatus === "approved" ? (
                  <button type="button" className="button secondary" disabled title={detailBlockerText || "当前测试点还不能生成用例"}>
                    生成用例（需解除阻断）
                  </button>
                ) : null}
                <button type="button" className="button success" disabled={saving || detailStatus === "approved"} onClick={() => openReviewConfirm(detailItem, "approved")}>
                  {detailStatus === "rejected" ? "重新通过" : detailStatus === "approved" ? "✅ 已通过" : "通过"}
                </button>
                <button type="button" className="button secondary" disabled={!hasPrevDetail} onClick={() => void moveDetail(-1)}>
                  ← 上一条
                </button>
                <button type="button" className="button secondary" disabled={!hasNextDetail} onClick={() => void moveDetail(1)}>
                  下一条 →
                </button>
              </div>
            </footer>
          </div>
        </section>
      ) : null}

      {reviewTarget ? (
        <ConfirmDialog
          title={reviewTarget.status === "approved" ? "确认通过测试点" : "确认驳回测试点"}
          description={reviewTarget.status === "approved" ? "确认通过此测试点？通过后可参与生成用例。" : "请填写驳回原因（可选），便于后续修改。"}
          confirmText={reviewTarget.status === "approved" ? "确认通过" : "确认驳回"}
          danger={reviewTarget.status === "rejected"}
          busy={saving}
          details={[reviewTarget.title, `数量：${reviewTarget.keys.length}`]}
          noteLabel={reviewTarget.status === "rejected" ? "驳回原因" : undefined}
          noteValue={reviewNote}
          notePlaceholder="可选：请说明驳回原因"
          noteRequired={false}
          onNoteChange={setReviewNote}
          onCancel={() => {
            setReviewTarget(null);
            setReviewNote("");
          }}
          onConfirm={() => void applyReview(reviewTarget.keys, reviewTarget.status, reviewNote)}
        />
      ) : null}
    </main>
  );
}
