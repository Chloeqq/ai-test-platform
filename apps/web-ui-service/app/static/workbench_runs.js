(function () {
  const shared = window.WorkbenchShared;

  function createController(config) {
    const state = config.state;
    const els = config.els;
    const authFetch = config.authFetch;
    const loadCases = config.loadCases;
    const loadCase = config.loadCase;
    const saveEditorCase = config.saveEditorCase;
    const onRunStatusChange = typeof config.onRunStatusChange === "function" ? config.onRunStatusChange : () => {};

    function setRunStatus(text) {
      if (els.runStatus) els.runStatus.textContent = String(text || "等待执行...");
      onRunStatusChange(String(text || "等待执行..."));
    }

    function resetLogs() {
      state.logLines = [];
      if (els.logViewer) els.logViewer.textContent = "";
    }

    function appendLog(line) {
      state.logLines.push(String(line || ""));
      if (state.logLines.length > 500) state.logLines = state.logLines.slice(-500);
      if (els.logViewer) els.logViewer.textContent = state.logLines.join("\n");
    }

    function clearAnalysis() {
      if (els.analysisSummary) els.analysisSummary.textContent = "暂无失败分析数据。";
      if (els.analysisDetail) els.analysisDetail.innerHTML = "";
      if (els.auditTimeline) els.auditTimeline.innerHTML = '<div class="wb-review-empty">运行后将在这里展示审计时间线。</div>';
    }

    function closeEventSource() {
      if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
      }
    }

    function renderAuditTimeline(entries) {
      const rows = Array.isArray(entries) ? entries : [];
      if (!els.auditTimeline) return;
      if (!rows.length) {
        els.auditTimeline.innerHTML = '<div class="wb-review-empty">暂无审计时间线。</div>';
        return;
      }
      els.auditTimeline.innerHTML = rows
        .slice(0, 20)
        .map((item) => {
          return (
            '<div class="wb-audit-line">' +
            "<strong>" +
            shared.escapeHtml(item.action || item.title || "事件") +
            "</strong>" +
            '<div class="wb-audit-meta">' +
            "<span>" +
            shared.escapeHtml(shared.formatTime(item.timestamp || item.created_at)) +
            "</span>" +
            "<span>" +
            shared.escapeHtml(item.actor || item.reviewer || "") +
            "</span>" +
            "</div>" +
            (item.note ? '<p class="wb-audit-note">' + shared.escapeHtml(item.note) + "</p>" : "") +
            "</div>"
          );
        })
        .join("");
    }

    function renderAnalysis(payload) {
      const items = Array.isArray(payload?.items) ? payload.items : [];
      const summary = payload?.failure_source_summary || {};
      if (els.analysisSummary) {
        els.analysisSummary.textContent =
          "失败样本 " + Number(summary.total_failures || items.length || 0) + " 条，主因 " + String(summary.top_source || "unknown");
      }
      if (els.analysisDetail) {
        if (!items.length) {
          els.analysisDetail.innerHTML = '<div class="wb-review-empty">暂无失败样本。</div>';
        } else {
          els.analysisDetail.innerHTML = items
            .slice(0, 10)
            .map((item) => {
              return (
                '<div class="wb-review-card">' +
                "<strong>" +
                shared.escapeHtml(item.failure_source || "unknown") +
                "</strong>" +
                "<p>" +
                shared.escapeHtml(item.summary || item.reason || "暂无摘要") +
                "</p>" +
                "</div>"
              );
            })
            .join("");
        }
      }
    }

    async function loadAnalysis(runId) {
      const payload = await shared.requestJson(authFetch, "/api/workbench/runs/" + encodeURIComponent(runId) + "/analysis", { method: "GET" });
      renderAnalysis(payload);
    }

    async function loadRunContext(runId) {
      const payload = await shared.requestJson(authFetch, "/api/workbench/runs/" + encodeURIComponent(runId), { method: "GET" });
      const item = payload.item && typeof payload.item === "object" ? payload.item : payload;
      state.currentRunId = String(item.run_id || runId);
      setRunStatus("运行状态：" + String(item.status || "unknown"));
      if (els.currentRunHeader) {
        els.currentRunHeader.textContent = String(item.status || "unknown");
      }
      if (item.case_id) {
        state.currentCaseId = String(item.case_id);
        if (!state.currentCasePath) {
          state.currentCasePath = String(item.case_path || "");
        }
      }
      if (state.currentCaseId) {
        loadCase(state.currentCaseId).catch(() => {});
      }
      renderAuditTimeline(item.review_audit_timeline || []);
      await loadAnalysis(state.currentRunId).catch(() => {
        clearAnalysis();
      });
      return item;
    }

    function connectEventStream(runId) {
      closeEventSource();
      const streamUrl = "/api/workbench/runs/" + encodeURIComponent(runId) + "/events";
      const source = new EventSource(streamUrl);
      state.eventSource = source;

      source.onmessage = (event) => {
        appendLog(event.data || "");
        let payload = {};
        try {
          payload = JSON.parse(event.data || "{}");
        } catch (_error) {
          payload = {};
        }
        const status = String(payload.status || payload.event || "").trim();
        if (status) {
          setRunStatus("运行状态：" + status);
        }
        if (status === "passed" || status === "failed" || status === "complete" || payload.event === "complete") {
          loadRunContext(runId).catch(() => {});
          closeEventSource();
          if (typeof loadCases === "function") loadCases(state.casePage, state.casePageSize).catch(() => {});
        }
      };

      source.onerror = () => {
        closeEventSource();
      };
    }

    async function startRun() {
      if (!state.currentCaseId) throw new Error("请先选择用例");
      await saveEditorCase().catch(() => {});
      resetLogs();
      clearAnalysis();
      setRunStatus("提交运行中...");
      const body = await shared.requestJson(authFetch, "/api/workbench/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: String(state.project || "default"),
          case_id: String(state.currentCaseId),
          case_path: String(state.currentCasePath || ""),
          source: "manual",
        }),
      });
      const item = body.item && typeof body.item === "object" ? body.item : body;
      const runId = String(item.run_id || body.run_id || "").trim();
      if (!runId) throw new Error("未返回 run_id");
      state.currentRunId = runId;
      appendLog("run_id=" + runId);
      connectEventStream(runId);
      await loadRunContext(runId).catch(() => {});
    }

    async function rerunCurrent() {
      if (!state.currentRunId) throw new Error("请先执行一次用例");
      const body = await shared.requestJson(authFetch, "/api/workbench/runs/" + encodeURIComponent(state.currentRunId) + "/rerun", {
        method: "POST",
      });
      const item = body.item && typeof body.item === "object" ? body.item : body;
      const runId = String(item.run_id || body.run_id || state.currentRunId);
      state.currentRunId = runId;
      resetLogs();
      connectEventStream(runId);
      await loadRunContext(runId).catch(() => {});
    }

    async function healAndRerun() {
      if (!state.currentRunId) throw new Error("请先执行一次用例");
      const body = await shared.requestJson(
        authFetch,
        "/api/workbench/runs/" + encodeURIComponent(state.currentRunId) + "/heal-and-rerun?wait_seconds=180",
        { method: "POST" }
      );
      const item = body.item && typeof body.item === "object" ? body.item : body;
      const runId = String(item.run_id || body.run_id || state.currentRunId);
      state.currentRunId = runId;
      resetLogs();
      connectEventStream(runId);
      await loadRunContext(runId).catch(() => {});
    }

    function bindEvents() {
      els.runBtn?.addEventListener("click", () => {
        startRun().catch((error) => window.alert(error?.message || "执行失败"));
      });
      els.rerunBtn?.addEventListener("click", () => {
        rerunCurrent().catch((error) => window.alert(error?.message || "重跑失败"));
      });
      els.healBtn?.addEventListener("click", () => {
        healAndRerun().catch((error) => window.alert(error?.message || "自愈重跑失败"));
      });
      els.downloadBtn?.addEventListener("click", () => {
        if (!state.currentRunId) {
          window.alert("暂无可下载日志");
          return;
        }
        window.open("/api/workbench/download-log/" + encodeURIComponent(state.currentRunId), "_blank", "noopener,noreferrer");
      });
    }

    return {
      bindEvents: bindEvents,
      clearAnalysis: clearAnalysis,
      closeEventSource: closeEventSource,
      loadRunContext: loadRunContext,
      resetLogs: resetLogs,
      setRunStatus: setRunStatus,
    };
  }

  window.WorkbenchRuns = {
    createController: createController,
  };
})();
