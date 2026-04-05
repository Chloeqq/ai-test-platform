(function () {
  function toNumber(value, fallback) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  }

  function asText(value, fallback) {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function levelKey(level) {
    const normalized = asText(level, "低").toLowerCase();
    if (normalized === "high" || normalized === "高") return "high";
    if (normalized === "medium" || normalized === "中") return "medium";
    return "low";
  }

  function levelLabel(level) {
    const key = levelKey(level);
    if (key === "high") return "高";
    if (key === "medium") return "中";
    return "低";
  }

  function formatPercent(value) {
    const num = toNumber(value, 0);
    return num.toFixed(1).replace(/\.0$/, "") + "%";
  }

  function formatAsOf(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return asText(value, "-");
  }

  function clearRiskClass(card) {
    if (!card) return;
    card.classList.remove("risk-low", "risk-medium", "risk-high");
  }

  function renderRisk(els, risk) {
    const safeRisk = risk && typeof risk === "object" ? risk : {};
    const key = levelKey(safeRisk.level);
    const label = levelLabel(safeRisk.level);
    const score = Math.max(0, Math.round(toNumber(safeRisk.score, 0)));

    if (els.riskCard) {
      clearRiskClass(els.riskCard);
      els.riskCard.classList.add("risk-" + key);
      if (safeRisk.detail_url) {
        els.riskCard.href = String(safeRisk.detail_url);
      }
    }
    if (els.riskLevelBadge) els.riskLevelBadge.textContent = label;
    if (els.dashboardRiskLevel) els.dashboardRiskLevel.textContent = label;
    if (els.riskScore) els.riskScore.textContent = String(score);
    if (els.riskSummary) els.riskSummary.textContent = asText(safeRisk.summary, "暂无风险摘要。");
  }

  function renderSummary(els, summary) {
    const safeSummary = summary && typeof summary === "object" ? summary : {};
    if (els.summaryPassRate) els.summaryPassRate.textContent = formatPercent(safeSummary.pass_rate_24h);
    if (els.summaryExecutionCount) els.summaryExecutionCount.textContent = String(toNumber(safeSummary.execution_count_24h, 0));
    if (els.summaryInterceptedLast10) els.summaryInterceptedLast10.textContent = String(toNumber(safeSummary.intercepted_last10, 0));
    if (els.summaryPendingIssues) els.summaryPendingIssues.textContent = String(toNumber(safeSummary.pending_issues, 0));

    if (els.riskStripPassRate) els.riskStripPassRate.textContent = formatPercent(safeSummary.pass_rate_24h);
    if (els.riskStripExecutionCount) els.riskStripExecutionCount.textContent = String(toNumber(safeSummary.execution_count_24h, 0));
    if (els.riskStripPendingIssues) els.riskStripPendingIssues.textContent = String(toNumber(safeSummary.pending_issues, 0));

    if (els.dashboardAsOf) els.dashboardAsOf.textContent = formatAsOf(safeSummary.as_of);
  }

  function renderTrend(els, points) {
    const rows = Array.isArray(points) ? points : [];
    if (!els.trendSvg || !rows.length) {
      if (els.trendMeta) els.trendMeta.textContent = "暂无趋势数据。";
      if (els.trendSvg) els.trendSvg.innerHTML = "";
      if (els.trendXAxis) els.trendXAxis.innerHTML = "";
      return;
    }

    const maxX = Math.max(rows.length - 1, 1);
    const maxY = 100;
    const width = 960;
    const height = 280;
    const paddingX = 24;
    const paddingY = 24;
    const innerWidth = width - paddingX * 2;
    const innerHeight = height - paddingY * 2;

    const coords = rows.map((item, index) => {
      const x = paddingX + (index / maxX) * innerWidth;
      const yRate = Math.min(100, Math.max(0, toNumber(item.pass_rate, 0)));
      const y = paddingY + (1 - yRate / maxY) * innerHeight;
      return { x: x, y: y, label: asText(item.hour, "--"), passRate: yRate };
    });

    const path = coords
      .map((item, idx) => (idx === 0 ? "M " : "L ") + item.x.toFixed(2) + " " + item.y.toFixed(2))
      .join(" ");

    const circles = coords
      .filter((_, idx) => idx % 4 === 0 || idx === coords.length - 1)
      .map((item) => {
        return '<circle cx="' + item.x.toFixed(2) + '" cy="' + item.y.toFixed(2) + '" r="3" fill="#2f79db"></circle>';
      })
      .join("");

    const guides = [0, 25, 50, 75, 100]
      .map((value) => {
        const y = paddingY + (1 - value / 100) * innerHeight;
        return '<line x1="' + paddingX + '" y1="' + y.toFixed(2) + '" x2="' + (width - paddingX) + '" y2="' + y.toFixed(2) + '" stroke="#dde7f3" stroke-width="1"></line>';
      })
      .join("");

    els.trendSvg.innerHTML =
      guides +
      '<path d="' +
      path +
      '" fill="none" stroke="#2f79db" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>' +
      circles;

    if (els.trendXAxis) {
      const labelIndexes = [0, Math.floor(maxX * 0.25), Math.floor(maxX * 0.5), Math.floor(maxX * 0.75), maxX];
      const uniqueIndexes = Array.from(new Set(labelIndexes));
      els.trendXAxis.innerHTML = uniqueIndexes
        .map((idx) => '<span>' + asText(rows[idx]?.hour, "--") + "</span>")
        .join("");
    }

    const latest = rows[rows.length - 1] || {};
    if (els.trendMeta) {
      els.trendMeta.textContent =
        "最近时段通过率 " +
        formatPercent(latest.pass_rate) +
        "，执行 " +
        String(toNumber(latest.execution_count, 0)) +
        " 次。";
    }
  }

  function renderPendingIssues(els, pendingIssues) {
    const rows = Array.isArray(pendingIssues) ? pendingIssues : [];
    if (!els.pendingIssuesList) return;
    if (!rows.length) {
      els.pendingIssuesList.innerHTML = "<li>当前没有待确认问题。</li>";
      return;
    }

    els.pendingIssuesList.innerHTML = rows
      .slice(0, 6)
      .map((item) => {
        const title = asText(item.title, "待确认问题");
        const agent = asText(item.agent, "系统");
        const confidence = toNumber(item.confidence, 0);
        const note = asText(item.recommendation, "");
        const detailUrl = asText(item.detail_url, "#");
        return (
          '<li><div class="pending-item-head"><a class="pending-item-title" href="' +
          detailUrl +
          '">' +
          title +
          '</a><span class="pill">' +
          Math.round(confidence * 100) +
          '%</span></div><div class="pending-item-meta">来源：' +
          agent +
          '</div><p class="pending-item-note">' +
          note +
          "</p></li>"
        );
      })
      .join("");
  }

  function renderWeeklyFocus(els, governance) {
    const manager = governance?.manager_summary && typeof governance.manager_summary === "object" ? governance.manager_summary : {};
    if (els.managerHeadline) els.managerHeadline.textContent = asText(manager.headline, "正在汇总治理摘要...");
    if (els.managerReleaseReadiness) els.managerReleaseReadiness.textContent = asText(manager.release_readiness, "-");
    if (els.managerTraceabilityStatus) els.managerTraceabilityStatus.textContent = asText(manager.traceability_status, "-");
    if (els.managerMultisourceStatus) els.managerMultisourceStatus.textContent = asText(manager.multisource_status, "-");
    if (els.managerWeeklyFocus) els.managerWeeklyFocus.textContent = asText(manager.weekly_focus || manager.top_theme, "-");

    if (!els.managerHighlightsList) return;
    const highlights = Array.isArray(manager.highlights) ? manager.highlights : [];
    if (!highlights.length) {
      els.managerHighlightsList.innerHTML = "<li>暂无本周重点摘要。</li>";
      return;
    }
    els.managerHighlightsList.innerHTML = highlights
      .slice(0, 6)
      .map((item) => "<li>" + asText(item, "") + "</li>")
      .join("");
  }

  function renderActionItems(els, governance) {
    const actionItems = Array.isArray(governance?.action_items) ? governance.action_items : [];
    if (!els.governanceActionsList) return;
    if (!actionItems.length) {
      els.governanceActionsList.innerHTML = "<li>当前没有新增治理行动建议。</li>";
    } else {
      els.governanceActionsList.innerHTML = actionItems
        .slice(0, 8)
        .map((item) => {
          const title = asText(item.title, "治理建议");
          const status = asText(item.status, "持续跟进");
          const summary = asText(item.summary, "");
          const href = asText(item.href, "#");
          const level = levelKey(item.level);
          return (
            '<li><div class="pending-item-head"><a class="pending-item-title" href="' +
            href +
            '">' +
            title +
            '</a><span class="pill pill-' +
            level +
            '">' +
            status +
            '</span></div><p class="pending-item-note">' +
            summary +
            "</p></li>"
          );
        })
        .join("");
    }

    if (els.governanceMeta) {
      const degraded = Array.isArray(governance?.degraded_sources) && governance.degraded_sources.length > 0;
      if (degraded) {
        els.governanceMeta.textContent = "部分治理数据源降级，已展示可用结果。";
      } else {
        els.governanceMeta.textContent = "已同步治理建议，可下钻到对应页面继续处理。";
      }
    }
  }

  function renderLoadError(els) {
    if (els.trendMeta) els.trendMeta.textContent = "仪表盘加载失败，请稍后重试。";
    if (els.governanceMeta) els.governanceMeta.textContent = "待处理事项加载失败，请稍后重试。";
    if (els.pendingIssuesList) els.pendingIssuesList.innerHTML = "<li>加载失败，请稍后刷新重试。</li>";
    if (els.governanceActionsList) els.governanceActionsList.innerHTML = "<li>加载失败，请稍后刷新重试。</li>";
    if (els.managerHighlightsList) els.managerHighlightsList.innerHTML = "<li>加载失败，请稍后刷新重试。</li>";
  }

  window.dashboardSections = {
    renderRisk: renderRisk,
    renderSummary: renderSummary,
    renderTrend: renderTrend,
    renderPendingIssues: renderPendingIssues,
    renderWeeklyFocus: renderWeeklyFocus,
    renderActionItems: renderActionItems,
    renderLoadError: renderLoadError,
  };
})();
