(function () {
  const shell = document.getElementById("tp-asset-detail-shell");
  if (!shell) return;
  const assetId = shell.dataset.assetId || "";
  if (!assetId) return;

  const els = {
    pointCount: document.getElementById("tpd-point-count"),
    coverageStatus: document.getElementById("tpd-coverage-status"),
    gateDecision: document.getElementById("tpd-gate-decision"),
    latestRunStatus: document.getElementById("tpd-latest-run-status"),
    baseInfo: document.getElementById("tpd-base-info"),
    governance: document.getElementById("tpd-governance-summary"),
    runSummary: document.getElementById("tpd-run-summary"),
    pointsTbody: document.getElementById("tpd-points-tbody"),
    semanticTechnique: document.getElementById("tpd-semantic-technique"),
    openMatrix: document.getElementById("tpd-open-matrix"),
    openExecutions: document.getElementById("tpd-open-executions"),
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function badge(value) {
    const text = String(value || "unknown").trim() || "unknown";
    const cls = text.toLowerCase().replaceAll(/[^a-z0-9_]+/g, "_");
    return `<span class="badge badge-${cls}">${escapeHtml(text)}</span>`;
  }

  function displayRunId(value) {
    if (typeof window.platformDisplayRunId === "function") return window.platformDisplayRunId(value);
    return String(value || "").trim() || "-";
  }

  async function load() {
    const response = await fetch(`/api/workbench/test-point-assets/${encodeURIComponent(assetId)}`, { cache: "no-store" });
    const payload = response.ok ? await response.json() : {};
    const item = payload.item || {};
    const traceability = item.traceability_summary || {};
    const coverage = traceability.coverage || {};
    const review = traceability.review || {};
    const gate = traceability.gate || {};
    const risk = traceability.risk || {};
    const semantic = traceability.semantic || {};
    const technique = traceability.technique || {};
    const latestRun = item.latest_run || {};
    const plan = item.plan || {};
    const points = Array.isArray(plan.points) ? plan.points : [];

    els.pointCount.textContent = String(item.point_count || points.length || 0);
    els.coverageStatus.innerHTML = badge(coverage.latest_run_status || coverage.asset_status || "unknown");
    els.gateDecision.innerHTML = badge(gate.effective_decision || "unknown");
    els.latestRunStatus.innerHTML = badge(latestRun.status || "unknown");

    els.baseInfo.innerHTML = `
      <article class="kv-item"><span>标题</span><strong>${escapeHtml(item.title || assetId)}</strong></article>
      <article class="kv-item"><span>页面 / 来源</span><strong>${escapeHtml(item.page || "-")} ｜ ${escapeHtml(item.source_type || "-")}</strong></article>
      <article class="kv-item"><span>优先级 / confidence</span><strong>${escapeHtml(item.priority || "-")} ｜ ${escapeHtml(item.confidence ?? "-")}</strong></article>
      <article class="kv-item"><span>Requirement</span><p>${escapeHtml((item.requirement || []).join("；") || "暂无 requirement 文本")}</p></article>
      <article class="kv-item"><span>Plan Path</span><p class="mono">${escapeHtml(item.plan_path || "-")}</p></article>
    `;

    els.governance.innerHTML = `
      <article class="kv-item"><span>选择状态</span><strong>${badge((item.selection_summary || {}).selection_state || "unknown")}</strong></article>
      <article class="kv-item"><span>评审状态</span><strong>${badge(review.test_point_status || "unknown")}</strong><p class="meta-text">pending=${escapeHtml(review.pending_sections ?? 0)} ｜ actor=${escapeHtml(review.latest_actor_display || "-")}</p></article>
      <article class="kv-item"><span>门禁摘要</span><strong>${badge(gate.effective_decision || gate.decision || "unknown")}</strong><p class="meta-text">${escapeHtml(gate.gate_reason_summary || "暂无门禁说明")}</p></article>
      <article class="kv-item"><span>追溯覆盖</span><strong>${badge(coverage.latest_run_status || coverage.asset_status || "unknown")}</strong><p class="meta-text">missing=${escapeHtml(coverage.missing_count ?? 0)}</p></article>
    `;

    els.runSummary.innerHTML = `
      <article class="kv-item"><span>最近运行</span><strong>${badge(latestRun.status || "unknown")}</strong><p class="meta-text mono">${escapeHtml(displayRunId(latestRun.run_id || "-"))}</p></article>
      <article class="kv-item"><span>风险摘要</span><strong>${escapeHtml(risk.risk_level || "-")}</strong><p class="meta-text">top factor=${escapeHtml((risk.top_factor || {}).factor || "-")} ｜ count=${escapeHtml(risk.factor_count ?? 0)}</p></article>
      <article class="kv-item"><span>语义摘要</span><strong>${escapeHtml(semantic.page_type || "-")}</strong><p class="meta-text">${escapeHtml(semantic.primary_goal || semantic.business_domain || "-")}</p></article>
    `;

    if (!points.length) {
      els.pointsTbody.innerHTML = '<tr><td colspan="5" class="empty-state">当前资产没有可展示的测试点。</td></tr>';
    } else {
      els.pointsTbody.innerHTML = points.map((point) => {
        const trace = point.metadata && point.metadata.traceability ? point.metadata.traceability : {};
        const traceSummary = [ ...(trace.source_ids || []), ...(trace.intent_ids || []) ].join(" / ");
        return `
          <tr>
            <td class="mono">${escapeHtml(point.key || "-")}</td>
            <td>${badge(point.point_type || "unknown")}</td>
            <td>
              <div class="table-title">${escapeHtml(point.description || point.summary || "-")}</div>
              <div class="table-subtitle">${escapeHtml(point.action || "-")} → ${escapeHtml(point.target || "-")}</div>
            </td>
            <td>${badge(point.technique_type || "normal")}</td>
            <td>${escapeHtml(traceSummary || "暂无追溯")}</td>
          </tr>
        `;
      }).join("");
    }

    const techniqueDistribution = Object.entries(technique.technique_distribution || {})
      .map(([key, value]) => `${key}: ${value}`)
      .join(" ｜ ");
    els.semanticTechnique.innerHTML = `
      <article class="kv-item"><span>语义摘要</span><strong>${escapeHtml(semantic.page_type || "-")}</strong><p class="meta-text">${escapeHtml((semantic.primary_actions || []).join(" / ") || semantic.business_domain || "-")}</p></article>
      <article class="kv-item"><span>技术分布</span><strong>${escapeHtml(techniqueDistribution || "暂无技术分布")}</strong><p class="meta-text">mainline=${escapeHtml(technique.mainline_point_count ?? 0)} ｜ design_only=${escapeHtml(technique.design_only_point_count ?? 0)}</p></article>
      <article class="kv-item"><span>Warnings</span><p>${escapeHtml((item.warnings || []).join("；") || "当前无额外 warning")}</p></article>
    `;

    els.openMatrix.href = `/assets/test-points/${encodeURIComponent(assetId)}/matrix`;
    els.openExecutions.href = `/executions?page=${encodeURIComponent(item.page || "")}`;
  }

  load().catch((error) => {
    els.baseInfo.innerHTML = `<div class="error-state">${escapeHtml(error.message || "加载资产详情失败")}</div>`;
    els.pointsTbody.innerHTML = `<tr><td colspan="5" class="error-state">${escapeHtml(error.message || "加载资产详情失败")}</td></tr>`;
  });
})();
