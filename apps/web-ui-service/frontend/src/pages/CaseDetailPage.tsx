import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { batchGenerateCasesFromTestPointAssets, batchUpdateTestCaseStatus, getWorkbenchRun, getWorkbenchTestCase, runWorkbenchCase } from "../api/assets";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode } from "../config/projects";
import { formatDateTime } from "../lib/datetime";
import { toReactReportUrl } from "../lib/reportUrls";
import { buildRuntimeDesktopUrl } from "../lib/runtimeDesktop";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
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

function intentTypeLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    functional: "功能",
    negative: "异常",
    boundary: "边界",
    format: "格式",
    security: "安全",
    interaction_exception: "交互异常",
  };
  return labels[normalized] || text(value);
}

function rawText(value: unknown): string {
  return String(value ?? "").trim();
}

function targetCodeOf(step: Record<string, unknown>): string {
  return rawText(step.target).replace(/^element:/u, "");
}

function friendlyElementName(code: string, fallback?: unknown): string {
  const normalized = rawText(fallback);
  if (normalized) {
    return normalized;
  }
  const labels: Record<string, string> = {
    username_input: "用户名输入框",
    password_input: "密码输入框",
    login_button: "登录按钮",
    remember_password_checkbox: "记住密码复选框",
    password_toggle: "密码显隐开关",
    home_menu: "首页菜单",
    logout_option: "退出登录按钮",
  };
  return labels[code] || code || "目标元素";
}

function traceabilityRawText(step: Record<string, unknown>): string {
  const traceability = step.traceability;
  if (!traceability || typeof traceability !== "object") {
    return "";
  }
  return rawText((traceability as Record<string, unknown>).raw_text);
}

function semanticTargetName(step: Record<string, unknown>, targetCode: string): string {
  const candidates = [
    rawText(step.raw_text),
    traceabilityRawText(step),
    rawText(step.description),
  ].filter(Boolean);
  const merged = candidates.join(" ");
  if (/密码输入框|输入密码|password_input|input:密码/u.test(merged)) {
    return "密码输入框";
  }
  if (/账号输入框|用户名输入框|输入账号|输入用户名|username_input|input:账号|input:用户名/u.test(merged)) {
    return "用户名输入框";
  }
  if (/登录按钮|点击登录|login_button|click:登录/u.test(merged)) {
    return "登录按钮";
  }
  if (/记住密码|remember_password/u.test(merged)) {
    return "记住密码复选框";
  }
  const hintMatch = merged.match(/(?:input|fill|click|点击|输入)[:：]?\s*([^=\s，,。；;]+)/iu);
  const hintedName = rawText(hintMatch?.[1]).replace(/^(在|点击)/u, "").replace(/输入$/u, "");
  if (hintedName && !["input", "fill", "click"].includes(hintedName.toLowerCase())) {
    return hintedName;
  }
  return friendlyElementName(targetCode, step.target_name);
}

function actionLabel(value: unknown): string {
  const normalized = rawText(value).toLowerCase();
  const labels: Record<string, string> = {
    goto: "打开",
    navigate: "打开",
    fill: "输入",
    input: "输入",
    click: "点击",
    assert_visible: "断言可见",
    assert_text: "断言文本",
    assert_url: "断言地址",
    wait_for: "等待",
    login: "登录",
  };
  return labels[normalized] || text(value);
}

function stepActionKind(action: string): string {
  if (["goto", "navigate"].includes(action)) {
    return "url";
  }
  if (["fill", "input", "type"].includes(action)) {
    return "input";
  }
  if (action === "click") {
    return "click";
  }
  if (action.startsWith("assert")) {
    return "assert";
  }
  if (action.includes("wait")) {
    return "wait";
  }
  return "operation";
}

