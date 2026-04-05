(function () {
  function createWorkbenchHistorySupport(config) {
    const { els, filterFields, storageKey, detailHelper } = config;

    function parseSortValue(text) {
      const value = String(text || "").trim().toLowerCase();
      return value === "asc" ? "asc" : "desc";
    }

    function sortedItems(items) {
      const rows = Array.isArray(items) ? items.slice() : [];
      const sortKey = String(els.sortKey?.value || "timestamp");
      const sortDir = parseSortValue(els.sortDir?.value);
      rows.sort((a, b) => {
        const av = String(a?.[sortKey] || a?.timestamp || "");
        const bv = String(b?.[sortKey] || b?.timestamp || "");
        if (av === bv) return 0;
        if (sortDir === "asc") return av > bv ? 1 : -1;
        return av > bv ? -1 : 1;
      });
      return rows;
    }

    function updateFilterSummary(totalItems) {
      if (!els.filterSummary) return;
      const parts = [];
      Object.entries(filterFields).forEach(([key, node]) => {
        const value = String(node?.value || "").trim();
        if (!value) return;
        parts.push(key + "=" + value);
      });
      els.filterSummary.textContent =
        "当前筛选结果 " + Number(totalItems || 0) + " 条" + (parts.length ? " · " + parts.join(" / ") : " · 默认视图");
    }

    function persistFilters() {
      if (typeof window.platformWriteFilterState !== "function") return;
      window.platformWriteFilterState(storageKey, filterFields);
    }

    function restoreFilters() {
      if (typeof window.platformRestoreFilterState === "function") {
        window.platformRestoreFilterState(storageKey, filterFields);
      }
      const params = new URLSearchParams(window.location.search || "");
      Object.entries(filterFields).forEach(([key, node]) => {
        if (!node) return;
        const value = String(params.get(key) || "").trim();
        if (!value) return;
        node.value = value;
      });
    }

    function syncQueryToUrl() {
      const params = new URLSearchParams(window.location.search || "");
      Object.entries(filterFields).forEach(([key, node]) => {
        const value = String(node?.value || "").trim();
        if (!value) params.delete(key);
        else params.set(key, value);
      });
      const query = params.toString();
      const nextUrl = window.location.pathname + (query ? "?" + query : "");
      window.history.replaceState({}, "", nextUrl);
    }

    function setRefreshTimestamp() {
      if (!els.lastUpdated) return;
      if (typeof window.platformFormatDateTime === "function") {
        els.lastUpdated.textContent = "最后刷新：" + window.platformFormatDateTime(new Date().toISOString());
      } else {
        els.lastUpdated.textContent = "最后刷新：" + new Date().toLocaleString();
      }
    }

    function resetFilters(state) {
      Object.values(filterFields).forEach((node) => {
        if (node) node.value = "";
      });
      if (els.sortKey) els.sortKey.value = "timestamp";
      if (els.sortDir) els.sortDir.value = "desc";
      state.selectedIds.clear();
      state.selectedKey = "";
      persistFilters();
      syncQueryToUrl();
      updateFilterSummary(state.totalItems || 0);
      if (els.detailPanel) {
        els.detailPanel.innerHTML = detailHelper.renderDetailPanel(null);
      }
    }

    async function copyText(text) {
      const payload = String(text || "");
      if (!payload) return false;
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        try {
          await navigator.clipboard.writeText(payload);
          return true;
        } catch (_error) {
          return false;
        }
      }
      return false;
    }

    function updateAuthNotice() {
      if (!els.authNotice) return;
      const auth = window.platformAuth;
      const state = auth && typeof auth.getAuthState === "function" ? String(auth.getAuthState()) : "anonymous";
      if (state === "authenticated" || state === "token") {
        const user = auth && typeof auth.getCurrentUser === "function" ? auth.getCurrentUser() : null;
        const name = String(user?.username || user?.name || "当前用户").trim();
        els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
        els.authNotice.textContent = name + " 已登录，确认类操作会写入真实审计记录。";
      } else {
        els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
        els.authNotice.textContent = "历史记录支持匿名查看，但确认动作需要登录后提交。";
      }
    }

    return {
      copyText: copyText,
      persistFilters: persistFilters,
      resetFilters: resetFilters,
      restoreFilters: restoreFilters,
      setRefreshTimestamp: setRefreshTimestamp,
      sortedItems: sortedItems,
      syncQueryToUrl: syncQueryToUrl,
      updateAuthNotice: updateAuthNotice,
      updateFilterSummary: updateFilterSummary,
    };
  }

  window.createWorkbenchHistorySupport = createWorkbenchHistorySupport;
})();
