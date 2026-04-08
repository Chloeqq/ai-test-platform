(function () {
  function createWorkbenchHistorySupport(options) {
    const { els, filterFields, storageKey, detailHelper, listPage } = options;

    function copyText(text) {
      if (!text) return Promise.resolve(false);
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
      }
      return Promise.resolve(false);
    }

    function syncQueryToUrl() {
      try {
        const url = new URL(window.location.href);
        Object.entries(filterFields).forEach(([key, node]) => {
          const value = String(node?.value || "").trim();
          if (value) url.searchParams.set(key, value);
          else url.searchParams.delete(key);
        });
        window.history.replaceState({}, "", `${url.pathname}${url.search}`);
      } catch (_error) {
        // Ignore URL sync failure.
      }
    }

    function restoreFilters() {
      if (typeof window.platformRestoreFilterState === "function") {
        window.platformRestoreFilterState(storageKey, filterFields);
      }
      Object.entries(filterFields).forEach(([key, node]) => {
        if (!node) return;
        try {
          const params = new URLSearchParams(window.location.search || "");
          const value = String(params.get(key) || "").trim();
          if (value) node.value = value;
        } catch (_error) {
          // Ignore query parse failure.
        }
      });
      if (els.advancedFilters) {
        els.advancedFilters.open = Boolean(
          String(els.riskGateFilter.value || "").trim() ||
            String(els.selfHealingStatusFilter.value || "").trim() ||
            String(els.actorFilter.value || "").trim()
        );
      }
    }

    function persistFilters() {
      if (typeof window.platformWriteFilterState === "function") {
        window.platformWriteFilterState(storageKey, filterFields);
      }
      if (els.advancedFilters) {
        els.advancedFilters.open = Boolean(
          String(els.riskGateFilter.value || "").trim() ||
            String(els.selfHealingStatusFilter.value || "").trim() ||
            String(els.actorFilter.value || "").trim()
        );
      }
    }

    function sortedItems(items) {
      if (!listPage) return items;
      return listPage.sortItems(items, els.sortKey?.value || "timestamp", els.sortDir?.value || "desc", {
        timestamp: { get: (item) => item.timestamp || "", type: "date" },
        action: { get: (item) => item.action || "", type: "string" },
        status: { get: (item) => item.status || "", type: "string" },
        risk_gate: {
          get: (item) => ((item.risk_summary && typeof item.risk_summary === "object" ? item.risk_summary.gate_decision : "") || ""),
          type: "string",
        },
        self_healing: {
          get: (item) => ((item.self_healing_summary && typeof item.self_healing_summary === "object" ? item.self_healing_summary.status : "") || ""),
          type: "string",
        },
      });
    }

    function updateFilterSummary(totalItems) {
      const active = [
        els.keywordFilter.value && `关键词 ${els.keywordFilter.value.trim()}`,
        els.projectFilter.value && `项目 ${els.projectFilter.value.trim()}`,
        els.actionFilter.value && `动作 ${els.actionFilter.value.trim()}`,
        els.statusFilter.value && `状态 ${els.statusFilter.value.trim()}`,
        els.riskGateFilter.value && `门禁 ${els.riskGateFilter.value.trim()}`,
        els.selfHealingStatusFilter.value && `自愈 ${els.selfHealingStatusFilter.value.trim()}`,
        els.actorFilter.value && `确认人 ${els.actorFilter.value.trim()}`,
      ].filter(Boolean);
      els.filterSummary.textContent = active.length
        ? `当前筛选：${active.join(" / ")}，命中 ${totalItems} 条历史`
        : `当前按默认规则展示最近历史，共 ${totalItems} 条`;
    }

    function setRefreshTimestamp() {
      if (typeof window.platformFormatRefreshTime === "function") {
        els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
      } else {
        els.lastUpdated.textContent = `最后刷新：${new Date().toISOString()}`;
      }
    }

    function resetFilters(state) {
      Object.values(filterFields).forEach((node) => {
        if (node) node.value = "";
      });
      els.sortKey.value = "timestamp";
      els.sortDir.value = "desc";
      state.page = 1;
      state.pageSize = 20;
      state.selectedKey = "";
      state.selectedIds.clear();
      if (typeof window.platformClearFilterState === "function") {
        window.platformClearFilterState(storageKey);
      }
      if (els.advancedFilters) els.advancedFilters.open = false;
      syncQueryToUrl();
    }

    function updateAuthNotice() {
      if (!els.authNotice) return;
      const authState = window.platformAuth && typeof window.platformAuth.getAuthState === "function"
        ? String(window.platformAuth.getAuthState() || "anonymous").toLowerCase()
        : "anonymous";
      if (authState === "authenticated" || authState === "token") {
        const currentUser = window.platformAuth && typeof window.platformAuth.getCurrentUser === "function"
          ? window.platformAuth.getCurrentUser()
          : null;
        const username = String(currentUser?.username || currentUser?.name || "当前用户").trim();
        els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
        els.authNotice.textContent = `${username} 已登录。之后产生的确认点记录会直接显示为你的真实身份。`;
        return;
      }
      els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
      els.authNotice.textContent = "当前为未登录状态：你可以查看历史，但若后续在生成页做确认，系统会先要求登录以保证审计可追溯。";
    }

    return {
      copyText,
      persistFilters,
      resetFilters,
      restoreFilters,
      setRefreshTimestamp,
      sortedItems,
      syncQueryToUrl,
      updateFilterSummary,
      updateAuthNotice,
    };
  }

  window.createWorkbenchHistorySupport = createWorkbenchHistorySupport;
})();
