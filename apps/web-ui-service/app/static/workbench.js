(function () {
  const shell = document.getElementById("workbench-shell");
  const shared = window.WorkbenchShared;
  const workbenchCases = window.WorkbenchCases;
  const workbenchRuns = window.WorkbenchRuns;
  if (!shell || !shared || !workbenchCases || !workbenchRuns) return;

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
  };

  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
  const searchParams = new URLSearchParams(window.location.search || "");
  state.project = String(searchParams.get("project") || "default").trim() || "default";

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
    currentCaseBar: document.getElementById("wb-current-case-bar"),
    currentCaseHeader: document.getElementById("wb-current-case-header"),
    currentPageHeader: document.getElementById("wb-current-page-header"),
    currentPriorityHeader: document.getElementById("wb-current-priority-header"),
    currentUpdatedHeader: document.getElementById("wb-current-updated-header"),
    currentRunHeader: document.getElementById("wb-current-run-header"),
  };

  const focusReviewType = String(searchParams.get("review_type") || "").trim().toLowerCase();
  const deepLinkRunId = String(searchParams.get("run_id") || "").trim();
  const deepLinkCaseId = String(searchParams.get("case_id") || "").trim();

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
      els.authNotice.textContent = `${username} 已登录。这里的调试执行、确认点和审计记录都会绑定到真实用户。`;
      return;
    }
    els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
    els.authNotice.textContent = "当前为未登录状态：这里仍可调试与执行，但需要审计落点的确认动作会要求先登录。";
  }

  function updateCurrentCaseBar(item) {
    const payload = item && typeof item === "object" ? item : {};
    if (els.currentCaseBar) {
      els.currentCaseBar.hidden = false;
    }
    if (els.currentCaseHeader) {
      els.currentCaseHeader.textContent = shared.displayCaseId(payload.case_id || state.currentCaseId || "-");
    }
    if (els.currentPageHeader) {
      els.currentPageHeader.textContent = String(payload.page || "-").trim() || "-";
    }
    if (els.currentPriorityHeader) {
      els.currentPriorityHeader.textContent = String(payload.priority || "-").trim() || "-";
    }
    if (els.currentUpdatedHeader) {
      els.currentUpdatedHeader.textContent = shared.formatTime(payload.updated_at || "-");
    }
    if (els.currentRunHeader && !state.currentRunId) {
      els.currentRunHeader.textContent = "等待执行";
    }
  }

  function updateRunStatusSummary(text) {
    if (els.currentRunHeader) {
      els.currentRunHeader.textContent = String(text || "等待执行");
    }
  }

  let runController = null;
  const caseController = workbenchCases.createController({
    state,
    els,
    authFetch,
    onCaseLoaded(item) {
      state.currentRunId = "";
      if (runController) {
        runController.resetLogs();
        runController.clearAnalysis();
        runController.setRunStatus("等待执行...");
      }
      updateCurrentCaseBar(item);
    },
  });

  runController = workbenchRuns.createController({
    state,
    els,
    authFetch,
    focusReviewType,
    loadCases: caseController.loadCases,
    loadCase: caseController.loadCase,
    saveEditorCase: caseController.saveEditorCase,
    onRunStatusChange: updateRunStatusSummary,
  });

  async function bootstrap() {
    updateAuthNotice();
    caseController.bindEvents();
    runController.bindEvents();
    await caseController.loadProjects();
    if (deepLinkRunId) {
      await runController.loadRunContext(deepLinkRunId);
    } else if (deepLinkCaseId) {
      await caseController.loadCases(state.casePage, state.casePageSize, deepLinkCaseId);
      await caseController.loadCase(deepLinkCaseId);
    } else {
      await caseController.loadCases();
    }
    window.addEventListener("platform-auth-changed", updateAuthNotice);
    window.addEventListener("beforeunload", () => runController.closeEventSource());
  }

  bootstrap().catch((error) => {
    console.error(error);
    window.alert("工作台加载失败，请检查后端服务。");
  });
})();
