import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { getTestPointAsset, updateTestPointAsset } from "../api/assets";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { normalizeProjectCode } from "../config/projects";

interface EditableCandidate {
  intentId: string;
  title: string;
  summary: string;
  intentType: string;
  priority: string;
  precondition: string;
  stepsText: string;
  expected: string;
  involvedElementsText: string;
  raw: Record<string, unknown>;
}

interface AssetEditorForm {
  title: string;
  page: string;
  priority: string;
  requirement: string;
  sourceType: string;
  sourceLabel: string;
}

const EMPTY_FORM: AssetEditorForm = {
  title: "",
  page: "",
  priority: "P1",
  requirement: "",
  sourceType: "manual",
  sourceLabel: "手动保存",
};

function text(value: unknown): string {
  return String(value || "").trim();
}

function displayText(value: unknown): string {
  return text(value) || "-";
}

function sourceLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    selection_save: "来自 AI 生成",
    generate_chain: "AI 生成链路",
    requirement_intents: "AI 需求解析",
    manual: "手动保存",
    yaml_case: "YAML 用例同步",
    fallback: "系统兜底生成",
    openapi_spec: "OpenAPI 导入",
  };
  const normalized = text(sourceType).toLowerCase();
  return labels[normalized] || text(sourceType) || "未知来源";
}

function listText(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => text(item)).filter(Boolean);
}

const LOGIN_INVOLVED_ELEMENT_ALIASES: Record<string, string> = {
  "用户名输入框": "username_input",
  "账号输入框": "username_input",
  "用户名": "username_input",
  "账号": "username_input",
  "密码输入框": "password_input",
  "密码": "password_input",
  "登录按钮": "login_button",
  "登录": "login_button",
  "首页菜单": "home_menu",
  "首页": "home_menu",
  "工作台首页": "home_menu",
};

function normalizeInvolvedElements(value: unknown, page: unknown): string[] {
  const rows = Array.isArray(value) ? listText(value) : splitElements(String(value || ""));
  if (String(page || "").trim() !== "login") {
    return Array.from(new Set(rows));
  }
  const normalized: string[] = [];
  rows.forEach((row) => {
    const elementCode = LOGIN_INVOLVED_ELEMENT_ALIASES[row] || row;
    if (elementCode && !normalized.includes(elementCode)) {
      normalized.push(elementCode);
    }
  });
  return normalized;
}

function stepTextList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows: string[] = [];
  value.forEach((raw) => {
    if (typeof raw === "string") {
      const row = raw.trim();
      if (row) {
        rows.push(row);
      }
      return;
    }
    if (raw && typeof raw === "object") {
      const item = raw as Record<string, unknown>;
      const row = text(item.raw_text || item.value || item.description || item.action);
      if (row) {
        rows.push(row);
      }
    }
  });
  return rows;
}

