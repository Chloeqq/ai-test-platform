(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function buildWorkbenchHref(item) {
    const params = new URLSearchParams();
    const runId = String(item?.run_id || "").trim();
    const project = String(item?.project || "").trim();
    if (runId) {
      params.set("run_id", runId);
    }
    if (project) {
      params.set("project", project);
    }
    const query = params.toString();
    return query ? `/execution/workbench?${query}` : "/execution/workbench";
  }

  function renderDetail(item, helpers) {
    if (!item) {
      return '<div class="empty-state">先选择一条执行任务。</div>';
    }
    const summary = item.multisource_summary || {};
    const evidence = item.evidence_health || {};
    const freshness = item.evidence_freshness || {};
    const retry = item.retry || {};
    const dependency = item.dependency || {};
    return `
      <div class="detail-highlight">
        <h3>${escapeHtml(helpers.displayRunId(item.run_id || item.task_id || "-"))}</h3>
        <p>case=${escapeHtml(helpers.displayCaseId(item.case_id || "-"))} ｜ page=${escapeHtml(item.page || "-")} ｜ runner=${escapeHtml(item.runner || "-")}</p>
      </div>
      <article class="kv-item"><span>状态</span><strong>${helpers.badge(item.status || "unknown")}</strong><p class="meta-text">queue=${escapeHtml(item.queue_status || "-")} ｜ source=${escapeHtml(item.source || "-")}</p></article>
      <article class="kv-item"><span>证据健康</span><strong>${helpers.badge(evidence.status || "unknown")}</strong><p class="meta-text">${escapeHtml(evidence.reason || "-")}</p></article>
      <article class="kv-item"><span>证据时效</span><strong>${helpers.badge(freshness.status || "unknown")}</strong><p class="meta-text">${escapeHtml(freshness.reason || "-")}</p></article>
      <article class="kv-item"><span>Strict-mode</span><strong>${helpers.badge(item.strict_mode?.status || "unknown")}</strong><p class="meta-text">${escapeHtml(item.strict_mode?.reason || "-")}</p></article>
      <article class="kv-item"><span>多源摘要</span><strong>${escapeHtml(summary.source_count ?? 0)} 路输入</strong><p class="meta-text">traceability=${escapeHtml(summary.traceability_status || "-")} ｜ changed_areas=${escapeHtml((summary.changed_areas || []).join(" / ") || "-")}</p></article>
      <article class="kv-item"><span>重试 / 依赖</span><strong>retry=${escapeHtml(retry.enabled ? "true" : "false")}</strong><p class="meta-text">dependencies=${escapeHtml(dependency.dependency_count ?? 0)} ｜ scopes=${escapeHtml((summary.recommended_regression_scope || []).join(" / ") || "-")}</p></article>
      <div class="button-row">
        <a class="action-link" href="${buildWorkbenchHref(item)}">去调试工作台</a>
        <a class="action-link" href="/execution/results">查看执行结果</a>
      </div>
    `;
  }

  function renderRow(item, selectedTaskId, selectedIds, helpers) {
    const workbenchHref = buildWorkbenchHref(item);
    const menu = window.ListPage && typeof window.ListPage.renderRowMenu === "function"
      ? window.ListPage.renderRowMenu([
        { href: workbenchHref, label: "调试任务" },
        { href: "/execution/results", label: "执行结果" },
        { href: `/execution/results/${encodeURIComponent(item.run_id || item.task_id || "")}`, label: "结果详情" },
      ])
      : "-";
    return `
      <tr class="${String(item.task_id) === selectedTaskId ? "is-active" : ""}" data-task-id="${escapeHtml(item.task_id)}">
        <td class="selection-col"><input class="er-check" type="checkbox" data-task-id="${escapeHtml(item.task_id)}" ${selectedIds.has(String(item.task_id)) ? "checked" : ""} aria-label="选择任务"></td>
        <td><div class="table-title">${escapeHtml(helpers.displayRunId(item.run_id || item.task_id || "-"))}</div><div class="table-subtitle mono">case · ${escapeHtml(helpers.displayCaseId(item.case_id || "-"))}</div></td>
        <td>${helpers.badge(item.status || "unknown")}</td>
        <td>${helpers.badge(item.queue_status || "unknown")}</td>
        <td>${helpers.badge(item.source || "unknown")}</td>
        <td>${helpers.badge(item.evidence_health?.status || "unknown")}</td>
        <td>${helpers.badge(item.strict_mode?.status || "unknown")}</td>
        <td>${escapeHtml(helpers.formatTime(item.finished_at || item.started_at || item.created_at || "-"))}</td>
        <td class="row-actions-col">${menu}</td>
      </tr>
    `;
  }

  window.ExecutionRunsPresenter = {
    renderDetail,
    renderRow,
  };
})();
