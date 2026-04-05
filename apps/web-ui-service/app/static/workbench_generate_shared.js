(function () {
  const METHOD_LABELS = {
    url: "URL 自动生成（推荐）",
    prd: "PRD 文档生成",
    api: "API 生成",
    story: "用户故事生成",
    custom: "自定义输入",
  };

  function normalizeMethod(value) {
    const method = String(value || "").trim().toLowerCase();
    if (METHOD_LABELS[method]) return method;
    return "url";
  }

  function generationMethodLabel(method) {
    return METHOD_LABELS[normalizeMethod(method)] || METHOD_LABELS.url;
  }

  async function readJsonFile(fileInput) {
    const file = fileInput?.files?.[0];
    if (!file) return [];
    const content = await file.text();
    const parsed = JSON.parse(content);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === "object") return [parsed];
    return [];
  }

  function parseJsonObject(text) {
    const raw = String(text || "").trim();
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function splitCsv(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function splitLines(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function resolveRequirement(els, method) {
    if (method === "prd") return String(els.prdRequirementInput?.value || els.requirementInput?.value || "").trim();
    if (method === "api") return String(els.apiRequirementInput?.value || els.requirementInput?.value || "").trim();
    if (method === "story") return String(els.storyRequirementInput?.value || els.requirementInput?.value || "").trim();
    if (method === "custom") return String(els.customRequirementInput?.value || els.requirementInput?.value || "").trim();
    return String(els.requirementInput?.value || "").trim();
  }

  function buildGeneratePayload(els, inputSources) {
    const method = normalizeMethod(els.methodInput?.value);
    const openapiSpec = parseJsonObject(els.openapiSpecInput?.value);
    const payload = {
      project: String(els.projectSelect?.value || "default").trim() || "default",
      page: String(els.pageInput?.value || "").trim(),
      requirement: resolveRequirement(els, method),
      title: String(els.titleInput?.value || "").trim(),
      priority: String(els.prioritySelect?.value || "P1").trim() || "P1",
      source: String(els.sourceSelect?.value || "manual").trim() || "manual",
      tags: splitCsv(els.tagsInput?.value || "ai-generated"),
      input_sources: Array.isArray(inputSources) ? inputSources : [],
      openapi_spec: openapiSpec,
      prd_text: String(els.prdTextInput?.value || "").trim(),
      prd_url: String(els.prdUrlInput?.value || "").trim(),
      user_story: String(els.userStoryInput?.value || "").trim(),
      git_diff: String(els.gitDiffInput?.value || "").trim(),
      git_diff_path: String(els.gitDiffPathInput?.value || "").trim(),
      openapi_url: String(els.openapiUrlInput?.value || "").trim(),
      defect_ticket: String(els.defectTicketInput?.value || "").trim(),
      runtime_logs: String(els.runtimeLogsInput?.value || "").trim(),
      page_urls: splitLines(els.pageUrlsInput?.value || ""),
      generation_method: method,
    };
    return payload;
  }

  function buildPreviewCandidates(item, els) {
    const base = item && typeof item === "object" ? item : {};
    const summary = String(base.requirement_analysis_markdown || "").trim();
    const ruleCount = Number(base.rule_count || 0);
    const ambiguity = Number(base.ambiguity_count || 0);
    const previewPoints = [];
    if (base.quality_gate?.decision) previewPoints.push("质量门决策：" + base.quality_gate.decision);
    if (ruleCount > 0) previewPoints.push("业务规则：" + ruleCount + " 条");
    if (ambiguity > 0) previewPoints.push("歧义点：" + ambiguity + " 条");
    if (!previewPoints.length && summary) previewPoints.push(summary.slice(0, 120));
    if (!previewPoints.length) previewPoints.push("已完成候选预览，请确认后生成 Draft。");

    return [
      {
        preview_id: "candidate-1",
        title: String(els.titleInput?.value || "").trim() || "候选 Draft #1",
        summary: summary ? summary.slice(0, 120) : "基于当前输入生成的候选用例。",
        page: String(base.page || els.pageInput?.value || "").trim(),
        priority: String(base.priority || els.prioritySelect?.value || "P1"),
        tags: splitCsv(els.tagsInput?.value || "ai-generated"),
        test_points: previewPoints,
      },
    ];
  }

  function applyReturnApplySample(els) {
    if (els.methodInput) els.methodInput.value = "url";
    if (els.pageUrlsInput) els.pageUrlsInput.value = "http://127.0.0.1:5173/#/oms/returnApply";
    if (els.requirementInput) els.requirementInput.value = "验证退货申请页面可访问，列表展示正常，查询与详情查看可用。";
    if (els.titleInput) els.titleInput.value = "退货申请基础流程";
    if (els.pageInput) els.pageInput.value = "returnapply";
    if (els.tagsInput) els.tagsInput.value = "ai-generated,smoke,returnapply";
  }

  window.WorkbenchGenerateShared = {
    applyReturnApplySample: applyReturnApplySample,
    buildGeneratePayload: buildGeneratePayload,
    buildPreviewCandidates: buildPreviewCandidates,
    generationMethodLabel: generationMethodLabel,
    normalizeMethod: normalizeMethod,
    readJsonFile: readJsonFile,
  };
})();
