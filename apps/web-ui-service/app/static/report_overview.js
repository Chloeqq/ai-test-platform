(function () {
  const shell = document.getElementById("report-overview-shell");
  if (!shell) return;

  const els = {
    passRate: document.getElementById("rp-pass-rate"),
    healthScore: document.getElementById("rp-health-score"),
    highRisk: document.getElementById("rp-high-risk"),
    actionable: document.getElementById("rp-actionable"),
    executionMeta: document.getElementById("rp-execution-meta"),
    recentBody: document.getElementById("rp-recent-body"),
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

  function formatFailureSource(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (!normalized) return "-";
    const labels = {
      page_object: "Page Object",
      page_analysis: "页面分析",
      case_design: "用例设计",
      app_bug: "应用缺陷",
      environment: "环境问题",
      unknown: "待确认",
    };
    return labels[normalized] || normalized;
  }

  function renderRow(item) {
    const defects = item.defects || [];
    const defectLabel = defects.length ? defects.map((defect) => defect.defect_id).join("、") : "未关联";
    const sourceLabel = formatFailureSource(item.failure_source);
    const reviewLabel = item.requires_manual_review ? "需要" : "否";
    return `
      <tr>
        <td>${escapeHtml(item.case_id || "-")}</td>
        <td>${escapeHtml(item.summary || "-")}</td>
        <td>${escapeHtml(item.risk_level || "-")}</td>
        <td title="${escapeHtml(item.failure_source || "")}">${escapeHtml(sourceLabel)}</td>
        <td>${escapeHtml(reviewLabel)}</td>
        <td>${escapeHtml(defectLabel)}</td>
        <td>${escapeHtml(formatTime(item.finished_at))}</td>
      </tr>
    `;
  }

  function renderExecutionMeta(meta) {
    if (!els.executionMeta) return;
    const info = meta && typeof meta === "object" ? meta : {};
    const health = String(info.health || "unknown");
    const policy = String(info.policy_mode || "-");
    const manifestCount = Number(info.manifest_record_count || 0);
    const compatCount = Number(info.compat_scan_record_count || 0);
    const runtimeRealtime = Number(info.runtime_realtime_count || 0);
    const runtimeFallback = Number(info.runtime_fallback_count || 0);
    const ratio = Math.round(Number(info.manifest_first_ratio || 0) * 100);
    const warnings = Array.isArray(info.warnings) ? info.warnings.slice(0, 3).map((item) => String(item || "").trim()).filter(Boolean) : [];
    const warning = health !== "healthy" || compatCount > 0 || runtimeFallback > 0;
    const details = [
      `policy=${policy}`,
      `health=${health}`,
      `manifest=${manifestCount}`,
      `compat=${compatCount}`,
      `runtime_realtime=${runtimeRealtime}`,
      `runtime_fallback=${runtimeFallback}`,
      `manifest_ratio=${ratio}%`,
    ].join("，");
    const warningText = warnings.length ? `<br>告警：${warnings.map((item) => escapeHtml(item)).join(" / ")}` : "";
    els.executionMeta.innerHTML = `执行记录来源：${escapeHtml(details)}${warningText}`;
    els.executionMeta.hidden = false;
    els.executionMeta.classList.toggle("warning", warning);
  }

  async function loadOverview() {
    const resp = await fetch("/api/report/overview", { cache: "no-store" });
    if (!resp.ok) {
      els.recentBody.innerHTML = '<tr><td colspan="7">加载失败</td></tr>';
      return;
    }
    const data = await resp.json();
    const summary = data.summary || {};
    renderExecutionMeta(data.execution_meta);
    els.passRate.textContent = `${summary.pass_rate ?? 0}%`;
    els.healthScore.textContent = summary.health_score ?? "-";
    els.highRisk.textContent = summary.high_risk_failures ?? "-";
    els.actionable.textContent = summary.actionable_suggestions ?? "-";

    const items = data.recent_failures || [];
    if (!items.length) {
      els.recentBody.innerHTML = '<tr><td colspan="7">暂无失败记录</td></tr>';
      return;
    }
    els.recentBody.innerHTML = items.map(renderRow).join("");
  }

  loadOverview().catch((error) => {
    console.error(error);
    els.recentBody.innerHTML = '<tr><td colspan="7">加载失败</td></tr>';
  });
})();
