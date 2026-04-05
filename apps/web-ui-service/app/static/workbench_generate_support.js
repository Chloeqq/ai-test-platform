(function () {
  function hasText(node) {
    return String(node?.value || "").trim().length > 0;
  }

  function parseJsonArrayLike(node) {
    const text = String(node?.value || "").trim();
    if (!text) return true;
    try {
      const parsed = JSON.parse(text);
      return Array.isArray(parsed) || (parsed && typeof parsed === "object");
    } catch (_error) {
      return false;
    }
  }

  function inputStepStatus(els, shared, method) {
    const normalizedMethod = shared.normalizeMethod(method);
    if (normalizedMethod === "url") {
      if (!hasText(els.pageUrlsInput)) return { ok: false, message: "请至少填写一个页面 URL。" };
      return { ok: true, message: "URL 输入已就绪，可进入候选预览。" };
    }
    if (normalizedMethod === "prd") {
      if (!hasText(els.prdTextInput) && !hasText(els.prdUrlInput)) return { ok: false, message: "请填写 PRD 文本或 PRD 文档 URL。" };
      return { ok: true, message: "PRD 输入已就绪，可进入候选预览。" };
    }
    if (normalizedMethod === "api") {
      if (!hasText(els.openapiSpecInput) && !hasText(els.openapiUrlInput)) return { ok: false, message: "请填写 OpenAPI JSON 或 OpenAPI URL。" };
      return { ok: true, message: "API 输入已就绪，可进入候选预览。" };
    }
    if (normalizedMethod === "story") {
      if (!hasText(els.userStoryInput)) return { ok: false, message: "请填写用户故事内容。" };
      return { ok: true, message: "用户故事输入已就绪，可进入候选预览。" };
    }
    if (!hasText(els.customRequirementInput) && !hasText(els.inputSourcesInput)) {
      return { ok: false, message: "请填写自定义需求描述或附加输入源。" };
    }
    if (!parseJsonArrayLike(els.inputSourcesInput)) {
      return { ok: false, message: "附加输入源 JSON 格式不正确。" };
    }
    return { ok: true, message: "输入已就绪，可进入候选预览。" };
  }

  function previewStepStatus(state) {
    const count = Array.isArray(state?.previewCandidates) ? state.previewCandidates.length : 0;
    if (count > 0) return { ok: true, message: "候选预览已生成，可确认提交。" };
    return { ok: false, message: "请先生成候选预览，再确认提交。" };
  }

  function canProceed(currentStep, nextStep, els, state, shared) {
    if (nextStep <= currentStep) return true;
    if (nextStep <= 2) return true;
    if (nextStep === 3) return inputStepStatus(els, shared, state.method).ok;
    if (nextStep === 4) return previewStepStatus(state).ok;
    return true;
  }

  function resolveInitialStep(search) {
    const params = new URLSearchParams(search || "");
    const step = Number(params.get("step") || 1);
    if (!Number.isFinite(step)) return 1;
    return Math.min(4, Math.max(1, step));
  }

  window.WorkbenchGenerateSupport = {
    canProceed: canProceed,
    inputStepStatus: inputStepStatus,
    previewStepStatus: previewStepStatus,
    resolveInitialStep: resolveInitialStep,
  };
})();
