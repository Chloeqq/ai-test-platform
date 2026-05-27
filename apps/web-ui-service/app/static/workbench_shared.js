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

  function normalizeCaseId(value) {
    if (typeof window.platformNormalizeCaseId === "function") {
      return window.platformNormalizeCaseId(value);
    }
    return String(value || "").trim();
  }

  function displayCaseId(value) {
    if (typeof window.platformDisplayCaseId === "function") {
      return window.platformDisplayCaseId(value);
    }
    return String(value || "").trim() || "-";
  }

  function extractCaseIdFromYaml(text) {
    const content = String(text || "");
    const matched = content.match(/^\s*id\s*:\s*(.+?)\s*(?:#.*)?$/im);
    if (!matched) return "";
    return normalizeCaseId(matched[1]);
  }

  function reviewStatusText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "confirmed") return "已确认";
    if (normalized === "skipped") return "已跳过";
    if (normalized === "not_required") return "无需确认";
    return "待确认";
  }

  function gateApprovalText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "pending_second_approval") return "待二次审批";
    if (normalized === "approved") return "已审批";
    if (normalized === "revoked") return "已撤销";
    return normalized || "未知";
  }

  function gateRecordText(value) {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "revoked") return "已撤销";
    if (normalized === "active") return "有效";
    return normalized || "未知";
  }

  function renderGateMetrics(metrics) {
    const data = metrics && typeof metrics === "object" ? metrics : {};
    return [
      `status=${String(data.status || "-")}`,
      `coverage=${String(data.coverage_status || "-")}`,
      `low_conf_elements=${Number(data.low_confidence_elements || 0)}`,
      `missing_po=${Number(data.missing_page_object_elements || 0)}`,
      `pending_points=${Number(data.pending_test_points || 0)}`,
      `skip_points=${Number(data.skip_suggestions || 0)}`,
      `dependency_points=${Number(data.dependency_review_points || 0)}`,
      `low_conf_dependency_points=${Number(data.low_confidence_dependency_points || 0)}`,
      `missing_dependency_points=${Number(data.missing_dependency_points || 0)}`,
      `dependency_skip_points=${Number(data.dependency_skip_points || 0)}`,
      `pending_sections=${Number(data.pending_review_sections || 0)}`,
    ].join(" · ");
  }

  function renderGateConfigSnapshot(snapshot) {
    const data = snapshot && typeof snapshot === "object" ? snapshot : {};
    return [
      `缺失必需元素阻断阈值=${Number(data.block_missing_required_threshold || 0)}`,
      `未识别依赖阻断阈值=${Number(data.block_missing_dependency_points_threshold || 0)}`,
      `失败即阻断=${Boolean(data.block_on_failed_status)}`,
      `风险阻断联动=${Boolean(data.block_on_risk_block)}`,
      `低置信度元素告警=${Boolean(data.warn_on_low_confidence_elements)}`,
      `待确认测试点告警=${Boolean(data.warn_on_pending_test_points)}`,
      `低置信度依赖告警=${Boolean(data.warn_on_low_confidence_dependency_points)}`,
      `待确认分组告警=${Boolean(data.warn_on_pending_reviews)}`,
    ].join(" · ");
  }

  function renderGateNextAction(decision) {
    const normalized = String(decision || "").trim().toLowerCase();
    if (normalized === "block") {
      return "下一步：先修复阻断项，再重新执行；当前不建议直接放行。";
    }
    if (normalized === "manual_review") {
      return "下一步：先完成确认点，再决定人工放行还是人工阻断。";
    }
    return "下一步：当前门禁允许继续推进，可结合后续执行或发布流程继续处理。";
  }

  function renderReviewSummary(reviewState) {
    if (!reviewState || typeof reviewState !== "object") {
      return '<div>确认点：当前运行未记录确认信息。</div>';
    }
    const element = reviewState.element && typeof reviewState.element === "object" ? reviewState.element : {};
    const testPoint = reviewState.test_point && typeof reviewState.test_point === "object" ? reviewState.test_point : {};
    const risk = reviewState.risk && typeof reviewState.risk === "object" ? reviewState.risk : {};
    return `
      <div>确认点总览：待确认 ${escapeHtml(reviewState.pending_sections || 0)} 组，已确认 ${escapeHtml(reviewState.confirmed_sections || 0)} 组</div>
      <div>元素确认：${escapeHtml(reviewStatusText(element.status))}（${escapeHtml(element.candidate_count || 0)} 项）</div>
      <div>测试点确认：${escapeHtml(reviewStatusText(testPoint.status))}（${escapeHtml(testPoint.candidate_count || 0)} 项）</div>
      <div>风险决策：${escapeHtml(reviewStatusText(risk.status))}（${escapeHtml(risk.candidate_count || 0)} 项）</div>
    `;
  }

  function renderExecutionGateSummary(executionGate) {
    const gate = executionGate && typeof executionGate === "object" ? executionGate : {};
    if (!Object.keys(gate).length) {
      return '<div>执行门禁：当前运行未记录门禁决策。</div>';
    }
    const blockers = Array.isArray(gate.blockers) ? gate.blockers.filter(Boolean) : [];
    const warnings = Array.isArray(gate.warnings) ? gate.warnings.filter(Boolean) : [];
    const evidence = Array.isArray(gate.evidence) ? gate.evidence.filter(Boolean) : [];
    const metrics = gate.metrics && typeof gate.metrics === "object" ? gate.metrics : {};
    const configSnapshot = gate.config_snapshot && typeof gate.config_snapshot === "object" ? gate.config_snapshot : {};
    const effectiveDecision = String(gate.effective_decision || gate.decision || "allow").trim() || "allow";
    const manualDecision = gate.manual_decision && typeof gate.manual_decision === "object" ? gate.manual_decision : {};
    const approvalStatus = String(gate.approval_status || manualDecision.approval_status || "approved").trim().toLowerCase() || "approved";
    const recordStatus = String(gate.record_status || manualDecision.record_status || "active").trim().toLowerCase() || "active";
    const revokedBy = String(manualDecision.revoked_by || gate.revoked_by || manualDecision.decided_by || "-").trim() || "-";
    const revokedByRole = String(manualDecision.revoked_by_role || gate.revoked_by_role || "").trim();
    const revokedAt = String(manualDecision.revoked_at || gate.revoked_at || "").trim();
    return `
      <div>执行门禁：系统决策=${escapeHtml(gate.decision || "allow")}，生效决策=${escapeHtml(effectiveDecision)}，来源=${escapeHtml(gate.decision_source || "system")}</div>
      <div>requires_review=${escapeHtml(String(Boolean(gate.requires_review)))}</div>
      <div>规则边界：未识别依赖达到阈值时阻断；低置信度依赖默认人工复核。</div>
      <div>规则快照：${escapeHtml(renderGateConfigSnapshot(configSnapshot))}</div>
      <div>命中指标：${escapeHtml(renderGateMetrics(metrics))}</div>
      <div>动作建议：${escapeHtml(renderGateNextAction(effectiveDecision))}</div>
      <div>审批状态=${escapeHtml(gateApprovalText(approvalStatus))}，记录状态=${escapeHtml(gateRecordText(recordStatus))}</div>
      <div>门禁阻断项：${escapeHtml(blockers.length)}</div>
      <div>门禁告警项：${escapeHtml(warnings.length)}</div>
      ${blockers.length ? `<div>阻断原因：${escapeHtml(blockers.join(" "))}</div>` : ""}
      ${warnings.length ? `<div>告警原因：${escapeHtml(warnings.join(" "))}</div>` : ""}
      ${evidence.length ? `<div>门禁依据：${escapeHtml(evidence.join(" "))}</div>` : ""}
      ${manualDecision && Object.keys(manualDecision).length ? `<div>人工决策：${escapeHtml(manualDecision.decision || "-")} · ${escapeHtml(manualDecision.decided_by || "-")} · ${escapeHtml(formatTime(manualDecision.updated_at || "-"))}${manualDecision.note ? ` · 备注：${escapeHtml(manualDecision.note)}` : ""}</div>` : ""}
      ${manualDecision?.second_approver ? `<div>二次审批：${escapeHtml(manualDecision.second_approver)}${manualDecision.second_approver_role ? ` (${escapeHtml(manualDecision.second_approver_role)})` : ""}${manualDecision.second_approved_at ? ` · ${escapeHtml(manualDecision.second_approved_at)}` : ""}</div>` : ""}
      ${recordStatus === "revoked" ? `<div>撤销信息：${escapeHtml(revokedBy)}${revokedByRole ? ` (${escapeHtml(revokedByRole)})` : ""}${revokedAt ? ` · ${escapeHtml(revokedAt)}` : ""}</div>` : ""}
    `;
  }

  function renderReviewAuditSummary(summary) {
    if (!summary || typeof summary !== "object") {
      return "";
    }
    const sections = Array.isArray(summary.sections) ? summary.sections : [];
    const lines = sections
      .filter((section) => section && typeof section === "object" && (section.actor_display || section.updated_at || section.candidate_count))
      .map((section) => {
        const actor = String(section.actor_display || section.confirmed_by || "").trim();
        const updatedAt = String(section.updated_at || "").trim();
        if (!actor && !updatedAt) {
          return `<div>${escapeHtml(section.label || section.review_type || "-")}：${escapeHtml(reviewStatusText(section.status))}</div>`;
        }
        return `<div>${escapeHtml(section.label || section.review_type || "-")}：${escapeHtml(reviewStatusText(section.status))}${actor ? ` · ${escapeHtml(actor)}` : ""}${updatedAt ? ` · ${escapeHtml(formatTime(updatedAt))}` : ""}</div>`;
      })
      .join("");
    if (!lines) {
      return "";
    }
    const latestActor = String(summary.latest_actor_display || "").trim();
    const latestUpdatedAt = String(summary.latest_updated_at || "").trim();
    const latestLine = latestActor || latestUpdatedAt
      ? `<div>最近一次确认：${escapeHtml(latestActor || "-")}${latestUpdatedAt ? ` · ${escapeHtml(formatTime(latestUpdatedAt))}` : ""}</div>`
      : "";
    return `
      <div class="wb-review-audit">
        <div>审计摘要：待确认 ${escapeHtml(summary.pending_sections || 0)} 组，已确认 ${escapeHtml(summary.confirmed_sections || 0)} 组</div>
        ${latestLine}
        ${lines}
      </div>
    `;
  }

  function renderAuditTimeline(container, timeline, focusReviewType) {
    if (!container) return;
    const rows = Array.isArray(timeline) ? timeline : [];
    if (!rows.length) {
      container.className = "wb-audit-panel wb-review-empty";
      container.innerHTML = "当前运行暂无确认、拒绝或风险决策审计事件。";
      return;
    }
    container.className = "wb-audit-panel";
    container.innerHTML = `
      <section class="wb-audit-card">
        <h3>审计时间线</h3>
        ${rows
          .map(
            (entry, index) => `
              <div class="wb-audit-line ${focusReviewType && focusReviewType === String(entry.review_type || "").trim().toLowerCase() ? "wb-audit-line-active" : ""}">
                <strong>${index + 1}. ${escapeHtml(entry.detail_summary || entry.action || "-")}</strong>
                <div class="wb-audit-meta">
                  <span>时间：${escapeHtml(formatTime(entry.timestamp))}</span>
                  <span>类型：${escapeHtml(entry.review_type || "-")}</span>
                  <span>状态：${escapeHtml(entry.status || "-")}</span>
                  <span>确认人：${escapeHtml(entry.actor_display || entry.confirmed_by || "-")}</span>
                </div>
                ${entry.gate_reason_summary ? `<div class="wb-audit-note">门禁依据：${escapeHtml(entry.gate_reason_summary)}</div>` : ""}
              </div>
            `
          )
          .join("")}
      </section>
    `;
  }

  function renderSourceEvidence(items) {
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) return "-";
    return rows
      .slice(0, 3)
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const signal = String(item.signal || "-").trim();
        const value = String(item.value || "-").trim();
        const origin = String(item.origin || "-").trim();
        return `${signal}:${value} @ ${origin}`;
      })
      .filter(Boolean)
      .join("；");
  }

  window.WorkbenchShared = {
    displayCaseId,
    escapeHtml,
    extractCaseIdFromYaml,
    formatTime,
    normalizeCaseId,
    renderAuditTimeline,
    renderExecutionGateSummary,
    renderReviewAuditSummary,
    renderReviewSummary,
    renderSourceEvidence,
  };
})();
