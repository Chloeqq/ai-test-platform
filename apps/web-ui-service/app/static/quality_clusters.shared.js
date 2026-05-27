(function () {
  function readInitialQuery(name) {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return String(params.get(name) || "").trim();
    } catch (_error) {
      return "";
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function formatRefreshTime(value) {
    if (typeof window.platformFormatRefreshTime === "function") return window.platformFormatRefreshTime(value);
    return String(value || "").trim() || "最后刷新：-";
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
  }

  function copyText(text) {
    if (!text) return Promise.resolve(false);
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
    }
    return Promise.resolve(false);
  }

  function renderBadge(value, fallback) {
    if (typeof window.platformRenderBadge === "function") return window.platformRenderBadge(value, fallback);
    const text = String(value || fallback || "unknown").trim() || fallback || "unknown";
    return `<span class="badge badge-default">${escapeHtml(text)}</span>`;
  }

  function renderSeverityBadge(value) {
    const normalized = String(value || "S4").trim().toUpperCase() || "S4";
    const style =
      normalized === "S0" || normalized === "S1"
        ? "critical"
        : normalized === "S2"
          ? "high"
          : normalized === "S3"
            ? "medium"
            : "low";
    return `<span class="badge badge-${style}">${escapeHtml(normalized)}</span>`;
  }

  function severityRank(value) {
    const normalized = String(value || "").trim().toUpperCase();
    if (normalized === "S0") return 0;
    if (normalized === "S1") return 1;
    if (normalized === "S2") return 2;
    if (normalized === "S3") return 3;
    return 4;
  }

  function syncQuery(params) {
    try {
      const url = new URL(window.location.href);
      Object.entries(params || {}).forEach(([key, value]) => {
        const text = String(value || "").trim();
        if (text) url.searchParams.set(key, text);
        else url.searchParams.delete(key);
      });
      window.history.replaceState({}, "", `${url.pathname}${url.search}`);
    } catch (_error) {
      // Ignore URL sync failure.
    }
  }

  window.qualityClustersShared = {
    readInitialQuery,
    escapeHtml,
    formatTime,
    formatRefreshTime,
    displayCaseId,
    copyText,
    renderBadge,
    renderSeverityBadge,
    severityRank,
    syncQuery,
  };
})();