function splitLines(value: string): string[] {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitElements(value: string): string[] {
  return String(value || "")
    .split(/[\n,，]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function requirementFromItem(item: Record<string, unknown>): string {
  const plan = (item.plan || {}) as Record<string, unknown>;
  const metadata = (plan.metadata || {}) as Record<string, unknown>;
  const normalizedRequirement = text(metadata.normalized_requirement || metadata.raw_requirement || metadata.original_requirement);
  if (normalizedRequirement) {
    return normalizedRequirement;
  }
  const itemRequirement = item.requirement;
  if (Array.isArray(itemRequirement)) {
    return itemRequirement.map((row) => text(row)).filter(Boolean).join("\n");
  }
  const planRequirement = plan.requirement;
  if (Array.isArray(planRequirement)) {
    return planRequirement.map((row) => text(row)).filter(Boolean).join("\n");
  }
  return text(itemRequirement || planRequirement);
}

function snapshotFromPoint(point: Record<string, unknown>): Record<string, unknown> {
  const metadata = (point.metadata || {}) as Record<string, unknown>;
  const snapshot = (metadata.candidate_snapshot || {}) as Record<string, unknown>;
  if (snapshot && typeof snapshot === "object" && Object.keys(snapshot).length) {
    return {
      ...snapshot,
      ...point,
    };
  }
  return point;
}

function candidateFromRow(row: Record<string, unknown>, index: number, fallbackPriority: string, page: unknown): EditableCandidate {
  const intentId = text(row.intent_id || row.intentId || row.key) || `intent-${String(index + 1).padStart(2, "0")}`;
  const title = text(row.title || row.summary || row.description || intentId) || intentId;
  const summary = text(row.summary || row.title || row.description || title) || title;
  const steps = stepTextList(row.steps);
  const elements = normalizeInvolvedElements(row.involved_elements || row.involvedElements, page);
  return {
    intentId,
    title,
    summary,
    intentType: text(row.intent_type || row.intentType || row.point_type) || "functional",
    priority: text(row.priority) || fallbackPriority || "P1",
    precondition: text(row.precondition),
    stepsText: steps.join("\n"),
    expected: text(row.expected || row.expected_result),
    involvedElementsText: elements.join(", "),
    raw: row,
  };
}

function candidatesFromItem(item: Record<string, unknown>): EditableCandidate[] {
  const plan = (item.plan || {}) as Record<string, unknown>;
  const metadata = (plan.metadata || {}) as Record<string, unknown>;
  const fallbackPriority = text(item.priority || plan.priority) || "P1";
  const points = Array.isArray(plan.points) ? plan.points : [];
  if (points.length) {
    return points
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .map((point, index) => candidateFromRow(snapshotFromPoint(point), index, fallbackPriority, item.page || plan.page));
  }
  const selectedCandidates = Array.isArray(metadata.selected_candidates) ? metadata.selected_candidates : [];
  const candidateRows = selectedCandidates.filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"));
  if (candidateRows.length) {
    return candidateRows.map((row, index) => candidateFromRow(row, index, fallbackPriority, item.page || plan.page));
  }
  return [];
}

function payloadPoint(candidate: EditableCandidate, index: number, page: unknown): Record<string, unknown> {
  const expected = text(candidate.expected);
  const intentId = text(candidate.intentId) || `intent-${String(index + 1).padStart(2, "0")}`;
  const pointType = text(candidate.intentType) || "functional";
  const steps = splitLines(candidate.stepsText).map((step) => ({
    action: "candidate_step",
    target: "",
    value: step,
    raw_text: step,
  }));
  return {
    ...candidate.raw,
    key: text((candidate.raw || {}).key) || intentId,
    intent_id: intentId,
    title: text(candidate.title),
    description: text(candidate.summary || candidate.title),
    summary: text(candidate.summary || candidate.title),
    point_type: pointType,
    intent_type: pointType,
    priority: text(candidate.priority) || "P1",
    precondition: text(candidate.precondition),
    steps,
    expected,
    expected_result: expected,
    involved_elements: normalizeInvolvedElements(candidate.involvedElementsText, page),
  };
}

export function TestPointAssetEditPage() {
  const params = useParams<{ assetId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const assetId = text(params.assetId);
  const project = useMemo(() => {
    const query = new URLSearchParams(location.search);
    return normalizeProjectCode(query.get("project"));
  }, [location.search]);
  const [form, setForm] = useState<AssetEditorForm>(EMPTY_FORM);
  const [candidates, setCandidates] = useState<EditableCandidate[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!assetId) {
        setErrorText("缺少 asset_id");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorText("");
      setActionText("");
      try {
        const payload = await getTestPointAsset(assetId, project);
        const item = (payload.item || {}) as Record<string, unknown>;
        const plan = (item.plan || {}) as Record<string, unknown>;
        const rows = candidatesFromItem(item);
        if (!cancelled) {
          setForm({
            title: text(item.title || plan.title || assetId),
            page: text(item.page || plan.page),
            priority: text(item.priority || plan.priority) || "P1",
            requirement: requirementFromItem(item),
            sourceType: text(item.source_type || plan.source_type) || "manual",
            sourceLabel: text(item.source_label) || sourceLabel(text(item.source_type || plan.source_type)),
          });
          setCandidates(rows);
          setSelectedIndex(0);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "测试点资产加载失败");
          setCandidates([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [assetId, project]);

  const currentCandidate = candidates[selectedIndex];
  const detailUrl = `/assets/test-points/${encodeURIComponent(assetId)}?project=${encodeURIComponent(project)}`;
  const listUrl = `/assets/test-points?project=${encodeURIComponent(project)}`;

  function updateCurrentCandidate(patch: Partial<EditableCandidate>) {
    setCandidates((prev) => prev.map((candidate, index) => (index === selectedIndex ? { ...candidate, ...patch } : candidate)));
  }

  async function submitEditor() {
    const normalizedPage = text(form.page);
    if (!assetId) {
      setErrorText("asset_id 不能为空。");
      return;
    }
    if (!normalizedPage) {
      setErrorText("页面(page)不能为空。");
      return;
    }
    if (!candidates.length) {
      setErrorText("至少需要保留一条测试点。");
      return;
    }
    const invalidIndex = candidates.findIndex((candidate) => !text(candidate.intentId) || !text(candidate.title));
    if (invalidIndex >= 0) {
      setSelectedIndex(invalidIndex);
      setErrorText(`第 ${invalidIndex + 1} 条测试点缺少 intent_id 或标题。`);
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const payload = await updateTestPointAsset(assetId, {
        project,
        asset_id: assetId,
        page: normalizedPage,
        title: text(form.title) || assetId,
        priority: text(form.priority) || "P1",
        requirement: text(form.requirement) || text(form.title) || assetId,
        source_type: text(form.sourceType) || "manual",
        points: candidates.map((candidate, index) => payloadPoint(candidate, index, normalizedPage)),
      });
      const item = (payload.item || {}) as Record<string, unknown>;
      const plan = (item.plan || {}) as Record<string, unknown>;
      const persistedRows = candidatesFromItem(item);
      if (Object.keys(item).length) {
        setForm({
          title: text(item.title || plan.title || assetId),
          page: text(item.page || plan.page),
          priority: text(item.priority || plan.priority) || "P1",
          requirement: requirementFromItem(item),
          sourceType: text(item.source_type || plan.source_type) || text(form.sourceType) || "manual",
          sourceLabel: text(item.source_label) || sourceLabel(text(item.source_type || plan.source_type || form.sourceType)),
        });
      }
      if (persistedRows.length) {
        setCandidates(persistedRows);
        setSelectedIndex((prev) => Math.min(prev, persistedRows.length - 1));
      }
      setActionText("测试点资产已保存，全部测试点明细已同步更新。");
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "测试点资产保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>编辑测试点资产</h1>
          <p className="muted">下钻维护资产内的全部测试点，保存时会提交完整测试点数组。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={detailUrl}>
            返回详情
          </Link>
          <Link className="button secondary" to={listUrl}>
            返回列表
          </Link>
        </div>
      </header>

      {loading ? <section className="panel">正在加载编辑数据...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {actionText ? <section className="panel">{actionText}</section> : null}

      {!loading ? (
        <section className="panel">
          <div className="table-head">
            <div>
              <h2>资产信息</h2>
              <p className="muted">这里维护资产级字段；测试点级字段在下方逐条切换编辑。</p>
            </div>
            <span className="muted">资产编码：<span className="mono">{displayText(assetId)}</span></span>
          </div>
          <div className="form-grid">
            <label className="span-2">
              标题
              <input
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label>
              页面
              <input
                value={form.page}
                onChange={(event) => setForm((prev) => ({ ...prev, page: event.target.value }))}
                disabled={busy}
              />
            </label>
            <label>
              优先级
              <select
                value={form.priority}
                onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
                disabled={busy}
              >
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
              </select>
            </label>
            <label>
              来源
              <input
                value={form.sourceLabel}
                disabled
              />
            </label>
            <label className="span-3">
              需求原文
              <textarea
                rows={6}
                value={form.requirement}
                onChange={(event) => setForm((prev) => ({ ...prev, requirement: event.target.value }))}
                disabled={busy}
              />
            </label>
          </div>
        </section>
      ) : null}

      {!loading ? (
        <section className="panel test-point-editor-panel">
          <div className="table-head">
            <div>
              <h2>测试点编辑</h2>
              <p className="muted">左侧切换测试点，右侧编辑当前条目。不会再只绑定第一条测试点。</p>
            </div>
            <span className="muted">共 {candidates.length} 条，当前第 {candidates.length ? selectedIndex + 1 : 0} 条</span>
          </div>
          {candidates.length && currentCandidate ? (
            <div className="test-point-editor-layout">
              <aside className="intent-switcher" aria-label="测试点切换">
                <label>
                  快速切换
                  <select
                    value={selectedIndex}
                    onChange={(event) => setSelectedIndex(Number(event.target.value))}
                    disabled={busy}
                  >
                    {candidates.map((candidate, index) => (
                      <option key={`${candidate.intentId}-${index}`} value={index}>
                        {index + 1}. {candidate.intentId} - {candidate.title || candidate.summary}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="intent-list">
                  {candidates.map((candidate, index) => (
                    <button
                      key={`${candidate.intentId}-${index}`}
                      type="button"
                      className={index === selectedIndex ? "intent-list-item is-active" : "intent-list-item"}
                      onClick={() => setSelectedIndex(index)}
                      disabled={busy}
                    >
                      <span className="mono">{candidate.intentId || `intent-${index + 1}`}</span>
                      <strong>{candidate.title || candidate.summary || "未命名测试点"}</strong>
                      <small>{candidate.intentType || "functional"} ｜ {candidate.priority || "P1"}</small>
                    </button>
                  ))}
                </div>
              </aside>

              <div className="intent-editor form-grid">
                <label>
                  intent_id
                  <input
                    value={currentCandidate.intentId}
                    onChange={(event) => updateCurrentCandidate({ intentId: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label>
                  类型
                  <input
                    value={currentCandidate.intentType}
                    onChange={(event) => updateCurrentCandidate({ intentType: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label>
                  优先级
                  <select
                    value={currentCandidate.priority}
                    onChange={(event) => updateCurrentCandidate({ priority: event.target.value })}
                    disabled={busy}
                  >
                    <option value="P0">P0</option>
                    <option value="P1">P1</option>
                    <option value="P2">P2</option>
                  </select>
                </label>
                <label className="span-3">
                  标题
                  <input
                    value={currentCandidate.title}
                    onChange={(event) => updateCurrentCandidate({ title: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label className="span-3">
                  摘要
                  <input
                    value={currentCandidate.summary}
                    onChange={(event) => updateCurrentCandidate({ summary: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label className="span-3">
                  前置条件
                  <input
                    value={currentCandidate.precondition}
                    onChange={(event) => updateCurrentCandidate({ precondition: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label className="span-3">
                  步骤（每行一条）
                  <textarea
                    rows={7}
                    value={currentCandidate.stepsText}
                    onChange={(event) => updateCurrentCandidate({ stepsText: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label className="span-3">
                  预期结果
                  <textarea
                    rows={4}
                    value={currentCandidate.expected}
                    onChange={(event) => updateCurrentCandidate({ expected: event.target.value })}
                    disabled={busy}
                  />
                </label>
                <label className="span-3">
                  涉及元素（逗号或换行分隔）
                  <input
                    value={currentCandidate.involvedElementsText}
                    onChange={(event) => updateCurrentCandidate({ involvedElementsText: event.target.value })}
                    disabled={busy}
                  />
                </label>
              </div>
            </div>
          ) : (
            <EmptyState title="暂无可编辑测试点" description="当前资产详情没有返回 plan.points 或 selected_candidates，请先检查资产保存结果。" />
          )}
          <div className="header-actions sticky-action-row">
            <div className="sticky-action-feedback" role="status" aria-live="polite">
              {actionText ? <span className="inline-feedback success">{actionText}</span> : null}
              {errorText ? <span className="inline-feedback error">{errorText}</span> : null}
              {!actionText && !errorText ? <span className="muted">保存会提交当前资产内全部 {candidates.length} 条测试点。</span> : null}
            </div>
            <div className="header-actions">
              <button type="button" className="button" onClick={() => void submitEditor()} disabled={busy || !candidates.length}>
                {busy ? "保存中..." : "保存全部测试点"}
              </button>
              <button type="button" className="button secondary" onClick={() => navigate(detailUrl)} disabled={busy}>
                取消
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {!loading ? (
        <DataTable title="全部测试点预览" actions={<span className="muted">保存会提交这 {candidates.length} 条</span>}>
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>intent_id</th>
                <th>标题</th>
                <th>类型</th>
                <th>优先级</th>
                <th>步骤数</th>
                <th>涉及元素</th>
              </tr>
            </thead>
            <tbody>
              {candidates.length ? (
                candidates.map((candidate, index) => (
                  <tr key={`${candidate.intentId}-${index}`} className={index === selectedIndex ? "is-active" : ""}>
                    <td>{index + 1}</td>
                    <td className="mono">{displayText(candidate.intentId)}</td>
                    <td>{displayText(candidate.title || candidate.summary)}</td>
                    <td>{displayText(candidate.intentType)}</td>
                    <td>{displayText(candidate.priority)}</td>
                    <td>{splitLines(candidate.stepsText).length}</td>
                    <td className="mono">{splitElements(candidate.involvedElementsText).join(", ") || "-"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>
                    <EmptyState title="暂无测试点" description="没有可预览的测试点数据。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTable>
      ) : null}
    </main>
  );
}
