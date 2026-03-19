(function () {
  const shell = document.getElementById("workbench-generate-shell");
  if (!shell) return;

  const els = {
    form: document.getElementById("wb-generate-form"),
    projectSelect: document.getElementById("gen-project"),
    pageInput: document.getElementById("gen-page"),
    caseIdInput: document.getElementById("gen-case-id"),
    titleInput: document.getElementById("gen-title"),
    prioritySelect: document.getElementById("gen-priority"),
    tagsInput: document.getElementById("gen-tags"),
    requirementInput: document.getElementById("gen-requirement"),
    result: document.getElementById("gen-result"),
    yamlPreview: document.getElementById("gen-yaml-preview"),
    openPreview: document.getElementById("gen-open-preview"),
  };

  const state = {
    project: "default",
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeTags(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }

  function setResult(text) {
    els.result.textContent = text;
  }

  function setPreviewLink(caseId, project) {
    if (!caseId) {
      els.openPreview.setAttribute("href", "#");
      return;
    }
    const query = new URLSearchParams({
      case_id: caseId,
      project: project || "default",
    });
    els.openPreview.setAttribute("href", `/workbench/preview?${query.toString()}`);
  }

  async function loadProjects() {
    const resp = await fetch("/api/workbench/projects");
    if (!resp.ok) throw new Error("load projects failed");
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) items.push("default");
    els.projectSelect.innerHTML = items
      .map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`)
      .join("");
    if (!items.includes(state.project)) {
      state.project = items[0];
    }
    els.projectSelect.value = state.project;
  }

  async function handleGenerate(event) {
    event.preventDefault();
    const requirement = els.requirementInput.value.trim();
    if (!requirement) {
      alert("请输入需求描述。");
      return;
    }
    const payload = {
      project: els.projectSelect.value || "default",
      page: els.pageInput.value.trim() || "product",
      case_id: els.caseIdInput.value.trim(),
      title: els.titleInput.value.trim(),
      priority: els.prioritySelect.value || "P1",
      tags: normalizeTags(els.tagsInput.value),
      requirement,
    };
    if (!payload.tags.length) {
      payload.tags = ["ai-generated"];
    }
    setResult("生成中，请稍候...");
    els.yamlPreview.textContent = "";
    try {
      const resp = await fetch("/api/workbench/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        setResult(`生成失败：${error.detail || resp.statusText}`);
        return;
      }
      const data = await resp.json();
      const item = data.item || {};
      setResult(`生成成功：${item.case_id || "-"}`);
      els.yamlPreview.textContent = item.yaml_content || "";
      setPreviewLink(item.case_id, payload.project);
    } catch (error) {
      console.error(error);
      setResult("生成失败，请检查服务状态。");
    }
  }

  function bindEvents() {
    els.projectSelect.addEventListener("change", () => {
      state.project = els.projectSelect.value || "default";
      setPreviewLink("", state.project);
    });
    els.form.addEventListener("submit", handleGenerate);
  }

  async function bootstrap() {
    bindEvents();
    await loadProjects();
    setPreviewLink("", state.project);
  }

  bootstrap().catch((error) => {
    console.error(error);
    setResult("加载失败，请检查后端服务。");
  });
})();
