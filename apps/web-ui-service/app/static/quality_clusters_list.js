(function () {
  const shared = window.qualityClustersShared;
  const createDetailController = window.createQualityClustersDetailController;
  if (!shared || typeof createDetailController !== "function") return;

  function createQualityClustersListController(options) {
    const { els, state, persistFilters, syncQueryToUrl } = options;
    const detailController = createDetailController({ els, state });

    function updateFilterOptions(selectEl, rows, keyField, allLabel) {
      if (!selectEl) return;
      const previousValue = String(selectEl.value || "");
      const keys = [];
      for (const row of Array.isArray(rows) ? rows : []) {
        if (!row || typeof row !== "object") continue;
        const key = String(row[keyField] || "").trim();
        if (!key || keys.includes(key)) continue;
        keys.push(key);
      }
      selectEl.innerHTML =
        `<option value="">${allLabel}</option>` +
        keys.map((key) => `<option value="${shared.escapeHtml(key)}">${shared.escapeHtml(key)}</option>`).join("");
      if (previousValue && keys.includes(previousValue)) {
        selectEl.value = previousValue;
      }
    }

    function buildClusterQuery() {
      const params = new URLSearchParams();
      params.set("limit", String(Number(els.limitSelect?.value || 200) || 200));
      params.set("max_clusters", String(Number(els.maxClustersSelect?.value || 20) || 20));
      if (String(els.queueFilterSelect?.value || "").trim()) params.set("queue", String(els.queueFilterSelect.value).trim());
      if (String(els.classFilterSelect?.value || "").trim()) params.set("failure_class", String(els.classFilterSelect.value).trim());
      if (String(els.severityFilterSelect?.value || "").trim()) params.set("severity", String(els.severityFilterSelect.value).trim());
      return params.toString();
    }

    function filteredClusters() {
      const keyword = String(els.keywordFilter?.value || "").trim().toLowerCase();
      const manualReviewOnly = String(els.manualReviewSelect?.value || "").trim() === "1";
      const items = state.clusters.filter((item) => {
        if (!item || typeof item !== "object") return false;
        if (manualReviewOnly && Number(item.requires_manual_review_count || 0) <= 0) return false;
        if (!keyword) return true;
        const haystack = [
          item.cluster_id,
          item.failure_class,
          item.queue,
          item.owner_team,
          item.latest_case_id,
          item.bucket_key,
          ...(Array.isArray(item.sample_cases) ? item.sample_cases.map((sample) => sample?.case_id) : []),
        ]
          .map((entry) => String(entry || "").toLowerCase())
          .join(" ");
        return haystack.includes(keyword);
      });
      return window.ListPage
        ? window.ListPage.sortItems(items, els.sortKey?.value || "last_seen_at", els.sortDir?.value || "desc", {
          cluster_id: { get: (item) => item.cluster_id || "", type: "string" },
          failure_class: { get: (item) => item.failure_class || "", type: "string" },
          queue: { get: (item) => item.queue || "", type: "string" },
          severity: { get: (item) => shared.severityRank(item.severity), type: "number" },
          manual_review: { get: (item) => item.manual_review_ratio || item.requires_manual_review_count || 0, type: "number" },
          last_seen_at: { get: (item) => item.last_seen_at || "", type: "date" },
        })
        : items;
    }

    function updateHeroMetrics(items) {
      const rows = Array.isArray(items) ? items : [];
      const totalFailed = rows.reduce((sum, item) => sum + (Number(item.occurrence_count || 0) || 0), 0);
      const manualReviewClusters = rows.filter((item) => Number(item.requires_manual_review_count || 0) > 0).length;
      const hotspotCounter = new Map();
      rows.forEach((item) => {
        const key = String(item.failure_class || "unknown").trim() || "unknown";
        hotspotCounter.set(key, (hotspotCounter.get(key) || 0) + (Number(item.occurrence_count || 0) || 0));
      });
      let topKey = "";
      let topCount = 0;
      hotspotCounter.forEach((count, key) => {
        if (count > topCount) {
          topKey = key;
          topCount = count;
        }
      });
      els.kpiTotalFailed.textContent = String(totalFailed);
      els.kpiTotalClusters.textContent = String(rows.length);
      els.kpiManualReviewClusters.textContent = String(manualReviewClusters);
      els.kpiTopHotspot.textContent = topKey || "-";
      els.kpiTopHotspotDesc.textContent = topKey ? `${topCount} 次失败归到该热点原因` : "当前筛选条件下暂无热点原因";
    }

    function updateFilterSummary(items) {
      const active = [
        els.keywordFilter.value && `关键词 ${els.keywordFilter.value.trim()}`,
        els.queueFilterSelect.value && `队列 ${els.queueFilterSelect.value.trim()}`,
        els.classFilterSelect.value && `故障类 ${els.classFilterSelect.value.trim()}`,
        els.severityFilterSelect.value && `严重级别 ${els.severityFilterSelect.value.trim()}`,
        els.manualReviewSelect.value === "1" && "仅人工复核",
        els.qgAlertFilterInput.value && `门禁告警码 ${els.qgAlertFilterInput.value.trim()}`,
        els.qgPageFilterInput.value && `门禁页面 ${els.qgPageFilterInput.value.trim()}`,
      ].filter(Boolean);
      els.filterSummary.textContent = active.length
        ? `当前筛选：${active.join(" / ")}，命中 ${items.length} 个聚类`
        : `当前按默认规则展示全部聚类，共 ${items.length} 个`;
    }

    function updateSelectionBar() {
      const count = state.selectedIds.size;
      els.selectionBar.hidden = count === 0;
      els.selectionCopy.textContent = `已选择 ${count} 项`;
    }

    function renderTable() {
      const items = filteredClusters();
      updateHeroMetrics(items);
      updateFilterSummary(items);

      const pager = typeof window.platformPaginateItems === "function"
        ? window.platformPaginateItems(items, state.page, state.pageSize)
        : { items, page: 1, pageSize: items.length || 10, totalItems: items.length, totalPages: 1 };
      state.page = pager.page;
      state.pageSize = pager.pageSize;

      if (!pager.items.length) {
        els.tbody.innerHTML = '<tr><td colspan="8" class="empty-state">当前筛选条件下没有失败聚类。</td></tr>';
        els.checkAll.checked = false;
      } else {
        els.tbody.innerHTML = pager.items
          .map((item) => {
            const clusterId = String(item.cluster_id || "").trim();
            const checked = state.selectedIds.has(clusterId) ? "checked" : "";
            const actionMenu = window.ListPage && typeof window.ListPage.renderRowMenu === "function"
              ? window.ListPage.renderRowMenu([
                { href: `/quality/failure-clusters?cluster_id=${encodeURIComponent(clusterId)}`, label: "查看详情" },
                { href: "/quality/gates", label: "质量门禁" },
                { href: "/defects", label: "缺陷管理" },
              ])
              : "-";
            return `
              <tr class="${clusterId === state.selectedClusterId ? "is-active" : ""}" data-cluster-id="${shared.escapeHtml(clusterId)}">
                <td class="selection-col"><input class="cluster-check" type="checkbox" data-cluster-id="${shared.escapeHtml(clusterId)}" ${checked} aria-label="选择聚类"></td>
                <td><div class="table-title">${shared.escapeHtml(clusterId || "-")}</div><div class="table-subtitle">最新用例 · ${shared.escapeHtml(shared.displayCaseId(item.latest_case_id || "-"))}</div></td>
                <td>${shared.escapeHtml(item.failure_class || "-")}</td>
                <td>${shared.escapeHtml(item.queue || "-")}</td>
                <td>${shared.renderSeverityBadge(item.severity || "S4")}</td>
                <td>${shared.escapeHtml(String(item.requires_manual_review_count || 0))}</td>
                <td>${shared.escapeHtml(shared.formatTime(item.last_seen_at))}</td>
                <td class="row-actions-col">${actionMenu}</td>
              </tr>
            `;
          })
          .join("");
        const currentIds = pager.items.map((item) => String(item.cluster_id || "").trim()).filter(Boolean);
        els.checkAll.checked = currentIds.length > 0 && currentIds.every((id) => state.selectedIds.has(id));
      }

      if (typeof window.platformRenderSimplePagination === "function") {
        window.platformRenderSimplePagination(
          els.footer,
          {
            page: pager.page,
            pageSize: pager.pageSize,
            totalItems: pager.totalItems,
            totalPages: pager.totalPages,
          },
          (nextPage, nextPageSize) => {
            state.page = nextPage;
            state.pageSize = nextPageSize;
            renderTable();
          }
        );
      }

      els.tbody.querySelectorAll(".cluster-check").forEach((checkbox) => {
        checkbox.addEventListener("click", (event) => event.stopPropagation());
        checkbox.addEventListener("change", () => {
          const clusterId = String(checkbox.dataset.clusterId || "").trim();
          if (!clusterId) return;
          if (checkbox.checked) state.selectedIds.add(clusterId);
          else state.selectedIds.delete(clusterId);
          updateSelectionBar();
        });
      });
      updateSelectionBar();
    }

    async function loadClusters() {
      els.tbody.innerHTML = '<tr><td colspan="8" class="loading-state">正在加载失败聚类...</td></tr>';
      const response = await fetch(`/failures/clusters?${buildClusterQuery()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("失败聚类加载失败");
      const payload = await response.json();
      state.clusters = Array.isArray(payload.clusters) ? payload.clusters : [];
      updateFilterOptions(els.queueFilterSelect, payload.queue_distribution, "queue", "全部队列");
      updateFilterOptions(els.classFilterSelect, payload.class_distribution, "failure_class", "全部故障类");
      updateFilterOptions(els.severityFilterSelect, payload.severity_distribution, "severity", "全部级别");
      renderTable();

      const currentItems = filteredClusters();
      const exists = currentItems.some((item) => String(item.cluster_id || "").trim() === state.selectedClusterId);
      if (!exists) {
        state.selectedClusterId = String(currentItems[0]?.cluster_id || "").trim();
        renderTable();
      }
      syncQueryToUrl();
      if (state.selectedClusterId) {
        await detailController.loadClusterDetail(state.selectedClusterId);
      } else {
        detailController.renderDetail(null);
      }
    }

    function bindFilterInputs(refresh) {
      [els.queueFilterSelect, els.classFilterSelect, els.severityFilterSelect, els.manualReviewSelect, els.limitSelect, els.maxClustersSelect].forEach((node) => {
        node?.addEventListener("change", () => {
          state.page = 1;
          refresh().catch(console.error);
        });
      });

      [els.qgAlertFilterInput, els.qgPageFilterInput].forEach((node) => node?.addEventListener("input", persistFilters));
    }

    function bindTableEvents() {
      els.tbody.addEventListener("click", (event) => {
        if (!(event.target instanceof HTMLElement)) return;
        const row = event.target.closest("[data-cluster-id]");
        if (!row) return;
        const clusterId = String(row.getAttribute("data-cluster-id") || "").trim();
        if (!clusterId) return;
        state.selectedClusterId = clusterId;
        renderTable();
        syncQueryToUrl();
        detailController.loadClusterDetail(clusterId).catch((error) => {
          console.error(error);
          els.detailPanel.innerHTML = '<div class="error-state">聚类详情加载失败，请稍后重试。</div>';
        });
      });
      els.checkAll.addEventListener("change", () => {
        const currentIds = Array.from(els.tbody.querySelectorAll(".cluster-check"))
          .map((node) => String(node.dataset.clusterId || "").trim())
          .filter(Boolean);
        if (els.checkAll.checked) currentIds.forEach((id) => state.selectedIds.add(id));
        else currentIds.forEach((id) => state.selectedIds.delete(id));
        renderTable();
      });
      els.copySelectionBtn.addEventListener("click", async () => {
        const text = Array.from(state.selectedIds).join("\n");
        const copied = await shared.copyText(text);
        els.selectionCopy.textContent = copied ? `已复制 ${state.selectedIds.size} 个聚类 ID` : `复制失败，请手动复制 ${state.selectedIds.size} 个聚类 ID`;
      });
      els.copyCaseSelectionBtn.addEventListener("click", async () => {
        const caseIds = state.clusters
          .filter((item) => state.selectedIds.has(String(item.cluster_id || "").trim()))
          .map((item) => String(item.latest_case_id || "").trim())
          .filter(Boolean)
          .join("\n");
        const copied = await shared.copyText(caseIds);
        els.selectionCopy.textContent = copied ? `已复制 ${state.selectedIds.size} 个最新用例 ID` : `复制失败，请手动复制 ${state.selectedIds.size} 个最新用例 ID`;
      });
    }

    return {
      bindFilterInputs,
      bindTableEvents,
      loadClusters,
    };
  }

  window.createQualityClustersListController = createQualityClustersListController;
})();
