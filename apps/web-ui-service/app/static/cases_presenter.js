(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function tagsMarkup(tags) {
    const rows = Array.isArray(tags) ? tags : [];
    if (!rows.length) return "-";
    return rows.map((tag) => '<span class="tag-pill">' + escapeHtml(tag) + "</span>").join("");
  }

  function buildSearchContextPills(searchContext) {
    const ctx = searchContext && typeof searchContext === "object" ? searchContext : {};
    const items = [];
    Object.entries(ctx).forEach(([key, value]) => {
      const text = String(value || "").trim();
      if (!text) return;
      items.push(
        '<button type="button" class="pill" data-remove-key="' +
          escapeHtml(key) +
          '">' +
          escapeHtml(key) +
          ": " +
          escapeHtml(text) +
          "</button>"
      );
    });
    return items.join("");
  }

  window.CasesPresenter = {
    tableLoadingMarkup() {
      return '<tr><td colspan="10" class="loading-state">正在加载用例列表...</td></tr>';
    },
    tableRowsMarkup(items, selectedIds) {
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) return '<tr><td colspan="10" class="empty-state">暂无数据</td></tr>';
      return rows
        .map((item) => {
          const id = Number(item.id || 0);
          const checked = selectedIds && selectedIds.has(id) ? " checked" : "";
          return (
            "<tr>" +
            '<td><input class="cases-row-check" type="checkbox" data-case-id="' +
            id +
            '"' +
            checked +
            "></td>" +
            "<td></td>" +
            "<td>" +
            id +
            "</td>" +
            "<td>" +
            escapeHtml(item.name || "-") +
            "</td>" +
            "<td>" +
            escapeHtml(item.status || "-") +
            " / " +
            escapeHtml(item.last_execution_result || "-") +
            "</td>" +
            "<td>" +
            tagsMarkup(item.tags || []) +
            "</td>" +
            "<td>" +
            escapeHtml(item.version || "-") +
            "</td>" +
            "<td>" +
            escapeHtml(item.module || "-") +
            "</td>" +
            "<td>" +
            escapeHtml(item.updated_at || "-") +
            "</td>" +
            '<td><div class="cases-row-actions">' +
            '<button type="button" class="btn cases-inline-btn" data-row-action="open" data-case-id="' +
            id +
            '">详情</button>' +
            '<button type="button" class="btn cases-inline-btn" data-row-action="delete" data-case-id="' +
            id +
            '">删除</button>' +
            "</div></td>" +
            "</tr>"
          );
        })
        .join("");
    },
    searchContextMarkup(searchContext) {
      const pills = buildSearchContextPills(searchContext);
      if (!pills) return "";
      return (
        '<span class="inline-tip">已生效筛选：</span>' +
        pills +
        '<button type="button" class="btn cases-inline-btn" data-clear-all-context="true">清空全部</button>'
      );
    },
  };
})();
