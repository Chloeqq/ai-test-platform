(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") {
      return window.platformFormatDateTime(value);
    }
    return String(value || "").trim() || "-";
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

  function renderIssueList(element, rows, emptyText) {
    if (!element) return;
    if (!rows.length) {
      element.innerHTML = `<li class="empty-line">${escapeHtml(emptyText)}</li>`;
      return;
    }
    element.innerHTML = rows
      .map(
        (item) => `
          <li class="issue-item">
            <div class="issue-top">
              <span class="issue-title">${escapeHtml(item.title || "-")}</span>
              ${item.status ? `<span class="issue-status">${escapeHtml(item.status)}</span>` : ""}
            </div>
            ${item.meta ? `<p class="issue-meta">${escapeHtml(item.meta)}</p>` : ""}
            <p class="issue-recommendation">${escapeHtml(item.summary || "-")}</p>
            ${item.href ? `<a class="issue-link" href="${escapeHtml(item.href)}">进入对应页面</a>` : ""}
          </li>
        `
      )
      .join("");
  }

  function renderRisk(els, risk) {
    const level = risk.level || "待评估";
    if (els.riskCard) {
      els.riskCard.classList.remove("risk-low", "risk-medium", "risk-high");
      els.riskCard.classList.add(riskClass(level));
      els.riskCard.href = risk.detail_url || "/quality/trends";
    }
    if (els.riskLevelBadge) els.riskLevelBadge.textContent = level;
    if (els.riskScore) els.riskScore.textContent = String(risk.score ?? 0);
    if (els.riskSummary) els.riskSummary.textContent = risk.summary || "暂无风险说明。";
    if (els.dashboardRiskLevel) els.dashboardRiskLevel.textContent = level;
    if (els.riskStripPassRate) els.riskStripPassRate.textContent = "-";
    if (els.riskStripExecutionCount) els.riskStripExecutionCount.textContent = "-";
    if (els.riskStripPendingIssues) els.riskStripPendingIssues.textContent = "-";
    if (els.dashboardRiskAdvice) els.dashboardRiskAdvice.textContent = level === "待评估" ? "等待数据" : riskAdvice(level);
  }

  function renderSummary(els, summary) {
    const passRateText = summary.pass_rate_24h === null || summary.pass_rate_24h === undefined ? "暂无数据" : `${summary.pass_rate_24h}%`;
    const executionCountText = summary.execution_count_24h === null || summary.execution_count_24h === undefined ? "暂无数据" : String(summary.execution_count_24h);
    const pendingIssuesText = summary.pending_issues === null || summary.pending_issues === undefined ? "暂无数据" : String(summary.pending_issues);

    if (els.summaryPassRate) els.summaryPassRate.textContent = passRateText;
    if (els.summaryExecutionCount) els.summaryExecutionCount.textContent = executionCountText;
    if (els.summaryInterceptedLast10) {
      els.summaryInterceptedLast10.textContent = summary.intercepted_last10 === null || summary.intercepted_last10 === undefined ? "暂无数据" : String(summary.intercepted_last10);
    }
    if (els.summaryPendingIssues) els.summaryPendingIssues.textContent = pendingIssuesText;
    if (els.riskStripPassRate) els.riskStripPassRate.textContent = passRateText;
    if (els.riskStripExecutionCount) els.riskStripExecutionCount.textContent = executionCountText;
    if (els.riskStripPendingIssues) els.riskStripPendingIssues.textContent = pendingIssuesText;
    if (els.dashboardAsOf) els.dashboardAsOf.textContent = summary.as_of ? formatTime(summary.as_of) : "暂无更新";
  }

  function renderTrend(els, points) {
    if (!els.trendMeta || !els.trendSvg || !els.trendXAxis) return;
    if (!points || !points.length) {
      els.trendMeta.textContent = "暂无趋势数据。";
      els.trendSvg.innerHTML = "";
      els.trendXAxis.innerHTML = "";
      return;
    }

    const width = 960;
    const height = 280;
    const padLeft = 42;
    const padRight = 16;
    const padTop = 18;
    const padBottom = 34;
    const plotH = height - padTop - padBottom;
    const plotW = width - padLeft - padRight;
    const passRates = points.map((item) => Number(item.pass_rate) || 0);
    const execCounts = points.map((item) => Number(item.execution_count) || 0);
    const execMax = Math.max(...execCounts, 1);
    const execScaled = execCounts.map((item) => (item / execMax) * 100);

    const passPoints = toPolylinePoints(passRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const execPoints = toPolylinePoints(execScaled, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const pointCoords = buildPointCoordinates(passRates, 0, 100, width, height, padLeft, padRight, padTop, padBottom);
    const gridYValues = [0, 25, 50, 75, 100];
    const gridLines = gridYValues
      .map((value) => {
        const y = padTop + ((100 - value) / 100) * plotH;
        return `<line x1="${padLeft}" y1="${y}" x2="${padLeft + plotW}" y2="${y}" stroke="#d7e2ef" stroke-width="1" stroke-dasharray="4 4"></line>`;
      })
      .join("");

    els.trendSvg.innerHTML = `
      ${gridLines}
      <polyline fill="none" stroke="#2f79db" stroke-width="3" points="${passPoints}"></polyline>
      <polyline fill="none" stroke="#de8a23" stroke-width="2.5" points="${execPoints}"></polyline>
      ${pointCoords
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
        .join("")}
      <text x="${padLeft}" y="${padTop - 4}" fill="#7489a7" font-size="11">通过率 %</text>
      <text x="${width - 74}" y="${padTop - 4}" fill="#7489a7" font-size="11">执行次数(归一化)</text>
    `;

    const labelIndexes = [0, 4, 8, 12, 16, 20, points.length - 1].filter((idx, pos, arr) => idx < points.length && arr.indexOf(idx) === pos);
    els.trendXAxis.innerHTML = labelIndexes.map((idx) => `<span>${escapeHtml(points[idx]?.hour || "")}</span>`).join("");
    const latest = points[points.length - 1] || {};
    els.trendMeta.textContent = `当前时段通过率 ${latest.pass_rate || 0}% ，执行次数 ${latest.execution_count || 0} 次。`;
  }

  function renderWeeklyFocus(els, governancePayload) {
    const managerSummary = governancePayload && governancePayload.manager_summary && typeof governancePayload.manager_summary === "object"
      ? governancePayload.manager_summary
      : {};
    const topRisks = governancePayload && Array.isArray(governancePayload.top_governance_risks)
      ? governancePayload.top_governance_risks
      : [];
    const highlights = Array.isArray(managerSummary.highlights) ? [...managerSummary.highlights] : [];

    if (topRisks.length) {
      highlights.push(`高风险任务 ${topRisks[0].task_id || "-"}：${topRisks[0].governance_risk_reason || "请进入执行任务页处理。"}`);
    }

    if (els.managerHeadline) {
      const headline = managerSummary.headline || "当前重点正在汇总。";
      const topTheme = managerSummary.top_theme ? ` 本周主题：${managerSummary.top_theme}。` : "";
      els.managerHeadline.textContent = `${headline}${topTheme}`;
    }
    if (els.managerReleaseReadiness) els.managerReleaseReadiness.textContent = managerSummary.release_readiness || "-";
    if (els.managerTraceabilityStatus) els.managerTraceabilityStatus.textContent = managerSummary.traceability_status || "-";
    if (els.managerMultisourceStatus) els.managerMultisourceStatus.textContent = managerSummary.multisource_status || "-";
    if (els.managerWeeklyFocus) els.managerWeeklyFocus.textContent = managerSummary.weekly_focus || managerSummary.top_theme || "-";

    renderIssueList(
      els.managerHighlightsList,
      highlights.map((item) => ({ title: "本周重点", summary: item })),
      "暂无本周重点。"
    );
  }

  function renderActionItems(els, governancePayload) {
    const risk = governancePayload && governancePayload.risk && typeof governancePayload.risk === "object"
      ? governancePayload.risk
      : {};
    const degradedSources = governancePayload && Array.isArray(governancePayload.degraded_sources)
      ? governancePayload.degraded_sources
      : [];
    const actions = governancePayload && Array.isArray(governancePayload.action_items)
      ? governancePayload.action_items
      : [];

    if (els.governanceMeta) {
      let text = risk.summary || "暂无治理摘要。";
      if (degradedSources.length) text += ` 当前有 ${degradedSources.join("、")} 数据源处于降级状态。`;
      els.governanceMeta.textContent = text;
    }

    renderIssueList(
      els.governanceActionsList,
      actions.map((item) => ({
        title: item.title || "-",
        status: item.status || "",
        summary: item.summary || "-",
        href: item.href || "/execution/runs",
      })),
      "暂无治理行动建议。"
    );
  }

  function renderPendingIssues(els, rows) {
    renderIssueList(
      els.pendingIssuesList,
      (rows || []).map((item) => ({
        title: `${item.issue_key || "-"} · ${item.title || "-"}`,
        status: item.status || "",
        meta: `${item.agent || "-"} 推荐，置信度 ${((Number(item.confidence || 0) || 0) * 100).toFixed(0)}%`,
        summary: item.recommendation || "-",
        href: item.detail_url || "#",
      })),
      "暂无待确认问题。"
    );
  }

  function renderLoadError(els) {
    if (els.riskSummary) els.riskSummary.textContent = "仪表盘加载失败，请检查服务状态与日志。";
    if (els.trendMeta) els.trendMeta.textContent = "平台概览加载失败。";
    if (els.managerHeadline) els.managerHeadline.textContent = "本周重点加载失败。";
    if (els.governanceMeta) els.governanceMeta.textContent = "待处理事项加载失败。";
    renderIssueList(els.managerHighlightsList, [], "本周重点加载失败。");
    renderIssueList(els.governanceActionsList, [], "治理行动建议加载失败。");
    renderIssueList(els.pendingIssuesList, [], "待确认问题加载失败。");
  }

  window.dashboardSections = {
    renderRisk,
    renderSummary,
    renderTrend,
    renderWeeklyFocus,
    renderActionItems,
    renderPendingIssues,
    renderLoadError,
  };
})();
