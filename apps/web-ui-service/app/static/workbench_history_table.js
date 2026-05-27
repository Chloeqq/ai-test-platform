(function () {
  function renderRows(rows, selectedKey, selectedIds, detailHelper) {
    return rows.map((item) => {
      const rowId = detailHelper.rowKey(item);
      const checked = selectedIds.has(rowId) ? "checked" : "";
      const riskGate = (item.risk_summary && typeof item.risk_summary === "object" ? item.risk_summary.gate_decision : "") || "";
      const selfHealing = (item.self_healing_summary && typeof item.self_healing_summary === "object" ? item.self_healing_summary.status : "") || "";
      return `
        <tr class="${rowId === selectedKey ? "is-active" : ""}" data-history-row="${detailHelper.escapeHtml(rowId)}">
          <td class="selection-col"><input class="wb-history-check" type="checkbox" data-history-row="${detailHelper.escapeHtml(rowId)}" ${checked} aria-label="选择记录"></td>
          <td>${detailHelper.escapeHtml(detailHelper.formatTime(item.timestamp))}</td>
          <td>${detailHelper.buildActionLink(item)}</td>
          <td><div class="table-title">${detailHelper.escapeHtml(detailHelper.displayCaseId(item.case_id || "-"))}</div><div class="table-subtitle mono">${detailHelper.escapeHtml(detailHelper.displayRunId(item.run_id || "-"))}</div></td>
          <td>${detailHelper.escapeHtml(item.page || "-")}</td>
          <td>${detailHelper.renderBadge(item.status || "unknown", "unknown")}</td>
          <td>${detailHelper.escapeHtml(item.actor_display || item.confirmed_by || "-")}</td>
          <td>${riskGate ? detailHelper.renderBadge(riskGate, "unknown") : "-"}</td>
          <td>${selfHealing ? detailHelper.renderBadge(selfHealing, "unknown") : "-"}</td>
        </tr>
      `;
    }).join("");
  }

  window.WorkbenchHistoryTable = { renderRows };
})();
