(function () {
  const METHOD_LABELS = {
    url: "URL 自动生成",
    prd: "PRD 文档生成",
    api: "API 生成",
    story: "用户故事生成",
    custom: "自定义输入",
  };

  function normalizeMethod(value) {
    const candidate = String(value || "").trim().toLowerCase();
    return METHOD_LABELS[candidate] ? candidate : "url";
  }

  function generationMethodLabel(value) {
    return METHOD_LABELS[normalizeMethod(value)];
  }

  function readJsonFile(input) {
    const file = input && input.files && input.files[0];
    if (!file) return Promise.resolve([]);
    return file.text().then((text) => {
      try {
        const payload = JSON.parse(text);
        return Array.isArray(payload) ? payload : [];
      } catch (_error) {
        throw new Error("导入 JSON 文件解析失败，请检查格式。");
      }
    });
  }

  function splitLines(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function splitTags(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function parseJsonText(value, fallback) {
    const raw = String(value || "").trim();
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (_error) {
      throw new Error("高级输入源 JSON 解析失败，请检查格式。");
    }
  }

  function dedupeStrings(items) {
    const seen = new Set();
    return items.filter((item) => {
      const value = String(item || "").trim();
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function inferPageFromUrl(rawUrl) {
    const value = String(rawUrl || "").trim();
    if (!value) return "";
    const lowerValue = value.toLowerCase();
    if (lowerValue.includes("/oms/returnapply")) return "returnapply";
    if (lowerValue.includes("/oms/order")) return "order";
    if (lowerValue.includes("/pms/addproduct")) return "addproduct";
    if (lowerValue.includes("/pms/product")) return "product";
    if (lowerValue.includes("/ums/admin")) return "login";
    return "";
  }

  function buildUrlInputSources(pageUrls) {
    return splitLines(pageUrls).map((url) => ({
      source_type: "page_url",
      content: url,
    }));
  }

  function mergeInputSources(primary, secondary) {
    return [...(Array.isArray(primary) ? primary : []), ...(Array.isArray(secondary) ? secondary : [])]
      .filter((item) => item && typeof item === "object")
      .map((item) => ({
        source_type: String(item.source_type || item.type || "").trim(),
        content: String(item.content || item.value || "").trim(),
      }))
      .filter((item) => item.source_type && item.content);
  }

  function resolveRequirementByMethod(els, method) {
    if (method === "prd") {
      return String(els.prdRequirementInput?.value || "").trim();
    }
    if (method === "api") {
      return String(els.apiRequirementInput?.value || "").trim();
    }
    if (method === "story") {
      return String(els.storyRequirementInput?.value || "").trim();
    }
    if (method === "custom") {
      return String(els.customRequirementInput?.value || "").trim();
    }
    return String(els.requirementInput?.value || "").trim();
  }

  function resolvePageField(els, method) {
    const explicitPage = String(els.pageInput?.value || "").trim();
    if (explicitPage) return explicitPage;
    if (method === "url") {
      const firstUrl = splitLines(els.pageUrlsInput?.value || "")[0];
      return inferPageFromUrl(firstUrl);
    }
    return "";
  }

  function applyReturnApplySample(els) {
    if (els.methodInput) {
      els.methodInput.value = "url";
    }
    if (els.pageInput) {
      els.pageInput.value = "returnapply";
    }
    if (els.titleInput) {
      els.titleInput.value = "returnApply 样板回归";
    }
    if (els.prioritySelect) {
      els.prioritySelect.value = "P1";
    }
    if (els.sourceSelect) {
      els.sourceSelect.value = "regression";
    }
    if (els.tagsInput) {
      els.tagsInput.value = "ai-generated,smoke,returnapply";
    }
    if (els.pageUrlsInput) {
      els.pageUrlsInput.value = "http://localhost:5173/#/oms/returnApply";
    }
    if (els.requirementInput) {
      els.requirementInput.value = "验证 returnApply 页面可访问、订单查询可用、提交申请主流程正常，并在生成后回到用例中心审核。";
    }
  }

  function buildGeneratePayload(els, extraInputSources) {
    const method = normalizeMethod(els.methodInput?.value);
    const pageUrls = splitLines(els.pageUrlsInput?.value || "");
    const methodInputSources = method === "url" ? buildUrlInputSources(pageUrls.join("\n")) : [];
    return {
      project: els.projectSelect.value || "default",
      page: resolvePageField(els, method),
      requirement: resolveRequirementByMethod(els, method),
      title: String(els.titleInput?.value || "").trim(),
      priority: els.prioritySelect.value || "P1",
      tags: splitTags(els.tagsInput.value),
      source: els.sourceSelect.value || "manual",
      input_sources: mergeInputSources(methodInputSources, extraInputSources),
      openapi_spec: parseJsonText(els.openapiSpecInput?.value || "", {}),
      prd_text: String(els.prdTextInput?.value || "").trim(),
      prd_url: String(els.prdUrlInput?.value || "").trim(),
      user_story: String(els.userStoryInput?.value || "").trim(),
      git_diff: String(els.gitDiffInput?.value || "").trim(),
      git_diff_path: String(els.gitDiffPathInput?.value || "").trim(),
      openapi_url: String(els.openapiUrlInput?.value || "").trim(),
      defect_ticket: String(els.defectTicketInput?.value || "").trim(),
      runtime_logs: String(els.runtimeLogsInput?.value || "").trim(),
    };
  }

  function buildAutoRunPayload(els, extraInputSources) {
    const payload = buildGeneratePayload(els, extraInputSources);
    return {
      ...payload,
      page_urls: splitLines(els.pageUrlsInput?.value || ""),
      wait_seconds: 240,
    };
  }

  function normalizeTextList(value, fallback) {
    if (Array.isArray(value)) {
      return dedupeStrings(
        value.map((item) => {
          if (typeof item === "string") return item;
          if (!item || typeof item !== "object") return "";
          return String(item.summary || item.description || item.title || item.action || item.value || "").trim();
        })
      );
    }
    const single = String(value || "").trim();
    if (single) return [single];
    return Array.isArray(fallback) ? fallback : [];
  }

  function buildPreviewCandidates(item, els) {
    const requirementSpec = item && typeof item.requirement_spec === "object" ? item.requirement_spec : {};
    const method = normalizeMethod(els.methodInput?.value);
    const previewPage = String(requirementSpec.page || resolvePageField(els, method) || "common").trim() || "common";
    const previewPriority = String(requirementSpec.priority || els.prioritySelect.value || "P1").trim() || "P1";
    const previewSource = String(els.sourceSelect.value || "manual").trim() || "manual";
    const baseTags = splitTags(els.tagsInput?.value || "");
    const intents = Array.isArray(requirementSpec.test_intents) ? requirementSpec.test_intents : [];
    if (!intents.length) {
      const fallbackTitle = String(els.titleInput?.value || "").trim() || `${generationMethodLabel(method)}候选 Draft`;
      const fallbackSummary = resolveRequirementByMethod(els, method) || "系统将根据当前输入生成基础验证场景。";
      return [
        {
          preview_id: "draft-01",
          title: fallbackTitle,
          page: previewPage,
          priority: previewPriority,
          source: previewSource,
          intent_type: "functional",
          tags: baseTags,
          steps: [fallbackSummary],
          expected_results: ["生成后请在用例中心继续审核结构化字段与步骤细节。"],
        },
      ];
    }

    return intents.map((intent, index) => {
      const summary = String(intent?.summary || intent?.title || "").trim() || `候选 Draft ${index + 1}`;
      const intentType = String(intent?.intent_type || "functional").trim() || "functional";
      const steps = normalizeTextList(intent?.steps_hint || intent?.steps, [summary]);
      const expectedResults = normalizeTextList(intent?.acceptance_criteria || intent?.assertions, [
        String(intent?.description || "").trim() || summary,
      ]);
      return {
        preview_id: `draft-${String(index + 1).padStart(2, "0")}`,
        title: summary,
        page: previewPage,
        priority: String(intent?.priority || previewPriority).trim() || previewPriority,
        source: previewSource,
        intent_type: intentType,
        tags: dedupeStrings([...baseTags, intentType]),
        steps,
        expected_results: expectedResults,
      };
    });
  }

  window.WorkbenchGenerateShared = {
    applyReturnApplySample,
    buildAutoRunPayload,
    buildGeneratePayload,
    buildPreviewCandidates,
    generationMethodLabel,
    inferPageFromUrl,
    normalizeMethod,
    readJsonFile,
    splitLines,
  };
})();
