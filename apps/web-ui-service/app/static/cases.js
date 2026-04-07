(function () {
  const shell = document.getElementById("cases-shell");
  const api = window.CasesApi;
  const presenter = window.CasesPresenter;
  const tableActions = window.CasesTableActions;
  const treeModule = window.CasesTree;
  const listPage = window.ListPage;
  const support = window.CasesSupport;
  const projectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  if (!shell || !api || !presenter || !tableActions || !treeModule || !listPage || !support || !projectsApi || !projectManager) return;

  const state = {
    items: [],
    lastLoadedAt: null,
    page: 1,
    pageSize: 20,
    pagination: null,
    searchContext: {},
    stats: {},
    selectedIds: new Set(),
    treeItems: [],
    treeSelection: { product_line: "", module: "" },
    reviewMode: window.location.pathname.includes("/cases/review"),
  };
  const storageKey = "cases_filters_v5";
  const els = {
    btnArchive: document.getElementById("btn-archive"),
    btnBatchDelete: document.getElementById("btn-batch-delete"),
    btnBatchRun: document.getElementById("btn-batch-run"),
    btnClearSelection: document.getElementById("btn-clear-selection"),
    btnCreateProject: document.getElementById("btn-create-project"),
    btnExport: document.getElementById("btn-export"),
    btnNewCase: document.getElementById("btn-new-case"),
    btnPurgeDdt: document.getElementById("btn-purge-ddt"),
    btnSearch: document.getElementById("btn-search"),
    btnRefresh: document.getElementById("btn-refresh"),
    btnResetFilters: document.getElementById("btn-reset-filters"),
    btnTags: document.getElementById("btn-tags"),
    btnTreeClear: document.getElementById("btn-tree-clear"),
    btnTreeCollapse: document.getElementById("btn-tree-collapse"),
    btnTreeDelete: document.getElementById("btn-tree-delete"),
    btnTreeEdit: document.getElementById("btn-tree-edit"),
    btnTreeExpand: document.getElementById("btn-tree-expand"),
    btnTreeAdd: document.getElementById("btn-tree-add"),
    checkAll: document.getElementById("check-all"),
    filterCreator: document.getElementById("filter-creator"),
    filterLastResult: document.getElementById("filter-last-result"),
    filterModule: document.getElementById("filter-module"),
    filterPriority: document.getElementById("filter-priority"),
    filterProductLine: document.getElementById("filter-product-line"),
    filterProjectCode: document.getElementById("filter-project-code"),
    filterSource: document.getElementById("filter-source"),
    filterStatus: document.getElementById("filter-status"),
    footerSummary: document.getElementById("cases-visible-summary"),
    lastUpdated: document.getElementById("cases-last-updated"),
    pagination: document.getElementById("cases-pagination"),
    quickFilters: document.getElementById("cases-quick-filters"),
    searchContext: document.getElementById("cases-search-context"),
    searchInput: document.getElementById("search-input"),
    searchClear: document.getElementById("cases-search-clear"),
    statusColTitle: document.getElementById("cases-status-col-title"),
    resultColTitle: document.getElementById("cases-result-col-title"),
    statTotal: document.getElementById("cases-stat-total"),
    statAutomationRate: document.getElementById("cases-stat-automation-rate"),
    statPassRate: document.getElementById("cases-stat-pass-rate"),
    statFailed: document.getElementById("cases-stat-failed"),
    selectedCount: document.getElementById("cases-selected-count"),
    selectionBar: document.getElementById("cases-selection-bar"),
    sortDir: document.getElementById("cases-sort-dir"),
    sortKey: document.getElementById("cases-sort-key"),
    tableBody: document.getElementById("cases-table-body"),
    tree: document.getElementById("cases-tree"),
    treeTotal: document.getElementById("cases-tree-total"),
  };
  const requiredElements = [
    "btnArchive",
    "btnBatchDelete",
    "btnBatchRun",
    "btnClearSelection",
    "btnCreateProject",
    "btnExport",
    "btnNewCase",
    "btnPurgeDdt",
    "btnRefresh",
    "btnResetFilters",
    "btnSearch",
    "btnTags",
    "btnTreeClear",
    "btnTreeCollapse",
    "btnTreeDelete",
    "btnTreeEdit",
    "btnTreeExpand",
    "btnTreeAdd",
    "checkAll",
    "filterCreator",
    "filterLastResult",
    "filterModule",
    "filterPriority",
    "filterProductLine",
    "filterProjectCode",
    "filterSource",
    "filterStatus",
    "footerSummary",
    "lastUpdated",
    "pagination",
    "quickFilters",
    "searchContext",
    "searchInput",
    "searchClear",
    "statusColTitle",
    "resultColTitle",
    "statTotal",
    "statAutomationRate",
    "statPassRate",
    "statFailed",
    "selectedCount",
    "selectionBar",
    "sortDir",
    "sortKey",
    "tableBody",
    "tree",
    "treeTotal",
  ];
  const missingElements = requiredElements.filter((key) => !els[key]);
  if (missingElements.length) {
    console.error("[cases] missing required DOM nodes:", missingElements.join(", "));
    return;
  }
  const treeController = treeModule.createCasesTree({
    els,
    state,
    onSelectionChange: applyTreeSelection,
  });

  function formatDateTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "-");
  }

  function clearSelection() {
    state.selectedIds.clear();
    syncCheckAll();
  }

  function syncTreeSelectionFromFilters() {
    support.syncTreeSelectionFromFilters(els, state);
  }

  function updateSelectionBar() {
    const count = state.selectedIds.size;
    els.selectedCount.textContent = String(count);
    els.selectionBar.classList.toggle("hidden", count === 0);
  }

  function syncCheckAll() {
    const visibleIds = state.items.map((item) => item.id);
    els.checkAll.checked = visibleIds.length > 0 && visibleIds.every((id) => state.selectedIds.has(id));
    updateSelectionBar();
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState !== "function") return;
    window.platformWriteFilterState(storageKey, support.filterFieldNodes(els));
  }

  function renderTable() {
    els.tableBody.innerHTML = presenter.tableRowsMarkup(state.items, state.selectedIds, { reviewMode: state.reviewMode });
    syncCheckAll();
  }

  function renderLoading() {
    els.tableBody.innerHTML = presenter.tableLoadingMarkup();
  }

  function renderPagination() {
    if (typeof window.Pagination !== "function") return;
    const pagination = state.pagination || { page: 1, page_size: 20, total_items: 0 };
    const totalItems = Number(pagination.total_items) || 0;
    const pageSize = Number(pagination.page_size) || 20;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    if (totalPages <= 1) {
      els.pagination.innerHTML = "";
      return;
    }
    new window.Pagination("#cases-pagination", {
      onChange: (page, pageSize) => {
        state.page = page;
        state.pageSize = pageSize;
        clearSelection();
        loadList().catch((error) => window.alert(error.message || "加载失败"));
      },
      page: pagination.page || 1,
      page_size: pagination.page_size || 20,
      page_size_options: [10, 20, 50],
      show_quick_jumper: false,
      show_total: false,
      total_items: pagination.total_items || 0,
    });
  }

  function currentUsername() {
    if (window.platformAuth && typeof window.platformAuth.getCurrentUser === "function") {
      const user = window.platformAuth.getCurrentUser();
      const username = String(user && (user.username || user.name) || "").trim();
      if (username) return username;
    }
    return "admin";
  }

  function detectQuickPreset() {
    const creator = String(els.filterCreator.value || "").trim();
    const lastResult = String(els.filterLastResult.value || "").trim().toLowerCase();
    const priority = String(els.filterPriority.value || "").trim().toUpperCase();
    const source = String(els.filterSource.value || "").trim().toLowerCase();
    const status = String(els.filterStatus.value || "").trim().toLowerCase();
    const isCustomExtra = Boolean(String(els.searchInput.value || "").trim()) || Boolean(status);
    if (!creator && !lastResult && !priority && !source && !isCustomExtra) return "all";
    if (source === "ai" && !creator && !lastResult && !priority && !isCustomExtra) return "ai";
    if (source === "imp" && !creator && !lastResult && !priority && !isCustomExtra) return "imp";
    if (creator && creator === currentUsername() && !source && !lastResult && !priority && !isCustomExtra) return "mine";
    if (lastResult === "failed" && !creator && !source && !priority && !isCustomExtra) return "failed";
    if (status === "inactive" && !creator && !lastResult && !priority && !source && !Boolean(String(els.searchInput.value || "").trim())) {
      return "review";
    }
    if (priority === "P0,P1" && !creator && !lastResult && !source && !isCustomExtra) return "critical";
    return "";
  }

  function applyQuickPreset(preset) {
    const normalizedPreset = String(preset || "").trim().toLowerCase();
    const me = currentUsername();
    els.filterCreator.value = "";
    els.filterLastResult.value = "";
    els.filterPriority.value = "";
    els.filterSource.value = "";
    els.filterStatus.value = "";
    if (normalizedPreset === "mine") {
      els.filterCreator.value = me;
    } else if (normalizedPreset === "failed") {
      els.filterLastResult.value = "failed";
    } else if (normalizedPreset === "review") {
      els.filterStatus.value = "inactive";
    } else if (normalizedPreset === "critical") {
      els.filterPriority.value = "P0,P1";
    } else if (normalizedPreset === "ai") {
      els.filterSource.value = "ai";
    } else if (normalizedPreset === "imp") {
      els.filterSource.value = "imp";
    }
  }

  function syncQuickFilters() {
    const activePreset = detectQuickPreset();
    const buttons = Array.from(els.quickFilters.querySelectorAll("[data-quick-preset]"));
    buttons.forEach((button) => {
      const preset = String(button.dataset.quickPreset || "").trim().toLowerCase();
      button.classList.toggle("is-active", preset === activePreset);
    });
  }

  function renderSearchContext() {
    const markup = presenter.searchContextMarkup(state.searchContext);
    els.searchContext.innerHTML = markup;
    els.searchContext.hidden = !markup;
  }

  function renderStats() {
    const stats = state.stats && typeof state.stats === "object" ? state.stats : {};
    const total = Number(stats.total || 0);
    const passed = Number(stats.passed || 0);
    const failed = Number(stats.failed || 0);
    const automated = Number(stats.automated || 0);
    const passRateRaw = Number.isFinite(Number(stats.pass_rate)) ? Number(stats.pass_rate) : (total ? (passed / total) * 100 : 0);
    const automationRateRaw = Number.isFinite(Number(stats.automation_rate)) ? Number(stats.automation_rate) : (total ? (automated / total) * 100 : 0);
    els.statTotal.textContent = String(total);
    els.statFailed.textContent = String(failed);
    els.statPassRate.textContent = `${passRateRaw.toFixed(1)}%`;
    els.statAutomationRate.textContent = `${automationRateRaw.toFixed(1)}%`;
  }

  function resetFilters() {
    els.searchInput.value = "";
    els.searchInput.dispatchEvent(new Event("input", { bubbles: true }));
    els.filterProjectCode.value = "";
    els.filterCreator.value = "";
    els.filterLastResult.value = "";
    els.filterPriority.value = "";
    els.filterSource.value = "";
    els.filterStatus.value = "";
    els.filterProductLine.value = "";
    els.filterModule.value = "";
    els.sortKey.value = "updated_at";
    els.sortDir.value = "desc";
    syncTreeSelectionFromFilters();
    syncQuickFilters();
    state.page = 1;
    clearSelection();
  }

  async function loadTree() {
    const payload = await api.tree(support.treeParams(els));
    state.treeItems = Array.isArray(payload.items) ? payload.items : [];
    treeController.render();
  }

  function fillProjectOptions(items, selectedValue) {
    const options = ['<option value="">全部项目</option>'].concat(
      (Array.isArray(items) ? items : []).map((item) => {
        const projectCode = String(item.project_code || "").trim();
        const projectName = String(item.project_name || projectCode).trim();
        return `<option value="${projectCode}">${projectCode} · ${projectName}</option>`;
      })
    );
    els.filterProjectCode.innerHTML = options.join("");
    els.filterProjectCode.value = selectedValue || "";
    if (window.CasesDialog && typeof window.CasesDialog.setProjectOptions === "function") {
      window.CasesDialog.setProjectOptions(items);
    }
  }

  async function loadProjects(selectedValue) {
    const payload = await projectsApi.list();
    fillProjectOptions(payload.items || [], selectedValue);
  }

  function openProjectManager() {
    projectManager.open({
      selectedProjectCode: String(els.filterProjectCode.value || "atp").trim() || "atp",
      onChanged: async ({ action, project_code: projectCode }) => {
        const selectedProjectCode = action === "delete" ? "" : String(projectCode || "").trim().toLowerCase();
        await loadProjects(selectedProjectCode);
        state.page = 1;
        clearSelection();
        await loadList();
      },
    });
  }

  async function loadList() {
    persistFilters();
    renderLoading();
    clearSelection();
    const [payload, treePayload] = await Promise.all([
      api.list(support.params(els, state)),
      api.tree(support.treeParams(els)),
    ]);
    state.treeItems = Array.isArray(treePayload.items) ? treePayload.items : [];
    state.items = payload.items || [];
    state.pagination = payload.pagination || null;
    state.searchContext = payload.search_context || {};
    state.stats = payload.stats || {};
    state.lastLoadedAt = new Date().toISOString();
    syncTreeSelectionFromFilters();
    syncQuickFilters();
    treeController.render();
    renderStats();
    renderSearchContext();
    renderTable();
    renderPagination();
    support.updateFooterMeta(els, state, formatDateTime);
  }

  function applyTreeSelection(productLine, module) {
    els.filterProductLine.value = productLine || "";
    els.filterModule.value = module || "";
    syncTreeSelectionFromFilters();
    state.page = 1;
    clearSelection();
    loadList().catch((error) => window.alert(error.message || "加载失败"));
  }

  function bindSelection() {
    els.checkAll.addEventListener("change", () => {
      state.items.forEach((item) => {
        if (els.checkAll.checked) state.selectedIds.add(item.id);
        else state.selectedIds.delete(item.id);
      });
      renderTable();
    });
  }

  function bindActions() {
    els.btnNewCase.addEventListener("click", () => window.CasesDialog && window.CasesDialog.openDialog());
    els.btnSearch.addEventListener("click", () => {
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "搜索失败"));
    });
    els.btnRefresh.addEventListener("click", () => loadList().catch((error) => window.alert(error.message || "重新加载失败")));
    els.btnPurgeDdt.addEventListener("click", async () => {
      const confirmed = window.confirm("将删除系统内全部 DDT 用例及其关联资产，且不可恢复。是否继续？");
      if (!confirmed) return;
      const originalText = els.btnPurgeDdt.textContent;
      els.btnPurgeDdt.disabled = true;
      els.btnPurgeDdt.textContent = "清理中...";
      try {
        const payload = await api.purgeDdtCases();
        const deletedCount = Number(payload.deleted_count || 0);
        window.alert(`DDT 用例清理完成，已删除 ${deletedCount} 条。`);
        state.page = 1;
        clearSelection();
        await loadList();
      } catch (error) {
        window.alert(error.message || "清理 DDT 用例失败");
      } finally {
        els.btnPurgeDdt.disabled = false;
        els.btnPurgeDdt.textContent = originalText || "清理DDT用例";
      }
    });
    els.btnResetFilters.addEventListener("click", () => {
      resetFilters();
      loadList().catch((error) => window.alert(error.message || "重置失败"));
    });
    els.filterProjectCode.addEventListener("change", () => {
      els.filterProductLine.value = "";
      els.filterModule.value = "";
      syncTreeSelectionFromFilters();
      treeController.render();
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "切换项目失败"));
    });
    els.quickFilters.addEventListener("click", (event) => {
      const trigger = event.target instanceof Element ? event.target.closest("[data-quick-preset]") : null;
      if (!trigger) return;
      const quickPreset = String(trigger.dataset.quickPreset || "").trim().toLowerCase();
      const currentPreset = detectQuickPreset();
      if (currentPreset === quickPreset) return;
      applyQuickPreset(quickPreset);
      syncQuickFilters();
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "切换筛选失败"));
    });
    els.btnCreateProject.addEventListener("click", () => {
      try {
        openProjectManager();
      } catch (error) {
        window.alert(error.message || "打开项目管理失败");
      }
    });
    els.btnTreeAdd.addEventListener("click", async () => {
      const projectCode = String(els.filterProjectCode.value || "atp").trim() || "atp";
      const selectedProductLine = String(state.treeSelection.product_line || "").trim();
      const selectedModule = String(state.treeSelection.module || "").trim();
      const defaultProductLine = selectedProductLine || "";
      const targetProductLine = (window.prompt("产品线名称", defaultProductLine) || "").trim();
      if (!targetProductLine) return;
      const defaultModule = selectedModule ? "" : "";
      const targetModule = (window.prompt("模块名称（可留空，仅新增产品线节点）", defaultModule) || "").trim();
      try {
        await api.treeCreate({
          project_code: projectCode,
          product_line: targetProductLine,
          module: targetModule,
        });
        await loadTree();
      } catch (error) {
        window.alert(error.message || "新增节点失败");
      } finally {
        document.getElementById("cases-tree-ops").open = false;
      }
    });
    els.btnTreeEdit.addEventListener("click", async () => {
      const projectCode = String(els.filterProjectCode.value || "atp").trim() || "atp";
      const selectedProductLine = String(state.treeSelection.product_line || "").trim();
      const selectedModule = String(state.treeSelection.module || "").trim();
      if (!selectedProductLine) {
        window.alert("请先在模块树中选择一个产品线或模块节点。");
        return;
      }
      const nextProductLine = (window.prompt("新的产品线名称", selectedProductLine) || "").trim();
      if (!nextProductLine) return;
      const nextModule = selectedModule
        ? (window.prompt("新的模块名称（可留空表示移动到产品线根节点）", selectedModule) || "").trim()
        : "";
      try {
        await api.treeUpdate({
          project_code: projectCode,
          product_line: selectedProductLine,
          module: selectedModule,
          new_product_line: nextProductLine,
          new_module: nextModule,
        });
        if (selectedModule) {
          state.treeSelection = { product_line: nextProductLine, module: nextModule };
          els.filterProductLine.value = nextProductLine;
          els.filterModule.value = nextModule;
        } else {
          state.treeSelection = { product_line: nextProductLine, module: "" };
          els.filterProductLine.value = nextProductLine;
          els.filterModule.value = "";
        }
        state.page = 1;
        clearSelection();
        await loadList();
      } catch (error) {
        window.alert(error.message || "编辑节点失败");
      } finally {
        document.getElementById("cases-tree-ops").open = false;
      }
    });
    els.btnTreeDelete.addEventListener("click", async () => {
      const projectCode = String(els.filterProjectCode.value || "atp").trim() || "atp";
      const selectedProductLine = String(state.treeSelection.product_line || "").trim();
      const selectedModule = String(state.treeSelection.module || "").trim();
      if (!selectedProductLine) {
        window.alert("请先在模块树中选择一个产品线或模块节点。");
        return;
      }
      const targetLabel = selectedModule ? `${selectedProductLine} / ${selectedModule}` : selectedProductLine;
      if (!window.confirm(`确认删除节点 ${targetLabel} 吗？`)) return;
      try {
        await api.treeDelete({
          project_code: projectCode,
          product_line: selectedProductLine,
          module: selectedModule,
          cascade_cases: false,
        });
        onTreeNodeDeleted();
      } catch (error) {
        const message = String(error && error.message || "");
        if (message.includes("cascade_cases=true")) {
          const confirmedCascade = window.confirm("该节点下仍有关联用例。是否连同用例一起删除？该操作不可恢复。");
          if (!confirmedCascade) return;
          try {
            await api.treeDelete({
              project_code: projectCode,
              product_line: selectedProductLine,
              module: selectedModule,
              cascade_cases: true,
            });
            onTreeNodeDeleted();
          } catch (cascadeError) {
            window.alert(cascadeError.message || "删除节点失败");
          }
        } else {
          window.alert(message || "删除节点失败");
        }
      } finally {
        document.getElementById("cases-tree-ops").open = false;
      }
    });
    els.searchContext.addEventListener("click", (event) => {
      const clearAllTrigger = event.target.closest("[data-clear-all-context]");
      if (clearAllTrigger) {
        resetFilters();
        loadList().catch((error) => window.alert(error.message || "清空失败"));
        return;
      }
      const trigger = event.target.closest("[data-remove-key]");
      if (!trigger) return;
      const { removeKey } = trigger.dataset;
      support.clearSearchContextKey(els, state, removeKey);
      syncTreeSelectionFromFilters();
      syncQuickFilters();
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "更新筛选失败"));
    });
  }

  function onTreeNodeDeleted() {
    els.filterProductLine.value = "";
    els.filterModule.value = "";
    state.treeSelection = { product_line: "", module: "" };
    state.page = 1;
    clearSelection();
    loadList().catch((error) => window.alert(error.message || "删除后刷新失败"));
  }

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, support.filterFieldNodes(els));
  }
  if (state.reviewMode) {
    const hasExplicitFilter =
      Boolean(String(els.filterSource.value || "").trim()) ||
      Boolean(String(els.filterStatus.value || "").trim()) ||
      Boolean(String(els.searchInput.value || "").trim());
    if (!hasExplicitFilter) {
      els.filterStatus.value = "inactive";
    }
    els.statusColTitle.textContent = "审核状态";
    els.resultColTitle.textContent = "执行状态";
  }

  listPage.mountSearchField({
    input: els.searchInput,
    clearButton: els.searchClear,
    searchButton: els.btnSearch,
    onSearch: () => {
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "搜索失败"));
    },
  });
  listPage.bindSortHeaders({
    container: shell,
    keyInput: els.sortKey,
    dirInput: els.sortDir,
    onChange: () => {
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "排序失败"));
    },
  });
  syncTreeSelectionFromFilters();
  syncQuickFilters();
  support.updateFooterMeta(els, state, formatDateTime);
  renderSearchContext();
  bindSelection();
  treeController.bind();
  tableActions.bindTableActions({
    api,
    clearSelection,
    els,
    loadList,
    renderTable,
    reviewMode: state.reviewMode,
    state,
    syncCheckAll,
  });
  bindActions();
  window.addEventListener("cases:reload", () => {
    loadList().catch((error) => window.alert(error.message || "加载失败"));
  });
  Promise.all([loadProjects(String(els.filterProjectCode?.value || "")), loadList()])
    .catch((error) => window.alert(error.message || "加载失败"));
})();
