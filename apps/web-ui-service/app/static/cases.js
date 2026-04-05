(function () {
  const shell = document.getElementById("cases-shell");
  const api = window.CasesApi;
  const presenter = window.CasesPresenter;
  const tableActions = window.CasesTableActions;
  const treeModule = window.CasesTree;
  const listPage = window.ListPage;
  const support = window.CasesSupport;
  if (!shell || !api || !presenter || !tableActions || !treeModule || !listPage || !support) return;

  const state = {
    items: [],
    lastLoadedAt: null,
    page: 1,
    pageSize: 20,
    pagination: null,
    searchContext: {},
    selectedIds: new Set(),
    treeItems: [],
    treeSelection: { product_line: "", module: "" },
  };
  const storageKey = "cases_filters_v5";
  const els = {
    btnArchive: document.getElementById("btn-archive"),
    btnClearSelection: document.getElementById("btn-clear-selection"),
    btnExport: document.getElementById("btn-export"),
    btnNewCase: document.getElementById("btn-new-case"),
    btnSearch: document.getElementById("btn-search"),
    btnRefresh: document.getElementById("btn-refresh"),
    btnResetFilters: document.getElementById("btn-reset-filters"),
    btnTags: document.getElementById("btn-tags"),
    btnTreeClear: document.getElementById("btn-tree-clear"),
    btnTreeCollapse: document.getElementById("btn-tree-collapse"),
    btnTreeExpand: document.getElementById("btn-tree-expand"),
    checkAll: document.getElementById("check-all"),
    filterModule: document.getElementById("filter-module"),
    filterProductLine: document.getElementById("filter-product-line"),
    footerSummary: document.getElementById("cases-visible-summary"),
    lastUpdated: document.getElementById("cases-last-updated"),
    pagination: document.getElementById("cases-pagination"),
    searchContext: document.getElementById("cases-search-context"),
    searchInput: document.getElementById("search-input"),
    searchClear: document.getElementById("cases-search-clear"),
    selectedCount: document.getElementById("cases-selected-count"),
    selectionBar: document.getElementById("cases-selection-bar"),
    sortDir: document.getElementById("cases-sort-dir"),
    sortKey: document.getElementById("cases-sort-key"),
    tableBody: document.getElementById("cases-table-body"),
    tree: document.getElementById("cases-tree"),
    treeTotal: document.getElementById("cases-tree-total"),
  };
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
    els.tableBody.innerHTML = presenter.tableRowsMarkup(state.items, state.selectedIds);
    syncCheckAll();
  }

  function renderLoading() {
    els.tableBody.innerHTML = presenter.tableLoadingMarkup();
  }

  function renderPagination() {
    if (typeof window.Pagination !== "function") return;
    const pagination = state.pagination || { page: 1, page_size: 20, total_items: 0 };
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
      show_total: true,
      total_items: pagination.total_items || 0,
    });
  }

  function renderSearchContext() {
    const markup = presenter.searchContextMarkup(state.searchContext);
    els.searchContext.innerHTML = markup;
    els.searchContext.hidden = !markup;
  }

  function resetFilters() {
    els.searchInput.value = "";
    els.searchInput.dispatchEvent(new Event("input", { bubbles: true }));
    els.filterProductLine.value = "";
    els.filterModule.value = "";
    els.sortKey.value = "updated_at";
    els.sortDir.value = "desc";
    syncTreeSelectionFromFilters();
    state.page = 1;
    clearSelection();
  }

  async function loadTree() {
    const payload = await api.tree();
    state.treeItems = Array.isArray(payload.items) ? payload.items : [];
    treeController.render();
  }

  async function loadList() {
    persistFilters();
    renderLoading();
    clearSelection();
    const payload = await api.list(support.params(els, state));
    state.items = payload.items || [];
    state.pagination = payload.pagination || null;
    state.searchContext = payload.search_context || {};
    state.lastLoadedAt = new Date().toISOString();
    syncTreeSelectionFromFilters();
    treeController.render();
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
    els.btnResetFilters.addEventListener("click", () => {
      resetFilters();
      loadList().catch((error) => window.alert(error.message || "重置失败"));
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
      state.page = 1;
      clearSelection();
      loadList().catch((error) => window.alert(error.message || "更新筛选失败"));
    });
  }

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, support.filterFieldNodes(els));
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
    state,
    syncCheckAll,
  });
  bindActions();
  window.addEventListener("cases:reload", () => {
    Promise.all([loadTree(), loadList()]).catch((error) => window.alert(error.message || "加载失败"));
  });
  Promise.all([loadTree(), loadList()]).catch((error) => window.alert(error.message || "加载失败"));
})();
