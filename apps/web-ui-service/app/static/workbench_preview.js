(function () {
  const shell = document.getElementById("workbench-preview-shell");
  if (!shell) return;

  const els = {
    caseLabel: document.getElementById("wb-preview-case"),
    pathLabel: document.getElementById("wb-preview-path"),
    editor: document.getElementById("wb-preview-editor"),
    saveBtn: document.getElementById("wb-preview-save"),
    runBtn: document.getElementById("wb-preview-run"),
    workbenchBtn: document.getElementById("wb-preview-workbench"),
  };

  const params = new URLSearchParams(window.location.search);
  const state = {
    project: params.get("project") || "default",
    caseId: params.get("case_id") || "",
    casePath: "",
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function updateHeader() {
    els.caseLabel.textContent = state.caseId || "未选择";
    els.pathLabel.textContent = state.casePath ? `路径：${state.casePath}` : "";
  }

  function setWorkbenchLink(runId) {
    if (!els.workbenchBtn) return;
    if (!runId) {
      els.workbenchBtn.href = "/workbench";
      els.workbenchBtn.setAttribute("aria-disabled", "true");
      els.workbenchBtn.textContent = "查看工作台结果";
      return;
    }
    const params = new URLSearchParams();
    params.set("run_id", runId);
    if (state.project) {
      params.set("project", state.project);
    }
    if (state.caseId) {
      params.set("case_id", state.caseId);
    }
    els.workbenchBtn.href = `/workbench?${params.toString()}`;
    els.workbenchBtn.removeAttribute("aria-disabled");
    els.workbenchBtn.textContent = "查看工作台结果";
  }

  async function loadCase() {
    if (!state.caseId) {
      updateHeader();
      setWorkbenchLink("");
      els.editor.value = "# 未指定用例ID，请从生成页或工作台选择用例后进入预览。";
      return;
    }
    const resp = await fetch(`/api/workbench/cases/${encodeURIComponent(state.caseId)}?project=${encodeURIComponent(state.project)}`);
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`加载失败：${error.detail || resp.statusText}`);
      return;
    }
    const data = await resp.json();
    const item = data.item || {};
    state.caseId = item.case_id || state.caseId;
    state.casePath = item.path || "";
    els.editor.value = item.yaml_content || "";
    updateHeader();
    setWorkbenchLink("");
  }

  async function saveCase() {
    if (!state.caseId) {
      alert("未指定用例ID。");
      return;
    }
    const resp = await fetch(`/api/workbench/cases/${encodeURIComponent(state.caseId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        yaml_content: els.editor.value,
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`保存失败：${error.detail || resp.statusText}`);
      return;
    }
    const data = await resp.json();
    const item = data.item || {};
    state.casePath = item.path || state.casePath;
    updateHeader();
    alert("保存成功。");
  }

  async function runCase() {
    if (!state.caseId) {
      alert("未指定用例ID。");
      return;
    }
    const resp = await fetch("/api/workbench/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        case_id: state.caseId,
        case_path: state.casePath,
        source: "preview",
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`启动失败：${error.detail || resp.statusText}`);
      return;
    }
    const data = await resp.json();
    const runId = data.item?.run_id || "";
    if (runId) {
      setWorkbenchLink(runId);
      alert(`已触发执行：${runId}。可直接点击“查看工作台结果”回到工作台。`);
    } else {
      alert("已触发执行，请回到工作台查看日志。");
    }
  }

  function bindEvents() {
    els.saveBtn.addEventListener("click", saveCase);
    els.runBtn.addEventListener("click", runCase);
  }

  function bootstrap() {
    bindEvents();
    updateHeader();
    loadCase().catch((error) => {
      console.error(error);
      alert(`加载失败：${escapeHtml(error?.message || "unknown error")}`);
    });
  }

  bootstrap();
})();
