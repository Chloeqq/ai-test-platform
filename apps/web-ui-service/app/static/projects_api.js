(function () {
  function readJson(response) {
    return response.json().catch(() => ({}));
  }

  async function request(url, options) {
    const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);
    const response = await authFetch(url, options);
    const body = await readJson(response);
    if (!response.ok) {
      throw new Error(body.detail || body.message || "请求失败");
    }
    return body;
  }

  window.ProjectsApi = {
    list() {
      return request("/api/test-projects");
    },
    create(payload) {
      return request("/api/test-projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    update(projectCode, payload) {
      return request(`/api/test-projects/${encodeURIComponent(projectCode)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    remove(projectCode) {
      return request(`/api/test-projects/${encodeURIComponent(projectCode)}`, {
        method: "DELETE",
      });
    },
  };
})();
