(function () {
  const shell = document.getElementById("workbench-shell");
  if (!shell) return;

  const state = {
    project: "default",
    currentCaseId: "",
    currentCasePath: "",
    currentRunId: "",
    eventSource: null,
    logLines: [],
  };

  const els = {
    projectSelect: document.getElementById("wb-project"),
    refreshBtn: document.getElementById("wb-refresh"),
    caseBody: document.getElementById("wb-case-body"),
    yamlEditor: document.getElementById("wb-yaml-editor"),
    currentCase: document.getElementById("wb-current-case"),
    currentPath: document.getElementById("wb-current-path"),
    saveBtn: document.getElementById("wb-save"),
    runBtn: document.getElementById("wb-run"),
    runStatus: document.getElementById("wb-run-status"),
    logViewer: document.getElementById("wb-log-viewer"),
    analysisSummary: document.getElementById("wb-analysis-summary"),
    analysisDetail: document.getElementById("wb-analysis-detail"),
    healBtn: document.getElementById("wb-heal"),
    rerunBtn: document.getElementById("wb-rerun"),
    downloadBtn: document.getElementById("wb-download-log"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (!value) return "-";
    try {
      return new Date(value).toLocaleString("zh-CN");
    } catch (_error) {
      return String(value);
    }
  }

  function setRunStatus(text) {
    els.runStatus.textContent = text;
  }

  function resetLogs() {
    state.logLines = [];
    els.logViewer.textContent = "";
  }

  function appendLog(line) {
    state.logLines.push(line);
    if (state.logLines.length > 400) {
      state.logLines.shift();
    }
    els.logViewer.textContent = state.logLines.join("\n");
    els.logViewer.scrollTop = els.logViewer.scrollHeight;
  }

  function closeEventSource() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
  }

  async function loadProjects() {
    const resp = await fetch("/api/workbench/projects");
    if (!resp.ok) throw new Error("load projects failed");
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) items.push("default");
    els.projectSelect.innerHTML = items.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
    if (!items.includes(state.project)) {
      state.project = items[0];
    }
    els.projectSelect.value = state.project;
  }

  async function loadCases() {
    const resp = await fetch(`/api/workbench/cases?project=${encodeURIComponent(state.project)}`);
    if (!resp.ok) throw new Error("load cases failed");
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) {
      els.caseBody.innerHTML = '<tr><td colspan="5">暂无用例</td></tr>';
      return;
    }
    els.caseBody.innerHTML = items
      .map(
        (item) => `
          <tr data-case-id="${escapeHtml(item.case_id)}">
            <td>${escapeHtml(item.case_id)}</td>
            <td>${escapeHtml(item.title)}</td>
            <td>${escapeHtml(item.page)}</td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${formatTime(item.updated_at)}</td>
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
  }

  async function loadCase(caseId) {
    const resp = await fetch(`/api/workbench/cases/${encodeURIComponent(caseId)}?project=${encodeURIComponent(state.project)}`);
    if (!resp.ok) {
      alert("加载用例失败");
      return;
    }
    const payload = await resp.json();
    const item = payload.item || {};
    state.currentCaseId = item.case_id || caseId;
    state.currentCasePath = item.path || "";
    els.currentCase.textContent = state.currentCaseId || "未选择";
    els.currentPath.textContent = state.currentCasePath;
    els.yamlEditor.value = item.yaml_content || "";
    resetLogs();
    setRunStatus("等待执行...");
    els.analysisSummary.textContent = "暂无失败分析数据。";
    els.analysisDetail.innerHTML = "";
  }

  async function saveCase() {
    if (!state.currentCaseId) {
      alert("请先选择用例。");
      return;
    }
    const resp = await fetch(`/api/workbench/cases/${encodeURIComponent(state.currentCaseId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        yaml_content: els.yamlEditor.value,
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`保存失败：${error.detail || resp.statusText}`);
      return;
    }
    await resp.json();
    await loadCases();
    alert("用例已保存。");
  }

  function openEventStream(runId) {
    closeEventSource();
    const source = new EventSource(`/api/workbench/runs/${encodeURIComponent(runId)}/events`);
    state.eventSource = source;
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === "complete") {
          appendLog(`[run] status=${payload.status}`);
          setRunStatus(`执行完成：${payload.status}`);
          closeEventSource();
          loadAnalysis(runId);
          return;
        }
        if (payload.line) {
          appendLog(payload.line);
        }
      } catch (_error) {
        appendLog(event.data);
      }
    };
    source.onerror = () => {
      appendLog("[stream] connection closed");
      closeEventSource();
    };
  }

  async function runCase() {
    if (!state.currentCaseId) {
      alert("请先选择用例。");
      return;
    }
    resetLogs();
    setRunStatus("排队中...");
    els.analysisSummary.textContent = "运行中，等待失败分析...";
    els.analysisDetail.innerHTML = "";
    const resp = await fetch("/api/workbench/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project: state.project,
        case_id: state.currentCaseId,
        case_path: state.currentCasePath,
        source: "manual",
      }),
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`启动失败：${error.detail || resp.statusText}`);
      setRunStatus("启动失败");
      return;
    }
    const payload = await resp.json();
    const job = payload.item || {};
    state.currentRunId = job.run_id || "";
    setRunStatus(`运行中：${state.currentRunId}`);
    openEventStream(state.currentRunId);
  }

  async function loadAnalysis(runId) {
    if (!runId) return;
    const resp = await fetch(`/api/workbench/runs/${encodeURIComponent(runId)}/analysis`);
    if (!resp.ok) return;
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) {
      els.analysisSummary.textContent = "暂无失败分析数据。";
      els.analysisDetail.innerHTML = "";
      return;
    }
    const entry = items[0];
    const analysis = entry.analysis || {};
    const suggestion = entry.suggestion || {};
    els.analysisSummary.textContent = `${analysis.summary || "失败分析已生成"}（风险：${analysis.risk_level || "-"}）`;
    els.analysisDetail.innerHTML = `
      <div>失败类型：${escapeHtml(analysis.failure_category || "-")}</div>
      <div>可能原因：${escapeHtml(analysis.likely_cause || "-")}</div>
      <div>建议动作：${escapeHtml(analysis.recommended_action || "-")}</div>
      <div>置信度：${escapeHtml(analysis.confidence || "-")}</div>
      <div>修复建议：${escapeHtml(suggestion.summary || suggestion.suggestion || "-")}</div>
      <div>证据目录：<code>${escapeHtml(entry.artifact_dir || "-")}</code></div>
    `;
  }

  async function healRun() {
    if (!state.currentRunId) {
      alert("暂无可修复的运行记录。");
      return;
    }
    const resp = await fetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/heal`, {
      method: "POST",
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`修复失败：${error.detail?.message || error.detail || resp.statusText}`);
      return;
    }
    const payload = await resp.json();
    els.analysisSummary.textContent = `修复流程完成：${payload.item?.status || "unknown"}`;
    els.analysisDetail.innerHTML = `<div>修复结果：<code>${escapeHtml(JSON.stringify(payload.item || {}, null, 2))}</code></div>`;
  }

  async function rerunCase() {
    if (!state.currentRunId) {
      alert("暂无可重跑的运行记录。");
      return;
    }
    const resp = await fetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/rerun`, {
      method: "POST",
    });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      alert(`重跑失败：${error.detail || resp.statusText}`);
      return;
    }
    const payload = await resp.json();
    const job = payload.item || {};
    state.currentRunId = job.run_id || "";
    resetLogs();
    setRunStatus(`重跑中：${state.currentRunId}`);
    openEventStream(state.currentRunId);
  }

  function downloadLog() {
    if (!state.currentRunId) {
      alert("暂无日志可下载。");
      return;
    }
    window.open(`/api/workbench/download-log/${encodeURIComponent(state.currentRunId)}`, "_blank");
  }

  function bindEvents() {
    els.projectSelect.addEventListener("change", async () => {
      state.project = els.projectSelect.value;
      await loadCases();
    });
    els.refreshBtn.addEventListener("click", loadCases);
    els.saveBtn.addEventListener("click", saveCase);
    els.runBtn.addEventListener("click", runCase);
    els.healBtn.addEventListener("click", healRun);
    els.rerunBtn.addEventListener("click", rerunCase);
    els.downloadBtn.addEventListener("click", downloadLog);
  }

  async function bootstrap() {
    bindEvents();
    await loadProjects();
    await loadCases();
  }

  bootstrap().catch((error) => {
    console.error(error);
    alert("工作台加载失败，请检查后端服务。");
  });
})();
