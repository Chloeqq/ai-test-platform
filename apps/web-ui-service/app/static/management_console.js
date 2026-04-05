(function () {
  const presenter = window.ManagementConsolePresenter;
  const listPage = window.ListPage || null;
  const shell = document.getElementById("management-console-shell");
  if (!shell || !presenter) return;

  function parseJsonScript(id, fallback) {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent || "");
    } catch (_error) {
      return fallback;
    }
  }

  const state = {
    items: Array.isArray(parseJsonScript("management-console-data", [])) ? parseJsonScript("management-console-data", []) : [],
    selectedIds: new Set(),
    activeId: "",
    page: 1,
    pageSize: 20,
  };
  const config = parseJsonScript("management-console-config", {});
  const storageKey = `management_console_filters:${window.location.pathname}`;

  const els = {
    search: document.getElementById("management-console-search"),
    searchClear: document.getElementById("management-console-search-clear"),
    searchButton: document.getElementById("management-console-search-button"),
    status: document.getElementById("management-console-status"),
    meta: document.getElementById("management-console-meta"),
    advanced: document.getElementById("management-console-advanced"),
    apply: document.getElementById("management-console-apply"),
    refresh: document.getElementById("management-console-refresh"),
    reset: document.getElementById("management-console-reset"),
    summary: document.getElementById("management-console-summary"),
    lastUpdated: document.getElementById("management-console-last-updated"),
    selectionBar: document.getElementById("management-console-selection-bar"),
    selectionCopy: document.getElementById("management-console-selection-copy"),
    selectionCopyBtn: document.getElementById("management-console-copy"),
    selectionClearBtn: document.getElementById("management-console-clear"),
    checkAll: document.getElementById("management-console-check-all"),
    list: document.getElementById("management-console-list"),
    footer: document.getElementById("management-console-footer"),
    detailEmpty: document.getElementById("management-console-detail-empty"),
    detailPanel: document.getElementById("management-console-detail-panel"),
  };

  const filterFields = {
    keyword: els.search,
    status: els.status,
    meta: els.meta,
  };

  function refreshStamp() {
    if (els.lastUpdated && typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  function restoreFilters() {
    if (typeof window.platformRestoreFilterState === "function") {
      window.platformRestoreFilterState(storageKey, filterFields);
    }
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    if (els.advanced) els.advanced.open = Boolean(String(els.meta.value || "").trim());
  }

  function populateStatusOptions() {
    const statuses = Array.from(new Set(state.items.map((item) => String(item.status || item.badge || "").trim()).filter(Boolean))).sort();
    const current = String(els.status.value || "");
    els.status.innerHTML = ['<option value="">全部状态</option>']
      .concat(statuses.map((value) => `<option value="${presenter.escapeHtml(value)}">${presenter.escapeHtml(value)}</option>`))
      .join("");
    els.status.value = current;
  }

  function matches(item, keyword, status, metaKeyword) {
    const haystack = [
      item.title,
      item.meta,
      item.badge,
      item.status,
      ...(Array.isArray(item.tags) ? item.tags : []),
      ...(Array.isArray(item.keywords) ? item.keywords : []),
      item.detail_title,
      item.detail_description,
      ...(Array.isArray(item.detail_bullets) ? item.detail_bullets : []),
    ].map((entry) => String(entry || "").toLowerCase()).join(" ");
    if (keyword && !haystack.includes(keyword)) return false;
    if (status && String(item.status || item.badge || "").toLowerCase() !== status) return false;
    if (metaKeyword) {
      const metaText = [item.meta, item.owner, item.group, ...(Array.isArray(item.tags) ? item.tags : [])]
        .map((entry) => String(entry || "").toLowerCase())
        .join(" ");
      if (!metaText.includes(metaKeyword)) return false;
    }
    return true;
  }

  function filteredItems() {
    const keyword = String(els.search.value || "").trim().toLowerCase();
    const status = String(els.status.value || "").trim().toLowerCase();
    const metaKeyword = String(els.meta.value || "").trim().toLowerCase();
    return state.items
      .filter((item) => matches(item, keyword, status, metaKeyword))
      .sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
  }

  function updateSummary(items) {
    const active = [
      els.search.value && `关键词 ${els.search.value.trim()}`,
      els.status.value && `状态 ${els.status.value.trim()}`,
      els.meta.value && `补充关键词 ${els.meta.value.trim()}`,
    ].filter(Boolean);
    els.summary.textContent = active.length
      ? `当前筛选：${active.join(" / ")}，命中 ${items.length} 项`
      : `当前按默认条件展示全部管理项，共 ${items.length} 项`;
  }

  function updateSelectionBar() {
    const count = state.selectedIds.size;
    els.selectionBar.hidden = count === 0;
    els.selectionCopy.textContent = `已选择 ${count} 项`;
  }

  function renderDetail(item) {
    if (!item) {
      els.detailEmpty.classList.remove("hidden");
      els.detailPanel.classList.add("hidden");
      els.detailPanel.innerHTML = "";
      return;
    }
    els.detailEmpty.classList.add("hidden");
    els.detailPanel.classList.remove("hidden");
    els.detailPanel.innerHTML = presenter.renderDetail(item);
  }

  function renderList() {
    const items = filteredItems();
    updateSummary(items);
    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(items, state.page, state.pageSize)
      : { items, page: 1, pageSize: items.length || 20, totalItems: items.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      const emptyState = config.empty_state || {};
      els.list.innerHTML = `
        <div class="empty-state">
          <strong>${presenter.escapeHtml(emptyState.title || "当前筛选下暂无数据")}</strong>
          <p>${presenter.escapeHtml(emptyState.description || "可以重置筛选后重试。")}</p>
        </div>
      `;
      if (els.checkAll) els.checkAll.checked = false;
      renderDetail(null);
    } else {
      if (!state.activeId || !pager.items.some((item) => String(item.id) === state.activeId)) {
        state.activeId = String(pager.items[0].id || "");
      }
      els.list.innerHTML = pager.items.map((item) => presenter.renderListItem(item, state.activeId, state.selectedIds)).join("");
      renderDetail(items.find((item) => String(item.id) === state.activeId) || pager.items[0]);
    }

    if (typeof window.Pagination === "function") {
      new window.Pagination("#management-console-footer", {
        page: pager.page,
        page_size: pager.pageSize,
        total_items: pager.totalItems,
        page_size_options: [10, 20, 50, 100],
        show_total: true,
        onChange: (nextPage, nextPageSize) => {
          state.page = nextPage;
          state.pageSize = nextPageSize;
          renderList();
        },
      });
    }

    els.list.querySelectorAll(".management-item-trigger").forEach((button) => {
      button.addEventListener("click", () => {
        state.activeId = String(button.dataset.managementId || "");
        renderList();
      });
    });
    els.list.querySelectorAll(".management-check").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const id = String(checkbox.dataset.managementId || "");
        if (!id) return;
        if (checkbox.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        updateSelectionBar();
      });
    });

    const pageIds = pager.items.map((item) => String(item.id || "")).filter(Boolean);
    if (els.checkAll) els.checkAll.checked = pageIds.length > 0 && pageIds.every((id) => state.selectedIds.has(id));
    updateSelectionBar();
    refreshStamp();
  }

  function refreshList() {
    els.list.classList.add("loading-state");
    els.list.textContent = "正在刷新管理页列表...";
    window.setTimeout(() => {
      els.list.classList.remove("loading-state");
      renderList();
    }, 60);
  }

  function resetFilters() {
    els.search.value = "";
    els.status.value = "";
    els.meta.value = "";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advanced) els.advanced.open = false;
    renderList();
  }

  function bindEvents() {
    els.checkAll.addEventListener("change", () => {
      const visibleIds = Array.from(els.list.querySelectorAll(".management-check")).map((node) => String(node.dataset.managementId || "")).filter(Boolean);
      visibleIds.forEach((id) => {
        if (els.checkAll.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
      });
      renderList();
    });
    els.selectionCopyBtn.addEventListener("click", async () => {
      const text = state.items.filter((item) => state.selectedIds.has(String(item.id))).map((item) => item.title || item.id).join("\n");
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        els.selectionCopy.textContent = `已复制 ${state.selectedIds.size} 项`;
      } catch (_error) {
        els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedIds.size} 项`;
      }
    });
    els.selectionClearBtn.addEventListener("click", () => {
      state.selectedIds.clear();
      renderList();
    });

    els.status.addEventListener("change", () => {
      state.page = 1;
      persistFilters();
      renderList();
    });
    els.meta.addEventListener("input", persistFilters);
    els.meta.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.page = 1;
        persistFilters();
        renderList();
      }
    });
    els.searchButton.addEventListener("click", () => {
      state.page = 1;
      persistFilters();
      renderList();
    });
    els.apply.addEventListener("click", () => {
      state.page = 1;
      persistFilters();
      renderList();
    });
    els.refresh.addEventListener("click", refreshList);
    els.reset.addEventListener("click", resetFilters);

    if (listPage) {
      listPage.mountSearchField({
        input: els.search,
        clearButton: els.searchClear,
        onSearch: () => {
          state.page = 1;
          persistFilters();
          renderList();
        },
      });
    }
  }

  populateStatusOptions();
  restoreFilters();
  persistFilters();
  bindEvents();
  renderList();
})();
