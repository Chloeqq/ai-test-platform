(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function populateSelect(select, values, label) {
    const current = String(select.value || "");
    select.innerHTML = [`<option value="">${label}</option>`]
      .concat(values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`))
      .join("");
    select.value = current;
  }

  function populateFilterOptions(items, nodes) {
    populateSelect(
      nodes.status,
      Array.from(new Set(items.map((item) => String(item.status || "").trim()).filter(Boolean))).sort(),
      "全部状态"
    );
    populateSelect(
      nodes.queue,
      Array.from(new Set(items.map((item) => String(item.queue_status || "").trim()).filter(Boolean))).sort(),
      "全部队列状态"
    );
    populateSelect(
      nodes.source,
      Array.from(new Set(items.map((item) => String(item.source || "").trim()).filter(Boolean))).sort(),
      "全部来源"
    );
  }

  function currentFilters(nodes) {
    return {
      keyword: String(nodes.keyword.value || "").trim(),
      project: String(nodes.project.value || "").trim(),
      status: String(nodes.status.value || "").trim(),
      queue: String(nodes.queue.value || "").trim(),
      source: String(nodes.source.value || "").trim(),
      evidence: String(nodes.evidence.value || "").trim(),
      strict: String(nodes.strict.value || "").trim(),
      retry: String(nodes.retry.value || "").trim(),
      dependency: String(nodes.dependency.value || "").trim(),
      sortKey: String(nodes.sortKey.value || "finished_at").trim(),
      sortDir: String(nodes.sortDir.value || "desc").trim(),
    };
  }

  function buildTaskParams(nodes) {
    const params = new URLSearchParams({ limit: "300" });
    [
      ["project_code", nodes.project],
      ["status", nodes.status],
      ["queue_status", nodes.queue],
      ["source", nodes.source],
      ["evidence_health_status", nodes.evidence],
      ["strict_mode_status", nodes.strict],
      ["retry_enabled", nodes.retry],
      ["has_dependencies", nodes.dependency],
    ].forEach(([key, node]) => {
      const value = String(node.value || "").trim();
      if (value) params.set(key, value);
    });
    return params;
  }

  function filterAndSortItems(items, filters, listPage) {
    const keyword = filters.keyword.toLowerCase();
    const project = filters.project.toLowerCase();
    const status = filters.status.toLowerCase();
    const queue = filters.queue.toLowerCase();
    const source = filters.source.toLowerCase();
    const filtered = items.filter((item) => {
      const haystack = [
        item.task_id,
        item.run_id,
        item.case_id,
        item.project_code,
        item.project,
        item.page,
        item.runner,
        item.queue,
        item.queue_status,
        item.source,
        ...(item.multisource_summary?.changed_areas || []),
        ...(item.multisource_summary?.source_types || []),
      ]
        .map((entry) => String(entry || "").toLowerCase())
        .join(" ");
      if (keyword && !haystack.includes(keyword)) return false;
      if (project && String(item.project_code || item.project || "").toLowerCase() !== project) return false;
      if (status && String(item.status || "").toLowerCase() !== status) return false;
      if (queue && String(item.queue_status || "").toLowerCase() !== queue) return false;
      if (source && String(item.source || "").toLowerCase() !== source) return false;
      return true;
    });

    return listPage.sortItems(filtered, filters.sortKey || "finished_at", filters.sortDir || "desc", {
      run_id: { get: (item) => item.run_id || item.task_id || "", type: "date" },
      status: { get: (item) => item.status || "", type: "string" },
      queue_status: { get: (item) => item.queue_status || "", type: "string" },
      source: { get: (item) => item.source || "", type: "string" },
      evidence_health: { get: (item) => item.evidence_health?.status || "", type: "string" },
      strict_mode: { get: (item) => item.strict_mode?.status || "", type: "string" },
      finished_at: { get: (item) => item.finished_at || item.started_at || item.created_at || "", type: "date" },
    });
  }

  function filterSummary(filters, count) {
    const active = [
      filters.keyword && `关键词 ${filters.keyword}`,
      filters.project && `项目 ${filters.project}`,
      filters.status && `状态 ${filters.status}`,
      filters.queue && `队列 ${filters.queue}`,
      filters.source && `来源 ${filters.source}`,
      filters.evidence && `证据 ${filters.evidence}`,
      filters.strict && `Strict ${filters.strict}`,
      filters.retry && `重试 ${filters.retry}`,
      filters.dependency && `依赖 ${filters.dependency}`,
    ].filter(Boolean);

    if (active.length) {
      return `当前筛选：${active.join(" / ")}，命中 ${count} 条任务`;
    }
    return `当前按默认条件展示执行任务，共 ${count} 条`;
  }

  window.ExecutionRunsSupport = {
    buildTaskParams,
    currentFilters,
    filterAndSortItems,
    filterSummary,
    populateFilterOptions,
  };
})();
