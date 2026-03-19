(function () {
  const shell = document.getElementById("dashboard-shell");
  if (!shell) return;

  const els = {
    riskCard: document.getElementById("risk-card"),
    riskLevelBadge: document.getElementById("risk-level-badge"),
    riskScore: document.getElementById("risk-score"),
    riskSummary: document.getElementById("risk-summary"),
    summaryPassRate: document.getElementById("summary-pass-rate"),
    summaryExecutionCount: document.getElementById("summary-execution-count"),
    summaryPendingIssues: document.getElementById("summary-pending-issues"),
    trendMeta: document.getElementById("trend-meta"),
    trendSvg: document.getElementById("trend-svg"),
    trendXAxis: document.getElementById("trend-x-axis"),
    flakyList: document.getElementById("flaky-list"),
    gateBody: document.getElementById("gate-body"),
    pendingIssuesList: document.getElementById("pending-issues-list"),
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
      return new Date(value).toLocaleString("zh-CN", { hour12: false });
    } catch (_error) {
      return String(value);
    }
  }

  function riskClass(level) {
    if (level === "高") return "risk-high";
    if (level === "中") return "risk-medium";
    return "risk-low";
  }

  function gateStatusLabel(status) {
    if (status === "intercepted") return "拦截";
    if (status === "warning") return "预警";
    return "通过";
  }

  function renderRisk(risk) {
    const level = risk.level || "低";
    els.riskCard.classList.remove("risk-low", "risk-medium", "risk-high");
    els.riskCard.classList.add(riskClass(level));
    els.riskCard.href = risk.detail_url || "/quality/trends";
    els.riskLevelBadge.textContent = level;
    els.riskScore.textContent = String(risk.score ?? 0);
    els.riskSummary.textContent = risk.summary || "暂无风险说明。";
  }

  function renderSummary(summary) {
    els.summaryPassRate.textContent = `${summary.pass_rate_24h ?? 0}%`;
    els.summaryExecutionCount.textContent = String(summary.execution_count_24h ?? 0);
    els.summaryPendingIssues.textContent = String(summary.pending_issues ?? 0);
  }

  function toPolylinePoints(values, min, max, width, height, padLeft, padRight, padTop, padBottom) {
    const count = values.length;
    if (!count) return "";
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;
    const safeMax = max <= min ? min + 1 : max;
    return values
      .map((value, idx) => {
        const x = padLeft + (count === 1 ? plotW / 2 : (plotW * idx) / (count - 1));
        const y = padTop + ((safeMax - value) / (safeMax - min)) * plotH;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  }

  function renderTrend(points) {
    if (!points || !points.length) {
      els.trendMeta.textContent = "暂无趋势数据。";
      els.trendSvg.innerHTML = "";
      return;
    }

    const width = 960;
    const height = 280;
    const padLeft = 42;
    const padRight = 16;
    const padTop = 18;
    const padBottom = 34;

    const passRates = points.map((item) => Number(item.pass_rate) || 0);
    const execCounts = points.map((item) => Number(item.execution_count) || 0);
    const latest = points[points.length - 1];
    const latestExec = execCounts[execCounts.length - 1];
    const execMax = Math.max(...execCounts, 1);
    const execScaled = execCounts.map((item) => (item / execMax) * 100);
    const passPoints = toPolylinePoints(passRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const execPoints = toPolylinePoints(execScaled, 0, 100, width, height, padLeft, padRight, padTop, padBottom);

    const gridYValues = [0, 25, 50, 75, 100];
    const plotH = height - padTop - padBottom;
    const plotW = width - padLeft - padRight;
    const gridLines = gridYValues
      .map((value) => {
        const y = padTop + ((100 - value) / 100) * plotH;
        return `<line x1="${padLeft}" y1="${y}" x2="${padLeft + plotW}" y2="${y}" stroke="#d7e2ef" stroke-width="1" stroke-dasharray="4 4"></line>`;
      })
      .join("");

    const passEndX = padLeft + plotW;
    const passEndY = padTop + ((100 - passRates[passRates.length - 1]) / 100) * plotH;
    const execEndY = padTop + ((100 - execScaled[execScaled.length - 1]) / 100) * plotH;

    els.trendSvg.innerHTML = `
      ${gridLines}
      <polyline fill="none" stroke="#2f79db" stroke-width="3" points="${passPoints}"></polyline>
      <polyline fill="none" stroke="#de8a23" stroke-width="2.5" points="${execPoints}"></polyline>
      <circle cx="${passEndX}" cy="${passEndY}" r="4" fill="#2f79db"></circle>
      <circle cx="${passEndX}" cy="${execEndY}" r="4" fill="#de8a23"></circle>
      <text x="${padLeft}" y="${padTop - 4}" fill="#7489a7" font-size="11">通过率 %</text>
      <text x="${width - 74}" y="${padTop - 4}" fill="#7489a7" font-size="11">执行次数(归一化)</text>
    `;

    const labelIndexes = [0, 4, 8, 12, 16, 20, points.length - 1];
    els.trendXAxis.innerHTML = labelIndexes
      .map((idx) => `<span>${escapeHtml(points[idx]?.hour || "")}</span>`)
      .join("");

    els.trendMeta.textContent =
      `当前时段通过率 ${latest.pass_rate}% ，执行次数 ${latestExec} 次。` +
      ` 蓝线为通过率，橙线为执行量趋势。`;
  }

  function renderFlaky(rows) {
    if (!rows || !rows.length) {
      els.flakyList.innerHTML = '<li class="empty-line">暂无Flaky用例数据。</li>';
      return;
    }
    els.flakyList.innerHTML = rows
      .map((item) => {
        const rate = Number(item.flaky_rate || 0).toFixed(1);
        return `
          <li class="flaky-item">
            <div class="flaky-item-top">
              <a href="/assets/cases/${item.case_id}">${escapeHtml(item.name)}</a>
              <span class="flaky-rate">${rate}%</span>
            </div>
            <div class="flaky-bar"><span style="width: ${Math.min(Number(rate), 100)}%"></span></div>
            <p class="flaky-meta">模块：${escapeHtml(item.module)} | 运行：${item.total_runs} 次 | 波动：${item.unstable_runs} 次</p>
          </li>
        `;
      })
      .join("");
  }

  function renderGate(rows) {
    if (!rows || !rows.length) {
      els.gateBody.innerHTML = '<tr><td colspan="4">暂无门禁记录</td></tr>';
      return;
    }
    els.gateBody.innerHTML = rows
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.pr_key)}</td>
            <td>${escapeHtml(item.branch)}</td>
            <td><span class="gate-status ${escapeHtml(item.gate_status)}">${gateStatusLabel(item.gate_status)}</span></td>
            <td>${formatTime(item.executed_at)}</td>
          </tr>
        `
      )
      .join("");
  }

  function renderPendingIssues(rows) {
    if (!rows || !rows.length) {
      els.pendingIssuesList.innerHTML = '<li class="empty-line">暂无待处理问题。</li>';
      return;
    }
    els.pendingIssuesList.innerHTML = rows
      .map(
        (item) => `
          <li class="issue-item">
            <div class="issue-top">
              <span class="issue-title">${escapeHtml(item.issue_key)} · ${escapeHtml(item.title)}</span>
              <span class="issue-status">${escapeHtml(item.status)}</span>
            </div>
            <p class="issue-meta">${escapeHtml(item.agent)} 推荐，置信度 ${(Number(item.confidence || 0) * 100).toFixed(0)}%</p>
            <p class="issue-recommendation">${escapeHtml(item.recommendation)}</p>
            <a class="issue-link" href="${escapeHtml(item.detail_url || "#")}">进入确认</a>
          </li>
        `
      )
      .join("");
  }

  async function loadDashboard() {
    const response = await fetch("/api/dashboard/overview");
    if (!response.ok) {
      throw new Error("load dashboard failed");
    }
    const payload = await response.json();
    renderRisk(payload.risk || {});
    renderSummary(payload.summary || {});
    renderTrend(payload.trend_24h || []);
    renderFlaky(payload.top_flaky || []);
    renderGate(payload.gate_last10 || []);
    renderPendingIssues(payload.pending_issues || []);
  }

  loadDashboard().catch((error) => {
    console.error(error);
    els.riskSummary.textContent = "仪表盘加载失败，请检查服务状态与日志。";
    els.trendMeta.textContent = "趋势图加载失败。";
    els.flakyList.innerHTML = '<li class="empty-line">Flaky列表加载失败。</li>';
    els.gateBody.innerHTML = '<tr><td colspan="4">门禁数据加载失败</td></tr>';
    els.pendingIssuesList.innerHTML = '<li class="empty-line">待处理问题加载失败。</li>';
  });
})();
