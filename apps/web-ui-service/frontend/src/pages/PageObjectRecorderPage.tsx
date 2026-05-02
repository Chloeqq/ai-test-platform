import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  batchDeleteRecorderSessions,
  createRecorderSession,
  getRecorderSessionPlayback,
  heartbeatRecorderSession,
  listRecorderSessions,
  replayRecorderSession,
  stopRecorderSession,
} from "../api/assets";
import { BulkActionBar } from "../components/BulkActionBar";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

interface RecorderForm {
  project_code: string;
  client: string;
  page_code: string;
  page_name: string;
  url: string;
  started_by: string;
}

const DEFAULT_FORM: RecorderForm = {
  project_code: DEFAULT_PROJECT_CODE,
  client: "web",
  page_code: "",
  page_name: "",
  url: "",
  started_by: "admin",
};

function text(value: unknown): string {
  const normalized = String(value ?? "").trim();
  return normalized || "-";
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item) => Boolean(item) && typeof item === "object") as Array<Record<string, unknown>>;
}

function describeStep(step: Record<string, unknown>): string {
  const action = text(step.action);
  const locatorType = String(step.locator_type || "").trim();
  const locatorValue = String(step.locator_value || "").trim();
  const role = String(step.role || "").trim();
  const value = String(step.value || "").trim();
  const locator = locatorType && locatorValue ? `${locatorType}${role ? `(${role})` : ""}=${locatorValue}` : locatorValue;
  if (value) {
    return `${action} ${locator || ""} -> ${value}`.trim();
  }
  return `${action} ${locator || ""}`.trim();
}

