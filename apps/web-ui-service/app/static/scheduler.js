(function () {
  const shell = document.getElementById("scheduler-shell");
  if (!shell) return;

  const els = {
    totalTasks: document.getElementById("sch-total-tasks"),
    activeTasks: document.getElementById("sch-active-tasks"),
    queuedTasks: document.getElementById("sch-queued-tasks"),
    runningTasks: document.getElementById("sch-running-tasks"),
    distributionCards: document.getElementById("sch-distribution-cards"),
    queueTbody: document.getElementById("sch-queue-tbody"),
    recommendations: document.getElementById("sch-recommendations"),
    lanes: document.getElementById("sch-lanes"),
    filterKeyword: document.getElementById("sch-filter-keyword"),
    searchClear: document.getElementById("sch-search-clear"),
    searchButton: document.getElementById("sch-search"),
    filterRunner: document.getElementById("sch-filter-runner"),
    filterPool: document.getElementById("sch-filter-pool"),
    advancedFilters: document.getElementById("sch-advanced-filters"),
    applyFilters: document.getElementById("sch-apply-filters"),
    refresh: document.getElementById("sch-refresh"),
    reset: document.getElementById("sch-reset"),
    footer: document.getElementById("sch-footer"),
    lastUpdated: document.getElementById("sch-last-updated"),
    filterSummary: document.getElementById("sch-filter-summary"),
  };

  const state = {
    rows: [],
    page: 1,
    pageSize: 10,
  };
  const storageKey = "scheduler_filters_v1";
  const filterFields = {
    keyword: els.filterKeyword,
    runner: els.filterRunner,
    pool: els.filterPool,
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

  function topPair(bucket) {
    const entries = Object.entries(bucket || {}).sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
    return entries[0] || ["-", 0];
  }

  function filteredRows() {
    const keyword = String(els.filterKeyword.value || "").trim().toLowerCase();
    const runner = String(els.filterRunner.value || "").trim().toLowerCase();
    const pool = String(els.filterPool.value || "").trim().toLowerCase();
    return state.rows.filter((row) => {
      if (keyword) {
        const haystack = [
          row.queue,
          row.runner,
          Object.keys(row.runner_distribution || {}).join(" "),
          Object.keys(row.environment_pools || {}).join(" "),
          Object.keys(row.resource_profiles || {}).join(" "),
        ].map((entry) => String(entry || "").toLowerCase()).join(" ");
        if (!haystack.includes(keyword)) return false;
      }
      if (runner && !Object.keys(row.runner_distribution || {}).join(" ").toLowerCase().includes(runner) && !String(row.runner || "").toLowerCase().includes(runner)) return false;
      if (pool && !Object.keys(row.environment_pools || {}).join(" ").toLowerCase().includes(pool)) return false;
      return true;
    });
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    if (els.advancedFilters) els.advancedFilters.open = Boolean(String(els.filterPool.value || "").trim());
  }

  function updateFilterSummary(rows) {
    const active = [];
    if (els.filterKeyword.value.trim()) active.push(`关键词 ${els.filterKeyword.value.trim()}`);
    if (els.filterRunner.value.trim()) active.push(`Runner ${els.filterRunner.value.trim()}`);
    if (els.filterPool.value.trim()) active.push(`环境池 ${els.filterPool.value.trim()}`);
    if (els.advancedFilters) els.advancedFilters.open = Boolean(els.filterPool.value.trim());
    els.filterSummary.textContent = active.length
      ? `当前筛选：${active.join(" / ")}，展示 ${rows.length} 条队列记录`
      : `当前按默认策略展示调度队列与资源分布，共 ${rows.length} 条队列记录`;
  }

  function renderRows() {
    const filtered = filteredRows();
    updateFilterSummary(filtered);
    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.queueTbody.innerHTML = '<tr><td colspan="6" class="empty-state">当前筛选条件下没有可展示的调度队列。</td></tr>';
    } else {
      els.queueTbody.innerHTML = pager.items.map((row) => `
        <tr>
          <td>${escapeHtml(row.queue || "-")}</td>
          <td>${escapeHtml(row.queued ?? 0)}</td>
          <td>${escapeHtml(row.running ?? 0)}</td>
          <td>${badge(row.pressure || "unknown")}</td>
          <td>${escapeHtml(Object.keys(row.resource_profiles || {}).join(" / ") || "-")}</td>
          <td>${escapeHtml(Object.keys(row.environment_pools || {}).join(" / ") || "-")}</td>
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
        renderRows();
      });
    }
    if (typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  async function load() {
    const [summaryResponse, planResponse] = await Promise.all([
      fetch("/api/workbench/scheduler/summary", { cache: "no-store" }),
      fetch("/api/workbench/scheduler/dispatch-plan", { cache: "no-store" }),
    ]);
    const summaryPayload = summaryResponse.ok ? await summaryResponse.json() : {};
    const planPayload = planResponse.ok ? await planResponse.json() : {};
    const summary = summaryPayload.item || {};
    const plan = planPayload.item || {};

    els.totalTasks.textContent = String(summary.total_tasks || 0);
    els.activeTasks.textContent = String(summary.active_task_count || 0);
    els.queuedTasks.textContent = String(summary.queued_task_count || 0);
    els.runningTasks.textContent = String(summary.running_task_count || 0);

    const [topPool, topPoolCount] = topPair(summary.environment_pool_distribution || {});
    const [topRunner, topRunnerCount] = topPair(summary.runner_distribution || {});
    const [topProfile, topProfileCount] = topPair(summary.resource_profile_distribution || {});
    els.distributionCards.innerHTML = `
      <article class="stat-card"><h3>主环境池</h3><strong>${escapeHtml(topPool)}</strong><p>${escapeHtml(topPoolCount)} 个任务命中该环境池</p></article>
      <article class="stat-card"><h3>主 Runner</h3><strong>${escapeHtml(topRunner)}</strong><p>${escapeHtml(topRunnerCount)} 个任务命中该 runner</p></article>
      <article class="stat-card"><h3>主资源画像</h3><strong>${escapeHtml(topProfile)}</strong><p>${escapeHtml(topProfileCount)} 个任务命中该画像</p></article>
    `;

    state.rows = Array.isArray(summary.queue_distribution) ? summary.queue_distribution : [];
    renderRows();

    const recommendations = Array.isArray(summary.recommendations) ? summary.recommendations : [];
    els.recommendations.innerHTML = recommendations.length
      ? recommendations.map((item) => `<article class="list-card"><h3>${escapeHtml(item.title || "-")}</h3><p>${escapeHtml(item.summary || "-")}</p></article>`).join("")
      : '<div class="empty-state">当前没有额外调度建议。</div>';

    const lanes = Array.isArray(plan.dispatch_lanes) ? plan.dispatch_lanes : [];
    els.lanes.innerHTML = lanes.length
      ? lanes.map((lane) => `
          <article class="list-card">
            <h3>${escapeHtml(lane.queue || "-")} / ${escapeHtml(lane.runner || "-")}</h3>
            <p>resource=${escapeHtml(lane.resource_profile || "-")} ｜ pool=${escapeHtml(lane.environment_pool || "-")} ｜ tasks=${escapeHtml(lane.task_count ?? 0)} ｜ concurrency=${escapeHtml(lane.recommended_concurrency ?? 0)}</p>
            <p class="meta-text mono">task_ids=${escapeHtml((lane.task_ids || []).join(", ") || "-")}</p>
          </article>
        `).join("")
      : '<div class="empty-state">当前没有 queued dispatch lanes。</div>';
  }

  [els.filterKeyword, els.filterRunner, els.filterPool].forEach((node) => {
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.page = 1;
        persistFilters();
        renderRows();
      }
    });
    node.addEventListener("input", persistFilters);
  });
  els.searchButton.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderRows();
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderRows();
  });
  els.refresh.addEventListener("click", load);
  els.reset.addEventListener("click", () => {
    els.filterKeyword.value = "";
    els.filterRunner.value = "";
    els.filterPool.value = "";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advancedFilters) els.advancedFilters.open = false;
    renderRows();
  });

  if (window.ListPage) {
    window.ListPage.mountSearchField({
      input: els.filterKeyword,
      clearButton: els.searchClear,
      onSearch: () => {
        state.page = 1;
        persistFilters();
        renderRows();
      },
    });
  }
  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  persistFilters();

  load().catch((error) => {
    els.queueTbody.innerHTML = `<tr><td colspan="6" class="error-state">${escapeHtml(error.message || "加载调度中心失败")}</td></tr>`;
  });
})();