function stepDisplay(step: unknown, index: number): { title: string; action: string; value: string; kind: string } {
  if (!step || typeof step !== "object") {
    return { title: typeof step === "string" ? step : `步骤 ${index + 1}`, action: "操作", value: "-", kind: "operation" };
  }
  const row = step as Record<string, unknown>;
  const action = rawText(row.action).toLowerCase();
  const targetCode = targetCodeOf(row);
  const targetName = semanticTargetName(row, targetCode);
  const value = rawText(row.value ?? row.step_data);
  if (action === "goto" || action === "navigate") {
    return { title: "打开登录页面", action: "目标 URL", value: value || targetCode || "-", kind: "url" };
  }
  if (action === "fill" || action === "input") {
    return { title: `在${targetName}输入`, action: "输入", value, kind: "input" };
  }
  if (action === "click") {
    return { title: `点击${targetName}`, action: "点击", value: targetCode || targetName, kind: "click" };
  }
  return {
    title: [actionLabel(action), targetName].filter(Boolean).join(" "),
    action: actionLabel(action),
    value: value || targetCode || "-",
    kind: stepActionKind(action),
  };
}

function locatorText(step: Record<string, unknown>): string {
  const locatorType = rawText(step.locator_type);
  const locatorValue = rawText(step.locator_value);
  if (!locatorType && !locatorValue) {
    return "-";
  }
  return [locatorType, locatorValue].filter(Boolean).join("=");
}

function isSuspiciousBinding(step: Record<string, unknown>): boolean {
  const action = rawText(step.action).toLowerCase();
  const code = targetCodeOf(step).toLowerCase();
  const name = rawText(step.target_name).toLowerCase();
  const semanticName = semanticTargetName(step, code).toLowerCase();
  const locator = rawText(step.locator_value).toLowerCase();
  if (action === "input" || action === "fill") {
    if ((name.includes("密码") || semanticName.includes("密码") || name.includes("password")) && (code.includes("remember") || code.includes("checkbox") || locator.includes("记住密码"))) {
      return true;
    }
    if ((semanticName.includes("用户名") || semanticName.includes("账号") || name.includes("用户名") || name.includes("账号") || name.includes("username")) && !code.includes("username") && !code.includes("account")) {
      return true;
    }
  }
  return false;
}

function bindingStatus(step: Record<string, unknown>): { className: string; label: string } {
  if (isSuspiciousBinding(step)) {
    return { className: "case-bind-bad", label: "错误绑定" };
  }
  if (!targetCodeOf(step) || locatorText(step) === "-") {
    return { className: "case-bind-missing", label: "缺失" };
  }
  return { className: "case-bind-ok", label: "已绑定" };
}

function scriptText(value: unknown): string {
  return String(value || "").trim() || "暂无脚本源码，请重新生成用例。";
}

