(function () {
  const shell = document.getElementById("workbench-generate-shell");
  const shared = window.WorkbenchGenerateShared;
  const presenter = window.WorkbenchGeneratePresenter;
  const support = window.WorkbenchGenerateSupport;
  const projectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  if (!shell || !shared || !support || !presenter || !projectsApi || !projectManager) return;

  const state = {
    method: shared.normalizeMethod(document.getElementById("gen-method")?.value),
    previewCandidates: [],
    selectedCandidateId: "",
  };

  const els = {
    form: document.getElementById("wb-generate-form"),
    methodInput: document.getElementById("gen-method"),
    methodSummary: document.getElementById("gen-method-summary"),
    methodCards: Array.from(shell.querySelectorAll("[data-generation-method]")),
    methodPanels: Array.from(shell.querySelectorAll("[data-method-panel]")),
    projectSelect: document.getElementById("gen-project"),
    pageInput: document.getElementById("gen-page"),
    titleInput: document.getElementById("gen-title"),
    prioritySelect: document.getElementById("gen-priority"),
    sourceSelect: document.getElementById("gen-source"),
    tagsInput: document.getElementById("gen-tags"),
    requirementInput: document.getElementById("gen-requirement"),
    prdRequirementInput: document.getElementById("gen-prd-requirement"),
    apiRequirementInput: document.getElementById("gen-api-requirement"),
    storyRequirementInput: document.getElementById("gen-story-requirement"),
    customRequirementInput: document.getElementById("gen-custom-requirement"),
    prdTextInput: document.getElementById("gen-prd-text"),
    prdUrlInput: document.getElementById("gen-prd-url"),
    userStoryInput: document.getElementById("gen-user-story"),
    gitDiffInput: document.getElementById("gen-git-diff"),
    gitDiffPathInput: document.getElementById("gen-git-diff-path"),
    defectTicketInput: document.getElementById("gen-defect-ticket"),
    runtimeLogsInput: document.getElementById("gen-runtime-logs"),
    openapiSpecInput: document.getElementById("gen-openapi-spec"),
    openapiUrlInput: document.getElementById("gen-openapi-url"),
    inputSourcesInput: document.getElementById("gen-input-sources"),
    jsonFileInput: document.getElementById("gen-json-file"),
    pageUrlsInput: document.getElementById("gen-page-urls"),
    stepStatus: document.getElementById("gen-step-status"),
    loadReturnApplyBtn: document.getElementById("gen-load-returnapply"),
    backToInputBtn: document.getElementById("gen-back-to-input"),
    previewPointsBtn: document.getElementById("gen-preview-points"),
    createProjectBtn: document.getElementById("gen-create-project"),
    confirmGenerateBtn: document.getElementById("gen-confirm-generate"),
    intentSummary: document.getElementById("gen-intent-summary"),
    intentPreview: document.getElementById("gen-intent-preview"),
    candidateList: document.getElementById("gen-candidate-list"),
    candidateDetail: document.getElementById("gen-candidate-detail"),
    result: document.getElementById("gen-result"),
    yamlPreview: document.getElementById("gen-yaml-preview"),
    openReview: document.getElementById("gen-open-review"),
    openCases: document.getElementById("gen-open-cases"),
    openHistory: document.getElementById("gen-open-history"),
    continueGenerate: document.getElementById("gen-continue-generate"),
    openWorkbenchResult: document.getElementById("gen-open-workbench-result"),
    authNotice: document.getElementById("gen-auth-notice"),
  };

  function renderMethodState() {
    state.method = shared.normalizeMethod(els.methodInput?.value);
    els.methodCards.forEach((card) => {
      const cardMethod = shared.normalizeMethod(card.dataset.generationMethod);
      card.classList.toggle("is-active", cardMethod === state.method);
    });
    els.methodPanels.forEach((panel) => {
      const panelMethod = shared.normalizeMethod(panel.dataset.methodPanel);
      panel.classList.toggle("is-active", panelMethod === state.method);
    });
    presenter.setText(els.methodSummary, `当前方式：${shared.generationMethodLabel(state.method)}`);
    refreshWizardState();
  }

  function refreshWizardState() {
    const stepTwo = support.inputStepStatus(els, shared, state.method);
    const preview = support.previewStepStatus(state);
    presenter.setText(els.stepStatus, stepTwo.message);
    if (!preview.ok && !String(els.intentSummary?.textContent || "").includes("正在生成候选预览")) {
      presenter.setText(els.intentSummary, preview.message);
    }
    if (els.confirmGenerateBtn) {
      els.confirmGenerateBtn.disabled = !preview.ok;
    }
    if (window.WorkbenchGenerateWizard && typeof window.WorkbenchGenerateWizard.refresh === "function") {
      window.WorkbenchGenerateWizard.refresh();
    }
  }

  function updateAuthNotice() {
    if (!els.authNotice || !window.platformAuth || typeof window.platformAuth.getCurrentUser !== "function") return;
    const user = window.platformAuth.getCurrentUser() || {};
    const username = String(user.username || user.name || "").trim();
    if (!username) return;
    els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
    els.authNotice.textContent = `${username} 已登录，生成 Draft 与后续审核动作都会保留真实审计记录。`;
  }

  function setProjectOptions(items, selectedValue) {
    const options = (Array.isArray(items) ? items : []).map((item) => {
      const projectCode = String(item.project_code || "").trim();
      const projectName = String(item.project_name || projectCode).trim();
      const selected = projectCode === (selectedValue || "atp") ? " selected" : "";
      return `<option value="${projectCode}"${selected}>${projectCode} · ${projectName}</option>`;
    });
    if (els.projectSelect) {
      els.projectSelect.innerHTML = options.join("") || '<option value="atp" selected>atp</option>';
    }
  }

  async function loadProjects(selectedValue) {
    const payload = await projectsApi.list();
    setProjectOptions(payload.items || [], selectedValue || String(els.projectSelect?.value || "atp").trim() || "atp");
  }

  function openProjectManager() {
    projectManager.open({
      selectedProjectCode: String(els.projectSelect?.value || "atp").trim() || "atp",
      onChanged: async ({ action, project_code: projectCode }) => {
        const selectedProjectCode = action === "delete" ? "atp" : String(projectCode || "").trim().toLowerCase();
        await loadProjects(selectedProjectCode);
        if (action === "create") {
          presenter.setText(els.result, `项目 ${selectedProjectCode} 已创建，可直接用于生成 Draft。`);
          return;
        }
        if (action === "update") {
          presenter.setText(els.result, `项目 ${selectedProjectCode} 已更新。`);
          return;
        }
        presenter.setText(els.result, `项目 ${String(projectCode || "").trim().toLowerCase()} 已删除。`);
      },
    });
  }

  async function collectExtraInputSources() {
    let typedSources = [];
    try {
      typedSources = JSON.parse(els.inputSourcesInput?.value || "[]");
    } catch (_error) {
      throw new Error("附加输入源 JSON 解析失败，请检查格式。");
    }
    const fileSources = await shared.readJsonFile(els.jsonFileInput);
    return [...(Array.isArray(typedSources) ? typedSources : []), ...fileSources];
  }

  async function submitJson(url, payload) {
    const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
    const response = await authFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail?.message || body?.detail || body?.message || "请求失败");
    }
    return body;
  }

  function getCandidateById(candidateId) {
    return state.previewCandidates.find((item) => item.preview_id === candidateId) || null;
  }

  function buildWorkbenchHref(caseId, projectCode) {
    const params = new URLSearchParams();
    if (caseId) {
      params.set("case_id", caseId);
    }
    if (projectCode) {
      params.set("project", projectCode);
    }
    const query = params.toString();
    return query ? `/execution/workbench?${query}` : "/execution/workbench";
  }

  function renderCandidateList() {
    presenter.renderCandidateList(els, state, getCandidateById, (candidateId) => {
      state.selectedCandidateId = candidateId;
      renderCandidateList();
      presenter.renderCandidateDetail(els, getCandidateById(state.selectedCandidateId));
    });
  }

  async function previewPoints() {
    presenter.setText(els.intentSummary, "正在生成候选预览...");
    const inputSources = await collectExtraInputSources();
    const payload = shared.buildGeneratePayload(els, inputSources);
    const body = await submitJson("/api/workbench/preview-test-points", payload);
    const item = body.item || {};
    state.previewCandidates = shared.buildPreviewCandidates(item, els);
    state.selectedCandidateId = state.previewCandidates[0]?.preview_id || "";
    renderCandidateList();
    presenter.setText(
      els.intentSummary,
      `已生成 ${state.previewCandidates.length} 个候选 Draft，测试点 ${item.intent_count || 0} 个，输入来源 ${item.source_count || 0} 路。`
    );
    presenter.setText(els.intentPreview, item.requirement_analysis_markdown || "");
    refreshWizardState();
    if (window.WorkbenchGenerateWizard) window.WorkbenchGenerateWizard.goTo(3);
  }

  async function generateCase(event) {
    if (event) event.preventDefault();
    if (!state.previewCandidates.length) {
      presenter.setText(els.result, "请先生成候选预览，再提交 Draft。");
      if (window.WorkbenchGenerateWizard) window.WorkbenchGenerateWizard.goTo(3);
      return;
    }
    presenter.setText(els.result, "正在生成 Draft...");
    const inputSources = await collectExtraInputSources();
    const payload = shared.buildGeneratePayload(els, inputSources, state.previewCandidates);
    const body = await submitJson("/api/workbench/generate", payload);
    const items = Array.isArray(body.items) && body.items.length ? body.items : [body.item || {}];
    const caseIds = items
      .map((item) => String(item && item.case_id || "").trim())
      .filter(Boolean);
    const generatedCount = Number(body.count || caseIds.length || items.length || 0);
    presenter.setText(els.result, `已生成 ${generatedCount || 1} 条 Draft 用例，下一步请到用例中心审核。`);
    const firstItem = items[0] || {};
    const previewText = caseIds.length
      ? `批量生成 case_id：\n${caseIds.map((id) => `- ${id}`).join("\n")}\n\n---\n\n${String(firstItem.yaml_content || "").trim()}`
      : (firstItem.yaml_content || JSON.stringify(firstItem, null, 2));
    presenter.setText(els.yamlPreview, previewText);
    if (caseIds.length) {
      const firstCaseId = caseIds[0];
      const projectCode = String(firstItem.project_code || payload.project || els.projectSelect?.value || "atp").trim() || "atp";
      els.openCases.href = `/cases/review?project_code=${encodeURIComponent(projectCode)}`;
      els.openWorkbenchResult.href = buildWorkbenchHref(firstCaseId, projectCode);
    }
    if (window.WorkbenchGenerateWizard) window.WorkbenchGenerateWizard.goTo(4);
  }

  function bindStepSignals() {
    [
      els.pageUrlsInput,
      els.requirementInput,
      els.prdTextInput,
      els.prdUrlInput,
      els.prdRequirementInput,
      els.openapiSpecInput,
      els.openapiUrlInput,
      els.apiRequirementInput,
      els.userStoryInput,
      els.storyRequirementInput,
      els.customRequirementInput,
      els.inputSourcesInput,
      els.jsonFileInput,
    ]
      .filter(Boolean)
      .forEach((field) => {
        const eventName = field.tagName === "INPUT" && field.type === "file" ? "change" : "input";
        field.addEventListener(eventName, () => refreshWizardState());
      });
  }

  function bindEvents() {
    els.methodCards.forEach((card) => {
      card.addEventListener("click", () => {
        if (els.methodInput) {
          els.methodInput.value = shared.normalizeMethod(card.dataset.generationMethod);
        }
        renderMethodState();
      });
    });

    els.loadReturnApplyBtn?.addEventListener("click", () => {
      shared.applyReturnApplySample(els);
      renderMethodState();
      if (window.WorkbenchGenerateWizard) window.WorkbenchGenerateWizard.goTo(2);
    });

    els.backToInputBtn?.addEventListener("click", () => {
      if (window.WorkbenchGenerateWizard) window.WorkbenchGenerateWizard.goTo(2);
    });

    els.previewPointsBtn?.addEventListener("click", () => {
      previewPoints().catch((error) => presenter.setText(els.intentSummary, error.message || "预览失败"));
    });
    els.createProjectBtn?.addEventListener("click", () => {
      try {
        openProjectManager();
      } catch (error) {
        presenter.setText(els.result, error.message || "打开项目管理失败");
      }
    });

    els.form?.addEventListener("submit", (event) => {
      generateCase(event).catch((error) => presenter.setText(els.result, error.message || "生成失败"));
    });

    bindStepSignals();
  }

  function bootstrap() {
    loadProjects(String(els.projectSelect?.value || "atp").trim() || "atp").catch(() => {});
    renderMethodState();
    bindEvents();
    if (window.WorkbenchGenerateWizard && typeof window.WorkbenchGenerateWizard.setCanProceed === "function") {
      window.WorkbenchGenerateWizard.setCanProceed((currentStep, nextStep) =>
        support.canProceed(currentStep, nextStep, els, state, shared)
      );
      window.WorkbenchGenerateWizard.goTo(support.resolveInitialStep(window.location.search));
    }
    if (new URLSearchParams(window.location.search).get("sample") === "returnapply") {
      shared.applyReturnApplySample(els);
      renderMethodState();
    }
    renderCandidateList();
    updateAuthNotice();
    refreshWizardState();
  }

  bootstrap();
})();
