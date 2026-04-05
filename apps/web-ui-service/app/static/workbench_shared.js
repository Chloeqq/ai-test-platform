(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    const text = String(value || "").trim();
    return text || "-";
  }

  function displayCaseId(value) {
    const text = String(value || "").trim();
    return text || "-";
  }

  async function requestJson(authFetch, url, options) {
    const response = await authFetch(url, options || {});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body?.detail?.message || body?.detail || body?.message || "请求失败";
      throw new Error(String(message));
    }
    return body;
  }

  window.WorkbenchShared = {
    displayCaseId: displayCaseId,
    escapeHtml: escapeHtml,
    formatTime: formatTime,
    requestJson: requestJson,
  };
})();
