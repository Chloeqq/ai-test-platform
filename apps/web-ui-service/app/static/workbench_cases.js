(function () {
  const shared = window.WorkbenchShared;
  if (!shared) return;

  function createController({ state, els, authFetch, onCaseLoaded }) {
    let casePagination = null;

    function setCurrentCase(item) {
      const payload = item && typeof item === "object" ? item : {};
      state.currentCaseId = String(payload.case_id || state.currentCaseId || "").trim();
      state.currentCasePath = String(payload.path || state.currentCasePath || "").trim();
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

    async function loadProjects() {
      const resp = await authFetch("/api/workbench/projects");
      if (!resp.ok) throw new Error("load projects failed");
      const payload = await resp.json();
      const items = payload.items || [];
      if (!items.length) items.push("atp");
      els.projectSelect.innerHTML = items
        .map((item) => `<option value="${shared.escapeHtml(item)}">${shared.escapeHtml(item)}</option>`)
        .join("");
      if (!items.includes(state.project)) {
        state.project = items[0];
      }
      els.projectSelect.value = state.project;
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
      setCurrentCase(item);
      renderCaseRows();
    }

    async function saveEditorCase({ announce = true } = {}) {
      const editorContent = String(els.yamlEditor.value || "").trim();
      const inferredCaseId = shared.normalizeCaseId(state.currentCaseId || shared.extractCaseIdFromYaml(editorContent));
      if (!inferredCaseId) {
        window.alert("请先选择用例，或在 YAML 中补充 id。");
        return null;
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
      setCurrentCase(item);
      await loadCases(state.casePage, state.casePageSize, state.currentCaseId);
      if (announce) {
        window.alert("用例已保存。");
      }
      return state.currentCaseId;
    }

    function bindEvents() {
      els.projectSelect.addEventListener("change", async () => {
        state.project = els.projectSelect.value;
        await loadCases();
      });
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
