(function () {
  function createTestPointAssetsSupport(options) {
    const {
      els,
      listPage,
      filterFields,
      storageKey,
      advancedFilterKeys,
    } = options;

    function escapeHtml(value) {
      if (typeof window.platformEscapeHtml === "function") return window.platformEscapeHtml(value);
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function badge(value) {
      if (typeof window.platformRenderBadge === "function") return window.platformRenderBadge(value);
      return `<span class="badge">${escapeHtml(value || "unknown")}</span>`;
    }

    function topPair(bucket) {
      const entries = Object.entries(bucket || {});
      entries.sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
      return entries[0] || ["-", 0];
    }

    function displayRunId(value) {
      if (typeof window.platformDisplayRunId === "function") return window.platformDisplayRunId(value);
      return String(value || "").trim() || "-";
    }

    function queryValues() {
      const values = typeof window.platformCollectFilterValues === "function"
        ? window.platformCollectFilterValues(filterFields, {
          page: (value) => String(value || "").trim().toLowerCase(),
          keyword: (value) => String(value || "").trim().toLowerCase(),
          source_type: (value) => String(value || "").trim().toLowerCase(),
          coverage_status: (value) => String(value || "").trim().toLowerCase(),
          review_status: (value) => String(value || "").trim().toLowerCase(),
          gate_decision: (value) => String(value || "").trim().toLowerCase(),
          selection_state: (value) => String(value || "").trim().toLowerCase(),
        })
        : {
          page: String(els.filterPage.value || "").trim().toLowerCase(),
          keyword: String(els.filterKeyword.value || "").trim().toLowerCase(),
          source_type: String(els.filterSourceType.value || "").trim().toLowerCase(),
          coverage_status: String(els.filterCoverageStatus.value || "").trim().toLowerCase(),
          review_status: String(els.filterReviewStatus.value || "").trim().toLowerCase(),
          gate_decision: String(els.filterGateDecision.value || "").trim().toLowerCase(),
          selection_state: String(els.filterSelectionState.value || "").trim().toLowerCase(),
        };
      return {
        page: values.page || "",
        keyword: values.keyword || "",
        sourceType: values.source_type || "",
        coverageStatus: values.coverage_status || "",
        reviewStatus: values.review_status || "",
        gateDecision: values.gate_decision || "",
        selectionState: values.selection_state || "",
      };
    }

    function refreshStamp() {
      if (typeof window.platformSetRefreshTime === "function") {
        window.platformSetRefreshTime(els.lastUpdated, new Date().toISOString());
        return;
      }
      if (els.lastUpdated && typeof window.platformFormatRefreshTime === "function") {
        els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
      }
    }

    function syncAdvancedFilters(filters) {
      const values = filters || queryValues();
      const hasAdvanced = typeof window.platformHasActiveFilterValues === "function"
        ? window.platformHasActiveFilterValues(
          {
            source_type: values.sourceType,
            coverage_status: values.coverageStatus,
            review_status: values.reviewStatus,
            gate_decision: values.gateDecision,
            selection_state: values.selectionState,
          },
          advancedFilterKeys,
        )
        : advancedFilterKeys.some((key) => {
          const lookup = {
            source_type: values.sourceType,
            coverage_status: values.coverageStatus,
            review_status: values.reviewStatus,
            gate_decision: values.gateDecision,
            selection_state: values.selectionState,
          };
          return Boolean(String(lookup[key] || "").trim());
        });
      if (typeof window.platformSetDetailsOpen === "function") {
        window.platformSetDetailsOpen(els.advancedFilters, hasAdvanced);
        return;
      }
      if (els.advancedFilters) els.advancedFilters.open = hasAdvanced;
    }

    function persistFilters() {
      if (typeof window.platformWriteFilterState === "function") {
        window.platformWriteFilterState(storageKey, filterFields);
      }
      syncAdvancedFilters();
    }

    function filteredItems(items) {
      const filters = queryValues();
      const filtered = items.filter((item) => {
        const traceability = item.traceability_summary || {};
        const gate = traceability.gate || {};
        const review = traceability.review || {};
        const coverage = traceability.coverage || {};
        const haystack = [
          item.asset_id,
          item.title,
          item.page,
          item.source_type,
          ...(item.requirement || []),
        ].map((entry) => String(entry || "").toLowerCase()).join(" ");
        if (filters.page && !String(item.page || "").toLowerCase().includes(filters.page)) return false;
        if (filters.keyword && !haystack.includes(filters.keyword)) return false;
        if (filters.sourceType && !String(item.source_type || "").toLowerCase().includes(filters.sourceType)) return false;
        if (filters.coverageStatus) {
          const status = String(coverage.latest_run_status || coverage.asset_status || "").toLowerCase();
          if (!status.includes(filters.coverageStatus)) return false;
        }
        if (filters.reviewStatus) {
          const status = String(review.test_point_status || "").toLowerCase();
          if (!status.includes(filters.reviewStatus)) return false;
        }
        if (filters.gateDecision) {
          const status = String(gate.effective_decision || gate.decision || "").toLowerCase();
          if (!status.includes(filters.gateDecision)) return false;
        }
        if (filters.selectionState) {
          const status = String((item.selection_summary || {}).selection_state || "").toLowerCase();
          if (!status.includes(filters.selectionState)) return false;
        }
        return true;
      });
      return listPage.sortItems(filtered, els.sortKey.value || "page", els.sortDir.value || "asc", {
        title: { get: (item) => item.title || item.asset_id || "", type: "string" },
        page: { get: (item) => item.page || "", type: "string" },
        source_type: { get: (item) => item.source_type || "", type: "string" },
        point_count: { get: (item) => item.point_count || 0, type: "number" },
        selection_state: { get: (item) => (item.selection_summary || {}).selection_state || "", type: "string" },
        gate_decision: { get: (item) => (item.traceability_summary?.gate || {}).effective_decision || "", type: "string" },
        latest_run: { get: (item) => item.latest_run?.run_id || "", type: "date" },
      });
    }

    function updateFilterSummary(items) {
      const filters = queryValues();
      const active = [];
      if (filters.page) active.push({ label: "页面", value: filters.page });
      if (filters.keyword) active.push({ label: "关键词", value: filters.keyword });
      if (filters.sourceType) active.push({ label: "来源", value: filters.sourceType });
      if (filters.coverageStatus) active.push({ label: "覆盖", value: filters.coverageStatus });
      if (filters.reviewStatus) active.push({ label: "评审", value: filters.reviewStatus });
      if (filters.gateDecision) active.push({ label: "门禁", value: filters.gateDecision });
      if (filters.selectionState) active.push({ label: "选择", value: filters.selectionState });
      syncAdvancedFilters(filters);
      if (typeof window.platformRenderFilterSummary === "function") {
        window.platformRenderFilterSummary(els.filterSummary, active, {
          totalItems: items.length,
          hitText: (total) => `命中 ${total} 个资产`,
          emptyText: (total) => `当前按默认治理视角展示全部测试点资产，共 ${total} 个`,
        });
        return;
      }
      els.filterSummary.textContent = active.length
        ? `当前筛选：${active.map((item) => `${item.label} ${item.value}`).join(" / ")}，命中 ${items.length} 个资产`
        : `当前按默认治理视角展示全部测试点资产，共 ${items.length} 个`;
    }

    function updateSelectionBar(selectedIds) {
      if (typeof window.platformSyncSelectionBar === "function") {
        window.platformSyncSelectionBar(els.selectionBar, els.selectionCopy, selectedIds.size, {
          copyText: (count) => `已选择 ${count} 项`,
        });
        return;
      }
      const count = selectedIds.size;
      els.selectionBar.hidden = count === 0;
      els.selectionCopy.textContent = `已选择 ${count} 项`;
    }

    function renderSummary(coverageSummary) {
      els.total.textContent = String(coverageSummary.total_assets || 0);
      els.totalPoints.textContent = String(coverageSummary.total_points || 0);
      els.readyAssets.textContent = String(coverageSummary.regression_ready_asset_count || 0);
      els.gapAssets.textContent = String((coverageSummary.latest_run_coverage_status_counts || {}).gap || 0);

      const [coverageKey, coverageCount] = topPair(coverageSummary.latest_run_coverage_status_counts || {});
      els.summaryCoverage.textContent = coverageKey;
      els.summaryCoverageDesc.textContent = `最近运行最多的是 ${coverageKey}（${coverageCount} 条）`;

      const [selectionKey, selectionCount] = topPair(coverageSummary.selection_state_counts || {});
      els.summarySelection.textContent = selectionKey;
      els.summarySelectionDesc.textContent = `当前筛选窗口内 ${selectionKey} = ${selectionCount}`;

      const [pageKey, pageCount] = topPair(coverageSummary.page_counts || {});
      els.summaryPage.textContent = pageKey;
      els.summaryPageDesc.textContent = `页面 ${pageKey} 下共有 ${pageCount} 个资产`;

      const [sourceKey, sourceCount] = topPair(coverageSummary.source_type_counts || {});
      els.summarySource.textContent = sourceKey;
      els.summarySourceDesc.textContent = `来源 ${sourceKey} 下共有 ${sourceCount} 个资产`;
    }

    return {
      badge,
      displayRunId,
      escapeHtml,
      filteredItems,
      persistFilters,
      queryValues,
      refreshStamp,
      renderSummary,
      syncAdvancedFilters,
      updateFilterSummary,
      updateSelectionBar,
    };
  }

  window.createTestPointAssetsSupport = createTestPointAssetsSupport;
})();
