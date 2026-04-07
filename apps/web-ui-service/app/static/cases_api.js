(function () {
  function readJson(response) {
    return response.json().catch(() => ({}));
  }

  function resolveErrorMessage(body) {
    if (!body || typeof body !== "object") return "请求失败";
    const detail = body.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail && typeof detail === "object") {
      const message = String(detail.message || detail.error || "").trim();
      if (message) return message;
    }
    const message = String(body.message || "").trim();
    if (message) return message;
    return "请求失败";
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    const body = await readJson(response);
    if (!response.ok) {
      throw new Error(resolveErrorMessage(body));
    }
    return body;
  }

  async function requestBlob(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const contentType = String(response.headers.get("content-type") || "").toLowerCase();
      if (contentType.includes("application/json")) {
        const body = await readJson(response);
        throw new Error(resolveErrorMessage(body));
      }
      const text = await response.text().catch(() => "");
      throw new Error(text || "请求失败");
    }

    const blob = await response.blob();
    const disposition = String(response.headers.get("content-disposition") || "");
    const match = disposition.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i);
    const filename = match ? decodeURIComponent(match[1]) : "test-cases-template.xlsx";
    return { blob, filename };
  }

  function toQuery(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim()) sp.set(key, String(value).trim());
    });
    return sp.toString();
  }

  window.CasesApi = {
    tree(params = {}) {
      const query = toQuery(params);
      return request(query ? `/api/test-cases/tree?${query}` : "/api/test-cases/tree");
    },
    list(params) {
      return request(`/api/test-cases?${toQuery(params)}`);
    },
    detail(caseId) {
      return request(`/api/test-cases/${encodeURIComponent(caseId)}`);
    },
    create(payload) {
      return request("/api/test-cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    export(ids, format = "xlsx") {
      return requestBlob("/api/test-cases/batch/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, format }),
      });
    },
    updateStatus(ids, statusValue) {
      return request("/api/test-cases/batch/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, status: statusValue }),
      });
    },
    batchDelete(ids, caseIds = []) {
      return request("/api/test-cases/batch/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, case_ids: caseIds }),
      });
    },
    purgeDdtCases() {
      return request("/api/test-cases/batch/purge-ddt", {
        method: "POST",
      });
    },
    updateTags(ids, tags) {
      return request("/api/test-cases/batch/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, tags, mode: "replace" }),
      });
    },
    treeCreate(payload) {
      return request("/api/test-cases/tree/nodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    treeUpdate(payload) {
      return request("/api/test-cases/tree/nodes", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    treeDelete(payload) {
      return request("/api/test-cases/tree/nodes", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
  };
})();
