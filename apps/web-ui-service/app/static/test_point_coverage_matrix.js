(function () {
  const shell = document.getElementById("tp-matrix-shell");
  if (!shell) return;
  const assetId = shell.dataset.assetId || "";
  if (!assetId) return;

  const els = {
    covered: document.getElementById("tpm-covered"),
    partial: document.getElementById("tpm-partial"),
    gap: document.getElementById("tpm-gap"),
    orphan: document.getElementById("tpm-orphan"),
    tbody: document.getElementById("tpm-tbody"),
    selected: document.getElementById("tpm-selected-row"),
    refresh: document.getElementById("tpm-refresh"),
    filterStatus: document.getElementById("tpm-filter-status"),
    filterChangedArea: document.getElementById("tpm-filter-changed-area"),
    filterOrphanOnly: document.getElementById("tpm-filter-orphan-only"),
    backAsset: document.getElementById("tpm-back-asset"),
  };

  const state = { rows: [], selectedId: "" };

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

  function applyFilters(rows) {
    const status = String(els.filterStatus.value || "").trim().toLowerCase();
    const changedArea = String(els.filterChangedArea.value || "").trim().toLowerCase();
    const orphanOnly = String(els.filterOrphanOnly.value || "").trim();
    return rows.filter((row) => {
      const rowStatus = String(row.traceability_status || "").trim().toLowerCase();
      const areas = Array.isArray(row.changed_areas) ? row.changed_areas.map((item) => String(item || "").toLowerCase()) : [];
      if (status && rowStatus !== status) return false;
      if (changedArea && !areas.some((item) => item.includes(changedArea))) return false;
      if (orphanOnly === "1" && rowStatus !== "orphan") return false;
      return true;
    });
  }

  function renderSelected(row) {
    if (!row) {
      els.selected.innerHTML = '<div class="empty-state">先选择一行矩阵数据。</div>';
      return;
    }
    els.selected.innerHTML = `
      <div class="detail-highlight">
        <h3>${escapeHtml(row.row_id || "-")}</h3>
        <p>${escapeHtml(row.explanation || "暂无说明")}</p>
      </div>
      <article class="kv-item"><span>追溯状态</span><strong>${badge(row.traceability_status || "unknown")}</strong></article>
      <article class="kv-item"><span>Source IDs</span><p class="mono">${escapeHtml((row.source_ids || []).join(" / ") || "-")}</p></article>
      <article class="kv-item"><span>Intent IDs</span><p class="mono">${escapeHtml((row.intent_ids || []).join(" / ") || "-")}</p></article>
      <article class="kv-item"><span>Point Keys</span><p class="mono">${escapeHtml((row.point_keys || []).join(" / ") || "-")}</p></article>
      <article class="kv-item"><span>缺失 Point Keys</span><p class="mono">${escapeHtml((row.missing_point_keys || []).join(" / ") || "无")}</p></article>
      <article class="kv-item"><span>Changed Areas</span><p>${escapeHtml((row.changed_areas || []).join(" / ") || "-")}</p></article>
      <div class="button-row">
        <a class="action-link" href="/assets/test-points/${encodeURIComponent(assetId)}">返回资产详情</a>
      </div>
    `;
  }

  function renderTable() {
    const rows = applyFilters(state.rows);
    if (!rows.length) {
      els.tbody.innerHTML = '<tr><td colspan="6" class="empty-state">当前筛选条件下没有矩阵行。</td></tr>';
      renderSelected(null);
      return;
    }
    const selected = rows.find((row) => row.row_id === state.selectedId) || rows[0];
    state.selectedId = selected.row_id;
    els.tbody.innerHTML = rows.map((row) => `
      <tr class="${row.row_id === state.selectedId ? "is-active" : ""}" data-row-id="${escapeHtml(row.row_id)}">
        <td class="mono">${escapeHtml(row.row_id)}</td>
        <td>${badge(row.traceability_status || "unknown")}</td>
        <td>${escapeHtml((row.source_ids || []).join(" / ") || "-")}</td>
        <td>${escapeHtml((row.intent_ids || []).join(" / ") || "-")}</td>
        <td>${escapeHtml((row.point_keys || []).join(" / ") || "-")}</td>
        <td>${escapeHtml((row.changed_areas || []).join(" / ") || "-")}</td>
      </tr>
    `).join("");
    renderSelected(selected);
  }

  async function load() {
    els.backAsset.href = `/assets/test-points/${encodeURIComponent(assetId)}`;
    const response = await fetch(`/api/workbench/test-point-assets/${encodeURIComponent(assetId)}/coverage-matrix`, { cache: "no-store" });
    const payload = response.ok ? await response.json() : {};
    const item = payload.item || {};
    const summary = item.summary || {};
    state.rows = Array.isArray(item.rows) ? item.rows : [];
    els.covered.textContent = String(summary.covered_count || 0);
    els.partial.textContent = String(summary.partial_count || 0);
    els.gap.textContent = String(summary.gap_count || 0);
    els.orphan.textContent = String(summary.orphan_count || 0);
    renderTable();
  }

  els.refresh.addEventListener("click", renderTable);
  els.tbody.addEventListener("click", function (event) {
    const row = event.target.closest("tr[data-row-id]");
    if (!row) return;
    state.selectedId = row.dataset.rowId || "";
    renderTable();
  });

  load().catch((error) => {
    els.tbody.innerHTML = `<tr><td colspan="6" class="error-state">${escapeHtml(error.message || "加载覆盖矩阵失败")}</td></tr>`;
  });
})();
