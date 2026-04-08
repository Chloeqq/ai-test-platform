(function () {
  const shell = document.getElementById("page-objects-shell");
  if (!shell) return;

  const projectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  const projectSelectorSupport = window.ProjectSelectorSupport;
  const FILTER_STORAGE_KEY = "atp.page-objects.filters.v1";
  const url = new URL(window.location.href);
  const initialContext = {
    projectCode: String(url.searchParams.get("project_code") || "").trim(),
    client: String(url.searchParams.get("client") || "").trim(),
    health: String(url.searchParams.get("health") || "").trim(),
    pageCode: String(url.searchParams.get("page_code") || "").trim(),
    elementCode: String(url.searchParams.get("element_code") || "").trim(),
    focus: String(url.searchParams.get("focus") || "").trim(),
    recorderAction: String(url.searchParams.get("recorder_action") || "").trim(),
    recorderPageStatus: String(url.searchParams.get("recorder_page_status") || "").trim(),
    recorderIngestedCount: String(url.searchParams.get("recorder_ingested_count") || "").trim(),
    recorderStepCount: String(url.searchParams.get("recorder_step_count") || "").trim(),
    openCreate: String(url.searchParams.get("open") || "").trim() === "create",
    prefillName: String(url.searchParams.get("prefill_name") || url.searchParams.get("page_name") || "").trim(),
    prefillUrl: String(url.searchParams.get("prefill_url") || url.searchParams.get("page_url") || "").trim(),
  };

  const els = {
    filterProject: document.getElementById("po-filter-project"),
    manageProject: document.getElementById("po-manage-project"),
    projectStatusNote: document.getElementById("po-project-status-note"),
    filterClient: document.getElementById("po-filter-client"),
    filterStatus: document.getElementById("po-filter-status"),
    filterHealth: document.getElementById("po-filter-health"),
    filterKeyword: document.getElementById("po-filter-keyword"),
    applyFilters: document.getElementById("po-apply-filters"),
    resetFilters: document.getElementById("po-reset-filters"),
    refresh: document.getElementById("po-refresh"),
    summary: document.getElementById("po-summary"),
    checkAll: document.getElementById("po-check-all"),
    selectionBar: document.getElementById("po-selection-bar"),
    selectionCount: document.getElementById("po-selection-count"),
    batchPublish: document.getElementById("po-batch-publish"),
    batchRetire: document.getElementById("po-batch-retire"),
    batchDelete: document.getElementById("po-batch-delete"),
    batchClear: document.getElementById("po-batch-clear"),
    listBody: document.getElementById("po-list-tbody"),
    openCreate: document.getElementById("po-open-create"),
    createDrawer: document.getElementById("po-create-drawer"),
    createBackdrop: document.getElementById("po-create-drawer-backdrop"),
    createClose: document.getElementById("po-create-close"),
    createForm: document.getElementById("po-create-form"),
    createSubmitMode: document.getElementById("po-create-submit-mode"),
    createCode: document.getElementById("po-create-code"),
    createName: document.getElementById("po-create-name"),
    createUrl: document.getElementById("po-create-url"),
    createPrecondition: document.getElementById("po-create-precondition"),
    createModule: document.getElementById("po-create-module"),
    createStatus: document.getElementById("po-create-status"),
    createHealth: document.getElementById("po-create-health"),
    createDescription: document.getElementById("po-create-description"),
    createDraft: document.getElementById("po-create-draft"),
    createSubmit: document.getElementById("po-create-submit"),
    createPrev: document.getElementById("po-create-prev"),
    createNext: document.getElementById("po-create-next"),
    createStepTriggers: Array.from(document.querySelectorAll("[data-create-step-trigger]")),
    createStepPanels: Array.from(document.querySelectorAll("[data-create-step-panel]")),
    quickElementCode: document.getElementById("po-quick-element-code"),
    quickElementName: document.getElementById("po-quick-element-name"),
    quickElementLocatorType: document.getElementById("po-quick-element-locator-type"),
    quickElementLocatorValue: document.getElementById("po-quick-element-locator-value"),
    previewName: document.getElementById("po-preview-name"),
    previewCode: document.getElementById("po-preview-code"),
    previewStatus: document.getElementById("po-preview-status"),
    previewElement: document.getElementById("po-preview-element"),
    sideTabs: Array.from(document.querySelectorAll("[data-po-tab]")),
    detailPanel: document.getElementById("po-detail-panel"),
    elementsPanel: document.getElementById("po-elements-panel"),
    empty: document.getElementById("po-empty"),
    detailForm: document.getElementById("po-detail-form"),
    detailCode: document.getElementById("po-detail-code"),
    detailName: document.getElementById("po-detail-name"),
    detailUrl: document.getElementById("po-detail-url"),
    detailPrecondition: document.getElementById("po-detail-precondition"),
    detailModule: document.getElementById("po-detail-module"),
    detailStatus: document.getElementById("po-detail-status"),
    detailHealth: document.getElementById("po-detail-health"),
    detailDescription: document.getElementById("po-detail-description"),
    detailDelete: document.getElementById("po-detail-delete"),
    elementForm: document.getElementById("po-element-form"),
    elementCode: document.getElementById("po-element-code"),
    elementName: document.getElementById("po-element-name"),
    elementLocatorType: document.getElementById("po-element-locator-type"),
    elementLocatorValue: document.getElementById("po-element-locator-value"),
    elementBackup: document.getElementById("po-element-backup"),
    elementStatus: document.getElementById("po-element-status"),
    elementHealth: document.getElementById("po-element-health"),
    elementRole: document.getElementById("po-element-role"),
    elementSave: document.getElementById("po-element-save"),
    elementReset: document.getElementById("po-element-reset"),
    elementDelete: document.getElementById("po-element-delete"),
    elementsBody: document.getElementById("po-elements-tbody"),
    toast: document.getElementById("po-toast"),
  };

  const state = {
    items: [],
    selectedPageCode: "",
    selectedElementCode: "",
    elements: [],
    projectItems: [],
    activeTab: initialContext.focus === "detail" ? "detail" : "elements",
    createStep: 1,
    createCodeDirty: false,
    createSubmitMode: "draft",
    pendingPageCode: initialContext.pageCode,
    pendingElementCode: initialContext.elementCode,
    contextConsumed: false,
    filteredItems: [],
    bulkSelected: new Set(),
  };

  function detectKeywordProbeTarget() {
    const parsed = parseSearchQuery(String(els.filterKeyword.value || "").trim());
    if (parsed.code) return String(parsed.code || "").trim().toLowerCase();
    if (parsed.name) return String(parsed.name || "").trim().toLowerCase();
    if (parsed.text.length === 1) return String(parsed.text[0] || "").trim().toLowerCase();
    return "";
  }

  function safeLocalStorageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (_error) {
      return;
    }
  }

  function readSavedFilters() {
    const raw = safeLocalStorageGet(FILTER_STORAGE_KEY);
    if (!raw) return {};
    try {
      const payload = JSON.parse(raw);
      if (!payload || typeof payload !== "object") return {};
      return payload;
    } catch (_error) {
      return {};
    }
  }

  function persistFilters() {
    safeLocalStorageSet(
      FILTER_STORAGE_KEY,
      JSON.stringify({
        projectCode: String(els.filterProject.value || "").trim(),
        client: String(els.filterClient.value || "").trim(),
        status: String(els.filterStatus.value || "").trim(),
        health: String(els.filterHealth.value || "").trim(),
        keyword: String(els.filterKeyword.value || "").trim(),
      })
    );
  }

  function stripInitialContext() {
    if (state.contextConsumed) return;
    const nextUrl = new URL(window.location.href);
    [
      "project_code",
      "client",
      "health",
      "page_code",
      "element_code",
      "focus",
      "recorder_action",
      "recorder_page_status",
      "recorder_ingested_count",
      "recorder_step_count",
      "open",
      "prefill_name",
      "prefill_url",
      "page_name",
      "page_url",
    ].forEach(function (key) {
      nextUrl.searchParams.delete(key);
    });
    const nextSearch = nextUrl.searchParams.toString();
    const nextHref = nextUrl.pathname + (nextSearch ? ("?" + nextSearch) : "") + nextUrl.hash;
    window.history.replaceState({}, "", nextHref);
    state.contextConsumed = true;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function showToast(message, error) {
    if (!els.toast) return;
    els.toast.textContent = message;
    els.toast.classList.remove("hidden");
    if (error) els.toast.classList.add("error");
    else els.toast.classList.remove("error");
    window.clearTimeout(showToast.timerId);
    showToast.timerId = window.setTimeout(function () {
      els.toast.classList.add("hidden");
    }, 2600);
  }

  async function request(path, options) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      ...options,
    });
    const payload = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const detail = payload && payload.detail ? String(payload.detail) : "request failed";
      throw new Error(detail);
    }
    return payload;
  }

  function queryString(params) {
    const search = new URLSearchParams();
    Object.keys(params).forEach(function (key) {
      const value = String(params[key] || "").trim();
      if (!value) return;
      search.set(key, value);
    });
    const output = search.toString();
    return output ? ("?" + output) : "";
  }

  function normalizeSlug(value, maxLength) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, maxLength || 80);
  }

  function derivePageCodeCandidate() {
    const fromName = normalizeSlug(els.createName.value, 40);
    if (fromName) return fromName;
    const rawUrl = String(els.createUrl.value || "").trim();
    if (!rawUrl) return "";
    try {
      const parsed = new URL(rawUrl, window.location.origin);
      const joined = parsed.pathname.split("/").filter(Boolean).slice(-2).join("-");
      return normalizeSlug(joined, 40);
    } catch (_error) {
      return normalizeSlug(rawUrl, 40);
    }
  }

  function deriveQuickElementCodeCandidate() {
    return normalizeSlug(els.quickElementName.value, 80);
  }

  function syncCreateDerivedFields() {
    if (!state.createCodeDirty) {
      const candidate = derivePageCodeCandidate();
      if (candidate) els.createCode.value = candidate;
    }
    if (!String(els.quickElementCode.value || "").trim()) {
      const elementCandidate = deriveQuickElementCodeCandidate();
      if (elementCandidate) els.quickElementCode.value = elementCandidate;
    }
    syncCreatePreview();
  }

  function syncCreatePreview() {
    if (els.previewName) els.previewName.textContent = String(els.createName.value || "").trim() || "-";
    if (els.previewCode) els.previewCode.textContent = String(els.createCode.value || "").trim() || "-";
    if (els.previewStatus) {
      els.previewStatus.textContent = state.createSubmitMode === "publish"
        ? "published"
        : (String(els.createStatus.value || "draft").trim() || "draft");
    }
    if (els.previewElement) {
      const elementCode = String(els.quickElementCode.value || "").trim();
      const elementName = String(els.quickElementName.value || "").trim();
      els.previewElement.textContent = elementCode || elementName
        ? [elementCode || "-", elementName || "-"].join(" / ")
        : "未填写";
    }
  }

  function setCreateStep(step) {
    const nextStep = Math.max(1, Math.min(3, Number(step || 1)));
    state.createStep = nextStep;
    els.createStepTriggers.forEach(function (trigger) {
      const active = Number(trigger.dataset.createStepTrigger || 0) === nextStep;
      trigger.classList.toggle("is-active", active);
    });
    els.createStepPanels.forEach(function (panel) {
      const active = Number(panel.dataset.createStepPanel || 0) === nextStep;
      panel.classList.toggle("hidden", !active);
    });
    if (els.createPrev) els.createPrev.disabled = nextStep === 1;
    if (els.createNext) els.createNext.classList.toggle("hidden", nextStep === 3);
    if (els.createDraft) els.createDraft.classList.toggle("hidden", nextStep !== 3);
    if (els.createSubmit) els.createSubmit.classList.toggle("hidden", nextStep !== 3);
    syncCreatePreview();
  }

  function openCreateDrawer() {
    if (!els.createDrawer || !els.createBackdrop) return;
    els.createDrawer.classList.remove("hidden");
    els.createBackdrop.classList.remove("hidden");
    els.createDrawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("po-drawer-open");
    setCreateStep(state.createStep || 1);
  }

  function closeCreateDrawer() {
    if (!els.createDrawer || !els.createBackdrop) return;
    els.createDrawer.classList.add("hidden");
    els.createBackdrop.classList.add("hidden");
    els.createDrawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("po-drawer-open");
  }

  function resetCreateForm() {
    els.createForm.reset();
    els.createModule.value = "0";
    els.createStatus.value = "draft";
    els.createHealth.value = "1";
    els.quickElementLocatorType.value = "css";
    els.createSubmitMode.value = "draft";
    state.createCodeDirty = false;
    state.createSubmitMode = "draft";
    setCreateStep(1);
    syncCreatePreview();
  }

  function setActiveTab(tab) {
    state.activeTab = tab === "detail" ? "detail" : "elements";
    els.sideTabs.forEach(function (button) {
      const active = button.dataset.poTab === state.activeTab;
      button.classList.toggle("is-active", active);
    });
    if (els.detailPanel) els.detailPanel.classList.toggle("hidden", state.activeTab !== "detail");
    if (els.elementsPanel) els.elementsPanel.classList.toggle("hidden", state.activeTab !== "elements");
  }

  function getScope() {
    const currentProjectCode = projectSelectorSupport
      ? (projectSelectorSupport.normalizeCode(els.filterProject.value || "atp") || "atp")
      : (String(els.filterProject.value || "").trim().toLowerCase() || "atp");
    return {
      project_code: currentProjectCode,
      client: String(els.filterClient.value || "").trim() || "web",
    };
  }

  function isCurrentProjectActive() {
    if (!projectSelectorSupport) return true;
    const currentProjectCode = projectSelectorSupport.normalizeCode(els.filterProject.value || "atp");
    const project = state.projectItems.find(function (item) {
      return projectSelectorSupport.normalizeCode(item.project_code) === currentProjectCode;
    });
    if (!project) return true;
    return projectSelectorSupport.normalizeCode(project.status || "active") === "active";
  }

  function syncWriteGuards() {
    const active = isCurrentProjectActive();
    if (els.createDraft) els.createDraft.disabled = !active;
    if (els.createSubmit) els.createSubmit.disabled = !active;
    if (els.detailForm) {
      const detailSave = els.detailForm.querySelector("#po-detail-save");
      if (detailSave) detailSave.disabled = !active;
    }
    if (els.elementSave) els.elementSave.disabled = !active;
    if (els.projectStatusNote) {
      els.projectStatusNote.textContent = active
        ? ""
        : "当前项目为 inactive，仅允许浏览与删除，不允许新增或编辑。";
    }
    syncSelectionBar();
  }

  function setProjectOptions(items, selectedValue) {
    if (!projectSelectorSupport) return;
    projectSelectorSupport.applyProjectOptions(els.filterProject, items, {
      selectedValue: selectedValue || "atp",
      defaultProjectCode: "atp",
    });
    state.projectItems = Array.isArray(items) ? items : [];
    syncWriteGuards();
  }

  async function loadProjects(selectedValue) {
    if (!projectsApi || typeof projectsApi.list !== "function" || !projectSelectorSupport) return;
    const items = await projectSelectorSupport.loadProjectOptions({
      projectsApi: projectsApi,
      selectEl: els.filterProject,
      selectedValue: selectedValue || "atp",
      defaultProjectCode: "atp",
    });
    setProjectOptions(items, selectedValue || "atp");
  }

  function openProjectManager() {
    if (!projectManager || typeof projectManager.open !== "function" || !projectSelectorSupport) {
      showToast("项目管理组件未就绪。", true);
      return;
    }
    projectSelectorSupport.openProjectManager({
      projectManager: projectManager,
      projectsApi: projectsApi,
      selectEl: els.filterProject,
      defaultProjectCode: "atp",
      deleteFallbackValue: "atp",
      onChanged: async function ({ action, projectCode, items, selectedProjectCode }) {
        setProjectOptions(items, selectedProjectCode || "atp");
        state.selectedPageCode = "";
        state.selectedElementCode = "";
        await loadPageObjects();
        if (action === "create") showToast("项目 " + selectedProjectCode + " 已创建。");
        else if (action === "update") showToast("项目 " + selectedProjectCode + " 已更新。");
        else if (action === "delete") showToast("项目 " + projectCode + " 已删除。");
      },
    });
  }

  function parseSearchQuery(input) {
    const tokens = String(input || "").trim().split(/\s+/).filter(Boolean);
    const parsed = {
      text: [],
      status: "",
      health: "",
      creator: "",
      module: "",
      code: "",
      name: "",
      precondition: "",
    };
    tokens.forEach(function (token) {
      const separatorIndex = token.indexOf(":");
      if (separatorIndex <= 0) {
        parsed.text.push(token.toLowerCase());
        return;
      }
      const key = token.slice(0, separatorIndex).toLowerCase();
      const value = token.slice(separatorIndex + 1).trim().toLowerCase();
      if (!value) return;
      if (key === "status") parsed.status = value;
      else if (key === "health") parsed.health = value;
      else if (key === "creator" || key === "created_by") parsed.creator = value;
      else if (key === "module" || key === "module_id") parsed.module = value;
      else if (key === "code" || key === "page_code") parsed.code = value;
      else if (key === "name" || key === "page_name") parsed.name = value;
      else if (key === "precondition" || key === "precondition_state") parsed.precondition = value;
      else parsed.text.push(token.toLowerCase());
    });
    return parsed;
  }

  function getFilteredItems() {
    const keyword = String(els.filterKeyword.value || "").trim();
    const parsed = parseSearchQuery(keyword);
    const uiHealth = String(els.filterHealth.value || "").trim();
    return state.items.filter(function (item) {
      const pageCode = String(item.page_code || "").toLowerCase();
      const pageName = String(item.page_name || "").toLowerCase();
      const description = String(item.description || "").toLowerCase();
      const precondition = String(item.precondition_state || "").toLowerCase();
      const createdBy = String(item.created_by || "").toLowerCase();
      const moduleId = String(item.module_id == null ? "" : item.module_id).toLowerCase();
      const status = String(item.status || "").toLowerCase();
      const health = String(item.health_status == null ? "" : item.health_status).toLowerCase();

      if (uiHealth && health !== uiHealth) return false;
      if (parsed.status && status !== parsed.status) return false;
      if (parsed.health && health !== parsed.health) return false;
      if (parsed.creator && !createdBy.includes(parsed.creator)) return false;
      if (parsed.module && moduleId !== parsed.module) return false;
      if (parsed.code && !pageCode.includes(parsed.code)) return false;
      if (parsed.name && !pageName.includes(parsed.name)) return false;
      if (parsed.precondition && !precondition.includes(parsed.precondition)) return false;
      if (parsed.text.length) {
        const haystack = [pageCode, pageName, description, precondition, createdBy, moduleId].join(" ");
        const match = parsed.text.every(function (textToken) {
          return haystack.includes(textToken);
        });
        if (!match) return false;
      }
      return true;
    });
  }

  function getSelectedItems() {
    return state.items.filter(function (item) {
      return state.bulkSelected.has(item.page_code);
    });
  }

  function syncSelectionBar() {
    const count = state.bulkSelected.size;
    if (els.selectionCount) els.selectionCount.textContent = String(count);
    if (els.selectionBar) els.selectionBar.classList.toggle("hidden", count === 0);
    if (els.checkAll) {
      const visibleCodes = state.filteredItems.map(function (item) { return item.page_code; });
      const selectedVisibleCount = visibleCodes.filter(function (code) { return state.bulkSelected.has(code); }).length;
      els.checkAll.checked = visibleCodes.length > 0 && selectedVisibleCount === visibleCodes.length;
      els.checkAll.indeterminate = selectedVisibleCount > 0 && selectedVisibleCount < visibleCodes.length;
    }
    const writeDisabled = !isCurrentProjectActive() || count === 0;
    if (els.batchPublish) els.batchPublish.disabled = writeDisabled;
    if (els.batchRetire) els.batchRetire.disabled = writeDisabled;
    if (els.batchDelete) els.batchDelete.disabled = count === 0;
    if (els.batchClear) els.batchClear.disabled = count === 0;
  }

  function clearBulkSelection() {
    state.bulkSelected.clear();
    syncSelectionBar();
  }

  function focusElementForm() {
    setActiveTab("elements");
    if (!state.selectedPageCode) return;
    els.elementCode.focus();
  }

  function renderList() {
    const filtered = getFilteredItems();
    state.filteredItems = filtered;
    const previousSelectedPageCode = state.selectedPageCode;
    if (!filtered.some(function (item) { return item.page_code === state.selectedPageCode; })) {
      state.selectedPageCode = filtered.length ? String(filtered[0].page_code || "") : "";
      state.selectedElementCode = "";
    }
    const selectionChanged = previousSelectedPageCode !== state.selectedPageCode;
    if (!filtered.length) {
      els.listBody.innerHTML = [
        '<tr><td colspan="7" class="empty-state">',
        '<div class="po-empty-block">',
        "<strong>还没有页面对象</strong>",
        "<p>点击“开始页面录制”一键生成，或手动创建页面对象。</p>",
        '<div class="po-empty-actions">',
        '<a class="btn btn-primary" href="/assets/page-objects/recorder">开始页面录制</a>',
        '<button class="btn btn-soft" type="button" data-empty-action="create">手动创建</button>',
        "</div>",
        "</div>",
        "</td></tr>",
      ].join("");
      els.summary.textContent = state.items.length
        ? "当前筛选条件下暂无页面对象，请调整项目/状态/关键词。"
        : "暂无页面对象";
      setPageDetail(null);
      syncSelectionBar();
      return { selectionChanged: selectionChanged };
    }
    els.summary.textContent = "共 " + filtered.length + " 个页面对象。";
    els.listBody.innerHTML = filtered.map(function (item) {
      const selected = item.page_code === state.selectedPageCode ? " class=\"selected\"" : "";
      const checked = state.bulkSelected.has(item.page_code) ? " checked" : "";
      const updatedAt = item.updated_at ? new Date(item.updated_at).toLocaleString() : "-";
      return "<tr data-page-code=\"" + escapeHtml(item.page_code) + "\"" + selected + ">"
        + "<td class=\"po-col-check\"><input data-row-check type=\"checkbox\" aria-label=\"选择 " + escapeHtml(item.page_code) + "\"" + checked + "></td>"
        + "<td><strong>" + escapeHtml(item.page_code) + "</strong></td>"
        + "<td>" + escapeHtml(item.page_name) + "</td>"
        + "<td>" + escapeHtml(item.status) + "</td>"
        + "<td>" + escapeHtml(item.element_count) + "</td>"
        + "<td>" + escapeHtml(item.health_status) + "</td>"
        + "<td>" + escapeHtml(updatedAt) + "</td>"
        + "</tr>";
    }).join("");
    syncSelectionBar();
    return { selectionChanged: selectionChanged };
  }

  async function syncListSelectionAfterFilterRender() {
    const renderResult = renderList() || {};
    if (renderResult.selectionChanged) {
      await loadSelectedPage();
    }
  }

  function renderElements() {
    if (!state.selectedPageCode) {
      els.elementsBody.innerHTML = '<tr><td colspan="4" class="empty-state"><div class="po-empty-block"><strong>请选择页面对象</strong><p>从左侧列表选择一个页面对象后，再补录或校验元素。</p></div></td></tr>';
      return;
    }
    if (!state.elements.length) {
      els.elementsBody.innerHTML = [
        '<tr><td colspan="4" class="empty-state">',
        '<div class="po-empty-block">',
        "<strong>该页面暂无元素</strong>",
        "<p>可以先手动补一个关键元素，或重新录制页面。</p>",
        '<div class="po-empty-actions">',
        '<button class="btn btn-soft" type="button" data-element-empty-action="focus-form">添加元素</button>',
        '<a class="btn btn-soft" href="/assets/page-objects/recorder">重新录制页面</a>',
        "</div>",
        "</div>",
        "</td></tr>",
      ].join("");
      return;
    }
    els.elementsBody.innerHTML = state.elements.map(function (item) {
      const selected = item.element_code === state.selectedElementCode ? " class=\"selected\"" : "";
      return "<tr data-element-code=\"" + escapeHtml(item.element_code) + "\"" + selected + ">"
        + "<td><strong>" + escapeHtml(item.element_code) + "</strong><br><span>" + escapeHtml(item.element_name) + "</span></td>"
        + "<td>" + escapeHtml(item.locator_type) + " · " + escapeHtml(item.locator_value) + "</td>"
        + "<td>" + escapeHtml(item.status) + " / " + escapeHtml(item.health_status) + "</td>"
        + "<td>" + escapeHtml(item.version) + "</td>"
        + "</tr>";
    }).join("");
  }

  function resetElementForm() {
    state.selectedElementCode = "";
    els.elementCode.value = "";
    els.elementName.value = "";
    els.elementLocatorType.value = "css";
    els.elementLocatorValue.value = "";
    els.elementBackup.value = "";
    els.elementStatus.value = "active";
    els.elementHealth.value = "1";
    els.elementRole.value = "";
    els.elementCode.disabled = false;
    els.elementSave.textContent = "新增元素";
    els.elementDelete.disabled = true;
  }

  function setPageDetail(item) {
    if (!item) {
      els.empty.classList.remove("hidden");
      els.detailForm.classList.add("hidden");
      els.elementForm.classList.add("hidden");
      resetElementForm();
      renderElements();
      return;
    }
    els.empty.classList.add("hidden");
    els.detailForm.classList.remove("hidden");
    els.elementForm.classList.remove("hidden");
    els.detailCode.value = item.page_code || "";
    els.detailName.value = item.page_name || "";
    els.detailUrl.value = item.page_url || "";
    els.detailPrecondition.value = item.precondition_state || "";
    els.detailModule.value = String(item.module_id == null ? 0 : item.module_id);
    els.detailStatus.value = item.status || "draft";
    els.detailHealth.value = String(item.health_status == null ? 1 : item.health_status);
    els.detailDescription.value = item.description || "";
  }

  async function loadPageObjects(options) {
    const config = options && typeof options === "object" ? options : {};
    const allowAutoProjectFallback = config.allowAutoProjectFallback !== false;
    persistFilters();
    els.listBody.innerHTML = '<tr><td colspan="6" class="loading-state">正在加载页面对象...</td></tr>';
    const params = {
      project_code: String(els.filterProject.value || "").trim(),
      client: String(els.filterClient.value || "").trim(),
      status: String(els.filterStatus.value || "").trim(),
    };
    const payload = await request("/api/page-objects" + queryString(params));
    state.items = Array.isArray(payload.items) ? payload.items : [];
    if (
      allowAutoProjectFallback
      && state.items.length === 0
      && String(params.project_code || "").trim()
    ) {
      const probeTarget = detectKeywordProbeTarget();
      if (probeTarget) {
        const probePayload = await request(
          "/api/page-objects" + queryString({
            client: params.client,
            status: params.status,
          })
        );
        const probeItems = Array.isArray(probePayload.items) ? probePayload.items : [];
        const matched = probeItems.filter(function (item) {
          const pageCode = String(item.page_code || "").toLowerCase();
          const pageName = String(item.page_name || "").toLowerCase();
          return pageCode.includes(probeTarget) || pageName.includes(probeTarget);
        });
        const distinctProjects = Array.from(new Set(matched.map(function (item) {
          return String(item.project_code || "").trim().toLowerCase();
        }).filter(Boolean)));
        if (distinctProjects.length === 1 && distinctProjects[0] !== String(params.project_code || "").trim().toLowerCase()) {
          const nextProjectCode = distinctProjects[0];
          const option = els.filterProject.querySelector('option[value="' + nextProjectCode + '"]');
          if (option) {
            els.filterProject.value = nextProjectCode;
            persistFilters();
            showToast("已自动切换到项目 " + nextProjectCode + " 以显示匹配结果。");
            return loadPageObjects({ allowAutoProjectFallback: false });
          }
        }
      }
    }
    state.bulkSelected = new Set(Array.from(state.bulkSelected).filter(function (pageCode) {
      return state.items.some(function (item) { return item.page_code === pageCode; });
    }));
    if (state.pendingPageCode && state.items.some(function (item) { return item.page_code === state.pendingPageCode; })) {
      state.selectedPageCode = state.pendingPageCode;
      state.pendingPageCode = "";
    } else if (!state.items.some(function (item) { return item.page_code === state.selectedPageCode; })) {
      state.selectedPageCode = state.items.length ? state.items[0].page_code : "";
    }
    await syncListSelectionAfterFilterRender();
    if (!state.selectedPageCode) {
      setPageDetail(null);
      return;
    }
    await loadSelectedPage();
  }

  async function loadSelectedPage() {
    if (!state.selectedPageCode) {
      setPageDetail(null);
      return;
    }
    const scope = getScope();
    const pagePayload = await request(
      "/api/page-objects/" + encodeURIComponent(state.selectedPageCode) + queryString(scope)
    );
    setPageDetail(pagePayload.item || null);
    const elementsPayload = await request(
      "/api/page-objects/" + encodeURIComponent(state.selectedPageCode) + "/elements" + queryString(scope)
    );
    state.elements = Array.isArray(elementsPayload.items) ? elementsPayload.items : [];
    if (state.pendingElementCode && state.elements.some(function (item) { return item.element_code === state.pendingElementCode; })) {
      state.selectedElementCode = state.pendingElementCode;
      state.pendingElementCode = "";
    } else if (!state.elements.some(function (item) { return item.element_code === state.selectedElementCode; })) {
      state.selectedElementCode = "";
    }
    renderElements();
    if (!state.selectedElementCode) {
      resetElementForm();
    } else {
      const target = state.elements.find(function (item) { return item.element_code === state.selectedElementCode; });
      if (target) {
        els.elementCode.value = target.element_code || "";
        els.elementName.value = target.element_name || "";
        els.elementLocatorType.value = target.locator_type || "css";
        els.elementLocatorValue.value = target.locator_value || "";
        els.elementBackup.value = target.backup_locator || "";
        els.elementStatus.value = target.status || "active";
        els.elementHealth.value = String(target.health_status == null ? 1 : target.health_status);
        els.elementRole.value = target.role || "";
        els.elementCode.disabled = true;
        els.elementSave.textContent = "保存元素";
        els.elementDelete.disabled = false;
      }
    }
  }

  function collectQuickElement() {
    const payload = {
      element_code: String(els.quickElementCode.value || "").trim(),
      element_name: String(els.quickElementName.value || "").trim(),
      locator_type: String(els.quickElementLocatorType.value || "css").trim(),
      locator_value: String(els.quickElementLocatorValue.value || "").trim(),
    };
    const complete = Boolean(payload.element_code && payload.element_name && payload.locator_value);
    const partial = Boolean(payload.element_code || payload.element_name || payload.locator_value);
    return { payload: payload, complete: complete, partial: partial };
  }

  async function createPageObject(event) {
    event.preventDefault();
    if (!isCurrentProjectActive()) {
      showToast("当前项目是 inactive，无法创建页面对象。", true);
      return;
    }
    const scope = getScope();
    const pageCode = String(els.createCode.value || "").trim();
    if (!pageCode) {
      showToast("请先补齐页面编码。", true);
      setCreateStep(1);
      return;
    }
    const quickElement = collectQuickElement();
    if (quickElement.partial && !quickElement.complete) {
      showToast("如需快速补元素，请补齐元素编码、名称和定位。", true);
      setCreateStep(2);
      return;
    }
    const payload = {
      project_code: scope.project_code,
      client: scope.client,
      page_code: pageCode,
      page_name: String(els.createName.value || "").trim(),
      page_url: String(els.createUrl.value || "").trim(),
      precondition_state: String(els.createPrecondition.value || "").trim(),
      module_id: Number(els.createModule.value || 0),
      health_status: Number(els.createHealth.value || 1),
      description: String(els.createDescription.value || "").trim(),
      status: state.createSubmitMode === "publish" ? "published" : "draft",
      created_by: "ui-user",
    };
    let quickElementWarning = "";
    const result = await request("/api/page-objects", { method: "POST", body: JSON.stringify(payload) });
    state.selectedPageCode = String(result.item && result.item.page_code ? result.item.page_code : pageCode);
    if (quickElement.complete) {
      try {
        await request(
          "/api/page-objects/" + encodeURIComponent(state.selectedPageCode) + "/elements" + queryString(scope),
          {
            method: "POST",
            body: JSON.stringify({
              element_code: quickElement.payload.element_code,
              element_name: quickElement.payload.element_name,
              locator_type: quickElement.payload.locator_type,
              locator_value: quickElement.payload.locator_value,
              health_status: 1,
              status: "active",
              role: "",
              is_primary: true,
              owner: "ui-user",
              changed_by: "ui-user",
              change_summary: "element created from create drawer",
            }),
          }
        );
        state.selectedElementCode = quickElement.payload.element_code;
      } catch (error) {
        state.selectedElementCode = "";
        quickElementWarning = "页面对象已创建，但快速元素补录失败：" + (error instanceof Error ? error.message : "unknown error");
      }
    }
    closeCreateDrawer();
    resetCreateForm();
    setActiveTab(quickElement.complete ? "elements" : "detail");
    if (quickElementWarning) showToast(quickElementWarning, true);
    else showToast(state.createSubmitMode === "publish" ? "页面对象已创建并发布。" : "页面对象草稿已创建。");
    await loadPageObjects();
  }

  async function savePageObject(event) {
    event.preventDefault();
    if (!state.selectedPageCode) return;
    if (!isCurrentProjectActive()) {
      showToast("当前项目是 inactive，无法编辑页面对象。", true);
      return;
    }
    const scope = getScope();
    const payload = {
      page_name: String(els.detailName.value || "").trim(),
      page_url: String(els.detailUrl.value || "").trim(),
      precondition_state: String(els.detailPrecondition.value || "").trim(),
      module_id: Number(els.detailModule.value || 0),
      health_status: Number(els.detailHealth.value || 1),
      description: String(els.detailDescription.value || "").trim(),
      status: String(els.detailStatus.value || "draft"),
    };
    await request(
      "/api/page-objects/" + encodeURIComponent(state.selectedPageCode) + queryString(scope),
      { method: "PUT", body: JSON.stringify(payload) }
    );
    showToast("页面对象已保存。");
    await loadPageObjects();
  }

  async function deletePageObject() {
    if (!state.selectedPageCode) return;
    const selected = state.items.find(function (item) { return item.page_code === state.selectedPageCode; });
    const elementCount = Number(selected && selected.element_count ? selected.element_count : 0);
    const hasElements = elementCount > 0;
    let message = "删除后不可恢复，确认删除页面对象 " + state.selectedPageCode + " 吗？";
    if (hasElements) {
      message = "该页面对象包含 " + elementCount + " 个元素，删除后不可恢复。是否继续并级联删除全部元素？";
    }
    const confirmed = window.confirm(message);
    if (!confirmed) return;
    const scope = getScope();
    await request(
      "/api/page-objects/" + encodeURIComponent(state.selectedPageCode)
      + queryString({ project_code: scope.project_code, client: scope.client, cascade_elements: hasElements ? "true" : "false" }),
      { method: "DELETE" }
    );
    showToast("页面对象已删除。");
    state.selectedPageCode = "";
    state.selectedElementCode = "";
    await loadPageObjects();
  }

  async function updatePageObjectStatus(item, nextStatus) {
    await request(
      "/api/page-objects/" + encodeURIComponent(item.page_code)
      + queryString({ project_code: item.project_code, client: item.client }),
      {
        method: "PUT",
        body: JSON.stringify({
          page_name: String(item.page_name || "").trim(),
          page_url: String(item.page_url || "").trim(),
          precondition_state: String(item.precondition_state || "").trim(),
          module_id: Number(item.module_id || 0),
          health_status: Number(item.health_status == null ? 1 : item.health_status),
          description: String(item.description || "").trim(),
          status: nextStatus,
        }),
      }
    );
  }

  async function runBatchStatusUpdate(nextStatus, actionLabel) {
    const selectedItems = getSelectedItems();
    if (!selectedItems.length) return;
    if (!isCurrentProjectActive()) {
      showToast("当前项目是 inactive，无法执行批量状态变更。", true);
      return;
    }
    const elementCount = selectedItems.reduce(function (sum, item) {
      return sum + Number(item.element_count || 0);
    }, 0);
    const confirmed = window.confirm(
      "确认" + actionLabel + " " + selectedItems.length + " 个页面对象吗？涉及元素 " + elementCount + " 个。"
    );
    if (!confirmed) return;
    for (const item of selectedItems) {
      await updatePageObjectStatus(item, nextStatus);
    }
    clearBulkSelection();
    showToast(actionLabel + "完成，共处理 " + selectedItems.length + " 个页面对象。");
    await loadPageObjects();
  }

  async function runBatchDelete() {
    const selectedItems = getSelectedItems();
    if (!selectedItems.length) return;
    const objectCount = selectedItems.length;
    const elementCount = selectedItems.reduce(function (sum, item) {
      return sum + Number(item.element_count || 0);
    }, 0);
    const confirmed = window.confirm(
      "确认批量删除 " + objectCount + " 个页面对象吗？该操作不可恢复，并将级联删除 " + elementCount + " 个元素。"
    );
    if (!confirmed) return;
    for (const item of selectedItems) {
      await request(
        "/api/page-objects/" + encodeURIComponent(item.page_code)
        + queryString({
          project_code: item.project_code,
          client: item.client,
          cascade_elements: Number(item.element_count || 0) > 0 ? "true" : "false",
        }),
        { method: "DELETE" }
      );
      if (item.page_code === state.selectedPageCode) {
        state.selectedPageCode = "";
        state.selectedElementCode = "";
      }
    }
    clearBulkSelection();
    showToast("批量删除完成，共删除 " + objectCount + " 个页面对象。");
    await loadPageObjects();
  }

  async function saveElement(event) {
    event.preventDefault();
    if (!state.selectedPageCode) return;
    if (!isCurrentProjectActive()) {
      showToast("当前项目是 inactive，无法写入元素。", true);
      return;
    }
    const scope = getScope();
    const elementCode = String(els.elementCode.value || "").trim();
    const basePayload = {
      element_name: String(els.elementName.value || "").trim(),
      locator_type: String(els.elementLocatorType.value || "").trim(),
      locator_value: String(els.elementLocatorValue.value || "").trim(),
      backup_locator: String(els.elementBackup.value || "").trim(),
      health_status: Number(els.elementHealth.value || 1),
      role: String(els.elementRole.value || "").trim(),
      status: String(els.elementStatus.value || "active").trim(),
      owner: "ui-user",
      changed_by: "ui-user",
      change_summary: state.selectedElementCode ? "element updated from ui" : "element created from ui",
    };
    if (state.selectedElementCode) {
      await request(
        "/api/page-objects/" + encodeURIComponent(state.selectedPageCode)
        + "/elements/" + encodeURIComponent(state.selectedElementCode)
        + queryString(scope),
        { method: "PUT", body: JSON.stringify(basePayload) }
      );
      showToast("元素已更新。");
    } else {
      await request(
        "/api/page-objects/" + encodeURIComponent(state.selectedPageCode)
        + "/elements" + queryString(scope),
        {
          method: "POST",
          body: JSON.stringify({
            ...basePayload,
            element_code: elementCode,
            is_primary: true,
          }),
        }
      );
      state.selectedElementCode = elementCode;
      showToast("元素已新增。");
    }
    await loadSelectedPage();
  }

  async function deleteElement() {
    if (!state.selectedPageCode || !state.selectedElementCode) return;
    if (!window.confirm("删除元素后不可恢复，确认删除 " + state.selectedElementCode + " 吗？")) return;
    const scope = getScope();
    await request(
      "/api/page-objects/" + encodeURIComponent(state.selectedPageCode)
      + "/elements/" + encodeURIComponent(state.selectedElementCode)
      + queryString(scope),
      { method: "DELETE" }
    );
    showToast("元素已删除。");
    state.selectedElementCode = "";
    await loadPageObjects();
  }

  function applySavedAndInitialFilters() {
    const savedFilters = readSavedFilters();
    if (initialContext.pageCode) {
      els.filterClient.value = initialContext.client || String(savedFilters.client || "web");
      els.filterStatus.value = "";
      els.filterHealth.value = "";
      els.filterKeyword.value = "page_code:" + initialContext.pageCode;
      return;
    }
    els.filterClient.value = initialContext.client || String(savedFilters.client || "web");
    els.filterStatus.value = String(savedFilters.status || "");
    els.filterHealth.value = initialContext.health || String(savedFilters.health || "");
    els.filterKeyword.value = String(savedFilters.keyword || "");
  }

  function preferredProjectCode() {
    const savedFilters = readSavedFilters();
    return initialContext.projectCode || String(savedFilters.projectCode || "atp");
  }

  function applyInitialCreatePrefill() {
    if (initialContext.prefillName) els.createName.value = initialContext.prefillName;
    if (initialContext.prefillUrl) els.createUrl.value = initialContext.prefillUrl;
    syncCreateDerivedFields();
    if (initialContext.openCreate || initialContext.prefillName || initialContext.prefillUrl) {
      openCreateDrawer();
    }
  }

  function buildRecorderReturnMessage() {
    if (!initialContext.recorderAction || !initialContext.pageCode) return "";
    const ingestedCount = Number(initialContext.recorderIngestedCount || 0);
    const stepCount = Number(initialContext.recorderStepCount || 0);
    const pageCode = initialContext.pageCode;
    const pageStatus = initialContext.recorderPageStatus || "-";
    if (initialContext.recorderAction === "created") {
      return "录制已创建页面对象 " + pageCode + "，入库元素 " + ingestedCount + " 个，生成步骤草稿 " + stepCount + " 条。";
    }
    if (initialContext.recorderAction === "existing") {
      return "录制已回写到已有页面对象 " + pageCode + "（当前状态 " + pageStatus + "），如列表为空通常是旧筛选条件导致。";
    }
    if (initialContext.recorderAction === "already_stopped") {
      return "该录制会话已经停止，已为你定位到页面对象 " + pageCode + "。";
    }
    return "已定位到页面对象 " + pageCode + "。";
  }

  function attachListeners() {
    els.listBody.addEventListener("change", function (event) {
      const rowCheck = event.target.closest("[data-row-check]");
      if (!rowCheck) return;
      const row = rowCheck.closest("tr[data-page-code]");
      if (!row) return;
      const pageCode = String(row.dataset.pageCode || "");
      if (!pageCode) return;
      if (rowCheck.checked) state.bulkSelected.add(pageCode);
      else state.bulkSelected.delete(pageCode);
      syncSelectionBar();
    });

    els.listBody.addEventListener("click", function (event) {
      const createButton = event.target.closest("[data-empty-action='create']");
      if (createButton) {
        openCreateDrawer();
        return;
      }
      if (event.target.closest("[data-row-check]")) return;
      const row = event.target.closest("tr[data-page-code]");
      if (!row) return;
      state.selectedPageCode = String(row.dataset.pageCode || "");
      state.selectedElementCode = "";
      loadSelectedPage().then(renderList).catch(function (error) {
        showToast(error.message || "加载页面详情失败", true);
      });
    });

    els.elementsBody.addEventListener("click", function (event) {
      const emptyAction = event.target.closest("[data-element-empty-action='focus-form']");
      if (emptyAction) {
        focusElementForm();
        return;
      }
      const row = event.target.closest("tr[data-element-code]");
      if (!row) return;
      state.selectedElementCode = String(row.dataset.elementCode || "");
      const target = state.elements.find(function (item) { return item.element_code === state.selectedElementCode; });
      if (!target) return;
      els.elementCode.value = target.element_code || "";
      els.elementName.value = target.element_name || "";
      els.elementLocatorType.value = target.locator_type || "css";
      els.elementLocatorValue.value = target.locator_value || "";
      els.elementBackup.value = target.backup_locator || "";
      els.elementStatus.value = target.status || "active";
      els.elementHealth.value = String(target.health_status == null ? 1 : target.health_status);
      els.elementRole.value = target.role || "";
      els.elementCode.disabled = true;
      els.elementSave.textContent = "保存元素";
      els.elementDelete.disabled = false;
      renderElements();
    });

    if (els.checkAll) {
      els.checkAll.addEventListener("change", function () {
        state.filteredItems.forEach(function (item) {
          if (els.checkAll.checked) state.bulkSelected.add(item.page_code);
          else state.bulkSelected.delete(item.page_code);
        });
        renderList();
      });
    }

    els.applyFilters.addEventListener("click", function () {
      persistFilters();
      loadPageObjects().catch(function (error) {
        showToast(error.message || "加载页面对象失败", true);
      });
    });

    els.filterProject.addEventListener("change", function () {
      syncWriteGuards();
      persistFilters();
    });

    els.filterClient.addEventListener("change", persistFilters);
    els.filterStatus.addEventListener("change", persistFilters);
    els.filterHealth.addEventListener("change", persistFilters);

    els.resetFilters.addEventListener("click", function () {
      els.filterProject.value = "atp";
      els.filterClient.value = "web";
      els.filterStatus.value = "";
      els.filterHealth.value = "";
      els.filterKeyword.value = "";
      persistFilters();
      loadPageObjects().catch(function (error) {
        showToast(error.message || "加载页面对象失败", true);
      });
    });

    els.refresh.addEventListener("click", function () {
      loadPageObjects().catch(function (error) {
        showToast(error.message || "加载页面对象失败", true);
      });
    });

    if (els.manageProject) {
      els.manageProject.addEventListener("click", function () {
        openProjectManager();
      });
    }

    els.filterKeyword.addEventListener("input", function () {
      persistFilters();
      syncListSelectionAfterFilterRender().catch(function (error) {
        showToast(error.message || "同步筛选结果失败", true);
      });
    });

    els.filterHealth.addEventListener("change", function () {
      persistFilters();
      syncListSelectionAfterFilterRender().catch(function (error) {
        showToast(error.message || "同步筛选结果失败", true);
      });
    });

    if (els.openCreate) els.openCreate.addEventListener("click", openCreateDrawer);
    if (els.createClose) els.createClose.addEventListener("click", closeCreateDrawer);
    if (els.createBackdrop) els.createBackdrop.addEventListener("click", closeCreateDrawer);

    els.createStepTriggers.forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        setCreateStep(Number(trigger.dataset.createStepTrigger || 1));
      });
    });

    if (els.createPrev) {
      els.createPrev.addEventListener("click", function () {
        setCreateStep(state.createStep - 1);
      });
    }

    if (els.createNext) {
      els.createNext.addEventListener("click", function () {
        setCreateStep(state.createStep + 1);
      });
    }

    els.createName.addEventListener("input", syncCreateDerivedFields);
    els.createUrl.addEventListener("input", syncCreateDerivedFields);
    els.createCode.addEventListener("input", function () {
      state.createCodeDirty = Boolean(String(els.createCode.value || "").trim());
      syncCreatePreview();
    });
    els.createStatus.addEventListener("change", syncCreatePreview);
    els.quickElementName.addEventListener("input", syncCreateDerivedFields);
    els.quickElementCode.addEventListener("input", syncCreatePreview);
    els.quickElementLocatorValue.addEventListener("input", syncCreatePreview);

    if (els.createDraft) {
      els.createDraft.addEventListener("click", function () {
        state.createSubmitMode = "draft";
        els.createSubmitMode.value = "draft";
        syncCreatePreview();
      });
    }

    if (els.createSubmit) {
      els.createSubmit.addEventListener("click", function () {
        state.createSubmitMode = "publish";
        els.createSubmitMode.value = "publish";
        syncCreatePreview();
      });
    }

    els.createForm.addEventListener("submit", function (event) {
      if (event.submitter === els.createSubmit) {
        state.createSubmitMode = "publish";
        els.createSubmitMode.value = "publish";
      } else if (event.submitter === els.createDraft) {
        state.createSubmitMode = "draft";
        els.createSubmitMode.value = "draft";
      }
      createPageObject(event).catch(function (error) {
        showToast(error.message || "创建页面对象失败", true);
      });
    });

    els.sideTabs.forEach(function (button) {
      button.addEventListener("click", function () {
        setActiveTab(button.dataset.poTab || "elements");
      });
    });

    els.detailForm.addEventListener("submit", function (event) {
      savePageObject(event).catch(function (error) {
        showToast(error.message || "保存页面对象失败", true);
      });
    });

    els.detailDelete.addEventListener("click", function () {
      deletePageObject().catch(function (error) {
        showToast(error.message || "删除页面对象失败", true);
      });
    });

    if (els.batchPublish) {
      els.batchPublish.addEventListener("click", function () {
        runBatchStatusUpdate("published", "批量发布").catch(function (error) {
          showToast(error.message || "批量发布失败", true);
        });
      });
    }

    if (els.batchRetire) {
      els.batchRetire.addEventListener("click", function () {
        runBatchStatusUpdate("retired", "批量退役").catch(function (error) {
          showToast(error.message || "批量退役失败", true);
        });
      });
    }

    if (els.batchDelete) {
      els.batchDelete.addEventListener("click", function () {
        runBatchDelete().catch(function (error) {
          showToast(error.message || "批量删除失败", true);
        });
      });
    }

    if (els.batchClear) {
      els.batchClear.addEventListener("click", function () {
        clearBulkSelection();
        renderList();
      });
    }

    els.elementForm.addEventListener("submit", function (event) {
      saveElement(event).catch(function (error) {
        showToast(error.message || "保存元素失败", true);
      });
    });

    els.elementReset.addEventListener("click", resetElementForm);
    els.elementDelete.addEventListener("click", function () {
      deleteElement().catch(function (error) {
        showToast(error.message || "删除元素失败", true);
      });
    });

    window.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && els.createDrawer && !els.createDrawer.classList.contains("hidden")) {
        closeCreateDrawer();
      }
    });
  }

  async function init() {
    applySavedAndInitialFilters();
    setActiveTab(state.activeTab);
    setCreateStep(1);
    syncCreatePreview();
    attachListeners();

    const projectCode = preferredProjectCode();
    if (projectsApi && typeof projectsApi.list === "function") {
      await loadProjects(projectCode);
    } else if (projectCode) {
      els.filterProject.value = projectCode;
    }

    if (projectCode) els.filterProject.value = projectCode;
    syncWriteGuards();
    applyInitialCreatePrefill();
    await loadPageObjects();

    if (initialContext.pageCode) {
      showToast(buildRecorderReturnMessage() || ("已定位到页面对象 " + initialContext.pageCode + "。"));
    }
    stripInitialContext();
  }

  init().catch(function (error) {
    showToast(error.message || "页面初始化失败", true);
  });
})();
