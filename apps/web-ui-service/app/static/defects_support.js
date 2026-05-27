(function () {
  function normalizeCaseId(value) {
    if (typeof window.platformNormalizeCaseId === "function") {
      return window.platformNormalizeCaseId(value);
    }
    return String(value || "").trim();
  }

  function filters(nodes) {
    return {
      keyword: String(nodes.filterKeyword.value || "").trim().toLowerCase(),
      system: String(nodes.filterSystem.value || "").trim().toLowerCase(),
    };
  }

  function applyFilters(items, nodes, listPage) {
    const current = filters(nodes);
    const filtered = items.filter((item) => {
      const defectId = String(item.defect_id || "").trim().toLowerCase();
      const system = String(item.system || "").trim().toLowerCase();
      const caseId = normalizeCaseId(item.case_id || "");
      const haystack = [defectId, system, caseId, String(item.note || "").trim().toLowerCase()].join(" ");
      if (current.keyword && !haystack.includes(current.keyword)) return false;
      if (current.system && !system.includes(current.system)) return false;
      return true;
    });
    return listPage.sortItems(filtered, nodes.sortKey.value || "linked_at", nodes.sortDir.value || "desc", {
      defect_id: { get: (item) => item.defect_id || "", type: "string" },
      system: { get: (item) => item.system || "", type: "string" },
      case_id: { get: (item) => normalizeCaseId(item.case_id || ""), type: "string" },
      linked_at: { get: (item) => item.linked_at || "", type: "date" },
    });
  }

  function filterSummary(nodes, count) {
    const current = filters(nodes);
    const active = [];
    if (current.keyword) active.push(`关键词 ${current.keyword}`);
    if (current.system) active.push(`系统 ${current.system}`);
    if (active.length) {
      return `当前筛选：${active.join(" / ")}，命中 ${count} 条关联`;
    }
    return `当前按默认条件展示全部缺陷关联，共 ${count} 条`;
  }

  function summaryStats(items) {
    return {
      total: items.length,
      linkedCases: new Set(items.map((item) => normalizeCaseId(item.case_id || "")).filter(Boolean)).size,
      systems: new Set(items.map((item) => String(item.system || "").trim()).filter(Boolean)).size || 0,
      latestLinked: items[0]?.linked_at || "-",
    };
  }

  function copyValues(selectedKeys, items, kind) {
    return Array.from(selectedKeys)
      .map((key) => {
        if (kind === "case") return normalizeCaseId(key.split(":")[0] || "");
        return key.split(":").pop() || "";
      })
      .filter(Boolean)
      .join("\n");
  }

  window.DefectsSupport = {
    applyFilters,
    copyValues,
    filterSummary,
    filters,
    normalizeCaseId,
    summaryStats,
  };
})();
