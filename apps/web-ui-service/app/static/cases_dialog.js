(function () {
  const dialog = document.getElementById("new-case-dialog");
  const api = window.CasesApi;
  const projectsApi = window.ProjectsApi;
  const projectSelectorSupport = window.ProjectSelectorSupport;
  if (!dialog || !api || !projectsApi || !projectSelectorSupport) return;

  const els = {
    projectSelect: document.getElementById("new-project-code"),
    form: document.getElementById("new-case-form"),
    close: document.getElementById("btn-close-dialog"),
    cancel: document.getElementById("btn-cancel-dialog"),
  };
  const requiredElements = ["projectSelect", "form", "close", "cancel"];
  const missingElements = requiredElements.filter((key) => !els[key]);
  if (missingElements.length) {
    console.error("[cases-dialog] missing required DOM nodes:", missingElements.join(", "));
    return;
  }

  function setProjectOptions(items) {
    projectSelectorSupport.applyProjectOptions(els.projectSelect, items, {
      selectedValue: String(els.projectSelect.value || "atp").trim().toLowerCase() || "atp",
      defaultProjectCode: "atp",
      disableInactive: true,
      inactiveLabelSuffix: " (inactive,不可用)",
    });
  }

  async function loadProjects() {
    const items = await projectSelectorSupport.loadProjectOptions({
      projectsApi: projectsApi,
      selectEl: els.projectSelect,
      selectedValue: String(els.projectSelect.value || "atp").trim().toLowerCase() || "atp",
      defaultProjectCode: "atp",
      disableInactive: true,
      inactiveLabelSuffix: " (inactive,不可用)",
    });
    setProjectOptions(items);
  }

  function openDialog() {
    loadProjects().catch(() => {});
    dialog.showModal();
  }

  function closeDialog() {
    dialog.close();
  }

  function splitComma(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function submitForm(event) {
    event.preventDefault();
    const selectedOption = els.projectSelect.options[els.projectSelect.selectedIndex] || null;
    const projectCode = projectSelectorSupport.normalizeCode(els.projectSelect.value || "");
    if (!projectCode || (selectedOption && selectedOption.disabled)) {
      window.alert("没有可用的 active 项目，请先在项目管理中创建或启用项目。");
      return;
    }
    const payload = {
      mode: "manual",
      project_code: projectCode,
      name: String(document.getElementById("new-name")?.value || "").trim(),
      product_line: String(document.getElementById("new-product-line")?.value || "").trim(),
      module: String(document.getElementById("new-module")?.value || "").trim(),
      priority: String(document.getElementById("new-priority")?.value || "P2"),
      test_type: String(document.getElementById("new-test-type")?.value || "ui"),
      tags: splitComma(document.getElementById("new-tags")?.value),
      markers: splitComma(document.getElementById("new-markers")?.value),
      creator: String(document.getElementById("new-creator")?.value || "").trim(),
      pytest_path: String(document.getElementById("new-pytest-path")?.value || "").trim(),
      status: String(document.getElementById("new-status")?.value || "active"),
      script_code: String(document.getElementById("new-script")?.value || ""),
      requirement: "",
      data_config: { enabled: false, parameters: [], rows: [] },
    };
    await api.create(payload);
    closeDialog();
    window.dispatchEvent(new CustomEvent("cases:reload"));
  }

  els.form.addEventListener("submit", (event) => {
    submitForm(event).catch((error) => window.alert(error.message || "创建失败"));
  });
  els.close.addEventListener("click", closeDialog);
  els.cancel.addEventListener("click", closeDialog);
  loadProjects().catch(() => {});
  window.CasesDialog = { openDialog, setProjectOptions };
})();
