(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function displayTime(value) {
    return typeof window.platformFormatDateTime === "function" ? window.platformFormatDateTime(value) : String(value || "-");
  }

  function displayStatusLabel(value) {
    if (typeof window.platformDisplayStatus === "function") return window.platformDisplayStatus(value, "-");
    return String(value || "-");
  }

  function displayTestType(value) {
    if (typeof window.platformDisplayTestType === "function") return window.platformDisplayTestType(value, "-");
    return String(value || "-");
  }

  function displayResultLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "passed") return "通过";
    if (normalized === "failed") return "失败";
    if (normalized === "skipped") return "跳过";
    if (normalized === "unknown") return "未知";
    return normalized || "-";
  }

  function toneOf(value) {
    const normalized = String(value || "unknown").trim().toLowerCase() || "unknown";
    if (["passed", "active"].includes(normalized)) return "passed";
    if (["failed", "deprecated"].includes(normalized)) return "failed";
    if (["skipped", "inactive", "unknown"].includes(normalized)) return "unknown";
    return "unknown";
  }

  function statusIndicator(label, tone) {
    return `
      <span class="cases-status-indicator is-${escapeHtml(tone)}">
        <span class="cases-status-dot" aria-hidden="true"></span>
        <span>${escapeHtml(label || "-")}</span>
      </span>
    `;
  }

  function statusGroup(label, value, tone) {
    return `
      <span class="cases-status-group">
        <span class="cases-status-caption">${escapeHtml(label)}</span>
        ${statusIndicator(value, tone)}
      </span>
    `;
  }

  function renderIcon(icon) {
    if (icon === "edit") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10-10-4-4L4 16v4z"></path><path d="M13 7l4 4"></path></svg>';
    if (icon === "tag") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12l8-8h8v8l-8 8-8-8z"></path><circle cx="16" cy="8" r="1.5"></circle></svg>';
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12"></path><path d="M9 7V5h6v2"></path><path d="M8 7l1 12h6l1-12"></path></svg>';
  }

  function filterTreeItems(items, keyword) {
    const normalizedItems = normalizeTreeItems(items);
    const term = String(keyword || "").trim().toLowerCase();
    if (!term) return normalizedItems;
    return normalizedItems
      .map((group) => {
        const modules = Array.isArray(group.modules) ? group.modules : [];
        const matchedModules = modules.filter((item) => String(item.module || "").toLowerCase().includes(term));
        if (String(group.product_line || "").toLowerCase().includes(term)) return group;
        if (!matchedModules.length) return null;
        return { ...group, modules: matchedModules };
      })
      .filter(Boolean);
  }

  function normalizeTreeItems(items) {
    return (Array.isArray(items) ? items : []).map((group) => {
      const modules = (Array.isArray(group.modules) ? group.modules : [])
        .map((item) => {
          if (typeof item === "string") return { module: item, count: "" };
          return {
            module: String(item && item.module || ""),
            count: item && typeof item.count !== "undefined" ? item.count : "",
          };
        })
        .filter((item) => item.module);
      const countedModules = modules.reduce((sum, item) => sum + (Number(item.count) || 0), 0);
      const fallbackCount = countedModules || modules.length;
      return {
        product_line: String(group && group.product_line || ""),
        count: typeof group.count !== "undefined" ? group.count : fallbackCount,
        modules,
      };
    }).filter((group) => group.product_line);
  }

  function totalTreeCount(items) {
    return normalizeTreeItems(items).reduce((sum, group) => sum + (Number(group.count) || 0), 0);
  }

  function treeMarkup(items, keyword, selection) {
    const filtered = filterTreeItems(items, keyword);
    const active = selection || {};
    if (!filtered.length) return '<div class="cases-tree-empty">没有匹配的模块目录。</div>';
    const total = totalTreeCount(filtered);
    return [
      `<button type="button" class="cases-tree-root ${!active.product_line && !active.module ? "is-active" : ""}" data-tree-action="all">`,
      '<span class="cases-tree-label"><strong>全部用例</strong><span>显示所有模块下的用例资产</span></span>',
      `<span class="cases-tree-count">${total}</span>`,
      "</button>",
    ].join("") + filtered.map((group) => `
      <details class="cases-tree-group ${active.product_line === group.product_line && !active.module ? "is-active" : ""}" open>
        <summary data-tree-action="product-line" data-product-line="${escapeHtml(group.product_line)}">
          <span class="cases-tree-label"><strong>${escapeHtml(group.product_line)}</strong><span>按产品线快速定位</span></span>
          <span class="cases-tree-count">${escapeHtml(group.count)}</span>
        </summary>
        <div class="cases-tree-modules">
          ${(Array.isArray(group.modules) ? group.modules : []).map((item) => `
            <button
              type="button"
              class="cases-tree-module-button ${active.product_line === group.product_line && active.module === item.module ? "is-active" : ""}"
              data-tree-action="module"
              data-product-line="${escapeHtml(group.product_line)}"
              data-module="${escapeHtml(item.module)}"
            >
              <span class="cases-tree-label"><strong>${escapeHtml(item.module)}</strong><span>模块内用例</span></span>
              <span class="cases-tree-count">${escapeHtml(item.count)}</span>
            </button>
          `).join("")}
        </div>
      </details>
    `).join("");
  }

  function tagsMarkup(values) {
    const items = Array.isArray(values) ? values.filter(Boolean).slice(0, 2) : [];
    if (!items.length) return '<span class="cases-tag is-empty">-</span>';
    return `<div class="cases-tag-list">${items.map((item) => `<span class="cases-tag">${escapeHtml(item)}</span>`).join("")}</div>`;
  }

  function versionMarkup(value) {
    const versionNo = Number(value || 0);
    if (!versionNo) return '<span class="cases-version-badge is-empty">-</span>';
    return `<span class="cases-version-badge">v${escapeHtml(versionNo)}</span>`;
  }

  function modulePath(item) {
    const productLine = String(item.product_line || "").trim();
    const module = String(item.module || "").trim();
    if (!productLine && !module) return '<span class="cases-module-path is-empty">-</span>';
    return `<span class="cases-module-path">${escapeHtml(productLine)} / ${escapeHtml(module)}</span>`;
  }

  function resultStack(item) {
    return `
      <div class="cases-result-stack">
        ${statusGroup("状态", displayStatusLabel(item.status), toneOf(item.status))}
        ${statusGroup("结果", displayResultLabel(item.last_execution_result), toneOf(item.last_execution_result))}
      </div>
    `;
  }

  function searchContextEntries(context) {
    const source = context && typeof context === "object" ? context : {};
    return [
      ["product_line", "产品线", (value) => value],
      ["module", "模块", (value) => value],
      ["keyword", "关键词", (value) => value],
      ["test_type", "测试类型", displayTestType],
      ["status", "状态", displayStatusLabel],
      ["creator", "创建人", (value) => value],
      ["last_result", "执行结果", displayResultLabel],
    ]
      .map(([key, label, formatter]) => {
        const rawValue = String(source[key] || "").trim();
        if (!rawValue) return null;
        return {
          key,
          label,
          value: formatter(rawValue),
        };
      })
      .filter(Boolean);
  }

  function searchContextMarkup(context) {
    const entries = searchContextEntries(context);
    if (!entries.length) return "";
    return `
      <div class="cases-context-meta">
        <span>当前搜索上下文</span>
        <div class="cases-context-meta-actions">
          <p>单搜索框条件和左侧模块树定位会统一展示在这里，点击标签右侧关闭按钮可移除单项条件。</p>
          <button
            type="button"
            class="cases-context-clear"
            data-clear-all-context="true"
            aria-label="清空全部搜索上下文"
          >清空全部</button>
        </div>
      </div>
      <div class="cases-context-pills">
        ${entries.map((item) => `
          <span class="cases-context-pill">
            <strong>${escapeHtml(item.label)}</strong>${escapeHtml(item.value)}
            <button
              type="button"
              class="cases-context-remove"
              data-remove-key="${escapeHtml(item.key)}"
              aria-label="移除${escapeHtml(item.label)}条件"
              title="移除${escapeHtml(item.label)}条件"
            >×</button>
          </span>
        `).join("")}
      </div>
    `;
  }

  function tableRowsMarkup(items, selectedIds) {
    const selected = selectedIds instanceof Set ? selectedIds : new Set();
    if (!Array.isArray(items) || !items.length) {
      return '<tr class="cases-table-empty-row"><td colspan="10"><div class="cases-table-empty">当前筛选下暂无用例。可以前往 <a href="/ai-generation">AI生成</a> 创建 Draft，或手动新建草稿。</div></td></tr>';
    }
    return items.map((item) => `
      <tr>
        <td><input class="case-check" type="checkbox" data-id="${item.id}" ${selected.has(item.id) ? "checked" : ""}></td>
        <td><span class="cases-row-handle" aria-hidden="true"></span></td>
        <td>${escapeHtml(item.id)}</td>
        <td>
          <div class="cases-row-name">
            <a href="/cases/${item.id}">${escapeHtml(item.name)}</a>
            <span class="cases-row-name-meta">${escapeHtml(displayTestType(item.test_type))} · ${escapeHtml(item.priority || "-")}</span>
          </div>
        </td>
        <td>${resultStack(item)}</td>
        <td>${tagsMarkup(item.tags)}</td>
        <td>${versionMarkup(item.latest_version_no)}</td>
        <td>${modulePath(item)}</td>
        <td><span class="cases-time-cell">${escapeHtml(displayTime(item.updated_at))}</span></td>
        <td>
          <div class="cases-row-actions">
            <a class="cases-icon-btn is-edit" href="/cases/${item.id}" title="查看详情">${renderIcon("edit")}</a>
            <button type="button" class="cases-icon-btn is-tag" data-row-action="tag" data-case-id="${item.id}" title="修改标签">${renderIcon("tag")}</button>
            <button type="button" class="cases-icon-btn is-archive" data-row-action="archive" data-case-id="${item.id}" title="废弃用例">${renderIcon("archive")}</button>
          </div>
        </td>
      </tr>
    `).join("");
  }

  function tableLoadingMarkup() {
    return '<tr class="cases-table-empty-row"><td colspan="10"><div class="cases-table-loading">正在加载用例列表...</div></td></tr>';
  }

  window.CasesPresenter = {
    escapeHtml,
    searchContextMarkup,
    tableLoadingMarkup,
    tableRowsMarkup,
    totalTreeCount,
    treeMarkup,
  };
})();
