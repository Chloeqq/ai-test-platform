(function () {
  const shell = document.getElementById("quality-trends-shell");
  if (!shell) return;

  const els = {
    blocked7d: document.getElementById("qt-blocked-7d"),
    riskBlocked7d: document.getElementById("qt-risk-blocked-7d"),
    reviewRequired7d: document.getElementById("qt-review-required-7d"),
    strictMode: document.getElementById("qt-strict-mode"),
    trendTbody: document.getElementById("qt-trend-tbody"),
    topSummary: document.getElementById("qt-top-summary"),
    metrics: document.getElementById("qt-metrics"),
    keyword: document.getElementById("qt-keyword"),
    searchClear: document.getElementById("qt-search-clear"),
    searchButton: document.getElementById("qt-search"),
    window: document.getElementById("qt-window"),
    view: document.getElementById("qt-view"),
    alertCode: document.getElementById("qt-alert-code"),
    advancedFilters: document.getElementById("qt-advanced-filters"),
    applyFilters: document.getElementById("qt-apply-filters"),
    refresh: document.getElementById("qt-refresh"),
    reset: document.getElementById("qt-reset"),
    footer: document.getElementById("qt-footer"),
    lastUpdated: document.getElementById("qt-last-updated"),
    filterSummary: document.getElementById("qt-filter-summary"),
  };

  const state = {
    trend: [],
    page: 1,
    pageSize: 10,
  };
  const storageKey = "quality_trends_filters_v1";
  const filterFields = {
    keyword: els.keyword,
    window: els.window,
    view: els.view,
    alert_code: els.alertCode,
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function badge(value) {
    const text = String(value || "unknown").trim() || "unknown";
    const cls = text.toLowerCase().replaceAll(/[^a-z0-9_]+/g, "_");
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function filteredTrend() {
    const keyword = String(els.keyword.value || "").trim().toLowerCase();
    const alertCode = String(els.alertCode.value || "").trim().toLowerCase();
    const windowSize = Math.max(1, Number(els.window.value || 14) || 14);
    const base = state.trend.slice(-windowSize).filter((row) => {
      if (!keyword) return true;
      const haystack = [row.day, row.top_alert_code, row.top_theme, row.direction]
        .map((entry) => String(entry || "").toLowerCase())
        .join(" ");
      return haystack.includes(keyword);
    });
    if (!alertCode) return base;
    return base.filter((row) => String(row.top_alert_code || "").toLowerCase().includes(alertCode));
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    if (els.advancedFilters) els.advancedFilters.open = Boolean(String(els.alertCode.value || "").trim());
  }

  function updateFilterSummary(items) {
    const parts = [];
    if (els.keyword.value.trim()) parts.push(`关键词 ${els.keyword.value.trim()}`);
    if (els.view.value) parts.push(`视图 ${els.view.options[els.view.selectedIndex]?.text || els.view.value}`);
    if (els.window.value) parts.push(`窗口 ${els.window.value} 天`);
    if (els.alertCode.value.trim()) parts.push(`告警码 ${els.alertCode.value.trim()}`);
    if (els.advancedFilters) els.advancedFilters.open = Boolean(els.alertCode.value.trim());
    els.filterSummary.textContent = parts.length
      ? `当前筛选：${parts.join(" / ")}，展示 ${items.length} 条趋势记录`
      : `当前按默认时间窗口展示治理趋势，共 ${items.length} 条`;
  }

  function renderTrendTable() {
    const filtered = filteredTrend();
    updateFilterSummary(filtered);
    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.trendTbody.innerHTML = '<tr><td colspan="5" class="empty-state">当前筛选条件下没有趋势数据。</td></tr>';
    } else {
      els.trendTbody.innerHTML = pager.items.map((row) => `
        <tr>
          <td>${escapeHtml(row.day || "-")}</td>
          <td>${escapeHtml(row.quality_gate_block ?? 0)}</td>
          <td>${escapeHtml(row.risk_blocked_runs ?? 0)}</td>
          <td>${escapeHtml(row.review_required_runs ?? 0)}</td>
          <td>${escapeHtml(row.pressure_score ?? 0)}</td>
        </tr>
      `).join("");
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
        renderTrendTable();
      });
    }
    if (typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  async function load() {
    const response = await fetch("/api/dashboard/governance", { cache: "no-store" });
    const payload = response.ok ? await response.json() : {};
    const trendSummary = payload.trend_summary_7d || {};
    const summary = payload.summary || {};
    const metricDefinitions = payload.metric_definitions || {};
    const failureClusters = payload.failure_clusters || {};
    const flakyAnalysis = payload.flaky_analysis || {};
    const managerSummary = payload.manager_summary || {};
    const strictPolicy = summary.strict_manifest_policy || {};
    state.trend = Array.isArray(payload.trend_14d) ? payload.trend_14d : [];

    els.blocked7d.textContent = String(trendSummary.quality_gate_blocked || 0);
    els.riskBlocked7d.textContent = String(trendSummary.risk_blocked_runs || 0);
    els.reviewRequired7d.textContent = String(trendSummary.review_required_runs || 0);
    els.strictMode.innerHTML = badge(strictPolicy.mode || summary.strict_mode_readiness?.status || "unknown");

    els.topSummary.innerHTML = `
      <article class="list-card"><h3>管理者摘要</h3><p>${escapeHtml(managerSummary.weekly_focus || managerSummary.headline || "暂无摘要")}</p></article>
      <article class="list-card"><h3>失败聚类焦点</h3><p>${escapeHtml((failureClusters.analysis || {}).summary || "暂无聚类焦点")}</p></article>
      <article class="list-card"><h3>Flaky 摘要</h3><p>${escapeHtml(flakyAnalysis.summary || "暂无 Flaky 摘要")}</p></article>
      <article class="list-card"><h3>Strict Manifest</h3><p>${escapeHtml(strictPolicy.next_action || "暂无 strict manifest 建议")}</p></article>
      <article class="list-card"><h3>Top Alert Code</h3><p>${escapeHtml(summary.top_alert_code || "暂无")}</p></article>
    `;

    const keys = [
      "high_risk_task_count",
      "block_rate_24h",
      "manual_review_cluster_count",
      "no_manifest_task_count",
      "multisource_task_count",
      "traceability_gap_task_count",
      "strict_mode_readiness",
      "strict_manifest_policy",
    ];
    els.metrics.innerHTML = keys.map((key) => `
      <article class="kv-item">
        <span>${escapeHtml(key)}</span>
        <p>${escapeHtml(metricDefinitions[key] || "暂无口径说明")}</p>
      </article>
    `).join("");

    renderTrendTable();
  }

  els.refresh.addEventListener("click", load);
  els.searchButton.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderTrendTable();
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderTrendTable();
  });
  els.reset.addEventListener("click", () => {
    els.keyword.value = "";
    els.window.value = "14";
    els.view.value = "governance";
    els.alertCode.value = "";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advancedFilters) els.advancedFilters.open = false;
    renderTrendTable();
  });
  [els.window, els.view].forEach((node) => node.addEventListener("change", () => {
    state.page = 1;
    persistFilters();
    renderTrendTable();
  }));
  if (window.ListPage) {
    window.ListPage.mountSearchField({
      input: els.keyword,
      clearButton: els.searchClear,
      onSearch: () => {
        state.page = 1;
        persistFilters();
        renderTrendTable();
      },
    });
  }
  els.alertCode.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.page = 1;
      persistFilters();
      renderTrendTable();
    }
  });
  els.alertCode.addEventListener("input", persistFilters);

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  persistFilters();

  load().catch((error) => {
    els.trendTbody.innerHTML = `<tr><td colspan="5" class="error-state">${escapeHtml(error.message || "加载趋势失败")}</td></tr>`;
  });
})();
