(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function rowKey(item) {
    const runId = String(item?.run_id || "").trim();
    const action = String(item?.action || "").trim();
    const ts = String(item?.timestamp || item?.created_at || "").trim();
    return runId + "::" + action + "::" + ts;
  }

  function safeText(value, fallback) {
    const text = String(value || "").trim();
    return text || fallback;
  }

  function formatStatus(status) {
    const value = safeText(status, "unknown").toLowerCase();
    return '<span class="wb-history-status ' + escapeHtml(value) + '">' + escapeHtml(value) + "</span>";
  }

  function renderSummaryPanel(summary) {
    const data = summary && typeof summary === "object" ? summary : {};
    const blocks = [
      ["记录总数", data.total_items ?? 0],
      ["高频动作", data.top_action?.value || "-"],
      ["高频门禁", data.top_risk_gate?.value || "-"],
      ["高频自愈", data.top_self_healing_status?.value || "-"],
    ];
    return (
      '<section class="wb-history-summary">' +
      '<div class="wb-history-summary-grid">' +
      blocks
        .map((row) => {
          return (
            '<article class="wb-history-summary-card">' +
            '<span class="wb-history-summary-label">' +
            escapeHtml(row[0]) +
            "</span>" +
            "<strong>" +
            escapeHtml(row[1]) +
            "</strong>" +
            "</article>"
          );
        })
        .join("") +
      "</div>" +
      "</section>"
    );
  }

  function renderDetailPanel(item) {
    if (!item || typeof item !== "object") {
      return '<div class="empty-state">先选择一条操作历史。</div>';
    }
    const blocks = [
      ["动作", safeText(item.action, "-")],
      ["状态", safeText(item.status, "-")],
      ["用例", safeText(item.case_id, "-")],
      ["Run ID", safeText(item.run_id, "-")],
      ["页面", safeText(item.page, "-")],
      ["确认人", safeText(item.actor || item.reviewer, "-")],
      ["时间", safeText(item.timestamp || item.created_at, "-")],
    ];
    const note = safeText(item.detail_summary || item.note || item.reason, "");
    return (
      '<section class="wb-history-detail">' +
      '<div class="wb-history-detail-block">' +
      '<span class="wb-history-detail-label">状态</span>' +
      formatStatus(item.status) +
      "</div>" +
      blocks
        .map((row) => {
          return (
            '<div class="wb-history-detail-line"><strong>' +
            escapeHtml(row[0]) +
            ":</strong> <span>" +
            escapeHtml(row[1]) +
            "</span></div>"
          );
        })
        .join("") +
      (note ? '<p class="wb-history-detail-note">' + escapeHtml(note) + "</p>" : "") +
      "</section>"
    );
  }

  window.workbenchHistoryDetail = {
    escapeHtml: escapeHtml,
    renderDetailPanel: renderDetailPanel,
    renderSummaryPanel: renderSummaryPanel,
    rowKey: rowKey,
  };
})();
