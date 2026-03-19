(function () {
  const shell = document.getElementById("report-performance-shell");
  if (!shell) return;

  const els = {
    avg: document.getElementById("rp-perf-avg"),
    max: document.getElementById("rp-perf-max"),
    delta: document.getElementById("rp-perf-delta"),
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

  async function loadPerformance() {
    const resp = await fetch("/api/report/performance");
    if (!resp.ok) {
      els.body.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
      return;
    }
    const data = await resp.json();
    const summary = data.summary || {};
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
