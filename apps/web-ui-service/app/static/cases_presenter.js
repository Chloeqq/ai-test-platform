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
    if (!normalized) return "未执行";
    if (normalized === "passed") return "通过";
    if (normalized === "failed") return "失败";
    if (normalized === "skipped") return "跳过";
    if (normalized === "running") return "执行中";
    if (normalized === "queued") return "排队中";
    if (normalized === "blocked") return "阻塞";
    if (normalized === "unknown") return "未知";
    return normalized || "-";
  }

  function displaySourceLabel(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "ai") return "AI生成";
    if (normalized === "mn") return "人工编写";
    if (normalized === "cv") return "人工复核";
    if (normalized === "imp") return "导入";
    if (normalized === "fb") return "Coverage";
    return normalized || "-";
  }

  function displayCaseId(value, fallback) {
    if (typeof window.platformDisplayCaseId === "function") {
      return window.platformDisplayCaseId(value || fallback || "");
    }
    return String(value || fallback || "").trim() || "-";
  }

  function detailHref(item) {
    const rawCaseId = String(item && item.case_id || "").trim();
    if (rawCaseId) return `/cases/${encodeURIComponent(rawCaseId)}`;
    return `/cases/${encodeURIComponent(String(item && item.id || "").trim())}`;
  }

  function toneOf(value) {
    return String(value || "unknown").trim().toLowerCase() || "unknown";
  }

  function statusIndicator(label, tone) {
    const normalizedTone = String(tone || "unknown").trim().toLowerCase() || "unknown";
    const icon =
      normalizedTone === "passed" || normalizedTone === "active"
        ? "✓"
        : normalizedTone === "failed" || normalizedTone === "deprecated"
          ? "✕"
          : normalizedTone === "skipped"
            ? "−"
            : "•";
    return `
      <span class="cases-status-indicator is-${escapeHtml(normalizedTone)}">
        <span class="cases-status-icon" aria-hidden="true">${icon}</span>
        <span class="cases-status-text">${escapeHtml(label || "-")}</span>
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

  function priorityBadge(value) {
    const normalized = String(value || "").trim().toUpperCase() || "P3";
    const tone = ["P0", "P1", "P2", "P3"].includes(normalized) ? normalized.toLowerCase() : "p3";
    return `<span class="cases-priority-badge is-${tone}">${escapeHtml(normalized)}</span>`;
  }

  function automationBadge(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "automated") {
      return '<span class="cases-automation-badge is-automated">自动化</span>';
    }
    if (normalized === "manual") {
      return '<span class="cases-automation-badge is-manual">手工</span>';
    }
    return '<span class="cases-automation-badge is-unknown">未知</span>';
  }

  function renderIcon(icon) {
    if (icon === "edit") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10-10-4-4L4 16v4z"></path><path d="M13 7l4 4"></path></svg>';
    if (icon === "tag") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12l8-8h8v8l-8 8-8-8z"></path><circle cx="16" cy="8" r="1.5"></circle></svg>';
    if (icon === "run") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5l11 7-11 7z"></path></svg>';
    if (icon === "approve") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12l5 5 11-11"></path></svg>';
    if (icon === "reject") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12"></path><path d="M18 6l-12 12"></path></svg>';
    if (icon === "delete") return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12"></path><path d="M9 7V5h6v2"></path><path d="M8 7l1 12h6l1-12"></path></svg>';
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7h12"></path><path d="M9 7V5h6v2"></path><path d="M8 7l1 12h6l1-12"></path></svg>';
  }

  function rowActionsMarkup(item, reviewMode) {
    if (reviewMode) {
      return `
        <div class="cases-row-actions">
          <button type="button" class="btn cases-inline-btn" data-row-action="run" data-case-id="${item.id}" title="执行用例">执行</button>
          <button type="button" class="btn cases-inline-btn" data-row-action="approve" data-case-id="${item.id}" title="审核通过">审核通过</button>
          <button type="button" class="btn cases-inline-btn" data-row-action="reject" data-case-id="${item.id}" title="驳回">驳回</button>
          <button type="button" class="btn cases-inline-btn cases-inline-danger" data-row-action="delete" data-case-id="${item.id}" title="删除">删除</button>
          <a class="cases-icon-btn is-edit" href="${detailHref(item)}" title="查看详情">${renderIcon("edit")}</a>
        </div>
      `;
    }
    return `
      <div class="cases-row-actions">
        <button type="button" class="cases-icon-btn is-tag" data-row-action="run" data-case-id="${item.id}" title="执行用例">${renderIcon("run")}</button>
        <a class="cases-icon-btn is-edit" href="${detailHref(item)}" title="查看详情">${renderIcon("edit")}</a>
        <button type="button" class="cases-icon-btn is-tag" data-row-action="tag" data-case-id="${item.id}" title="修改标签">${renderIcon("tag")}</button>
        <button type="button" class="cases-icon-btn is-archive" data-row-action="archive" data-case-id="${item.id}" title="废弃用例">${renderIcon("archive")}</button>
      </div>
    `;
  }

  function filterTreeItems(items, keyword, projectCode) {
    const normalizedItems = normalizeTreeItems(items, projectCode);
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

  function normalizeTreeItems(items, projectCode) {
    const projectFilter = String(projectCode || "").trim().toLowerCase();
    return (Array.isArray(items) ? items : []).map((group) => {
      const currentProjectCode = String(group && group.project_code || "").trim();
      if (projectFilter && currentProjectCode.toLowerCase() !== projectFilter) return null;
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
        project_code: currentProjectCode,
        product_line: String(group && group.product_line || ""),
        count: typeof group.count !== "undefined" ? group.count : fallbackCount,
        modules,
      };
    }).filter((group) => group && group.product_line);
  }

  function totalTreeCount(items, projectCode) {
    return normalizeTreeItems(items, projectCode).reduce((sum, group) => sum + (Number(group.count) || 0), 0);
  }

  function treeMarkup(items, keyword, selection, projectCode) {
    const filtered = filterTreeItems(items, keyword, projectCode);
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
    const projectCode = String(item.project_code || "").trim();
    const productLine = String(item.product_line || "").trim();
    const module = String(item.module || "").trim();
    if (!projectCode && !productLine && !module) return '<span class="cases-module-path is-empty">-</span>';
    const pathValue = `${projectCode || "-"} / ${productLine || "-"} / ${module || "-"}`;
    return `<span class="cases-module-path" title="${escapeHtml(pathValue)}">${escapeHtml(pathValue)}</span>`;
  }

  function searchContextEntries(context) {
    const source = context && typeof context === "object" ? context : {};
    return [
      ["project_code", "项目", (value) => value],
      ["product_line", "产品线", (value) => value],
      ["module", "模块", (value) => value],
      ["keyword", "关键词", (value) => value],
      ["priority", "优先级", (value) => value],
      ["test_type", "测试类型", displayTestType],
      ["status", "状态", displayStatusLabel],
      ["creator", "创建人", (value) => value],
      ["last_result", "执行结果", displayResultLabel],
      ["source", "来源", displaySourceLabel],
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
          <span
            class="cases-context-help"
            title="单搜索框条件和左侧模块树定位会统一展示在这里，点击标签右侧关闭按钮可移除单项条件。"
          >上下文说明</span>
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

  function tableRowsMarkup(items, selectedIds, options) {
    const reviewMode = Boolean(options && options.reviewMode);
    const selected = selectedIds instanceof Set ? selectedIds : new Set();
    if (!Array.isArray(items) || !items.length) {
      return '<tr class="cases-table-empty-row"><td colspan="13"><div class="cases-table-empty">当前筛选下暂无用例。可以前往 <a href="/ai-generation">AI生成</a> 创建 Draft，或手动新建草稿。</div></td></tr>';
    }
    return items.map((item) => `
      <tr>
        <td><input class="case-check" type="checkbox" data-id="${item.id}" ${selected.has(item.id) ? "checked" : ""}></td>
        <td><span class="cases-row-handle" aria-hidden="true"></span></td>
        <td><span class="mono cases-case-id">${escapeHtml(displayCaseId(item.case_id, item.id))}</span></td>
        <td>
          <div class="cases-row-name">
            <a href="${detailHref(item)}">${escapeHtml(item.name)}</a>
            <span class="cases-row-name-meta">${escapeHtml(displaySourceLabel(item.source))} · ${escapeHtml(displayTestType(item.test_type || ""))}</span>
          </div>
        </td>
        <td>${priorityBadge(item.priority)}</td>
        <td>${statusIndicator(displayStatusLabel(item.status), toneOf(item.status))}</td>
        <td>${statusIndicator(displayResultLabel(item.last_execution_result), toneOf(item.last_execution_result))}</td>
        <td>${automationBadge(item.automation_status)}</td>
        <td>${tagsMarkup(item.tags)}</td>
        <td>${versionMarkup(item.latest_version_no)}</td>
        <td>${modulePath(item)}</td>
        <td><span class="cases-time-cell">${escapeHtml(displayTime(item.updated_at))}</span></td>
        <td>${rowActionsMarkup(item, reviewMode)}</td>
      </tr>
    `).join("");
  }

  function tableLoadingMarkup() {
    return '<tr class="cases-table-empty-row"><td colspan="13"><div class="cases-table-loading">正在加载用例列表...</div></td></tr>';
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
