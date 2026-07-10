import { type FocusEvent, type MouseEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import {
  batchGenerateCasesFromTestPointAssets,
  batchReviewTestPoints,
  getTestPointAsset,
  getTestPointAssetCoverageMatrix,
  updateTestPointAsset,
} from "../api/assets";
import { BulkActionBar } from "../components/BulkActionBar";
import { ColumnFilter } from "../components/ColumnFilter";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { TablePagination } from "../components/TablePagination";
import { normalizeProjectCode } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function numberValue(value: unknown): string {
  if (typeof value === "number") {
    return String(value);
  }
  const normalized = String(value || "").trim();
  return normalized || "0";
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function generationFailureLabel(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "原因未返回";
  }
  if (raw.includes("execution_compiler_intent_coverage_failed")) {
    return "缺少可编译步骤或测试点未被脚本覆盖";
  }
  if (raw.includes("page_object_no_qualified_elements")) {
    return "页面对象缺少合格元素";
  }
  if (raw.includes("page_object_url_missing")) {
    return "页面对象缺少页面 URL";
  }
  if (raw.includes("page_object_db_lookup_failed")) {
    return "页面对象数据库查询失败";
  }
  return raw.length > 80 ? `${raw.slice(0, 80)}...` : raw;
}

function buildGenerationFeedback(response: Record<string, unknown>): string {
  const count = Number(response.count || 0);
  const summary = response.summary && typeof response.summary === "object" ? (response.summary as Record<string, unknown>) : {};
  const skipped = asRecordList(summary.skipped);
  const skippedCount = Number(summary.skipped_assets || skipped.length || 0);
  const skippedText = skipped
    .slice(0, 3)
    .map((item) => `${text(item.intent_id || item.asset_id)}：${generationFailureLabel(item.reason || item.message)}`)
    .join("；");
  if (count > 0 && skippedCount > 0) {
    return `已生成 ${count} 条用例；${skippedCount} 条测试点未生成${skippedText ? `：${skippedText}` : "，请查看生成明细"}。`;
  }
  if (count > 0) {
    return `已生成 ${count} 条已通过测试点用例，可前往用例中心查看。`;
  }
  if (skippedCount > 0) {
    return `未生成用例；${skippedCount} 条测试点被跳过${skippedText ? `：${skippedText}` : "，请检查已通过测试点和页面对象配置"}。`;
  }
  return "未生成用例，请检查已通过测试点和页面对象配置。";
}

type SummaryBadgeTone = "ai" | "manual" | "warning" | "success" | "danger" | "neutral";
type PointReviewStatus = "pending" | "approved" | "rejected";

interface SummaryBadgeConfig {
  label: string;
  tone: SummaryBadgeTone;
  hint?: string;
  raw?: string;
}

function classifyWarning(w: string): { category: string; tone: string } {
  const lower = w.toLowerCase();
  if (lower.includes("assertion_missing")) return { category: "阻断问题", tone: "danger" };
  if (lower.includes("缺少涉及元素")) return { category: "阻断问题", tone: "danger" };
  if (lower.includes("元素未在 page object 注册")) return { category: "阻断问题", tone: "danger" };
  if (lower.includes("仍需人工结构化")) return { category: "待人工处理", tone: "warning" };
  if (lower.includes("缺少明确测试数据") || lower.includes("空格输入") || lower.includes("无法无损表达")) return { category: "数据补充", tone: "warning" };
  return { category: "其他", tone: "neutral" };
}

function QualityGateCard({ report }: { report: Record<string, unknown> }) {
  if (!report || !Object.keys(report).length) {
    return null;
  }
  const score = Number(report.score ?? 0);
  const decision = String(report.decision || "PASS");
  const zeroCount = Number(report.zero_assertion_count ?? 0);
  const total = Number(report.total_points ?? 0);
  const candidateCount = Number(report.candidate_step_count ?? 0);
  const unprocessedCount = Number(report.unprocessed_count ?? 0);
  const byType = (report.by_point_type || {}) as Record<string, Record<string, number>>;

  // P0-2: 优先新字段 quality_warnings / data_warnings，回退到旧字段
  const qualityWarnings: string[] = Array.isArray(report.quality_warnings)
    ? report.quality_warnings as string[] : [];
  const dataWarnings: string[] = Array.isArray(report.data_warnings)
    ? report.data_warnings as string[] : [];
  const effectiveQuality = qualityWarnings.length > 0
    ? qualityWarnings
    : (Array.isArray(report.assertion_warnings) ? report.assertion_warnings as string[] : []);
  const effectiveData = dataWarnings;

  const decisionBadge: Record<string, { label: string; icon: string; tone: string }> = {
    REJECT: { label: "不可执行", icon: "🚫", tone: "danger" },
    REVIEW: { label: "需审核", icon: "⚠️", tone: "warning" },
    PASS: { label: "可执行", icon: "✅", tone: "success" },
  };
  const badge = decisionBadge[decision] || { label: decision, icon: "❓", tone: "neutral" };

  const hasQualityIssues = zeroCount > 0 || candidateCount > 0 || effectiveQuality.length > 0;
  const hasDataHints = effectiveData.length > 0;
  const hasContent = hasQualityIssues || hasDataHints || Object.keys(byType).length > 0;

  return (
    <div className={`asset-review-banner asset-review-${badge.tone}`}>
      {/* ── 质量评分 ── */}
      <div className="detail-field-row" style={{ flexWrap: "wrap", gap: "8px 16px", alignItems: "baseline" }}>
        <strong>质量评分</strong>
        <span style={{ fontSize: "1.1rem", fontWeight: 600 }}>{score}/100</span>
      </div>

      {/* ── 执行状态 ── */}
      <div className="detail-field-row" style={{ flexWrap: "wrap", gap: "4px 12px", alignItems: "baseline" }}>
        <strong>执行状态</strong>
        <span>{badge.icon} {badge.label}</span>
      </div>

      {/* ── 指标 ── */}
      <div className="detail-field-row" style={{ flexWrap: "wrap", gap: "4px 12px", fontSize: "0.9rem" }}>
        <span>零断言: <strong>{zeroCount}</strong>/{total}</span>
        {candidateCount > 0 ? (
          <span>未结构化: <strong>{candidateCount}</strong> (其中 {unprocessedCount} 无断言)</span>
        ) : null}
      </div>
      {!hasContent ? null : (
        <div className="detail-field-section" style={{ marginTop: 8 }}>
          {/* ── 零断言 by type ── */}
          {Object.keys(byType).length > 0 && zeroCount > 0 ? (
            <div className="detail-field-row" style={{ flexWrap: "wrap", gap: 4 }}>
              {Object.entries(byType).map(([pt, stats]) =>
                stats.zero_assertion > 0 ? (
                  <span key={pt} className="tag tag--danger">
                    {pt}: {stats.zero_assertion}/{stats.total} 零断言
                  </span>
                ) : null
              )}
            </div>
          ) : null}

          {/* ── 质量问题 ── */}
          {effectiveQuality.length > 0 ? (
            <div className="detail-field-row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4, marginTop: 4 }}>
              <span className="tag tag--danger" style={{ fontWeight: 600 }}>质量问题 ({effectiveQuality.length})</span>
              {effectiveQuality.slice(0, 5).map((w, i) => (
                <div key={i} className="detail-field-help" style={{ paddingLeft: 8 }}>🚫 {w}</div>
              ))}
              {effectiveQuality.length > 5 ? (
                <div className="detail-field-help" style={{ paddingLeft: 8 }}>...及其他 {effectiveQuality.length - 5} 条</div>
              ) : null}
            </div>
          ) : null}

          {/* ── 待结构化 ── */}
          {unprocessedCount > 0 ? (
            <div className="detail-field-row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4, marginTop: 4 }}>
              <span className="tag tag--warning" style={{ fontWeight: 600 }}>待结构化 ({unprocessedCount})</span>
              <div className="detail-field-help" style={{ paddingLeft: 8 }}>
                ⚠️ {unprocessedCount} 个测试点存在 candidate_step 且未生成断言步骤，建议进入编辑页完成人工结构化。
              </div>
            </div>
          ) : null}

          {/* ── 数据补充 ── */}
          {effectiveData.length > 0 ? (
            <div className="detail-field-row" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4, marginTop: 4 }}>
              <span className="tag tag--neutral" style={{ fontWeight: 600 }}>数据补充 ({effectiveData.length})</span>
              {effectiveData.slice(0, 3).map((w, i) => (
                <div key={i} className="detail-field-help" style={{ paddingLeft: 8 }}>📋 {w}</div>
              ))}
              {effectiveData.length > 3 ? (
                <div className="detail-field-help" style={{ paddingLeft: 8 }}>...及其他 {effectiveData.length - 3} 条</div>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

const SOURCE_BADGE_MAP: Record<string, SummaryBadgeConfig> = {
  selection_save: { label: "AI 自动生成", tone: "ai" },
  generate_chain: { label: "AI 自动生成", tone: "ai" },
  requirement_intents: { label: "AI 自动生成", tone: "ai" },
  manual: { label: "手动创建", tone: "manual" },
  yaml_case: { label: "YAML 用例同步", tone: "neutral" },
  fallback: { label: "系统兜底生成", tone: "neutral" },
  openapi_spec: { label: "OpenAPI 导入", tone: "neutral" },
};

const STATUS_BADGE_MAP: Record<string, SummaryBadgeConfig> = {
  needs_review: { label: "⚠️ 待审核", tone: "warning", hint: "建议先审核再生成用例" },
  review: { label: "⚠️ 待审核", tone: "warning", hint: "建议先审核再生成用例" },
  pending: { label: "⚠️ 待审核", tone: "warning", hint: "建议先审核再生成用例" },
  approved: { label: "✅ 已通过", tone: "success", hint: "可进入生成用例" },
  ready: { label: "✅ 已通过", tone: "success", hint: "可进入生成用例" },
  active: { label: "✅ 已通过", tone: "success", hint: "可进入生成用例" },
  rejected: { label: "❌ 已驳回", tone: "danger", hint: "需修改后重新审核" },
  blocked: { label: "已阻断", tone: "danger", hint: "请先处理阻断原因" },
  block: { label: "已阻断", tone: "danger", hint: "请先处理阻断原因" },
  draft: { label: "草稿", tone: "neutral", hint: "可继续编辑完善" },
  unknown: { label: "未知", tone: "neutral" },
};

function sourceBadgeConfig(item: Record<string, unknown>): SummaryBadgeConfig {
  const raw = String(item.source_type || item.source_label || "").trim();
  const normalized = raw.toLowerCase();
  const mapped = SOURCE_BADGE_MAP[normalized];
  if (mapped) {
    return { ...mapped, raw };
  }
  const label = text(item.source_label || item.source_type);
  return { label, tone: "neutral", raw };
}

function statusBadgeConfig(item: Record<string, unknown>): SummaryBadgeConfig {
  const plan = (item.plan || {}) as Record<string, unknown>;
  const selectionSummary = (item.selection_summary || {}) as Record<string, unknown>;
  const reviewSummary = (item.review_summary || plan.review_summary || {}) as Record<string, unknown>;
  const rawCandidates = [
    reviewSummary.manual_review_status,
    reviewSummary.review_status,
    item.review_status,
    selectionSummary.selection_state,
    item.status,
  ];
  const raw = String(rawCandidates.find((value) => String(value || "").trim()) || "").trim();
  const normalized = raw.toLowerCase();
  const needsReview = Boolean(item.requires_review || plan.requires_review);
  const fallbackStatus = needsReview && (!normalized || normalized === "unknown" || normalized === "ready") ? "needs_review" : normalized;
  const mapped = STATUS_BADGE_MAP[fallbackStatus] || STATUS_BADGE_MAP.unknown;
  return { ...mapped, raw: raw || fallbackStatus };
}

function traceabilityStatusLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    covered: "已覆盖",
    partial: "部分覆盖",
    gap: "存在缺口",
    orphan: "待关联",
    unknown: "未知",
  };
  return labels[normalized] || text(value);
}

function intentTypeLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    functional: "功能",
    positive: "正向",
    negative: "异常",
    business_exception: "业务异常",
    security: "安全",
    boundary: "边界",
    format: "格式",
    interaction_exception: "交互异常",
  };
  return labels[normalized] || text(value);
}

function intentTypeClass(value: unknown): string {
  const normalized = String(value || "unknown").trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-") || "unknown";
  return `type-${normalized}`;
}

function priorityClass(value: unknown): string {
  const normalized = String(value || "unknown").trim().toLowerCase().replace(/[^a-z0-9_-]/g, "-") || "unknown";
  return `priority-${normalized}`;
}

function priorityRank(value: unknown): number {
  const normalized = String(value || "").trim().toUpperCase();
  const matched = normalized.match(/^P(\d+)$/);
  return matched ? Number(matched[1]) : 999;
}

function reviewStatusValue(row: Record<string, unknown>): PointReviewStatus {
  const normalized = String(row.review_status || row.manual_review_status || "").trim().toLowerCase();
  if (["approved", "pass", "passed", "ready"].includes(normalized)) {
    return "approved";
  }
  if (["rejected", "reject", "failed"].includes(normalized)) {
    return "rejected";
  }
  return "pending";
}

function reviewStatusLabel(value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已驳回",
  };
  return labels[normalized] || "待审核";
}

function reviewStatusClass(value: unknown): string {
  return `review-${reviewStatusValue({ review_status: value })}`;
}

function reviewStatusOptions(rows: Array<Record<string, unknown>>): Array<{ value: string; label: string; count: number }> {
  const counts: Record<PointReviewStatus, number> = {
    pending: 0,
    approved: 0,
    rejected: 0,
  };
  rows.forEach((row) => {
    counts[reviewStatusValue(row)] += 1;
  });
  return (["pending", "approved", "rejected"] as PointReviewStatus[])
    .filter((value) => counts[value] > 0)
    .map((value) => ({
      value,
      label: reviewStatusLabel(value),
      count: counts[value],
    }));
}

function reviewCounts(rows: Array<Record<string, unknown>>): Record<PointReviewStatus | "total", number> {
  const counts: Record<PointReviewStatus | "total", number> = {
    total: rows.length,
    pending: 0,
    approved: 0,
    rejected: 0,
  };
  rows.forEach((row) => {
    counts[reviewStatusValue(row)] += 1;
  });
  return counts;
}

function assetReviewBadgeConfig(counts: Record<PointReviewStatus | "total", number>, fallback: SummaryBadgeConfig): SummaryBadgeConfig {
  if (!counts.total) {
    return fallback;
  }
  if (counts.approved === counts.total) {
    return { label: "✅ 已通过", tone: "success", hint: "全部测试点已通过，可进入生成用例" };
  }
  if (counts.rejected === counts.total) {
    return { label: "❌ 已驳回", tone: "danger", hint: "全部测试点被驳回，请修改后重新审核" };
  }
  if (counts.approved > 0) {
    return { label: "部分通过", tone: "warning", hint: `已通过 ${counts.approved}/${counts.total} 条，可基于已通过测试点继续推进` };
  }
  return { label: "⚠️ 待审核", tone: "warning", hint: "请选择测试点进行批量或单条审核" };
}

function optionCounts(
  rows: Array<Record<string, unknown>>,
  key: string,
  labelForValue: (value: unknown) => string,
  sortValues: (left: string, right: string) => number,
): Array<{ value: string; label: string; count: number }> {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const value = String(row[key] || "").trim();
    if (value) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
  });
  return Array.from(counts.entries())
    .sort(([left], [right]) => sortValues(left, right))
    .map(([value, count]) => ({
      value,
      label: labelForValue(value),
      count,
    }));
}

