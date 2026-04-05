(function () {
  function escapeHtml(value) {
    if (typeof window.platformEscapeHtml === "function") return window.platformEscapeHtml(value);
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderSelected(item, helpers) {
    if (!item) {
      return '<div class="empty-state">先选择一条测试点资产。</div>';
    }
    const traceability = item.traceability_summary || {};
    const coverage = traceability.coverage || {};
    const review = traceability.review || {};
    const gate = traceability.gate || {};
    const risk = traceability.risk || {};
    const semantic = traceability.semantic || {};
    const latestRun = item.latest_run || {};
    return `
      <div class="detail-highlight">
        <h3>${escapeHtml(item.title || item.asset_id)}</h3>
        <p>${escapeHtml(item.page || "-")} ｜ ${escapeHtml(item.source_type || "-")} ｜ confidence ${escapeHtml(item.confidence ?? "-")}</p>
      </div>
      <div class="kv-list">
        <article class="kv-item"><span>选择状态</span><strong>${helpers.badge((item.selection_summary || {}).selection_state || "unknown")}</strong></article>
        <article class="kv-item"><span>覆盖状态</span><strong>${helpers.badge(coverage.latest_run_status || coverage.asset_status || "unknown")}</strong><p class="meta-text">missing_count=${escapeHtml(coverage.missing_count ?? 0)}</p></article>
        <article class="kv-item"><span>评审状态</span><strong>${helpers.badge(review.test_point_status || "unknown")}</strong><p class="meta-text">pending=${escapeHtml(review.pending_sections ?? 0)} ｜ actor=${escapeHtml(review.latest_actor_display || "-")}</p></article>
        <article class="kv-item"><span>门禁状态</span><strong>${helpers.badge(gate.effective_decision || gate.decision || "unknown")}</strong><p class="meta-text">${escapeHtml(gate.gate_reason_summary || "暂无门禁说明")}</p></article>
        <article class="kv-item"><span>风险摘要</span><strong>${escapeHtml(risk.risk_level || "-")}</strong><p class="meta-text">top factor=${escapeHtml((risk.top_factor || {}).factor || "-")}</p></article>
        <article class="kv-item"><span>语义摘要</span><strong>${escapeHtml(semantic.page_type || "-")}</strong><p class="meta-text">${escapeHtml(semantic.primary_goal || semantic.business_domain || "-")}</p></article>
        <article class="kv-item"><span>最近运行</span><strong>${helpers.badge(latestRun.status || coverage.latest_run_status || "unknown")}</strong><p class="meta-text">${escapeHtml(helpers.displayRunId(latestRun.run_id || "-"))}</p></article>
      </div>
      <div class="button-row">
        <a class="action-link" href="/assets/test-points/${encodeURIComponent(item.asset_id)}">查看资产详情</a>
        <a class="action-link" href="/assets/test-points/${encodeURIComponent(item.asset_id)}/matrix">查看覆盖矩阵</a>
        <a class="action-link" href="/execution/runs?page=${encodeURIComponent(item.page || "")}">查看执行记录</a>
      </div>
    `;
  }

  function renderRow(item, selectedId, selectedIds, helpers) {
    const traceability = item.traceability_summary || {};
    const gate = traceability.gate || {};
    const coverage = traceability.coverage || {};
    const latestRun = item.latest_run || {};
    const menu = window.ListPage && typeof window.ListPage.renderRowMenu === "function"
      ? window.ListPage.renderRowMenu([
        { href: `/assets/test-points/${encodeURIComponent(item.asset_id)}`, label: "资产详情" },
        { href: `/assets/test-points/${encodeURIComponent(item.asset_id)}/matrix`, label: "覆盖矩阵" },
        { href: `/execution/runs?page=${encodeURIComponent(item.page || "")}`, label: "执行记录" },
      ])
      : "-";
    return `
      <tr class="${selectedId === item.asset_id ? "is-active" : ""}" data-asset-id="${escapeHtml(item.asset_id)}">
        <td class="selection-col"><input class="tp-assets-check" type="checkbox" data-asset-id="${escapeHtml(item.asset_id)}" ${selectedIds.has(item.asset_id) ? "checked" : ""} aria-label="选择资产"></td>
        <td>
          <div class="table-title">${escapeHtml(item.title || item.asset_id)}</div>
          <div class="table-subtitle mono">${escapeHtml(item.asset_id)}</div>
        </td>
        <td>${escapeHtml(item.page || "-")}</td>
        <td>${helpers.badge(item.source_type || "unknown")}</td>
        <td>${escapeHtml(item.point_count ?? 0)}</td>
        <td>${helpers.badge((item.selection_summary || {}).selection_state || "unknown")}</td>
        <td>${helpers.badge(gate.effective_decision || "unknown")}</td>
        <td><div class="table-title">${helpers.badge(latestRun.status || coverage.latest_run_status || "unknown")}</div><div class="table-subtitle mono">${escapeHtml(helpers.displayRunId(latestRun.run_id || "-"))}</div></td>
        <td class="row-actions-col">${menu}</td>
      </tr>
    `;
  }

  window.TestPointAssetsPresenter = {
    renderRow,
    renderSelected,
  };
})();
