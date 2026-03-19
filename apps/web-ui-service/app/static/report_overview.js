(function () {
  const shell = document.getElementById("report-overview-shell");
  if (!shell) return;

  const els = {
    passRate: document.getElementById("rp-pass-rate"),
    healthScore: document.getElementById("rp-health-score"),
    highRisk: document.getElementById("rp-high-risk"),
    actionable: document.getElementById("rp-actionable"),
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

  function renderRow(item) {
    const defects = item.defects || [];
    const defectLabel = defects.length ? defects.map((defect) => defect.defect_id).join("、") : "未关联";
    return `
      <tr>
        <td>${escapeHtml(item.case_id || "-")}</td>
        <td>${escapeHtml(item.summary || "-")}</td>
        <td>${escapeHtml(item.risk_level || "-")}</td>
        <td>${escapeHtml(defectLabel)}</td>
        <td>${escapeHtml(formatTime(item.finished_at))}</td>
      </tr>
    `;
  }

  async function loadOverview() {
    const resp = await fetch("/api/report/overview");
    if (!resp.ok) {
      els.recentBody.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
      return;
    }
    const data = await resp.json();
    const summary = data.summary || {};
    els.passRate.textContent = `${summary.pass_rate ?? 0}%`;
    els.healthScore.textContent = summary.health_score ?? "-";
    els.highRisk.textContent = summary.high_risk_failures ?? "-";
    els.actionable.textContent = summary.actionable_suggestions ?? "-";

    const items = data.recent_failures || [];
    if (!items.length) {
      els.recentBody.innerHTML = '<tr><td colspan="5">暂无失败记录</td></tr>';
      return;
    }
    els.recentBody.innerHTML = items.map(renderRow).join("");
  }

  loadOverview().catch((error) => {
    console.error(error);
    els.recentBody.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
  });
})();
