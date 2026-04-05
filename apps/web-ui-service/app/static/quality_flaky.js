(function () {
  const shell = document.getElementById("quality-flaky-shell");
  const listPage = window.ListPage;
  if (!shell || !listPage) return;

  const els = {
    totalItems: document.getElementById("qf-total-items"),
    linkedCount: document.getElementById("qf-linked-count"),
    stabilityScore: document.getElementById("qf-stability-score"),
    nextAction: document.getElementById("qf-next-action"),
    tbody: document.getElementById("qf-tbody"),
    selectedPanel: document.getElementById("qf-selected-panel"),
    filterKeyword: document.getElementById("qf-filter-keyword"),
    search: document.getElementById("qf-search"),
    searchClear: document.getElementById("qf-search-clear"),
    filterPage: document.getElementById("qf-filter-page"),
    filterModule: document.getElementById("qf-filter-module"),
    filterSourceType: document.getElementById("qf-filter-source-type"),
    filterChangedArea: document.getElementById("qf-filter-changed-area"),
    sortKey: document.getElementById("qf-sort-key"),
    sortDir: document.getElementById("qf-sort-dir"),
    advancedFilters: document.getElementById("qf-advanced-filters"),
    applyFilters: document.getElementById("qf-apply-filters"),
    refresh: document.getElementById("qf-refresh"),
    reset: document.getElementById("qf-reset"),
    lastUpdated: document.getElementById("qf-last-updated"),
    filterSummary: document.getElementById("qf-filter-summary"),
    footer: document.getElementById("qf-footer"),
    checkAll: document.getElementById("qf-check-all"),
    selectionBar: document.getElementById("qf-selection-bar"),
    selectionCopy: document.getElementById("qf-selection-copy"),
    copySelection: document.getElementById("qf-copy-selection"),
  };

  const state = {
    items: [],
    selectedCaseId: "",
    selectedIds: new Set(),
    page: 1,
    pageSize: 20,
  };
  const storageKey = "quality_flaky_filters_v1";
  const filterFields = {
    keyword: els.filterKeyword,
    page: els.filterPage,
    module: els.filterModule,
    source_type: els.filterSourceType,
    changed_area: els.filterChangedArea,
    sort_key: els.sortKey,
    sort_dir: els.sortDir,
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

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
  }

  function normalizeCaseId(value) {
    if (typeof window.platformNormalizeCaseId === "function") return window.platformNormalizeCaseId(value);
    return String(value || "").trim();
  }

  function refreshStamp() {
    if (els.lastUpdated && typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    const hasAdvanced = [els.filterModule, els.filterSourceType, els.filterChangedArea]
      .some((node) => String(node.value || "").trim());
    if (els.advancedFilters) els.advancedFilters.open = hasAdvanced;
  }

  function filteredItems() {
    const keyword = String(els.filterKeyword.value || "").trim().toLowerCase();
    const page = String(els.filterPage.value || "").trim().toLowerCase();
    const module = String(els.filterModule.value || "").trim().toLowerCase();
    const sourceType = String(els.filterSourceType.value || "").trim().toLowerCase();
    const changedArea = String(els.filterChangedArea.value || "").trim().toLowerCase();
    const filtered = state.items.filter((item) => {
      const haystack = [
        item.case_id,
        item.name,
        item.reason,
        item.module,
        item.page,
        ...(item.changed_areas || []),
        ...(item.source_types || []),
      ]
        .map((entry) => String(entry || "").toLowerCase())
        .join(" ");
      if (keyword && !haystack.includes(keyword)) return false;
      if (page && !String(item.page || "").toLowerCase().includes(page)) return false;
      if (module && !String(item.module || "").toLowerCase().includes(module)) return false;
      if (sourceType && !(item.source_types || []).some((entry) => String(entry || "").toLowerCase().includes(sourceType))) return false;
      if (changedArea && !(item.changed_areas || []).some((entry) => String(entry || "").toLowerCase().includes(changedArea))) return false;
      return true;
    });
    return listPage.sortItems(filtered, els.sortKey.value || "flaky_rate", els.sortDir.value || "desc", {
      name: { get: (item) => item.name || item.case_id || "", type: "string" },
      flaky_rate: { get: (item) => item.flaky_rate || 0, type: "number" },
      stability_score: { get: (item) => item.stability_score || 0, type: "number" },
      matched_risk_task_count: { get: (item) => item.matched_risk_task_count || 0, type: "number" },
    });
  }

  function updateFilterSummary(items) {
    const active = [
      els.filterKeyword.value && `关键词 ${els.filterKeyword.value.trim()}`,
      els.filterPage.value && `页面 ${els.filterPage.value.trim()}`,
      els.filterModule.value && `模块 ${els.filterModule.value.trim()}`,
      els.filterSourceType.value && `来源 ${els.filterSourceType.value.trim()}`,
      els.filterChangedArea.value && `变更域 ${els.filterChangedArea.value.trim()}`,
    ].filter(Boolean);
    if (els.advancedFilters) {
      els.advancedFilters.open = Boolean(els.filterModule.value || els.filterSourceType.value || els.filterChangedArea.value);
    }
    els.filterSummary.textContent = active.length
      ? `当前筛选：${active.join(" / ")}，命中 ${items.length} 项`
      : `当前按默认规则展示全部 flaky 项，共 ${items.length} 项`;
  }

  function updateSelectionBar() {
    const count = state.selectedIds.size;
    els.selectionBar.hidden = count === 0;
    els.selectionCopy.textContent = `已选择 ${count} 项`;
  }

  function renderSelected(item) {
    if (!item) {
      els.selectedPanel.innerHTML = '<div class="empty-state">先选择一条 flaky 记录。</div>';
      return;
    }
    els.selectedPanel.innerHTML = `
      <div class="detail-highlight">
        <h3>${escapeHtml(item.name || "-")}</h3>
        <p>${escapeHtml(item.reason || "暂无说明")}</p>
      </div>
      <article class="kv-item"><span>Flaky Rate</span><strong>${escapeHtml(item.flaky_rate ?? 0)}%</strong></article>
      <article class="kv-item"><span>稳定分</span><strong>${escapeHtml(item.stability_score ?? 0)}</strong></article>
      <article class="kv-item"><span>风险重叠</span><strong>${escapeHtml(item.matched_risk_task_count ?? 0)}</strong><p class="meta-text">ratio=${escapeHtml(item.risk_overlap_ratio ?? 0)}</p></article>
      <article class="kv-item"><span>变更域</span><p>${escapeHtml((item.changed_areas || []).join(" / ") || "暂无")}</p></article>
      <article class="kv-item"><span>命中因子</span><p>${escapeHtml((item.matched_factors || []).join(" / ") || "暂无")}</p></article>
      <div class="button-row">
        <a class="action-link" href="${escapeHtml(item.href || "/execution/runs")}">查看执行记录</a>
        <a class="action-link" href="/quality/failure-clusters">查看失败聚类</a>
      </div>
    `;
  }

  function renderTable() {
    const filtered = filteredItems();
    updateFilterSummary(filtered);

    const average = filtered.length
      ? Math.round(filtered.reduce((sum, item) => sum + Number(item.stability_score || 0), 0) / filtered.length)
      : 0;
    els.totalItems.textContent = String(filtered.length);
    els.linkedCount.textContent = String(filtered.filter((item) => Number(item.matched_risk_task_count || 0) > 0).length);
    els.stabilityScore.textContent = String(average);
    els.nextAction.textContent = filtered.some((item) => Number(item.matched_risk_task_count || 0) > 0) ? "先处理重叠项" : "先补稳定性断言";

    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="7" class="empty-state">当前筛选条件下没有 flaky 结果。</td></tr>';
      renderSelected(null);
    } else {
      const selected = pager.items.find((item) => normalizeCaseId(item.case_id || "") === state.selectedCaseId)
        || filtered.find((item) => normalizeCaseId(item.case_id || "") === state.selectedCaseId)
        || pager.items[0];
      state.selectedCaseId = normalizeCaseId(selected.case_id || "");
      els.tbody.innerHTML = pager.items.map((item) => {
        const normalizedId = normalizeCaseId(item.case_id || "");
        const checked = state.selectedIds.has(normalizedId) ? "checked" : "";
        const actionMenu = listPage.renderRowMenu([
          { href: escapeHtml(item.href || "/execution/runs"), label: "查看执行记录" },
          { href: "/quality/failure-clusters", label: "查看失败聚类" },
        ]);
        return `
          <tr class="${normalizedId === state.selectedCaseId ? "is-active" : ""}" data-case-id="${escapeHtml(normalizedId)}">
            <td class="selection-col"><input class="qf-check" type="checkbox" data-case-id="${escapeHtml(normalizedId)}" ${checked} aria-label="选择用例"></td>
            <td><div class="table-title">${escapeHtml(item.name || "-")}</div><div class="table-subtitle mono">用例 ID · ${escapeHtml(displayCaseId(item.case_id || "-"))}</div></td>
            <td>${escapeHtml(item.module || "-")}</td>
            <td>${escapeHtml(item.flaky_rate ?? 0)}%</td>
            <td>${escapeHtml(item.stability_score ?? 0)}</td>
            <td>${escapeHtml(item.matched_risk_task_count ?? 0)}</td>
            <td class="row-actions-col">${actionMenu}</td>
          </tr>
        `;
      }).join("");
      renderSelected(selected);
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

    const rowChecks = els.tbody.querySelectorAll(".qf-check");
    rowChecks.forEach((checkbox) => {
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const id = normalizeCaseId(checkbox.dataset.caseId || "");
        if (!id) return;
        if (checkbox.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        updateSelectionBar();
      });
    });
    if (els.checkAll) {
      const currentIds = Array.from(rowChecks).map((node) => normalizeCaseId(node.dataset.caseId || "")).filter(Boolean);
      els.checkAll.checked = currentIds.length > 0 && currentIds.every((id) => state.selectedIds.has(id));
    }
    updateSelectionBar();
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="7" class="loading-state">正在加载 flaky 分析...</td></tr>';
    const response = await fetch("/api/dashboard/governance", { cache: "no-store" });
    const payload = response.ok ? await response.json() : {};
    const flaky = payload.flaky_analysis || {};
    state.items = Array.isArray(flaky.items) ? flaky.items : [];
    refreshStamp();
    renderTable();
  }

  [els.filterPage, els.filterModule, els.filterSourceType, els.filterChangedArea].forEach((node) => node.addEventListener("input", persistFilters));

  listPage.mountSearchField({
    input: els.filterKeyword,
    clearButton: els.searchClear,
    searchButton: els.search,
    onSearch: () => {
      state.page = 1;
      persistFilters();
      renderTable();
    },
  });
  listPage.bindSortHeaders({
    container: shell,
    keyInput: els.sortKey,
    dirInput: els.sortDir,
    onChange: () => {
      persistFilters();
      renderTable();
    },
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderTable();
  });

  els.refresh.addEventListener("click", load);
  els.reset.addEventListener("click", () => {
    [els.filterKeyword, els.filterPage, els.filterModule, els.filterSourceType, els.filterChangedArea].forEach((node) => {
      node.value = "";
    });
    els.sortKey.value = "flaky_rate";
    els.sortDir.value = "desc";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advancedFilters) els.advancedFilters.open = false;
    renderTable();
  });
  els.copySelection.addEventListener("click", async () => {
    const text = Array.from(state.selectedIds).join("\n");
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      els.selectionCopy.textContent = `已复制 ${state.selectedIds.size} 个用例 ID`;
    } catch (_error) {
      els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedIds.size} 个用例 ID`;
    }
  });
  els.checkAll.addEventListener("change", () => {
    const currentIds = Array.from(els.tbody.querySelectorAll(".qf-check"))
      .map((node) => normalizeCaseId(node.dataset.caseId || ""))
      .filter(Boolean);
    if (els.checkAll.checked) currentIds.forEach((id) => state.selectedIds.add(id));
    else currentIds.forEach((id) => state.selectedIds.delete(id));
    renderTable();
  });
  els.tbody.addEventListener("click", function (event) {
    const row = event.target.closest("tr[data-case-id]");
    if (!row) return;
    state.selectedCaseId = normalizeCaseId(row.dataset.caseId || "");
    renderTable();
  });

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  persistFilters();

  load().catch((error) => {
    els.tbody.innerHTML = `<tr><td colspan="7" class="error-state">${escapeHtml(error.message || "加载 flaky 分析失败")}</td></tr>`;
  });
})();