export function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const location = useLocation();
  const caseId = String(params.caseId || "").trim();
  const project = useMemo(() => {
    const query = new URLSearchParams(location.search);
    return normalizeProjectCode(query.get("project") || DEFAULT_PROJECT_CODE);
  }, [location.search]);
  const [item, setItem] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [scriptExpanded, setScriptExpanded] = useState<boolean>(false);
  const [discardOpen, setDiscardOpen] = useState<boolean>(false);
  const runtimeDesktopUrl = buildRuntimeDesktopUrl();

  async function reload() {
    if (!caseId) {
      setErrorText("缺少 case_id");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorText("");
    try {
      const payload = await getWorkbenchTestCase(caseId, project);
      setItem((payload.item || {}) as Record<string, unknown>);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例详情加载失败");
      setItem({});
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, project]);

  async function executeCase() {
    if (!caseId || busy) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setFeedback("");
    try {
      window.open(runtimeDesktopUrl, "aitest-runtime-desktop");
      const response = await runWorkbenchCase({
        project,
        case_id: caseId,
        source: "case_detail",
      });
      const responseItem = (response.item || response) as Record<string, unknown>;
      const runId = String(responseItem.run_id || responseItem.id || "").trim();
      setFeedback(
        runId
          ? `已提交执行任务：${runId}。可打开实时桌面观察执行过程，完成后会自动刷新执行历史。`
          : "已提交执行任务。",
      );
      let finalFeedback = "";
      if (runId) {
        const finalStatus = await waitForRunTerminal(runId, (status) => {
          setFeedback(`执行任务 ${runId} 当前状态：${executionLabel(status)}。可打开实时桌面观察，完成后查看报告、录屏和执行记录。`);
        });
        finalFeedback = `执行任务 ${runId} 已完成：${executionLabel(finalStatus)}。执行历史、报告和录屏入口已同步。`;
      }
      await reload();
      if (finalFeedback) {
        setFeedback(finalFeedback);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "执行用例失败");
    } finally {
      setBusy(false);
    }
  }

  async function discardCase() {
    if (!caseId || busy) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setFeedback("");
    try {
      await batchUpdateTestCaseStatus({
        case_ids: [caseId],
        status: "deprecated",
      });
      setFeedback("已废弃该用例。");
      setDiscardOpen(false);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "废弃用例失败");
    } finally {
      setBusy(false);
    }
  }

  async function regenerateCase() {
    const assetId = String(item.source_asset_id || "").trim();
    const currentSteps = Array.isArray(item.steps) ? item.steps : [];
    const itemIntentIds = Array.isArray(item.intent_ids)
      ? item.intent_ids.map((value) => rawText(value)).filter(Boolean)
      : [];
    if (!assetId || busy) {
      setErrorText("缺少来源资产，无法再次生成。");
      return;
    }
    const intentIds = Array.from(
      new Set(
        (itemIntentIds.length ? itemIntentIds : currentSteps
          .map((step) => (step && typeof step === "object" ? rawText((step as Record<string, unknown>).intent_id) : ""))
          .filter((value) => value && value !== "__page_entry__")),
      ),
    );
    setBusy(true);
    setErrorText("");
    setFeedback("");
    try {
      const response = await batchGenerateCasesFromTestPointAssets({
        project,
        asset_ids: [assetId],
        intent_ids: intentIds.length ? intentIds : undefined,
        source: "ai",
      });
      setFeedback(`已再次生成 ${Number(response.count || 0)} 条用例，可在用例中心查看。`);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "再次生成失败");
    } finally {
      setBusy(false);
    }
  }

  const sourceAssetId = String(item.source_asset_id || "").trim();
  const executions = Array.isArray(item.executions) ? item.executions : [];
  const steps = Array.isArray(item.steps) ? item.steps : [];
  const involvedElements = Array.isArray(item.involved_elements)
    ? item.involved_elements.map((value) => String(value || "").replace(/^element:/u, "").trim()).filter(Boolean)
    : [];
  const elementRows: Record<string, unknown>[] = Array.from(
    steps.reduce<Map<string, Record<string, unknown>>>((rows, step) => {
      if (!step || typeof step !== "object") {
        return rows;
      }
      const row = step as Record<string, unknown>;
      const code = targetCodeOf(row);
      if (!code) {
        return rows;
      }
      const key = `${semanticTargetName(row, code)}::${code}`;
      const previous = rows.get(key);
      if (!previous || isSuspiciousBinding(row)) {
        rows.set(key, row);
      }
      return rows;
    }, new Map<string, Record<string, unknown>>()).values(),
  );

  return (
    <main className="page shell detail-page detail-page--case">
      <header className="detail-toolbar">
        <div className="detail-toolbar-main">
          <h1>用例详情</h1>
          <p>查看单条独立用例的完整信息、步骤、脚本源码和执行历史。</p>
        </div>
        <div className="detail-toolbar-actions">
          <button type="button" className="button" onClick={() => void executeCase()} disabled={busy || item.active_status === "deprecated"}>
            执行用例
          </button>
          <button type="button" className="button secondary" onClick={() => void regenerateCase()} disabled={busy || !sourceAssetId}>
            再次生成
          </button>
          <button type="button" className="button secondary" onClick={() => setScriptExpanded((value) => !value)}>
            {scriptExpanded ? "收起脚本源码" : "查看脚本源码"}
          </button>
          <button type="button" className="button danger secondary" onClick={() => setDiscardOpen(true)} disabled={busy || item.active_status === "deprecated"}>
            废弃用例
          </button>
          <Link className="button secondary" to={`/cases?project=${encodeURIComponent(project)}`}>
            返回列表
          </Link>
        </div>
      </header>

      {loading ? <section className="panel">正在加载用例详情...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {feedback ? (
        <section className="panel case-feedback">
          <span>{feedback}</span>
          <a className="subtle-link" href={runtimeDesktopUrl} target="_blank" rel="noreferrer">
            打开实时桌面
          </a>
          {feedback.includes("用例中心") ? (
            <Link className="subtle-link" to={`/cases?project=${encodeURIComponent(project)}`}>
              前往用例中心
            </Link>
          ) : null}
        </section>
      ) : null}
      {!loading && !errorText ? (
        <section className="execution-visibility-hint">
          <span>执行会在容器桌面中启动浏览器；如需看过程，请打开实时桌面，执行结束后报告页可查看录屏。</span>
          <a href={runtimeDesktopUrl} target="_blank" rel="noreferrer">
            打开实时桌面
          </a>
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="detail-hero">
          <div className="detail-title-row">
            <div>
              <h2 className="detail-title">{text(item.title)}</h2>
              <p className="detail-subtitle detail-mono">{text(item.case_id)}</p>
            </div>
            <span className={item.active_status === "deprecated" ? "detail-status detail-status--danger" : "detail-status detail-status--success"}>
              {item.active_status === "deprecated" ? "已废弃" : "活跃"}
            </span>
          </div>
          <p className="detail-description">{text(item.description || item.title)}</p>
          <div className="detail-field-grid">
            <div className="detail-field">
              <span className="detail-field-label">页面</span>
              <strong className="detail-field-value">{text(item.page)}</strong>
            </div>
            <div className="detail-field detail-field--wide">
              <span className="detail-field-label">测试地址</span>
              <strong className="detail-field-value detail-url">{text(item.page_url)}</strong>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">类型</span>
              <strong className="detail-field-value">{intentTypeLabel(item.intent_type)}</strong>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">优先级</span>
              <strong className="detail-field-value">{text(item.priority)}</strong>
            </div>
            <div className="detail-field detail-field--wide">
              <span className="detail-field-label">来源资产</span>
              <strong className="detail-field-value">
                {sourceAssetId ? (
                  <Link to={`/assets/test-points/${encodeURIComponent(sourceAssetId)}?project=${encodeURIComponent(project)}`}>
                    {text(item.source_asset_title || sourceAssetId)} [查看]
                  </Link>
                ) : (
                  "-"
                )}
              </strong>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">创建</span>
              <strong className="detail-field-value">{formatDateTime(item.created_at)}</strong>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">更新</span>
              <strong className="detail-field-value">{formatDateTime(item.updated_at)}</strong>
            </div>
          </div>
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="detail-section">
          <div className="detail-section-header">
            <div>
              <h2 className="detail-section-title">测试步骤与预期</h2>
              <p className="detail-section-desc">以测试人员可读的方式展示步骤、动作和参数。</p>
            </div>
          </div>
          <p className="detail-section-body">
            <strong>前置条件：</strong>
            {text(item.precondition)}
          </p>
          {steps.length ? (
            <div className="detail-table-wrap">
              <table className="detail-table detail-table--steps case-steps-table">
                <thead>
                  <tr>
                    <th>序号</th>
                    <th>步骤说明</th>
                    <th>动作</th>
                    <th>参数/目标</th>
                  </tr>
                </thead>
                <tbody>
                  {steps.map((step, index) => {
                    const display = stepDisplay(step, index);
                    const value = display.value || "-";
                    return (
                      <tr key={`${display.title}-${index}`}>
                        <td><span className="case-step-index">{String(index + 1).padStart(2, "0")}</span></td>
                        <td>{display.title}</td>
                        <td><span className={`case-action-badge ${display.kind}`}>{display.action}</span></td>
                        <td><span className="case-value-pill" title={value}>{value}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p>-</p>
          )}
          <p className="detail-section-body">
            <strong>预期结果：</strong>
            {text(item.expected_result)}
          </p>
          <h3 className="detail-section-title">涉及元素绑定</h3>
          {elementRows.length ? (
            <div className="detail-table-wrap">
              <table className="detail-table detail-table--elements case-element-table">
                <thead>
                  <tr>
                    <th>元素中文名</th>
                    <th>元素编码</th>
                    <th>定位器</th>
                    <th>绑定状态</th>
                  </tr>
                </thead>
                <tbody>
                  {elementRows.map((step, index) => {
                    const code = targetCodeOf(step);
                    const status = bindingStatus(step);
                    const locator = locatorText(step);
                    return (
                      <tr key={`${code}-${index}`}>
                        <td>{semanticTargetName(step, code)}</td>
                        <td className="mono">{code}</td>
                        <td><span className="case-locator-pill" title={locator}>{locator}</span></td>
                        <td><span className={status.className}>{status.label}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p>{involvedElements.length ? involvedElements.join("、") : "-"}</p>
          )}
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="detail-section">
          <h2 className="detail-section-title">执行历史（最近 5 条）</h2>
          <div className="detail-table-wrap">
            <table className="detail-table detail-table--history">
              <thead>
                <tr>
                  <th>执行时间</th>
                  <th>触发方式</th>
                  <th>结果</th>
                  <th>耗时</th>
                  <th>日志/报告</th>
                </tr>
              </thead>
              <tbody>
                {executions.length ? (
                  executions.map((execution, index) => {
                    const row = execution as Record<string, unknown>;
                    const reportUrl = toReactReportUrl(row.report_url);
                    return (
                      <tr key={`${String(row.executed_at || "")}-${index}`}>
                        <td>{formatDateTime(row.executed_at)}</td>
                        <td>手动/系统</td>
                        <td>{executionLabel(row.status)}</td>
                        <td>{Number(row.duration_ms || 0) ? `${Number(row.duration_ms || 0)}ms` : "-"}</td>
                        <td>
                          {reportUrl ? (
                            <span className="asset-actions-inline">
                              <a href={reportUrl}>查看报告/录屏</a>
                            </span>
                          ) : (
                            <span className="muted">暂无报告</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                ) : null}
              </tbody>
            </table>
            {!executions.length ? (
              <div className="case-empty-history">
                <strong>暂无执行历史</strong>
                <p>点击「执行用例」开始第一次测试运行。</p>
                <button type="button" className="button" onClick={() => void executeCase()} disabled={busy || item.active_status === "deprecated"}>
                  立即执行
                </button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="detail-section case-script-panel">
          <div className="detail-section-header case-section-head">
            <div>
              <h2 className="detail-section-title">脚本源码</h2>
              <p className="detail-section-desc">默认折叠，展开后查看当前自动化用例源码。</p>
            </div>
            <button type="button" className="button secondary" onClick={() => setScriptExpanded((value) => !value)}>
              {scriptExpanded ? "收起脚本源码" : "展开查看"}
            </button>
          </div>
          {scriptExpanded ? (
            <pre className="detail-code">{scriptText(item.script_code)}</pre>
          ) : (
            <button type="button" className="case-script-collapsed" onClick={() => setScriptExpanded(true)}>
              展开查看生成的自动化脚本
            </button>
          )}
        </section>
      ) : null}

      {discardOpen ? (
        <ConfirmDialog
          title="确认废弃用例"
          description="废弃后，该用例默认不再进入执行列表，但历史记录仍会保留。"
          confirmText="确认废弃"
          danger
          busy={busy}
          details={[`用例：${text(item.title || item.case_id)}`]}
          onCancel={() => setDiscardOpen(false)}
          onConfirm={() => void discardCase()}
        />
      ) : null}
    </main>
  );
}
