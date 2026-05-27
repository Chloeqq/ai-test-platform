(function () {
  const dialog = document.getElementById("new-case-dialog");
  const api = window.CasesApi;
  if (!dialog || !api) return;

  const els = {
    form: document.getElementById("new-case-form"),
    close: document.getElementById("btn-close-dialog"),
    cancel: document.getElementById("btn-cancel-dialog"),
  };

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
      name: document.getElementById("new-name").value.trim(),
      product_line: document.getElementById("new-product-line").value.trim(),
      module: document.getElementById("new-module").value.trim(),
      priority: document.getElementById("new-priority").value,
      test_type: document.getElementById("new-test-type").value,
      tags: splitComma(document.getElementById("new-tags").value),
      markers: splitComma(document.getElementById("new-markers").value),
      creator: document.getElementById("new-creator").value.trim(),
      pytest_path: document.getElementById("new-pytest-path").value.trim(),
      status: document.getElementById("new-status").value,
      script_code: document.getElementById("new-script").value,
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
  window.CasesDialog = { openDialog };
})();
