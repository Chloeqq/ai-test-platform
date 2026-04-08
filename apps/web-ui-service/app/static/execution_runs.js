(function () {
  const shell = document.getElementById("execution-runs-shell");
  const presenter = window.ExecutionRunsPresenter;
  const listPage = window.ListPage;
  const support = window.ExecutionRunsSupport;
  const projectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  const projectSelectorSupport = window.ProjectSelectorSupport;
  if (!shell || !presenter || !listPage || !support) return;

  const els = {
    totalTasks: document.getElementById("er-total-tasks"),
    queueRunning: document.getElementById("er-queue-running"),
    strictReady: document.getElementById("er-strict-ready"),
    governancePriority: document.getElementById("er-governance-priority"),
    keyword: document.getElementById("er-filter-keyword"),
    search: document.getElementById("er-search"),
    searchClear: document.getElementById("er-search-clear"),
    project: document.getElementById("er-filter-project"),
    status: document.getElementById("er-filter-status"),
    queue: document.getElementById("er-filter-queue"),
    source: document.getElementById("er-filter-source"),
    sortKey: document.getElementById("er-sort-key"),
    sortDir: document.getElementById("er-sort-dir"),
    evidence: document.getElementById("er-filter-evidence"),
    strict: document.getElementById("er-filter-strict"),
    retry: document.getElementById("er-filter-retry"),
    dependency: document.getElementById("er-filter-dependency"),
    advanced: document.getElementById("er-advanced-filters"),
    applyFilters: document.getElementById("er-apply-filters"),
    manageProject: document.getElementById("er-manage-project"),
    refresh: document.getElementById("er-refresh"),
    reset: document.getElementById("er-reset"),
    filterSummary: document.getElementById("er-filter-summary"),
    projectNote: document.getElementById("er-project-note"),
    lastUpdated: document.getElementById("er-last-updated"),
    selectionBar: document.getElementById("er-selection-bar"),
    selectionCopy: document.getElementById("er-selection-copy"),
    copyRuns: document.getElementById("er-copy-runs"),
    copyCases: document.getElementById("er-copy-cases"),
    checkAll: document.getElementById("er-check-all"),
    tbody: document.getElementById("er-tbody"),
    footer: document.getElementById("er-footer"),
    detailPanel: document.getElementById("er-detail-panel"),
  };

  const state = {
    items: [],
    selectedTaskId: "",
    selectedIds: new Set(),
    page: 1,
    pageSize: 20,
    summary: {},
    projectItems: [],
  };
  const storageKey = "execution_runs_filters_v1";

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function badge(value) {
    if (typeof window.platformRenderBadge === "function") return window.platformRenderBadge(value, "unknown");
    const text = String(value || "unknown").trim() || "unknown";
    const cls = text.toLowerCase().replaceAll(/[^a-z0-9_]+/g, "_");
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function displayRunId(value) {
    if (typeof window.platformDisplayRunId === "function") return window.platformDisplayRunId(value);
    return String(value || "").trim() || "-";
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
  }

  function updateLastUpdated() {
    if (typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  function selectedProjectCode() {
    if (!projectSelectorSupport) return String(els.project?.value || "").trim().toLowerCase();
    return projectSelectorSupport.normalizeCode(els.project?.value || "");
  }

  function syncProjectGovernanceNote() {
    if (!els.projectNote) return;
    const currentProjectCode = selectedProjectCode();
    if (!currentProjectCode) {
      els.projectNote.textContent = "";
      return;
    }
    const currentProject = state.projectItems.find((item) => {
      return projectSelectorSupport
        ? projectSelectorSupport.normalizeCode(item.project_code) === currentProjectCode
        : String(item.project_code || "").trim().toLowerCase() === currentProjectCode;
    });
    const projectStatus = String(currentProject?.status || "active").trim().toLowerCase() || "active";
    els.projectNote.textContent = projectStatus === "inactive"
      ? "当前筛选项目为 inactive，本页仍允许查看执行任务；如需回到生成、保存或审核写入口，请先恢复项目为 active。"
      : "";
  }

  function setProjectOptions(items, selectedValue) {
    if (!projectSelectorSupport || !els.project) return;
    state.projectItems = Array.isArray(items) ? items : [];
    projectSelectorSupport.applyProjectOptions(els.project, state.projectItems, {
      selectedValue: selectedValue != null ? selectedValue : (els.project.value || ""),
      defaultProjectCode: "atp",
      emptyOptionLabel: "全部项目",
    });
    syncProjectGovernanceNote();
  }

  async function loadProjects(selectedValue) {
    if (!projectsApi || !projectSelectorSupport || !els.project) return;
    const items = await projectSelectorSupport.loadProjectOptions({
      projectsApi,
      selectEl: els.project,
      selectedValue: selectedValue != null ? selectedValue : (els.project.value || ""),
      defaultProjectCode: "atp",
      emptyOptionLabel: "全部项目",
    });
    state.projectItems = Array.isArray(items) ? items : [];
    syncProjectGovernanceNote();
  }

  function openProjectManager() {
    if (!projectSelectorSupport || !projectManager || !projectsApi || !els.project) return;
    projectSelectorSupport.openProjectManager({
      projectManager,
      projectsApi,
      selectEl: els.project,
      selectedProjectCode: selectedProjectCode(),
      defaultProjectCode: "atp",
      deleteFallbackValue: "",
      emptyOptionLabel: "全部项目",
      onChanged: async ({ items, selectedProjectCode }) => {
        setProjectOptions(items, selectedProjectCode || "");
        state.page = 1;
        await load().catch(() => {});
      },
    });
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, {
        keyword: els.keyword,
        project: els.project,
        status: els.status,
        queue: els.queue,
        source: els.source,
        sort_key: els.sortKey,
        sort_dir: els.sortDir,
        evidence: els.evidence,
        strict: els.strict,
        retry: els.retry,
        dependency: els.dependency,
      });
    }
    if (els.advanced) {
      els.advanced.open = Boolean(els.evidence.value || els.strict.value || els.retry.value || els.dependency.value);
    }
  }

  function filteredItems() {
    return support.filterAndSortItems(state.items, support.currentFilters(els), listPage);
  }

  function updateSelectionBar() {
    const count = state.selectedIds.size;
    els.selectionBar.hidden = count === 0;
    els.selectionCopy.textContent = `已选择 ${count} 项`;
  }

  function renderTable() {
    const summary = state.summary || {};
    const items = filteredItems();
    els.filterSummary.textContent = support.filterSummary(support.currentFilters(els), items.length);

    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(items, state.page, state.pageSize)
      : { items, page: 1, pageSize: items.length || 20, totalItems: items.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    els.totalTasks.textContent = String(summary.total_tasks || items.length || 0);
    els.queueRunning.textContent = `${summary.queue_status_counts?.queued || 0} / ${summary.queue_status_counts?.running || 0}`;
    els.strictReady.textContent = `${summary.strict_mode_ready_task_count || 0}`;
    els.governancePriority.innerHTML = badge(summary.governance_risk_priority || "none");

    if (!pager.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="8" class="empty-state">当前筛选条件下没有执行任务。</td></tr>';
      els.detailPanel.innerHTML = presenter.renderDetail(null, { badge, displayCaseId, displayRunId, formatTime });
    } else {
      if (!state.selectedTaskId || !pager.items.some((item) => String(item.task_id) === state.selectedTaskId)) {
        state.selectedTaskId = String(pager.items[0].task_id || "");
      }
      els.tbody.innerHTML = pager.items.map((item) => presenter.renderRow(item, state.selectedTaskId, state.selectedIds, {
        badge,
        displayCaseId,
        displayRunId,
        formatTime,
      })).join("");
      els.detailPanel.innerHTML = presenter.renderDetail(
        items.find((item) => String(item.task_id) === state.selectedTaskId) || pager.items[0],
        { badge, displayCaseId, displayRunId, formatTime },
      );
    }

    if (typeof window.Pagination === "function") {
      new window.Pagination("#er-footer", {
        page: pager.page,
        page_size: pager.pageSize,
        total_items: pager.totalItems,
        page_size_options: [10, 20, 50, 100],
        show_total: true,
        onChange: (nextPage, nextPageSize) => {
          state.page = nextPage;
          state.pageSize = nextPageSize;
          renderTable(summary);
        },
      });
    }

    els.tbody.querySelectorAll(".er-check").forEach((checkbox) => {
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const id = String(checkbox.dataset.taskId || "");
        if (!id) return;
        if (checkbox.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        updateSelectionBar();
      });
    });
    els.tbody.querySelectorAll("tr[data-task-id]").forEach((row) => {
      row.addEventListener("click", () => {
        state.selectedTaskId = String(row.dataset.taskId || "");
        renderTable(summary);
      });
    });
    const pageIds = pager.items.map((item) => String(item.task_id || "")).filter(Boolean);
    els.checkAll.checked = pageIds.length > 0 && pageIds.every((id) => state.selectedIds.has(id));
    updateSelectionBar();
    updateLastUpdated();
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="8" class="loading-state">正在加载执行任务...</td></tr>';
    const params = support.buildTaskParams(els);
    const response = await fetch(`/api/workbench/tasks?${params.toString()}`, { cache: "no-store" });
    const payload = response.ok ? await response.json() : { items: [], summary: {} };
    state.items = Array.isArray(payload.items) ? payload.items : [];
    support.populateFilterOptions(state.items, els);
    state.summary = payload.summary || {};
    renderTable();
  }

  async function copySelection(kind) {
    const values = state.items
      .filter((item) => state.selectedIds.has(String(item.task_id)))
      .map((item) => String(kind === "case" ? item.case_id || "" : item.run_id || item.task_id || "").trim())
      .filter(Boolean)
      .join("\n");
    if (!values) return;
    try {
      await navigator.clipboard.writeText(values);
      els.selectionCopy.textContent = `已复制 ${state.selectedIds.size} 项`;
    } catch (_error) {
      els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedIds.size} 项`;
    }
  }

  [els.project, els.status, els.queue, els.source, els.evidence, els.strict, els.retry, els.dependency].forEach((node) => {
    node.addEventListener("change", () => {
      syncProjectGovernanceNote();
      persistFilters();
    });
  });
  listPage.mountSearchField({
    input: els.keyword,
    clearButton: els.searchClear,
    searchButton: els.search,
    onSearch: () => {
      state.page = 1;
      persistFilters();
      load().catch((error) => {
        els.tbody.innerHTML = `<tr><td colspan="9" class="error-state">${escapeHtml(error.message || "加载失败")}</td></tr>`;
      });
    },
  });
  listPage.bindSortHeaders({
    container: shell,
    keyInput: els.sortKey,
    dirInput: els.sortDir,
    onChange: () => {
      state.page = 1;
      persistFilters();
      renderTable();
    },
  });
  els.checkAll.addEventListener("change", () => {
    const pageIds = Array.from(els.tbody.querySelectorAll(".er-check")).map((node) => String(node.dataset.taskId || "")).filter(Boolean);
    pageIds.forEach((id) => {
      if (els.checkAll.checked) state.selectedIds.add(id);
      else state.selectedIds.delete(id);
    });
    updateSelectionBar();
    renderTable();
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    load().catch(() => {});
  });
  if (els.manageProject) {
    els.manageProject.addEventListener("click", () => openProjectManager());
  }
  els.refresh.addEventListener("click", () => load().catch(() => {}));
  els.reset.addEventListener("click", () => {
    [els.keyword, els.project, els.status, els.queue, els.source, els.evidence, els.strict, els.retry, els.dependency].forEach((node) => { node.value = ""; });
    els.sortKey.value = "finished_at";
    els.sortDir.value = "desc";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advanced) els.advanced.open = false;
    syncProjectGovernanceNote();
    load().catch(() => {});
  });
  els.copyRuns.addEventListener("click", () => copySelection("run"));
  els.copyCases.addEventListener("click", () => copySelection("case"));

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, {
      keyword: els.keyword,
      project: els.project,
      status: els.status,
      queue: els.queue,
      source: els.source,
      sort_key: els.sortKey,
      sort_dir: els.sortDir,
      evidence: els.evidence,
      strict: els.strict,
      retry: els.retry,
      dependency: els.dependency,
    });
  }
  persistFilters();
  loadProjects(String(els.project?.value || "").trim())
    .catch(() => {
      syncProjectGovernanceNote();
    })
    .finally(() => {
      load().catch((error) => {
        els.tbody.innerHTML = `<tr><td colspan="8" class="error-state">${escapeHtml(error.message || "加载执行任务失败")}</td></tr>`;
      });
    });
})();
