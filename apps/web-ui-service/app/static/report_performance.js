(function () {
  const shell = document.getElementById("report-performance-shell");
  if (!shell) return;

  const els = {
    avg: document.getElementById("rp-perf-avg"),
    max: document.getElementById("rp-perf-max"),
    delta: document.getElementById("rp-perf-delta"),
    executionMeta: document.getElementById("rp-execution-meta"),
    body: document.getElementById("rp-perf-body"),
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

  function renderRow(item) {
    const duration = typeof item.duration_seconds === "number" ? item.duration_seconds.toFixed(2) : "-";
    return `
      <tr>
        <td>${escapeHtml(item.run_id || "-")}</td>
        <td>${escapeHtml(item.case_id || "-")}</td>
        <td>${escapeHtml(item.status || "-")}</td>
        <td>${escapeHtml(duration)}</td>
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

  async function loadPerformance() {
    const resp = await fetch("/api/report/performance", { cache: "no-store" });
    if (!resp.ok) {
      els.body.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
      return;
    }
    const data = await resp.json();
    const summary = data.summary || {};
    renderExecutionMeta(data.execution_meta);
    els.avg.textContent = `${summary.average_duration_seconds ?? 0}s`;
    els.max.textContent = `${summary.max_duration_seconds ?? 0}s`;
    els.delta.textContent = `${summary.latest_delta_seconds ?? 0}s`;

    const items = data.slow_cases || [];
    if (!items.length) {
      els.body.innerHTML = '<tr><td colspan="5">暂无数据</td></tr>';
      return;
    }
    els.body.innerHTML = items.map(renderRow).join("");
  }

  loadPerformance().catch((error) => {
    console.error(error);
    els.body.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
  });
})();
