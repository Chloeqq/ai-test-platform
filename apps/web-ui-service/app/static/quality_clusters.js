(function () {
  const shared = window.qualityClustersShared;
  const createGatePanel = window.createQualityClustersGatePanel;
  const createListController = window.createQualityClustersListController;
  const shell = document.getElementById("cluster-shell");
  if (!shell || !shared || typeof createGatePanel !== "function" || typeof createListController !== "function") return;

  const els = {
    keywordFilter: document.getElementById("cluster-keyword-filter"),
    searchBtn: document.getElementById("cluster-search"),
    searchClear: document.getElementById("cluster-search-clear"),
    queueFilterSelect: document.getElementById("queue-filter-select"),
    classFilterSelect: document.getElementById("class-filter-select"),
    severityFilterSelect: document.getElementById("severity-filter-select"),
    sortKey: document.getElementById("cluster-sort-key"),
    sortDir: document.getElementById("cluster-sort-dir"),
    manualReviewSelect: document.getElementById("cluster-manual-review-select"),
    qgAlertFilterInput: document.getElementById("qg-alert-filter-input"),
    qgPageFilterInput: document.getElementById("qg-page-filter-input"),
    limitSelect: document.getElementById("limit-select"),
    maxClustersSelect: document.getElementById("max-clusters-select"),
    advancedFilters: document.getElementById("cluster-advanced-filters"),
    applyFiltersBtn: document.getElementById("cluster-apply-filters"),
    refreshBtn: document.getElementById("cluster-refresh"),
    resetBtn: document.getElementById("cluster-reset"),
    lastUpdated: document.getElementById("cluster-last-updated"),
    filterSummary: document.getElementById("cluster-filter-summary"),
    selectionBar: document.getElementById("cluster-selection-bar"),
    selectionCopy: document.getElementById("cluster-selection-copy"),
    copySelectionBtn: document.getElementById("cluster-copy-selection"),
    copyCaseSelectionBtn: document.getElementById("cluster-copy-case-selection"),
    checkAll: document.getElementById("cluster-check-all"),
    tbody: document.getElementById("cluster-tbody"),
    footer: document.getElementById("cluster-footer"),
    detailPanel: document.getElementById("cluster-detail-panel"),
    kpiTotalFailed: document.getElementById("kpi-total-failed"),
    kpiTotalClusters: document.getElementById("kpi-total-clusters"),
    kpiManualReviewClusters: document.getElementById("kpi-manual-review-clusters"),
    kpiTopHotspot: document.getElementById("kpi-top-hotspot"),
    kpiTopHotspotDesc: document.getElementById("kpi-top-hotspot-desc"),
    qgTotalEvents: document.getElementById("qg-total-events"),
    qgBlockedEvents: document.getElementById("qg-blocked-events"),
    qgBlockRate: document.getElementById("qg-block-rate"),
    qgBlockRateDesc: document.getElementById("qg-block-rate-desc"),
    qgTopAlert: document.getElementById("qg-top-alert"),
    qgTopAlertCount: document.getElementById("qg-top-alert-count"),
    qgAlertList: document.getElementById("qg-alert-list"),
    qgDetailSubtitle: document.getElementById("qg-detail-subtitle"),
    qgSuggestionList: document.getElementById("qg-suggestion-list"),
    qgRecentBlockedList: document.getElementById("qg-recent-blocked-list"),
  };

  const state = {
    clusters: [],
    selectedClusterId: shared.readInitialQuery("cluster_id"),
    selectedIds: new Set(),
    page: 1,
    pageSize: 10,
    currentCluster: null,
    qualityGateSummary: null,
    selectedAlertCode: shared.readInitialQuery("alert_code"),
  };

  const storageKey = "quality_clusters_filters_v2";
  const filterFields = {
    keyword: els.keywordFilter,
    queue: els.queueFilterSelect,
    failure_class: els.classFilterSelect,
    severity: els.severityFilterSelect,
    sort_key: els.sortKey,
    sort_dir: els.sortDir,
    manual_review: els.manualReviewSelect,
    alert_code: els.qgAlertFilterInput,
    page: els.qgPageFilterInput,
    limit: els.limitSelect,
    max_clusters: els.maxClustersSelect,
  };

  function readQueryOverrides() {
    Object.entries(filterFields).forEach(([key, node]) => {
      if (!node) return;
      const value = shared.readInitialQuery(key);
      if (value) node.value = value;
    });
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    if (els.advancedFilters) {
      els.advancedFilters.open = Boolean(
        String(els.manualReviewSelect?.value || "").trim() ||
          String(els.qgAlertFilterInput?.value || "").trim() ||
          String(els.qgPageFilterInput?.value || "").trim() ||
          String(els.limitSelect?.value || "").trim() !== "200" ||
          String(els.maxClustersSelect?.value || "").trim() !== "20"
      );
    }
  }

  function syncQueryToUrl() {
    shared.syncQuery({
      keyword: els.keywordFilter?.value,
      queue: els.queueFilterSelect?.value,
      failure_class: els.classFilterSelect?.value,
      severity: els.severityFilterSelect?.value,
      manual_review: els.manualReviewSelect?.value,
      alert_code: els.qgAlertFilterInput?.value,
      page: els.qgPageFilterInput?.value,
      cluster_id: state.selectedClusterId,
    });
  }

  function buildQualityGateQuery() {
    const params = new URLSearchParams();
    const limit = Number(els.limitSelect?.value || 200) || 200;
    params.set("limit", String(Math.max(100, limit * 5)));
    if (String(els.qgAlertFilterInput?.value || "").trim()) params.set("alert_code", String(els.qgAlertFilterInput.value).trim());
    if (String(els.qgPageFilterInput?.value || "").trim()) params.set("page", String(els.qgPageFilterInput.value).trim());
    return params.toString();
  }

  const gatePanel = createGatePanel({
    els,
    state,
    buildQuery: buildQualityGateQuery,
    persistFilters,
    syncQueryToUrl,
  });
  const listController = createListController({
    els,
    state,
    persistFilters,
    syncQueryToUrl,
  });

  function resetFilters() {
    Object.values(filterFields).forEach((node) => {
      if (node) node.value = "";
    });
    els.sortKey.value = "last_seen_at";
    els.sortDir.value = "desc";
    els.limitSelect.value = "200";
    els.maxClustersSelect.value = "20";
    state.page = 1;
    state.selectedClusterId = "";
    state.selectedIds.clear();
    state.currentCluster = null;
    state.selectedAlertCode = "";
    if (typeof window.platformClearFilterState === "function") {
      window.platformClearFilterState(storageKey);
    }
    if (els.advancedFilters) els.advancedFilters.open = false;
    syncQueryToUrl();
  }

  async function refresh() {
    els.refreshBtn.disabled = true;
    els.refreshBtn.textContent = "刷新中...";
    persistFilters();
    syncQueryToUrl();
    try {
      await Promise.all([listController.loadClusters(), gatePanel.load()]);
      els.lastUpdated.textContent = shared.formatRefreshTime(new Date().toISOString());
    } catch (error) {
      console.error(error);
      els.tbody.innerHTML = `<tr><td colspan="7" class="error-state">${shared.escapeHtml(error.message || "失败聚类加载失败")}</td></tr>`;
      els.detailPanel.innerHTML = '<div class="error-state">聚类详情加载失败，请稍后重试。</div>';
      gatePanel.renderError(error.message || "门禁数据加载失败");
      els.lastUpdated.textContent = "最后刷新：加载失败";
    } finally {
      els.refreshBtn.disabled = false;
      els.refreshBtn.textContent = "刷新聚类";
    }
  }

  els.refreshBtn.addEventListener("click", () => refresh().catch(console.error));
  els.resetBtn.addEventListener("click", () => {
    resetFilters();
    refresh().catch(console.error);
  });

  if (window.ListPage) {
    window.ListPage.mountSearchField({
      input: els.keywordFilter,
      clearButton: els.searchClear,
      searchButton: els.searchBtn,
      onSearch: () => {
        state.page = 1;
        refresh().catch(console.error);
      },
    });
    window.ListPage.bindSortHeaders({
      container: shell,
      keyInput: els.sortKey,
      dirInput: els.sortDir,
      onChange: () => {
        state.page = 1;
        persistFilters();
        syncQueryToUrl();
        listController.loadClusters().catch(console.error);
      },
    });
  }
  els.applyFiltersBtn.addEventListener("click", () => {
    state.page = 1;
    refresh().catch(console.error);
  });
  listController.bindFilterInputs(refresh);
  listController.bindTableEvents();
  gatePanel.bindEvents();

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  readQueryOverrides();
  persistFilters();
  refresh().catch(console.error);
})();
