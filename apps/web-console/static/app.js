const templateListEl = document.getElementById("template-list");
const templateDetailEl = document.getElementById("template-detail");
const resultEl = document.getElementById("result");
const resultSummaryEl = document.getElementById("result-summary");
const statusEl = document.getElementById("status");
const latestReportSummaryEl = document.getElementById("latest-report-summary");
const latestReportRawEl = document.getElementById("latest-report-raw");
const latestReportAnalysisEl = document.getElementById("latest-report-analysis");
const latestReportHealingEl = document.getElementById("latest-report-healing");
const latestReportHealingExecutionEl = document.getElementById("latest-report-healing-execution");
const latestReportManagementEl = document.getElementById("latest-report-management");
const environmentFailureCasesEl = document.getElementById("environment-failure-cases");
const actionableHealingCasesEl = document.getElementById("actionable-healing-cases");
const stepListEl = document.getElementById("step-list");
const elementListEl = document.getElementById("element-list");
const favoriteListEl = document.getElementById("favorite-list");
const recentListEl = document.getElementById("recent-list");
const formEl = document.getElementById("scaffold-form");
const templateInputEl = document.getElementById("template-input");
const titleInputEl = document.getElementById("title-input");
const requirementInputEl = document.getElementById("requirement-input");
const autofillHintEl = document.getElementById("autofill-hint");
const requestPreviewEl = document.getElementById("request-preview");
const requestPreviewSummaryEl = document.getElementById("request-preview-summary");
const requestPreviewChecksEl = document.getElementById("request-preview-checks");
const requestPreviewBodyEl = document.getElementById("request-preview-body");
const requestPreviewDiffEl = document.getElementById("request-preview-diff");
const confirmPreviewButtonEl = document.getElementById("confirm-preview");
const cancelPreviewButtonEl = document.getElementById("cancel-preview");
const reloadButtonEl = document.getElementById("reload-templates");
const clearHistoryButtonEl = document.getElementById("clear-history");
const exportHistoryButtonEl = document.getElementById("export-history");
const reloadReportSummaryButtonEl = document.getElementById("reload-report-summary");
const STORAGE_KEY = "ai-test-platform.console.scaffold-form";
const HISTORY_KEY = "ai-test-platform.console.scaffold-history";
const LAST_REQUEST_KEY = "ai-test-platform.console.last-request";
const HISTORY_LIMIT = 6;

let templates = [];
let activeTemplate = "";
let autofillState = {
  title: "",
  requirement: "",
};
let pendingRequest = null;

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();

  if (!response.ok) {
    const message = payload?.error?.message || `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function renderTemplates(items) {
  templateListEl.innerHTML = "";

  if (!items.length) {
    templateListEl.textContent = "No templates available. 当前没有可用模板。";
    return;
  }

  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "template-card";
    if (item.name === activeTemplate) {
      button.classList.add("is-active");
    }

    button.innerHTML = `<strong>${item.name}</strong><span>${item.summary || "No summary"}</span>`;
    button.addEventListener("click", () => selectTemplate(item.name));
    templateListEl.appendChild(button);
  }
}

async function loadTemplates() {
  statusEl.textContent = "Loading templates... 正在加载模板。";

  try {
    const payload = await fetchJson("/assets/scaffold/templates");
    templates = payload.templates || [];
    renderTemplates(templates);
    statusEl.textContent = `Loaded ${templates.length} template(s).`;

    if (templates.length && !activeTemplate) {
      await selectTemplate(templates[0].name);
    }
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

function renderLatestReportSummary(payload) {
  const report = payload?.report || {};
  const summaryPath = payload?.report_summary_path || "";
  const reportJsonPath = payload?.report_json_path || "";
  const reportMarkdownPath = payload?.report_markdown_path || "";
  const reportJson = JSON.stringify(report, null, 2);
  const suggestionFiles = Array.isArray(report?.evidence?.suggestion_files) ? report.evidence.suggestion_files : [];
  const primarySuggestionPath = suggestionFiles[0] || "";
  latestReportSummaryEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Case ID</strong>
        <span>${report.case_id || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Status</strong>
        <span>${report.status || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Source</strong>
        <span>${report.source || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Mode</strong>
        <span>${report.request_context?.mode || "-"}</span>
      </div>
    </div>
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Summary Path</strong>
        <span>${summaryPath || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Report JSON</strong>
        <span>${reportJsonPath || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Report Markdown</strong>
        <span>${reportMarkdownPath || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Finished At</strong>
        <span>${report.finished_at || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Suggestion Files</strong>
        <span>${suggestionFiles.length}</span>
      </div>
      <div class="summary-item">
        <strong>Primary Suggestion</strong>
        <span>${primarySuggestionPath || "-"}</span>
      </div>
    </div>
    <div class="recent-actions">
      <button type="button" class="small-ghost" data-copy-path="${summaryPath || ""}">Copy Summary Path</button>
      <button type="button" class="small-ghost" data-copy-path="${reportJsonPath || ""}">Copy Report JSON Path</button>
      <button type="button" class="small-ghost" data-copy-path="${reportMarkdownPath || ""}">Copy Markdown Path</button>
      <button type="button" class="small-ghost" data-copy-path="${primarySuggestionPath || ""}">Copy Suggestion Path</button>
      <button type="button" class="small-ghost" data-copy-report-text='${reportJson.replaceAll("'", "&#39;")}'>Copy Full Report JSON</button>
    </div>
  `;
  latestReportRawEl.textContent = JSON.stringify(payload, null, 2);
  renderLatestReportAnalysis(report);
  renderLatestReportHealing(report);
  renderLatestReportHealingExecution(report);
  renderLatestReportManagement(payload?.report_summary_preview || {});
}

