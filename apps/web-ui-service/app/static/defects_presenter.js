(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderSelected(item, helpers) {
    if (!item) {
      return '<div class="empty-state">先选择一条缺陷记录。</div>';
    }
    return `
      <article class="kv-item"><span>缺陷编号</span><strong>${escapeHtml(item.defect_id || "-")}</strong></article>
      <article class="kv-item"><span>系统</span><strong>${escapeHtml(item.system || "-")}</strong></article>
      <article class="kv-item"><span>关联用例</span><strong>${escapeHtml(helpers.displayCaseId(item.case_id || "-"))}</strong></article>
      <article class="kv-item"><span>备注</span><p>${escapeHtml(item.note || "暂无备注")}</p></article>
      <article class="kv-item"><span>缺陷链接</span><p class="mono">${escapeHtml(item.defect_url || "-")}</p></article>
      <div class="button-row">
        ${item.defect_url ? `<a class="action-link" href="${escapeHtml(item.defect_url)}" target="_blank" rel="noreferrer">打开缺陷链接</a>` : ""}
        <a class="action-link" href="/execution/results/failures?case_id=${encodeURIComponent(helpers.normalizeCaseId(item.case_id || ""))}">查看失败详情</a>
        <a class="action-link" href="/cases/${encodeURIComponent(item.case_id || "")}">查看用例</a>
      </div>
    `;
  }

  function renderRow(item, selectedKey, selectedKeys, helpers) {
    const rowKey = `${item.case_id}:${item.defect_id}`;
    const menu = window.ListPage && typeof window.ListPage.renderRowMenu === "function"
      ? window.ListPage.renderRowMenu([
        item.defect_url ? { href: item.defect_url, label: "打开缺陷", target: "_blank", rel: "noreferrer" } : null,
        { href: `/execution/results/failures?case_id=${encodeURIComponent(helpers.normalizeCaseId(item.case_id || ""))}`, label: "失败详情" },
        { href: `/cases/${encodeURIComponent(item.case_id || "")}`, label: "查看用例" },
      ])
      : "-";
    return `
      <tr class="${rowKey === selectedKey ? "is-active" : ""}" data-defect-key="${escapeHtml(rowKey)}">
        <td class="selection-col"><input class="def-check" type="checkbox" data-defect-key="${escapeHtml(rowKey)}" ${selectedKeys.has(rowKey) ? "checked" : ""} aria-label="选择缺陷"></td>
        <td><div class="table-title">${escapeHtml(item.defect_id || "-")}</div><div class="table-subtitle mono">${escapeHtml(item.defect_url || "-")}</div></td>
        <td>${escapeHtml(item.system || "-")}</td>
        <td>${escapeHtml(helpers.displayCaseId(item.case_id || "-"))}</td>
        <td>${escapeHtml(item.note || "-")}</td>
        <td>${escapeHtml(helpers.formatDateTime(item.linked_at || "-"))}</td>
        <td class="row-actions-col">${menu}</td>
      </tr>
    `;
  }

  window.DefectsPresenter = {
    renderRow,
    renderSelected,
  };
})();
