(function () {
  const projectsApi = window.ProjectsApi;
  if (!projectsApi) return;

  const state = {
    mode: "edit",
    items: [],
    activeCode: "",
    onChanged: null,
  };
  let refs = null;
  let toastTimer = null;

  function normalizeCode(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function findProject(projectCode) {
    const normalizedCode = normalizeCode(projectCode);
    return state.items.find((item) => normalizeCode(item.project_code) === normalizedCode) || null;
  }

  function toFriendlyMessage(error) {
    const raw = String((error && error.message) || "").trim();
    const lower = raw.toLowerCase();
    if (!raw) return "保存项目失败。";
    if (lower.includes("project already exists")) return "项目已存在。";
    if (lower.includes("no updatable fields provided")) return "项目已存在（无变更）。";
    if (lower.includes("project is referenced by")) return "项目已被用例或执行记录引用，不能删除。";
    if (lower.includes("default project cannot be deleted")) return "默认项目 atp 不允许删除。";
    return raw;
  }

  function isSameProjectData(item, { projectName, description, status }) {
    if (!item) return false;
    const currentName = String(item.project_name || "").trim();
    const currentDescription = String(item.description || "").trim();
    const currentStatus = normalizeCode(item.status || "active") || "active";
    return currentName === projectName && currentDescription === description && currentStatus === status;
  }

  function setMessage(text, tone) {
    if (!refs || !refs.message) return;
    refs.message.textContent = String(text || "");
    refs.message.className = `project-manager-message project-manager-message-${tone || "info"}`;
  }

  function showToast(text, tone) {
    if (!refs || !refs.toast) return;
    if (toastTimer) {
      window.clearTimeout(toastTimer);
      toastTimer = null;
    }
    refs.toast.textContent = String(text || "");
    refs.toast.className = `project-manager-toast project-manager-toast-${tone || "info"} is-visible`;
    toastTimer = window.setTimeout(() => {
      refs.toast.className = "project-manager-toast";
      toastTimer = null;
    }, 2200);
  }

  function renderProjectOptions() {
    if (!refs || !refs.projectSelect) return;
    const options = state.items.map((item) => {
      const projectCode = normalizeCode(item.project_code);
      const projectName = String(item.project_name || projectCode).trim();
      return `<option value="${escapeHtml(projectCode)}">${escapeHtml(projectCode)} · ${escapeHtml(projectName)}</option>`;
    });
    refs.projectSelect.innerHTML = options.join("") || '<option value="atp">atp · ATP</option>';
  }

  function enterCreateMode(seedProjectCode) {
    if (!refs) return;
    state.mode = "create";
    state.activeCode = "";
    refs.projectCode.disabled = false;
    refs.projectCode.value = normalizeCode(seedProjectCode || "");
    refs.projectName.value = "";
    refs.projectDescription.value = "";
    refs.projectStatus.value = "active";
    refs.deleteBtn.disabled = true;
    setMessage("创建新项目：填写编码和名称后点击保存。", "info");
  }

  function fillFormByProject(item) {
    if (!refs || !item) return;
    state.mode = "edit";
    state.activeCode = normalizeCode(item.project_code);
    refs.projectCode.disabled = true;
    refs.projectCode.value = state.activeCode;
    refs.projectName.value = String(item.project_name || "").trim();
    refs.projectDescription.value = String(item.description || "").trim();
    refs.projectStatus.value = normalizeCode(item.status) === "inactive" ? "inactive" : "active";
    refs.deleteBtn.disabled = state.activeCode === "atp";
    setMessage(`正在编辑项目 ${state.activeCode}。`, "info");
  }

  async function notifyChanged(event) {
    if (typeof state.onChanged !== "function") return;
    await Promise.resolve(state.onChanged(event));
  }

  async function reloadProjects(preferredProjectCode) {
    const payload = await projectsApi.list();
    state.items = Array.isArray(payload.items) ? payload.items : [];
    renderProjectOptions();

    const preferredCode = normalizeCode(preferredProjectCode || state.activeCode || "atp");
    const selectedProject = findProject(preferredCode) || state.items[0] || null;
    if (!selectedProject) {
      enterCreateMode(preferredCode);
      return;
    }
    refs.projectSelect.value = normalizeCode(selectedProject.project_code);
    fillFormByProject(selectedProject);
  }

  async function saveProject() {
    const projectName = String(refs.projectName.value || "").trim();
    const description = String(refs.projectDescription.value || "").trim();
    const status = normalizeCode(refs.projectStatus.value || "active") || "active";
    if (!projectName) {
      setMessage("项目名称不能为空。", "error");
      return;
    }

    if (state.mode === "create") {
      const projectCode = normalizeCode(refs.projectCode.value);
      if (!projectCode) {
        setMessage("项目编码不能为空。", "error");
        return;
      }
      if (findProject(projectCode)) {
        setMessage("项目已存在，请直接编辑。", "info");
        showToast("项目已存在，请直接编辑。", "info");
        refs.projectSelect.value = projectCode;
        fillFormByProject(findProject(projectCode));
        return;
      }
      await projectsApi.create({
        project_code: projectCode,
        project_name: projectName,
        description,
        created_by: "admin",
      });
      await reloadProjects(projectCode);
      setMessage(`项目 ${projectCode} 已创建。`, "success");
      await notifyChanged({ action: "create", project_code: projectCode });
      showToast(`项目 ${projectCode} 已创建`, "success");
      refs.dialog.close();
      return;
    }

    const projectCode = normalizeCode(state.activeCode || refs.projectSelect.value);
    if (!projectCode) {
      setMessage("未找到可编辑的项目。", "error");
      return;
    }
    const currentItem = findProject(projectCode);
    if (isSameProjectData(currentItem, { projectName, description, status })) {
      setMessage("项目已存在（无变更）。", "info");
      showToast("项目已存在（无变更）。", "info");
      return;
    }
    await projectsApi.update(projectCode, {
      project_name: projectName,
      description,
      status,
    });
    await reloadProjects(projectCode);
    setMessage(`项目 ${projectCode} 已更新。`, "success");
    await notifyChanged({ action: "update", project_code: projectCode });
    showToast(`项目 ${projectCode} 已保存`, "success");
    refs.dialog.close();
  }

  async function deleteProject() {
    const projectCode = normalizeCode(state.activeCode || refs.projectSelect.value);
    if (!projectCode) {
      setMessage("未找到可删除的项目。", "error");
      return;
    }
    if (!window.confirm(`确认删除项目 ${projectCode} 吗？`)) return;

    await projectsApi.remove(projectCode);
    await reloadProjects("atp");
    setMessage(`项目 ${projectCode} 已删除。`, "success");
    await notifyChanged({ action: "delete", project_code: projectCode });
    showToast(`项目 ${projectCode} 已删除`, "success");
  }

  function bindEvents() {
    refs.closeBtn.addEventListener("click", () => refs.dialog.close());
    refs.cancelBtn.addEventListener("click", () => refs.dialog.close());
    refs.newBtn.addEventListener("click", () => {
      enterCreateMode("");
      refs.projectCode.focus();
    });
    refs.projectSelect.addEventListener("change", () => {
      const item = findProject(refs.projectSelect.value);
      if (item) fillFormByProject(item);
    });
    refs.saveBtn.addEventListener("click", () => {
      saveProject().catch((error) => {
        const text = toFriendlyMessage(error);
        setMessage(text, "error");
        showToast(text, "error");
      });
    });
    refs.deleteBtn.addEventListener("click", () => {
      deleteProject().catch((error) => {
        const text = toFriendlyMessage(error);
        setMessage(text, "error");
        showToast(text, "error");
      });
    });
  }

  function ensureDialog() {
    if (refs) return refs;

    const container = document.createElement("div");
    container.innerHTML = `
      <div id="project-manager-toast" class="project-manager-toast" role="status" aria-live="polite"></div>
      <dialog id="project-manager-dialog" class="project-manager-dialog">
        <form method="dialog" class="project-manager-form">
          <header class="project-manager-header">
            <h3>项目管理</h3>
            <button type="button" class="project-manager-close" id="project-manager-close" aria-label="关闭">×</button>
          </header>
          <div class="project-manager-body">
            <aside class="project-manager-list">
              <label for="project-manager-select">项目列表</label>
              <select id="project-manager-select" size="8"></select>
              <button type="button" class="btn cases-inline-btn" id="project-manager-new">新增项目</button>
            </aside>
            <section class="project-manager-editor">
              <label>项目编码
                <input id="project-manager-code" placeholder="例如 atp、mall">
              </label>
              <label>项目名称
                <input id="project-manager-name" placeholder="例如 Mall Platform">
              </label>
              <label>项目状态
                <select id="project-manager-status">
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                </select>
              </label>
              <label>项目描述
                <textarea id="project-manager-description" rows="4" placeholder="项目描述（可选）"></textarea>
              </label>
              <div id="project-manager-message" class="project-manager-message project-manager-message-info"></div>
            </section>
          </div>
          <footer class="project-manager-footer">
            <button type="button" class="btn" id="project-manager-cancel">关闭</button>
            <button type="button" class="btn cases-inline-danger" id="project-manager-delete">删除项目</button>
            <button type="button" class="btn btn-primary" id="project-manager-save">保存</button>
          </footer>
        </form>
      </dialog>
    `;
    const toastNode = container.firstElementChild;
    const dialogNode = container.lastElementChild;
    document.body.appendChild(toastNode);
    document.body.appendChild(dialogNode);

    refs = {
      dialog: dialogNode,
      closeBtn: document.getElementById("project-manager-close"),
      cancelBtn: document.getElementById("project-manager-cancel"),
      deleteBtn: document.getElementById("project-manager-delete"),
      saveBtn: document.getElementById("project-manager-save"),
      newBtn: document.getElementById("project-manager-new"),
      projectSelect: document.getElementById("project-manager-select"),
      projectCode: document.getElementById("project-manager-code"),
      projectName: document.getElementById("project-manager-name"),
      projectStatus: document.getElementById("project-manager-status"),
      projectDescription: document.getElementById("project-manager-description"),
      message: document.getElementById("project-manager-message"),
      toast: toastNode,
    };
    bindEvents();
    return refs;
  }

  function open(options) {
    const dialogRefs = ensureDialog();
    state.onChanged = options && typeof options.onChanged === "function" ? options.onChanged : null;
    const selectedProjectCode =
      normalizeCode(options && options.selectedProjectCode) || normalizeCode(dialogRefs.projectSelect.value) || "atp";
    reloadProjects(selectedProjectCode)
      .then(() => {
        if (!dialogRefs.dialog.open) dialogRefs.dialog.showModal();
      })
      .catch((error) => {
        setMessage(error.message || "加载项目失败。", "error");
        if (!dialogRefs.dialog.open) dialogRefs.dialog.showModal();
      });
  }

  window.ProjectManagerDialog = { open };
})();
