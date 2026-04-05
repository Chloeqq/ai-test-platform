(function () {
  const shell = document.getElementById("gate-console-shell");
  if (!shell) return;

  const authFetch = window.platformAuthFetch || window.fetch.bind(window);
  const els = {
    threshold: document.getElementById("gate-threshold"),
    blocked24h: document.getElementById("gate-blocked-24h"),
    blockRate24h: document.getElementById("gate-block-rate-24h"),
    pendingApprovals: document.getElementById("gate-pending-approvals"),
    configCards: document.getElementById("gate-config-cards"),
    topAlertCode: document.getElementById("gate-top-alert-code"),
    topAlertReason: document.getElementById("gate-top-alert-reason"),
    historyTbody: document.getElementById("gate-history-tbody"),
    historySummary: document.getElementById("gate-history-summary"),
    historyFooter: document.getElementById("gate-history-footer"),
    lastUpdated: document.getElementById("gate-last-updated"),
    filterKeyword: document.getElementById("gate-filter-keyword"),
    searchClear: document.getElementById("gate-search-clear"),
    searchButton: document.getElementById("gate-search"),
    filterAction: document.getElementById("gate-filter-action"),
    filterApproval: document.getElementById("gate-filter-approval"),
    advancedFilters: document.getElementById("gate-advanced-filters"),
    applyFilters: document.getElementById("gate-apply-filters"),
    historyRefresh: document.getElementById("gate-history-refresh"),
    historyReset: document.getElementById("gate-history-reset"),
    project: document.getElementById("gate-project"),
    runId: document.getElementById("gate-run-id"),
    page: document.getElementById("gate-page"),
    caseId: document.getElementById("gate-case-id"),
    decision: document.getElementById("gate-decision"),
    note: document.getElementById("gate-note"),
    saveBtn: document.getElementById("gate-save-btn"),
    approveBtn: document.getElementById("gate-approve-btn"),
    revokeBtn: document.getElementById("gate-revoke-btn"),
    feedback: document.getElementById("gate-action-feedback"),
  };

  const state = {
    historyItems: [],
    page: 1,
    pageSize: 10,
  };
  const storageKey = "gate_history_filters_v1";
  const filterFields = {
    keyword: els.filterKeyword,
    action: els.filterAction,
    approval: els.filterApproval,
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

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function displayRunId(value) {
    if (typeof window.platformDisplayRunId === "function") return window.platformDisplayRunId(value);
    return String(value || "").trim() || "-";
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`请求失败: ${url}`);
    return response.json();
  }

  function filteredHistory() {
    const keyword = String(els.filterKeyword.value || "").trim().toLowerCase();
    const action = String(els.filterAction.value || "").trim().toLowerCase();
    const approval = String(els.filterApproval.value || "").trim().toLowerCase();
    return state.historyItems.filter((row) => {
      if (keyword) {
        const haystack = [row.run_id, row.page, row.action, row.detail_summary, row.case_id]
          .map((entry) => String(entry || "").toLowerCase())
          .join(" ");
        if (!haystack.includes(keyword)) return false;
      }
      if (action && !String(row.action || "").toLowerCase().includes(action)) return false;
      if (approval && !String(row.approval_status || "").toLowerCase().includes(approval)) return false;
      return true;
    });
  }

  function persistFilters() {
    if (typeof window.platformWriteFilterState === "function") {
      window.platformWriteFilterState(storageKey, filterFields);
    }
    if (els.advancedFilters) els.advancedFilters.open = Boolean(String(els.filterApproval.value || "").trim());
  }

  function renderConfig(config, qualityGate, historyItems) {
    const item = config.item || {};
    const summary = (qualityGate.item || {}).summary_24h || {};
    const blockerDistribution = (qualityGate.item || {}).blocker_distribution || [];
    const pending = historyItems.filter((row) => String(row.approval_status || "").trim().toLowerCase() === "pending");
    els.threshold.textContent = String(item.block_missing_required_threshold || "-");
    els.blocked24h.textContent = String(summary.blocked_events || 0);
    els.blockRate24h.textContent = `${Math.round(Number(summary.block_rate || 0) * 100)}%`;
    els.pendingApprovals.textContent = String(pending.length);
    els.configCards.innerHTML = `
      <article class="stat-card"><h3>block_on_failed_status</h3><strong>${String(Boolean(item.block_on_failed_status))}</strong><p>失败状态是否默认触发阻断。</p></article>
      <article class="stat-card"><h3>block_on_risk_block</h3><strong>${String(Boolean(item.block_on_risk_block))}</strong><p>风险评估 block 是否自动升级为执行门禁阻断。</p></article>
      <article class="stat-card"><h3>warn_on_pending_reviews</h3><strong>${String(Boolean(item.warn_on_pending_reviews))}</strong><p>如果 review 仍未确认，是否只给 warning。</p></article>
      <article class="stat-card"><h3>dual_approval_enabled</h3><strong>${String(Boolean(item.dual_approval_enabled))}</strong><p>当前是否启用二次审批。</p></article>
    `;
    const topAlert = blockerDistribution[0] || {};
    els.topAlertCode.textContent = `当前热点告警码：${topAlert.alert_code || "-"}`;
    els.topAlertReason.textContent = topAlert.alert_code
      ? `最近 24 小时 ${topAlert.alert_code} 出现 ${topAlert.count || 0} 次，可优先围绕该告警做输入治理。`
      : "最近 24 小时暂无明显门禁阻断热点。";
  }

  function renderHistory() {
    const filtered = filteredHistory();
    const active = [];
    if (els.filterKeyword.value.trim()) active.push(`关键词 ${els.filterKeyword.value.trim()}`);
    if (els.filterAction.value.trim()) active.push(`动作 ${els.filterAction.value.trim()}`);
    if (els.filterApproval.value.trim()) active.push(`审批 ${els.filterApproval.value.trim()}`);
    if (els.advancedFilters) els.advancedFilters.open = Boolean(els.filterApproval.value.trim());
    els.historySummary.textContent = active.length
      ? `当前筛选：${active.join(" / ")}，展示 ${filtered.length} 条门禁历史`
      : `当前按默认顺序展示最近门禁决策，共 ${filtered.length} 条历史记录`;

    const pager = typeof window.platformPaginateItems === "function"
      ? window.platformPaginateItems(filtered, state.page, state.pageSize)
      : { items: filtered, page: 1, pageSize: filtered.length || 10, totalItems: filtered.length, totalPages: 1 };
    state.page = pager.page;
    state.pageSize = pager.pageSize;

    if (!pager.items.length) {
      els.historyTbody.innerHTML = '<tr><td colspan="7" class="empty-state">当前没有可展示的门禁历史。</td></tr>';
    } else {
      els.historyTbody.innerHTML = pager.items.map((row) => `
        <tr>
          <td>${escapeHtml(formatTime(row.timestamp || "-"))}</td>
          <td>${escapeHtml(row.action || "-")}</td>
          <td>
            <div class="table-title mono">${escapeHtml(displayRunId(row.run_id || "-"))}</div>
            <div class="table-subtitle">${escapeHtml(row.page || "-")}</div>
          </td>
          <td>${badge(row.decision || "unknown")}</td>
          <td>${badge(row.approval_status || "n/a")}</td>
          <td>${escapeHtml(row.actor_display || row.confirmed_by || "-")}</td>
          <td>${escapeHtml(row.detail_summary || "-")}</td>
        </tr>
      `).join("");
    }
    if (typeof window.platformRenderSimplePagination === "function") {
      window.platformRenderSimplePagination(els.historyFooter, {
        page: pager.page,
        pageSize: pager.pageSize,
        totalItems: pager.totalItems,
        totalPages: pager.totalPages,
      }, (nextPage, nextPageSize) => {
        state.page = nextPage;
        state.pageSize = nextPageSize;
        renderHistory();
      });
    }
    if (typeof window.platformFormatRefreshTime === "function") {
      els.lastUpdated.textContent = window.platformFormatRefreshTime(new Date().toISOString());
    }
  }

  function currentPayload() {
    return {
      project: String(els.project.value || "default").trim() || "default",
      run_id: String(els.runId.value || "").trim(),
      page: String(els.page.value || "").trim(),
      case_id: typeof window.platformNormalizeCaseId === "function" ? window.platformNormalizeCaseId(els.caseId.value || "") : String(els.caseId.value || "").trim(),
      decision: String(els.decision.value || "manual_review").trim(),
      note: String(els.note.value || "").trim(),
    };
  }

  async function postAction(url, body) {
    els.feedback.textContent = "正在提交...";
    const response = await authFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || payload.error || "提交失败";
      throw new Error(String(detail));
    }
    els.feedback.textContent = `已完成：${url.split("/").pop()}`;
    return payload;
  }

  async function load() {
    const [config, qualityGate, history] = await Promise.all([
      fetchJson("/api/workbench/execution-gate/config"),
      fetchJson("/api/workbench/quality-gates/summary?limit=100"),
      fetchJson("/api/workbench/history?limit=80"),
    ]);
    state.historyItems = Array.isArray(history.items)
      ? history.items.filter((row) => String(row.action || "").startsWith("execution_gate_"))
      : [];
    renderConfig(config, qualityGate, state.historyItems);
    renderHistory();
  }

  [els.filterKeyword, els.filterAction, els.filterApproval].forEach((node) => {
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.page = 1;
        persistFilters();
        renderHistory();
      }
    });
    node.addEventListener("input", persistFilters);
  });
  els.searchButton.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderHistory();
  });
  els.applyFilters.addEventListener("click", () => {
    state.page = 1;
    persistFilters();
    renderHistory();
  });
  els.historyRefresh.addEventListener("click", load);
  els.historyReset.addEventListener("click", () => {
    els.filterKeyword.value = "";
    els.filterAction.value = "";
    els.filterApproval.value = "";
    state.page = 1;
    if (typeof window.platformClearFilterState === "function") window.platformClearFilterState(storageKey);
    if (els.advancedFilters) els.advancedFilters.open = false;
    renderHistory();
  });
  els.saveBtn.addEventListener("click", () => {
    postAction("/api/workbench/execution-gate/decisions", currentPayload()).then(load).catch((error) => {
      els.feedback.textContent = error.message || "保存决策失败";
    });
  });
  els.approveBtn.addEventListener("click", () => {
    const body = currentPayload();
    postAction("/api/workbench/execution-gate/decisions/approve", { project: body.project, run_id: body.run_id, page: body.page, note: body.note })
      .then(load)
      .catch((error) => {
        els.feedback.textContent = error.message || "审批失败";
      });
  });
  els.revokeBtn.addEventListener("click", () => {
    const body = currentPayload();
    postAction("/api/workbench/execution-gate/decisions/revoke", { project: body.project, run_id: body.run_id, page: body.page, note: body.note })
      .then(load)
      .catch((error) => {
        els.feedback.textContent = error.message || "撤销失败";
      });
  });

  if (window.ListPage) {
    window.ListPage.mountSearchField({
      input: els.filterKeyword,
      clearButton: els.searchClear,
      onSearch: () => {
        state.page = 1;
        persistFilters();
        renderHistory();
      },
    });
  }
  if (typeof window.platformRestoreFilterState === "function") {
    window.platformRestoreFilterState(storageKey, filterFields);
  }
  persistFilters();

  load().catch((error) => {
    els.historyTbody.innerHTML = `<tr><td colspan="7" class="error-state">${escapeHtml(error.message || "加载门禁页失败")}</td></tr>`;
  });
})();
