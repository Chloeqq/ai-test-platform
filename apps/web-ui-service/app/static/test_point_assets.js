(function () {
  const shell = document.getElementById("tp-assets-shell");
  const presenter = window.TestPointAssetsPresenter;
  const listPage = window.ListPage;
  const createSupport = window.createTestPointAssetsSupport;
  if (!shell || !presenter || !listPage || typeof createSupport !== "function") return;

  const els = {
    total: document.getElementById("tp-assets-total"),
    totalPoints: document.getElementById("tp-points-total"),
    readyAssets: document.getElementById("tp-ready-assets"),
    gapAssets: document.getElementById("tp-gap-assets"),
    tbody: document.getElementById("tp-assets-tbody"),
    selectedPanel: document.getElementById("tp-selected-panel"),
    summaryCoverage: document.getElementById("tp-summary-coverage"),
    summaryCoverageDesc: document.getElementById("tp-summary-coverage-desc"),
    summarySelection: document.getElementById("tp-summary-selection"),
    summarySelectionDesc: document.getElementById("tp-summary-selection-desc"),
    summaryPage: document.getElementById("tp-summary-page"),
    summaryPageDesc: document.getElementById("tp-summary-page-desc"),
    summarySource: document.getElementById("tp-summary-source"),
    summarySourceDesc: document.getElementById("tp-summary-source-desc"),
    refresh: document.getElementById("tp-assets-refresh"),
    applyFilters: document.getElementById("tp-assets-apply-filters"),
    reset: document.getElementById("tp-assets-reset"),
    footer: document.getElementById("tp-assets-footer"),
    selectionBar: document.getElementById("tp-assets-selection-bar"),
    selectionCopy: document.getElementById("tp-assets-selection-copy"),
    copySelection: document.getElementById("tp-assets-copy-selection"),
    checkAll: document.getElementById("tp-assets-check-all"),
    lastUpdated: document.getElementById("tp-assets-last-updated"),
    filterSummary: document.getElementById("tp-assets-filter-summary"),
    filterPage: document.getElementById("tp-filter-page"),
    filterKeyword: document.getElementById("tp-filter-keyword"),
    search: document.getElementById("tp-search"),
    searchClear: document.getElementById("tp-search-clear"),
    filterSourceType: document.getElementById("tp-filter-source-type"),
    filterCoverageStatus: document.getElementById("tp-filter-coverage-status"),
    filterReviewStatus: document.getElementById("tp-filter-review-status"),
    filterGateDecision: document.getElementById("tp-filter-gate-decision"),
    filterSelectionState: document.getElementById("tp-filter-selection-state"),
    sortKey: document.getElementById("tp-sort-key"),
    sortDir: document.getElementById("tp-sort-dir"),
    advancedFilters: document.getElementById("tp-assets-advanced-filters"),
  };

  const state = {
    items: [],
    selectedId: "",
    selectedIds: new Set(),
    page: 1,
    pageSize: 20,
    coverageSummary: {},
  };
  const storageKey = "test_point_assets_filters_v1";
  const filterFields = {
    page: els.filterPage,
    keyword: els.filterKeyword,
    source_type: els.filterSourceType,
    coverage_status: els.filterCoverageStatus,
    review_status: els.filterReviewStatus,
    gate_decision: els.filterGateDecision,
    selection_state: els.filterSelectionState,
    sort_key: els.sortKey,
    sort_dir: els.sortDir,
  };
  const support = createSupport({
    els,
    listPage,
    filterFields,
    storageKey,
    advancedFilterKeys: ["source_type", "coverage_status", "review_status", "gate_decision", "selection_state"],
  });

  function renderTable() {
    const filtered = support.filteredItems(state.items);
    support.updateFilterSummary(filtered);
    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="9" class="empty-state">当前筛选条件下没有测试点资产。</td></tr>';
      els.selectedPanel.innerHTML = presenter.renderSelected(null, { badge: support.badge, displayRunId: support.displayRunId });
    } else {
      const selected = pager.items.find((item) => item.asset_id === state.selectedId)
        || filtered.find((item) => item.asset_id === state.selectedId)
        || pager.items[0];
      state.selectedId = selected.asset_id;
      els.tbody.innerHTML = pager.items.map((item) => presenter.renderRow(item, state.selectedId, state.selectedIds, {
        badge: support.badge,
        displayRunId: support.displayRunId,
      })).join("");
      els.selectedPanel.innerHTML = presenter.renderSelected(selected, {
        badge: support.badge,
        displayRunId: support.displayRunId,
      });
    }

    if (typeof window.platformRenderSimplePagination === "function") {
      window.platformRenderSimplePagination(els.footer, {
        page: pager.page,
        pageSize: pager.pageSize,
        totalItems: pager.totalItems,
        totalPages: pager.totalPages,
      }, (nextPage, nextPageSize) => {
        state.page = nextPage;
        state.pageSize = nextPageSize;
        renderTable();
      });
    }

    const rowChecks = els.tbody.querySelectorAll(".tp-assets-check");
    rowChecks.forEach((checkbox) => {
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const id = String(checkbox.dataset.assetId || "").trim();
        if (!id) return;
        if (checkbox.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        support.updateSelectionBar(state.selectedIds);
      });
    });
    if (els.checkAll) {
      const currentIds = Array.from(rowChecks).map((node) => String(node.dataset.assetId || "").trim()).filter(Boolean);
      els.checkAll.checked = currentIds.length > 0 && currentIds.every((id) => state.selectedIds.has(id));
    }
    support.updateSelectionBar(state.selectedIds);
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="8" class="loading-state">正在加载测试点资产...</td></tr>';
    const [listResp, summaryResp] = await Promise.all([
      fetch("/api/workbench/test-point-assets", { cache: "no-store" }),
      fetch("/api/workbench/test-point-assets/coverage-summary", { cache: "no-store" }),
    ]);
    const listPayload = listResp.ok ? await listResp.json() : { items: [] };
    const summaryPayload = summaryResp.ok ? await summaryResp.json() : { item: {} };
    state.items = Array.isArray(listPayload.items) ? listPayload.items : [];
    state.coverageSummary = summaryPayload.item || {};
    support.renderSummary(state.coverageSummary);
    support.refreshStamp();
    renderTable();
  }

  [els.filterPage, els.filterSourceType, els.filterCoverageStatus, els.filterReviewStatus, els.filterGateDecision, els.filterSelectionState].forEach((node) => {
    node.addEventListener("input", support.persistFilters);
  });

  listPage.mountSearchField({
    input: els.filterKeyword,
    clearButton: els.searchClear,
    searchButton: els.search,
    onSearch: () => {
      state.page = 1;
      support.persistFilters();
      renderTable();
    },
  });
  listPage.bindSortHeaders({
    container: shell,
    keyInput: els.sortKey,
    dirInput: els.sortDir,
    onChange: () => {
      support.persistFilters();
      renderTable();
    },
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    support.persistFilters();
    renderTable();
  });
  els.refresh.addEventListener("click", load);
  els.reset.addEventListener("click", () => {
    [els.filterPage, els.filterKeyword, els.filterSourceType, els.filterCoverageStatus, els.filterReviewStatus, els.filterGateDecision, els.filterSelectionState].forEach((node) => {
      node.value = "";
    });
    els.sortKey.value = "page";
    els.sortDir.value = "asc";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advancedFilters) els.advancedFilters.open = false;
    renderTable();
  });
  els.copySelection.addEventListener("click", async () => {
    const text = Array.from(state.selectedIds).join("\n");
    if (!text) return;
    try {
      const copied = typeof window.platformCopyText === "function"
        ? await window.platformCopyText(text)
        : await navigator.clipboard.writeText(text).then(() => true);
      els.selectionCopy.textContent = copied
        ? `已复制 ${state.selectedIds.size} 个资产 ID`
        : `复制失败，请手动复制 ${state.selectedIds.size} 个资产 ID`;
    } catch (_error) {
      els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedIds.size} 个资产 ID`;
    }
  });
  els.checkAll.addEventListener("change", () => {
    const currentIds = Array.from(els.tbody.querySelectorAll(".tp-assets-check"))
      .map((node) => String(node.dataset.assetId || "").trim())
      .filter(Boolean);
    if (els.checkAll.checked) currentIds.forEach((id) => state.selectedIds.add(id));
    else currentIds.forEach((id) => state.selectedIds.delete(id));
    renderTable();
  });
  els.tbody.addEventListener("click", function (event) {
    const row = event.target.closest("tr[data-asset-id]");
    if (!row) return;
    state.selectedId = row.dataset.assetId || "";
    renderTable();
  });

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  support.persistFilters();
  load().catch((error) => {
    els.tbody.innerHTML = `<tr><td colspan="8" class="error-state">${support.escapeHtml(error.message || "加载测试点资产失败")}</td></tr>`;
  });
})();
