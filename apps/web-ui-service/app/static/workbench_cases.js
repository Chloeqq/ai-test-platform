(function () {
  const shared = window.WorkbenchShared;
  const sharedProjectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  const projectSelectorSupport = window.ProjectSelectorSupport;
  if (!shared) return;

  function createController({ state, els, authFetch, onCaseLoaded }) {
    let casePagination = null;

    const workbenchProjectsApi = {
      async list() {
        const resp = await authFetch("/api/workbench/projects");
        if (!resp.ok) throw new Error("load projects failed");
        return resp.json();
      },
      create: sharedProjectsApi && typeof sharedProjectsApi.create === "function"
        ? sharedProjectsApi.create.bind(sharedProjectsApi)
        : null,
      update: sharedProjectsApi && typeof sharedProjectsApi.update === "function"
        ? sharedProjectsApi.update.bind(sharedProjectsApi)
        : null,
      remove: sharedProjectsApi && typeof sharedProjectsApi.remove === "function"
        ? sharedProjectsApi.remove.bind(sharedProjectsApi)
        : null,
    };

    function normalizeProjectCode(value) {
      if (projectSelectorSupport && typeof projectSelectorSupport.normalizeCode === "function") {
        return projectSelectorSupport.normalizeCode(value);
      }
      return String(value || "").trim().toLowerCase();
    }

    function findProjectItem(projectCode) {
      const normalizedCode = normalizeProjectCode(projectCode);
      return (Array.isArray(state.projectItems) ? state.projectItems : []).find((item) => {
        return normalizeProjectCode(item && item.project_code) === normalizedCode;
      }) || null;
    }

    function isCurrentProjectActive() {
      const currentProject = findProjectItem(state.project);
      if (!currentProject) return true;
      return normalizeProjectCode(currentProject.status || "active") === "active";
    }

    function workbenchGovernanceNote() {
      return "当前项目为 inactive，Workbench 仅允许浏览已保存 YAML 与直接运行已落库版本；保存和 YAML 编辑已禁用。";
    }

    function syncWriteGuards() {
      const writeBlocked = !isCurrentProjectActive();
      state.projectWriteBlocked = writeBlocked;
      if (els.governanceNote) {
        els.governanceNote.hidden = !writeBlocked;
        els.governanceNote.textContent = writeBlocked ? workbenchGovernanceNote() : "";
      }
      if (els.saveBtn) {
        els.saveBtn.disabled = writeBlocked;
      }
      if (els.yamlEditor) {
        els.yamlEditor.readOnly = writeBlocked;
        els.yamlEditor.classList.toggle("is-readonly", writeBlocked);
      }
    }

    function setProjectOptions(items, selectedValue) {
      const projectItems = Array.isArray(items) ? items : [];
      state.projectItems = projectItems;
      if (projectSelectorSupport && typeof projectSelectorSupport.applyProjectOptions === "function") {
        projectSelectorSupport.applyProjectOptions(els.projectSelect, projectItems, {
          selectedValue: selectedValue || state.project || "atp",
          defaultProjectCode: "atp",
          includeInactive: true,
          disableInactive: false,
          inactiveLabelSuffix: " (inactive)",
        });
      } else {
        els.projectSelect.innerHTML = projectItems
          .map((item) => {
            const code = normalizeProjectCode(item && item.project_code);
            const projectName = String(item && item.project_name || code).trim() || code;
            const selected = code === normalizeProjectCode(selectedValue || state.project || "atp") ? " selected" : "";
            return `<option value="${shared.escapeHtml(code)}"${selected}>${shared.escapeHtml(code)} · ${shared.escapeHtml(projectName)}</option>`;
          })
          .join("");
      }
      state.project = normalizeProjectCode(els.projectSelect.value || selectedValue || state.project || "atp") || "atp";
      syncWriteGuards();
    }

    function clearCurrentCase() {
      state.currentCaseId = "";
      state.currentCasePath = "";
      state.persistedYamlContent = "";
      els.currentCase.textContent = "未选择";
      els.currentPath.textContent = "";
      if (els.yamlEditor) {
        els.yamlEditor.value = "";
      }
      if (typeof onCaseLoaded === "function") {
        onCaseLoaded({});
      }
    }

    function setCurrentCase(item) {
      if (!item || typeof item !== "object") {
        clearCurrentCase();
        return;
      }
      const payload = item;
      state.currentCaseId = String(payload.case_id || "").trim();
      state.currentCasePath = String(payload.path || "").trim();
      state.persistedYamlContent = String(payload.yaml_content || state.persistedYamlContent || "");
      els.currentCase.textContent = shared.displayCaseId(state.currentCaseId || "") || "未选择";
      els.currentPath.textContent = state.currentCasePath || "";
      if (typeof onCaseLoaded === "function") {
        onCaseLoaded(payload);
      }
    }

    function getCasePageCount() {
      return Math.max(1, Number(state.casePagination?.total_pages || 1));
    }

    function clampCasePage(page) {
      return Math.min(Math.max(1, Number(page) || 1), getCasePageCount());
    }

    function renderCasePagination() {
      if (!els.casePagination) return;
      const pagination = state.casePagination || {};
      const currentPage = clampCasePage(pagination.page || state.casePage);
      const total = Number(pagination.total_items || 0);
      if (typeof window.Pagination !== "function") {
        els.casePagination.innerHTML = total
          ? `<span class="case-page-info">第 ${currentPage} / ${getCasePageCount()} 页 · 共 ${total} 条</span>`
          : '<span class="case-page-info">暂无用例</span>';
        return;
      }
      const paginationOptions = {
        page: currentPage,
        page_size: Number(pagination.page_size || state.casePageSize),
        total_items: total,
        page_size_options: [10, 20, 50, 100],
        show_total: true,
        show_quick_jumper: true,
        onChange: (page, pageSize) => loadCases(page, pageSize),
      };
      if (!casePagination) {
        casePagination = new window.Pagination("#wb-case-pagination", paginationOptions);
        return;
      }
      casePagination.update(paginationOptions);
    }

    function renderCaseRows() {
      const items = state.caseItems || [];
      if (!items.length) {
        els.caseBody.innerHTML = state.casePagination.total_items
          ? '<tr><td colspan="5">当前页暂无用例</td></tr>'
          : '<tr><td colspan="5">暂无用例</td></tr>';
        renderCasePagination();
        return;
      }
      els.caseBody.innerHTML = items
        .map(
          (item) => `
            <tr data-case-id="${shared.escapeHtml(item.case_id)}" class="${state.currentCaseId === item.case_id ? "is-active" : ""}">
              <td>${shared.escapeHtml(shared.displayCaseId(item.case_id))}</td>
              <td>${shared.escapeHtml(item.title)}</td>
              <td>${shared.escapeHtml(item.page)}</td>
              <td>${shared.escapeHtml(item.priority)}</td>
              <td>${shared.formatTime(item.updated_at)}</td>
            </tr>
          `
        )
        .join("");
      els.caseBody.querySelectorAll("tr").forEach((row) => {
        row.addEventListener("click", () => {
          const caseId = row.getAttribute("data-case-id");
          if (caseId) {
            loadCase(caseId);
          }
        });
      });
      renderCasePagination();
    }

    async function loadProjects(selectedValue = state.project) {
      const payload = await workbenchProjectsApi.list();
      const items = Array.isArray(payload.items) ? payload.items : [];
      const normalizedItems = items.length
        ? items
        : [{ project_code: "atp", project_name: "ATP", status: "active", source: "default" }];
      setProjectOptions(normalizedItems, selectedValue);
    }

    async function loadCases(page = state.casePage, pageSize = state.casePageSize, focusCaseId = "") {
      const params = new URLSearchParams({
        project: state.project,
        page: String(Math.max(1, Number(page) || 1)),
        page_size: String(Math.max(1, Number(pageSize) || state.casePageSize)),
      });
      if (focusCaseId) {
        params.set("focus_case_id", focusCaseId);
      }
      const resp = await authFetch(`/api/workbench/cases?${params.toString()}`);
      if (!resp.ok) throw new Error("load cases failed");
      const payload = await resp.json();
      state.caseItems = Array.isArray(payload.items) ? payload.items : [];
      state.casePagination = payload.pagination && typeof payload.pagination === "object"
        ? payload.pagination
        : {
            page: Math.max(1, Number(page) || 1),
            page_size: Math.max(1, Number(pageSize) || state.casePageSize),
            total_items: state.caseItems.length,
            total_pages: 1,
            has_prev: false,
            has_next: false,
            prev_page: null,
            next_page: null,
          };
      state.casePage = Number(state.casePagination.page || 1);
      state.casePageSize = Number(state.casePagination.page_size || pageSize || state.casePageSize);
      renderCaseRows();
    }

    async function loadCase(caseId) {
      const resp = await authFetch(`/api/workbench/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(state.project)}`);
      if (!resp.ok) {
        window.alert("加载用例失败");
        return;
      }
      const payload = await resp.json();
      const item = payload.item || {};
      els.yamlEditor.value = item.yaml_content || "";
      state.persistedYamlContent = String(item.yaml_content || "");
      setCurrentCase(item);
      syncWriteGuards();
      renderCaseRows();
    }

    async function openProjectManager() {
      if (!projectSelectorSupport || !projectManager || !workbenchProjectsApi.create || !workbenchProjectsApi.update || !workbenchProjectsApi.remove) {
        window.alert("项目管理组件未就绪。");
        return;
      }
      projectSelectorSupport.openProjectManager({
        projectManager: projectManager,
        projectsApi: workbenchProjectsApi,
        selectEl: els.projectSelect,
        defaultProjectCode: "atp",
        deleteFallbackValue: "atp",
        includeInactive: true,
        disableInactive: false,
        inactiveLabelSuffix: " (inactive)",
        onChanged: async ({ items, selectedProjectCode }) => {
          setProjectOptions(items, selectedProjectCode || state.project || "atp");
          clearCurrentCase();
          await loadCases(1, state.casePageSize);
        },
      });
    }

    async function saveEditorCase({ announce = true } = {}) {
      const rawEditorContent = String(els.yamlEditor.value || "");
      const editorContent = rawEditorContent.trim();
      const inferredCaseId = shared.normalizeCaseId(state.currentCaseId || shared.extractCaseIdFromYaml(editorContent));
      if (!inferredCaseId) {
        window.alert("请先选择用例，或在 YAML 中补充 id。");
        return null;
      }

      if (state.projectWriteBlocked) {
        if (rawEditorContent !== String(state.persistedYamlContent || "")) {
          window.alert("当前项目为 inactive，Workbench 已禁用 YAML 保存；如需编辑请先恢复项目为 active。");
          return null;
        }
        return inferredCaseId;
      }

      const resp = await authFetch(`/api/workbench/cases/${encodeURIComponent(inferredCaseId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: state.project,
          yaml_content: els.yamlEditor.value,
        }),
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        window.alert(`保存失败：${error.detail || resp.statusText}`);
        return null;
      }

      const payload = await resp.json();
      const item = payload.item || {};
      state.persistedYamlContent = String(item.yaml_content || els.yamlEditor.value || "");
      setCurrentCase(item);
      await loadCases(state.casePage, state.casePageSize, state.currentCaseId);
      if (announce) {
        window.alert("用例已保存。");
      }
      return state.currentCaseId;
    }

    function bindEvents() {
      els.projectSelect.addEventListener("change", async () => {
        state.project = normalizeProjectCode(els.projectSelect.value);
        syncWriteGuards();
        clearCurrentCase();
        await loadCases(1, state.casePageSize);
      });
      if (els.manageProjectBtn) {
        els.manageProjectBtn.addEventListener("click", () => {
          openProjectManager().catch((error) => window.alert(error.message || "项目管理失败"));
        });
      }
      els.refreshBtn.addEventListener("click", () => loadCases());
      els.saveBtn.addEventListener("click", () => {
        saveEditorCase({ announce: true }).catch((error) => window.alert(error.message || "保存失败"));
      });
    }

    return {
      bindEvents,
      loadCase,
      loadCases,
      loadProjects,
      saveEditorCase,
      setCurrentCase,
    };
  }

  window.WorkbenchCases = { createController };
})();
