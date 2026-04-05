(function () {
  const shell = document.getElementById("workbench-generate-shell");
  const shared = window.WorkbenchGenerateShared;
  const presenter = window.WorkbenchGeneratePresenter;
  const support = window.WorkbenchGenerateSupport;
  if (!shell || !shared || !support || !presenter) return;

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
  }

  function updateAuthNotice() {
    if (!els.authNotice || !window.platformAuth || typeof window.platformAuth.getCurrentUser !== "function") return;
    const user = window.platformAuth.getCurrentUser() || {};
    const username = String(user.username || user.name || "").trim();
    if (!username) return;
    els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
    els.authNotice.textContent = `${username} 已登录，生成 Draft 与后续审核动作都会保留真实审计记录。`;
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
    const payload = shared.buildGeneratePayload(els, inputSources);
    const body = await submitJson("/api/workbench/generate", payload);
    const item = body.item || {};
    const caseId = String(item.case_id || "").trim();
    presenter.setText(els.result, `已生成 ${caseId || "1 条"} Draft 用例，下一步请到用例中心审核。`);
    presenter.setText(els.yamlPreview, item.yaml_content || JSON.stringify(item, null, 2));
    if (caseId) {
      els.openCases.href = `/cases/${encodeURIComponent(caseId)}`;
      els.openWorkbenchResult.href = `/execution/workbench?case_id=${encodeURIComponent(caseId)}`;
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

    els.form?.addEventListener("submit", (event) => {
      generateCase(event).catch((error) => presenter.setText(els.result, error.message || "生成失败"));
    });

    bindStepSignals();
  }

  function bootstrap() {
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