function pointIdOf(row: Record<string, unknown>): string {
  return String(row.intent_id || row.key || "").trim();
}

function candidatePayloadFromRow(row: Record<string, unknown>, page: unknown): Record<string, unknown> {
  const expected = String(row.expected || row.expected_result || "").trim();
  const intentId = pointIdOf(row);
  return {
    ...row,
    key: String(row.key || intentId).trim(),
    intent_id: intentId,
    title: String(row.title || row.summary || row.intent_id || "").trim(),
    summary: String(row.summary || row.title || "").trim(),
    description: String(row.summary || row.title || "").trim(),
    point_type: String(row.point_type || row.intent_type || "functional").trim(),
    intent_type: String(row.intent_type || row.point_type || "functional").trim(),
    priority: String(row.priority || "P1").trim(),
    precondition: String(row.precondition || "").trim(),
    steps: stepTextList(row.steps).map((step) => ({
      action: "candidate_step",
      target: "",
      value: step,
      raw_text: step,
    })),
    raw_steps: asRecordList(row.steps),  // preserve original structured steps for machine instructions
    expected,
    expected_result: expected,
    involved_elements: normalizeInvolvedElements(row.involved_elements, page),
    review_status: reviewStatusValue(row),
    review_note: String(row.review_note || "").trim(),
    reviewed_at: String(row.reviewed_at || "").trim(),
    reviewed_by: String(row.reviewed_by || "").trim(),
  };
}