export function PageObjectRecorderPage() {
  const params = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const routeSessionId = String(params.sessionId || "").trim();
  const isPlaybackDetailRoute = Boolean(routeSessionId);
  const [form, setForm] = useState<RecorderForm>({
    ...DEFAULT_FORM,
    project_code: normalizeProjectCode(searchParams.get("project") || DEFAULT_FORM.project_code),
    page_code: searchParams.get("page_code") || "",
    page_name: searchParams.get("page_name") || "",
    url: searchParams.get("url") || "",
  });
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [payload, setPayload] = useState<Record<string, unknown>>({});
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyRows, setHistoryRows] = useState<Array<Record<string, unknown>>>([]);
  const [selectedHistorySessionIds, setSelectedHistorySessionIds] = useState<string[]>([]);
  const [historyStatus, setHistoryStatus] = useState<string>("");
  const [playbackPayload, setPlaybackPayload] = useState<Record<string, unknown>>({});
  const [playbackCursor, setPlaybackCursor] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [replayLoading, setReplayLoading] = useState<boolean>(false);
  const [replayResult, setReplayResult] = useState<Record<string, unknown>>({});
  const [deleteHistoryOpen, setDeleteHistoryOpen] = useState<boolean>(false);
  const timerRef = useRef<number | null>(null);

  const playbackSession = useMemo(() => asRecord(playbackPayload.session), [playbackPayload]);
  const playbackSteps = useMemo(() => asRecordList(playbackPayload.recorded_steps), [playbackPayload]);
  const playbackScript = useMemo(() => String(playbackPayload.script_code || ""), [playbackPayload]);
  const playbackStderr = useMemo(() => String(playbackPayload.stderr_tail || ""), [playbackPayload]);
  const visibleHistorySessionIds = useMemo(() => historyRows.map((item) => String(item.session_id || "").trim()).filter(Boolean), [historyRows]);
  const allHistorySelected = visibleHistorySessionIds.length > 0 && visibleHistorySessionIds.every((item) => selectedHistorySessionIds.includes(item));
  const currentPayload = useMemo(() => {
    const item = asRecord(payload.item);
    return Object.keys(item).length ? item : payload;
  }, [payload]);
  const currentStatus = String(currentPayload.status || "").trim().toLowerCase();
  const isRecording = Boolean(sessionId.trim() && currentStatus !== "stopped" && currentStatus !== "failed");
  const currentSummary = useMemo(() => {
    const nested = asRecord(currentPayload.candidate_summary);
    return Object.keys(nested).length ? nested : currentPayload;
  }, [currentPayload]);
  const elementsLink = useMemo(() => {
    const query = new URLSearchParams();
    const projectCode = normalizeProjectCode(form.project_code);
    if (projectCode) {
      query.set("project", projectCode);
    }
    return form.page_code.trim()
      ? `/assets/page-objects/${encodeURIComponent(form.page_code.trim())}/elements?${query.toString()}`
      : "/assets/page-objects";
  }, [form.page_code, form.project_code]);
  const candidateReviewLink = useMemo(() => {
    const query = new URLSearchParams();
    const projectCode = normalizeProjectCode(form.project_code);
    if (projectCode) {
      query.set("project", projectCode);
    }
    query.set("tab", "candidates");
    if (sessionId.trim()) {
      query.set("session_id", sessionId.trim());
    }
    return form.page_code.trim()
      ? `/assets/page-objects/${encodeURIComponent(form.page_code.trim())}/elements?${query.toString()}`
      : "/assets/page-objects";
  }, [form.page_code, form.project_code, sessionId]);

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopReplay() {
    clearTimer();
    setIsPlaying(false);
  }

  function resetReplay() {
    stopReplay();
    setPlaybackCursor(0);
  }

  function startReplay() {
    if (playbackSteps.length <= 0) {
      setFeedback("该录制会话没有可回放步骤。");
      return;
    }
    stopReplay();
    setPlaybackCursor(0);
    setIsPlaying(true);
    let nextCursor = 0;
    const runNext = () => {
      nextCursor += 1;
      setPlaybackCursor(nextCursor);
      if (nextCursor >= playbackSteps.length) {
        setIsPlaying(false);
        timerRef.current = null;
        return;
      }
      timerRef.current = window.setTimeout(runNext, 900);
    };
    timerRef.current = window.setTimeout(runNext, 280);
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const response = await listRecorderSessions({
        project_code: normalizeProjectCode(form.project_code),
        client: form.client.trim() || "web",
        page_code: form.page_code.trim() || undefined,
        status: historyStatus.trim() || undefined,
        limit: 30,
        offset: 0,
      });
      const rows = asRecordList(response.items);
      setHistoryRows(rows);
      const nextSessionIds = new Set(rows.map((item) => String(item.session_id || "").trim()).filter(Boolean));
      setSelectedHistorySessionIds((prev) => prev.filter((item) => nextSessionIds.has(item)));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "加载录制历史失败");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadPlayback(targetSessionId: string) {
    if (!targetSessionId.trim()) {
      return;
    }
    try {
      const response = await getRecorderSessionPlayback(targetSessionId);
      const item = asRecord(response.item);
      setPlaybackPayload(item);
      setPlaybackCursor(0);
      setIsPlaying(false);
      setReplayResult({});
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "加载录制回放失败");
    }
  }

  async function handleReplayExecution() {
    const targetSessionId = String(playbackSession.session_id || sessionId || "").trim();
    if (!targetSessionId) {
      setFeedback("请先选择一条录制历史。");
      return;
    }
    setReplayLoading(true);
    setFeedback("正在执行真实回放，请在 noVNC 桌面中观察浏览器动作...");
    try {
      const response = await replayRecorderSession(targetSessionId, { timeout_seconds: 180 });
      const item = asRecord(response.item);
      setReplayResult(item);
      const status = String(item.status || "").trim();
      setFeedback(status === "passed" ? "真实回放执行通过。" : `真实回放执行结束：${status || "unknown"}`);
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "真实回放执行失败");
    } finally {
      setReplayLoading(false);
    }
  }

  function toggleHistorySelection(sessionId: string) {
    const normalized = sessionId.trim();
    if (!normalized) {
      return;
    }
    setSelectedHistorySessionIds((prev) => (prev.includes(normalized) ? prev.filter((item) => item !== normalized) : [...prev, normalized]));
  }

  function toggleAllHistorySelection(checked: boolean) {
    setSelectedHistorySessionIds(checked ? Array.from(new Set(visibleHistorySessionIds)) : []);
  }

  async function batchRemoveHistoryRows() {
    if (!selectedHistorySessionIds.length || loading) {
      return;
    }
    setDeleteHistoryOpen(true);
  }

  async function confirmBatchRemoveHistoryRows() {
    setLoading(true);
    setFeedback("正在物理删除录制历史...");
    try {
      const response = await batchDeleteRecorderSessions(
        { session_ids: selectedHistorySessionIds, delete_artifacts: true },
        { project_code: normalizeProjectCode(form.project_code), client: form.client.trim() || "web" },
      );
      const item = asRecord(response.item);
      setFeedback(`录制历史已物理删除：${text(item.deleted_session_count)} 条。`);
      setSelectedHistorySessionIds([]);
      setDeleteHistoryOpen(false);
      await loadHistory();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量删除录制历史失败");
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
          setForm((prev) => (codes.includes(prev.project_code) ? prev : { ...prev, project_code: codes[0] || DEFAULT_PROJECT_CODE }));
        }
      } catch {
        // Keep default project option.
      }
    }
    void loadProjectOptions();
    if (routeSessionId) {
      void loadPlayback(routeSessionId);
    } else {
      void loadHistory();
    }
    return () => {
      cancelled = true;
      clearTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSessionId]);

  async function handleCreate() {
    if (loading) {
      return;
    }
    if (!form.page_code.trim() || !form.page_name.trim() || !form.url.trim()) {
      setFeedback("page_code/page_name/url 为必填。");
      return;
    }
    setLoading(true);
    setFeedback("正在创建录制会话...");
    try {
      const response = await createRecorderSession({
        project_code: normalizeProjectCode(form.project_code),
        client: form.client.trim() || "web",
        page_code: form.page_code.trim(),
        page_name: form.page_name.trim(),
        url: form.url.trim(),
        started_by: form.started_by.trim() || "admin",
      });
      const item = (response.item || {}) as Record<string, unknown>;
      const nextSessionId = String(item.session_id || item.id || "").trim();
      setSessionId(nextSessionId);
      setPayload(item);
      setFeedback(nextSessionId ? "录制窗口已启动，请在桌面环境完成操作，结束后回到这里停止录制。" : "录制窗口已启动。");
      await loadHistory();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "创建会话失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleHeartbeat() {
    if (loading || !sessionId.trim()) {
      return;
    }
    setLoading(true);
    setFeedback("正在发送心跳...");
    try {
      const response = await heartbeatRecorderSession(sessionId.trim(), {
        heartbeat_by: form.started_by.trim() || "admin",
      });
      const item = (response.item || {}) as Record<string, unknown>;
      setPayload(item);
      setFeedback("心跳已更新。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "心跳失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    if (loading || !sessionId.trim()) {
      return;
    }
    setLoading(true);
    setFeedback("正在停止会话并处理录制产物...");
    try {
      const response = await stopRecorderSession(sessionId.trim(), {
        cascade_elements: false,
        verify_locators: false,
        verify_timeout_ms: 4000,
        changed_by: form.started_by.trim() || "admin",
      });
      setPayload((response || {}) as Record<string, unknown>);
      setFeedback("会话已停止。");
      await loadHistory();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "停止会话失败");
    } finally {
      setLoading(false);
    }
  }

  function renderPlaybackDetail() {
    return (
      <section className="panel">
        <div className="table-head">
          <h2>回放详情</h2>
          <div className="header-actions">
            <button type="button" className="button" disabled={!playbackSteps.length || replayLoading} onClick={() => void handleReplayExecution()}>
              {replayLoading ? "执行中..." : "执行真实回放"}
            </button>
            <button type="button" className="button secondary" disabled={!playbackSteps.length || isPlaying} onClick={startReplay}>
              播放步骤预览
            </button>
            <button type="button" className="button secondary" disabled={!isPlaying} onClick={stopReplay}>
              停止
            </button>
            <button type="button" className="button secondary" disabled={!playbackSteps.length} onClick={resetReplay}>
              重置
            </button>
            <Link className="button secondary" to="/assets/page-objects/recorder">
              返回录制页
            </Link>
          </div>
        </div>
        <p>
          <strong>当前会话：</strong>
          <span className="mono"> {text(playbackSession.session_id || routeSessionId)}</span>
          <span className="muted">（{text(playbackSession.status)}）</span>
        </p>
        <p className="muted">
          回放进度：{playbackSteps.length ? `${Math.min(playbackCursor, playbackSteps.length)}/${playbackSteps.length}` : "-"}
        </p>
        {Object.keys(replayResult).length ? (
          <div className="summary-grid">
            <div>
              <strong>真实回放状态</strong>
              <span>{text(replayResult.status)}</span>
            </div>
            <div>
              <strong>退出码</strong>
              <span>{text(replayResult.exit_code)}</span>
            </div>
            <div>
              <strong>耗时</strong>
              <span>{text(replayResult.duration_seconds)}s</span>
            </div>
          </div>
        ) : null}
        <ol className="recorder-steps">
          {playbackSteps.length ? (
            playbackSteps.map((step, index) => {
              const isActive = playbackCursor === index + 1;
              const isDone = playbackCursor > index + 1;
              return (
                <li key={`step-${index + 1}`} className={`recorder-step${isActive ? " active" : ""}${isDone ? " done" : ""}`}>
                  <span className="mono">#{text(step.index || index + 1)}</span>
                  <span>{describeStep(step)}</span>
                </li>
              );
            })
          ) : (
            <li className="recorder-step">正在加载回放详情，或该会话暂无可回放步骤。</li>
          )}
        </ol>
        <h3>录制脚本</h3>
        <pre className="json-block">{playbackScript || "暂无脚本内容"}</pre>
        {String(replayResult.stderr_tail || "").trim() ? (
          <>
            <h3>真实回放 stderr</h3>
            <pre className="json-block">{String(replayResult.stderr_tail || "")}</pre>
          </>
        ) : null}
        {String(replayResult.stdout_tail || "").trim() ? (
          <>
            <h3>真实回放 stdout</h3>
            <pre className="json-block">{String(replayResult.stdout_tail || "")}</pre>
          </>
        ) : null}
        {playbackStderr ? (
          <>
            <h3>stderr</h3>
            <pre className="json-block">{playbackStderr}</pre>
          </>
        ) : null}
      </section>
    );
  }

  if (isPlaybackDetailRoute) {
    return (
      <main className="page shell">
        <header className="header panel">
          <div>
            <h1>录制回放详情</h1>
          <p className="muted">从录制历史下钻进入，独立查看步骤、脚本和真实回放结果。</p>
          </div>
          <div className="header-actions">
            <Link className="button secondary" to="/assets/page-objects/recorder">
              返回录制页
            </Link>
          </div>
        </header>
        {feedback ? <section className="panel">{feedback}</section> : null}
        {renderPlaybackDetail()}
      </main>
    );
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>{form.page_name.trim() || "页面对象录制"}<span className="page-title-code"> / {text(form.page_code)}</span></h1>
          <p className="muted">发起页面录制，停止后生成候选元素，再进入元素列表审核治理。</p>
          <p className="muted">
            录制依赖后端所在环境具备可交互桌面（Display/XServer）。若部署在纯服务容器中，创建会话会失败并给出原因提示。
          </p>
          <div className="asset-pill-strip page-meta-strip">
            <span className="asset-pill">项目：{text(form.project_code)}</span>
            <span className="asset-pill">页面：{text(form.page_code)}</span>
            <span className="asset-pill">URL：{text(form.url)}</span>
          </div>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={elementsLink}>
            返回元素列表
          </Link>
          <button type="button" className="button secondary" onClick={() => void loadHistory()} disabled={loading || historyLoading}>
            刷新
          </button>
          {isRecording ? (
            <button type="button" className="button danger" onClick={() => void handleStop()} disabled={loading || !sessionId.trim()}>
              停止录制
            </button>
          ) : (
            <button type="button" className="button" onClick={() => void handleCreate()} disabled={loading}>
              开始录制
            </button>
          )}
        </div>
      </header>

      <section className="panel form-grid recorder-config-card">
        <label>
          项目
          <select
            value={form.project_code}
            onChange={(event) => setForm((prev) => ({ ...prev, project_code: normalizeProjectCode(event.target.value) }))}
          >
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label>
          端类型
          <input value={form.client} onChange={(event) => setForm((prev) => ({ ...prev, client: event.target.value }))} />
        </label>
        <label>
          录制人
          <input value={form.started_by} onChange={(event) => setForm((prev) => ({ ...prev, started_by: event.target.value }))} />
        </label>
        <label>
          页面编码
          <input value={form.page_code} onChange={(event) => setForm((prev) => ({ ...prev, page_code: event.target.value }))} />
        </label>
        <label>
          页面名称
          <input value={form.page_name} onChange={(event) => setForm((prev) => ({ ...prev, page_name: event.target.value }))} />
        </label>
        <label className="span-3">
          录制地址
          <input value={form.url} onChange={(event) => setForm((prev) => ({ ...prev, url: event.target.value }))} />
        </label>
      </section>

      <section className="panel recorder-session-card">
        <div className="table-head">
          <div>
            <h2>当前会话</h2>
            <p className="muted">录制启动后请在 noVNC/桌面浏览器中完成页面操作。</p>
          </div>
          <div className="header-actions">
            <button type="button" className="button secondary" onClick={() => void handleHeartbeat()} disabled={loading || !sessionId.trim()}>
              更新心跳
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                stopReplay();
                setForm({ ...DEFAULT_FORM });
                setSessionId("");
                setPayload({});
                setPlaybackPayload({});
                setPlaybackCursor(0);
                setReplayResult({});
                setFeedback("表单已重置，可快速新建录制会话。");
              }}
            >
              重新录制
            </button>
          </div>
        </div>
        <div className="summary-grid">
          <div>
            <strong>状态</strong>
            <span><span className={`status-pill recorder-${currentStatus || "unknown"}`}>{text(currentPayload.status || (sessionId ? "active" : "未开始"))}</span></span>
          </div>
          <div>
            <strong>会话 ID</strong>
            <span className="mono">{text(sessionId || currentPayload.session_id)}</span>
          </div>
          <div>
            <strong>脚本路径</strong>
            <span className="mono compact-text">{text(currentPayload.script_path)}</span>
          </div>
        </div>
        <p className={String(feedback || "").includes("失败") ? "error" : "muted"}>{text(feedback || "未开始录制。")}</p>
      </section>

      {String(currentPayload.status || "").trim().toLowerCase() === "stopped" ? (
        <section className="panel recorder-result-card">
          <div className="table-head">
            <div>
              <h2>本次录制已完成</h2>
              <p className="muted">候选元素已进入治理池，请继续到元素列表审核。</p>
            </div>
            <Link className="button" to={candidateReviewLink}>
              去元素列表审核
            </Link>
          </div>
          <div className="summary-grid">
            <div><strong>候选总数</strong><span>{text(currentSummary.candidate_count)}</span></div>
            <div><strong>候选分组数</strong><span>{text(currentSummary.candidate_group_count)}</span></div>
            <div><strong>推荐可提升数</strong><span>{text(currentSummary.promote_count || currentSummary.recommended_promote_count)}</span></div>
            <div><strong>页面匹配状态</strong><span>{text(currentSummary.page_match_status || "已匹配")}</span></div>
            <div><strong>回放步骤数</strong><span>{text(currentSummary.recorded_step_count || currentPayload.recorded_step_count)}</span></div>
          </div>
          <div className="header-actions">
            <button type="button" className="button secondary" onClick={() => navigate(`/assets/page-objects/recorder/sessions/${encodeURIComponent(sessionId.trim())}`)} disabled={!sessionId.trim()}>
              查看回放
            </button>
            <button type="button" className="button secondary" onClick={() => navigate(`/assets/page-objects/recorder/sessions/${encodeURIComponent(sessionId.trim())}`)} disabled={!sessionId.trim()}>
              查看脚本
            </button>
            <button type="button" className="button secondary" onClick={() => setSessionId("")}>
              重新录制
            </button>
          </div>
        </section>
      ) : null}

      <section className="panel form-grid">
        <label>
          历史状态筛选
          <select value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value)}>
            <option value="">全部</option>
            <option value="active">录制中</option>
            <option value="stopped">已停止</option>
            <option value="failed">失败</option>
          </select>
        </label>
        <div className="span-2 header-actions" style={{ alignItems: "end" }}>
          <button type="button" className="button secondary" onClick={() => void loadHistory()} disabled={historyLoading}>
            {historyLoading ? "加载中..." : "查询录制历史"}
          </button>
          <span className="muted">历史条数：{historyRows.length}</span>
        </div>
      </section>

      <DataTable
        title="页面录制历史"
        actions={(
          <BulkActionBar selectedCount={selectedHistorySessionIds.length}>
            <button type="button" className="button secondary" onClick={() => void batchRemoveHistoryRows()} disabled={loading || !selectedHistorySessionIds.length}>
              批量删除
            </button>
          </BulkActionBar>
        )}
      >
        <table>
          <thead>
            <tr>
              <th>
                <input type="checkbox" checked={allHistorySelected} onChange={(event) => toggleAllHistorySelection(event.target.checked)} disabled={loading || !visibleHistorySessionIds.length} />
              </th>
              <th>session_id</th>
              <th>页面</th>
              <th>状态</th>
              <th>候选数</th>
              <th>候选组</th>
              <th>已提升</th>
              <th>已拒绝</th>
              <th>步骤数</th>
              <th>开始时间</th>
              <th>停止时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {historyRows.length ? (
              historyRows.map((row, index) => {
                const rowSessionId = String(row.session_id || "").trim();
                const nestedSummary = asRecord(row.candidate_summary);
                const summary = Object.keys(nestedSummary).length ? nestedSummary : row;
                const reviewLink = row.page_code
                  ? `/assets/page-objects/${encodeURIComponent(String(row.page_code))}/elements?project=${encodeURIComponent(normalizeProjectCode(String(row.project_code || form.project_code)))}&tab=candidates&session_id=${encodeURIComponent(rowSessionId)}`
                  : "";
                return (
                  <tr key={rowSessionId || String(row.id || index)}>
                    <td>
                      <input type="checkbox" checked={Boolean(rowSessionId && selectedHistorySessionIds.includes(rowSessionId))} onChange={() => toggleHistorySelection(rowSessionId)} disabled={loading || !rowSessionId} />
                    </td>
                    <td className="mono">{text(rowSessionId)}</td>
                    <td>{text(row.page_name)} ({text(row.page_code)})</td>
                    <td><span className={`status-pill recorder-${String(row.status || "").trim().toLowerCase()}`}>{text(row.status)}</span></td>
                    <td>{text(summary.candidate_count)}</td>
                    <td>{text(summary.candidate_group_count)}</td>
                    <td>{text(summary.promoted_count)}</td>
                    <td>{text(summary.rejected_count)}</td>
                    <td>{text(row.recorded_step_count)}</td>
                    <td>{formatDateTime(row.started_at)}</td>
                    <td>{formatDateTime(row.stopped_at)}</td>
                    <td>
                      <div className="header-actions">
                        {rowSessionId ? (
                          <Link className="button secondary" to={`/assets/page-objects/recorder/sessions/${encodeURIComponent(rowSessionId)}`}>
                            查看回放
                          </Link>
                        ) : null}
                        {reviewLink && Number(summary.candidate_group_count || 0) > 0 ? (
                          <Link className="button secondary" to={reviewLink} aria-disabled={!Number(summary.candidate_group_count || 0)}>
                            去审核
                          </Link>
                        ) : rowSessionId ? (
                          <button type="button" className="button secondary" disabled>
                            去审核
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={12}>
                  <EmptyState title="暂无录制历史" description="完成一次录制后，这里会展示回放和候选摘要。" />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </DataTable>
      {deleteHistoryOpen ? (
        <ConfirmDialog
          title="确认物理删除录制历史"
          description="录制历史删除后不可在平台中继续回放。"
          danger
          busy={loading}
          confirmText="确认删除"
          details={[`将删除 ${selectedHistorySessionIds.length} 条录制历史`, "关联候选和本地录制脚本产物会一起删除"]}
          onCancel={() => setDeleteHistoryOpen(false)}
          onConfirm={() => void confirmBatchRemoveHistoryRows()}
        />
      ) : null}

    </main>
  );
}
