(function () {
  function statusClass(status) {
    const value = String(status || "").trim().toLowerCase();
    if (value === "failed" || value === "rejected" || value === "error") return "failed";
    if (value === "passed" || value === "confirmed" || value === "success") return "passed";
    return "unknown";
  }

  function safeText(value, helper) {
    const text = String(value || "").trim();
    return helper.escapeHtml(text || "-");
  }

  function renderRows(rows, selectedKey, selectedIds, helper) {
    return rows
      .map((item) => {
        const key = helper.rowKey(item);
        const activeClass = key === selectedKey ? " wb-history-row-active" : "";
        const checked = selectedIds.has(key) ? " checked" : "";
        const status = String(item.status || "").trim();
        const runId = String(item.run_id || "").trim();
        const caseId = String(item.case_id || "").trim();
        const page = String(item.page || "").trim();
        const actor = String(item.actor || item.reviewer || "").trim();
        const riskGate = String(item.risk_gate_decision || item.risk_gate || "-").trim();
        const selfHealing = String(item.self_healing_status || "-").trim();
        const statusHtml =
          '<span class="wb-history-status ' + statusClass(status) + '">' + helper.escapeHtml(status || "unknown") + "</span>";
        return (
          '<tr data-history-row="' +
          helper.escapeHtml(key) +
          '" class="' +
          activeClass.trim() +
          '">' +
          '<td><input class="wb-history-check" type="checkbox" data-history-row="' +
          helper.escapeHtml(key) +
          '"' +
          checked +
          "></td>" +
          "<td>" +
          safeText(item.timestamp || item.created_at, helper) +
          "</td>" +
          "<td>" +
          safeText(item.action, helper) +
          "</td>" +
          "<td>" +
          '<div class="wb-history-inline-meta">' +
          "Case: " +
          safeText(caseId, helper) +
          "<br>Run: " +
          safeText(runId, helper) +
          "</div>" +
          "</td>" +
          "<td>" +
          safeText(page, helper) +
          "</td>" +
          "<td>" +
          statusHtml +
          "</td>" +
          "<td>" +
          safeText(actor, helper) +
          "</td>" +
          "<td>" +
          safeText(riskGate, helper) +
          "</td>" +
          "<td>" +
          safeText(selfHealing, helper) +
          "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  window.WorkbenchHistoryTable = {
    renderRows: renderRows,
  };
})();
