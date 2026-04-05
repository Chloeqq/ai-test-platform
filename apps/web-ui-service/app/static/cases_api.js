(function () {
  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);

  function toQuery(params) {
    const query = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, rawValue]) => {
      const value = rawValue == null ? "" : String(rawValue);
      if (!value) return;
      query.set(key, value);
    });
    return query.toString();
  }

  async function requestJson(path, options) {
    const response = await authFetch(path, options || {});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body?.detail?.message || body?.detail || body?.message || "请求失败";
      throw new Error(String(message));
    }
    return body;
  }

  async function requestRaw(path, options) {
    const response = await authFetch(path, options || {});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const message = body?.detail?.message || body?.detail || body?.message || "请求失败";
      throw new Error(String(message));
    }
    return response;
  }

  window.CasesApi = {
    async list(params) {
      const query = toQuery(params);
      return requestJson("/api/test-cases" + (query ? "?" + query : ""), { method: "GET" });
    },
    async tree() {
      return requestJson("/api/test-cases/tree", { method: "GET" });
    },
    async create(payload) {
      return requestJson("/api/test-cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    },
    async batchDelete(ids) {
      return requestJson("/api/test-cases/batch/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: Array.isArray(ids) ? ids : [] }),
      });
    },
    async batchTags(payload) {
      return requestJson("/api/test-cases/batch/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    },
    async batchExport(payload) {
      return requestRaw("/api/test-cases/batch/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
    },
  };
})();
