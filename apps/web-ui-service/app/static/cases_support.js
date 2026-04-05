(function () {
  function params(els, state) {
    return {
      module: els.filterModule.value,
      page: state.page,
      page_size: state.pageSize,
      product_line: els.filterProductLine.value,
      q: els.searchInput.value.trim(),
      sort_field: els.sortKey.value || "updated_at",
      sort_order: els.sortDir.value || "desc",
    };
  }

  function normalizeStatusSearchValue(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "active") return "启用";
    if (normalized === "inactive") return "停用";
    if (normalized === "deprecated") return "已废弃";
    return String(value || "").trim();
  }

  function normalizeResultSearchValue(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "passed") return "通过";
    if (normalized === "failed") return "失败";
    if (normalized === "skipped") return "跳过";
    if (normalized === "unknown") return "未知";
    return String(value || "").trim();
  }

  function formatSearchTokenValue(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    if (/[\s:]/.test(text)) return `"${text.replaceAll('"', '\\"')}"`;
    return text;
  }

  function buildSearchInputFromContext(context) {
    const source = context && typeof context === "object" ? context : {};
    const keyword = String(source.keyword || "").trim();
    const parts = [];
    if (keyword) parts.push(keyword);

    const fieldTokens = [
      ["test_type", "类型", String(source.test_type || "").trim()],
      ["status", "状态", normalizeStatusSearchValue(source.status)],
      ["creator", "创建人", String(source.creator || "").trim()],
      ["last_result", "结果", normalizeResultSearchValue(source.last_result)],
    ];

    fieldTokens.forEach(([, label, rawValue]) => {
      const value = formatSearchTokenValue(rawValue);
      if (value) parts.push(`${label}:${value}`);
    });

    return parts.join(" ").trim();
  }

  function clearSearchContextKey(els, state, key) {
    const targetKey = String(key || "").trim();
    if (!targetKey) return;
    if (targetKey === "product_line") {
      els.filterProductLine.value = "";
      els.filterModule.value = "";
      return;
    }
    if (targetKey === "module") {
      els.filterModule.value = "";
      return;
    }
    const context = { ...(state.searchContext || {}) };
    context[targetKey] = "";
    els.searchInput.value = buildSearchInputFromContext(context);
    els.searchInput.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function filterFieldNodes(els) {
    return {
      module: els.filterModule,
      product_line: els.filterProductLine,
      q: els.searchInput,
      sort_dir: els.sortDir,
      sort_key: els.sortKey,
    };
  }

  function syncTreeSelectionFromFilters(els, state) {
    state.treeSelection = {
      product_line: els.filterProductLine.value,
      module: els.filterModule.value,
    };
  }

  function updateFooterMeta(els, state, formatDateTime) {
    const total = Number(state.pagination && state.pagination.total_items) || 0;
    const pageCount = state.items.length;
    els.footerSummary.textContent = total ? `当前页 ${pageCount} 条 / 共 ${total} 条` : `当前页 ${pageCount} 条`;
    els.lastUpdated.textContent = state.lastLoadedAt ? `最近刷新：${formatDateTime(state.lastLoadedAt)}` : "最近刷新：未刷新";
  }

  window.CasesSupport = {
    buildSearchInputFromContext,
    clearSearchContextKey,
    filterFieldNodes,
    params,
    syncTreeSelectionFromFilters,
    updateFooterMeta,
  };
})();
