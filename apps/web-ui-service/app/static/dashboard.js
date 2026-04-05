(function () {
  const shell = document.getElementById("dashboard-shell");
  if (!shell) return;

  const sections = window.dashboardSections;
  if (!sections) return;

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
    managerHeadline: document.getElementById("manager-headline"),
    managerReleaseReadiness: document.getElementById("manager-release-readiness"),
    managerTraceabilityStatus: document.getElementById("manager-traceability-status"),
    managerMultisourceStatus: document.getElementById("manager-multisource-status"),
    managerWeeklyFocus: document.getElementById("manager-weekly-focus"),
    managerHighlightsList: document.getElementById("manager-highlights-list"),
    governanceMeta: document.getElementById("governance-meta"),
    governanceActionsList: document.getElementById("governance-actions-list"),
    pendingIssuesList: document.getElementById("pending-issues-list"),
  };

  async function loadDashboard() {
    const [overviewResult, governanceResult] = await Promise.allSettled([
      fetch("/api/dashboard/overview", { cache: "no-store" }),
      fetch("/api/dashboard/governance", { cache: "no-store" }),
    ]);

    if (overviewResult.status !== "fulfilled" || !overviewResult.value.ok) {
      throw new Error("load dashboard overview failed");
    }

    const overviewPayload = await overviewResult.value.json();
    sections.renderRisk(els, overviewPayload.risk || {});
    sections.renderSummary(els, { ...(overviewPayload.summary || {}), as_of: overviewPayload.as_of || "" });
    sections.renderTrend(els, overviewPayload.trend_24h || []);
    sections.renderPendingIssues(els, overviewPayload.pending_issues || []);

    if (governanceResult.status === "fulfilled" && governanceResult.value.ok) {
      const governancePayload = await governanceResult.value.json();
      sections.renderWeeklyFocus(els, governancePayload || {});
      sections.renderActionItems(els, governancePayload || {});
      return;
    }

    sections.renderWeeklyFocus(els, {});
    sections.renderActionItems(els, {});
    if (els.governanceMeta) {
      els.governanceMeta.textContent = "待处理事项加载失败。";
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
    sections.renderLoadError(els);
  });

  window.setInterval(() => {
    refreshDashboard().catch((error) => {
      console.error(error);
      sections.renderLoadError(els);
    });
  }, 60000);
})();
