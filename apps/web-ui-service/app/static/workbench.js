(function () {
  const shell = document.getElementById("workbench-shell");
  if (!shell) return;

  const state = {
    project: "default",
    currentCaseId: "",
    currentCasePath: "",
    currentRunId: "",
    eventSource: null,
    logLines: [],
    caseItems: [],
    casePage: 1,
    casePageSize: 10,
    casePagination: {
      page: 1,
      page_size: 10,
      total_items: 0,
      total_pages: 1,
      has_prev: false,
      has_next: false,
      prev_page: null,
      next_page: null,
    },
    deepLinkRunId: "",
    deepLinkCaseId: "",
    focusReviewType: "",
    focusPage: "",
  };

  let casePagination = null;

  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
  const searchParams = new URLSearchParams(window.location.search || "");
  state.project = String(searchParams.get("project") || "default").trim() || "default";
  state.deepLinkRunId = String(searchParams.get("run_id") || "").trim();
  state.deepLinkCaseId = String(searchParams.get("case_id") || "").trim();
  state.focusReviewType = String(searchParams.get("review_type") || "").trim().toLowerCase();
  state.focusPage = String(searchParams.get("page") || "").trim().toLowerCase();

  const els = {
    projectSelect: document.getElementById("wb-project"),
    refreshBtn: document.getElementById("wb-refresh"),
    caseBody: document.getElementById("wb-case-body"),
    casePagination: document.getElementById("wb-case-pagination"),
    yamlEditor: document.getElementById("wb-yaml-editor"),
    currentCase: document.getElementById("wb-current-case"),
    currentPath: document.getElementById("wb-current-path"),
    saveBtn: document.getElementById("wb-save"),
    runBtn: document.getElementById("wb-run"),
    runStatus: document.getElementById("wb-run-status"),
    logViewer: document.getElementById("wb-log-viewer"),
    analysisSummary: document.getElementById("wb-analysis-summary"),
    analysisDetail: document.getElementById("wb-analysis-detail"),
    auditTimeline: document.getElementById("wb-audit-timeline"),
    healBtn: document.getElementById("wb-heal"),
    rerunBtn: document.getElementById("wb-rerun"),
    downloadBtn: document.getElementById("wb-download-log"),
    authNotice: document.getElementById("wb-auth-notice"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString("zh-CN");
    } catch (_error) {
      return String(value);
    }
  }

  function setRunStatus(text) {
    els.runStatus.textContent = text;
  }

  function getCasePageCount() {
    return Math.max(1, Number(state.casePagination?.total_pages || 1));
  }

  function clampCasePage(page) {
    const pageCount = getCasePageCount();
    return Math.min(Math.max(1, page || 1), pageCount);
  }

  function findCaseIndex(caseId) {
    if (!caseId) return -1;
    return (state.caseItems || []).findIndex((row) => String(row.case_id || "") === String(caseId || ""));
  }

  function normalizeCaseId(value) {
    return String(value || "")
      .trim()
      .replace(/^['"]|['"]$/g, "")
      .replace(/\s+/g, "-")
      .replace(/[^A-Za-z0-9_-]/g, "-")
      .replace(/-+/g, "-")
      .replace(/^[-_]+|[-_]+$/g, "")
      .toUpperCase();
  }

  function extractCaseIdFromYaml(text) {
    const content = String(text || "");
    const matched = content.match(/^\s*id\s*:\s*(.+?)\s*(?:#.*)?$/im);
    if (!matched) return "";
    return normalizeCaseId(matched[1]);
  }

  async function saveEditorCase({ announce = true } = {}) {
    const editorContent = String(els.yamlEditor.value || "").trim();
    const inferredCaseId = normalizeCaseId(state.currentCaseId || extractCaseIdFromYaml(editorContent));
    if (!inferredCaseId) {
      alert("请先选择用例，或在 YAML 中补充 id。");
      return null;
    }

    const resp = await authFetch(`/api/workbench/cases/${encodeURIComponent(inferredCaseId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        yaml_content: els.yamlEditor.value,
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`保存失败：${error.detail || resp.statusText}`);
      return null;
    }

    const payload = await resp.json();
    const item = payload.item || {};
    state.currentCaseId = item.case_id || inferredCaseId;
    state.currentCasePath = item.path || state.currentCasePath || "";
    els.currentCase.textContent = state.currentCaseId || "未选择";
    els.currentPath.textContent = state.currentCasePath;
    await loadCases(state.casePage, state.casePageSize, state.currentCaseId);
    if (announce) {
      alert("用例已保存。");
    }
    return state.currentCaseId;
  }

  function handleCasePaginationChange(page, pageSize) {
    const nextPage = Math.max(1, Number(page) || 1);
    const nextPageSize = Math.max(1, Number(pageSize) || state.casePageSize);
    loadCases(nextPage, nextPageSize);
  }

  function renderCasePagination() {
    if (!els.casePagination) return;
    const pagination = state.casePagination || {};
    const currentPage = clampCasePage(pagination.page || state.casePage);
    const total = Number(pagination.total_items || 0);
    if (typeof window.Pagination !== "function") {
      els.casePagination.innerHTML = total
        ? `<span class="case-page-info">第 ${currentPage} / ${getCasePageCount()} 页 · 共 ${total} 条</span>`
        : '<span class="case-page-info">暂无用例</span>';
      return;
    }
    const paginationOptions = {
      page: currentPage,
      page_size: Number(pagination.page_size || state.casePageSize),
      total_items: total,
      page_size_options: [10, 20, 50, 100],
      show_total: true,
      show_quick_jumper: true,
      onChange: handleCasePaginationChange,
    };
    if (!casePagination) {
      casePagination = new window.Pagination("#wb-case-pagination", paginationOptions);
      return;
    }
    casePagination.update(paginationOptions);
  }

  function renderCaseRows() {
    const items = state.caseItems || [];
    if (!items.length) {
      els.caseBody.innerHTML = state.casePagination.total_items
        ? '<tr><td colspan="5">当前页暂无用例</td></tr>'
        : '<tr><td colspan="5">暂无用例</td></tr>';
      renderCasePagination();
      return;
    }
    els.caseBody.innerHTML = items
      .map(
        (item) => `
          <tr data-case-id="${escapeHtml(item.case_id)}" class="${state.currentCaseId === item.case_id ? "is-active" : ""}">
            <td>${escapeHtml(item.case_id)}</td>
            <td>${escapeHtml(item.title)}</td>
            <td>${escapeHtml(item.page)}</td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${formatTime(item.updated_at)}</td>
          </tr>
        `
      )
      .join("");
    els.caseBody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        const caseId = row.getAttribute("data-case-id");
        if (caseId) {
          loadCase(caseId);
        }
      });
    });
    renderCasePagination();
  }

  function updateAuthNotice() {
    if (!els.authNotice) return;
    const authState = window.platformAuth && typeof window.platformAuth.getAuthState === "function"
      ? String(window.platformAuth.getAuthState() || "anonymous").toLowerCase()
      : "anonymous";
    if (authState === "authenticated" || authState === "token") {
      const currentUser = window.platformAuth && typeof window.platformAuth.getCurrentUser === "function"
        ? window.platformAuth.getCurrentUser()
        : null;
      const username = String(currentUser?.username || currentUser?.name || "当前用户").trim();
      els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
      els.authNotice.textContent = `${username} 已登录。运行记录中的确认点、风险决策和后续审计会绑定到真实用户。`;
      return;
    }
    els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
    els.authNotice.textContent = "当前为未登录状态：这里可以继续查看、编辑和执行，但需要落审计的确认动作会要求先登录。";
  }

  function reviewStatusText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "confirmed") return "已确认";
    if (normalized === "skipped") return "已跳过";
    if (normalized === "not_required") return "无需确认";
    return "待确认";
  }

  function gateApprovalText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "pending_second_approval") return "待二次审批";
    if (normalized === "approved") return "已审批";
    if (normalized === "revoked") return "已撤销";
    return normalized || "未知";
  }

  function gateRecordText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "revoked") return "已撤销";
    if (normalized === "active") return "有效";
    return normalized || "未知";
  }

  function renderGateMetrics(metrics) {
    const data = metrics && typeof metrics === "object" ? metrics : {};
    return [
      `status=${String(data.status || "-")}`,
      `coverage=${String(data.coverage_status || "-")}`,
      `low_conf_elements=${Number(data.low_confidence_elements || 0)}`,
      `missing_po=${Number(data.missing_page_object_elements || 0)}`,
      `pending_points=${Number(data.pending_test_points || 0)}`,
      `skip_points=${Number(data.skip_suggestions || 0)}`,
      `dependency_points=${Number(data.dependency_review_points || 0)}`,
      `low_conf_dependency_points=${Number(data.low_confidence_dependency_points || 0)}`,
      `missing_dependency_points=${Number(data.missing_dependency_points || 0)}`,
      `dependency_skip_points=${Number(data.dependency_skip_points || 0)}`,
      `pending_sections=${Number(data.pending_review_sections || 0)}`,
    ].join(" · ");
  }

  function renderGateConfigSnapshot(snapshot) {
    const data = snapshot && typeof snapshot === "object" ? snapshot : {};
    return [
      `缺失必需元素阻断阈值=${Number(data.block_missing_required_threshold || 0)}`,
      `未识别依赖阻断阈值=${Number(data.block_missing_dependency_points_threshold || 0)}`,
      `失败即阻断=${Boolean(data.block_on_failed_status)}`,
      `风险阻断联动=${Boolean(data.block_on_risk_block)}`,
      `低置信度元素告警=${Boolean(data.warn_on_low_confidence_elements)}`,
      `待确认测试点告警=${Boolean(data.warn_on_pending_test_points)}`,
      `低置信度依赖告警=${Boolean(data.warn_on_low_confidence_dependency_points)}`,
      `待确认分组告警=${Boolean(data.warn_on_pending_reviews)}`,
    ].join(" · ");
  }

  function renderGateNextAction(decision) {
    const normalized = String(decision || "").trim().toLowerCase();
    if (normalized === "block") {
      return "下一步：先修复阻断项，再重新执行；当前不建议直接放行。";
    }
    if (normalized === "manual_review") {
      return "下一步：先完成确认点，再决定人工放行还是人工阻断。";
    }
    return "下一步：当前门禁允许继续推进，可结合后续执行或发布流程继续处理。";
  }

  function renderReviewSummary(reviewState) {
    if (!reviewState || typeof reviewState !== "object") {
      return '<div>确认点：当前运行未记录确认信息。</div>';
    }
    const element = reviewState.element && typeof reviewState.element === "object" ? reviewState.element : {};
    const testPoint = reviewState.test_point && typeof reviewState.test_point === "object" ? reviewState.test_point : {};
    const risk = reviewState.risk && typeof reviewState.risk === "object" ? reviewState.risk : {};
    return `
      <div>确认点总览：待确认 ${escapeHtml(reviewState.pending_sections || 0)} 组，已确认 ${escapeHtml(reviewState.confirmed_sections || 0)} 组</div>
      <div>元素确认：${escapeHtml(reviewStatusText(element.status))}（${escapeHtml(element.candidate_count || 0)} 项）</div>
      <div>测试点确认：${escapeHtml(reviewStatusText(testPoint.status))}（${escapeHtml(testPoint.candidate_count || 0)} 项）</div>
      <div>风险决策：${escapeHtml(reviewStatusText(risk.status))}（${escapeHtml(risk.candidate_count || 0)} 项）</div>
    `;
  }

  function renderExecutionGateSummary(executionGate) {
    const gate = executionGate && typeof executionGate === "object" ? executionGate : {};
    if (!Object.keys(gate).length) {
      return '<div>执行门禁：当前运行未记录门禁决策。</div>';
    }
    const blockers = Array.isArray(gate.blockers) ? gate.blockers.filter(Boolean) : [];
    const warnings = Array.isArray(gate.warnings) ? gate.warnings.filter(Boolean) : [];
    const evidence = Array.isArray(gate.evidence) ? gate.evidence.filter(Boolean) : [];
    const metrics = gate.metrics && typeof gate.metrics === "object" ? gate.metrics : {};
    const configSnapshot = gate.config_snapshot && typeof gate.config_snapshot === "object" ? gate.config_snapshot : {};
    const effectiveDecision = String(gate.effective_decision || gate.decision || "allow").trim() || "allow";
    const manualDecision = gate.manual_decision && typeof gate.manual_decision === "object" ? gate.manual_decision : {};
    const approvalStatus = String(gate.approval_status || manualDecision.approval_status || "approved").trim().toLowerCase() || "approved";
    const recordStatus = String(gate.record_status || manualDecision.record_status || "active").trim().toLowerCase() || "active";
    const decisionMaker = String(manualDecision.decided_by || gate.decided_by || "").trim();
    const decisionMakerRole = String(manualDecision.decided_by_role || gate.decided_by_role || "").trim();
    const revokedBy = String(manualDecision.revoked_by || gate.revoked_by || decisionMaker || "-").trim() || "-";
    const revokedByRole = String(manualDecision.revoked_by_role || gate.revoked_by_role || decisionMakerRole || "").trim();
    const revokedAt = String(manualDecision.revoked_at || gate.revoked_at || "").trim();
    return `
      <div>执行门禁：系统决策=${escapeHtml(gate.decision || "allow")}，生效决策=${escapeHtml(effectiveDecision)}，来源=${escapeHtml(gate.decision_source || "system")}</div>
      <div>requires_review=${escapeHtml(String(Boolean(gate.requires_review)))}</div>
      <div>规则边界：未识别依赖达到阈值时阻断；低置信度依赖默认人工复核。</div>
      <div>规则快照：${escapeHtml(renderGateConfigSnapshot(configSnapshot))}</div>
      <div>命中指标：${escapeHtml(renderGateMetrics(metrics))}</div>
      <div>动作建议：${escapeHtml(renderGateNextAction(effectiveDecision))}</div>
      <div>审批状态=${escapeHtml(gateApprovalText(approvalStatus))}，记录状态=${escapeHtml(gateRecordText(recordStatus))}</div>
      <div>门禁阻断项：${escapeHtml(blockers.length)}</div>
      <div>门禁告警项：${escapeHtml(warnings.length)}</div>
      ${blockers.length ? `<div>阻断原因：${escapeHtml(blockers.join(" "))}</div>` : ""}
      ${warnings.length ? `<div>告警原因：${escapeHtml(warnings.join(" "))}</div>` : ""}
      ${evidence.length ? `<div>门禁依据：${escapeHtml(evidence.join(" "))}</div>` : ""}
      ${manualDecision && Object.keys(manualDecision).length ? `<div>人工决策：${escapeHtml(manualDecision.decision || "-")} · ${escapeHtml(manualDecision.decided_by || "-")} · ${escapeHtml(manualDecision.updated_at || "-")} ${manualDecision.note ? `· 备注：${escapeHtml(manualDecision.note)}` : ""}</div>` : ""}
      ${manualDecision?.second_approver ? `<div>二次审批：${escapeHtml(manualDecision.second_approver)}${manualDecision.second_approver_role ? ` (${escapeHtml(manualDecision.second_approver_role)})` : ""}${manualDecision.second_approved_at ? ` · ${escapeHtml(manualDecision.second_approved_at)}` : ""}</div>` : ""}
      ${recordStatus === "revoked" ? `<div>撤销信息：${escapeHtml(revokedBy)}${revokedByRole ? ` (${escapeHtml(revokedByRole)})` : ""}${revokedAt ? ` · ${escapeHtml(revokedAt)}` : ""}</div>` : ""}
    `;
  }

  function renderReviewAuditSummary(summary) {
    if (!summary || typeof summary !== "object") {
      return "";
    }
    const sections = Array.isArray(summary.sections) ? summary.sections : [];
    const lines = sections
      .filter((section) => section && typeof section === "object" && (section.actor_display || section.updated_at || section.candidate_count))
      .map((section) => {
        const actor = String(section.actor_display || section.confirmed_by || "").trim();
        const updatedAt = String(section.updated_at || "").trim();
        if (!actor && !updatedAt) {
          return `<div>${escapeHtml(section.label || section.review_type || "-")}：${escapeHtml(reviewStatusText(section.status))}</div>`;
        }
        return `<div>${escapeHtml(section.label || section.review_type || "-")}：${escapeHtml(reviewStatusText(section.status))}${actor ? ` · ${escapeHtml(actor)}` : ""}${updatedAt ? ` · ${escapeHtml(formatTime(updatedAt))}` : ""}</div>`;
      })
      .join("");
    if (!lines) {
      return "";
    }
    const latestActor = String(summary.latest_actor_display || "").trim();
    const latestUpdatedAt = String(summary.latest_updated_at || "").trim();
    const latestLine = latestActor || latestUpdatedAt
      ? `<div>最近一次确认：${escapeHtml(latestActor || "-")}${latestUpdatedAt ? ` · ${escapeHtml(formatTime(latestUpdatedAt))}` : ""}</div>`
      : "";
    return `
      <div class="wb-review-audit">
        <div>审计摘要：待确认 ${escapeHtml(summary.pending_sections || 0)} 组，已确认 ${escapeHtml(summary.confirmed_sections || 0)} 组</div>
        ${latestLine}
        ${lines}
      </div>
    `;
  }

  function renderAuditTimeline(timeline) {
    const rows = Array.isArray(timeline) ? timeline : [];
    if (!els.auditTimeline) {
      return;
    }
    if (!rows.length) {
      els.auditTimeline.className = "wb-audit-panel wb-review-empty";
      els.auditTimeline.innerHTML = "当前运行暂无确认、拒绝或风险决策审计事件。";
      return;
    }
    els.auditTimeline.className = "wb-audit-panel";
    els.auditTimeline.innerHTML = `
      <section class="wb-audit-card">
        <h3>审计时间线</h3>
        ${rows.map((entry, index) => `
          <div class="wb-audit-line ${state.focusReviewType && state.focusReviewType === String(entry.review_type || "").trim().toLowerCase() ? "wb-audit-line-active" : ""}">
            <strong>${index + 1}. ${escapeHtml(entry.detail_summary || entry.action || "-")}</strong>
            <div class="wb-audit-meta">
              <span>时间：${escapeHtml(formatTime(entry.timestamp))}</span>
              <span>类型：${escapeHtml(entry.review_type || "-")}</span>
              <span>状态：${escapeHtml(entry.status || "-")}</span>
              <span>确认人：${escapeHtml(entry.actor_display || entry.confirmed_by || "-")}</span>
            </div>
            ${entry.gate_reason_summary ? `<div class="wb-audit-note">门禁依据：${escapeHtml(entry.gate_reason_summary)}</div>` : ""}
          </div>
        `).join("")}
      </section>
    `;
  }

  function renderSourceEvidence(items) {
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      return "-";
    }
    return rows
      .slice(0, 3)
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const signal = String(item.signal || "-").trim();
        const value = String(item.value || "-").trim();
        const origin = String(item.origin || "-").trim();
        return `${signal}:${value} @ ${origin}`;
      })
      .filter(Boolean)
      .join("；");
  }

  function resetLogs() {
    state.logLines = [];
    els.logViewer.textContent = "";
  }

  function appendLog(line) {
    state.logLines.push(line);
    if (state.logLines.length > 400) {
      state.logLines.shift();
    }
    els.logViewer.textContent = state.logLines.join("\n");
    els.logViewer.scrollTop = els.logViewer.scrollHeight;
  }

  function closeEventSource() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
  }

  async function loadProjects() {
    const resp = await authFetch("/api/workbench/projects");
    if (!resp.ok) throw new Error("load projects failed");
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) items.push("default");
    els.projectSelect.innerHTML = items.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
    if (!items.includes(state.project)) {
      state.project = items[0];
    }
    els.projectSelect.value = state.project;
  }

  async function loadCases(page = state.casePage, pageSize = state.casePageSize, focusCaseId = "") {
    const params = new URLSearchParams({
      project: state.project,
      page: String(Math.max(1, Number(page) || 1)),
      page_size: String(Math.max(1, Number(pageSize) || state.casePageSize)),
    });
    if (focusCaseId) {
      params.set("focus_case_id", focusCaseId);
    }
    const resp = await authFetch(`/api/workbench/cases?${params.toString()}`);
    if (!resp.ok) throw new Error("load cases failed");
    const payload = await resp.json();
    state.caseItems = Array.isArray(payload.items) ? payload.items : [];
    state.casePagination = payload.pagination && typeof payload.pagination === "object"
      ? payload.pagination
      : {
          page: Math.max(1, Number(page) || 1),
          page_size: Math.max(1, Number(pageSize) || state.casePageSize),
          total_items: state.caseItems.length,
          total_pages: 1,
          has_prev: false,
          has_next: false,
          prev_page: null,
          next_page: null,
        };
    state.casePage = Number(state.casePagination.page || 1);
    state.casePageSize = Number(state.casePagination.page_size || pageSize || state.casePageSize);
    renderCaseRows();
  }

  async function loadCase(caseId) {
    const resp = await authFetch(`/api/workbench/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(state.project)}`);
    if (!resp.ok) {
      alert("加载用例失败");
      return;
    }
    const payload = await resp.json();
    const item = payload.item || {};
    state.currentCaseId = item.case_id || caseId;
    state.currentCasePath = item.path || "";
    els.currentCase.textContent = state.currentCaseId || "未选择";
    els.currentPath.textContent = state.currentCasePath;
    els.yamlEditor.value = item.yaml_content || "";
    renderCaseRows();
    resetLogs();
    setRunStatus("等待执行...");
    els.analysisSummary.textContent = "暂无失败分析数据。";
    els.analysisDetail.innerHTML = "";
    renderAuditTimeline([]);
  }

  async function loadRunContext(runId) {
    const response = await authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`);
    if (!response.ok) {
      throw new Error("load run failed");
    }
    const payload = await response.json().catch(() => ({}));
    const item = payload.item || {};
    if (item.project && item.project !== state.project) {
      state.project = item.project;
      els.projectSelect.value = state.project;
    }
    if (item.case_id) {
      await loadCases(state.casePage, state.casePageSize, item.case_id);
    } else {
      await loadCases(state.casePage, state.casePageSize);
    }
    if (item.case_id) {
      state.currentCaseId = item.case_id;
      state.currentCasePath = item.case_path || "";
      els.currentCase.textContent = state.currentCaseId || "未选择";
      els.currentPath.textContent = state.currentCasePath || "";
      renderCaseRows();
    }
    state.currentRunId = item.run_id || runId;
    setRunStatus(`已定位运行：${state.currentRunId}（${item.status || "unknown"}）`);
    await loadAnalysis(state.currentRunId);
    if (state.currentRunId) {
      openEventStream(state.currentRunId);
    }
    els.analysisSummary.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function saveCase() {
    const savedCaseId = await saveEditorCase({ announce: true });
    if (!savedCaseId) {
      return;
    }
  }

  function openEventStream(runId) {
    closeEventSource();
    const source = new EventSource(`/api/workbench/runs/${encodeURIComponent(runId)}/events`);
    state.eventSource = source;
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === "complete") {
          appendLog(`[run] status=${payload.status}`);
          setRunStatus(`执行完成：${payload.status}`);
          closeEventSource();
          loadAnalysis(runId);
          return;
        }
        if (payload.line) {
          appendLog(payload.line);
        }
      } catch (_error) {
        appendLog(event.data);
      }
    };
    source.onerror = () => {
      appendLog("[stream] connection closed");
      closeEventSource();
    };
  }

  async function runCase() {
    const savedCaseId = await saveEditorCase({ announce: false });
    if (!savedCaseId) {
      return;
    }
    resetLogs();
    setRunStatus("排队中...");
    els.analysisSummary.textContent = "运行中，等待失败分析...";
    els.analysisDetail.innerHTML = "";
    const resp = await authFetch("/api/workbench/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        case_id: savedCaseId,
        case_path: state.currentCasePath,
        source: "manual",
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`启动失败：${error.detail || resp.statusText}`);
      setRunStatus("启动失败");
      return;
    }
    const payload = await resp.json();
    const job = payload.item || {};
    state.currentRunId = job.run_id || "";
    setRunStatus(`运行中：${state.currentRunId}`);
    openEventStream(state.currentRunId);
  }

  async function loadAnalysis(runId) {
    if (!runId) return;
    const [analysisResp, runResp] = await Promise.all([
      authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}/analysis`),
      authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`),
    ]);
    if (!analysisResp.ok && !runResp.ok) return;
    const payload = analysisResp.ok ? await analysisResp.json() : { items: [] };
    const runPayload = runResp.ok ? await runResp.json() : { item: {} };
    const items = payload.items || [];
    const runItem = runPayload.item || {};
    const reviewSummaryHtml = renderReviewSummary(runItem.review_state);
    const reviewAuditHtml = renderReviewAuditSummary(runItem.review_audit_summary);
    const executionGateHtml = renderExecutionGateSummary(runItem.execution_gate);
    renderAuditTimeline(runItem.review_audit_timeline);
    if (!items.length) {
      const pageLabel = runItem.page ? `页面 ${runItem.page}` : "当前运行";
      els.analysisSummary.textContent = `${pageLabel} 暂无失败分析数据。`;
      els.analysisDetail.innerHTML = `${reviewSummaryHtml}${executionGateHtml}${reviewAuditHtml}`;
      return;
    }
    const entry = items[0];
    const analysis = entry.analysis || {};
    const suggestion = entry.suggestion || {};
    els.analysisSummary.textContent = `${analysis.summary || "失败分析已生成"}（风险：${analysis.risk_level || "-"}）`;
    els.analysisDetail.innerHTML = `
      ${reviewSummaryHtml}
      ${executionGateHtml}
      ${reviewAuditHtml}
      <div>失败类型：${escapeHtml(analysis.failure_category || "-")}</div>
      <div>失败来源：${escapeHtml(analysis.failure_source || "-")}</div>
      <div>来源依据：${escapeHtml(analysis.failure_source_reason || "-")}</div>
      <div>来源证据：${escapeHtml(renderSourceEvidence(analysis.source_evidence))}</div>
      <div>需人工复核：${escapeHtml(analysis.requires_manual_review ? "是" : "否")}</div>
      <div>可能原因：${escapeHtml(analysis.likely_cause || "-")}</div>
      <div>建议动作：${escapeHtml(analysis.recommended_action || "-")}</div>
      <div>置信度：${escapeHtml(analysis.confidence || "-")}</div>
      <div>修复建议：${escapeHtml(suggestion.summary || suggestion.suggestion || "-")}</div>
      <div>证据目录：<code>${escapeHtml(entry.artifact_dir || "-")}</code></div>
    `;
  }

  async function healRun() {
    if (!state.currentRunId) {
      alert("暂无可修复的运行记录。");
      return;
    }
    setRunStatus("修复并重跑中...");
    const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/heal-and-rerun`, {
      method: "POST",
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`修复并重跑失败：${error.detail?.message || error.detail || resp.statusText}`);
      return;
    }
    const payload = await resp.json();
    const item = payload.item || {};
    const heal = item.heal || {};
    const rerun = item.rerun || {};
    const rerunRunId = rerun.run_id || "";
    if (rerunRunId) {
      state.currentRunId = rerunRunId;
    }
    const healText = heal.ok ? `修复完成（${heal.item?.status || "ok"}）` : "修复未成功，已直接重跑";
    const rerunStatus = rerun.status || "running";
    els.analysisSummary.textContent = `${healText}；重跑状态：${rerunStatus}`;
    els.analysisDetail.innerHTML = `<pre><code>${escapeHtml(JSON.stringify(item, null, 2))}</code></pre>`;
    renderAuditTimeline([]);
    if (rerunStatus === "running") {
      openEventStream(state.currentRunId);
      return;
    }
    setRunStatus(`执行完成：${rerunStatus}`);
    loadAnalysis(state.currentRunId);
  }

  async function rerunCase() {
    if (!state.currentRunId) {
      alert("暂无可重跑的运行记录。");
      return;
    }
    const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/rerun`, {
      method: "POST",
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`重跑失败：${error.detail || resp.statusText}`);
      return;
    }
    const payload = await resp.json();
    const job = payload.item || {};
    state.currentRunId = job.run_id || "";
    resetLogs();
    setRunStatus(`重跑中：${state.currentRunId}`);
    openEventStream(state.currentRunId);
  }

  function downloadLog() {
    if (!state.currentRunId) {
      alert("暂无日志可下载。");
      return;
    }
    window.open(`/api/workbench/download-log/${encodeURIComponent(state.currentRunId)}`, "_blank");
  }

  function bindEvents() {
    els.projectSelect.addEventListener("change", async () => {
      state.project = els.projectSelect.value;
      await loadCases();
    });
    els.refreshBtn.addEventListener("click", loadCases);
    els.saveBtn.addEventListener("click", saveCase);
    els.runBtn.addEventListener("click", runCase);
    els.healBtn.addEventListener("click", healRun);
    els.rerunBtn.addEventListener("click", rerunCase);
    els.downloadBtn.addEventListener("click", downloadLog);
  }

  async function bootstrap() {
    updateAuthNotice();
    bindEvents();
    await loadProjects();
    if (state.deepLinkRunId) {
      await loadRunContext(state.deepLinkRunId);
    } else if (state.deepLinkCaseId) {
      await loadCases(state.casePage, state.casePageSize, state.deepLinkCaseId);
      await loadCase(state.deepLinkCaseId);
    } else {
      await loadCases();
    }
    window.addEventListener("platform-auth-changed", updateAuthNotice);
  }

  bootstrap().catch((error) => {
    console.error(error);
    alert("工作台加载失败，请检查后端服务。");
  });
})();
