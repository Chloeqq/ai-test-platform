(function () {
  function readJson(response) {
    return response.json().catch(() => ({}));
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    const body = await readJson(response);
    if (!response.ok) {
      throw new Error(body.detail || body.message || "请求失败");
    }
    return body;
  }

  function toQuery(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim()) sp.set(key, String(value).trim());
    });
    return sp.toString();
  }

  window.CasesApi = {
    tree() {
      return request("/api/test-cases/tree");
    },
    list(params) {
      return request(`/api/test-cases?${toQuery(params)}`);
    },
    detail(caseId) {
      return request(`/api/test-cases/${caseId}`);
    },
    create(payload) {
      return request("/api/test-cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    export(ids) {
      return request("/api/test-cases/batch/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, format: "json" }),
      });
    },
    updateStatus(ids, statusValue) {
      return request("/api/test-cases/batch/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, status: statusValue }),
      });
    },
    updateTags(ids, tags) {
      return request("/api/test-cases/batch/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, tags, mode: "replace" }),
      });
    },
  };
})();
