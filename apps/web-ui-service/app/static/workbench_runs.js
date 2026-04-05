(function () {
  const shared = window.WorkbenchShared;
  if (!shared) return;

  function createController({
    state,
    els,
    authFetch,
    focusReviewType,
    loadCases,
    loadCase,
    saveEditorCase,
    onRunStatusChange,
  }) {
    function setRunStatus(text) {
      els.runStatus.textContent = String(text || "");
      if (typeof onRunStatusChange === "function") {
        onRunStatusChange(String(text || ""));
      }
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

    function clearAnalysis() {
      els.analysisSummary.textContent = "暂无失败分析数据。";
      els.analysisDetail.innerHTML = "";
      shared.renderAuditTimeline(els.auditTimeline, [], focusReviewType);
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

    async function loadAnalysis(runId) {
      if (!runId) return;
      const [analysisResp, runResp] = await Promise.all([
        authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}/analysis`),
        authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`),
      ]);
      if (!analysisResp.ok && !runResp.ok) return;
      const payload = analysisResp.ok ? await analysisResp.json() : { items: [] };
      const runPayload = runResp.ok ? await runResp.json() : { item: {} };
      const items = payload.items || [];
      const runItem = runPayload.item || {};
      const reviewSummaryHtml = shared.renderReviewSummary(runItem.review_state);
      const reviewAuditHtml = shared.renderReviewAuditSummary(runItem.review_audit_summary);
      const executionGateHtml = shared.renderExecutionGateSummary(runItem.execution_gate);
      shared.renderAuditTimeline(els.auditTimeline, runItem.review_audit_timeline, focusReviewType);
      if (!items.length) {
        const pageLabel = runItem.page ? `页面 ${runItem.page}` : "当前运行";
        els.analysisSummary.textContent = `${pageLabel} 暂无失败分析数据。`;
        els.analysisDetail.innerHTML = `${reviewSummaryHtml}${executionGateHtml}${reviewAuditHtml}`;
        return;
      }
      const entry = items[0];
      const analysis = entry.analysis || {};
      const suggestion = entry.suggestion || {};
      els.analysisSummary.textContent = `${analysis.summary || "失败分析已生成"}（风险：${analysis.risk_level || "-"}）`;
      els.analysisDetail.innerHTML = `
        ${reviewSummaryHtml}
        ${executionGateHtml}
        ${reviewAuditHtml}
        <div>失败类型：${shared.escapeHtml(analysis.failure_category || "-")}</div>
        <div>失败来源：${shared.escapeHtml(analysis.failure_source || "-")}</div>
        <div>来源依据：${shared.escapeHtml(analysis.failure_source_reason || "-")}</div>
        <div>来源证据：${shared.escapeHtml(shared.renderSourceEvidence(analysis.source_evidence))}</div>
        <div>需人工复核：${shared.escapeHtml(analysis.requires_manual_review ? "是" : "否")}</div>
        <div>可能原因：${shared.escapeHtml(analysis.likely_cause || "-")}</div>
        <div>建议动作：${shared.escapeHtml(analysis.recommended_action || "-")}</div>
        <div>置信度：${shared.escapeHtml(analysis.confidence || "-")}</div>
        <div>修复建议：${shared.escapeHtml(suggestion.summary || suggestion.suggestion || "-")}</div>
        <div>证据目录：<code>${shared.escapeHtml(entry.artifact_dir || "-")}</code></div>
      `;
    }

    async function runCase() {
      const savedCaseId = await saveEditorCase({ announce: false });
      if (!savedCaseId) return;
      resetLogs();
      clearAnalysis();
      setRunStatus("排队中...");
      const resp = await authFetch("/api/workbench/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: state.project,
          case_id: savedCaseId,
          case_path: state.currentCasePath,
          source: "manual",
        }),
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        window.alert(`启动失败：${error.detail || resp.statusText}`);
        setRunStatus("启动失败");
        return;
      }
      const payload = await resp.json();
      const job = payload.item || {};
      state.currentRunId = job.run_id || "";
      setRunStatus(`运行中：${state.currentRunId}`);
      openEventStream(state.currentRunId);
    }

    async function healRun() {
      if (!state.currentRunId) {
        window.alert("暂无可修复的运行记录。");
        return;
      }
      setRunStatus("修复并重跑中...");
      const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/heal-and-rerun`, {
        method: "POST",
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        window.alert(`修复并重跑失败：${error.detail?.message || error.detail || resp.statusText}`);
        return;
      }
      const payload = await resp.json();
      const item = payload.item || {};
      const heal = item.heal || {};
      const rerun = item.rerun || {};
      const rerunRunId = rerun.run_id || "";
      if (rerunRunId) {
        state.currentRunId = rerunRunId;
      }
      const healText = heal.ok ? `修复完成（${heal.item?.status || "ok"}）` : "修复未成功，已直接重跑";
      const rerunStatus = rerun.status || "running";
      els.analysisSummary.textContent = `${healText}；重跑状态：${rerunStatus}`;
      els.analysisDetail.innerHTML = `<pre><code>${shared.escapeHtml(JSON.stringify(item, null, 2))}</code></pre>`;
      shared.renderAuditTimeline(els.auditTimeline, [], focusReviewType);
      if (rerunStatus === "running") {
        openEventStream(state.currentRunId);
        return;
      }
      setRunStatus(`执行完成：${rerunStatus}`);
      loadAnalysis(state.currentRunId);
    }

    async function rerunCase() {
      if (!state.currentRunId) {
        window.alert("暂无可重跑的运行记录。");
        return;
      }
      const resp = await authFetch(`/api/workbench/runs/${encodeURIComponent(state.currentRunId)}/rerun`, {
        method: "POST",
      });
      if (!resp.ok) {
        const error = await resp.json().catch(() => ({}));
        window.alert(`重跑失败：${error.detail || resp.statusText}`);
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
        window.alert("暂无日志可下载。");
        return;
      }
      window.open(`/api/workbench/download-log/${encodeURIComponent(state.currentRunId)}`, "_blank");
    }

    async function loadRunContext(runId) {
      const response = await authFetch(`/api/workbench/runs/${encodeURIComponent(runId)}`);
      if (!response.ok) {
        throw new Error("load run failed");
      }
      const payload = await response.json().catch(() => ({}));
      const item = payload.item || {};
      if (item.project && item.project !== state.project) {
        state.project = item.project;
        els.projectSelect.value = state.project;
      }
      if (item.case_id) {
        await loadCases(state.casePage, state.casePageSize, item.case_id);
        await loadCase(item.case_id);
      } else {
        await loadCases(state.casePage, state.casePageSize);
      }
      state.currentRunId = item.run_id || runId;
      setRunStatus(`已定位运行：${state.currentRunId}（${item.status || "unknown"}）`);
      await loadAnalysis(state.currentRunId);
      if (state.currentRunId) {
        openEventStream(state.currentRunId);
      }
      els.analysisSummary.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function bindEvents() {
      els.runBtn.addEventListener("click", () => {
        runCase().catch((error) => window.alert(error.message || "执行失败"));
      });
      els.healBtn.addEventListener("click", () => {
        healRun().catch((error) => window.alert(error.message || "修复失败"));
      });
      els.rerunBtn.addEventListener("click", () => {
        rerunCase().catch((error) => window.alert(error.message || "重跑失败"));
      });
      els.downloadBtn.addEventListener("click", downloadLog);
    }

    return {
      bindEvents,
      clearAnalysis,
      closeEventSource,
      loadAnalysis,
      loadRunContext,
      resetLogs,
      setRunStatus,
    };
  }

  window.WorkbenchRuns = { createController };
})();