function renderLatestReportAnalysis(report) {
  const analysis = report?.failure_analysis || {};
  const analysisJson = JSON.stringify(analysis, null, 2);
  latestReportAnalysisEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Failure Reason</strong>
        <span>${report?.failure_reason || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Category</strong>
        <span>${analysis?.failure_category || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Risk Level</strong>
        <span>${analysis?.risk_level || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Confidence</strong>
        <span>${analysis?.confidence || "-"}</span>
      </div>
    </div>
    <div class="summary-item">
      <strong>Summary</strong>
      <span>${analysis?.summary || "-"}</span>
    </div>
    <div class="summary-item">
      <strong>Likely Cause</strong>
      <span>${analysis?.likely_cause || "-"}</span>
    </div>
    <div class="summary-item">
      <strong>Recommended Action</strong>
      <span>${analysis?.recommended_action || "-"}</span>
    </div>
    <div class="recent-actions">
      <button type="button" class="small-ghost" data-copy-analysis-text='${analysisJson.replaceAll("'", "&#39;")}'>Copy Analysis JSON</button>
    </div>
  `;
}

function renderLatestReportHealing(report) {
  const previewAdvice = report?.self_healing_suggestion_preview || {};
  const fallbackAdvice = report?.self_healing_advice || {};
  const usePreview = Object.keys(previewAdvice).length > 0;
  const advice = usePreview ? previewAdvice : fallbackAdvice;
  const candidates = Array.isArray(advice?.fix_candidates)
    ? advice.fix_candidates
    : Array.isArray(fallbackAdvice?.suggested_changes)
      ? fallbackAdvice.suggested_changes
      : [];
  const suggestionFiles = Array.isArray(report?.evidence?.suggestion_files) ? report.evidence.suggestion_files : [];
  const candidateText = candidates.length ? candidates.join(" | ") : "-";
  const suggestionPathText = suggestionFiles.length ? suggestionFiles.join(" | ") : "-";
  const adviceJson = JSON.stringify(advice, null, 2);
  latestReportHealingEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Advice Source</strong>
        <span>${usePreview ? "suggestion.json" : "report advice"}</span>
      </div>
      <div class="summary-item">
        <strong>Advice Type</strong>
        <span>${advice?.advice_type || advice?.suggestion_type || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Confidence</strong>
        <span>${advice?.confidence || "-"}</span>
      </div>
    </div>
    <div class="summary-item">
      <strong>Summary</strong>
      <span>${advice?.summary || fallbackAdvice?.summary || "-"}</span>
    </div>
    <div class="summary-item">
      <strong>Suggestion</strong>
      <span>${advice?.suggestion || fallbackAdvice?.rationale || fallbackAdvice?.recommended_action || "-"}</span>
    </div>
    <div class="summary-item">
      <strong>Suggestion Target</strong>
      <span>${advice?.target || "-"}</span>
    </div>
    <div class="summary-item">
      <strong>Fix Candidates</strong>
      <span>${candidateText}</span>
    </div>
    <div class="summary-item">
      <strong>Suggestion Files</strong>
      <span>${suggestionPathText}</span>
    </div>
    <div class="recent-actions">
      <button type="button" class="small-ghost" data-copy-text='${adviceJson.replaceAll("'", "&#39;")}'>Copy Advice JSON</button>
    </div>
  `;
}

function renderLatestReportHealingExecution(report) {
  const execution = report?.self_healing_execution_preview || {};
  const resultFiles = Array.isArray(report?.evidence?.self_healing_result_files) ? report.evidence.self_healing_result_files : [];
  const primaryResultPath = resultFiles[0] || execution?.result_path || "";
  latestReportHealingExecutionEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Enabled</strong>
        <span>${report?.self_healing_enabled ?? "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Attempted</strong>
        <span>${report?.self_healing_attempted ?? "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Status</strong>
        <span>${execution?.status || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Attempts Used</strong>
        <span>${execution?.attempts_used ?? "-"}</span>
      </div>
    </div>
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Healed</strong>
        <span>${execution?.healed ?? "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Rolled Back</strong>
        <span>${execution?.rolled_back ?? "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Confidence</strong>
        <span>${execution?.confidence ?? "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Result Files</strong>
        <span>${resultFiles.length}</span>
      </div>
    </div>
    <div class="summary-item">
      <strong>Reason</strong>
      <span>${execution?.reason || "-"}</span>
    </div>
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Plan Path</strong>
        <span>${execution?.plan_path || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Result Path</strong>
        <span>${primaryResultPath || "-"}</span>
      </div>
    </div>
    <div class="recent-actions">
      <button type="button" class="small-ghost" data-copy-path="${primaryResultPath || ""}">Copy Healing Result Path</button>
      <button type="button" class="small-ghost" data-copy-text='${JSON.stringify(execution, null, 2).replaceAll("'", "&#39;")}'>Copy Healing Execution JSON</button>
    </div>
  `;
}

function renderLatestReportManagement(summary) {
  latestReportManagementEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Total Failed Cases</strong>
        <span>${summary?.total_failed_cases ?? 0}</span>
      </div>
      <div class="summary-item">
        <strong>Environment Failures</strong>
        <span>${summary?.environment_failures ?? 0}</span>
      </div>
      <div class="summary-item">
        <strong>Business Failures</strong>
        <span>${summary?.business_failures ?? 0}</span>
      </div>
      <div class="summary-item">
        <strong>High Risk Failures</strong>
        <span>${summary?.high_risk_failures ?? 0}</span>
      </div>
      <div class="summary-item">
        <strong>Actionable Self-Healing</strong>
        <span>${summary?.actionable_self_healing_cases ?? 0}</span>
      </div>
    </div>
  `;
  renderEnvironmentFailureCases(summary?.environment_failure_cases || []);
  renderActionableHealingCases(summary?.actionable_self_healing_case_details || []);
}

function renderEnvironmentFailureCases(cases) {
  if (!Array.isArray(cases) || !cases.length) {
    environmentFailureCasesEl.textContent = "No environment failure cases. 当前没有环境失败用例。";
    return;
  }
  environmentFailureCasesEl.innerHTML = cases
    .map((item) => `<div class="summary-item"><strong>Case</strong><span>${item}</span></div>`)
    .join("");
}

function renderActionableHealingCases(cases) {
  if (!Array.isArray(cases) || !cases.length) {
    actionableHealingCasesEl.textContent = "No actionable self-healing cases. 当前没有可修复建议用例。";
    return;
  }
  actionableHealingCasesEl.innerHTML = cases
    .map(
      (item) => `
        <div class="summary-item">
          <strong>${item?.case_id || "-"}</strong>
          <span>${item?.advice_type || "-"} -> ${item?.target || "-"}</span>
        </div>
      `
    )
    .join("");
}

async function loadLatestReportSummary() {
  try {
    const payload = await fetchJson("/reports/latest");
    renderLatestReportSummary(payload);
    statusEl.textContent = `Loaded latest report for ${payload?.report?.case_id || "unknown case"}.`;
  } catch (error) {
    latestReportSummaryEl.textContent = error.message;
    latestReportRawEl.textContent = "Unable to load latest report payload.";
    latestReportAnalysisEl.textContent = "Unable to load latest report analysis.";
    latestReportHealingEl.textContent = "Unable to load self-healing advice.";
    latestReportHealingExecutionEl.textContent = "Unable to load self-healing execution result.";
    latestReportManagementEl.textContent = "Unable to load management summary.";
    environmentFailureCasesEl.textContent = "Unable to load environment failure cases.";
    actionableHealingCasesEl.textContent = "Unable to load actionable self-healing cases.";
  }
}

async function selectTemplate(name) {
  activeTemplate = name;
  templateInputEl.value = name;
  persistFormState();
  renderTemplates(templates);
  templateDetailEl.textContent = "Loading template detail...";

  try {
    const payload = await fetchJson(`/assets/scaffold/templates/${encodeURIComponent(name)}`);
    templateDetailEl.textContent = JSON.stringify(payload.template, null, 2);
    autofillTemplateFields(payload.template);
  } catch (error) {
    templateDetailEl.textContent = error.message;
  }
}

function autofillTemplateFields(template) {
  const recommendedTitle = template.recommended_title || "";
  const recommendedRequirement = template.recommended_requirement || "";
  const changes = [];
  const preserved = [];

  if (!titleInputEl.value.trim() || titleInputEl.value.trim() === autofillState.title) {
    titleInputEl.value = recommendedTitle;
    changes.push("title");
  } else {
    preserved.push("title");
  }

  if (!requirementInputEl.value.trim() || requirementInputEl.value.trim() === autofillState.requirement) {
    requirementInputEl.value = recommendedRequirement;
    changes.push("requirement");
  } else {
    preserved.push("requirement");
  }

  autofillState = {
    title: recommendedTitle,
    requirement: recommendedRequirement,
  };

  persistFormState();
  autofillHintEl.textContent = buildAutofillHint(template.name, changes, preserved);
}

function buildAutofillHint(templateName, changes, preserved) {
  const changeText = changes.length ? `updated ${changes.join(" and ")}` : "did not overwrite recommended fields";
  const preserveText = preserved.length ? ` Preserved manual ${preserved.join(" and ")}.` : "";
  return `Template "${templateName}" ${changeText}.${preserveText}`;
}

function parseExtraElements(text) {
  if (!text.trim()) {
    return undefined;
  }
  return JSON.parse(text);
}

function validatePayload(payload) {
  const issues = [];
  const page = String(payload.page || "").trim();
  const title = String(payload.title || "").trim();
  const requirement = String(payload.requirement || "").trim();

  if (!page) {
    issues.push({ level: "error", message: "page is required." });
  }
  if (!title) {
    issues.push({ level: "error", message: "title is required." });
  }
  if (!requirement) {
    issues.push({ level: "error", message: "requirement is required." });
  }

  if (payload.elements !== undefined) {
    if (!Array.isArray(payload.elements)) {
      issues.push({ level: "error", message: "elements must be a JSON array." });
    } else {
      payload.elements.forEach((element, index) => {
        if (!element || typeof element !== "object" || Array.isArray(element)) {
          issues.push({ level: "error", message: `elements[${index}] must be an object.` });
          return;
        }

        const name = String(element.name || "").trim();
        const locatorType = String(element.locator_type || "").trim();
        const locatorValue = String(element.locator_value || "").trim();
        const smokeRole = String(element.smoke_role || "").trim();

        if (!name) {
          issues.push({ level: "error", message: `elements[${index}].name is required.` });
        }
        if (!locatorType) {
          issues.push({ level: "error", message: `elements[${index}].locator_type is required.` });
        }
        if (!locatorValue) {
          issues.push({ level: "error", message: `elements[${index}].locator_value is required.` });
        }
        if (locatorType === "role" && !String(element.role || "").trim()) {
          issues.push({ level: "error", message: `elements[${index}].role is required when locator_type is role.` });
        }
        if (smokeRole && smokeRole !== "menu" && smokeRole !== "assert") {
          issues.push({ level: "error", message: `elements[${index}].smoke_role must be menu or assert.` });
        }
      });
    }
  }

  if (!issues.length) {
    issues.push({ level: "info", message: "Ready to submit. Local preflight checks passed." });
  }

  return issues;
}

function buildPayloadFromForm() {
  const formData = new FormData(formEl);
  const payload = {
    page: String(formData.get("page") || "").trim(),
    title: String(formData.get("title") || "").trim(),
    requirement: String(formData.get("requirement") || "").trim(),
    description: String(formData.get("description") || "").trim(),
    priority: String(formData.get("priority") || "").trim() || "P1",
  };

  const template = String(formData.get("template") || "").trim();
  if (template) {
    payload.template = template;
  }

  const elements = parseExtraElements(String(formData.get("elements") || ""));
  if (elements) {
    payload.elements = elements;
  }

  return payload;
}

function readFormState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const data = JSON.parse(raw);
    return typeof data === "object" && data ? data : null;
  } catch (_error) {
    return null;
  }
}

function readHistory() {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) {
      return [];
    }
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch (_error) {
    return [];
  }
}

function readLastRequest() {
  try {
    const raw = window.localStorage.getItem(LAST_REQUEST_KEY);
    if (!raw) {
      return null;
    }
    const data = JSON.parse(raw);
    return typeof data === "object" && data ? data : null;
  } catch (_error) {
    return null;
  }
}

function writeLastRequest(payload) {
  window.localStorage.setItem(LAST_REQUEST_KEY, JSON.stringify(payload));
}

function writeHistory(history) {
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function persistFormState() {
  const formData = new FormData(formEl);
  const payload = Object.fromEntries(formData.entries());
  payload.activeTemplate = activeTemplate;
  payload.autofillState = autofillState;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function restoreFormState() {
  const saved = readFormState();
  if (!saved) {
    return;
  }

  for (const [key, value] of Object.entries(saved)) {
    if (key === "activeTemplate" || key === "autofillState") {
      continue;
    }
    const field = formEl.elements.namedItem(key);
    if (field && "value" in field) {
      field.value = typeof value === "string" ? value : "";
    }
  }

  if (saved.autofillState && typeof saved.autofillState === "object") {
    autofillState = {
      title: String(saved.autofillState.title || ""),
      requirement: String(saved.autofillState.requirement || ""),
    };
  }

  if (typeof saved.activeTemplate === "string") {
    activeTemplate = saved.activeTemplate;
  }

  autofillHintEl.textContent = "Restored the last scaffold form draft from this browser.";
}

function persistHistoryEntry(result, payload) {
  const previousEntry = readHistory().find(
    (entry) => entry.testCaseId === (result.test_case?.id || "") && entry.page === (result.page_object?.page || payload.page || ""),
  );
  const nextEntry = {
    createdAt: new Date().toISOString(),
    favorite: Boolean(previousEntry?.favorite),
    alias: previousEntry?.alias || "",
    page: result.page_object?.page || payload.page || "",
    template: payload.template || "",
    testCaseId: result.test_case?.id || "",
    pageObjectPath: result.page_object_path || "",
    testCasePath: result.test_case_path || "",
    title: payload.title || "",
    requirement: payload.requirement || "",
    description: payload.description || "",
    priority: payload.priority || "P1",
    elements: payload.elements || [],
  };

  const history = readHistory().filter(
    (entry) => !(entry.testCaseId === nextEntry.testCaseId && entry.page === nextEntry.page),
  );
  history.unshift(nextEntry);
  history.sort((left, right) => {
    const favoriteDelta = Number(Boolean(right.favorite)) - Number(Boolean(left.favorite));
    if (favoriteDelta !== 0) {
      return favoriteDelta;
    }
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
  });
  writeHistory(history.slice(0, HISTORY_LIMIT));
  renderRecentHistory();
}

function renderRecentHistory() {
  const history = readHistory();
  const favorites = history.filter((entry) => entry.favorite);
  const recent = history.filter((entry) => !entry.favorite);

  renderHistoryList({
    container: favoriteListEl,
    entries: favorites,
    emptyMessage: "No favorite scaffolds yet.",
    offset: 0,
  });

  renderHistoryList({
    container: recentListEl,
    entries: recent,
    emptyMessage: "No scaffold history yet.",
    offset: favorites.length,
  });
}

function renderHistoryList({ container, entries, emptyMessage, offset }) {
  if (!entries.length) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  container.innerHTML = entries
    .map((entry, index) => {
      const historyIndex = offset + index;
      const templateText = entry.template || "manual";
      const favoriteLabel = entry.favorite ? "Favorited" : "Favorite";
      const titleText = entry.alias || entry.testCaseId || "Unnamed scaffold";
      return `
        <article class="recent-card${entry.favorite ? " is-favorite" : ""}">
          <div class="recent-card-header">
            <div>
              <strong>${titleText}</strong>
              <span>page: ${entry.page || "-"} | template: ${templateText}</span>
            </div>
            <span>${new Date(entry.createdAt).toLocaleString()}</span>
          </div>
          <span>page object: ${entry.pageObjectPath || "-"}</span>
          <span>test case: ${entry.testCasePath || "-"}</span>
          <div class="recent-actions">
            <button type="button" class="small-ghost" data-history-index="${historyIndex}">Reuse This</button>
            <button type="button" class="small-ghost" data-rerun-history-index="${historyIndex}">Run Again</button>
            <button type="button" class="small-ghost" data-alias-history-index="${historyIndex}">Alias</button>
            <button type="button" class="favorite-ghost" data-favorite-history-index="${historyIndex}">${favoriteLabel}</button>
            <button type="button" class="small-ghost" data-copy-path="${entry.testCasePath || ""}">Copy Test Path</button>
            <button type="button" class="small-ghost" data-copy-path="${entry.pageObjectPath || ""}">Copy Page Object Path</button>
            <button type="button" class="danger-ghost" data-delete-history-index="${historyIndex}">Delete</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function rerunHistoryEntry(index) {
  const entry = readHistory()[index];
  if (!entry) {
    return;
  }

  setFieldValue("page", entry.page || "");
  setFieldValue("title", entry.title || "");
  setFieldValue("requirement", entry.requirement || "");
  setFieldValue("template", entry.template || "");
  setFieldValue("description", entry.description || "");
  setFieldValue("priority", entry.priority || "P1");
  setFieldValue("elements", entry.elements?.length ? JSON.stringify(entry.elements, null, 2) : "");
  activeTemplate = entry.template || "";
  renderTemplates(templates);
  persistFormState();
  autofillHintEl.textContent = `Prepared re-run for ${entry.alias || entry.testCaseId || entry.page || "history"}.`;
  showRequestPreview(buildPayloadFromForm(), "history");
}

function updateHistoryAlias(index) {
  const history = readHistory();
  const entry = history[index];
  if (!entry) {
    return;
  }

  const alias = window.prompt("Set a local alias for this scaffold", entry.alias || entry.testCaseId || "");
  if (alias === null) {
    return;
  }

  entry.alias = alias.trim();
  writeHistory(history);
  renderRecentHistory();
  statusEl.textContent = entry.alias ? `Saved alias "${entry.alias}".` : "Cleared scaffold alias.";
}

function applyHistoryEntry(index) {
  const entry = readHistory()[index];
  if (!entry) {
    return;
  }

  setFieldValue("page", entry.page || "");
  setFieldValue("title", entry.title || "");
  setFieldValue("requirement", entry.requirement || "");
  setFieldValue("template", entry.template || "");
  setFieldValue("description", entry.description || "");
  setFieldValue("priority", entry.priority || "P1");
  setFieldValue("elements", entry.elements?.length ? JSON.stringify(entry.elements, null, 2) : "");

  activeTemplate = entry.template || "";
  renderTemplates(templates);
  persistFormState();
  autofillHintEl.textContent = `Reused scaffold draft from ${entry.testCaseId || entry.page || "history"}.`;
}

function deleteHistoryEntry(index) {
  const history = readHistory();
  history.splice(index, 1);
  writeHistory(history);
  renderRecentHistory();
  statusEl.textContent = "Removed one scaffold record.";
}

function toggleFavorite(index) {
  const history = readHistory();
  const entry = history[index];
  if (!entry) {
    return;
  }

  entry.favorite = !entry.favorite;
  history.sort((left, right) => {
    const favoriteDelta = Number(Boolean(right.favorite)) - Number(Boolean(left.favorite));
    if (favoriteDelta !== 0) {
      return favoriteDelta;
    }
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
  });
  writeHistory(history);
  renderRecentHistory();
  statusEl.textContent = entry.favorite ? "Pinned scaffold record to the top." : "Removed scaffold pin.";
}

function clearHistory() {
  window.localStorage.removeItem(HISTORY_KEY);
  renderRecentHistory();
  statusEl.textContent = "Cleared scaffold history.";
}

async function copyPath(path) {
  if (!path) {
    statusEl.textContent = "Nothing to copy for this entry.";
    return;
  }

  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(path);
    statusEl.textContent = `Copied path: ${path}`;
    return;
  }

  const temp = document.createElement("textarea");
  temp.value = path;
  document.body.appendChild(temp);
  temp.select();
  document.execCommand("copy");
  document.body.removeChild(temp);
  statusEl.textContent = `Copied path: ${path}`;
}

async function copyText(text, successLabel = "Copied text.") {
  if (!text) {
    statusEl.textContent = "Nothing to copy for this entry.";
    return;
  }

  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    statusEl.textContent = successLabel;
    return;
  }

  const temp = document.createElement("textarea");
  temp.value = text;
  document.body.appendChild(temp);
  temp.select();
  document.execCommand("copy");
  document.body.removeChild(temp);
  statusEl.textContent = successLabel;
}

function openPath(path) {
  if (!path) {
    statusEl.textContent = "Nothing to open for this report.";
    return;
  }
  window.open(path, "_blank", "noopener");
}

function exportHistory() {
  const history = readHistory();
  if (!history.length) {
    statusEl.textContent = "No scaffold history to export.";
    return;
  }
  const blob = new Blob([JSON.stringify(history, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "scaffold-history.json";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  statusEl.textContent = "Exported scaffold history JSON.";
}

function setFieldValue(name, value) {
  const field = formEl.elements.namedItem(name);
  if (field && "value" in field) {
    field.value = value;
  }
}

function renderSummary(result) {
  const pageObject = result.page_object || {};
  const testCase = result.test_case || {};
  const steps = testCase.execution?.steps || [];
  const elements = Object.keys(pageObject.elements || {});

  resultSummaryEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Test Case</strong>
        <span>${testCase.id || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Page</strong>
        <span>${pageObject.page || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Elements</strong>
        <span>${elements.length}</span>
      </div>
      <div class="summary-item">
        <strong>Steps</strong>
        <span>${steps.length}</span>
      </div>
    </div>
    <div class="summary-grid">
      <div class="summary-item">
        <strong>Page Object Path</strong>
        <span>${result.page_object_path || "-"}</span>
      </div>
      <div class="summary-item">
        <strong>Test Case Path</strong>
        <span>${result.test_case_path || "-"}</span>
      </div>
    </div>
  `;
}

function showRequestPreview(payload, sourceLabel) {
  const issues = validatePayload(payload);
  const diff = buildRequestDiff(payload);
  const blockingIssues = issues.some((issue) => issue.level === "error");
  pendingRequest = { payload, sourceLabel };
  requestPreviewBodyEl.textContent = JSON.stringify(payload, null, 2);
  requestPreviewDiffEl.textContent = diff.text;
  requestPreviewSummaryEl.innerHTML = `
    <div class="summary-item">
      <strong>Source</strong>
      <span>${sourceLabel}</span>
    </div>
    <div class="summary-item">
      <strong>Changed Fields</strong>
      <span>${diff.changedKeys}</span>
    </div>
  `;
  requestPreviewChecksEl.innerHTML = issues
    .map((issue) => `<li class="check-item${issue.level === "error" ? " is-error" : " is-info"}">${issue.message}</li>`)
    .join("");
  confirmPreviewButtonEl.disabled = blockingIssues;
  requestPreviewEl.classList.remove("is-hidden");
  statusEl.textContent = blockingIssues
    ? `Previewing ${sourceLabel} request. Fix the preflight errors before sending.`
    : `Previewing ${sourceLabel} request. Confirm to send it.`;
}

function hideRequestPreview() {
  pendingRequest = null;
  requestPreviewBodyEl.textContent = "{}";
  requestPreviewDiffEl.textContent = "No previous request to compare.";
  requestPreviewSummaryEl.innerHTML = `
    <div class="summary-item">
      <strong>Source</strong>
      <span>Pending</span>
    </div>
    <div class="summary-item">
      <strong>Changed Fields</strong>
      <span>0</span>
    </div>
  `;
  requestPreviewChecksEl.innerHTML = `<li class="check-item is-info">No checks yet.</li>`;
  confirmPreviewButtonEl.disabled = false;
  requestPreviewEl.classList.add("is-hidden");
}

function buildRequestDiff(nextPayload) {
  const previousPayload = readLastRequest();
  if (!previousPayload) {
    return {
      text: "No previous request to compare.",
      changedKeys: 0,
    };
  }

  const lines = [];
  const keys = new Set([...Object.keys(previousPayload), ...Object.keys(nextPayload)]);
  for (const key of Array.from(keys).sort()) {
    const previousValue = JSON.stringify(previousPayload[key] ?? null);
    const nextValue = JSON.stringify(nextPayload[key] ?? null);
    if (previousValue === nextValue) {
      continue;
    }
    lines.push(`~ ${key}`);
    lines.push(`  previous: ${previousValue}`);
    lines.push(`  next:     ${nextValue}`);
  }

  return {
    text: lines.length ? lines.join("\n") : "No changes from the last request.",
    changedKeys: lines.filter((line) => line.startsWith("~ ")).length,
  };
}

function renderSteps(result) {
  const steps = result.test_case?.execution?.steps || [];
  if (!steps.length) {
    stepListEl.innerHTML = `<li class="empty-state">No generated steps yet.</li>`;
    return;
  }

  stepListEl.innerHTML = steps
    .map((step) => {
      const meta = [step.target ? `target: ${step.target}` : "", step.value ? `value: ${step.value}` : ""]
        .filter(Boolean)
        .join(" | ");
      return `
        <li>
          <span class="step-action">${step.action}</span>
          <span class="step-meta">${meta || "no extra args"}</span>
        </li>
      `;
    })
    .join("");
}

function renderElements(result) {
  const entries = Object.entries(result.page_object?.elements || {});
  if (!entries.length) {
    elementListEl.innerHTML = `<div class="empty-state">No generated elements yet.</div>`;
    return;
  }

  elementListEl.innerHTML = entries
    .map(([name, element]) => {
      const parts = [
        `locator: ${element.locator_type}`,
        element.role ? `role: ${element.role}` : "",
        `value: ${element.locator_value}`,
        element.description ? `desc: ${element.description}` : "",
      ].filter(Boolean);

      return `
        <article class="element-card">
          <strong>${name}</strong>
          <span>${parts.join(" | ")}</span>
        </article>
      `;
    })
    .join("");
}

async function submitScaffold(event) {
  event.preventDefault();
  try {
    showRequestPreview(buildPayloadFromForm(), "form");
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

async function executeScaffoldRequest(payload) {
  try {
    const result = await fetchJson("/assets/scaffold", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    renderSummary(result);
    renderSteps(result);
    renderElements(result);
    resultEl.textContent = JSON.stringify(result, null, 2);
    statusEl.textContent = `Created ${result.test_case?.id || "scaffold"} successfully.`;
    persistHistoryEntry(result, payload);
    persistFormState();
    writeLastRequest(payload);
    hideRequestPreview();
    await loadLatestReportSummary();
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

async function confirmPreview() {
  if (!pendingRequest) {
    statusEl.textContent = "No pending scaffold request.";
    return;
  }

  statusEl.textContent = `Sending ${pendingRequest.sourceLabel} request...`;
  await executeScaffoldRequest(pendingRequest.payload);
}

reloadButtonEl.addEventListener("click", loadTemplates);
formEl.addEventListener("submit", submitScaffold);
formEl.addEventListener("input", persistFormState);
function handleHistoryAction(event) {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  const index = target.dataset.historyIndex;
  if (index !== undefined) {
    applyHistoryEntry(Number(index));
    return;
  }

  const deleteIndex = target.dataset.deleteHistoryIndex;
  if (deleteIndex !== undefined) {
    deleteHistoryEntry(Number(deleteIndex));
    return;
  }

  const favoriteIndex = target.dataset.favoriteHistoryIndex;
  if (favoriteIndex !== undefined) {
    toggleFavorite(Number(favoriteIndex));
    return;
  }

  const rerunIndex = target.dataset.rerunHistoryIndex;
  if (rerunIndex !== undefined) {
    rerunHistoryEntry(Number(rerunIndex));
    return;
  }

  const aliasIndex = target.dataset.aliasHistoryIndex;
  if (aliasIndex !== undefined) {
    updateHistoryAlias(Number(aliasIndex));
    return;
  }

  const copyPathValue = target.dataset.copyPath;
  if (copyPathValue !== undefined) {
    copyPath(copyPathValue);
  }
}

function handleLatestReportAction(event) {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const copyPathValue = target.dataset.copyPath;
  if (copyPathValue !== undefined) {
    copyPath(copyPathValue);
    return;
  }

  const copyTextValue = target.dataset.copyText;
  if (copyTextValue !== undefined) {
    copyText(copyTextValue, "Copied self-healing advice JSON.");
    return;
  }

  const copyReportTextValue = target.dataset.copyReportText;
  if (copyReportTextValue !== undefined) {
    copyText(copyReportTextValue, "Copied full report JSON.");
    return;
  }

  const copyAnalysisTextValue = target.dataset.copyAnalysisText;
  if (copyAnalysisTextValue !== undefined) {
    copyText(copyAnalysisTextValue, "Copied failure analysis JSON.");
  }
}

recentListEl.addEventListener("click", handleHistoryAction);
favoriteListEl.addEventListener("click", handleHistoryAction);
latestReportSummaryEl.addEventListener("click", handleLatestReportAction);
latestReportAnalysisEl.addEventListener("click", handleLatestReportAction);
latestReportHealingEl.addEventListener("click", handleLatestReportAction);
clearHistoryButtonEl.addEventListener("click", clearHistory);
exportHistoryButtonEl.addEventListener("click", exportHistory);
confirmPreviewButtonEl.addEventListener("click", confirmPreview);
cancelPreviewButtonEl.addEventListener("click", hideRequestPreview);
reloadReportSummaryButtonEl.addEventListener("click", loadLatestReportSummary);
restoreFormState();
renderRecentHistory();
loadTemplates();
loadLatestReportSummary();
