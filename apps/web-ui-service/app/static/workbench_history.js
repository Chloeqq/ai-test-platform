(function () {
  const shell = document.getElementById("workbench-history-shell");
  if (!shell) return;

  const els = {
    refreshBtn: document.getElementById("wb-history-refresh"),
    body: document.getElementById("wb-history-body"),
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
    const status = item.status || item.queue_status || item.result || "-";
    let ref = "";
    if (item.run_id) {
      ref = `run:${item.run_id}`;
    } else if (item.path) {
      ref = item.path;
    } else {
      ref = "-";
    }
    return `
      <tr>
        <td>${escapeHtml(formatTime(item.timestamp))}</td>
        <td>${escapeHtml(item.action || "-")}</td>
        <td>${escapeHtml(item.case_id || "-")}</td>
        <td>${escapeHtml(status)}</td>
        <td>${escapeHtml(ref)}</td>
      </tr>
    `;
  }

  async function loadHistory() {
    const resp = await fetch("/api/workbench/history");
    if (!resp.ok) {
      els.body.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
      return;
    }
    const payload = await resp.json();
    const items = payload.items || [];
    if (!items.length) {
      els.body.innerHTML = '<tr><td colspan="5">暂无历史记录</td></tr>';
      return;
    }
    els.body.innerHTML = items.map(renderRow).join("");
  }

  function bindEvents() {
    els.refreshBtn.addEventListener("click", loadHistory);
  }

  function bootstrap() {
    bindEvents();
    loadHistory().catch((error) => {
      console.error(error);
      els.body.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
    });
  }

  bootstrap();
})();
