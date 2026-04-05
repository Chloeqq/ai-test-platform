(function () {
  function fieldValue(node) {
    return node ? String(node.value || "").trim() : "";
  }

  function parseKeywordKeyword(keyword) {
    return String(keyword || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function filterFieldNodes(els) {
    return {
      q: els.searchInput,
      product_line: els.filterProductLine,
      module: els.filterModule,
      sort_field: els.sortKey,
      sort_order: els.sortDir,
    };
  }

  function syncTreeSelectionFromFilters(els, state) {
    state.treeSelection = {
      product_line: fieldValue(els.filterProductLine),
      module: fieldValue(els.filterModule),
    };
  }

  function params(els, state) {
    return {
      q: parseKeywordKeyword(fieldValue(els.searchInput)),
      product_line: fieldValue(els.filterProductLine),
      module: fieldValue(els.filterModule),
      sort_field: fieldValue(els.sortKey) || "updated_at",
      sort_order: fieldValue(els.sortDir) || "desc",
      page: state.page || 1,
      page_size: state.pageSize || 20,
    };
  }

  function updateFooterMeta(els, state, formatDateTime) {
    const items = Array.isArray(state.items) ? state.items : [];
    const pagination = state.pagination || {};
    const totalItems = Number(pagination.total_items || items.length || 0);
    const page = Number(pagination.page || state.page || 1);
    if (els.footerSummary) {
      els.footerSummary.textContent = "当前页 " + items.length + " 条 · 全部 " + totalItems + " 条 · 第 " + page + " 页";
    }
    if (els.lastUpdated) {
      els.lastUpdated.textContent = "最近刷新：" + (state.lastLoadedAt ? formatDateTime(state.lastLoadedAt) : "未刷新");
    }
  }

  function clearSearchContextKey(els, _state, removeKey) {
    const key = String(removeKey || "").trim();
    if (!key) return;
    if (key === "q" && els.searchInput) els.searchInput.value = "";
    if (key === "product_line" && els.filterProductLine) els.filterProductLine.value = "";
    if (key === "module" && els.filterModule) els.filterModule.value = "";
    if (key === "sort_field" && els.sortKey) els.sortKey.value = "updated_at";
    if (key === "sort_order" && els.sortDir) els.sortDir.value = "desc";
  }

  window.CasesSupport = {
    clearSearchContextKey: clearSearchContextKey,
    filterFieldNodes: filterFieldNodes,
    params: params,
    syncTreeSelectionFromFilters: syncTreeSelectionFromFilters,
    updateFooterMeta: updateFooterMeta,
  };
})();
