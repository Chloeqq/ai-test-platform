(function () {
  const detailHelper = window.workbenchHistoryDetail;
  const createSupport = window.createWorkbenchHistorySupport;
  const tableRenderer = window.WorkbenchHistoryTable;
  const listPage = window.ListPage || null;
  const shell = document.getElementById("workbench-history-shell");
  if (!shell || !detailHelper || !tableRenderer || typeof createSupport !== "function") return;

  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
  const els = {
    body: document.getElementById("wb-history-body"),
    summaryPanel: document.getElementById("wb-history-summary-panel"),
    detailPanel: document.getElementById("wb-history-detail-panel"),
    authNotice: document.getElementById("wb-history-auth-notice"),
    keywordFilter: document.getElementById("wb-history-keyword"),
    keywordSearch: document.getElementById("wb-history-search"),
    keywordClear: document.getElementById("wb-history-search-clear"),
    actionFilter: document.getElementById("wb-history-action"),
    statusFilter: document.getElementById("wb-history-status"),
    sortKey: document.getElementById("wb-history-sort-key"),
    sortDir: document.getElementById("wb-history-sort-dir"),
    riskGateFilter: document.getElementById("wb-history-risk-gate"),
    selfHealingStatusFilter: document.getElementById("wb-history-self-healing-status"),
    actorFilter: document.getElementById("wb-history-actor"),
    advancedFilters: document.getElementById("wb-history-advanced-filters"),
    applyFiltersBtn: document.getElementById("wb-history-apply-filters"),
    refreshBtn: document.getElementById("wb-history-refresh"),
    resetBtn: document.getElementById("wb-history-reset"),
    lastUpdated: document.getElementById("wb-history-last-updated"),
    filterSummary: document.getElementById("wb-history-filter-summary"),
    selectionBar: document.getElementById("wb-history-selection-bar"),
    selectionCopy: document.getElementById("wb-history-selection-copy"),
    copyRunIdsBtn: document.getElementById("wb-history-copy-run-ids"),
    copyCaseIdsBtn: document.getElementById("wb-history-copy-case-ids"),
    checkAll: document.getElementById("wb-history-check-all"),
    footer: document.getElementById("wb-history-footer"),
    totalKpi: document.getElementById("history-kpi-total"),
    actionKpi: document.getElementById("history-kpi-action"),
    gateKpi: document.getElementById("history-kpi-gate"),
    healingKpi: document.getElementById("history-kpi-healing"),
  };

  const state = {
    items: [],
    selectedKey: "",
    selectedIds: new Set(),
    page: 1,
    pageSize: 20,
    totalPages: 1,
    totalItems: 0,
    summary: {},
  };
  const storageKey = "workbench_history_filters_v3";
  const filterFields = {
    keyword: els.keywordFilter,
    action: els.actionFilter,
    status: els.statusFilter,
    sort_key: els.sortKey,
    sort_dir: els.sortDir,
    risk_gate_decision: els.riskGateFilter,
    self_healing_status: els.selfHealingStatusFilter,
    actor: els.actorFilter,
  };
  const support = createSupport({ els, filterFields, storageKey, detailHelper, listPage });

  function updateHeroKpis(summary) {
    const data = summary && typeof summary === "object" ? summary : {};
    els.totalKpi.textContent = String(data.total_items || 0);
    els.actionKpi.textContent = String(data.top_action?.value || "-");
    els.gateKpi.textContent = String(data.top_risk_gate?.value || "-");
    els.healingKpi.textContent = String(data.top_self_healing_status?.value || "-");
  }

  function updateSelectionBar() {
    const count = state.selectedIds.size;
    els.selectionBar.hidden = count === 0;
    els.selectionCopy.textContent = `已选择 ${count} 项`;
  }

  function renderTable() {
    const rows = support.sortedItems(state.items);
    if (!rows.length) {
      els.body.innerHTML = '<tr><td colspan="9" class="empty-state">当前筛选条件下没有操作历史。</td></tr>';
      els.detailPanel.innerHTML = detailHelper.renderDetailPanel(null);
      els.checkAll.checked = false;
      updateSelectionBar();
      return;
    }

    const selectedItem = rows.find((item) => detailHelper.rowKey(item) === state.selectedKey) || rows[0];
    state.selectedKey = detailHelper.rowKey(selectedItem);
    els.body.innerHTML = tableRenderer.renderRows(rows, state.selectedKey, state.selectedIds, detailHelper);
    els.detailPanel.innerHTML = detailHelper.renderDetailPanel(selectedItem);

    const currentIds = rows.map((item) => detailHelper.rowKey(item));
    els.checkAll.checked = currentIds.length > 0 && currentIds.every((id) => state.selectedIds.has(id));
    updateSelectionBar();
    els.body.querySelectorAll(".wb-history-check").forEach((checkbox) => {
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const rowId = String(checkbox.dataset.historyRow || "").trim();
        if (!rowId) return;
        if (checkbox.checked) state.selectedIds.add(rowId);
        else state.selectedIds.delete(rowId);
        updateSelectionBar();
      });
    });
  }

  async function loadHistory() {
    const params = new URLSearchParams();
    params.set("limit", "500");
    params.set("page", String(state.page));
    params.set("page_size", String(state.pageSize));
    Object.entries(filterFields).forEach(([key, node]) => {
      const value = String(node?.value || "").trim();
      if (value) params.set(key, value);
    });

    const response = await authFetch(`/api/workbench/history?${params.toString()}`);
    if (!response.ok) throw new Error("操作历史加载失败");
    const payload = await response.json();
    state.items = Array.isArray(payload.items) ? payload.items : [];
    state.summary = payload.summary && typeof payload.summary === "object" ? payload.summary : {};
    state.page = Number(payload.pagination?.page || state.page || 1);
    state.pageSize = Number(payload.pagination?.page_size || state.pageSize || 20);
    state.totalPages = Number(payload.pagination?.total_pages || 1);
    state.totalItems = Number(payload.pagination?.total_items || state.items.length || 0);

    updateHeroKpis(state.summary);
    support.updateFilterSummary(state.totalItems);
    els.summaryPanel.innerHTML = detailHelper.renderSummaryPanel(state.summary);
    renderTable();
    if (typeof window.platformRenderSimplePagination === "function") {
      window.platformRenderSimplePagination(els.footer, {
        page: state.page,
        pageSize: state.pageSize,
        totalItems: state.totalItems,
        totalPages: state.totalPages,
      }, (nextPage, nextPageSize) => {
        state.page = nextPage;
        state.pageSize = nextPageSize;
        loadHistory().catch(handleLoadError);
      });
    }
  }

  function handleLoadError(error) {
    const message = detailHelper.escapeHtml(error?.message || "操作历史加载失败");
    els.body.innerHTML = `<tr><td colspan="9" class="error-state">${message}</td></tr>`;
    els.summaryPanel.innerHTML = `<div class="error-state">${message}</div>`;
    els.detailPanel.innerHTML = `<div class="error-state">${message}</div>`;
    els.lastUpdated.textContent = "最后刷新：加载失败";
  }

  async function refresh() {
    els.refreshBtn.disabled = true;
    els.refreshBtn.textContent = "刷新中...";
    support.persistFilters();
    support.syncQueryToUrl();
    try {
      await loadHistory();
      support.setRefreshTimestamp();
    } finally {
      els.refreshBtn.disabled = false;
      els.refreshBtn.textContent = "刷新历史";
    }
  }

  function scheduleActorSearch() {
    window.clearTimeout(scheduleActorSearch.timer);
    scheduleActorSearch.timer = window.setTimeout(() => {
      state.page = 1;
      refresh().catch(handleLoadError);
    }, 250);
  }

  function bindEvents() {
    [els.actionFilter, els.statusFilter, els.riskGateFilter].forEach((node) => {
      node.addEventListener("change", () => {
        state.page = 1;
        refresh().catch(handleLoadError);
      });
    });
    els.selfHealingStatusFilter.addEventListener("change", support.persistFilters);
    els.actorFilter.addEventListener("input", scheduleActorSearch);
    els.keywordSearch.addEventListener("click", () => {
      state.page = 1;
      refresh().catch(handleLoadError);
    });
    els.applyFiltersBtn.addEventListener("click", () => {
      state.page = 1;
      refresh().catch(handleLoadError);
    });
    els.refreshBtn.addEventListener("click", () => refresh().catch(handleLoadError));
    els.resetBtn.addEventListener("click", () => {
      support.resetFilters(state);
      refresh().catch(handleLoadError);
    });
    els.checkAll.addEventListener("change", () => {
      const currentIds = state.items.map((item) => detailHelper.rowKey(item));
      if (els.checkAll.checked) currentIds.forEach((id) => state.selectedIds.add(id));
      else currentIds.forEach((id) => state.selectedIds.delete(id));
      renderTable();
    });
    els.copyRunIdsBtn.addEventListener("click", async () => {
      const text = state.items.filter((item) => state.selectedIds.has(detailHelper.rowKey(item))).map((item) => String(item.run_id || "").trim()).filter(Boolean).join("\n");
      const copied = await support.copyText(text);
      els.selectionCopy.textContent = copied ? `已复制 ${state.selectedIds.size} 个 Run ID` : `复制失败，请手动复制 ${state.selectedIds.size} 个 Run ID`;
    });
    els.copyCaseIdsBtn.addEventListener("click", async () => {
      const text = state.items.filter((item) => state.selectedIds.has(detailHelper.rowKey(item))).map((item) => String(item.case_id || "").trim()).filter(Boolean).join("\n");
      const copied = await support.copyText(text);
      els.selectionCopy.textContent = copied ? `已复制 ${state.selectedIds.size} 个用例 ID` : `复制失败，请手动复制 ${state.selectedIds.size} 个用例 ID`;
    });
    els.body.addEventListener("click", (event) => {
      if (!(event.target instanceof HTMLElement)) return;
      const row = event.target.closest("[data-history-row]");
      if (!row) return;
      state.selectedKey = String(row.getAttribute("data-history-row") || "").trim();
      renderTable();
    });
    window.addEventListener("platform-auth-changed", support.updateAuthNotice);

    [els.keywordFilter, els.actorFilter].forEach((node) => {
      node.addEventListener("input", support.persistFilters);
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          state.page = 1;
          refresh().catch(handleLoadError);
        }
      });
    });

    if (listPage) {
      listPage.mountSearchField({
        input: els.keywordFilter,
        clearButton: els.keywordClear,
        onSearch: () => {
          state.page = 1;
          refresh().catch(handleLoadError);
        },
      });
      listPage.bindSortHeaders({
        root: shell,
        sortKeyInput: els.sortKey,
        sortDirInput: els.sortDir,
        onChange: () => {
          state.page = 1;
          refresh().catch(handleLoadError);
        },
      });
    }
  }

  support.restoreFilters();
  support.updateAuthNotice();
  bindEvents();
  refresh().catch(handleLoadError);
})();
