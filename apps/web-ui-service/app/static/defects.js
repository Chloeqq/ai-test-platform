(function () {
  const shell = document.getElementById("defects-shell");
  const presenter = window.DefectsPresenter;
  const listPage = window.ListPage;
  const support = window.DefectsSupport;
  if (!shell || !presenter || !listPage || !support) return;

  const authFetch = window.platformAuthFetch || window.fetch.bind(window);
  const els = {
    total: document.getElementById("def-total"),
    linkedCases: document.getElementById("def-linked-cases"),
    systems: document.getElementById("def-systems"),
    latestLinked: document.getElementById("def-latest-linked"),
    tbody: document.getElementById("def-tbody"),
    selectedPanel: document.getElementById("def-selected-panel"),
    refresh: document.getElementById("def-refresh"),
    applyFilters: document.getElementById("def-apply-filters"),
    reset: document.getElementById("def-reset"),
    footer: document.getElementById("def-footer"),
    lastUpdated: document.getElementById("def-last-updated"),
    filterSummary: document.getElementById("def-filter-summary"),
    selectionBar: document.getElementById("def-selection-bar"),
    selectionCopy: document.getElementById("def-selection-copy"),
    copySelection: document.getElementById("def-copy-selection"),
    copyCaseSelection: document.getElementById("def-copy-case-selection"),
    checkAll: document.getElementById("def-check-all"),
    search: document.getElementById("def-search"),
    searchClear: document.getElementById("def-search-clear"),
    filterKeyword: document.getElementById("def-filter-keyword"),
    filterSystem: document.getElementById("def-filter-system"),
    sortKey: document.getElementById("def-sort-key"),
    sortDir: document.getElementById("def-sort-dir"),
    formCaseId: document.getElementById("def-form-case-id"),
    formDefectId: document.getElementById("def-form-defect-id"),
    formDefectUrl: document.getElementById("def-form-defect-url"),
    formSystem: document.getElementById("def-form-system"),
    formNote: document.getElementById("def-form-note"),
    submit: document.getElementById("def-submit"),
    feedback: document.getElementById("def-feedback"),
  };

  const state = {
    items: [],
    selectedKey: "",
    selectedKeys: new Set(),
    page: 1,
    pageSize: 10,
  };
  const storageKey = "defects_filters_v1";
  const filterFields = {
    keyword: els.filterKeyword,
    system: els.filterSystem,
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

  function formatDateTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function formatRefreshTime(value) {
    if (typeof window.platformFormatRefreshTime === "function") return window.platformFormatRefreshTime(value);
    return String(value || "").trim() || "-";
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
  }

  function updateSelectionBar() {
    const count = state.selectedKeys.size;
    els.selectionBar.hidden = count === 0;
    els.selectionCopy.textContent = `已选择 ${count} 项`;
  }

  function renderTable() {
    const filtered = support.applyFilters(state.items, els, listPage);
    els.filterSummary.textContent = support.filterSummary(els, filtered.length);

    const stats = support.summaryStats(filtered);
    els.total.textContent = String(stats.total);
    els.linkedCases.textContent = String(stats.linkedCases);
    els.systems.textContent = String(stats.systems);
    els.latestLinked.textContent = formatDateTime(stats.latestLinked);

    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="7" class="empty-state">当前筛选条件下没有缺陷记录。</td></tr>';
      els.selectedPanel.innerHTML = presenter.renderSelected(null, {
        displayCaseId,
        normalizeCaseId: support.normalizeCaseId,
      });
    } else {
      const selected = pager.items.find((item) => `${item.case_id}:${item.defect_id}` === state.selectedKey)
        || filtered.find((item) => `${item.case_id}:${item.defect_id}` === state.selectedKey)
        || pager.items[0];
      state.selectedKey = `${selected.case_id}:${selected.defect_id}`;
      els.tbody.innerHTML = pager.items.map((item) => presenter.renderRow(item, state.selectedKey, state.selectedKeys, {
        displayCaseId,
        formatDateTime,
        normalizeCaseId: support.normalizeCaseId,
      })).join("");
      els.selectedPanel.innerHTML = presenter.renderSelected(selected, {
        displayCaseId,
        normalizeCaseId: support.normalizeCaseId,
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

    const rowChecks = els.tbody.querySelectorAll(".def-check");
    rowChecks.forEach((checkbox) => {
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const key = String(checkbox.dataset.defectKey || "").trim();
        if (!key) return;
        if (checkbox.checked) state.selectedKeys.add(key);
        else state.selectedKeys.delete(key);
        updateSelectionBar();
      });
    });
    if (els.checkAll) {
      const currentKeys = Array.from(rowChecks).map((node) => String(node.dataset.defectKey || "").trim()).filter(Boolean);
      els.checkAll.checked = currentKeys.length > 0 && currentKeys.every((key) => state.selectedKeys.has(key));
    }
    updateSelectionBar();
  }

  async function load() {
    const response = await fetch("/api/defects", { cache: "no-store" });
    const payload = response.ok ? await response.json() : { items: [] };
    state.items = Array.isArray(payload.items) ? payload.items : [];
    els.lastUpdated.textContent = formatRefreshTime(new Date().toISOString());
    renderTable();
  }

  [els.filterSystem].forEach((node) => {
    node.addEventListener("input", persistFilters);
  });
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
    els.filterKeyword.value = "";
    els.filterSystem.value = "";
    els.sortKey.value = "linked_at";
    els.sortDir.value = "desc";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    renderTable();
  });
  els.checkAll.addEventListener("change", () => {
    const currentKeys = Array.from(els.tbody.querySelectorAll(".def-check"))
      .map((node) => String(node.dataset.defectKey || "").trim())
      .filter(Boolean);
    if (els.checkAll.checked) currentKeys.forEach((key) => state.selectedKeys.add(key));
    else currentKeys.forEach((key) => state.selectedKeys.delete(key));
    renderTable();
  });
  els.copySelection.addEventListener("click", async () => {
    const defectIds = Array.from(state.selectedKeys)
      .map((key) => key.split(":").pop() || "")
      .filter(Boolean)
      .join("\n");
    if (!defectIds) return;
    try {
      await navigator.clipboard.writeText(defectIds);
      els.selectionCopy.textContent = `已复制 ${state.selectedKeys.size} 个缺陷编号`;
    } catch (_error) {
      els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedKeys.size} 个缺陷编号`;
    }
  });
  els.copyCaseSelection.addEventListener("click", async () => {
    const caseIds = support.copyValues(state.selectedKeys, state.items, "case");
    if (!caseIds) return;
    try {
      await navigator.clipboard.writeText(caseIds);
      els.selectionCopy.textContent = `已复制 ${state.selectedKeys.size} 个用例 ID`;
    } catch (_error) {
      els.selectionCopy.textContent = `复制失败，请手动复制 ${state.selectedKeys.size} 个用例 ID`;
    }
  });
  els.tbody.addEventListener("click", function (event) {
    const row = event.target.closest("tr[data-defect-key]");
    if (!row) return;
    state.selectedKey = row.dataset.defectKey || "";
    renderTable();
  });
  els.submit.addEventListener("click", async function () {
    els.feedback.textContent = "正在提交...";
    try {
      const response = await authFetch("/api/defects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: support.normalizeCaseId(els.formCaseId.value || ""),
          defect_id: String(els.formDefectId.value || "").trim(),
          defect_url: String(els.formDefectUrl.value || "").trim(),
          system: String(els.formSystem.value || "").trim(),
          note: String(els.formNote.value || "").trim(),
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(String(payload.detail || "新增缺陷关联失败"));
      els.feedback.textContent = `已新增关联：${payload.item?.defect_id || "-"}`;
      load();
    } catch (error) {
      els.feedback.textContent = error.message || "新增缺陷关联失败";
    }
  });

  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  persistFilters();

  load().catch((error) => {
    els.tbody.innerHTML = `<tr><td colspan="6" class="error-state">${escapeHtml(error.message || "加载缺陷列表失败")}</td></tr>`;
  });
})();
