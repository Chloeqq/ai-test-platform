(function () {
  const dialog = document.getElementById("new-case-dialog");
  const api = window.CasesApi;
  const projectsApi = window.ProjectsApi;
  if (!dialog || !api || !projectsApi) return;

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
    const options = (Array.isArray(items) ? items : []).map((item) => {
      const projectCode = String(item.project_code || "").trim();
      const projectName = String(item.project_name || projectCode).trim();
      const selected = projectCode === "atp" ? " selected" : "";
      return `<option value="${projectCode}"${selected}>${projectCode} · ${projectName}</option>`;
    });
    els.projectSelect.innerHTML = options.join("") || '<option value="atp" selected>atp</option>';
  }

  async function loadProjects() {
    const payload = await projectsApi.list();
    setProjectOptions(payload.items || []);
  }

  function openDialog() {
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
    const payload = {
      mode: "manual",
      project_code: els.projectSelect.value || "atp",
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