function coverageExplanationLabel(value: unknown): string {
  const normalized = String(value || "").trim();
  const labels: Record<string, string> = {
    "derived from test point traceability metadata": "由测试点追溯关系自动生成",
  };
  return labels[normalized.toLowerCase()] || text(value);
}

function sourceIdLabel(value: unknown, index: number): string {
  const normalized = String(value || "").trim();
  const matched = normalized.match(/^source-(\d+)$/i);
  if (matched) {
    return "手动输入";
  }
  return normalized ? `来源 ${index + 1}` : `来源 ${index + 1}`;
}

function sourceSummary(value: unknown): { label: string; tooltip: string } {
  const sourceIds = Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
  if (!sourceIds.length) {
    return { label: "未关联来源", tooltip: "" };
  }
  if (sourceIds.every((item) => /^source-\d+$/i.test(item))) {
    return {
      label: "手动输入",
      tooltip: `原始来源编号：${sourceIds.join(", ")}`,
    };
  }
  const labels = sourceIds.map((item, index) => sourceIdLabel(item, index));
  const label = labels.length === 1 ? labels[0] : `${labels[0]} 等 ${labels.length} 个来源`;
  return {
    label,
    tooltip: `原始来源编号：${sourceIds.join(", ")}`,
  };
}

function listText(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

const LOGIN_INVOLVED_ELEMENT_ALIASES: Record<string, string> = {
  "用户名输入框": "username_input",
  "账号输入框": "username_input",
  "用户名": "username_input",
  "账号": "username_input",
  "密码输入框": "password_input",
  "密码": "password_input",
  "登录按钮": "login_button",
  "登录": "login_button",
  "首页菜单": "home_menu",
  "首页": "home_menu",
  "工作台首页": "home_menu",
};

function normalizeInvolvedElements(value: unknown, page: unknown): string[] {
  const rows = listText(value);
  if (String(page || "").trim() !== "login") {
    return Array.from(new Set(rows));
  }
  const normalized: string[] = [];
  rows.forEach((row) => {
    const elementCode = LOGIN_INVOLVED_ELEMENT_ALIASES[row] || row;
    if (elementCode && !normalized.includes(elementCode)) {
      normalized.push(elementCode);
    }
  });
  return normalized;
}

function stepTextList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows: string[] = [];
  value.forEach((raw) => {
    if (typeof raw === "string") {
      const text = raw.trim();
      if (text) {
        rows.push(text);
      }
      return;
    }
    if (raw && typeof raw === "object") {
      const row = raw as Record<string, unknown>;
      const text = String(row.raw_text || row.value || row.description || row.action || "").trim();
      if (text) {
        rows.push(text);
      }
    }
  });
  return rows;
}

