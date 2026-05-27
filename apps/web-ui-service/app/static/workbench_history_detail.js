(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatTime(value) {
    if (typeof window.platformFormatDateTime === "function") return window.platformFormatDateTime(value);
    return String(value || "").trim() || "-";
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") return window.platformDisplayCaseId(value);
    return String(value || "").trim() || "-";
  }

  function displayRunId(value) {
    if (typeof window.platformDisplayRunId === "function") return window.platformDisplayRunId(value);
    return String(value || "").trim() || "-";
  }

  function renderBadge(value, fallback) {
    if (typeof window.platformRenderBadge === "function") return window.platformRenderBadge(value, fallback);
    const text = String(value || fallback || "unknown").trim() || fallback || "unknown";
    return `<span class="badge badge-default">${escapeHtml(text)}</span>`;
  }

  function rowKey(item) {
    return [
      String(item?.timestamp || "").trim(),
      String(item?.action || "").trim(),
      String(item?.run_id || "").trim(),
      String(item?.case_id || "").trim(),
      String(item?.page || "").trim(),
    ].join("::");
  }

  function buildWorkbenchAuditLink(item, label) {
    const runId = String(item?.run_id || "").trim();
    if (!runId) return escapeHtml(label || "-");
    const params = new URLSearchParams();
    params.set("run_id", runId);
    if (item?.project) params.set("project", String(item.project).trim());
    if (item?.review_type) params.set("review_type", String(item.review_type).trim());
    if (item?.page) params.set("page", String(item.page).trim());
    return `<a class="action-link" href="/execution/workbench?${params.toString()}">${escapeHtml(label || displayRunId(runId))}</a>`;
  }

  function buildGenerateAuditLink(item, label) {
    const runId = String(item?.run_id || "").trim();
    if (!runId) return escapeHtml(label || "-");
    const params = new URLSearchParams();
    params.set("run_id", runId);
    if (item?.project) params.set("project", String(item.project).trim());
    if (item?.review_type) params.set("review_type", String(item.review_type).trim());
    if (item?.page) params.set("page", String(item.page).trim());
    return `<a class="action-link" href="/ai-generation?${params.toString()}">${escapeHtml(label || displayRunId(runId))}</a>`;
  }

  function buildActionLink(item) {
    const action = String(item?.action || "").trim();
    if (!action) return "-";
    return action.startsWith("review_") ? buildGenerateAuditLink(item, action) : buildWorkbenchAuditLink(item, action);
  }

  function renderSummaryPanel(summary) {
    const data = summary && typeof summary === "object" ? summary : {};
    const actionCounts = data.action_counts && typeof data.action_counts === "object" ? data.action_counts : {};
    const riskGateCounts = data.risk_gate_counts && typeof data.risk_gate_counts === "object" ? data.risk_gate_counts : {};
    const selfHealingCounts = data.self_healing_status_counts && typeof data.self_healing_status_counts === "object" ? data.self_healing_status_counts : {};
    const actionText = Object.keys(actionCounts).length
      ? Object.entries(actionCounts).map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value)}`).join(" / ")
      : "暂无动作分布";
    const gateText = Object.keys(riskGateCounts).length
      ? Object.entries(riskGateCounts).map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value)}`).join(" / ")
      : "暂无门禁分布";
    const healingText = Object.keys(selfHealingCounts).length
      ? Object.entries(selfHealingCounts).map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value)}`).join(" / ")
      : "暂无自愈分布";
    return `
      <div class="workbench-history-summary-grid">
        <article class="kv-item">
          <span>当前结果</span>
          <strong>${escapeHtml(data.total_items || 0)}</strong>
          <p>命中当前筛选条件的历史记录数</p>
        </article>
        <article class="kv-item">
          <span>动作分布</span>
          <p>${actionText}</p>
        </article>
        <article class="kv-item">
          <span>门禁分布</span>
          <p>${gateText}</p>
        </article>
        <article class="kv-item">
          <span>自愈分布</span>
          <p>${healingText}</p>
        </article>
        <article class="kv-item">
          <span>治理关注</span>
          <p>需人工复核 ${escapeHtml(data.risk_requires_review_count || 0)} 条，边界拒绝 ${escapeHtml(data.boundary_rejected_count || 0)} 条</p>
        </article>
      </div>
    `;
  }

  function renderDetailPanel(item) {
    if (!item || typeof item !== "object") {
      return '<div class="empty-state">先选择一条操作历史。</div>';
    }
    const reviewItems = Array.isArray(item.review_items) ? item.review_items.filter(Boolean) : [];
    const matchedRules = Array.isArray(item.matched_rules) ? item.matched_rules.filter(Boolean) : [];
    const evidence = Array.isArray(item.evidence) ? item.evidence.filter(Boolean) : [];
    const riskSummary = item.risk_summary && typeof item.risk_summary === "object" ? item.risk_summary : {};
    const selfHealingSummary = item.self_healing_summary && typeof item.self_healing_summary === "object" ? item.self_healing_summary : {};
    const semanticSummary = item.page_semantic_summary && typeof item.page_semantic_summary === "object" ? item.page_semantic_summary : {};
    const failureSummary = item.failure_analysis && typeof item.failure_analysis === "object" ? item.failure_analysis : {};

    return `
      <section class="detail-highlight">
        <h3>${escapeHtml(item.action || "-")}</h3>
        <p>${escapeHtml(item.detail_summary || item.note || "暂无详情摘要")}</p>
      </section>
      <div class="kv-list">
        <article class="kv-item">
          <span>发生时间</span>
          <p>${escapeHtml(formatTime(item.timestamp))}</p>
        </article>
        <article class="kv-item">
          <span>用例 ID</span>
          <p>${escapeHtml(displayCaseId(item.case_id || "-"))}</p>
        </article>
        <article class="kv-item">
          <span>Run ID</span>
          <p>${escapeHtml(displayRunId(item.run_id || "-"))}</p>
        </article>
        <article class="kv-item">
          <span>页面 / 确认人</span>
          <p>${escapeHtml(item.page || "-")} ｜ ${escapeHtml(item.actor_display || item.confirmed_by || "-")}</p>
        </article>
      </div>
      <ul class="workbench-history-link-list">
        <li class="workbench-history-note-item">${buildActionLink(item)}</li>
        <li class="workbench-history-note-item">${buildWorkbenchAuditLink(item, item.run_id ? `查看调试上下文 ${displayRunId(item.run_id)}` : "暂无 Run 上下文")}</li>
      </ul>
      <div class="kv-list">
        <article class="kv-item">
          <span>风险摘要</span>
          <p>${escapeHtml(riskSummary.risk_level || "-")} ｜ ${escapeHtml(riskSummary.gate_decision || "-")} ｜ score=${escapeHtml(riskSummary.risk_score ?? "-")}</p>
        </article>
        <article class="kv-item">
          <span>自愈摘要</span>
          <p>${escapeHtml(selfHealingSummary.status || "-")} ｜ ${escapeHtml((selfHealingSummary.boundary || {}).advice_type || "-")} ｜ ${escapeHtml(selfHealingSummary.reason || "-")}</p>
        </article>
        <article class="kv-item">
          <span>页面语义</span>
          <p>${escapeHtml(semanticSummary.page_type || "-")} ｜ ${escapeHtml(semanticSummary.business_domain || "-")} ｜ ${escapeHtml(semanticSummary.primary_goal || "-")}</p>
        </article>
        <article class="kv-item">
          <span>失败归因</span>
          <p>${escapeHtml(item.failure_source || failureSummary.failure_source || "-")} ｜ ${escapeHtml(item.failure_source_reason || failureSummary.failure_source_reason || "-")}</p>
        </article>
      </div>
      <ul class="workbench-history-note-list">
        <li class="workbench-history-note-item">
          <strong>状态标签</strong>
          <p>${renderBadge(item.status || "unknown", "unknown")} ${renderBadge(riskSummary.gate_decision || "unknown", "unknown")} ${renderBadge(selfHealingSummary.status || "unknown", "unknown")}</p>
        </li>
        <li class="workbench-history-note-item">
          <strong>审核项</strong>
          <p>${escapeHtml(reviewItems.join(" / ") || "暂无审核项")}</p>
        </li>
        <li class="workbench-history-note-item">
          <strong>命中规则</strong>
          <p>${escapeHtml(matchedRules.map((rule) => `${rule.level || "rule"}:${rule.message || "-"}`).join(" / ") || "暂无规则")}</p>
        </li>
        <li class="workbench-history-note-item">
          <strong>证据摘要</strong>
          <p>${escapeHtml(evidence.join(" / ") || "暂无证据摘要")}</p>
        </li>
      </ul>
    `;
  }

  window.workbenchHistoryDetail = {
    buildActionLink,
    buildWorkbenchAuditLink,
    displayCaseId,
    displayRunId,
    escapeHtml,
    formatTime,
    renderBadge,
    renderDetailPanel,
    renderSummaryPanel,
    rowKey,
  };
})();
