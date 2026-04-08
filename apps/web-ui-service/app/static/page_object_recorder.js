(function () {
  const form = document.getElementById("recorder-form");
  if (!form) return;

  const projectsApi = window.ProjectsApi;
  const projectManager = window.ProjectManagerDialog;
  const projectSelectorSupport = window.ProjectSelectorSupport;
  const GUIDE_STORAGE_KEY = "atp.page-object-recorder.guide.dismissed";

  const els = {
    projectCode: document.getElementById("rec-project-code"),
    manageProject: document.getElementById("rec-manage-project"),
    client: document.getElementById("rec-client"),
    pageCode: document.getElementById("rec-page-code"),
    pageName: document.getElementById("rec-page-name"),
    url: document.getElementById("rec-url"),
    start: document.getElementById("rec-start"),
    heartbeat: document.getElementById("rec-heartbeat"),
    stop: document.getElementById("rec-stop"),
    refresh: document.getElementById("rec-refresh"),
    createCase: document.getElementById("rec-create-case"),
    cleanOrphan: document.getElementById("rec-clean-orphan"),
    manualLink: document.getElementById("rec-manual-link"),
    sessionId: document.getElementById("rec-session-id"),
    sessionStatus: document.getElementById("rec-session-status"),
    sessionPid: document.getElementById("rec-session-pid"),
    sessionScript: document.getElementById("rec-session-script"),
    startedAt: document.getElementById("rec-session-started-at"),
    heartbeatAt: document.getElementById("rec-session-heartbeat-at"),
    stoppedAt: document.getElementById("rec-session-stopped-at"),
    returnLink: document.getElementById("rec-return-link"),
    ingestSummary: document.getElementById("rec-ingest-summary"),
    ingestList: document.getElementById("rec-ingest-list"),
    stepSummary: document.getElementById("rec-step-summary"),
    stepList: document.getElementById("rec-step-list"),
    logList: document.getElementById("rec-log-list"),
    guide: document.getElementById("rec-guide"),
    guideDismiss: document.getElementById("rec-guide-dismiss"),
    guideCancel: document.getElementById("rec-guide-cancel"),
    guideConfirm: document.getElementById("rec-guide-confirm"),
  };

  const state = {
    sessionId: "",
    heartbeatTimer: null,
    allowStartWithoutGuide: false,
    pageCodeDirty: false,
  };

  function safeLocalStorageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (_error) {
      return;
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
    return String(value);
  }

  function setReturnLink(session, firstElementCode, options) {
    if (!els.returnLink) return;
    els.returnLink.href = buildReturnHref(session || {}, firstElementCode || "", options || {});
  }

  function log(message) {
    const timeText = new Date().toLocaleTimeString();
    const item = document.createElement("div");
    item.className = "recorder-item";
    item.innerHTML = "<strong>[" + escapeHtml(timeText) + "]</strong> " + escapeHtml(message);
    els.logList.prepend(item);
    els.logList.classList.remove("empty");
  }

  function normalizeSlug(value, maxLength) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, maxLength || 40);
  }

  function derivePageCodeCandidate() {
    const fromName = normalizeSlug(els.pageName.value, 40);
    if (fromName) return fromName;
    const rawUrl = String(els.url.value || "").trim();
    if (!rawUrl) return "";
    try {
      const parsed = new URL(rawUrl, window.location.origin);
      const joined = parsed.pathname.split("/").filter(Boolean).slice(-2).join("-");
      return normalizeSlug(joined, 40);
    } catch (_error) {
      return normalizeSlug(rawUrl, 40);
    }
  }

  function syncDerivedPageCode() {
    if (state.pageCodeDirty) return;
    const candidate = derivePageCodeCandidate();
    if (candidate) els.pageCode.value = candidate;
  }

  function shouldShowGuide() {
    return safeLocalStorageGet(GUIDE_STORAGE_KEY) !== "1";
  }

  function openGuide() {
    if (!els.guide) return;
    els.guide.classList.remove("hidden");
  }

  function closeGuide() {
    if (!els.guide) return;
    els.guide.classList.add("hidden");
  }

  function buildManualLinkHref() {
    const nextUrl = new URL("/assets/page-objects", window.location.origin);
    nextUrl.searchParams.set("open", "create");
    const projectCode = selectedProjectCode();
    if (projectCode) nextUrl.searchParams.set("project_code", projectCode);
    const client = String(els.client.value || "").trim();
    if (client) nextUrl.searchParams.set("client", client);
    const pageName = String(els.pageName.value || "").trim();
    if (pageName) nextUrl.searchParams.set("prefill_name", pageName);
    const pageUrl = String(els.url.value || "").trim();
    if (pageUrl) nextUrl.searchParams.set("prefill_url", pageUrl);
    return nextUrl.pathname + "?" + nextUrl.searchParams.toString();
  }

  function syncManualLink() {
    if (!els.manualLink) return;
    els.manualLink.href = buildManualLinkHref();
  }

  function buildReturnHref(session, firstElementCode) {
    const options = arguments[2] || {};
    const nextUrl = new URL("/assets/page-objects", window.location.origin);
    const projectCode = session && session.project_code ? String(session.project_code) : selectedProjectCode();
    const client = session && session.client ? String(session.client) : String(els.client.value || "");
    const pageCode = session && session.page_code ? String(session.page_code) : String(els.pageCode.value || "");
    if (projectCode) nextUrl.searchParams.set("project_code", projectCode);
    if (client) nextUrl.searchParams.set("client", client);
    if (pageCode) nextUrl.searchParams.set("page_code", pageCode);
    if (firstElementCode) nextUrl.searchParams.set("element_code", firstElementCode);
    if (options.recorderAction) nextUrl.searchParams.set("recorder_action", String(options.recorderAction));
    if (options.pageStatus) nextUrl.searchParams.set("recorder_page_status", String(options.pageStatus));
    if (options.ingestedCount != null) nextUrl.searchParams.set("recorder_ingested_count", String(options.ingestedCount));
    if (options.stepCount != null) nextUrl.searchParams.set("recorder_step_count", String(options.stepCount));
    nextUrl.searchParams.set("focus", "elements");
    return nextUrl.pathname + "?" + nextUrl.searchParams.toString();
  }

  function setProjectOptions(items, selectedValue) {
    if (!projectSelectorSupport) return;
    projectSelectorSupport.applyProjectOptions(els.projectCode, items, {
      selectedValue: selectedValue || "atp",
      defaultProjectCode: "atp",
      disableInactive: true,
      inactiveLabelSuffix: " (inactive,不可用)",
    });
  }

  function selectedProjectCode() {
    const option = els.projectCode.options[els.projectCode.selectedIndex] || null;
    if (!option || option.disabled) return "";
    return projectSelectorSupport
      ? (projectSelectorSupport.normalizeCode(option.value || "") || "")
      : (String(option.value || "").trim().toLowerCase() || "");
  }

  async function loadProjects(selectedValue) {
    if (!projectsApi || typeof projectsApi.list !== "function" || !projectSelectorSupport) return;
    const items = await projectSelectorSupport.loadProjectOptions({
      projectsApi: projectsApi,
      selectEl: els.projectCode,
      selectedValue: selectedValue || "atp",
      defaultProjectCode: "atp",
      disableInactive: true,
      inactiveLabelSuffix: " (inactive,不可用)",
    });
    setProjectOptions(items, selectedValue || "atp");
    syncManualLink();
  }

  function openProjectManager() {
    if (!projectManager || typeof projectManager.open !== "function" || !projectSelectorSupport) {
      log("项目管理组件未就绪");
      return;
    }
    projectSelectorSupport.openProjectManager({
      projectManager: projectManager,
      projectsApi: projectsApi,
      selectEl: els.projectCode,
      defaultProjectCode: "atp",
      deleteFallbackValue: "atp",
      disableInactive: true,
      inactiveLabelSuffix: " (inactive,不可用)",
      onChanged: async function ({ action, projectCode, items, selectedProjectCode }) {
        setProjectOptions(items, selectedProjectCode || "atp");
        syncManualLink();
        if (action === "create") log("项目 " + selectedProjectCode + " 已创建");
        else if (action === "update") log("项目 " + selectedProjectCode + " 已更新");
        else if (action === "delete") log("项目 " + projectCode + " 已删除");
      },
    });
  }

  async function api(path, options) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      ...options,
    });
    const payload = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const detail = payload && payload.detail ? String(payload.detail) : ("HTTP " + response.status);
      throw new Error(detail);
    }
    return payload;
  }

  function setSessionInfo(session) {
    els.sessionId.textContent = session.session_id || "-";
    els.sessionStatus.textContent = session.status || "-";
    els.sessionPid.textContent = session.process_pid == null ? "-" : String(session.process_pid);
    els.sessionScript.textContent = session.script_path || "-";
    els.startedAt.textContent = formatTime(session.started_at);
    els.heartbeatAt.textContent = formatTime(session.heartbeat_at);
    els.stoppedAt.textContent = formatTime(session.stopped_at);
  }

  function setButtonsForStatus(status) {
    const active = status === "active";
    const canCreateCase = status === "stopped" || status === "failed";
    els.heartbeat.disabled = !active;
    els.stop.disabled = !active;
    els.refresh.disabled = !state.sessionId;
    els.start.disabled = active;
    if (els.createCase) els.createCase.disabled = !state.sessionId || !canCreateCase;
  }

  function stopHeartbeatTimer() {
    if (state.heartbeatTimer) {
      window.clearInterval(state.heartbeatTimer);
      state.heartbeatTimer = null;
    }
  }

  function startHeartbeatTimer() {
    stopHeartbeatTimer();
    state.heartbeatTimer = window.setInterval(async function () {
      if (!state.sessionId) return;
      try {
        const payload = await api("/api/page-objects/recorder/sessions/" + encodeURIComponent(state.sessionId) + "/heartbeat", {
          method: "POST",
          body: JSON.stringify({ heartbeat_by: "ui-auto" }),
        });
        const session = payload.item || {};
        setSessionInfo(session);
        setButtonsForStatus(session.status || "");
        syncStepPreview(session.recorded_steps);
      } catch (_error) {
        stopHeartbeatTimer();
      }
    }, 20000);
  }

  function candidateActionLabel(action) {
    const mapping = {
      ingest: "建议入库",
      review: "建议复核",
      skip: "建议跳过",
    };
    return mapping[action] || "建议复核";
  }

  function candidateRiskLabel(tag) {
    const mapping = {
      dynamic_text: "动态文本",
      visual_node: "视觉节点",
      short_text: "文本过短",
      common_text: "高重复文案",
      long_text: "文案过长",
      index_selector: "索引选择器",
      generic_selector: "选择器过泛",
      xpath_maintenance: "XPath维护成本高",
      id_may_be_dynamic: "疑似动态ID",
      not_used_in_steps: "未出现在步骤中",
      probe_not_found: "回放未命中",
      probe_ambiguous: "回放命中多个",
      probe_not_visible: "回放不可见",
      probe_not_interactable: "回放不可交互",
      probe_error: "回放探测异常",
      probe_unverified: "未完成回放探测",
    };
    return mapping[tag] || String(tag || "");
  }

  function scoreLabel(item) {
    const score = Number(item && item.score ? item.score : 0);
    const tier = String(item && item.quality_tier ? item.quality_tier : "-");
    return tier + " · " + score.toFixed(2);
  }

  function renderElementCandidates(candidates, elements) {
    const list = Array.isArray(candidates) ? candidates : [];
    if (!list.length) {
      const ingested = Array.isArray(elements) ? elements : [];
      if (!ingested.length) {
        els.ingestList.innerHTML = "暂无元素";
        els.ingestList.classList.add("empty");
        return;
      }
      els.ingestList.classList.remove("empty");
      els.ingestList.innerHTML = ingested.map(function (item) {
        return "<div class=\"recorder-item\"><strong>" + escapeHtml(item.element_code || "-") + "</strong> · "
          + escapeHtml(item.locator_type || "-") + " · " + escapeHtml(item.locator_value || "-") + "</div>";
      }).join("");
      return;
    }
    els.ingestList.classList.remove("empty");
    els.ingestList.innerHTML = list.map(function (item) {
      const locatorLabel = item.locator_type === "role" && item.role
        ? (String(item.locator_type || "-") + "(" + String(item.role || "-") + ")")
        : String(item.locator_type || "-");
      const riskTags = Array.isArray(item.risk_tags) ? item.risk_tags : [];
      const riskText = riskTags.length ? riskTags.map(candidateRiskLabel).join(" · ") : "无明显风险";
      const action = String(item.recommended_action || "review");
      const probe = item.probe || {};
      const probeBits = [];
      if (probe && probe.status) probeBits.push("探测: " + String(probe.status));
      if (probe && probe.match_count != null) probeBits.push("匹配数: " + String(probe.match_count));
      if (probe && probe.visible != null) probeBits.push("可见: " + String(probe.visible));
      if (probe && probe.interactable != null) probeBits.push("可交互: " + String(probe.interactable));
      return [
        "<div class=\"recorder-item recorder-candidate recorder-candidate-" + escapeHtml(action) + "\">",
        "<div class=\"recorder-candidate-head\">",
        "<strong>" + escapeHtml(item.element_code || "候选元素" + String(item.index || "-")) + "</strong>",
        "<span class=\"recorder-candidate-score\">" + escapeHtml(scoreLabel(item)) + "</span>",
        "<span class=\"recorder-candidate-action\">" + escapeHtml(candidateActionLabel(action)) + "</span>",
        "</div>",
        "<div class=\"recorder-candidate-meta\">",
        "<span>定位: " + escapeHtml(locatorLabel) + " · " + escapeHtml(String(item.locator_value || "-")) + "</span>",
        "<span>分类: " + escapeHtml(String(item.category || "-")) + " · 命中步骤: " + escapeHtml(String(item.step_hit_count || 0)) + "</span>",
        probeBits.length ? "<span>" + escapeHtml(probeBits.join(" · ")) + "</span>" : "",
        "<span>风险: " + escapeHtml(riskText) + "</span>",
        "</div>",
        "</div>",
      ].join("");
    }).join("");
  }

  function actionLabel(action) {
    const mapping = {
      navigate: "打开页面",
      click: "点击",
      dblclick: "双击",
      fill: "输入",
      press: "按键",
      select_option: "选择",
      check: "勾选",
      uncheck: "取消勾选",
      hover: "悬停",
    };
    return mapping[action] || String(action || "步骤");
  }

  function describeStepTarget(step) {
    if (!step) return "-";
    if (step.element_code) return String(step.element_code);
    if (step.locator_type === "url") return String(step.locator_value || "-");
    if (step.locator_type === "role" && step.role) {
      return String(step.role) + " · " + String(step.locator_value || "-");
    }
    return String(step.locator_type || "-") + " · " + String(step.locator_value || "-");
  }

  function describeStepMeta(step) {
    const parts = [];
    if (step.locator_type && step.locator_type !== "url") parts.push("定位: " + String(step.locator_type));
    if (step.value && step.action !== "navigate") parts.push("值: " + String(step.value));
    return parts;
  }

  function renderRecordedSteps(steps) {
    const list = Array.isArray(steps) ? steps : [];
    if (!list.length) {
      els.stepList.innerHTML = "暂无步骤";
      els.stepList.classList.add("empty");
      return;
    }
    els.stepList.classList.remove("empty");
    els.stepList.innerHTML = list.map(function (step, index) {
      const meta = describeStepMeta(step).map(function (item) {
        return "<span>" + escapeHtml(item) + "</span>";
      }).join("");
      return [
        "<div class=\"recorder-item recorder-step\">",
        "<div class=\"recorder-step-head\">",
        "<span class=\"recorder-step-index\">步骤 " + escapeHtml(String(step.index || (index + 1))) + "</span>",
        "<span class=\"recorder-step-action\">" + escapeHtml(actionLabel(step.action)) + "</span>",
        "<strong class=\"recorder-step-target\">" + escapeHtml(describeStepTarget(step)) + "</strong>",
        "</div>",
        meta ? "<div class=\"recorder-step-meta\">" + meta + "</div>" : "",
        "</div>",
      ].join("");
    }).join("");
  }

  function resetRecordingViews() {
    els.ingestSummary.textContent = "尚未执行入库。";
    els.stepSummary.textContent = "尚未采集步骤。";
    renderElementCandidates([], []);
    renderRecordedSteps([]);
    setReturnLink(null, "");
  }

  function syncStepPreview(steps) {
    const list = Array.isArray(steps) ? steps : [];
    if (list.length) {
      els.stepSummary.textContent = "当前已捕获步骤 " + list.length + " 条。";
    } else if (!state.sessionId) {
      els.stepSummary.textContent = "尚未采集步骤。";
    } else {
      els.stepSummary.textContent = "当前尚未识别到可用步骤。";
    }
    renderRecordedSteps(list);
  }

  async function refreshSession() {
    if (!state.sessionId) return;
    const payload = await api("/api/page-objects/recorder/sessions/" + encodeURIComponent(state.sessionId));
    const session = payload.item || {};
    setSessionInfo(session);
    setButtonsForStatus(session.status || "");
    syncStepPreview(session.recorded_steps);
    if (session.status === "active") startHeartbeatTimer();
    else stopHeartbeatTimer();
  }

  async function startSession() {
    const projectCode = selectedProjectCode();
    if (!projectCode) {
      log("没有可用的 active 项目，请先在项目管理中新增 active 项目");
      return;
    }
    const payload = await api("/api/page-objects/recorder/sessions", {
      method: "POST",
      body: JSON.stringify({
        project_code: projectCode,
        client: els.client.value,
        page_code: els.pageCode.value,
        page_name: els.pageName.value,
        url: els.url.value,
        started_by: "ui-user",
      }),
    });
    const session = payload.item || {};
    state.sessionId = String(session.session_id || "");
    resetRecordingViews();
    setSessionInfo(session);
    setButtonsForStatus(session.status || "");
    startHeartbeatTimer();
    log("录制会话已创建：" + state.sessionId);
  }

  function attachListeners() {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      syncManualLink();
      if (!state.allowStartWithoutGuide && shouldShowGuide()) {
        openGuide();
        return;
      }
      state.allowStartWithoutGuide = false;
      try {
        await startSession();
      } catch (error) {
        log("创建录制会话失败：" + (error instanceof Error ? error.message : "unknown error"));
      }
    });

    els.heartbeat.addEventListener("click", async function () {
      if (!state.sessionId) return;
      try {
        const payload = await api("/api/page-objects/recorder/sessions/" + encodeURIComponent(state.sessionId) + "/heartbeat", {
          method: "POST",
          body: JSON.stringify({ heartbeat_by: "ui-user" }),
        });
        setSessionInfo(payload.item || {});
        syncStepPreview(payload.item && payload.item.recorded_steps);
        log("已发送心跳");
      } catch (error) {
        log("发送心跳失败：" + (error instanceof Error ? error.message : "unknown error"));
      }
    });

    els.stop.addEventListener("click", async function () {
      if (!state.sessionId) return;
      try {
        const payload = await api("/api/page-objects/recorder/sessions/" + encodeURIComponent(state.sessionId) + "/stop", {
          method: "POST",
          body: JSON.stringify({
            ingest_to_page_object: true,
            verify_locators: true,
            verify_timeout_ms: 3500,
            changed_by: "ui-user",
          }),
        });
        const session = payload.session || {};
        const elements = Array.isArray(payload.elements) ? payload.elements : [];
        const candidates = Array.isArray(payload.element_candidates) ? payload.element_candidates : [];
        const steps = Array.isArray(payload.steps) ? payload.steps : [];
        const verification = payload.verification || {};
        const ingestedCount = Number(payload.ingested_count || 0);
        const pageElementTotalCount = Number(payload.page_element_total_count || 0);
        const pageObjectAction = String(payload.page_object_action || "");
        const pageObject = payload.page_object || {};
        const firstElementCode = String(payload.first_element_code || "")
          || (elements.length ? String(elements[0].element_code || "") : "");
        setSessionInfo(session);
        setButtonsForStatus(session.status || "");
        stopHeartbeatTimer();
        if (pageObjectAction === "created") {
          els.ingestSummary.textContent = "已创建页面对象 " + (pageObject.page_code || session.page_code || "-") + "，并入库元素 " + ingestedCount + " 个。";
        } else if (pageObjectAction === "existing") {
          els.ingestSummary.textContent = "已回写到已有页面对象 " + (pageObject.page_code || session.page_code || "-") + "，本次新增元素 " + ingestedCount + " 个。";
        } else {
          els.ingestSummary.textContent = "已入库元素 " + ingestedCount + " 个。";
        }
        if (ingestedCount <= 0 && pageElementTotalCount > 0) {
          els.ingestSummary.textContent += " 当前页面对象累计元素 " + pageElementTotalCount + " 个。";
        }
        if (candidates.length) {
          const ingestableCount = candidates.filter(function (item) { return Boolean(item.ingestible); }).length;
          const skipCount = candidates.filter(function (item) { return String(item.recommended_action || "") === "skip"; }).length;
          els.ingestSummary.textContent += " 候选元素 " + candidates.length + " 个（可入库 " + ingestableCount + "，建议跳过 " + skipCount + "）。";
        }
        if (verification && verification.requested) {
          els.ingestSummary.textContent += " 可用性探测状态：" + String(verification.status || "unknown") + "。";
        }
        els.stepSummary.textContent = steps.length
          ? ("已生成步骤草稿 " + steps.length + " 条，请确认后返回页面对象页。")
          : "本次未识别到可用步骤。";
        renderElementCandidates(candidates, elements);
        renderRecordedSteps(steps);
        setReturnLink(session, firstElementCode, {
          recorderAction: pageObjectAction,
          pageStatus: pageObject.status || "",
          ingestedCount: ingestedCount,
          stepCount: steps.length,
        });
        log("录制会话已停止，页面对象结果为 " + (pageObjectAction || "unknown") + "，入库 " + ingestedCount + " 个元素，生成 " + steps.length + " 条步骤草稿");
      } catch (error) {
        log("停止录制失败：" + (error instanceof Error ? error.message : "unknown error"));
      }
    });

    els.refresh.addEventListener("click", async function () {
      try {
        await refreshSession();
        log("会话状态已刷新");
      } catch (error) {
        log("刷新会话失败：" + (error instanceof Error ? error.message : "unknown error"));
      }
    });

    if (els.cleanOrphan) {
      els.cleanOrphan.addEventListener("click", async function () {
        const previousDisabled = Boolean(els.cleanOrphan.disabled);
        els.cleanOrphan.disabled = true;
        try {
          const payload = await api("/api/page-objects/recorder/artifacts/cleanup", {
            method: "POST",
            body: JSON.stringify({}),
          });
          const item = payload.item || {};
          const scannedCount = Number(item.scanned_file_count || 0);
          const orphanCount = Number(item.orphan_file_count || 0);
          const cleanedCount = Number(item.cleaned_file_count || 0);
          log(
            "孤儿文件清理完成：扫描 "
            + scannedCount
            + " 个，识别孤儿 "
            + orphanCount
            + " 个，已清理 "
            + cleanedCount
            + " 个。"
          );
        } catch (error) {
          log("清理孤儿文件失败：" + (error instanceof Error ? error.message : "unknown error"));
        } finally {
          els.cleanOrphan.disabled = previousDisabled;
        }
      });
    }

    if (els.createCase) {
      els.createCase.addEventListener("click", async function () {
        if (!state.sessionId) return;
        const previousDisabled = Boolean(els.createCase.disabled);
        els.createCase.disabled = true;
        try {
          const payload = await api(
            "/api/page-objects/recorder/sessions/" + encodeURIComponent(state.sessionId) + "/cases/draft",
            {
              method: "POST",
              body: JSON.stringify({
                creator: "ui-user",
                link_page_refs: true,
              }),
            }
          );
          const item = payload.item || {};
          const caseId = String(item.case_id || "").trim();
          const linkedRefCount = Number(item.linked_ref_count || 0);
          const stepCount = Number(item.case_step_count || 0);
          log(
            "测试用例草稿已生成："
            + (caseId || "-")
            + "（步骤 "
            + stepCount
            + "，元素引用 "
            + linkedRefCount
            + "）"
          );
        } catch (error) {
          log("生成测试用例草稿失败：" + (error instanceof Error ? error.message : "unknown error"));
        } finally {
          els.createCase.disabled = previousDisabled;
        }
      });
    }

    if (els.manageProject) {
      els.manageProject.addEventListener("click", function () {
        openProjectManager();
      });
    }

    if (els.guideCancel) {
      els.guideCancel.addEventListener("click", closeGuide);
    }

    if (els.guideConfirm) {
      els.guideConfirm.addEventListener("click", function () {
        if (els.guideDismiss && els.guideDismiss.checked) {
          safeLocalStorageSet(GUIDE_STORAGE_KEY, "1");
        }
        state.allowStartWithoutGuide = true;
        closeGuide();
        form.requestSubmit();
      });
    }

    if (els.guide) {
      els.guide.addEventListener("click", function (event) {
        if (event.target === els.guide) closeGuide();
      });
    }

    els.projectCode.addEventListener("change", syncManualLink);
    els.client.addEventListener("change", syncManualLink);
    els.pageName.addEventListener("input", function () {
      syncDerivedPageCode();
      syncManualLink();
    });
    els.url.addEventListener("input", function () {
      syncDerivedPageCode();
      syncManualLink();
    });
    els.pageCode.addEventListener("input", function () {
      state.pageCodeDirty = Boolean(String(els.pageCode.value || "").trim());
      syncManualLink();
    });

    window.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeGuide();
    });
  }

  async function init() {
    attachListeners();
    syncDerivedPageCode();
    syncManualLink();
    resetRecordingViews();
    if (projectsApi && typeof projectsApi.list === "function") {
      await loadProjects(projectSelectorSupport ? (projectSelectorSupport.normalizeCode(els.projectCode.value || "atp") || "atp") : "atp");
    }
  }

  init().catch(function (error) {
    log("页面初始化失败：" + (error instanceof Error ? error.message : "unknown error"));
  });
})();