function formatRequirementText(value: string): string {
  return String(value || "")
    .replace(/\r\n/g, "\n")
    .replace(/\t/g, " ")
    .replace(/[ ]{2,}/g, " ")
    .replace(/\s*(业务目标：)/g, "\n$1")
    .replace(/\s*(关键流程：)/g, "\n\n$1\n")
    .replace(/\s*(验收点：)/g, "\n\n$1\n")
    .replace(/\s+(?=\d+\.\s)/g, "\n")
    .replace(/\s+-\s+/g, "\n- ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function requirementLineNode(line: string, index: number) {
  const normalized = String(line || "").trim();
  if (!normalized) {
    return <div key={`requirement-gap-${index}`} className="requirement-doc-gap" />;
  }
  const sectionMatch = normalized.match(/^(业务目标|关键流程|验收点)：\s*(.*)$/);
  if (sectionMatch) {
    const label = sectionMatch[1];
    const content = sectionMatch[2] || "";
    return (
      <div key={`requirement-section-${index}`} className="requirement-doc-section">
        <strong>{label}</strong>
        {content ? <span>{content}</span> : null}
      </div>
    );
  }
  const orderedMatch = normalized.match(/^(\d+)\.\s*(.*)$/);
  if (orderedMatch) {
    return (
      <div key={`requirement-step-${index}`} className="requirement-doc-item">
        <span className="requirement-doc-index">{orderedMatch[1]}</span>
        <span>{orderedMatch[2]}</span>
      </div>
    );
  }
  const bulletMatch = normalized.match(/^-\s*(.*)$/);
  if (bulletMatch) {
    return (
      <div key={`requirement-bullet-${index}`} className="requirement-doc-item">
        <span className="requirement-doc-dot" />
        <span>{bulletMatch[1]}</span>
      </div>
    );
  }
  return (
    <p key={`requirement-paragraph-${index}`} className="requirement-doc-paragraph">
      {normalized}
    </p>
  );
}

function pointRows(item: Record<string, unknown>): Array<Record<string, unknown>> {
  const plan = (item.plan || {}) as Record<string, unknown>;
  const page = item.page || plan.page;
  const points = Array.isArray(plan.points) ? plan.points : [];
  if (points.length) {
    return points
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .map((point) => {
        const snapshot = ((point.metadata as Record<string, unknown> | undefined)?.candidate_snapshot || {}) as Record<string, unknown>;
        const pointSteps = stepTextList(point.steps);
        const pointElements = normalizeInvolvedElements(point.involved_elements, page);
        // 详情页必须以 plan.points 为唯一事实源，旧 snapshot 只在字段缺失时兜底展示。
        return {
          key: String(point.key || snapshot.key || point.intent_id || snapshot.intent_id || "").trim(),
          intent_id: String(point.intent_id || point.key || snapshot.intent_id || "").trim(),
          title: String(point.title || point.summary || point.description || snapshot.title || snapshot.summary || point.intent_id || "").trim(),
          summary: String(point.summary || point.description || snapshot.summary || snapshot.title || "").trim(),
          intent_type: String(point.intent_type || point.point_type || snapshot.intent_type || "functional").trim(),
          point_type: String(point.point_type || point.intent_type || snapshot.intent_type || "functional").trim(),
          priority: String(point.priority || snapshot.priority || "P1").trim(),
          precondition: String(point.precondition || snapshot.precondition || "").trim(),
          steps: pointSteps.length ? pointSteps : stepTextList(snapshot.steps),
          raw_steps: asRecordList(point.steps),  // machine instructions
          expected: String(point.expected || point.expected_result || snapshot.expected || "").trim(),
          expected_result: String(point.expected_result || point.expected || snapshot.expected || "").trim(),
          involved_elements: pointElements.length ? pointElements : normalizeInvolvedElements(snapshot.involved_elements, page),
          review_status: String(point.review_status || snapshot.review_status || "").trim(),
          review_note: String(point.review_note || snapshot.review_note || "").trim(),
          reviewed_at: String(point.reviewed_at || snapshot.reviewed_at || "").trim(),
          reviewed_by: String(point.reviewed_by || snapshot.reviewed_by || "").trim(),
          gate_issues: (() => {
            const issues: string[] = [];
            if (!point.has_assertion) issues.push("零断言");
            if (point.has_candidate_step) issues.push("含未结构化步骤");
            if (Number(point.warning_count || 0) > 0) issues.push(`${point.warning_count}个警告`);
            return issues;
          })(),
        };
      });
  }
  const metadata = (plan.metadata || {}) as Record<string, unknown>;
  const candidates = Array.isArray(metadata.selected_candidates) ? metadata.selected_candidates : [];
  return candidates
    .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
    .map((row) => ({ ...row, involved_elements: normalizeInvolvedElements(row.involved_elements, page) }));
}

export function TestPointAssetDetailPage() {
  const params = useParams<{ assetId: string }>();
  const location = useLocation();
  const assetId = String(params.assetId || "").trim();
  const project = useMemo(() => {
    const query = new URLSearchParams(location.search);
    return normalizeProjectCode(query.get("project"));
  }, [location.search]);
  const showMatrixOnly = useMemo(() => location.pathname.endsWith("/matrix"), [location.pathname]);
  const [item, setItem] = useState<Record<string, unknown>>({});
  const [matrix, setMatrix] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [actionText, setActionText] = useState<string>("");
  const [floatingTooltip, setFloatingTooltip] = useState<{ content: string; x: number; y: number } | null>(null);
  const [requirementExpanded, setRequirementExpanded] = useState<boolean>(false);
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string>("");
  const [detailPage, setDetailPage] = useState<number>(1);
  const [detailPageSize, setDetailPageSize] = useState<number>(10);
  const [selectedPointIds, setSelectedPointIds] = useState<string[]>([]);
  const [pointDeleteTarget, setPointDeleteTarget] = useState<{ mode: "single" | "batch"; pointId?: string; title?: string } | null>(null);
  const [pointReviewTarget, setPointReviewTarget] = useState<{ mode: "single" | "batch"; status: PointReviewStatus; pointId?: string; title?: string } | null>(null);
  const [reviewNote, setReviewNote] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!assetId) {
        setErrorText("缺少 asset_id");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorText("");
      setActionText("");
      setRequirementExpanded(false);
      try {
        const [detailPayload, matrixPayload] = await Promise.all([
          getTestPointAsset(assetId, project),
          getTestPointAssetCoverageMatrix(assetId, project),
        ]);
        if (!cancelled) {
          setItem((detailPayload.item || {}) as Record<string, unknown>);
          setMatrix((matrixPayload.item || {}) as Record<string, unknown>);
          setSelectedPointIds([]);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "测试点资产详情加载失败");
          setItem({});
          setMatrix({});
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [assetId, project]);

  useEffect(() => {
    setDetailPage(1);
  }, [typeFilter, priorityFilter, reviewStatusFilter, detailPageSize]);

  const rows = Array.isArray(matrix.rows) ? matrix.rows : [];
  const summary = (matrix.summary || {}) as Record<string, unknown>;
  const detailRows = pointRows(item);
  const typeOptions = useMemo(
    () => optionCounts(
      detailRows,
      "intent_type",
      intentTypeLabel,
      (left, right) => intentTypeLabel(left).localeCompare(intentTypeLabel(right), "zh-Hans-CN"),
    ),
    [detailRows],
  );
  const priorityOptions = useMemo(
    () => optionCounts(
      detailRows,
      "priority",
      (value) => String(value || "").trim().toUpperCase() || "-",
      (left, right) => priorityRank(left) - priorityRank(right),
    ),
    [detailRows],
  );
  const reviewOptions = useMemo(() => reviewStatusOptions(detailRows), [detailRows]);
  const pointReviewCounts = useMemo(() => reviewCounts(detailRows), [detailRows]);
  const filteredDetailRows = useMemo(
    () => detailRows.filter((row) => {
      const rowType = String(row.intent_type || "").trim();
      const rowPriority = String(row.priority || "").trim();
      const rowReviewStatus = reviewStatusValue(row);
      return (!typeFilter || rowType === typeFilter)
        && (!priorityFilter || rowPriority === priorityFilter)
        && (!reviewStatusFilter || rowReviewStatus === reviewStatusFilter);
    }),
    [detailRows, priorityFilter, reviewStatusFilter, typeFilter],
  );
  const detailTotalPages = Math.max(1, Math.ceil(filteredDetailRows.length / Math.max(1, detailPageSize)));
  const safeDetailPage = Math.min(Math.max(1, detailPage), detailTotalPages);
  const pagedDetailRows = filteredDetailRows.slice((safeDetailPage - 1) * detailPageSize, safeDetailPage * detailPageSize);
  const pagedPointIds = pagedDetailRows.map(pointIdOf).filter(Boolean);
  const allPagedPointsSelected = Boolean(pagedPointIds.length && pagedPointIds.every((pointId) => selectedPointIds.includes(pointId)));
  const selectedPointCount = selectedPointIds.length;
  const pendingDeletePointIds = pointDeleteTarget?.mode === "batch"
    ? selectedPointIds
    : [pointDeleteTarget?.pointId || ""].filter(Boolean);
  const pendingReviewPointIds = pointReviewTarget?.mode === "batch"
    ? selectedPointIds
    : [pointReviewTarget?.pointId || ""].filter(Boolean);
  const requirementText = listText(item.requirement).join("\n");
  const formattedRequirementText = formatRequirementText(requirementText);
  const requirementLines = formattedRequirementText ? formattedRequirementText.split("\n") : [];
  const requirementPreviewLines = requirementLines.filter((line) => line.trim()).slice(0, 3);
  const visibleRequirementLines = requirementExpanded ? requirementLines : requirementPreviewLines;
  const hasRequirementOverflow = requirementLines.filter((line) => line.trim()).length > requirementPreviewLines.length;
  const sourceBadge = sourceBadgeConfig(item);
  const statusBadge = statusBadgeConfig(item);
  const assetReviewBadge = assetReviewBadgeConfig(pointReviewCounts, statusBadge);
  const generationDiagnostics = (item.generation_diagnostics || {}) as Record<string, unknown>;
  const missingGeneratedPoints = asRecordList(generationDiagnostics.missing);
  const duplicateGeneratedPoints = asRecordList(generationDiagnostics.duplicates);
  const hasGenerationIssues = missingGeneratedPoints.length > 0 || duplicateGeneratedPoints.length > 0;
  const generationFailuresLink = `/cases/generation-failures?project=${encodeURIComponent(project)}&asset_id=${encodeURIComponent(assetId)}`;

  function showFloatingTooltip(target: HTMLElement, content: string) {
    const normalized = String(content || "").trim();
    if (!normalized) {
      setFloatingTooltip(null);
      return;
    }
    const rect = target.getBoundingClientRect();
    const viewportWidth = window.innerWidth || 360;
    const x = Math.min(Math.max(rect.left + rect.width / 2, 180), Math.max(180, viewportWidth - 180));
    setFloatingTooltip({
      content: normalized,
      x,
      y: rect.bottom + 10,
    });
  }

  function showTooltipFromEvent(event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>, content: string) {
    showFloatingTooltip(event.currentTarget, content);
  }

  function togglePoint(pointId: string) {
    if (!pointId || busy) {
      return;
    }
    setSelectedPointIds((prev) => (prev.includes(pointId) ? prev.filter((item) => item !== pointId) : [...prev, pointId]));
  }

  function togglePagedPoints() {
    if (busy || !pagedPointIds.length) {
      return;
    }
    setSelectedPointIds((prev) => {
      if (pagedPointIds.every((pointId) => prev.includes(pointId))) {
        return prev.filter((pointId) => !pagedPointIds.includes(pointId));
      }
      return Array.from(new Set([...prev, ...pagedPointIds]));
    });
  }

  async function removePoints(pointIds: string[]) {
    const normalizedIds = pointIds.map((pointId) => String(pointId || "").trim()).filter(Boolean);
    if (!normalizedIds.length) {
      setPointDeleteTarget(null);
      return;
    }
    const remainingRows = detailRows.filter((row) => !normalizedIds.includes(pointIdOf(row)));
    if (!remainingRows.length) {
      setErrorText("至少需要保留一条测试点，不能删除全部明细。");
      setPointDeleteTarget(null);
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      await updateTestPointAsset(assetId, {
        project,
        asset_id: assetId,
        page: text(item.page),
        title: text(item.title) || assetId,
        priority: text(item.priority) || "P1",
        requirement: requirementText || text(item.title) || assetId,
        source_type: text(item.source_type) || "manual",
        points: remainingRows.map((row) => candidatePayloadFromRow(row, item.page)),
      });
      const [detailPayload, matrixPayload] = await Promise.all([
        getTestPointAsset(assetId, project),
        getTestPointAssetCoverageMatrix(assetId, project),
      ]);
      setItem((detailPayload.item || {}) as Record<string, unknown>);
      setMatrix((matrixPayload.item || {}) as Record<string, unknown>);
      setSelectedPointIds([]);
      setPointDeleteTarget(null);
      setActionText(`已删除 ${normalizedIds.length} 条测试点明细。`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "删除测试点明细失败");
    } finally {
      setBusy(false);
    }
  }

  async function reviewPoints(pointIds: string[], nextStatus: PointReviewStatus, note = "") {
    const normalizedIds = pointIds.map((pointId) => String(pointId || "").trim()).filter(Boolean);
    if (!normalizedIds.length) {
      setPointReviewTarget(null);
      return;
    }
    const normalizedNote = String(note || "").trim();
    if (nextStatus === "rejected" && !normalizedNote) {
      setErrorText("驳回测试点时必须填写驳回原因。");
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      await batchReviewTestPoints({
        project,
        decisions: normalizedIds.map((intentId) => ({ asset_id: assetId, intent_id: intentId })),
        status: nextStatus,
        note: normalizedNote,
        reviewed_by: "admin",
      });
      const [detailPayload, matrixPayload] = await Promise.all([
        getTestPointAsset(assetId, project),
        getTestPointAssetCoverageMatrix(assetId, project),
      ]);
      setItem((detailPayload.item || {}) as Record<string, unknown>);
      setMatrix((matrixPayload.item || {}) as Record<string, unknown>);
      setSelectedPointIds([]);
      setPointReviewTarget(null);
      setReviewNote("");
      setActionText(`已${nextStatus === "approved" ? "通过" : "驳回"} ${normalizedIds.length} 条测试点。`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "审核测试点失败");
    } finally {
      setBusy(false);
    }
  }

  async function generateApprovedCases() {
    if (!assetId || busy) {
      return;
    }
    setBusy(true);
    setErrorText("");
    setActionText("");
    try {
      const response = await batchGenerateCasesFromTestPointAssets({
        project,
        asset_ids: [assetId],
        source: "ai",
      });
      setActionText(buildGenerationFeedback(response as Record<string, unknown>));
      const [detailPayload, matrixPayload] = await Promise.all([
        getTestPointAsset(assetId, project),
        getTestPointAssetCoverageMatrix(assetId, project),
      ]);
      setItem((detailPayload.item || {}) as Record<string, unknown>);
      setMatrix((matrixPayload.item || {}) as Record<string, unknown>);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "生成已通过用例失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page shell detail-page detail-page--asset">
      <header className="detail-toolbar">
        <div className="detail-toolbar-main">
          <h1>测试点资产详情</h1>
        </div>
        <div className="detail-toolbar-actions">
          <button type="button" className="button" onClick={() => void generateApprovedCases()} disabled={busy || pointReviewCounts.approved <= 0}>
            生成已通过用例
          </button>
          <Link className="button secondary" to={`/cases?project=${encodeURIComponent(project)}`}>
            用例中心
          </Link>
          <Link className="button" to={`/assets/test-points/${encodeURIComponent(assetId)}/edit?project=${encodeURIComponent(project)}`}>
            编辑资产
          </Link>
          <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(project)}`}>
            返回资产列表
          </Link>
        </div>
      </header>

      {loading ? <section className="panel">正在加载资产详情...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {actionText ? <section className="panel">{actionText}</section> : null}

      {!loading && !errorText && !showMatrixOnly ? (
        <section className="detail-hero asset-detail-panel">
          <div className="asset-summary-strip detail-field-grid" aria-label="资产基础信息">
            <div className="asset-summary-item asset-summary-primary detail-field detail-field--wide">
              <span className="detail-field-label">标题</span>
              <strong className="detail-field-value">{text(item.title)}</strong>
            </div>
            <div className="asset-summary-item detail-field detail-field--wide">
              <span className="detail-field-label">资产编码</span>
              <strong className="detail-field-value detail-mono">{text(item.asset_id)}</strong>
            </div>
            <div className="asset-summary-item detail-field">
              <span className="detail-field-label">页面</span>
              <strong className="detail-field-value">{text(item.page)}</strong>
            </div>
            <div className="asset-summary-item detail-field">
              <span className="detail-field-label">优先级</span>
              <strong className="detail-field-value">{text(item.priority)}</strong>
            </div>
            <div className="asset-summary-item detail-field">
              <span className="detail-field-label">来源</span>
              <strong className="detail-field-value">
                <span className={`asset-state-badge asset-state-${sourceBadge.tone}`} title={sourceBadge.raw || sourceBadge.label}>
                  {sourceBadge.label}
                </span>
              </strong>
            </div>
            <div className="asset-summary-item detail-field">
              <span className="detail-field-label">点位数</span>
              <strong className="detail-field-value">{numberValue(item.point_count)}</strong>
              <small className="detail-field-help">可维护测试点</small>
            </div>
            <div className="asset-summary-item detail-field">
              <span className="detail-field-label">置信度</span>
              <strong className="detail-field-value">{numberValue(item.confidence)}</strong>
              <small className="detail-field-help">AI 解析参考值</small>
            </div>
            <div className="asset-summary-item asset-summary-muted detail-field">
              <span className="detail-field-label">状态</span>
              <strong className="detail-field-value">
                <span className={`asset-state-badge asset-state-${assetReviewBadge.tone}`} title={assetReviewBadge.raw || assetReviewBadge.label}>
                  {assetReviewBadge.label}
                </span>
              </strong>
              {assetReviewBadge.hint ? <small className="detail-field-help">{assetReviewBadge.hint}</small> : null}
            </div>
          </div>
          <QualityGateCard report={(item.quality_report || {}) as Record<string, unknown>} />
          {(() => {
            const qr = (item.quality_report || {}) as Record<string, unknown>;
            const perPoint = Array.isArray(qr.per_point) ? (qr.per_point as Array<Record<string, unknown>>) : [];
            const problemPoints = perPoint.filter((p) => !p.has_assertion || p.has_candidate_step);
            if (!problemPoints.length) return null;
            const editUrl = `/react/assets/test-points/${encodeURIComponent(assetId)}/edit?project=${encodeURIComponent(project)}`;
            return (
              <div className="panel point-quality-summary">
                <strong>需修复 ({problemPoints.length})</strong>
                <div className="detail-field-row">
                  {problemPoints.slice(0, 5).map((p) => (
                    <span key={String(p.intent_id)} className="tag tag--warning">
                      {String(p.intent_id)}: {!p.has_assertion ? "零断言" : ""}{p.has_candidate_step ? "占位步骤" : ""}
                    </span>
                  ))}
                  {problemPoints.length > 5 ? <span>...及其他 {problemPoints.length - 5} 个</span> : null}
                </div>
                <Link className="button secondary" to={editUrl}>编辑资产修复</Link>
              </div>
            );
          })()}
          <div className={`asset-review-banner asset-review-${assetReviewBadge.tone}`}>
            <strong>{assetReviewBadge.label}</strong>
            <span>
              共 {pointReviewCounts.total} 条测试点，已通过 {pointReviewCounts.approved} 条，已驳回 {pointReviewCounts.rejected} 条，待审核 {pointReviewCounts.pending} 条。
            </span>
          </div>
          {hasGenerationIssues ? (
            <div className="asset-generation-diagnostics-panel">
              <div className="asset-generation-diagnostics-header">
                <div>
                  <strong>生成覆盖诊断</strong>
                  <span>
                    已通过 {numberValue(generationDiagnostics.approved_intent_count)} 条，已生成覆盖 {numberValue(generationDiagnostics.generated_unique_intent_count)} 条；
                    未生成 {missingGeneratedPoints.length} 条，重复 {duplicateGeneratedPoints.length} 组。
                  </span>
                </div>
                <Link className="button secondary" to={`/cases?project=${encodeURIComponent(project)}&source_asset=${encodeURIComponent(assetId)}`}>
                  去用例中心处理
                </Link>
                <Link className="button secondary" to={generationFailuresLink}>
                  查看失败明细
                </Link>
              </div>
              {missingGeneratedPoints.length ? (
                <div className="asset-generation-diagnostics-block">
                  <h3>编译失败 / 未生成的已通过测试点</h3>
                  <table className="detail-table detail-table--compact">
                    <thead>
                      <tr>
                        <th>intent_id</th>
                        <th>标题</th>
                        <th>失败类型</th>
                        <th>原因与建议</th>
                      </tr>
                    </thead>
                    <tbody>
                      {missingGeneratedPoints.map((row, index) => (
                        <tr key={`missing-${String(row.intent_id || index)}`}>
                          <td className="mono">{text(row.intent_id)}</td>
                          <td>{text(row.title)}</td>
                          <td>{text(row.failure_type || row.failure_stage || row.reason)}</td>
                          <td>
                            <strong>{text(row.message || row.reason)}</strong>
                            {text(row.suggestion) !== "-" ? <p className="muted">{text(row.suggestion)}</p> : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {duplicateGeneratedPoints.length ? (
                <div className="asset-generation-diagnostics-block">
                  <h3>重复生成项</h3>
                  <table className="detail-table detail-table--compact">
                    <thead>
                      <tr>
                        <th>intent_id</th>
                        <th>标题</th>
                        <th>重复 case_id</th>
                        <th>建议</th>
                      </tr>
                    </thead>
                    <tbody>
                      {duplicateGeneratedPoints.map((row, index) => {
                        const caseIds = Array.isArray(row.case_ids)
                          ? row.case_ids.map((caseId) => String(caseId || "").trim()).filter(Boolean)
                          : [];
                        return (
                          <tr key={`duplicate-${String(row.intent_id || index)}`}>
                            <td className="mono">{text(row.intent_id)}</td>
                            <td>{text(row.title)}</td>
                            <td className="mono">{caseIds.length ? caseIds.join(", ") : "-"}</td>
                            <td>{text(row.message)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="asset-generation-diagnostics-panel asset-generation-diagnostics-panel--ok">
              <strong>生成覆盖诊断</strong>
              <span>当前未发现已通过测试点未生成或重复生成项。</span>
            </div>
          )}
          <div className="asset-requirement-panel">
            <div className="asset-requirement-header">
              <div>
                <p className="asset-requirement-label">
                  <strong>需求原文</strong>
                </p>
                <span className="asset-requirement-help">默认展示前 3 行，展开后查看完整业务目标、关键流程和验收点。</span>
              </div>
              {hasRequirementOverflow ? (
                <button type="button" className="requirement-toggle-button" onClick={() => setRequirementExpanded((value) => !value)}>
                  {requirementExpanded ? "收起" : "展开全部"}
                </button>
              ) : null}
            </div>
            <div className={`requirement-doc ${requirementExpanded ? "" : "requirement-doc-preview"}`}>
              {visibleRequirementLines.length ? visibleRequirementLines.map(requirementLineNode) : "-"}
            </div>
          </div>
        </section>
      ) : null}

      {!loading && !errorText && !showMatrixOnly ? (
        <DataTable
          title="测试点明细（与候选预览对齐）"
          actions={(
            <span className="muted">
              共 {detailRows.length} 条，当前 {filteredDetailRows.length} 条
            </span>
          )}
        >
          <table className="test-point-detail-table detail-table detail-table--asset-points">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={allPagedPointsSelected}
                    disabled={busy || !pagedPointIds.length}
                    aria-label="选择当前页测试点"
                    onChange={togglePagedPoints}
                  />
                </th>
                <th>intent_id</th>
                <th>标题</th>
                <th>
                  <ColumnFilter label="类型" value={typeFilter} options={typeOptions} onChange={setTypeFilter} />
                </th>
                <th>
                  <ColumnFilter label="优先级" value={priorityFilter} options={priorityOptions} onChange={setPriorityFilter} />
                </th>
                <th>
                  <ColumnFilter label="审核状态" value={reviewStatusFilter} options={reviewOptions} onChange={setReviewStatusFilter} />
                </th>
                <th>前置条件</th>
                <th>步骤</th>
                <th>预期结果</th>
                <th>机器指令</th>
                <th>Gate</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {pagedDetailRows.length ? (
                pagedDetailRows.map((row, index) => {
                  const steps = stepTextList(row.steps);
                  const sourceSteps = asRecordList(row.raw_steps).length ? asRecordList(row.raw_steps) : asRecordList(row.steps);
                  const instructions = sourceSteps.map((s) => {
                    const action = text(s.action);
                    const target = text(s.target).replace("element:", "");
                    const value = s.value != null ? String(s.value) : "";
                    if (action === "goto" || action === "assert_url") return `${action}:${value}`;
                    if (action === "assert_text" || action === "assert_visible") return `${action}:${target}=${value}`;
                    if (action === "assert_attribute") return `${action}:${target}.${text(s.attribute)}=${value}`;
                    if (value) return `${action}:${target}=${value}`;
                    return `${action}:${target}`;
                  });
                  const pointId = pointIdOf(row);
                  return (
                    <tr key={`${pointId || index}-${index}`}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedPointIds.includes(pointId)}
                          disabled={busy || !pointId}
                          aria-label={`选择测试点 ${pointId || index + 1}`}
                          onChange={() => togglePoint(pointId)}
                        />
                      </td>
                      <td className="mono">{text(row.intent_id)}</td>
                      <td>{text(row.title || row.summary)}</td>
                      <td>
                        <span className={`intent-type-badge ${intentTypeClass(row.intent_type)}`}>
                          {intentTypeLabel(row.intent_type)}
                        </span>
                      </td>
                      <td>
                        <span className={`priority-badge ${priorityClass(row.priority)}`}>
                          {text(row.priority)}
                        </span>
                      </td>
                      <td>
                        <span className={`review-status-badge ${reviewStatusClass(reviewStatusValue(row))}`} title={String(row.review_note || "")}>
                          {reviewStatusLabel(reviewStatusValue(row))}
                        </span>
                      </td>
                      <td>{text(row.precondition)}</td>
                      <td>{steps.length ? steps.join(" / ") : "-"}</td>
                      <td>{text(row.expected)}</td>
                      <td className="mono" style={{ fontSize: "0.8rem", lineHeight: "1.4" }}>
                        {instructions.length
                          ? instructions.map((inst, i) => <div key={i}>{inst}</div>)
                          : "-"}
                      </td>
                      <td>
                        {Array.isArray(row.gate_issues) && (row.gate_issues as string[]).length
                          ? (row.gate_issues as string[]).map((issue, i) => (
                              <span key={i} className="gate-issue-tag" style={{
                                display: "inline-block", background: "#fff3cd", color: "#856404",
                                padding: "1px 6px", borderRadius: "3px", fontSize: "0.75rem",
                                marginRight: "4px", marginBottom: "2px"
                              }}>{issue}</span>
                            ))
                          : <span style={{ color: "#28a745", fontSize: "0.8rem" }}>✅</span>}
                      </td>
                      <td>
                        <div className="table-row-actions">
                          <button
                            type="button"
                            className="link-button success-text"
                            disabled={busy || !pointId || reviewStatusValue(row) === "approved"}
                            onClick={() => {
                              setReviewNote("");
                              setPointReviewTarget({ mode: "single", pointId, status: "approved", title: text(row.title || row.summary) });
                            }}
                          >
                            通过
                          </button>
                          <button
                            type="button"
                            className="link-button danger-text"
                            disabled={busy || !pointId}
                            onClick={() => {
                              setReviewNote(String(row.review_note || ""));
                              setPointReviewTarget({ mode: "single", pointId, status: "rejected", title: text(row.title || row.summary) });
                            }}
                          >
                            驳回
                          </button>
                          <button
                            type="button"
                            className="link-button danger-text"
                            disabled={busy || !pointId}
                            onClick={() => setPointDeleteTarget({ mode: "single", pointId, title: text(row.title || row.summary) })}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={11}>
                    <EmptyState
                      title={detailRows.length ? "当前筛选下暂无测试点" : "暂无测试点明细"}
                      description={detailRows.length ? "请调整类型、优先级或审核状态筛选条件后再查看。" : "当前资产还没有保存完整测试点明细，请回到测试点资产页检查生成结果。"}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {selectedPointCount ? (
            <BulkActionBar selectedCount={selectedPointCount}>
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => {
                  setReviewNote("");
                  setPointReviewTarget({ mode: "batch", status: "approved" });
                }}
              >
                批量通过
              </button>
              <button
                type="button"
                className="button danger secondary"
                disabled={busy}
                onClick={() => {
                  setReviewNote("");
                  setPointReviewTarget({ mode: "batch", status: "rejected" });
                }}
              >
                批量驳回
              </button>
              <button type="button" className="button danger secondary" disabled={busy} onClick={() => setPointDeleteTarget({ mode: "batch" })}>
                批量删除
              </button>
            </BulkActionBar>
          ) : null}
          {detailRows.length ? (
            <TablePagination
              page={safeDetailPage}
              pageSize={detailPageSize}
              total={filteredDetailRows.length}
              onPageChange={setDetailPage}
              onPageSizeChange={setDetailPageSize}
            />
          ) : null}
        </DataTable>
      ) : null}

      {!loading && !errorText ? (
        <DataTable
          title="覆盖矩阵"
          actions={(
            <span className="muted">
              {traceabilityStatusLabel(summary.status)} ｜ 已覆盖 {numberValue(summary.covered_count)} ｜ 部分覆盖 {numberValue(summary.partial_count)} ｜ 缺口
              {numberValue(summary.gap_count)} ｜ 待关联 {numberValue(summary.orphan_count)}
            </span>
          )}
        >
          <table className="coverage-matrix-table detail-table detail-table--coverage">
            <thead>
              <tr>
                <th>追溯状态</th>
                <th>来源</th>
                <th>覆盖意图数</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((row, index) => {
                  const rowSource = sourceSummary(row.source_ids);
                  const intentIds = Array.isArray(row.intent_ids)
                    ? row.intent_ids.map((intentId: unknown) => String(intentId || "").trim()).filter(Boolean)
                    : [];
                  const intentTooltip = intentIds.join(", ");
                  const statusClass = String(row.traceability_status || "unknown").trim().toLowerCase() || "unknown";
                  return (
                    <tr key={String(row.row_id || index)}>
                      <td>
                        <span className={`coverage-status-badge status-${statusClass}`}>
                          {traceabilityStatusLabel(row.traceability_status)}
                        </span>
                      </td>
                      <td>
                        <span
                          className="coverage-source-label"
                          tabIndex={rowSource.tooltip ? 0 : undefined}
                          onMouseEnter={(event) => showTooltipFromEvent(event, rowSource.tooltip)}
                          onMouseLeave={() => setFloatingTooltip(null)}
                          onFocus={(event) => showTooltipFromEvent(event, rowSource.tooltip)}
                          onBlur={() => setFloatingTooltip(null)}
                        >
                          {rowSource.label}
                        </span>
                      </td>
                      <td>
                        <span
                          className="coverage-intent-count"
                          tabIndex={intentTooltip ? 0 : undefined}
                          aria-label={intentTooltip ? `覆盖的意图：${intentTooltip}` : undefined}
                          onMouseEnter={(event) => showTooltipFromEvent(event, intentTooltip)}
                          onMouseLeave={() => setFloatingTooltip(null)}
                          onFocus={(event) => showTooltipFromEvent(event, intentTooltip)}
                          onBlur={() => setFloatingTooltip(null)}
                        >
                          {intentIds.length} 个意图
                        </span>
                      </td>
                      <td>{coverageExplanationLabel(row.explanation)}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={4}>
                    <EmptyState title="暂无覆盖矩阵数据" description="生成或同步测试点资产后，覆盖矩阵会展示测试点与来源意图的追溯关系。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTable>
      ) : null}
      {floatingTooltip ? (
        <div className="floating-tooltip" style={{ left: floatingTooltip.x, top: floatingTooltip.y }}>
          {floatingTooltip.content}
        </div>
      ) : null}
      {pointDeleteTarget ? (
        <ConfirmDialog
          title={pointDeleteTarget.mode === "batch" ? "确认批量删除测试点" : "确认删除测试点"}
          description="删除后会更新当前测试点资产内的完整明细，请确认这些测试点不再需要继续维护或生成用例。"
          confirmText="确认删除"
          danger
          busy={busy}
          details={
            pointDeleteTarget.mode === "batch"
              ? [`将删除 ${pendingDeletePointIds.length} 条测试点`, "资产内至少需要保留 1 条测试点"]
              : [`测试点：${pointDeleteTarget.title || pointDeleteTarget.pointId || "-"}`, "资产内至少需要保留 1 条测试点"]
          }
          onCancel={() => setPointDeleteTarget(null)}
          onConfirm={() => void removePoints(pendingDeletePointIds)}
        />
      ) : null}
      {pointReviewTarget ? (
        <ConfirmDialog
          title={pointReviewTarget.status === "approved" ? "确认通过测试点" : "确认驳回测试点"}
          description={
            pointReviewTarget.status === "approved"
              ? "通过后，这些测试点可作为后续生成用例的有效输入。"
              : "驳回后，这些测试点需要修改后再重新审核。"
          }
          confirmText={pointReviewTarget.status === "approved" ? "确认通过" : "确认驳回"}
          danger={pointReviewTarget.status === "rejected"}
          busy={busy}
          details={
            pointReviewTarget.mode === "batch"
              ? [`将处理 ${pendingReviewPointIds.length} 条测试点`, pointReviewTarget.status === "approved" ? "批量通过所选测试点" : "批量驳回所选测试点"]
              : [`测试点：${pointReviewTarget.title || pointReviewTarget.pointId || "-"}`]
          }
          noteLabel={pointReviewTarget.status === "rejected" ? "驳回原因" : undefined}
          noteValue={reviewNote}
          notePlaceholder="请说明驳回原因，便于后续修改"
          noteRequired={pointReviewTarget.status === "rejected"}
          onNoteChange={setReviewNote}
          onCancel={() => {
            setPointReviewTarget(null);
            setReviewNote("");
          }}
          onConfirm={() => void reviewPoints(pendingReviewPointIds, pointReviewTarget.status, reviewNote)}
        />
      ) : null}
    </main>
  );
}
