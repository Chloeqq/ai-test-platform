(function () {
  const shared = window.qualityClustersShared;
  if (!shared) return;

  function createQualityClustersGatePanel(options) {
    const { els, state, buildQuery, persistFilters, syncQueryToUrl } = options;

    function setText(node, value) {
      if (node) node.textContent = value;
    }

    function renderAlertList(summary) {
      const distribution = Array.isArray(summary.blocker_distribution) ? summary.blocker_distribution : [];
      if (!distribution.length) {
        els.qgAlertList.innerHTML = '<li class="empty-state">当前窗口没有 quality gate 阻断分布。</li>';
        return;
      }
      els.qgAlertList.innerHTML = distribution
        .slice(0, 6)
        .map((item) => {
          const code = String(item.alert_code || "").trim();
          const active = state.selectedAlertCode === code ? "is-active" : "";
          return `
            <li class="cluster-alert-item ${active}" data-alert-code="${shared.escapeHtml(code)}">
              <div class="cluster-card-head">
                <strong>${shared.escapeHtml(code || "-")}</strong>
                <span>${shared.renderBadge(item.severity || "unknown", "unknown")}</span>
              </div>
              <div class="cluster-card-meta">
                <span>分类 ${shared.escapeHtml(item.category || "-")}</span>
                <span>阻断 ${shared.escapeHtml(String(item.count || 0))} 次</span>
              </div>
            </li>
          `;
        })
        .join("");
    }

    function renderSuggestion(summary) {
      const details = Array.isArray(summary.alert_details) ? summary.alert_details : [];
      const recentBlocked = Array.isArray(summary.recent_blocked) ? summary.recent_blocked : [];
      const detail = details.find((item) => String(item.alert_code || "").trim() === state.selectedAlertCode) || null;

      if (!detail) {
        setText(els.qgDetailSubtitle, "当前筛选条件下暂无可展示的门禁修复建议。");
        els.qgSuggestionList.innerHTML = '<li class="empty-state">暂无建议</li>';
        els.qgRecentBlockedList.innerHTML = recentBlocked.length
          ? recentBlocked
              .slice(0, 6)
              .map(
                (item) => `
                  <li class="cluster-sample-item">
                    <div class="cluster-card-head">
                      <strong>${shared.escapeHtml(shared.displayCaseId(item.case_id || item.page || "-"))}</strong>
                      <span>${shared.escapeHtml(shared.formatTime(item.timestamp))}</span>
                    </div>
                    <div class="cluster-card-meta">
                      <span>stage=${shared.escapeHtml(item.stage || "-")}</span>
                      <span>alerts=${shared.escapeHtml((item.blocker_alert_codes || []).join(",") || "-")}</span>
                    </div>
                  </li>
                `
              )
              .join("")
          : '<li class="empty-state">暂无阻断样本</li>';
        return;
      }

      const remediation = detail.remediation && typeof detail.remediation === "object" ? detail.remediation : {};
      setText(
        els.qgDetailSubtitle,
        `${detail.code || "-"} ｜ ${detail.category || "-"} ｜ ${detail.severity || "-"} ｜ ${detail.count || 0} 次`
      );
      els.qgSuggestionList.innerHTML = `
        <li class="cluster-sample-item">
          <div class="cluster-card-head">
            <strong>${shared.escapeHtml(remediation.title || "修复建议")}</strong>
            <span>${shared.escapeHtml(remediation.priority || "-")}</span>
          </div>
          <p class="meta-text">${shared.escapeHtml(remediation.suggestion || "-")}</p>
          <div class="cluster-card-meta">
            <span>责任角色 ${shared.escapeHtml(remediation.owner || "-")}</span>
            <span>alert_code ${shared.escapeHtml(detail.alert_code || "-")}</span>
          </div>
        </li>
      `;

      const samples = Array.isArray(detail.samples) ? detail.samples : [];
      els.qgRecentBlockedList.innerHTML = samples.length
        ? samples
            .slice(0, 6)
            .map((item) => {
              const caseId = String(item.case_id || "").trim();
              const href = caseId ? `/report/failures?case_id=${encodeURIComponent(caseId)}` : "";
              return `
                <li class="cluster-sample-item">
                  <div class="cluster-card-head">
                    <strong>${shared.escapeHtml(shared.displayCaseId(caseId || item.page || "-"))}</strong>
                    <span>${shared.escapeHtml(shared.formatTime(item.timestamp))}</span>
                  </div>
                  <p class="meta-text">stage=${shared.escapeHtml(item.stage || "-")} ｜ action=${shared.escapeHtml(item.action || "-")}</p>
                  <p class="meta-text">reason=${shared.escapeHtml(item.message || "-")}</p>
                  ${href ? `<a class="action-link" href="${href}" target="_blank" rel="noreferrer">查看失败样本</a>` : '<span class="cluster-empty-inline">当前样本无可跳转 case_id</span>'}
                </li>
              `;
            })
            .join("")
        : '<li class="empty-state">当前告警暂无阻断样本</li>';
    }

    function render() {
      const summary = state.qualityGateSummary && typeof state.qualityGateSummary === "object" ? state.qualityGateSummary : {};
      const totalEvents = Number(summary.total_events || 0);
      const blockedEvents = Number(summary.blocked_events || 0);
      const blockRate = Number(summary.block_rate || 0);
      const distribution = Array.isArray(summary.blocker_distribution) ? summary.blocker_distribution : [];
      const top = distribution[0] || {};

      setText(els.qgTotalEvents, String(totalEvents));
      setText(els.qgBlockedEvents, String(blockedEvents));
      setText(els.qgBlockRate, `${Math.round(blockRate * 100)}%`);
      setText(els.qgBlockRateDesc, `${blockedEvents}/${totalEvents} 次事件触发阻断`);
      setText(els.qgTopAlert, String(top.alert_code || "-"));
      setText(els.qgTopAlertCount, top.alert_code ? `${top.count || 0} 次阻断命中` : "暂无门禁分布");

      if (!state.selectedAlertCode && top.alert_code) {
        state.selectedAlertCode = String(top.alert_code || "").trim();
      }
      renderAlertList(summary);
      renderSuggestion(summary);
    }

    function renderLoading() {
      setText(els.qgTotalEvents, "-");
      setText(els.qgBlockedEvents, "-");
      setText(els.qgBlockRate, "-");
      setText(els.qgBlockRateDesc, "正在加载门禁统计");
      setText(els.qgTopAlert, "-");
      setText(els.qgTopAlertCount, "正在加载门禁统计");
      els.qgAlertList.innerHTML = '<li class="loading-state">正在加载门禁阻断分布...</li>';
      els.qgSuggestionList.innerHTML = '<li class="loading-state">正在加载门禁修复建议...</li>';
      els.qgRecentBlockedList.innerHTML = '<li class="loading-state">正在加载门禁阻断样本...</li>';
    }

    function renderError(message) {
      setText(els.qgBlockRateDesc, message || "门禁数据加载失败");
      setText(els.qgTopAlertCount, "请稍后重试");
      els.qgAlertList.innerHTML = `<li class="error-state">${shared.escapeHtml(message || "门禁数据加载失败")}</li>`;
      els.qgSuggestionList.innerHTML = '<li class="error-state">门禁建议加载失败</li>';
      els.qgRecentBlockedList.innerHTML = '<li class="error-state">门禁样本加载失败</li>';
    }

    async function load() {
      renderLoading();
      const response = await fetch(`/api/workbench/quality-gates/summary?${buildQuery()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("quality gate 数据加载失败");
      const payload = await response.json();
      state.qualityGateSummary = payload.item || {};
      const distribution = Array.isArray(state.qualityGateSummary.blocker_distribution)
        ? state.qualityGateSummary.blocker_distribution
        : [];
      const currentExists = distribution.some((item) => String(item.alert_code || "").trim() === state.selectedAlertCode);
      if (!currentExists) {
        state.selectedAlertCode = String(els.qgAlertFilterInput?.value || "").trim() || String(distribution[0]?.alert_code || "").trim();
      }
      render();
    }

    function bindEvents() {
      els.qgAlertList.addEventListener("click", (event) => {
        if (!(event.target instanceof HTMLElement)) return;
        const row = event.target.closest("[data-alert-code]");
        if (!row) return;
        const alertCode = String(row.getAttribute("data-alert-code") || "").trim();
        if (!alertCode) return;
        state.selectedAlertCode = alertCode;
        if (els.qgAlertFilterInput) {
          els.qgAlertFilterInput.value = alertCode;
        }
        persistFilters();
        syncQueryToUrl();
        render();
      });
    }

    return {
      bindEvents,
      load,
      renderError,
    };
  }

  window.createQualityClustersGatePanel = createQualityClustersGatePanel;
})();
