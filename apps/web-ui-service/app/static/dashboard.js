(function () {
  const shell = document.getElementById("dashboard-shell");
  if (!shell) return;

  const els = {
    riskCard: document.getElementById("risk-card"),
    riskLevelBadge: document.getElementById("risk-level-badge"),
    riskScore: document.getElementById("risk-score"),
    riskSummary: document.getElementById("risk-summary"),
    dashboardAsOf: document.getElementById("dashboard-as-of"),
    dashboardRiskLevel: document.getElementById("dashboard-risk-level"),
    dashboardRiskAdvice: document.getElementById("dashboard-risk-advice"),
    riskStripPassRate: document.getElementById("risk-strip-pass-rate"),
    riskStripExecutionCount: document.getElementById("risk-strip-execution-count"),
    riskStripPendingIssues: document.getElementById("risk-strip-pending-issues"),
    summaryPassRate: document.getElementById("summary-pass-rate"),
    summaryExecutionCount: document.getElementById("summary-execution-count"),
    summaryInterceptedLast10: document.getElementById("summary-intercepted-last10"),
    summaryPendingIssues: document.getElementById("summary-pending-issues"),
    trendMeta: document.getElementById("trend-meta"),
    trendSvg: document.getElementById("trend-svg"),
    trendXAxis: document.getElementById("trend-x-axis"),
    qgTrendMeta: document.getElementById("qg-trend-meta"),
    qgTotalEvents24h: document.getElementById("qg-total-events-24h"),
    qgBlockedEvents24h: document.getElementById("qg-blocked-events-24h"),
    qgBlockRate24h: document.getElementById("qg-block-rate-24h"),
    qgTopAlert24hLink: document.getElementById("qg-top-alert-24h-link"),
    qgTopAlert24hCount: document.getElementById("qg-top-alert-24h-count"),
    qgTrendSvg: document.getElementById("qg-trend-svg"),
    qgTrendXAxis: document.getElementById("qg-trend-x-axis"),
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

  function riskAdvice(level) {
    if (level === "高") return "优先处理";
    if (level === "中") return "持续关注";
    return "可推进回归";
  }

  function gateStatusLabel(status) {
    if (status === "intercepted") return "拦截";
    if (status === "warning") return "预警";
    return "通过";
  }

  function renderRisk(risk) {
    const level = risk.level || "待评估";
    els.riskCard.classList.remove("risk-low", "risk-medium", "risk-high");
    els.riskCard.classList.add(riskClass(level));
    els.riskCard.href = risk.detail_url || "/quality/trends";
    els.riskLevelBadge.textContent = level;
    els.riskScore.textContent = String(risk.score ?? 0);
    els.riskSummary.textContent = risk.summary || "暂无风险说明。";
    if (els.dashboardRiskLevel) {
      els.dashboardRiskLevel.textContent = level;
    }
    if (els.dashboardRiskAdvice) {
      els.dashboardRiskAdvice.textContent = level === "待评估" ? "等待数据" : riskAdvice(level);
    }
  }

  function renderSummary(summary) {
    const passRateText = summary.pass_rate_24h === null || summary.pass_rate_24h === undefined ? "暂无数据" : `${summary.pass_rate_24h}%`;
    const executionCountText = summary.execution_count_24h === null || summary.execution_count_24h === undefined ? "暂无数据" : String(summary.execution_count_24h);
    const pendingIssuesText = summary.pending_issues === null || summary.pending_issues === undefined ? "暂无数据" : String(summary.pending_issues);
    els.summaryPassRate.textContent = passRateText;
    els.summaryExecutionCount.textContent = executionCountText;
    if (els.summaryInterceptedLast10) {
      els.summaryInterceptedLast10.textContent = summary.intercepted_last10 === null || summary.intercepted_last10 === undefined ? "暂无数据" : String(summary.intercepted_last10);
    }
    els.summaryPendingIssues.textContent = pendingIssuesText;
    if (els.riskStripPassRate) {
      els.riskStripPassRate.textContent = passRateText;
    }
    if (els.riskStripExecutionCount) {
      els.riskStripExecutionCount.textContent = executionCountText;
    }
    if (els.riskStripPendingIssues) {
      els.riskStripPendingIssues.textContent = pendingIssuesText;
    }
    if (els.dashboardAsOf) {
      els.dashboardAsOf.textContent = summary.as_of ? formatTime(summary.as_of) : "暂无更新";
    }
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

  function buildPointCoordinates(values, min, max, width, height, padLeft, padRight, padTop, padBottom) {
    const count = values.length;
    if (!count) return [];
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;
    const safeMax = max <= min ? min + 1 : max;
    return values.map((value, idx) => {
      const x = padLeft + (count === 1 ? plotW / 2 : (plotW * idx) / (count - 1));
      const y = padTop + ((safeMax - value) / (safeMax - min)) * plotH;
      return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
    });
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
    const pointCoords = buildPointCoordinates(passRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);

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
    const pointMarkers = pointCoords
      .map((point, idx) => {
        const item = points[idx] || {};
        const passRate = Number(item.pass_rate || 0);
        const execCount = Number(item.execution_count || 0);
        return `
          <circle class="chart-point chart-point-pass" cx="${point.x}" cy="${point.y}" r="4" tabindex="0">
            <title>${escapeHtml(`${item.hour || "-"} | 通过率 ${passRate}% | 执行 ${execCount} 次`)}</title>
          </circle>
        `;
      })
      .join("");

    els.trendSvg.innerHTML = `
      ${gridLines}
      <polyline fill="none" stroke="#2f79db" stroke-width="3" points="${passPoints}"></polyline>
      <polyline fill="none" stroke="#de8a23" stroke-width="2.5" points="${execPoints}"></polyline>
      ${pointMarkers}
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

  function renderQualityGateTrend(summary, points) {
    const qgSummary = summary && typeof summary === "object" ? summary : {};
    const trendPoints = Array.isArray(points) ? points : [];
    const totalEvents = Number(qgSummary.total_events || 0);
    const blockedEvents = Number(qgSummary.blocked_events || 0);
    const blockRate = Number(qgSummary.block_rate || 0);
    const topAlertCode = String(qgSummary.top_alert_code || "-") || "-";
    const topAlertCount = Number(qgSummary.top_alert_count || 0);
    const topPage = String(qgSummary.top_page || "").trim();

    els.qgTotalEvents24h.textContent = String(totalEvents);
    els.qgBlockedEvents24h.textContent = String(blockedEvents);
    els.qgBlockRate24h.textContent = `${Math.round(blockRate * 100)}%`;
    if (els.qgTopAlert24hLink) {
      els.qgTopAlert24hLink.textContent = topAlertCode;
      if (topAlertCode === "-") {
        els.qgTopAlert24hLink.href = "/quality/clusters";
      } else {
        const query = new URLSearchParams({ alert_code: topAlertCode });
        if (topPage) {
          query.set("page", topPage);
        }
        els.qgTopAlert24hLink.href = `/quality/clusters?${query.toString()}`;
      }
    }
    els.qgTopAlert24hCount.textContent = topAlertCode === "-" ? "暂无拦截告警" : `${topAlertCount} 次命中`;

    if (!trendPoints.length) {
      els.qgTrendMeta.textContent = "暂无 quality gate 趋势数据。";
      els.qgTrendSvg.innerHTML = "";
      els.qgTrendXAxis.innerHTML = "";
      return;
    }

    const width = 960;
    const height = 220;
    const padLeft = 42;
    const padRight = 16;
    const padTop = 18;
    const padBottom = 34;
    const blockedCounts = trendPoints.map((item) => Number(item.block || 0));
    const blockRates = trendPoints.map((item) => Number(item.block_rate || 0) * 100);
    const maxBlocked = Math.max(...blockedCounts, 1);
    const blockedScaled = blockedCounts.map((item) => (item / maxBlocked) * 100);
    const blockedLine = toPolylinePoints(blockedScaled, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const blockRateLine = toPolylinePoints(blockRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const pointCoords = buildPointCoordinates(blockRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const plotH = height - padTop - padBottom;
    const plotW = width - padLeft - padRight;

    const gridYValues = [0, 25, 50, 75, 100];
    const gridLines = gridYValues
      .map((value) => {
        const y = padTop + ((100 - value) / 100) * plotH;
        return `<line x1="${padLeft}" y1="${y}" x2="${padLeft + plotW}" y2="${y}" stroke="#d7e2ef" stroke-width="1" stroke-dasharray="4 4"></line>`;
      })
      .join("");

    els.qgTrendSvg.innerHTML = `
      ${gridLines}
      <polyline fill="none" stroke="#d24f4f" stroke-width="3" points="${blockedLine}"></polyline>
      <polyline fill="none" stroke="#6f7fc8" stroke-width="2.5" points="${blockRateLine}"></polyline>
      ${pointCoords
        .map((point, idx) => {
          const item = trendPoints[idx] || {};
          const blockCount = Number(item.block || 0);
          const blockRate = Number(item.block_rate || 0) * 100;
          return `
            <circle class="chart-point chart-point-block" cx="${point.x}" cy="${point.y}" r="4" tabindex="0">
              <title>${escapeHtml(`${item.hour || "-"} | 拦截 ${blockCount} 次 | 拦截率 ${Math.round(blockRate)}%`)}</title>
            </circle>
          `;
        })
        .join("")}
      <text x="${padLeft}" y="${padTop - 4}" fill="#7489a7" font-size="11">拦截次数(归一化)</text>
      <text x="${width - 74}" y="${padTop - 4}" fill="#7489a7" font-size="11">拦截率 %</text>
    `;

    const labelIndexes = [0, 4, 8, 12, 16, 20, trendPoints.length - 1];
    els.qgTrendXAxis.innerHTML = labelIndexes.map((idx) => `<span>${escapeHtml(trendPoints[idx]?.hour || "")}</span>`).join("");
    const latest = trendPoints[trendPoints.length - 1] || {};
    els.qgTrendMeta.textContent =
      `最近24小时 quality gate 事件 ${totalEvents} 次，拦截 ${blockedEvents} 次（拦截率 ${Math.round(blockRate * 100)}%）。` +
      ` 当前小时拦截 ${latest.block || 0} 次。`;
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
      els.gateBody.innerHTML = '<tr><td colspan="6">暂无门禁记录</td></tr>';
      return;
    }
    els.gateBody.innerHTML = rows
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.pr_key)}</td>
            <td>${escapeHtml(item.case_name || "-")}</td>
            <td>${escapeHtml(item.branch)}</td>
            <td><span class="gate-status ${escapeHtml(item.gate_status)}">${gateStatusLabel(item.gate_status)}</span></td>
            <td class="gate-reason" title="${escapeHtml(item.reason || "-")}">${escapeHtml(item.reason || "-")}</td>
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

  function renderLoadError() {
    els.riskSummary.textContent = "仪表盘加载失败，请检查服务状态与日志。";
    els.trendMeta.textContent = "趋势图加载失败。";
    els.qgTrendMeta.textContent = "quality gate 趋势加载失败。";
    els.flakyList.innerHTML = '<li class="empty-line">Flaky列表加载失败。</li>';
    els.gateBody.innerHTML = '<tr><td colspan="6">门禁数据加载失败</td></tr>';
    els.pendingIssuesList.innerHTML = '<li class="empty-line">待处理问题加载失败。</li>';
  }

  async function loadDashboard() {
    const [overviewResult, qgResult] = await Promise.allSettled([
      fetch("/api/dashboard/overview", { cache: "no-store" }),
      fetch("/api/workbench/quality-gates/summary?limit=2000", { cache: "no-store" }),
    ]);
    if (overviewResult.status !== "fulfilled") {
      throw new Error("load dashboard failed");
    }
    const overviewResponse = overviewResult.value;
    if (!overviewResponse.ok) {
      throw new Error("load dashboard failed");
    }
    const payload = await overviewResponse.json();
    renderRisk(payload.risk || {});
    renderSummary({ ...(payload.summary || {}), as_of: payload.as_of || "" });
    renderTrend(payload.trend_24h || []);
    renderFlaky(payload.top_flaky || []);
    renderGate(payload.gate_last10 || []);
    renderPendingIssues(payload.pending_issues || []);

    if (qgResult.status === "fulfilled" && qgResult.value.ok) {
      const qgPayload = await qgResult.value.json();
      const item = qgPayload.item || {};
      renderQualityGateTrend(item.summary_24h || {}, item.decision_trend_24h || []);
    } else {
      renderQualityGateTrend({}, []);
      els.qgTrendMeta.textContent = "quality gate 趋势加载失败。";
    }
  }

  let refreshInFlight = false;

  async function refreshDashboard() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    try {
      await loadDashboard();
    } finally {
      refreshInFlight = false;
    }
  }

  refreshDashboard().catch((error) => {
    console.error(error);
    renderLoadError();
  });

  window.setInterval(() => {
    refreshDashboard().catch((error) => {
      console.error(error);
      renderLoadError();
    });
  }, 60000);
})();
