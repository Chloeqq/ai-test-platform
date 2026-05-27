(function () {
  function hasText(value) {
    return Boolean(String(value || "").trim());
  }

  function hasJsonFile(input) {
    return Boolean(input && input.files && input.files.length);
  }

  function inputStepStatus(els, shared, method) {
    const currentMethod = shared.normalizeMethod(method);
    if (currentMethod === "url") {
      const urls = shared.splitLines(els.pageUrlsInput?.value || "");
      return urls.length
        ? { ok: true, message: `已填写 ${urls.length} 个页面 URL，可进入候选预览。` }
        : { ok: false, message: "请至少填写 1 个页面 URL，再进入候选预览。" };
    }
    if (currentMethod === "prd") {
      const hasContent = hasText(els.prdTextInput?.value) || hasText(els.prdUrlInput?.value);
      return hasContent
        ? { ok: true, message: "已提供 PRD 输入，可进入候选预览。" }
        : { ok: false, message: "请填写 PRD 文本或 PRD 文档 URL。" };
    }
    if (currentMethod === "api") {
      const hasContent = hasText(els.openapiSpecInput?.value) || hasText(els.openapiUrlInput?.value);
      return hasContent
        ? { ok: true, message: "已提供接口契约输入，可进入候选预览。" }
        : { ok: false, message: "请填写 OpenAPI JSON 或 OpenAPI URL。" };
    }
    if (currentMethod === "story") {
      return hasText(els.userStoryInput?.value)
        ? { ok: true, message: "已填写用户故事，可进入候选预览。" }
        : { ok: false, message: "请先填写用户故事。" };
    }
    const hasCustomContent =
      hasText(els.customRequirementInput?.value) ||
      hasText(els.inputSourcesInput?.value) ||
      hasJsonFile(els.jsonFileInput);
    return hasCustomContent
      ? { ok: true, message: "已提供自定义上下文，可进入候选预览。" }
      : { ok: false, message: "请填写自定义需求、输入源 JSON 或导入 JSON 文件。" };
  }

  function previewStepStatus(state) {
    const count = Array.isArray(state.previewCandidates) ? state.previewCandidates.length : 0;
    return count
      ? { ok: true, message: `已生成 ${count} 个候选 Draft，可以提交正式生成。` }
      : { ok: false, message: "请先生成候选预览，确认后再提交 Draft。" };
  }

  function canProceed(currentStep, nextStep, els, state, shared) {
    if (currentStep === 2 && nextStep === 3) {
      return inputStepStatus(els, shared, state.method).ok;
    }
    if (currentStep === 3 && nextStep === 4) {
      return false;
    }
    return true;
  }

  function resolveInitialStep(search) {
    const params = new URLSearchParams(search || "");
    const rawStep = Number(params.get("step") || 1);
    if (!Number.isFinite(rawStep)) return 1;
    return Math.min(3, Math.max(1, rawStep));
  }

  window.WorkbenchGenerateSupport = {
    canProceed,
    inputStepStatus,
    previewStepStatus,
    resolveInitialStep,
  };
})();
