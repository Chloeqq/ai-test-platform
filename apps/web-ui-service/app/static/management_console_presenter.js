(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderBadge(value) {
    if (typeof window.platformRenderBadge === "function") return window.platformRenderBadge(value, "default");
    const text = String(value || "default").trim() || "default";
    const cls = text.toLowerCase().replaceAll(/[^a-z0-9_]+/g, "_");
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function renderDetail(item) {
    if (!item) return "";
    const detailSections = Array.isArray(item.detail_sections) ? item.detail_sections : [];
    const actions = Array.isArray(item.detail_actions) ? item.detail_actions : [];
    return `
      <h3>${escapeHtml(item.detail_title || item.title || "-")}</h3>
      <p>${escapeHtml(item.detail_description || item.meta || "-")}</p>
      ${item.status || item.badge ? `<div class="management-detail-badges">${renderBadge(item.status || item.badge)}</div>` : ""}
      ${item.detail_bullets && item.detail_bullets.length ? `
        <ul class="management-detail-list">
          ${item.detail_bullets.map((bullet) => `<li>${escapeHtml(bullet)}</li>`).join("")}
        </ul>
      ` : ""}
      ${detailSections.length ? `
        <div class="management-detail-sections">
          ${detailSections.map((section) => `
            <article class="management-detail-section">
              <strong>${escapeHtml(section.title || section.label || "-")}</strong>
              <p>${escapeHtml(section.body || section.value || "-")}</p>
            </article>
          `).join("")}
        </div>
      ` : ""}
      ${actions.length ? `
        <div class="button-row">
          ${actions.map((action) => `<a class="btn btn-soft" href="${escapeHtml(action.href || "#")}">${escapeHtml(action.label || "查看")}</a>`).join("")}
        </div>
      ` : ""}
    `;
  }

  function renderListItem(item, activeId, selectedIds) {
    return `
      <article class="management-list-item ${String(item.id) === activeId ? "is-active" : ""}" data-management-id="${escapeHtml(item.id)}">
        <div class="management-list-main">
          <input class="management-check" type="checkbox" data-management-id="${escapeHtml(item.id)}" ${selectedIds.has(String(item.id)) ? "checked" : ""} aria-label="选择记录">
          <button type="button" class="management-item-trigger" data-management-id="${escapeHtml(item.id)}">
            <span class="management-list-title">${escapeHtml(item.title || "-")}</span>
            <span class="management-list-meta">${escapeHtml(item.meta || "-")}</span>
            <span class="management-list-tags">${(Array.isArray(item.tags) ? item.tags : []).map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("")}</span>
          </button>
        </div>
        <div class="management-list-side">
          ${item.status || item.badge ? renderBadge(item.status || item.badge) : ""}
          <span class="management-list-time">${escapeHtml(formatTime(item.updated_at || ""))}</span>
        </div>
      </article>
    `;
  }

  window.ManagementConsolePresenter = {
    escapeHtml,
    renderDetail,
    renderListItem,
  };
})();
