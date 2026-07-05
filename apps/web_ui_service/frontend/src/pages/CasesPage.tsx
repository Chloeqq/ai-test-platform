import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  batchDeleteWorkbenchTestCases,
  deleteWorkbenchTestCase,
  getWorkbenchRun,
  listWorkbenchTestCases,
  runWorkbenchCase,
  type WorkbenchTestCasesResponse,
} from "../api/assets";
import { listProjects } from "../api/workbench";
import { TablePagination } from "../components/TablePagination";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";
import { toReactReportUrl } from "../lib/reportUrls";
import { buildRuntimeDesktopUrl } from "../lib/runtimeDesktop";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function intentTypeLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
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

function executionLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    passed: "通过",
    failed: "失败",
    skipped: "跳过",
    running: "执行中",
    unknown: "未执行",
  };
  return labels[normalized] || text(value);
}

function activeStatusLabel(value: unknown): string {
  return String(value || "").trim().toLowerCase() === "deprecated" ? "🛑 已废弃" : "✅ 活跃";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function waitForRunTerminal(runId: string, onStatus?: (status: string) => void): Promise<string> {
  const terminalStatuses = new Set(["passed", "failed", "cancelled", "skipped", "error"]);
  let lastStatus = "queued";
  for (let index = 0; index < 90; index += 1) {
    const payload = await getWorkbenchRun(runId);
    const item = (payload.item || payload) as Record<string, unknown>;
    const executionRecord = item.execution_record && typeof item.execution_record === "object" ? (item.execution_record as Record<string, unknown>) : {};
    lastStatus = String(item.status || executionRecord.status || lastStatus || "queued").trim().toLowerCase();
    onStatus?.(lastStatus);
    if (terminalStatuses.has(lastStatus)) {
      return lastStatus;
    }
    await sleep(2000);
  }
  return lastStatus;
}

export function CasesPage() {
  const [searchParams] = useSearchParams();
  const [project, setProject] = useState<string>(normalizeProjectCode(searchParams.get("project") || DEFAULT_PROJECT_CODE));
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [pageFilter, setPageFilter] = useState<string>(searchParams.get("page") || "");
  const [sourceAsset, setSourceAsset] = useState<string>(searchParams.get("source_asset") || "");
  const [intentType, setIntentType] = useState<string>("");
  const [priority, setPriority] = useState<string>("");
  const [executionStatus, setExecutionStatus] = useState<string>("");
  const [activeStatus, setActiveStatus] = useState<string>("active");
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [pagination, setPagination] = useState<WorkbenchTestCasesResponse["pagination"]>({});
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyCaseId, setBusyCaseId] = useState<string>("");
  const [clearingAll, setClearingAll] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const runtimeDesktopUrl = buildRuntimeDesktopUrl();

  async function reload(
    targetPage = 1,
    targetProject = project,
    targetPageFilter = pageFilter,
    targetSourceAsset = sourceAsset,
    targetIntentType = intentType,
    targetPriority = priority,
    targetExecutionStatus = executionStatus,
    targetActiveStatus = activeStatus,
    targetKeyword = keyword,
    targetPageSize = pageSize,
  ) {
    setLoading(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await listWorkbenchTestCases({
        project: normalizeProjectCode(targetProject),
        page: targetPageFilter.trim(),
        source_asset: targetSourceAsset.trim(),
        intent_type: targetIntentType.trim(),
        priority: targetPriority.trim(),
        execution_status: targetExecutionStatus.trim(),
        active_status: targetActiveStatus.trim(),
        keyword: targetKeyword.trim(),
        page_index: targetPage,
        page_size: targetPageSize,
      });
      setItems(Array.isArray(payload.items) ? payload.items : []);
      setSummary(payload.summary || {});
      setPagination(payload.pagination || {});
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例中心加载失败");
      setItems([]);
      setSummary({});
      setPagination({});
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
          const codes = projectOptions(projects.codes);
          setProjectCodes(codes);
        }
      } catch {
        // Keep default project option.
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

  async function executeCase(caseId: string) {
    const normalizedCaseId = String(caseId || "").trim();
    if (!normalizedCaseId || busyCaseId) {
      return;
    }
    setBusyCaseId(normalizedCaseId);
    setErrorText("");
    setFeedback("");
    try {
      window.open(runtimeDesktopUrl, "aitest-runtime-desktop");
      const response = await runWorkbenchCase({
        project,
        case_id: normalizedCaseId,
        source: "case_center",
      });
      const item = (response.item || response) as Record<string, unknown>;
      const runId = String(item.run_id || item.id || "").trim();
      setFeedback(
        runId
          ? `已提交执行任务：${runId}。可打开实时桌面观察执行过程，完成后会自动刷新执行记录。`
          : "已提交执行任务。",
      );
      let finalFeedback = "";
      if (runId) {
        const finalStatus = await waitForRunTerminal(runId, (status) => {
          setFeedback(`执行任务 ${runId} 当前状态：${executionLabel(status)}。可打开实时桌面观察，完成后查看报告、录屏和执行记录。`);
        });
        finalFeedback = `执行任务 ${runId} 已完成：${executionLabel(finalStatus)}。执行历史、报告和录屏入口已同步到用例中心。`;
      }
      await reload(Number(pagination?.page || 1));
      if (finalFeedback) {
        setFeedback(finalFeedback);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "执行用例失败");
    } finally {
      setBusyCaseId("");
    }
  }

  async function deleteCase(caseId: string, title: unknown) {
    const normalizedCaseId = String(caseId || "").trim();
    if (!normalizedCaseId || busyCaseId || clearingAll) {
      return;
    }
    const confirmed = window.confirm(
      `确认物理删除用例「${text(title)}」(${normalizedCaseId})？\n\n此操作会删除用例、步骤、版本、执行历史和关联文件，无法恢复。`,
    );
    if (!confirmed) {
      return;
    }
    setBusyCaseId(normalizedCaseId);
    setErrorText("");
    setFeedback("");
    try {
      const response = await deleteWorkbenchTestCase(normalizedCaseId, project);
      const deletedCount = Number(response.deleted_count || 0);
      setFeedback(deletedCount > 0 ? `已物理删除用例：${normalizedCaseId}` : "未删除任何用例。");
      const currentPage = Number(pagination?.page || 1);
      const nextPage = items.length <= 1 && currentPage > 1 ? currentPage - 1 : currentPage;
      await reload(nextPage);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "删除用例失败");
    } finally {
      setBusyCaseId("");
    }
  }

  async function clearProjectCases() {
    if (loading || clearingAll || busyCaseId) {
      return;
    }
    const expected = `清空${project}`;
    const input = window.prompt(
      `将物理删除当前项目「${project}」在用例中心的所有用例。\n\n这会同步删除步骤、版本、执行历史和关联文件，无法恢复。\n请输入「${expected}」确认。`,
    );
    if (input !== expected) {
      setFeedback("已取消清空操作。");
      return;
    }
    setClearingAll(true);
    setErrorText("");
    setFeedback("");
    try {
      const response = await batchDeleteWorkbenchTestCases({
        project,
        delete_all: true,
        confirm_text: input,
      });
      setFeedback(`已物理删除当前项目 ${project} 的 ${Number(response.deleted_count || 0)} 条用例。`);
      await reload(1);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "清空用例中心失败");
    } finally {
      setClearingAll(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>用例中心</h1>
            <p className="muted">管理所有已生成的自动化测试用例，可执行、查看报告和追溯来源资产。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to={`/cases/review?project=${encodeURIComponent(project)}`}>
              待审核用例
            </Link>
            <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(project)}`}>
              测试点资产
            </Link>
            <button type="button" className="button danger secondary" onClick={() => void clearProjectCases()} disabled={loading || clearingAll}>
              {clearingAll ? "清空中..." : "清空当前项目用例"}
            </button>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card metric-tone-info">
            <span>当前列表</span>
            <strong>{Number(summary.total || items.length)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>活跃用例</span>
            <strong>{Number(summary.active_count || 0)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>通过</span>
            <strong>{Number(summary.passed_count || 0)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-danger">
            <span>失败</span>
            <strong>{Number(summary.failed_count || 0)}</strong>
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
          <label>
            来源资产
            <input value={sourceAsset} onChange={(event) => setSourceAsset(event.target.value)} placeholder="资产标题/编码" />
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
            执行状态
            <select value={executionStatus} onChange={(event) => setExecutionStatus(event.target.value)}>
              <option value="">全部</option>
              <option value="passed">通过</option>
              <option value="failed">失败</option>
              <option value="unknown">未执行</option>
            </select>
          </label>
          <label>
            活跃状态
            <select value={activeStatus} onChange={(event) => setActiveStatus(event.target.value)}>
              <option value="active">活跃</option>
              <option value="deprecated">已废弃</option>
              <option value="">全部</option>
            </select>
          </label>
          <label className="grow">
            搜索
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="标题/编码" />
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reload(1)} disabled={loading}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setPageFilter("");
                setSourceAsset("");
                setIntentType("");
                setPriority("");
                setExecutionStatus("");
                setActiveStatus("active");
                setKeyword("");
                void reload(1, DEFAULT_PROJECT_CODE, "", "", "", "", "", "active", "");
              }}
              disabled={loading}
            >
              重置
            </button>
          </div>
        </section>

        <section className="asset-table-wrap">
          {loading ? <p>正在加载用例中心...</p> : null}
          {errorText ? <p className="error">{errorText}</p> : null}
          <div className="execution-visibility-hint">
            <span>执行会在容器桌面中启动浏览器；如需看过程，请先打开实时桌面。</span>
            <a href={runtimeDesktopUrl} target="_blank" rel="noreferrer">
              打开实时桌面
            </a>
          </div>
          {feedback ? (
            <p className="case-feedback-inline">
              {feedback}
              <a href={runtimeDesktopUrl} target="_blank" rel="noreferrer">
                实时桌面
              </a>
            </p>
          ) : null}
          {!loading && !errorText ? (
            <table className="workbench-list-table case-center-table">
              <thead>
                <tr>
                  <th>用例编码</th>
                  <th>用例标题</th>
                  <th>来源资产</th>
                  <th>页面</th>
                  <th>类型</th>
                  <th>优先级</th>
                  <th>活跃状态</th>
                  <th>上次执行</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.length ? (
                  items.map((item, index) => {
                    const caseId = String(item.case_id || "").trim();
                    const sourceAssetId = String(item.source_asset_id || "").trim();
                    const reportUrl = toReactReportUrl(item.last_report_url);
                    return (
                      <tr key={caseId || String(index)}>
                        <td className="mono">{text(caseId)}</td>
                        <td>
                          {caseId ? <Link to={`/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`}>{text(item.title)}</Link> : text(item.title)}
                        </td>
                        <td>
                          {sourceAssetId ? (
                            <Link to={`/assets/test-points/${encodeURIComponent(sourceAssetId)}?project=${encodeURIComponent(project)}`}>
                              {text(item.source_asset_title || sourceAssetId)}
                            </Link>
                          ) : (
                            "-"
                          )}
                        </td>
                        <td>{text(item.page)}</td>
                        <td>{intentTypeLabel(item.intent_type)}</td>
                        <td>{text(item.priority)}</td>
                        <td>{activeStatusLabel(item.active_status)}</td>
                        <td>
                          {String(item.last_execution_result || "").trim() && String(item.last_execution_result).trim() !== "unknown"
                            ? `${formatDateTime(item.last_executed_at)} ${executionLabel(item.last_execution_result)}`
                            : "- (未执行)"}
                        </td>
                        <td>
                          <div className="asset-actions-inline">
                            {caseId ? <Link to={`/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(project)}`}>查看</Link> : null}
                            {item.active_status !== "deprecated" ? (
                              <button type="button" className="link-button" disabled={!caseId || busyCaseId === caseId || clearingAll} onClick={() => void executeCase(caseId)}>
                                执行
                              </button>
                            ) : null}
                            {reportUrl ? <a href={reportUrl}>报告</a> : <span className="muted">报告</span>}
                            <button
                              type="button"
                              className="link-button danger-text"
                              disabled={!caseId || busyCaseId === caseId || clearingAll}
                              onClick={() => void deleteCase(caseId, item.title)}
                            >
                              删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={9} className="asset-empty">
                      当前筛选下没有已生成用例。
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
            void reload(1, project, pageFilter, sourceAsset, intentType, priority, executionStatus, activeStatus, keyword, nextPageSize);
          }}
        />
      </section>
    </main>
  );
}
