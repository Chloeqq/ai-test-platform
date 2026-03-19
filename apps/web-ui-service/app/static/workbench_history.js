(function () {
  const shell = document.getElementById("workbench-history-shell");
  if (!shell) return;

  const els = {
    refreshBtn: document.getElementById("wb-history-refresh"),
    body: document.getElementById("wb-history-body"),
    summary: document.getElementById("wb-history-summary"),
    authNotice: document.getElementById("wb-history-auth-notice"),
    actionFilter: document.getElementById("wb-history-action"),
    statusFilter: document.getElementById("wb-history-status"),
    riskGateFilter: document.getElementById("wb-history-risk-gate"),
    selfHealingStatusFilter: document.getElementById("wb-history-self-healing-status"),
    actorFilter: document.getElementById("wb-history-actor"),
  };

  const authFetch = typeof window.platformAuthFetch === "function" ? window.platformAuthFetch : window.fetch.bind(window);

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

  function normalizeStringList(values, limit = 3) {
    const items = Array.isArray(values) ? values : [];
    return items
      .map((item) => String(item || "").trim())
      .filter(Boolean)
      .slice(0, limit);
  }

  function normalizeRuleList(values, limit = 3) {
    const items = Array.isArray(values) ? values : [];
    return items
      .filter((item) => item && typeof item === "object" && String(item.message || "").trim())
      .slice(0, limit)
      .map((item) => ({
        level: String(item.level || "").trim(),
        message: String(item.message || "").trim(),
      }));
  }

  function renderSummary(summary) {
    if (!els.summary) return;
    const data = summary && typeof summary === "object" ? summary : {};
    const totalItems = Number(data.total_items || 0);
    const riskGateCounts = data.risk_gate_counts && typeof data.risk_gate_counts === "object" ? data.risk_gate_counts : {};
    const selfHealingStatusCounts =
      data.self_healing_status_counts && typeof data.self_healing_status_counts === "object"
        ? data.self_healing_status_counts
        : {};
    const topRiskGate = data.top_risk_gate && typeof data.top_risk_gate === "object" ? data.top_risk_gate : {};
    const topSelfHealingStatus =
      data.top_self_healing_status && typeof data.top_self_healing_status === "object"
        ? data.top_self_healing_status
        : {};
    const riskGateText = Object.keys(riskGateCounts).length
      ? Object.entries(riskGateCounts)
          .map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value)}`)
          .join(" / ")
      : "无";
    const selfHealingText = Object.keys(selfHealingStatusCounts).length
      ? Object.entries(selfHealingStatusCounts)
          .map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value)}`)
          .join(" / ")
      : "无";
    els.summary.innerHTML = `
      <div class="wb-history-summary-grid">
        <div class="wb-history-summary-card">
          <span class="wb-history-summary-label">当前结果</span>
          <strong>${escapeHtml(totalItems)}</strong>
          <span>条记录</span>
        </div>
        <div class="wb-history-summary-card">
          <span class="wb-history-summary-label">风险门禁分布</span>
          <strong>${riskGateText}</strong>
          <span>最高频：${escapeHtml(topRiskGate.value || "-")}${topRiskGate.count !== undefined ? ` (${escapeHtml(topRiskGate.count)})` : ""}</span>
        </div>
        <div class="wb-history-summary-card">
          <span class="wb-history-summary-label">自愈状态分布</span>
          <strong>${selfHealingText}</strong>
          <span>最高频：${escapeHtml(topSelfHealingStatus.value || "-")}${topSelfHealingStatus.count !== undefined ? ` (${escapeHtml(topSelfHealingStatus.count)})` : ""}</span>
        </div>
        <div class="wb-history-summary-card">
          <span class="wb-history-summary-label">治理关注项</span>
          <strong>需人工复核 ${escapeHtml(data.risk_requires_review_count || 0)}</strong>
          <span>边界拒绝 ${escapeHtml(data.boundary_rejected_count || 0)}</span>
        </div>
      </div>
    `;
  }

  function renderHistoryDetail(item, detailText) {
    const rules = normalizeRuleList(item?.matched_rules, 3);
    const evidence = normalizeStringList(item?.evidence, 3);
    const riskSummary = item?.risk_summary && typeof item.risk_summary === "object" ? item.risk_summary : {};
    const riskTopFactor = riskSummary?.top_factor && typeof riskSummary.top_factor === "object" ? riskSummary.top_factor : {};
    const semanticSummary = item?.page_semantic_summary && typeof item.page_semantic_summary === "object" ? item.page_semantic_summary : {};
    const selfHealingSummary = item?.self_healing_summary && typeof item.self_healing_summary === "object" ? item.self_healing_summary : {};
    const healingBoundary = selfHealingSummary?.boundary && typeof selfHealingSummary.boundary === "object" ? selfHealingSummary.boundary : {};
    const failureSource = String(item?.failure_source || item?.failure_analysis?.failure_source || "").trim();
    const failureSourceReason = String(
      item?.failure_source_reason || item?.failure_analysis?.failure_source_reason || ""
    ).trim();
    const requiresManualReview = Boolean(
      item?.requires_manual_review || item?.failure_analysis?.requires_manual_review
    );
    const blocks = [
      `<div class="wb-history-detail-summary">${escapeHtml(detailText)}</div>`,
    ];
    if (item?.gate_reason_summary) {
      blocks.push(`<div class="wb-history-detail-note">门禁依据：${escapeHtml(item.gate_reason_summary)}</div>`);
    }
    if (Object.keys(riskSummary).length) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">风险摘要</span>
          <div class="wb-history-detail-line">等级：${escapeHtml(riskSummary.risk_level || "-")}</div>
          <div class="wb-history-detail-line">门禁：${escapeHtml(riskSummary.gate_decision || "-")}</div>
          <div class="wb-history-detail-line">分数：${escapeHtml(riskSummary.risk_score ?? "-")}</div>
          <div class="wb-history-detail-line">因子数：${escapeHtml(riskSummary.factor_count ?? "-")}</div>
          <div class="wb-history-detail-line">主因子：${escapeHtml(riskTopFactor.factor || "-")}${riskTopFactor.score !== undefined ? ` (${escapeHtml(riskTopFactor.score)})` : ""}</div>
        </div>
      `);
    }
    if (Object.keys(semanticSummary).length) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">页面语义</span>
          <div class="wb-history-detail-line">类型：${escapeHtml(semanticSummary.page_type || "-")}</div>
          <div class="wb-history-detail-line">领域：${escapeHtml(semanticSummary.business_domain || "-")}</div>
          <div class="wb-history-detail-line">目标：${escapeHtml(semanticSummary.primary_goal || "-")}</div>
          <div class="wb-history-detail-line">动作：${escapeHtml(Array.isArray(semanticSummary.primary_actions) ? semanticSummary.primary_actions.join(" / ") : "-")}</div>
        </div>
      `);
    }
    if (Object.keys(selfHealingSummary).length) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">自愈摘要</span>
          <div class="wb-history-detail-line">状态：${escapeHtml(selfHealingSummary.status || "-")}</div>
          <div class="wb-history-detail-line">尝试：${escapeHtml(selfHealingSummary.attempted ? "是" : "否")}</div>
          <div class="wb-history-detail-line">边界允许：${escapeHtml(healingBoundary.allowed ? "是" : "否")}</div>
          <div class="wb-history-detail-line">建议类型：${escapeHtml(healingBoundary.advice_type || "-")}</div>
          <div class="wb-history-detail-line">边界原因：${escapeHtml(healingBoundary.reason || selfHealingSummary.reason || "-")}</div>
        </div>
      `);
    }
    if (failureSource || failureSourceReason || requiresManualReview) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">失败归因</span>
          <div class="wb-history-detail-line">来源：${escapeHtml(failureSource || "-")}</div>
          <div class="wb-history-detail-line">依据：${escapeHtml(failureSourceReason || "-")}</div>
          <div class="wb-history-detail-line">人工复核：${escapeHtml(requiresManualReview ? "需要" : "否")}</div>
        </div>
      `);
    }
    if (rules.length) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">命中规则</span>
          ${rules.map((rule) => `
            <div class="wb-history-detail-line">
              <strong>${escapeHtml(rule.level || "rule")}</strong>
              <span>${escapeHtml(rule.message)}</span>
            </div>
          `).join("")}
        </div>
      `);
    }
    if (evidence.length) {
      blocks.push(`
        <div class="wb-history-detail-block">
          <span class="wb-history-detail-label">证据摘要</span>
          ${evidence.map((line) => `<div class="wb-history-detail-line">${escapeHtml(line)}</div>`).join("")}
        </div>
      `);
    }
    return `<div class="wb-history-detail">${blocks.join("")}</div>`;
  }

  function buildWorkbenchAuditLink(item, label) {
    const runId = String(item?.run_id || "").trim();
    if (!runId) {
      return escapeHtml(label || "-");
    }
    const params = new URLSearchParams();
    params.set("run_id", runId);
    if (item?.project) params.set("project", String(item.project).trim());
    if (item?.review_type) params.set("review_type", String(item.review_type).trim());
    if (item?.page) params.set("page", String(item.page).trim());
    return `<a class="wb-audit-link" href="/workbench?${params.toString()}">${escapeHtml(label || `run:${runId}`)}</a>`;
  }

  function buildGenerateAuditLink(item, label) {
    const runId = String(item?.run_id || "").trim();
    if (!runId) {
      return escapeHtml(label || "-");
    }
    const params = new URLSearchParams();
    params.set("run_id", runId);
    if (item?.project) params.set("project", String(item.project).trim());
    if (item?.review_type) params.set("review_type", String(item.review_type).trim());
    if (item?.page) params.set("page", String(item.page).trim());
    return `<a class="wb-audit-link" href="/workbench/generate?${params.toString()}">${escapeHtml(label || `run:${runId}`)}</a>`;
  }

  function renderRow(item) {
    const status = item.status || item.queue_status || item.result || "-";
    const reviewItems = Array.isArray(item.review_items) ? item.review_items.filter(Boolean) : [];
    const detailSummary = item.detail_summary || item.note || "-";
    const extras = [];
    if (item.approval_status) {
      extras.push(`审批状态=${item.approval_status}`);
    }
    if (item.record_status) {
      extras.push(`记录状态=${item.record_status}`);
    }
    if (item.second_approver) {
      extras.push(`二次审批=${item.second_approver}${item.second_approver_role ? `(${item.second_approver_role})` : ""}`);
    }
    if (item.revoked_by) {
      extras.push(`撤销=${item.revoked_by}${item.revoked_by_role ? `(${item.revoked_by_role})` : ""}`);
    }
    const detailBase = reviewItems.length ? `${detailSummary}：${reviewItems.join(" / ")}` : detailSummary;
    const detailText = extras.length ? `${detailBase} · ${extras.join(" · ")}` : detailBase;
    const actor = item.actor_display || item.confirmed_by || "-";
    let ref = "-";
    if (item.run_id) {
      ref = buildWorkbenchAuditLink(item, `run:${item.run_id}`);
    } else if (item.path) {
      ref = escapeHtml(item.path);
    }
    const actionLink = String(item?.action || "").trim().startsWith("review_")
      ? buildGenerateAuditLink(item, item.action || "-")
      : buildWorkbenchAuditLink(item, item.action || "-");
    return `
      <tr>
        <td>${escapeHtml(formatTime(item.timestamp))}</td>
        <td>${actionLink}</td>
        <td>${escapeHtml(item.case_id || "-")}</td>
        <td>${escapeHtml(item.page || "-")}</td>
        <td>${escapeHtml(actor)}</td>
        <td>${escapeHtml(status)}</td>
        <td>${renderHistoryDetail(item, detailText)}</td>
        <td>${ref}</td>
      </tr>
    `;
  }

  function updateAuthNotice() {
    if (!els.authNotice) return;
    const authState = window.platformAuth && typeof window.platformAuth.getAuthState === "function"
      ? String(window.platformAuth.getAuthState() || "anonymous").toLowerCase()
      : "anonymous";
    if (authState === "authenticated" || authState === "token") {
      const currentUser = window.platformAuth && typeof window.platformAuth.getCurrentUser === "function"
        ? window.platformAuth.getCurrentUser()
        : null;
      const username = String(currentUser?.username || currentUser?.name || "当前用户").trim();
      els.authNotice.className = "wb-auth-notice wb-auth-notice-authenticated";
      els.authNotice.textContent = `${username} 已登录。之后产生的确认点记录会直接显示为你的真实身份。`;
      return;
    }
    els.authNotice.className = "wb-auth-notice wb-auth-notice-anonymous";
    els.authNotice.textContent = "当前为未登录状态：你可以查看历史，但若后续在生成页做确认，系统会先要求登录以保证审计可追溯。";
  }

  async function loadHistory() {
    const params = new URLSearchParams();
    const actionValue = String(els.actionFilter?.value || "").trim();
    const statusValue = String(els.statusFilter?.value || "").trim();
    const riskGateValue = String(els.riskGateFilter?.value || "").trim();
    const selfHealingStatusValue = String(els.selfHealingStatusFilter?.value || "").trim();
    const actorValue = String(els.actorFilter?.value || "").trim();
    if (actionValue) params.set("action", actionValue);
    if (statusValue) params.set("status", statusValue);
    if (riskGateValue) params.set("risk_gate_decision", riskGateValue);
    if (selfHealingStatusValue) params.set("self_healing_status", selfHealingStatusValue);
    if (actorValue) params.set("actor", actorValue);
    const query = params.toString();
    const resp = await authFetch(`/api/workbench/history${query ? `?${query}` : ""}`);
    if (!resp.ok) {
      renderSummary({});
      els.body.innerHTML = '<tr><td colspan="8">加载失败</td></tr>';
      return;
    }
    const payload = await resp.json();
    renderSummary(payload.summary);
    const items = payload.items || [];
    if (!items.length) {
      els.body.innerHTML = '<tr><td colspan="8">暂无历史记录</td></tr>';
      return;
    }
    els.body.innerHTML = items.map(renderRow).join("");
  }

  function bindEvents() {
    els.refreshBtn.addEventListener("click", loadHistory);
    els.actionFilter?.addEventListener("change", loadHistory);
    els.statusFilter?.addEventListener("change", loadHistory);
    els.riskGateFilter?.addEventListener("change", loadHistory);
    els.selfHealingStatusFilter?.addEventListener("change", loadHistory);
    els.actorFilter?.addEventListener("input", () => {
      window.clearTimeout(bindEvents.actorTimer);
      bindEvents.actorTimer = window.setTimeout(() => {
        loadHistory().catch((error) => {
          console.error(error);
          els.body.innerHTML = '<tr><td colspan="8">加载失败</td></tr>';
        });
      }, 250);
    });
  }

  function bootstrap() {
    updateAuthNotice();
    bindEvents();
    loadHistory().catch((error) => {
      console.error(error);
      els.body.innerHTML = '<tr><td colspan="8">加载失败</td></tr>';
    });
    window.addEventListener("platform-auth-changed", updateAuthNotice);
  }

  bootstrap();
})();
