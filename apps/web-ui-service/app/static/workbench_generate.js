(function () {
  const shell = document.getElementById("workbench-generate-shell");
  if (!shell) return;

  const els = {
    form: document.getElementById("wb-generate-form"),
    projectSelect: document.getElementById("gen-project"),
    pageInput: document.getElementById("gen-page"),
    titleInput: document.getElementById("gen-title"),
    prioritySelect: document.getElementById("gen-priority"),
    sourceSelect: document.getElementById("gen-source"),
    tagsInput: document.getElementById("gen-tags"),
    requirementInput: document.getElementById("gen-requirement"),
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
    result: document.getElementById("gen-result"),
    yamlPreview: document.getElementById("gen-yaml-preview"),
    openPreview: document.getElementById("gen-open-preview"),
    previewPointsBtn: document.getElementById("gen-preview-points"),
    intentSummary: document.getElementById("gen-intent-summary"),
    intentPreview: document.getElementById("gen-intent-preview"),
    autoRunBtn: document.getElementById("gen-auto-run"),
    autoResult: document.getElementById("gen-auto-result"),
    autoOutput: document.getElementById("gen-auto-output"),
    reviewSummary: document.getElementById("gen-review-summary"),
    reviewPanel: document.getElementById("gen-review-panel"),
    auditTimeline: document.getElementById("gen-audit-timeline"),
    authNotice: document.getElementById("gen-auth-notice"),
    openWorkbench: document.getElementById("gen-open-workbench"),
    loadReturnApplyBtn: document.getElementById("gen-load-returnapply"),
  };

  const state = {
    project: "default",
    reviewActions: {},
    gateActions: {},
    lastAutoRunPayload: null,
    deepLinkRunId: "",
    focusReviewType: "",
    focusPage: "",
    sampleKey: "",
    executionGateConfig: null,
  };

  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
  const searchParams = new URLSearchParams(window.location.search || "");
  state.project = String(searchParams.get("project") || "default").trim() || "default";
  state.deepLinkRunId = String(searchParams.get("run_id") || "").trim();
  state.focusReviewType = String(searchParams.get("review_type") || "").trim().toLowerCase();
  state.focusPage = String(searchParams.get("page") || "").trim().toLowerCase();
  state.sampleKey = String(searchParams.get("sample") || "").trim().toLowerCase();

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeTags(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  function setResult(text) {
    els.result.textContent = text;
  }

  function setAutoResult(text) {
    els.autoResult.textContent = text;
  }

  function setReviewSummary(text) {
    if (els.reviewSummary) {
      els.reviewSummary.textContent = text;
    }
  }

  function setIntentSummary(text) {
    els.intentSummary.textContent = text;
  }

  function currentAuthState() {
    if (window.platformAuth && typeof window.platformAuth.getAuthState === "function") {
      return String(window.platformAuth.getAuthState() || "anonymous").toLowerCase();
    }
    return "anonymous";
  }

  function currentUserProfile() {
    if (window.platformAuth && typeof window.platformAuth.getCurrentUser === "function") {
      return window.platformAuth.getCurrentUser() || {};
    }
    return {};
  }

  function currentUserName() {
    const user = currentUserProfile();
    return String(user?.username || user?.name || "").trim();
  }

  function currentUserRole() {
    const user = currentUserProfile();
    return String(user?.role || "").trim().toLowerCase();
  }

  function isAuthenticatedForAudit() {
    const authState = currentAuthState();
    return authState === "authenticated" || authState === "token";
  }

  function executionGateConfigList(name, fallback = []) {
    const values = state.executionGateConfig && Array.isArray(state.executionGateConfig[name])
      ? state.executionGateConfig[name]
      : fallback;
    return values
      .map((item) => String(item || "").trim().toLowerCase())
      .filter((item) => item.length > 0);
  }

  function isExecutionGatePrivilegedUser() {
    if (!isAuthenticatedForAudit()) return false;
    const privilegedRoles = executionGateConfigList("decision_privileged_roles", ["admin", "qa-lead", "release-manager"]);
    const role = currentUserRole();
    return privilegedRoles.includes(role);
  }

  function canApproveExecutionGateDecision() {
    if (!isExecutionGatePrivilegedUser()) return false;
    if (!state.executionGateConfig || !state.executionGateConfig.dual_approval_enabled) {
      return isExecutionGatePrivilegedUser();
    }
    return isExecutionGatePrivilegedUser();
  }

  function canRevokeExecutionGateDecision(decisionMaker) {
    if (!isAuthenticatedForAudit()) return false;
    if (isExecutionGatePrivilegedUser()) return true;
    const username = currentUserName();
    return Boolean(username) && String(decisionMaker || "").trim() === username;
  }

  function loginRedirectTarget() {
    return `/login?next=${encodeURIComponent(`${window.location.pathname}${window.location.search || ""}`)}`;
  }

  function updateAuthNotice() {
    if (!els.authNotice) return;
    if (isAuthenticatedForAudit()) {
      const currentUser = window.platformAuth && typeof window.platformAuth.getCurrentUser === "function"
        ? window.platformAuth.getCurrentUser()
        : null;
      const username = String(currentUser?.username || currentUser?.name || "当前用户").trim();
      els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
      els.authNotice.textContent = `${username} 已登录，后续确认点会写入真实审计记录。`;
      return;
    }
    els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
    els.authNotice.textContent = "当前为未登录状态：你仍可生成、预览和执行，但确认点属于审计动作，提交前会要求先登录。";
  }

  function formatQualityGateSummary(gate) {
    if (!gate || typeof gate !== "object") return "";
    const decision = String(gate.decision || "-").toLowerCase();
    const stage = String(gate.stage || "-");
    const metrics = gate.metrics && typeof gate.metrics === "object" ? gate.metrics : {};
    const blockers = Array.isArray(gate.blockers) ? gate.blockers : [];
    const parseConfidence = metrics.parse_confidence ?? "-";
    const intentCount = metrics.test_intent_count ?? "-";
    const gapRatio = metrics.coverage_gap_ratio ?? "-";
    return `quality_gate=${decision} stage=${stage} confidence=${parseConfidence} intents=${intentCount} gap_ratio=${gapRatio} blockers=${blockers.length}`;
  }

  function formatErrorDetail(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (typeof detail !== "object") return String(detail);
    const message = String(detail.message || detail.detail || detail.code || "请求失败");
    const gate = detail.quality_gate && typeof detail.quality_gate === "object" ? detail.quality_gate : null;
    if (!gate) return message;
    return `${message}; ${formatQualityGateSummary(gate)}`;
  }

  function confidenceClass(value) {
    const numeric = Number(value || 0);
    if (numeric >= 0.85) return "wb-badge wb-badge-high";
    if (numeric >= 0.6) return "wb-badge wb-badge-medium";
    return "wb-badge wb-badge-low";
  }

  function confidenceLabel(value) {
    const numeric = Number(value || 0);
    if (numeric >= 0.85) return `高置信度 ${Math.round(numeric * 100)}%`;
    if (numeric >= 0.6) return `中置信度 ${Math.round(numeric * 100)}%`;
    return `低置信度 ${Math.round(numeric * 100)}%`;
  }

  function formatTime(value) {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString("zh-CN");
    } catch (_error) {
      return String(value);
    }
  }

  function reviewStatusLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "confirmed") return "已确认";
    if (normalized === "skipped") return "已跳过";
    if (normalized === "not_required") return "无需确认";
    return "待确认";
  }

  function reviewStatusClass(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "confirmed") return "wb-badge wb-badge-high";
    if (normalized === "skipped" || normalized === "pending") return "wb-badge wb-badge-medium";
    return "wb-badge wb-badge-low";
  }

  function gateDecisionLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "block") return "阻断";
    if (normalized === "manual_review") return "人工复核";
    return "放行";
  }

  function gateDecisionClass(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "block") return "wb-badge wb-badge-low";
    if (normalized === "manual_review") return "wb-badge wb-badge-medium";
    return "wb-badge wb-badge-high";
  }

  function gateApprovalLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "pending_second_approval") return "待二次审批";
    if (normalized === "approved") return "已审批";
    if (normalized === "revoked") return "已撤销";
    return "未知";
  }

  function gateApprovalClass(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "approved") return "wb-badge wb-badge-high";
    if (normalized === "pending_second_approval") return "wb-badge wb-badge-medium";
    if (normalized === "revoked") return "wb-badge wb-badge-low";
    return "wb-badge";
  }

  function gateNextAction(decision) {
    const normalized = String(decision || "").trim().toLowerCase();
    if (normalized === "block") {
      return "下一步：先修复阻断项，再重新生成或重跑；当前不建议直接放行。";
    }
    if (normalized === "manual_review") {
      return "下一步：先完成元素 / 测试点 / 风险确认，再根据结果选择人工放行或人工阻断。";
    }
    return "下一步：当前链路可继续推进；如无新增异常，可进入后续执行或发布判断。";
  }

  function formatGateMetrics(metrics) {
    const data = metrics && typeof metrics === "object" ? metrics : {};
    const rows = [
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
    ];
    return rows.join(" · ");
  }

  function formatGateConfigSnapshot(snapshot) {
    const data = snapshot && typeof snapshot === "object" ? snapshot : {};
    const rows = [
      `缺失必需元素阻断阈值=${Number(data.block_missing_required_threshold || 0)}`,
      `未识别依赖阻断阈值=${Number(data.block_missing_dependency_points_threshold || 0)}`,
      `失败即阻断=${Boolean(data.block_on_failed_status)}`,
      `风险阻断联动=${Boolean(data.block_on_risk_block)}`,
      `低置信度元素告警=${Boolean(data.warn_on_low_confidence_elements)}`,
      `待确认测试点告警=${Boolean(data.warn_on_pending_test_points)}`,
      `低置信度依赖告警=${Boolean(data.warn_on_low_confidence_dependency_points)}`,
      `待确认分组告警=${Boolean(data.warn_on_pending_reviews)}`,
    ];
    return rows.join(" · ");
  }

  function normalizeUrls(value) {
    return String(value || "")
      .split("\n")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  function inferPageFromUrl(rawUrl) {
    const value = String(rawUrl || "").trim();
    if (!value) return "";
    try {
      const parsed = new URL(value);
      const route = parsed.hash && parsed.hash !== "#" ? parsed.hash.slice(1) : parsed.pathname;
      const segments = String(route || "")
        .split("/")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean);
      return segments.length ? segments[segments.length - 1] : "";
    } catch (_error) {
      return "";
    }
  }

  function deriveRequirement({ requirement, page, pageUrls, hasMultiSource }) {
    const manualRequirement = String(requirement || "").trim();
    if (manualRequirement) return manualRequirement;
    if (hasMultiSource) {
      return "多输入源需求驱动的页面核心流程验证";
    }
    const inferredPage = String(page || "").trim() || inferPageFromUrl((pageUrls || [])[0] || "");
    const pageLabel = inferredPage || "目标";
    return `自动生成的页面测试目标：验证 ${pageLabel} 页面可访问、关键区域可见、核心基础交互可执行。`;
  }

  function syncPageFromUrls() {
    if (!els.pageInput) return;
    const current = String(els.pageInput.value || "").trim();
    if (current) return;
    const urls = normalizeUrls(els.pageUrlsInput?.value);
    const inferred = inferPageFromUrl(urls[0] || "");
    if (inferred) {
      els.pageInput.value = inferred;
    }
  }

  function parseJsonText(text, label) {
    const trimmed = String(text || "").trim();
    if (!trimmed) return null;
    try {
      return JSON.parse(trimmed);
    } catch (_error) {
      throw new Error(`${label} 不是合法 JSON`);
    }
  }

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function flattenPostmanCollection(collection) {
    const records = [];

    function walkItems(items) {
      if (!Array.isArray(items)) return;
      items.forEach((item) => {
        if (!item || typeof item !== "object") return;
        if (Array.isArray(item.item)) {
          walkItems(item.item);
          return;
        }
        const request = item.request || {};
        const method = String(request.method || "").toUpperCase();
        let url = "";
        if (typeof request.url === "string") {
          url = request.url;
        } else if (request.url && typeof request.url === "object") {
          const raw = request.url.raw;
          if (typeof raw === "string") {
            url = raw;
          }
        }
        if (!method || !url) return;
        records.push(`${method} ${url}`);
      });
    }

    walkItems(collection.item);
    return records;
  }

  async function readJsonFile(file) {
    if (!file) return null;
    const content = await file.text();
    if (!String(content || "").trim()) return null;
    try {
      return JSON.parse(content);
    } catch (_error) {
      throw new Error("上传的 JSON 文件格式无效");
    }
  }

  async function collectMultiSourcePayload() {
    const patch = {};
    const openapiSpec = parseJsonText(els.openapiSpecInput?.value, "OpenAPI JSON");
    if (openapiSpec) {
      if (!isObject(openapiSpec)) {
        throw new Error("OpenAPI JSON 必须是对象");
      }
      patch.openapi_spec = openapiSpec;
    }

    const inputSources = parseJsonText(els.inputSourcesInput?.value, "附加输入源 JSON");
    if (inputSources) {
      if (!Array.isArray(inputSources)) {
        throw new Error("附加输入源 JSON 必须是数组");
      }
      patch.input_sources = inputSources.filter((item) => isObject(item));
    }

    if (els.prdTextInput?.value.trim()) patch.prd_text = els.prdTextInput.value.trim();
    if (els.prdUrlInput?.value.trim()) patch.prd_url = els.prdUrlInput.value.trim();
    if (els.userStoryInput?.value.trim()) patch.user_story = els.userStoryInput.value.trim();
    if (els.gitDiffInput?.value.trim()) patch.git_diff = els.gitDiffInput.value.trim();
    if (els.gitDiffPathInput?.value.trim()) patch.git_diff_path = els.gitDiffPathInput.value.trim();
    if (els.defectTicketInput?.value.trim()) patch.defect_ticket = els.defectTicketInput.value.trim();
    if (els.runtimeLogsInput?.value.trim()) patch.runtime_logs = els.runtimeLogsInput.value.trim();
    if (els.openapiUrlInput?.value.trim()) patch.openapi_url = els.openapiUrlInput.value.trim();

    const filePayload = await readJsonFile(els.jsonFileInput?.files?.[0]);
    if (filePayload) {
      if (isObject(filePayload) && (filePayload.openapi || filePayload.swagger || filePayload.paths)) {
        patch.openapi_spec = filePayload;
      } else if (isObject(filePayload) && Array.isArray(filePayload.item)) {
        const postmanLines = flattenPostmanCollection(filePayload);
        if (postmanLines.length) {
          if (!Array.isArray(patch.input_sources)) patch.input_sources = [];
          patch.input_sources.push({
            source_type: "postman",
            content: postmanLines.join("\n"),
            metadata: {
              name: String((filePayload.info || {}).name || "postman_collection"),
            },
          });
        }
      } else if (Array.isArray(filePayload)) {
        if (!Array.isArray(patch.input_sources)) patch.input_sources = [];
        patch.input_sources.push(...filePayload.filter((item) => isObject(item)));
      } else if (isObject(filePayload)) {
        if (Array.isArray(filePayload.input_sources)) {
          if (!Array.isArray(patch.input_sources)) patch.input_sources = [];
          patch.input_sources.push(...filePayload.input_sources.filter((item) => isObject(item)));
        }
        if (isObject(filePayload.openapi_spec) && !patch.openapi_spec) {
          patch.openapi_spec = filePayload.openapi_spec;
        }
        ["prd_text", "user_story", "git_diff", "defect_ticket", "runtime_logs"].forEach((field) => {
          if (!patch[field] && typeof filePayload[field] === "string" && filePayload[field].trim()) {
            patch[field] = filePayload[field].trim();
          }
        });
        ["prd_url", "openapi_url", "git_diff_path"].forEach((field) => {
          if (!patch[field] && typeof filePayload[field] === "string" && filePayload[field].trim()) {
            patch[field] = filePayload[field].trim();
          }
        });
      }
    }

    if (Array.isArray(patch.input_sources) && !patch.input_sources.length) {
      delete patch.input_sources;
    }
    return patch;
  }

  function hasMultiSourcePayload(payload) {
    return [
      Array.isArray(payload.input_sources) && payload.input_sources.length > 0,
      payload.openapi_spec && typeof payload.openapi_spec === "object",
      payload.prd_text,
      payload.prd_url,
      payload.user_story,
      payload.git_diff,
      payload.git_diff_path,
      payload.openapi_url,
      payload.defect_ticket,
      payload.runtime_logs,
    ].some(Boolean);
  }

  async function buildGeneratePayload() {
    syncPageFromUrls();
    const payload = {
      project: els.projectSelect.value || "default",
      page: els.pageInput.value.trim(),
      title: els.titleInput.value.trim(),
      priority: els.prioritySelect.value || "P1",
      source: els.sourceSelect?.value || "manual",
      tags: normalizeTags(els.tagsInput.value),
      requirement: els.requirementInput.value.trim(),
    };
    Object.assign(payload, await collectMultiSourcePayload());
    if (!payload.tags.length) {
      payload.tags = ["ai-generated"];
    }
    payload.requirement = deriveRequirement({
      requirement: payload.requirement,
      page: payload.page,
      pageUrls: normalizeUrls(els.pageUrlsInput?.value),
      hasMultiSource: hasMultiSourcePayload(payload),
    });
    return payload;
  }

  function renderIntentPreview(spec, qualityGate) {
    const intents = Array.isArray(spec?.test_intents) ? spec.test_intents : [];
    const ambiguities = Array.isArray(spec?.ambiguities) ? spec.ambiguities : [];
    const rules = Array.isArray(spec?.business_rules) ? spec.business_rules : [];
    const coverage = Array.isArray(spec?.coverage_matrix) ? spec.coverage_matrix : [];
    const lines = [];

    intents.forEach((intent, index) => {
      const title = intent?.title || "-";
      const intentType = intent?.intent_type || "unknown";
      const priority = intent?.priority || "P1";
      const deps = Array.isArray(intent?.dependencies) && intent.dependencies.length ? intent.dependencies.join(",") : "-";
      lines.push(`${index + 1}. [${intentType}/${priority}] ${title}`);
      lines.push(`   deps=${deps} steps=${Array.isArray(intent?.steps_hint) ? intent.steps_hint.join(",") : "-"}`);
    });
    if (ambiguities.length) {
      lines.push("");
      lines.push("Ambiguities:");
      ambiguities.forEach((item, index) => {
        lines.push(`${index + 1}. [${item?.severity || "medium"}] ${item?.text || "-"}`);
      });
    }
    if (rules.length) {
      lines.push("");
      lines.push("Business Rules:");
      rules.forEach((item, index) => {
        lines.push(`${index + 1}. [${item?.rule_type || "rule"}] ${item?.rule_text || "-"}`);
      });
    }
    if (coverage.length) {
      lines.push("");
      lines.push("Coverage:");
      coverage.slice(0, 20).forEach((row) => {
        const sourceType = row?.source_type || "-";
        const sourceId = row?.source_id || "-";
        const intentIds = Array.isArray(row?.intent_ids) ? row.intent_ids.join(",") : "-";
        lines.push(`- ${sourceId}/${sourceType} -> ${intentIds}`);
      });
    }
    if (qualityGate && typeof qualityGate === "object") {
      const blockers = Array.isArray(qualityGate.blockers) ? qualityGate.blockers : [];
      lines.push("");
      lines.push("Quality Gate:");
      lines.push(`- decision=${qualityGate.decision || "-"} stage=${qualityGate.stage || "-"}`);
      if (blockers.length) {
        blockers.forEach((blocker, index) => {
          const blockerCode = blocker?.code || "unknown";
          const blockerMessage = blocker?.message || "-";
          lines.push(`  ${index + 1}. ${blockerCode}: ${blockerMessage}`);
        });
      }
    }
    els.intentPreview.textContent = lines.join("\n");
  }

  async function handlePreviewPoints() {
    setIntentSummary("解析中，请稍候...");
    els.intentPreview.textContent = "";
    let payload = {};
    try {
      payload = await buildGeneratePayload();
    } catch (error) {
      alert(error?.message || "多输入源 JSON 解析失败");
      setIntentSummary("解析失败。");
      return;
    }
    if (els.previewPointsBtn) {
      els.previewPointsBtn.disabled = true;
    }
    try {
      const resp = await authFetch("/api/workbench/preview-test-points", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setIntentSummary(`解析失败：${data.detail || resp.statusText}`);
        els.intentPreview.textContent = JSON.stringify(data, null, 2);
        return;
      }
      const item = data.item || {};
      const spec = item.requirement_spec || {};
      const qualityGate = item.quality_gate && typeof item.quality_gate === "object" ? item.quality_gate : null;
      const analysisMarkdown = typeof item.requirement_analysis_markdown === "string" ? item.requirement_analysis_markdown.trim() : "";
      const resolvedPage = item.page || spec.page || "";
      if (!els.pageInput.value.trim() && resolvedPage) {
        els.pageInput.value = resolvedPage;
      }
      const gateSummary = qualityGate ? `，${formatQualityGateSummary(qualityGate)}` : "";
      setIntentSummary(
        `解析完成：page=${resolvedPage || "-"}，priority=${item.priority || "-"}，测试点=${item.intent_count || 0}，消歧=${item.ambiguity_count || 0}，规则=${item.rule_count || 0}，confidence=${item.parse_confidence || 0}${gateSummary}`
      );
      renderIntentPreview(spec, qualityGate);
      if (analysisMarkdown) {
        els.intentPreview.textContent = `${analysisMarkdown}\n---\n${els.intentPreview.textContent}`;
      }
    } catch (error) {
      console.error(error);
      setIntentSummary("解析失败，请检查服务状态。");
    } finally {
      if (els.previewPointsBtn) {
        els.previewPointsBtn.disabled = false;
      }
    }
  }

  function setPreviewLink(caseId, project) {
    if (!caseId) {
      els.openPreview.setAttribute("href", "#");
      return;
    }
    const query = new URLSearchParams({
      case_id: caseId,
      project: project || "default",
    });
    els.openPreview.setAttribute("href", `/workbench/preview?${query.toString()}`);
  }

  function setWorkbenchLink(runId, caseId, project) {
    if (!els.openWorkbench) return;
    if (!runId && !caseId) {
      els.openWorkbench.href = "/workbench";
      els.openWorkbench.setAttribute("aria-disabled", "true");
      return;
    }
    const query = new URLSearchParams({
      project: project || state.project || "default",
    });
    if (runId) {
      query.set("run_id", runId);
    }
    if (caseId) {
      query.set("case_id", caseId);
    }
    els.openWorkbench.href = `/workbench?${query.toString()}`;
    els.openWorkbench.removeAttribute("aria-disabled");
  }

  function applyGenerateSample(sampleKey) {
    const normalized = String(sampleKey || "").trim().toLowerCase();
    if (normalized !== "returnapply") {
      return false;
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
      els.requirementInput.value = "验证退货申请页面可访问，服务单号查询可用，并可从生成页回流到工作台查看结果。";
    }
    setPreviewLink("", state.project);
    setWorkbenchLink("", "", state.project);
    syncPageFromUrls();
    setResult("已载入 returnApply 样板。可直接预览、生成或一键执行。");
    return true;
  }

  async function loadProjects() {
    const resp = await authFetch("/api/workbench/projects");
    if (!resp.ok) throw new Error("load projects failed");
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) items.push("default");
    els.projectSelect.innerHTML = items
      .map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`)
      .join("");
    if (!items.includes(state.project)) {
      state.project = items[0];
    }
    els.projectSelect.value = state.project;
  }

  async function loadExecutionGateConfig() {
    try {
      const resp = await authFetch("/api/workbench/execution-gate/config");
      if (!resp.ok) {
        state.executionGateConfig = null;
        return;
      }
      const payload = await resp.json().catch(() => ({}));
      state.executionGateConfig = payload?.item && typeof payload.item === "object" ? payload.item : null;
    } catch (_error) {
      state.executionGateConfig = null;
    }
  }

  function renderAutoOutput(payload) {
    const items = payload.items || [];
    if (!items.length) {
      els.autoOutput.textContent = JSON.stringify(payload, null, 2);
      return;
    }
    const lines = items.map((item, index) => {
      const status = item.status || "-";
      const page = item.page || "-";
      const pageUrl = item.page_url || "-";
      const caseId = item.case_id || "-";
      const runId = item.run_id || "-";
      const poSummary = item.page_object_summary && typeof item.page_object_summary === "object" ? item.page_object_summary : {};
      const missingRequired = Array.isArray(poSummary.missing_required) ? poSummary.missing_required : [];
      const defaultsUsed = Array.isArray(poSummary.defaults_used) ? poSummary.defaults_used : [];
      const addedFromSurface = Array.isArray(poSummary.added_from_surface) ? poSummary.added_from_surface : [];
      const inferredCandidates = Array.isArray(poSummary.inferred_candidates) ? poSummary.inferred_candidates : [];
      const poStatus = poSummary.status || "-";
      const poTotal = poSummary.total_elements ?? "-";
      const requiredCount = poSummary.required_count ?? "-";
      const missingCount = poSummary.missing_required_count ?? "-";
      const poConfidence = poSummary.confidence ?? "-";
      const surfaceHealth = poSummary.surface_health || "-";
      const authState = poSummary.auth_state && typeof poSummary.auth_state === "object" ? poSummary.auth_state : {};
      const loadState = poSummary.load_state && typeof poSummary.load_state === "object" ? poSummary.load_state : {};
      const nextActions = Array.isArray(item?.page_object?.next_actions) ? item.page_object.next_actions : [];
      const surfaceSummary = item.page_surface_summary && typeof item.page_surface_summary === "object" ? item.page_surface_summary : {};
      const surfaceConfidence = surfaceSummary.confidence ?? "-";
      const pointPlan = item.test_points && typeof item.test_points === "object" ? item.test_points : {};
      const pointConfidence = pointPlan.confidence ?? "-";
      const executionGate = item.execution_gate && typeof item.execution_gate === "object" ? item.execution_gate : {};
      const gateDecision = String(executionGate.effective_decision || executionGate.decision || "").trim() || "allow";
      const gateBlockers = Array.isArray(executionGate.blockers) ? executionGate.blockers.filter(Boolean) : [];
      const gateWarnings = Array.isArray(executionGate.warnings) ? executionGate.warnings.filter(Boolean) : [];
      const gateEvidence = Array.isArray(executionGate.evidence) ? executionGate.evidence.filter(Boolean) : [];
      const manualDecision = executionGate.manual_decision && typeof executionGate.manual_decision === "object" ? executionGate.manual_decision : {};

      const block = [
        `${index + 1}. [${status}] page=${page} url=${pageUrl}`,
        `   case=${caseId} run=${runId}`,
        `   confidence surface=${surfaceConfidence} page_object=${poConfidence} test_points=${pointConfidence}`,
        `   execution_gate=${gateDecision} source=${executionGate.decision_source || "system"} blockers=${gateBlockers.length} warnings=${gateWarnings.length}`,
        `   page_object=${poStatus} total=${poTotal} required=${requiredCount} missing=${missingCount}`,
        `   from_surface=${addedFromSurface.join(",") || "-"} defaults=${defaultsUsed.join(",") || "-"}`,
        `   inferred=${inferredCandidates.join(",") || "-"}`,
        `   surface_health=${surfaceHealth} auth_login=${String(authState.login_success ?? "-")} route_mismatch=${String(loadState.route_mismatch ?? "-")} marker=${loadState.marker_selector || "-"}`,
      ];
      if (missingRequired.length) {
        block.push(`   missing_required=${missingRequired.join(",")}`);
      }
      if (nextActions.length) {
        block.push(`   next_actions=${nextActions.join(" | ")}`);
      }
      if (gateBlockers.length) {
        block.push(`   gate_blockers=${gateBlockers.join(" | ")}`);
      }
      if (gateWarnings.length) {
        block.push(`   gate_warnings=${gateWarnings.join(" | ")}`);
      }
      if (gateEvidence.length) {
        block.push(`   gate_evidence=${gateEvidence.join(" | ")}`);
      }
      if (manualDecision && Object.keys(manualDecision).length) {
        block.push(`   gate_manual=${manualDecision.decision || "-"} by=${manualDecision.decided_by || "-"} note=${manualDecision.note || "-"}`);
      }
      return block.join("\n");
    });
    lines.push("");
    lines.push(`Allure: ${payload?.allure?.refresh?.allure_index || payload?.allure?.error || "-"}`);
    els.autoOutput.textContent = lines.join("\n");
  }

  function summarizeAutoPayload(payload) {
    const items = Array.isArray(payload?.items) ? payload.items : [];
    return {
      total: items.length,
      passed: items.filter((item) => String(item?.status || "").toLowerCase() === "passed").length,
      failed: items.filter((item) => String(item?.status || "").toLowerCase() === "failed").length,
      coverage_gap: items.filter((item) => String(item?.status || "").toLowerCase() === "coverage_gap").length,
      generate_failed: items.filter((item) => String(item?.status || "").toLowerCase() === "generate_failed").length,
      pending_reviews: items.reduce((count, item) => {
        const reviewState = item?.review_state && typeof item.review_state === "object" ? item.review_state : {};
        return count + (Number(reviewState.pending_sections || 0) || 0);
      }, 0),
      confirmed_reviews: items.reduce((count, item) => {
        const reviewState = item?.review_state && typeof item.review_state === "object" ? item.review_state : {};
        return count + (Number(reviewState.confirmed_sections || 0) || 0);
      }, 0),
      gate_blocked: items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "block").length,
      gate_manual_review: items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "manual_review").length,
      gate_allow: items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "allow").length,
    };
  }

  function refreshAutoResultFromPayload(payload) {
    const summary = summarizeAutoPayload(payload);
    setAutoResult(
      `自动链路完成：总数 ${summary.total || 0}，通过 ${summary.passed || 0}，失败 ${summary.failed || 0}，覆盖缺口 ${summary.coverage_gap || 0}，生成失败 ${summary.generate_failed || 0}，待确认 ${summary.pending_reviews || 0}，门禁阻断 ${summary.gate_blocked || 0}，门禁复核 ${summary.gate_manual_review || 0}`
    );
  }

  function renderAuditTimeline(payload) {
    if (!els.auditTimeline) return;
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const timelineBlocks = items
      .map((item, index) => {
        const page = String(item?.page || `page-${index + 1}`);
        const runId = String(item?.run_id || "");
        const rows = Array.isArray(item?.review_audit_timeline) ? item.review_audit_timeline : [];
        if (!rows.length) {
          return `
            <section class="wb-audit-card">
              <h3>${escapeHtml(page)} 审计时间线</h3>
              <div class="wb-audit-line">当前运行 ${escapeHtml(runId || "-")} 暂无确认、拒绝或风险决策审计事件。</div>
            </section>
          `;
        }
        return `
          <section class="wb-audit-card">
            <h3>${escapeHtml(page)} 审计时间线</h3>
            ${rows.map((entry, rowIndex) => `
              <div class="wb-audit-line ${state.focusReviewType && state.focusReviewType === String(entry.review_type || "").trim().toLowerCase() && (!state.focusPage || state.focusPage === page.toLowerCase()) ? "wb-audit-line-active" : ""}">
                <strong>${rowIndex + 1}. ${escapeHtml(entry.detail_summary || entry.action || "-")}</strong>
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
      })
      .join("");

    if (!timelineBlocks) {
      els.auditTimeline.className = "wb-audit-panel wb-review-empty";
      els.auditTimeline.innerHTML = "当前批次暂无审计时间线。";
      return;
    }
    els.auditTimeline.className = "wb-audit-panel";
    els.auditTimeline.innerHTML = timelineBlocks;
  }

  function mergeRunSnapshotIntoAutoPayload(runItem) {
    if (!state.lastAutoRunPayload || !runItem || typeof runItem !== "object") return false;
    const items = Array.isArray(state.lastAutoRunPayload.items) ? state.lastAutoRunPayload.items : [];
    const runId = String(runItem.run_id || "");
    if (!runId) return false;
    const target = items.find((item) => String(item?.run_id || "") === runId);
    if (!target) return false;
    target.status = runItem.status || target.status;
    if (runItem.review_state && typeof runItem.review_state === "object") {
      target.review_state = runItem.review_state;
    }
    if (runItem.risk_report && typeof runItem.risk_report === "object") {
      target.risk_report = runItem.risk_report;
    }
    if (runItem.execution_gate && typeof runItem.execution_gate === "object") {
      target.execution_gate = runItem.execution_gate;
    }
    if (runItem.coverage && typeof runItem.coverage === "object") {
      target.coverage = runItem.coverage;
    }
    if (runItem.page_object_summary && typeof runItem.page_object_summary === "object") {
      target.page_object_summary = runItem.page_object_summary;
    }
    if (runItem.review_audit_summary && typeof runItem.review_audit_summary === "object") {
      target.review_audit_summary = runItem.review_audit_summary;
    }
    if (Array.isArray(runItem.review_audit_timeline)) {
      target.review_audit_timeline = runItem.review_audit_timeline;
    }
    return true;
  }

  async function refreshAutoRunState(runId) {
    if (!runId) return false;
    const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`);
    if (!resp.ok) {
      throw new Error(`刷新运行状态失败：${resp.statusText}`);
    }
    const payload = await resp.json().catch(() => ({}));
    const runItem = payload?.item;
    const merged = mergeRunSnapshotIntoAutoPayload(runItem);
    if (merged) {
      refreshAutoResultFromPayload(state.lastAutoRunPayload);
      renderAutoOutput(state.lastAutoRunPayload);
      renderReviewPanel(state.lastAutoRunPayload);
      renderAuditTimeline(state.lastAutoRunPayload);
    }
    return merged;
  }

  function defaultElementReviewSection(item) {
    const summary = item?.page_surface_summary && typeof item.page_surface_summary === "object" ? item.page_surface_summary : {};
    const items = Array.isArray(summary.low_confidence_items) ? summary.low_confidence_items : [];
    return {
      review_type: "element",
      status: items.length ? "pending" : "not_required",
      required: items.length > 0,
      candidate_count: items.length,
      items,
    };
  }

  function defaultTestPointReviewSection(item) {
    const plan = item?.test_points && typeof item.test_points === "object" ? item.test_points : {};
    const points = Array.isArray(plan.points) ? plan.points : [];
    const items = points
      .filter((point) => {
        const confidence = Number(point?.confidence || 0);
        const requiresReview = Boolean(point?.requires_review);
        const suggestion = String(point?.suggestion || "").trim().toLowerCase();
        return requiresReview || confidence < 0.75 || suggestion === "review" || suggestion === "skip";
      })
      .map((point) => ({
        key: point?.key || "-",
        label: point?.description || point?.key || "测试点",
        action: point?.action || "",
        target: point?.target || "",
        description: point?.description || "",
        confidence: point?.confidence || 0,
        warnings: Array.isArray(point?.warnings) ? point.warnings.filter(Boolean) : [],
        suggestion: point?.suggestion || (Number(point?.confidence || 0) < 0.6 ? "skip" : "review"),
        review_reason: point?.review_reason || "",
      }));
    return {
      review_type: "test_point",
      status: items.length ? "pending" : "not_required",
      required: items.length > 0,
      candidate_count: items.length,
      items,
    };
  }

  function defaultRiskReviewSection(item) {
    const riskReport = item?.risk_report && typeof item.risk_report === "object" ? item.risk_report : {};
    const requiresReview = Boolean(riskReport?.requires_review);
    const evidence = Array.isArray(riskReport?.evidence) ? riskReport.evidence.filter(Boolean) : [];
    const items = requiresReview
      ? [
          {
            key: "risk_decision",
            label: "风险决策确认",
            confidence: riskReport?.confidence || 0,
            description: riskReport?.recommendation || "",
            gate_decision: riskReport?.gate_decision || "",
            risk_level: riskReport?.risk_level || "",
            risk_score: riskReport?.risk_score || 0,
            warnings: evidence,
          },
        ]
      : [];
    return {
      review_type: "risk",
      status: items.length ? "pending" : "not_required",
      required: items.length > 0,
      candidate_count: items.length,
      items,
    };
  }

  function reviewSectionForItem(item, reviewType) {
    const reviewState = item?.review_state && typeof item.review_state === "object" ? item.review_state : {};
    const section = reviewState?.[reviewType];
    if (section && typeof section === "object") return section;
    if (reviewType === "element") return defaultElementReviewSection(item);
    if (reviewType === "test_point") return defaultTestPointReviewSection(item);
    return defaultRiskReviewSection(item);
  }

  function buildAutoPayloadFromRun(runItem) {
    const item = runItem && typeof runItem === "object" ? runItem : {};
    const normalizedItem = {
      run_id: item.run_id || "",
      project: item.project || state.project,
      page: item.page || "",
      case_id: item.case_id || "",
      status: item.status || "",
      page_url: item.page_url || "",
      page_surface_summary: item.page_surface_summary && typeof item.page_surface_summary === "object" ? item.page_surface_summary : {},
      page_object_summary: item.page_object_summary && typeof item.page_object_summary === "object" ? item.page_object_summary : {},
      test_points: item.test_points && typeof item.test_points === "object" ? item.test_points : {},
      review_state: item.review_state && typeof item.review_state === "object" ? item.review_state : {},
      review_audit_summary: item.review_audit_summary && typeof item.review_audit_summary === "object" ? item.review_audit_summary : {},
      review_audit_timeline: Array.isArray(item.review_audit_timeline) ? item.review_audit_timeline : [],
      risk_report: item.risk_report && typeof item.risk_report === "object" ? item.risk_report : {},
      execution_gate: item.execution_gate && typeof item.execution_gate === "object" ? item.execution_gate : {},
      coverage: item.coverage && typeof item.coverage === "object" ? item.coverage : {},
      page_object: item.page_object && typeof item.page_object === "object" ? item.page_object : {},
    };
    return {
      summary: {
        project: normalizedItem.project || "default",
      },
      items: [normalizedItem],
      allure: {},
    };
  }

  async function loadRunContext(runId) {
    const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`);
    if (!resp.ok) {
      throw new Error("加载运行记录失败");
    }
    const payload = await resp.json().catch(() => ({}));
    const runItem = payload?.item || {};
    state.project = runItem.project || state.project || "default";
    if (els.projectSelect) {
      els.projectSelect.value = state.project;
    }
    if (els.pageInput && !els.pageInput.value && runItem.page) {
      els.pageInput.value = runItem.page;
    }
    state.lastAutoRunPayload = buildAutoPayloadFromRun(runItem);
    refreshAutoResultFromPayload(state.lastAutoRunPayload);
    renderAutoOutput(state.lastAutoRunPayload);
    renderReviewPanel(state.lastAutoRunPayload);
    renderAuditTimeline(state.lastAutoRunPayload);
    setWorkbenchLink(runId, runItem.case_id || "", state.project);
    setReviewSummary(`已定位运行 ${runId} 的确认上下文。`);
    els.reviewPanel?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function persistReviewDecision(actionToken, button) {
    const action = state.reviewActions[actionToken];
    if (!action) return;
    if (!isAuthenticatedForAudit()) {
      setReviewSummary("确认动作需要登录后才能落真实审计记录，正在跳转登录页。");
      window.location.href = loginRedirectTarget();
      return;
    }
    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = "确认中...";
    try {
      const resp = await authFetch("/api/workbench/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(action.payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        if (resp.status === 401) {
          if (window.platformAuth && typeof window.platformAuth.clearToken === "function") {
            window.platformAuth.clearToken();
          }
          setReviewSummary("当前登录状态已失效或未登录，正在跳转登录页后再继续确认。");
          window.location.href = loginRedirectTarget();
          return;
        }
        throw new Error(data?.detail || resp.statusText || "确认失败");
      }
      let refreshed = false;
      if (state.lastAutoRunPayload && action.payload.run_id) {
        try {
          refreshed = await refreshAutoRunState(action.payload.run_id);
        } catch (refreshError) {
          console.error(refreshError);
        }
      }
      if (!refreshed) {
        const card = button.closest(".wb-review-card");
        if (card) {
          card.dataset.reviewStatus = action.payload.status;
          const badge = card.querySelector("[data-review-status]");
          if (badge) {
            badge.className = reviewStatusClass(action.payload.status);
            badge.textContent = reviewStatusLabel(action.payload.status);
          }
        }
        button.textContent = "已确认";
        setReviewSummary("确认已保存，运行状态刷新稍后同步。");
      }
    } catch (error) {
      console.error(error);
      button.disabled = false;
      button.textContent = originalText;
      alert(error?.message || "确认失败，请稍后重试");
    }
  }

  async function persistExecutionGateDecision(actionToken, button) {
    const action = state.gateActions[actionToken];
    if (!action) return;
    if (!isAuthenticatedForAudit()) {
      setReviewSummary("门禁人工决策需要登录后才能落真实审计记录，正在跳转登录页。");
      window.location.href = loginRedirectTarget();
      return;
    }
    const note = window.prompt("请输入门禁决策备注（可选）：", "") || "";
    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = "保存中...";
    try {
      const resp = await authFetch(action.endpoint || "/api/workbench/execution-gate/decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...action.payload,
          note,
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        if (resp.status === 401) {
          if (window.platformAuth && typeof window.platformAuth.clearToken === "function") {
            window.platformAuth.clearToken();
          }
          setReviewSummary("当前登录状态已失效或未登录，正在跳转登录页后再继续门禁决策。");
          window.location.href = loginRedirectTarget();
          return;
        }
        throw new Error(formatErrorDetail(data?.detail) || resp.statusText || "门禁决策保存失败");
      }
      let refreshed = false;
      if (state.lastAutoRunPayload && action.payload.run_id) {
        try {
          refreshed = await refreshAutoRunState(action.payload.run_id);
        } catch (refreshError) {
          console.error(refreshError);
        }
      }
      if (!refreshed) {
        button.textContent = action.successLabel || "已保存";
        setReviewSummary(action.successMessage || "门禁人工决策已保存，运行状态刷新稍后同步。");
      }
    } catch (error) {
      console.error(error);
      button.disabled = false;
      button.textContent = originalText;
      alert(error?.message || "门禁决策保存失败，请稍后重试");
    }
  }

  function renderReviewPanel(payload) {
    if (!els.reviewPanel) return;
    state.reviewActions = {};
    state.gateActions = {};
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const reviewBlocks = [];
    let pendingSections = 0;

    items.forEach((item, index) => {
      const page = String(item?.page || `page-${index + 1}`);
      const runId = String(item?.run_id || "");
      const caseId = String(item?.case_id || "");
      const executionGate = item?.execution_gate && typeof item.execution_gate === "object" ? item.execution_gate : {};
      if (executionGate && Object.keys(executionGate).length) {
        const effectiveDecision = String(executionGate.effective_decision || executionGate.decision || "").trim() || "allow";
        const gateWarnings = Array.isArray(executionGate.warnings) ? executionGate.warnings.filter(Boolean) : [];
        const gateBlockers = Array.isArray(executionGate.blockers) ? executionGate.blockers.filter(Boolean) : [];
        const gateEvidence = Array.isArray(executionGate.evidence) ? executionGate.evidence.filter(Boolean) : [];
        const gateMetrics = executionGate.metrics && typeof executionGate.metrics === "object" ? executionGate.metrics : {};
        const gateConfigSnapshot = executionGate.config_snapshot && typeof executionGate.config_snapshot === "object" ? executionGate.config_snapshot : {};
        const approvalStatus = String(executionGate.approval_status || executionGate.manual_decision?.approval_status || "approved").trim().toLowerCase() || "approved";
        const recordStatus = String(executionGate.record_status || executionGate.manual_decision?.record_status || "active").trim().toLowerCase() || "active";
        const manualDecision = executionGate.manual_decision && typeof executionGate.manual_decision === "object" ? executionGate.manual_decision : {};
        const hasManualDecision = Boolean(Object.keys(manualDecision).length);
        const authRequired = !isAuthenticatedForAudit();
        const nextAction = gateNextAction(effectiveDecision);
        const canApprove = hasManualDecision && approvalStatus === "pending_second_approval" && canApproveExecutionGateDecision();
        const canRevoke = hasManualDecision && recordStatus !== "revoked" && canRevokeExecutionGateDecision(manualDecision.decided_by || executionGate.decided_by || "");
        const allowToken = `gate:${runId}:${page}:allow`;
        const blockToken = `gate:${runId}:${page}:block`;
        const approveToken = `gate:${runId}:${page}:approve`;
        const revokeToken = `gate:${runId}:${page}:revoke`;
        state.gateActions[allowToken] = {
          endpoint: "/api/workbench/execution-gate/decisions",
          successLabel: "已放行",
          successMessage: "执行门禁人工放行已保存，运行状态刷新稍后同步。",
          payload: {
            project: state.project || payload?.summary?.project || "default",
            run_id: runId,
            case_id: caseId,
            page,
            decision: "allow",
          },
        };
        state.gateActions[blockToken] = {
          endpoint: "/api/workbench/execution-gate/decisions",
          successLabel: "已阻断",
          successMessage: "执行门禁人工阻断已保存，运行状态刷新稍后同步。",
          payload: {
            project: state.project || payload?.summary?.project || "default",
            run_id: runId,
            case_id: caseId,
            page,
            decision: "block",
          },
        };
        if (canApprove) {
          state.gateActions[approveToken] = {
            endpoint: "/api/workbench/execution-gate/decisions/approve",
            successLabel: "已审批",
            successMessage: "执行门禁二次审批已保存，运行状态刷新稍后同步。",
            payload: {
              project: state.project || payload?.summary?.project || "default",
              run_id: runId,
              page,
            },
          };
        }
        if (canRevoke) {
          state.gateActions[revokeToken] = {
            endpoint: "/api/workbench/execution-gate/decisions/revoke",
            successLabel: "已撤销",
            successMessage: "执行门禁决策撤销已保存，运行状态刷新稍后同步。",
            payload: {
              project: state.project || payload?.summary?.project || "default",
              run_id: runId,
              page,
            },
          };
        }
        const approvalMeta = hasManualDecision
          ? `<div class="wb-review-hint">审批状态：${escapeHtml(gateApprovalLabel(approvalStatus))} · 记录状态：${escapeHtml(recordStatus === "revoked" ? "已撤销" : "有效")}${manualDecision.second_approver ? ` · 二次审批：${escapeHtml(manualDecision.second_approver)}${manualDecision.second_approver_role ? ` (${escapeHtml(manualDecision.second_approver_role)})` : ""}${manualDecision.second_approved_at ? ` · ${escapeHtml(manualDecision.second_approved_at)}` : ""}` : ""}${manualDecision.revoked_by ? ` · 撤销：${escapeHtml(manualDecision.revoked_by)}${manualDecision.revoked_by_role ? ` (${escapeHtml(manualDecision.revoked_by_role)})` : ""}${manualDecision.revoked_at ? ` · ${escapeHtml(manualDecision.revoked_at)}` : ""}` : ""}</div>`
          : `<div class="wb-review-hint">审批状态：${escapeHtml(gateApprovalLabel(approvalStatus))} · 记录状态：${escapeHtml(recordStatus === "revoked" ? "已撤销" : "有效")}</div>`;
        reviewBlocks.push(`
          <section class="wb-review-card">
            <div class="wb-review-header">
              <h3>${escapeHtml(`执行门禁：${page}`)}</h3>
              <span class="${gateDecisionClass(effectiveDecision)}">${escapeHtml(gateDecisionLabel(effectiveDecision))}</span>
              <span class="${gateApprovalClass(approvalStatus)}">${escapeHtml(gateApprovalLabel(approvalStatus))}</span>
            </div>
            <p>门禁决策由确定性规则生成，用于执行前风险控制（非 AI 主观裁决）。</p>
            <div class="wb-review-hint">系统决策：${escapeHtml(executionGate.decision || "allow")} · 生效决策：${escapeHtml(effectiveDecision)} · 来源：${escapeHtml(executionGate.decision_source || "system")}</div>
            <div class="wb-review-hint">规则边界：未识别依赖达到阈值时直接阻断；低置信度依赖默认进入人工复核。</div>
            <div class="wb-review-hint">规则快照：${escapeHtml(formatGateConfigSnapshot(gateConfigSnapshot))}</div>
            <div class="wb-review-hint">命中指标：${escapeHtml(formatGateMetrics(gateMetrics))}</div>
            <div class="wb-review-hint">动作建议：${escapeHtml(nextAction)}</div>
            ${approvalMeta}
            ${gateBlockers.length ? `<div class="wb-review-warning">阻断原因：${escapeHtml(gateBlockers.join(" "))}</div>` : ""}
            ${gateWarnings.length ? `<div class="wb-review-hint">告警原因：${escapeHtml(gateWarnings.join(" "))}</div>` : ""}
            ${gateEvidence.length ? `<div class="wb-review-hint">门禁依据：${escapeHtml(gateEvidence.join(" "))}</div>` : ""}
            ${hasManualDecision ? `<div class="wb-review-hint">人工决策：${escapeHtml(manualDecision.decision || "-")} · ${escapeHtml(manualDecision.decided_by || "-")} · ${escapeHtml(manualDecision.updated_at || "-")} ${manualDecision.note ? `· 备注：${escapeHtml(manualDecision.note)}` : ""}</div>` : ""}
            <div class="wb-review-actions">
              <button type="button" class="btn" data-gate-action="decide" data-gate-token="${escapeHtml(allowToken)}" ${!runId ? "disabled" : ""}>${authRequired ? "登录后放行" : "人工放行"}</button>
              <button type="button" class="btn btn-danger" data-gate-action="decide" data-gate-token="${escapeHtml(blockToken)}" ${!runId ? "disabled" : ""}>${authRequired ? "登录后阻断" : "人工阻断"}</button>
              ${canApprove ? `<button type="button" class="btn" data-gate-action="approve" data-gate-token="${escapeHtml(approveToken)}">${authRequired ? "登录后审批" : "二次审批通过"}</button>` : ""}
              ${canRevoke ? `<button type="button" class="btn" data-gate-action="revoke" data-gate-token="${escapeHtml(revokeToken)}">${authRequired ? "登录后撤销" : "撤销决策"}</button>` : ""}
            </div>
          </section>
        `);
      }
      ["element", "test_point", "risk"].forEach((reviewType) => {
        const section = reviewSectionForItem(item, reviewType);
        const sectionItems = Array.isArray(section?.items) ? section.items : [];
        const required = Boolean(section?.required) || sectionItems.length > 0;
        if (!required) return;
        if (String(section?.status || "").trim().toLowerCase() === "pending") {
          pendingSections += 1;
        }
        const itemCards = sectionItems
          .map((entry, entryIndex) => {
            const warnings = Array.isArray(entry?.warnings) ? entry.warnings.filter(Boolean) : [];
            const warningHtml = warnings.length
              ? `<div class="wb-review-warning">${escapeHtml(warnings.join(" "))}</div>`
              : "";
            const locatorMeta = reviewType === "element"
              ? `<span>locator=${escapeHtml(entry?.locator_type || "-")}</span><span>${escapeHtml(entry?.locator_value || "-")}</span>`
              : (reviewType === "test_point"
                ? `<span>action=${escapeHtml(entry?.action || "-")}</span><span>target=${escapeHtml(entry?.target || "-")}</span>`
                : `<span>gate=${escapeHtml(entry?.gate_decision || "-")}</span><span>risk=${escapeHtml(entry?.risk_level || "-")}</span>`);
            const suggestionHtml = reviewType === "test_point"
              ? `<div class="wb-review-hint">建议：${escapeHtml(String(entry?.suggestion || "review").toUpperCase())}${entry?.review_reason ? ` · ${escapeHtml(entry.review_reason)}` : ""}</div>`
              : "";
            const dependencyReview = reviewType === "test_point" && entry?.dependency_review && typeof entry.dependency_review === "object"
              ? entry.dependency_review
              : {};
            const dependencyEvidence = reviewType === "test_point" && Array.isArray(dependencyReview.evidence)
              ? dependencyReview.evidence.filter(Boolean)
              : [];
            const dependencyElements = reviewType === "test_point" && Array.isArray(entry?.dependent_elements)
              ? entry.dependent_elements.filter(Boolean)
              : [];
            const dependencyHtml = reviewType === "test_point" && (dependencyElements.length || dependencyEvidence.length)
              ? `<div class="wb-review-hint">依赖元素：${escapeHtml(dependencyElements.join(", ") || "-")}${dependencyEvidence.length ? ` · 依据：${escapeHtml(dependencyEvidence.join(" "))}` : ""}</div>`
              : "";
            const riskHtml = reviewType === "risk"
              ? `<div class="wb-review-hint">风险等级：${escapeHtml(entry?.risk_level || "-")} · 风险分：${escapeHtml(entry?.risk_score || 0)} · 门禁：${escapeHtml(entry?.gate_decision || "-")}</div>`
              : "";
            return `
              <div class="wb-review-item">
                <strong>${entryIndex + 1}. ${escapeHtml(entry?.label || entry?.key || "-")}</strong>
                <div class="wb-review-meta">
                  <span class="${confidenceClass(entry?.confidence)}">${confidenceLabel(entry?.confidence)}</span>
                  ${locatorMeta}
                </div>
                ${warningHtml}
                ${suggestionHtml}
                ${dependencyHtml}
                ${riskHtml}
              </div>
            `;
          })
          .join("");
        const actorDisplay = String(section?.actor_display || section?.confirmed_by || "").trim();
        const updatedAt = String(section?.updated_at || "").trim();
        const confirmationMeta = actorDisplay || updatedAt
          ? `<div class="wb-review-hint">确认信息：${escapeHtml(actorDisplay || "anonymous")}${updatedAt ? ` · ${escapeHtml(updatedAt)}` : ""}</div>`
          : "";
        const statusValue = String(section?.status || "pending");
        const authRequired = !isAuthenticatedForAudit() && statusValue !== "confirmed";
        const title = reviewType === "element"
          ? `确认点 1：${page} 页面低置信度元素`
          : (reviewType === "test_point" ? `确认点 2：${page} 待确认测试点` : `确认点 3：${page} 风险决策`);
        const description = reviewType === "element"
          ? "这些元素已被自动识别，但建议在继续扩大测试覆盖前优先确认。"
          : (reviewType === "test_point"
            ? "这些测试点依赖低置信度元素或存在上下文歧义，建议先人工确认。"
            : "这是当前批次的风险结论与门禁建议，建议人工确认后再决定是否放行。");
        const actionToken = `${runId || "no-run"}:${page}:${reviewType}`;
        const actionDisabled = statusValue === "confirmed" || !runId;
        state.reviewActions[actionToken] = {
          payload: {
            project: state.project || payload?.summary?.project || "default",
            run_id: runId,
            case_id: caseId,
            page,
            review_type: reviewType,
            status: "confirmed",
            items: sectionItems.map((entry) => ({
              key: entry?.key || "",
              label: entry?.label || "",
              confidence: entry?.confidence || 0,
              warnings: Array.isArray(entry?.warnings) ? entry.warnings : [],
              locator_type: entry?.locator_type || "",
              locator_value: entry?.locator_value || "",
              action: entry?.action || "",
              target: entry?.target || "",
              description: entry?.description || "",
              suggestion: entry?.suggestion || "",
              review_reason: entry?.review_reason || "",
              dependent_elements: Array.isArray(entry?.dependent_elements) ? entry.dependent_elements : [],
              dependency_review: entry?.dependency_review && typeof entry.dependency_review === "object" ? entry.dependency_review : {},
              gate_decision: entry?.gate_decision || "",
              risk_level: entry?.risk_level || "",
              risk_score: entry?.risk_score || 0,
            })),
          },
        };
        const highlight = state.focusReviewType && state.focusReviewType === reviewType && (!state.focusPage || state.focusPage === page.toLowerCase());
        reviewBlocks.push(`
          <section class="wb-review-card ${highlight ? "wb-audit-line-active" : ""}" data-review-status="${escapeHtml(statusValue)}" data-auth-required="${authRequired ? "true" : "false"}">
            <div class="wb-review-header">
              <h3>${escapeHtml(title)}</h3>
              <span data-review-status class="${reviewStatusClass(statusValue)}">${reviewStatusLabel(statusValue)}</span>
            </div>
            <p>${escapeHtml(description)}</p>
            ${itemCards}
            ${confirmationMeta}
            <div class="wb-review-actions">
              <button type="button" class="btn" data-review-action="ack" data-review-token="${escapeHtml(actionToken)}" ${actionDisabled ? "disabled" : ""}>${statusValue === "confirmed" ? "已确认" : (runId ? (authRequired ? "登录后确认" : "标记已确认") : "无执行上下文")}</button>
            </div>
          </section>
        `);
      });
    });

    if (!reviewBlocks.length) {
      els.reviewPanel.className = "wb-review-panel wb-review-empty";
      els.reviewPanel.innerHTML = "当前批次没有低置信度元素、待确认测试点或风险决策，系统已自动跳过确认点。";
      setReviewSummary("确认点：未触发，当前页面分析、测试点与风险评估置信度较高。");
      return;
    }

    els.reviewPanel.className = "wb-review-panel";
    els.reviewPanel.innerHTML = reviewBlocks.join("");
    const totalLowConfidence = items.reduce((count, item) => count + Number(reviewSectionForItem(item, "element")?.candidate_count || 0), 0);
    const totalReviewPoints = items.reduce((count, item) => count + Number(reviewSectionForItem(item, "test_point")?.candidate_count || 0), 0);
    const totalRiskReviews = items.reduce((count, item) => count + Number(reviewSectionForItem(item, "risk")?.candidate_count || 0), 0);
    const gateBlocked = items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "block").length;
    const gateManualReview = items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "manual_review").length;
    const gateAllow = items.filter((item) => String(item?.execution_gate?.effective_decision || item?.execution_gate?.decision || "").toLowerCase() === "allow").length;
    const gateRuleNote = state.executionGateConfig
      ? `当前门禁阈值：缺失必需元素 >= ${state.executionGateConfig.block_missing_required_threshold} 时阻断，未识别依赖测试点 >= ${state.executionGateConfig.block_missing_dependency_points_threshold} 时阻断。`
      : "";
    const actionHint = gateBlocked > 0
      ? "建议先处理阻断项。"
      : (gateManualReview > 0 ? "建议先完成确认再决定是否放行。" : (gateAllow > 0 ? "当前可继续推进。" : ""));
    setReviewSummary(`确认点：低置信度元素 ${totalLowConfidence} 个，待确认测试点 ${totalReviewPoints} 个，风险决策 ${totalRiskReviews} 个，待处理确认分组 ${pendingSections} 个。门禁阻断 ${gateBlocked} 个，门禁复核 ${gateManualReview} 个。${actionHint}${gateRuleNote}`);
    if (!isAuthenticatedForAudit() && pendingSections > 0) {
      setReviewSummary(`确认点：低置信度元素 ${totalLowConfidence} 个，待确认测试点 ${totalReviewPoints} 个，风险决策 ${totalRiskReviews} 个，待处理确认分组 ${pendingSections} 个。门禁阻断 ${gateBlocked} 个，门禁复核 ${gateManualReview} 个。${actionHint}未登录时可查看，但确认前会先跳转登录。${gateRuleNote}`);
    }

    els.reviewPanel.querySelectorAll("[data-review-action='ack']").forEach((button) => {
      button.addEventListener("click", () => persistReviewDecision(button.dataset.reviewToken, button));
    });
    els.reviewPanel.querySelectorAll("[data-gate-action]").forEach((button) => {
      button.addEventListener("click", () => persistExecutionGateDecision(button.dataset.gateToken, button));
    });
  }

  async function handleGenerate(event) {
    event.preventDefault();
    let payload = {};
    try {
      payload = await buildGeneratePayload();
    } catch (error) {
      alert(error?.message || "多输入源 JSON 解析失败");
      return;
    }
    setResult("生成中，请稍候...");
    els.yamlPreview.textContent = "";
    try {
      const resp = await authFetch("/api/workbench/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        const detail = error?.detail;
        setResult(`生成失败：${formatErrorDetail(detail) || resp.statusText}`);
        if (detail && typeof detail === "object" && detail.quality_gate) {
          els.yamlPreview.textContent = JSON.stringify({ quality_gate: detail.quality_gate }, null, 2);
        }
        return;
      }
      const data = await resp.json();
      const item = data.item || {};
      const fallbackUsed = Boolean(item.orchestrator_design_fallback_used || item.orchestrator_fallback_reason);
      const fallbackNote = fallbackUsed ? "（已走设计兜底）" : "";
      const qualityGate = item.quality_gate && typeof item.quality_gate === "object" ? item.quality_gate : null;
      const gateNote = qualityGate ? `（${formatQualityGateSummary(qualityGate)}）` : "";
      setResult(`生成成功：${item.case_id || "-"} ${fallbackNote}${gateNote}。可直接进入预览，或返回工作台定位该用例。`);
      els.yamlPreview.textContent = item.yaml_content || "";
      setPreviewLink(item.case_id, payload.project);
      setWorkbenchLink("", item.case_id || "", payload.project);
    } catch (error) {
      console.error(error);
      setResult("生成失败，请检查服务状态。");
    }
  }

  async function handleAutoRun() {
    const pageUrls = normalizeUrls(els.pageUrlsInput.value);
    if (!pageUrls.length) {
      alert("请至少输入一个页面 URL。");
      return;
    }

    syncPageFromUrls();
    const payload = {
      project: els.projectSelect.value || "default",
      page_urls: pageUrls,
      source: els.sourceSelect?.value || "manual",
      wait_seconds: 240,
    };
    try {
      Object.assign(payload, await collectMultiSourcePayload());
    } catch (error) {
      alert(error?.message || "多输入源 JSON 解析失败");
      return;
    }
    payload.requirement = deriveRequirement({
      requirement: els.requirementInput.value.trim(),
      page: els.pageInput?.value.trim(),
      pageUrls,
      hasMultiSource: hasMultiSourcePayload(payload),
    });

    els.autoRunBtn.disabled = true;
    setAutoResult("自动链路执行中：测试点生成 -> 页面对象补齐 -> YAML 生成 -> 执行 -> 报告刷新");
    els.autoOutput.textContent = "";
    if (els.reviewPanel) {
      els.reviewPanel.className = "wb-review-panel wb-review-empty";
      els.reviewPanel.innerHTML = "正在分析页面元素，确认点将在执行完成后展示。";
    }
    if (els.auditTimeline) {
      els.auditTimeline.className = "wb-audit-panel wb-review-empty";
      els.auditTimeline.innerHTML = "正在等待审计事件产生。";
    }
    setReviewSummary("确认点分析中...");
    try {
      const resp = await authFetch("/api/workbench/auto-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setAutoResult(`自动链路失败：${data.detail || resp.statusText}`);
        els.autoOutput.textContent = JSON.stringify(data, null, 2);
        return;
      }
      state.project = payload.project || "default";
      state.lastAutoRunPayload = data;
      refreshAutoResultFromPayload(state.lastAutoRunPayload);
      renderAutoOutput(state.lastAutoRunPayload);
      renderReviewPanel(state.lastAutoRunPayload);
      renderAuditTimeline(state.lastAutoRunPayload);
      const firstCase = (data.items || []).find((item) => item.case_id);
      if (firstCase) {
        setPreviewLink(firstCase.case_id, payload.project);
        setWorkbenchLink(firstCase.run_id || "", firstCase.case_id, payload.project);
      }
      if (!firstCase && Array.isArray(data.items) && data.items.length) {
        const firstRun = data.items.find((item) => item?.run_id);
        if (firstRun) {
          setWorkbenchLink(firstRun.run_id, firstRun.case_id || "", payload.project);
        }
      }
    } catch (error) {
      console.error(error);
      setAutoResult("自动链路失败，请检查服务状态。");
      if (els.reviewPanel) {
        els.reviewPanel.className = "wb-review-panel wb-review-empty";
        els.reviewPanel.innerHTML = "确认点未生成，请先排查自动链路失败原因。";
      }
      if (els.auditTimeline) {
        els.auditTimeline.className = "wb-audit-panel wb-review-empty";
        els.auditTimeline.innerHTML = "审计时间线未生成，请先排查自动链路失败原因。";
      }
      setReviewSummary("确认点生成失败。");
    } finally {
      els.autoRunBtn.disabled = false;
    }
  }

  function bindEvents() {
    els.projectSelect.addEventListener("change", () => {
      state.project = els.projectSelect.value || "default";
      setPreviewLink("", state.project);
    });
    els.form.addEventListener("submit", handleGenerate);
    if (els.previewPointsBtn) {
      els.previewPointsBtn.addEventListener("click", handlePreviewPoints);
    }
    if (els.autoRunBtn) {
      els.autoRunBtn.addEventListener("click", handleAutoRun);
    }
    if (els.pageUrlsInput) {
      els.pageUrlsInput.addEventListener("input", () => {
        syncPageFromUrls();
      });
    }
    if (els.loadReturnApplyBtn) {
      els.loadReturnApplyBtn.addEventListener("click", () => {
        applyGenerateSample("returnapply");
      });
    }
  }

  async function bootstrap() {
    updateAuthNotice();
    bindEvents();
    await loadProjects();
    await loadExecutionGateConfig();
    syncPageFromUrls();
    setPreviewLink("", state.project);
    setWorkbenchLink("", "", state.project);
    setReviewSummary("确认点尚未触发。");
    if (state.sampleKey) {
      applyGenerateSample(state.sampleKey);
    }
    state.lastAutoRunPayload = null;
    renderAuditTimeline(null);
    if (state.deepLinkRunId) {
      await loadRunContext(state.deepLinkRunId);
    }
    window.addEventListener("platform-auth-changed", () => {
      updateAuthNotice();
      if (state.lastAutoRunPayload) {
        renderReviewPanel(state.lastAutoRunPayload);
        renderAuditTimeline(state.lastAutoRunPayload);
      }
    });
  }

  bootstrap().catch((error) => {
    console.error(error);
    setResult("加载失败，请检查后端服务。");
  });
})();
