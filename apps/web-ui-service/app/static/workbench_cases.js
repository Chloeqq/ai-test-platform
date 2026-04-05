(function () {
  const shared = window.WorkbenchShared;

  function createController(config) {
    const state = config.state;
    const els = config.els;
    const authFetch = config.authFetch;
    const onCaseLoaded = typeof config.onCaseLoaded === "function" ? config.onCaseLoaded : () => {};

    function renderCaseRows() {
      const rows = Array.isArray(state.caseItems) ? state.caseItems : [];
      if (!rows.length) {
        els.caseBody.innerHTML = '<tr><td colspan="5" class="empty-state">暂无可调试用例。</td></tr>';
        return;
      }
      els.caseBody.innerHTML = rows
        .map((item) => {
          const caseId = String(item.case_id || item.id || "").trim();
          const isActive = state.currentCaseId && caseId === state.currentCaseId;
          return (
            '<tr data-case-id="' +
            shared.escapeHtml(caseId) +
            '"' +
            (isActive ? ' class="is-active"' : "") +
            ">" +
            "<td>" +
            shared.escapeHtml(shared.displayCaseId(caseId)) +
            "</td>" +
            "<td>" +
            shared.escapeHtml(item.title || item.name || "-") +
            "</td>" +
            "<td>" +
            shared.escapeHtml(item.page || "-") +
            "</td>" +
            "<td>" +
            shared.escapeHtml(item.priority || "-") +
            "</td>" +
            "<td>" +
            shared.escapeHtml(shared.formatTime(item.updated_at || item.created_at)) +
            "</td>" +
            "</tr>"
          );
        })
        .join("");
    }

    function renderPagination() {
      if (!els.casePagination || typeof window.platformRenderSimplePagination !== "function") return;
      const info = state.casePagination || {};
      window.platformRenderSimplePagination(
        els.casePagination,
        {
          page: Number(info.page || state.casePage || 1),
          pageSize: Number(info.page_size || state.casePageSize || 10),
          totalItems: Number(info.total_items || 0),
          totalPages: Number(info.total_pages || 1),
        },
        (nextPage, nextPageSize) => {
          loadCases(nextPage, nextPageSize).catch((error) => window.alert(error?.message || "加载失败"));
        }
      );
    }

    async function loadProjects() {
      const payload = await shared.requestJson(authFetch, "/api/workbench/projects", { method: "GET" });
      const items = Array.isArray(payload.items) ? payload.items : [];
      els.projectSelect.innerHTML = items
        .map((item) => {
          const project = String(item || "").trim();
          const selected = project === state.project ? " selected" : "";
          return '<option value="' + shared.escapeHtml(project) + '"' + selected + ">" + shared.escapeHtml(project) + "</option>";
        })
        .join("");
      if (!items.length) {
        els.projectSelect.innerHTML = '<option value="default" selected>default</option>';
      }
      state.project = String(els.projectSelect.value || state.project || "default");
    }

    async function loadCases(page, pageSize, focusCaseId) {
      state.casePage = Number(page || state.casePage || 1);
      state.casePageSize = Number(pageSize || state.casePageSize || 10);
      const query = new URLSearchParams({
        project: String(state.project || "default"),
        page: String(state.casePage),
        page_size: String(state.casePageSize),
        sort_field: "updated_at",
        sort_order: "desc",
      });
      if (focusCaseId) query.set("focus_case_id", String(focusCaseId));
      const payload = await shared.requestJson(authFetch, "/api/workbench/cases?" + query.toString(), { method: "GET" });
      state.caseItems = Array.isArray(payload.items) ? payload.items : [];
      state.casePagination = payload.pagination && typeof payload.pagination === "object" ? payload.pagination : {};
      renderCaseRows();
      renderPagination();
      if (focusCaseId) {
        await loadCase(focusCaseId);
      }
    }

    async function loadCase(caseId) {
      const id = String(caseId || "").trim();
      if (!id) return;
      const query = new URLSearchParams({ project: String(state.project || "default") });
      const payload = await shared.requestJson(authFetch, "/api/workbench/cases/" + encodeURIComponent(id) + "?" + query.toString(), {
        method: "GET",
      });
      const item = payload.item && typeof payload.item === "object" ? payload.item : payload;
      state.currentCaseId = String(item.case_id || id).trim();
      state.currentCasePath = String(item.case_path || item.path || "").trim();
      if (els.currentCase) els.currentCase.textContent = shared.displayCaseId(state.currentCaseId);
      if (els.currentPath) els.currentPath.textContent = state.currentCasePath || "";
      if (els.yamlEditor) {
        els.yamlEditor.value = String(item.yaml_content || item.yaml || "");
      }
      onCaseLoaded(item);
      renderCaseRows();
    }

    async function saveEditorCase() {
      const caseId = String(state.currentCaseId || "").trim();
      if (!caseId) throw new Error("请先选择用例");
      const payload = {
        project: String(state.project || "default"),
        yaml_content: String(els.yamlEditor?.value || "").trim(),
      };
      if (!payload.yaml_content) throw new Error("YAML 内容不能为空");
      const result = await shared.requestJson(authFetch, "/api/workbench/cases/" + encodeURIComponent(caseId), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return result;
    }

    function bindEvents() {
      els.refreshBtn?.addEventListener("click", () => {
        loadCases(1, state.casePageSize).catch((error) => window.alert(error?.message || "刷新失败"));
      });
      els.projectSelect?.addEventListener("change", () => {
        state.project = String(els.projectSelect.value || "default");
        loadCases(1, state.casePageSize).catch((error) => window.alert(error?.message || "切换项目失败"));
      });
      els.saveBtn?.addEventListener("click", () => {
        saveEditorCase()
          .then(() => window.alert("保存成功"))
          .catch((error) => window.alert(error?.message || "保存失败"));
      });
      els.caseBody?.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const row = target.closest("[data-case-id]");
        if (!row) return;
        const caseId = String(row.getAttribute("data-case-id") || "").trim();
        loadCase(caseId).catch((error) => window.alert(error?.message || "加载用例失败"));
      });
    }

    return {
      bindEvents: bindEvents,
      loadCase: loadCase,
      loadCases: loadCases,
      loadProjects: loadProjects,
      saveEditorCase: saveEditorCase,
    };
  }

  window.WorkbenchCases = {
    createController: createController,
  };
})();
