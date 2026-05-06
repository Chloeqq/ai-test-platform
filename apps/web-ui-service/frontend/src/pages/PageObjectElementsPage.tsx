import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  batchDeleteCandidateElements,
  batchDeleteCandidateGroups,
  batchDeletePageElements,
  batchDeleteRecorderSessions,
  getCandidateGroup,
  getPageElement,
  getPageObject,
  getRecorderSessionPlayback,
  listPageElementVersions,
  listCandidateGroups,
  listPageElements,
  listPageObjectRefs,
  listRecorderSessions,
  mergeCandidateGroup,
  promoteCandidateGroup,
  rejectCandidateElement,
  rejectCandidateGroup,
  updatePageElement,
} from "../api/assets";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FilterBar } from "../components/FilterBar";
import { CandidateGroupDetailTable, CandidateGroupsTable, FormalElementsTable, RecorderHistoryTable } from "./PageObjectElementsTables";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

type TabId = "formal" | "candidates" | "history";
type ElementPanelMode = "detail" | "semantic" | "aliases" | "locators" | "refs";

interface PromoteForm {
  element_code: string;
  element_name: string;
  business_type: string;
  business_domain: string;
  is_key_element: boolean;
  locator_type: string;
  locator_value: string;
  role: string;
  locator_source: string;
  route_scope: string;
  testid_value: string;
  qa_value: string;
  governance_note: string;
  operator: string;
}

interface SemanticForm {
  element_code: string;
  element_name: string;
  business_type: string;
  business_domain: string;
  locator_source: string;
  match_strategy: string;
  stability_level: string;
  review_status: string;
  status: string;
  is_key_element: boolean;
  anchor_required: boolean;
  testid_value: string;
  qa_value: string;
  route_scope: string;
  governance_note: string;
}

interface AliasForm {
  aliases_text: string;
  semantic_tags_text: string;
}

const PAGE_OBJECT_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  review: "评审中",
  published: "已发布",
  retired: "已下线",
};

const PAGE_OBJECT_GOVERNANCE_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  active: "已可用",
  approved: "已通过",
  governing: "治理中",
  pending: "待审核",
  needs_review: "待审核",
  rejected: "已驳回",
  retired: "已下线",
};

const PAGE_NAME_LABELS: Record<string, string> = {
  home: "首页",
  login: "登录页",
  order: "订单页",
  payment: "支付页",
  permission: "权限页",
  product: "商品页",
  profile: "个人中心",
};

const PAGE_ELEMENT_STATUS_LABELS: Record<string, string> = {
  active: "启用",
  inactive: "停用",
  deprecated: "废弃",
};

const REVIEW_STATUS_LABELS: Record<string, string> = {
  approved: "已审核",
  pending: "待审核",
  rejected: "已拒绝",
};

const STABILITY_LABELS: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

const RECOMMENDED_ACTION_LABELS: Record<string, string> = {
  promote: "建议提升",
  ingest: "建议提升",
  review: "建议复核",
  skip: "建议跳过",
};

const CANDIDATE_STATUS_LABELS: Record<string, string> = {
  pending: "待审核",
  reviewed: "已查看",
  promoted: "已提升",
  rejected: "已拒绝",
  merged: "已合并",
};

const PROMOTION_STATUS_LABELS: Record<string, string> = {
  pending: "待审核",
  partially_promoted: "部分处理",
  promoted: "已处理",
  rejected: "已拒绝",
};

const RECORDER_STATUS_LABELS: Record<string, string> = {
  active: "录制中",
  stopped: "已停止",
  failed: "失败",
};

const BUSINESS_TYPES = [
  "input",
  "button",
  "link",
  "menu",
  "tab",
  "switch",
  "checkbox",
  "radio",
  "dialog",
  "table",
  "container",
  "metric_label",
  "metric_value",
  "password_toggle",
];

const BUSINESS_DOMAINS = ["auth", "navigation", "dashboard", "search", "table", "form", "detail", "common"];
const LOCATOR_SOURCES = ["testid", "qa", "role_name", "placeholder", "id", "name", "css", "xpath", "manual"];
const MATCH_STRATEGIES = ["exact", "alias", "derived", "composite"];
const STABILITY_LEVELS = ["high", "medium", "low"];
const REVIEW_STATUSES = ["approved", "pending", "rejected"];
const ELEMENT_STATUSES = ["active", "inactive", "deprecated"];
const STRICT_ELEMENT_CODE_NOISE_TOKENS = new Set(["css", "xpath", "path", "index", "idx", "nth", "button1", "input1", "icon1", "div", "span", "el", "node", "temp", "tmp", "locator"]);
const SUGGESTION_ELEMENT_CODE_NOISE_TOKENS = new Set([...STRICT_ELEMENT_CODE_NOISE_TOKENS, "role", "text"]);

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function pageDisplayName(pageObject: Record<string, unknown>): string {
  const pageCode = String(pageObject.page_code || "").trim().toLowerCase();
  const pageName = String(pageObject.page_name || "").trim();
  const normalizedPageName = pageName.toLowerCase();
  if (pageName && pageName !== pageCode && !PAGE_NAME_LABELS[normalizedPageName]) {
    return pageName;
  }
  return PAGE_NAME_LABELS[pageCode] || PAGE_NAME_LABELS[normalizedPageName] || text(pageName || pageCode);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }
  const raw = String(value || "").trim();
  if (!raw) {
    return [];
  }
  return raw.split(/[\n,，]/u).map((item) => item.trim()).filter(Boolean);
}

function numberOf(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(String(value || "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentValue(value: unknown): number {
  return Math.max(0, Math.min(100, Math.round(numberOf(value))));
}

function scoreTone(value: unknown): "good" | "warn" | "bad" {
  const score = percentValue(value);
  if (score >= 80) {
    return "good";
  }
  if (score >= 60) {
    return "warn";
  }
  return "bad";
}

function qualityTone(value: unknown): "good" | "ok" | "warn" | "bad" {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "A") {
    return "good";
  }
  if (normalized === "B") {
    return "ok";
  }
  if (normalized === "C") {
    return "warn";
  }
  return "bad";
}

function statusClass(prefix: string, value: unknown): string {
  const normalized = String(value || "").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-") || "unknown";
  return `status-pill ${prefix}-${normalized}`;
}

function riskBar(value: unknown) {
  const score = percentValue(value);
  return (
    <div className={`mini-progress tone-${scoreTone(score)}`}>
      <span>{score}</span>
      <em><i style={{ width: `${score}%` }} /></em>
    </div>
  );
}

function statusText(value: unknown, labels: Record<string, string>): string {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  return labels[normalized] || normalized;
}

function displayList(value: unknown): string {
  const items = asStringList(value);
  return items.length ? items.join("、") : "-";
}

function toSnakeCode(value: unknown): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function stripPagePrefix(code: string, pageCode: string): string {
  const pageToken = toSnakeCode(pageCode);
  if (!pageToken) {
    return code;
  }
  if (code.startsWith(`page_${pageToken}_`)) {
    return code.slice(`page_${pageToken}_`.length);
  }
  return code;
}

function suggestElementCode(value: unknown, pageCode: string, businessType: unknown): string {
  const normalizedBusinessType = String(businessType || "").trim().toLowerCase();
  if (normalizedBusinessType === "password_toggle") {
    return "password_toggle";
  }
  const pageToken = toSnakeCode(pageCode);
  const parts = stripPagePrefix(toSnakeCode(value), pageCode)
    .split("_")
    .filter((part) => part && part !== pageToken && part.length > 1 && !SUGGESTION_ELEMENT_CODE_NOISE_TOKENS.has(part) && !/^\d+$/.test(part));
  let suggestion = parts.join("_");
  if ((normalizedBusinessType === "metric_label" || normalizedBusinessType === "metric_value") && suggestion && !suggestion.endsWith(`_${normalizedBusinessType}`)) {
    suggestion = `${suggestion}_${normalizedBusinessType}`;
  }
  return /^[a-z][a-z0-9_]{2,79}$/.test(suggestion) ? suggestion : "";
}

function elementCodePolicyHint(value: unknown, pageCode: string, businessType: unknown): string {
  const code = String(value || "").trim();
  if (!code) {
    return "";
  }
  const normalizedBusinessType = String(businessType || "").trim().toLowerCase();
  const errors: string[] = [];
  if (!/^[a-z][a-z0-9_]{2,79}$/.test(code)) {
    errors.push("必须是 snake_case，小写字母开头，仅包含小写字母、数字和下划线。");
  }
  const parts = code.split("_").filter(Boolean);
  const noiseHits = parts.filter((part) => STRICT_ELEMENT_CODE_NOISE_TOKENS.has(part));
  if (noiseHits.length) {
    errors.push(`不能包含 locator/DOM 噪音词：${Array.from(new Set(noiseHits)).join(", ")}。`);
  }
  if (/^\d+$/.test(parts[parts.length - 1] || "")) {
    errors.push("不能用纯数字后缀作为主要区分方式。");
  }
  const pageToken = toSnakeCode(pageCode);
  if (pageToken && code.startsWith(`page_${pageToken}_`)) {
    errors.push("不能使用 page_页面名前缀，页面归属由页面对象承载。");
  }
  if (normalizedBusinessType === "password_toggle" && code !== "password_toggle") {
    errors.push("密码显隐元素必须统一命名为 password_toggle。");
  }
  if (normalizedBusinessType === "metric_label" && !code.endsWith("_metric_label")) {
    errors.push("指标标题必须以 _metric_label 结尾。");
  }
  if (normalizedBusinessType === "metric_value" && !code.endsWith("_metric_value")) {
    errors.push("指标值必须以 _metric_value 结尾。");
  }
  if (!errors.length) {
    return "";
  }
  const suggestion = suggestElementCode(code, pageCode, normalizedBusinessType);
  return `${errors.join(" ")}${suggestion ? ` 推荐编码：${suggestion}` : ""}`;
}

function describeStep(step: Record<string, unknown>): string {
  const action = text(step.action);
  const locatorType = String(step.locator_type || "").trim();
  const locatorValue = String(step.locator_value || "").trim();
  const role = String(step.role || "").trim();
  const value = String(step.value || "").trim();
  const locator = locatorType && locatorValue ? `${locatorType}${role ? `(${role})` : ""}=${locatorValue}` : locatorValue;
  if (value) {
    return `${action} ${locator || ""} -> ${value}`.trim();
  }
  return `${action} ${locator || ""}`.trim();
}

function stableHash(input: string): string {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16).padStart(8, "0").slice(0, 8);
}

function elementApiCode(item: Record<string, unknown>): string {
  return String(item.element_code || "").trim();
}

function inferDisplayElementName(item: Record<string, unknown>): string {
  const rawName = String(item.element_name || "").trim();
  const locatorType = String(item.locator_type || "").trim().toLowerCase();
  const locatorValue = String(item.locator_value || "").trim();
  const role = String(item.role || "").trim().toLowerCase();
  if (rawName && !/^录制元素\d+$/u.test(rawName)) {
    return rawName;
  }
  if (locatorType === "role") {
    if (role === "button") {
      return locatorValue ? (locatorValue.endsWith("按钮") ? locatorValue : `${locatorValue}按钮`) : "按钮";
    }
    if (["textbox", "searchbox", "combobox", "spinbutton"].includes(role)) {
      return locatorValue ? (locatorValue.endsWith("输入框") ? locatorValue : `${locatorValue}输入框`) : "输入框";
    }
    if (role === "link") {
      return locatorValue ? (locatorValue.endsWith("链接") ? locatorValue : `${locatorValue}链接`) : "链接";
    }
    return locatorValue || "角色控件";
  }
  if (locatorType === "placeholder") {
    return locatorValue ? (locatorValue.endsWith("输入框") ? locatorValue : `${locatorValue}输入框`) : "输入框";
  }
  return rawName || locatorValue || "-";
}

function inferDisplayElementCode(pageCode: string, item: Record<string, unknown>): string {
  const rawCode = String(item.element_code || "").trim();
  if (rawCode && !/---\d+$/u.test(rawCode)) {
    return rawCode;
  }
  const locatorType = String(item.locator_type || "").trim().toLowerCase();
  const role = String(item.role || "").trim().toLowerCase();
  const locatorValue = String(item.locator_value || "").trim();
  const normalizedPage = String(pageCode || "").trim().toLowerCase() || "page";
  let mid = locatorType || "elm";
  if (locatorType === "role") {
    if (role === "button") {
      mid = "btn";
    } else if (["textbox", "searchbox", "combobox", "spinbutton"].includes(role)) {
      mid = "input";
    } else {
      mid = role || "role";
    }
  }
  return `${normalizedPage}-${mid}-u${stableHash(`${locatorType}|${role}|${locatorValue}`)}`;
}

function defaultSemanticForm(element: Record<string, unknown>): SemanticForm {
  return {
    element_code: String(element.element_code || "").trim(),
    element_name: String(element.element_name || "").trim(),
    business_type: String(element.business_type || "").trim(),
    business_domain: String(element.business_domain || "").trim(),
    locator_source: String(element.locator_source || "").trim(),
    match_strategy: String(element.match_strategy || "exact").trim(),
    stability_level: String(element.stability_level || "low").trim(),
    review_status: String(element.review_status || "pending").trim(),
    status: String(element.status || "active").trim(),
    is_key_element: Boolean(element.is_key_element),
    anchor_required: Boolean(element.anchor_required),
    testid_value: String(element.testid_value || "").trim(),
    qa_value: String(element.qa_value || "").trim(),
    route_scope: String(element.route_scope || "").trim(),
    governance_note: String(element.governance_note || "").trim(),
  };
}

function defaultAliasForm(element: Record<string, unknown>): AliasForm {
  return {
    aliases_text: asStringList(element.aliases_json).join("\n"),
    semantic_tags_text: asStringList(element.semantic_tags_json).join("\n"),
  };
}

function defaultPromoteForm(group: Record<string, unknown>): PromoteForm {
  const locatorType = String(group.top_locator_type || "").trim();
  const locatorValue = String(group.top_locator_value || "").trim();
  return {
    element_code: String(group.proposed_element_code || "").trim(),
    element_name: String(group.proposed_element_name || "").trim(),
    business_type: String(group.business_type_guess || "").trim(),
    business_domain: String(group.business_domain_guess || "").trim(),
    is_key_element: false,
    locator_type: locatorType,
    locator_value: locatorValue,
    role: String(group.top_role || "").trim(),
    locator_source: String(group.top_locator_source || "").trim(),
    route_scope: String(group.route_scope || "").trim(),
    testid_value: locatorType === "data-testid" ? locatorValue : "",
    qa_value: locatorType === "data-qa" ? locatorValue : "",
    governance_note: "",
    operator: "admin",
  };
}

function normalizePanelMode(value: unknown): ElementPanelMode {
  const normalized = String(value || "").trim();
  return normalized === "semantic" || normalized === "aliases" || normalized === "locators" || normalized === "refs" ? normalized : "detail";
}

export function PageObjectElementsPage() {
  const params = useParams<{ pageCode: string; elementCode?: string; groupKey?: string; sessionId?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const normalizedPageCode = String(params.pageCode || "").trim();
  const routeElementCode = String(params.elementCode || "").trim();
  const routeGroupKey = String(params.groupKey || "").trim();
  const routeSessionId = String(params.sessionId || "").trim();
  const isElementDetailRoute = Boolean(routeElementCode);
  const isCandidateGroupRoute = Boolean(routeGroupKey);
  const isPlaybackRoute = Boolean(routeSessionId);
  const isDrilldownRoute = isElementDetailRoute || isCandidateGroupRoute || isPlaybackRoute;
  const routePanelMode = normalizePanelMode(searchParams.get("mode"));
  const initialTab = String(searchParams.get("tab") || "").trim();
  const [activeTab, setActiveTab] = useState<TabId>(initialTab === "candidates" || initialTab === "history" ? initialTab : "formal");
  const [projectCode, setProjectCode] = useState<string>(normalizeProjectCode(searchParams.get("project") || DEFAULT_PROJECT_CODE));
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [pageObject, setPageObject] = useState<Record<string, unknown>>({});
  const [elements, setElements] = useState<Array<Record<string, unknown>>>([]);
  const [selectedElementCodes, setSelectedElementCodes] = useState<string[]>([]);
  const [selectedElement, setSelectedElement] = useState<Record<string, unknown>>({});
  const [elementPanelMode, setElementPanelMode] = useState<ElementPanelMode>(routePanelMode);
  const [elementVersions, setElementVersions] = useState<Array<Record<string, unknown>>>([]);
  const [elementRefs, setElementRefs] = useState<Array<Record<string, unknown>>>([]);
  const [elementDetailLoading, setElementDetailLoading] = useState<boolean>(false);
  const [elementKeyword, setElementKeyword] = useState<string>("");
  const [elementBusinessTypeFilter, setElementBusinessTypeFilter] = useState<string>("");
  const [elementReviewFilter, setElementReviewFilter] = useState<string>("");
  const [elementStabilityFilter, setElementStabilityFilter] = useState<string>("");
  const [elementLocatorSourceFilter, setElementLocatorSourceFilter] = useState<string>("");
  const [elementKeyFilter, setElementKeyFilter] = useState<string>("");
  const [semanticForm, setSemanticForm] = useState<SemanticForm>(defaultSemanticForm({}));
  const [aliasForm, setAliasForm] = useState<AliasForm>(defaultAliasForm({}));
  const [candidateGroups, setCandidateGroups] = useState<Array<Record<string, unknown>>>([]);
  const [selectedGroupKeys, setSelectedGroupKeys] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<Record<string, unknown>>({});
  const [candidateRows, setCandidateRows] = useState<Array<Record<string, unknown>>>([]);
  const [selectedCandidateKeys, setSelectedCandidateKeys] = useState<string[]>([]);
  const [historyRows, setHistoryRows] = useState<Array<Record<string, unknown>>>([]);
  const [selectedHistorySessionIds, setSelectedHistorySessionIds] = useState<string[]>([]);
  const [playbackPayload, setPlaybackPayload] = useState<Record<string, unknown>>({});
  const [playbackCursor, setPlaybackCursor] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackLoading, setPlaybackLoading] = useState<boolean>(false);
  const [promotionStatus, setPromotionStatus] = useState<string>("");
  const [sessionFilter, setSessionFilter] = useState<string>(String(searchParams.get("session_id") || "").trim());
  const [historyStatus, setHistoryStatus] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [promoteGroup, setPromoteGroup] = useState<Record<string, unknown>>({});
  const [promoteForm, setPromoteForm] = useState<PromoteForm>(defaultPromoteForm({}));
  const [mergeGroup, setMergeGroup] = useState<Record<string, unknown>>({});
  const [mergeTargetCode, setMergeTargetCode] = useState<string>("");
  const [rejectGroupTarget, setRejectGroupTarget] = useState<Record<string, unknown>>({});
  const [rejectNote, setRejectNote] = useState<string>("");
  const [batchRejectOpen, setBatchRejectOpen] = useState<boolean>(false);
  const [candidateRejectTarget, setCandidateRejectTarget] = useState<Record<string, unknown>>({});
  const [deleteTarget, setDeleteTarget] = useState<"" | "elements" | "groups" | "candidates" | "history">("");
  const timerRef = useRef<number | null>(null);

  const playbackSession = useMemo(() => asRecord(playbackPayload.session), [playbackPayload]);
  const playbackSteps = useMemo(() => asRecordList(playbackPayload.recorded_steps), [playbackPayload]);
  const playbackScript = useMemo(() => String(playbackPayload.script_code || ""), [playbackPayload]);
  const playbackStderr = useMemo(() => String(playbackPayload.stderr_tail || ""), [playbackPayload]);
  const elementLocators = useMemo(() => asRecordList(selectedElement.locators), [selectedElement]);
  const promoteCodeHint = useMemo(
    () => elementCodePolicyHint(promoteForm.element_code, normalizedPageCode, promoteForm.business_type),
    [normalizedPageCode, promoteForm.business_type, promoteForm.element_code],
  );
  const promoteSuggestedCode = useMemo(
    () => suggestElementCode(promoteForm.element_code, normalizedPageCode, promoteForm.business_type),
    [normalizedPageCode, promoteForm.business_type, promoteForm.element_code],
  );
  const promoteValidationItems = useMemo(() => {
    const elementCode = promoteForm.element_code.trim();
    const locatorSource = promoteForm.locator_source.trim().toLowerCase();
    const hasStableContract = Boolean(promoteForm.testid_value.trim() || promoteForm.qa_value.trim());
    const duplicate = elements.some((item) => String(item.element_code || "").trim() === elementCode);
    const stableLocatorSources = new Set(["testid", "qa", "role_name", "placeholder", "id", "name", "manual"]);
    return [
      { ok: Boolean(elementCode && !promoteCodeHint), label: promoteCodeHint ? `编码规则：${promoteCodeHint}` : "编码规则通过" },
      { ok: Boolean(elementCode && !duplicate), label: duplicate ? "编码唯一：已存在同名正式元素" : "编码唯一通过" },
      { ok: !promoteForm.is_key_element || hasStableContract, label: promoteForm.is_key_element && !hasStableContract ? "关键元素必须填写 testid 或 qa" : "关键元素契约通过" },
      { ok: stableLocatorSources.has(locatorSource), label: stableLocatorSources.has(locatorSource) ? "主定位器稳定性可接受" : "主定位器稳定性不足，建议补充稳定定位来源" },
    ];
  }, [elements, promoteCodeHint, promoteForm.element_code, promoteForm.is_key_element, promoteForm.locator_source, promoteForm.qa_value, promoteForm.testid_value]);
  const promoteHasBlockingIssue = promoteValidationItems.some((item) => !item.ok);
  const semanticCodeHint = useMemo(
    () => elementCodePolicyHint(semanticForm.element_code, normalizedPageCode, semanticForm.business_type),
    [normalizedPageCode, semanticForm.business_type, semanticForm.element_code],
  );
  const selectedCodeHint = useMemo(
    () => elementCodePolicyHint(selectedElement.element_code, normalizedPageCode, selectedElement.business_type),
    [normalizedPageCode, selectedElement.business_type, selectedElement.element_code],
  );
  const selectedSuggestedCode = useMemo(
    () => suggestElementCode(selectedElement.element_code, normalizedPageCode, selectedElement.business_type),
    [normalizedPageCode, selectedElement.business_type, selectedElement.element_code],
  );
  const selectedReviewStatus = String(selectedElement.review_status || "").trim().toLowerCase();
  const visibleElementCodes = useMemo(() => elements.map((item) => elementApiCode(item)).filter(Boolean), [elements]);
  const visibleGroupKeys = useMemo(() => candidateGroups.map((item) => String(item.group_key || "").trim()).filter(Boolean), [candidateGroups]);
  const visibleCandidateKeys = useMemo(() => candidateRows.map((item) => String(item.candidate_key || "").trim()).filter(Boolean), [candidateRows]);
  const visibleHistorySessionIds = useMemo(() => historyRows.map((item) => String(item.session_id || "").trim()).filter(Boolean), [historyRows]);
  const allElementsSelected = visibleElementCodes.length > 0 && visibleElementCodes.every((code) => selectedElementCodes.includes(code));
  const allGroupsSelected = visibleGroupKeys.length > 0 && visibleGroupKeys.every((key) => selectedGroupKeys.includes(key));
  const allCandidatesSelected = visibleCandidateKeys.length > 0 && visibleCandidateKeys.every((key) => selectedCandidateKeys.includes(key));
  const allHistorySelected = visibleHistorySessionIds.length > 0 && visibleHistorySessionIds.every((id) => selectedHistorySessionIds.includes(id));
  const filteredElements = useMemo(() => {
    const keyword = elementKeyword.trim().toLowerCase();
    return elements.filter((item) => {
      if (elementBusinessTypeFilter && String(item.business_type || "").trim() !== elementBusinessTypeFilter) {
        return false;
      }
      if (elementReviewFilter && String(item.review_status || "").trim() !== elementReviewFilter) {
        return false;
      }
      if (elementStabilityFilter && String(item.stability_level || "").trim() !== elementStabilityFilter) {
        return false;
      }
      if (elementLocatorSourceFilter && String(item.locator_source || item.locator_type || "").trim() !== elementLocatorSourceFilter) {
        return false;
      }
      if (elementKeyFilter === "true" && !item.is_key_element) {
        return false;
      }
      if (elementKeyFilter === "false" && item.is_key_element) {
        return false;
      }
      if (!keyword) {
        return true;
      }
      return [item.element_code, item.element_name, item.locator_value, item.aliases_json, item.semantic_tags_json]
        .map((value) => (Array.isArray(value) ? value.join(" ") : String(value || "")))
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
  }, [elementBusinessTypeFilter, elementKeyFilter, elementKeyword, elementLocatorSourceFilter, elementReviewFilter, elementStabilityFilter, elements]);
  const governanceSummary = useMemo(() => {
    const formalCount = numberOf(pageObject.element_count || elements.length);
    const approvedCount = numberOf(pageObject.approved_element_count);
    const pendingCandidateCount = numberOf(pageObject.candidate_pending_count);
    const keyCount = numberOf(pageObject.key_element_count);
    const keyCoverage = formalCount > 0 ? Math.round((keyCount / formalCount) * 100) : 0;
    const testabilityScore = numberOf(pageObject.testability_score);
    return { formalCount, approvedCount, pendingCandidateCount, keyCount, keyCoverage, testabilityScore };
  }, [elements.length, pageObject]);

  const backLink = useMemo(() => {
    const query = new URLSearchParams();
    const normalizedProject = String(projectCode || "").trim();
    if (normalizedProject) {
      query.set("project", normalizedProject);
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return `/assets/page-objects${suffix}`;
  }, [projectCode]);

  const elementListLink = useMemo(() => {
    const query = new URLSearchParams();
    const normalizedProject = String(projectCode || "").trim();
    if (normalizedProject) {
      query.set("project", normalizedProject);
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements${suffix}`;
  }, [normalizedPageCode, projectCode]);

  const candidateListLink = useMemo(() => {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    query.set("tab", "candidates");
    if (sessionFilter) {
      query.set("session_id", sessionFilter);
    }
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements?${query.toString()}`;
  }, [normalizedPageCode, projectCode, sessionFilter]);

  const historyListLink = useMemo(() => {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    query.set("tab", "history");
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements?${query.toString()}`;
  }, [normalizedPageCode, projectCode]);

  const drilldownBackLink = isCandidateGroupRoute ? candidateListLink : isPlaybackRoute ? historyListLink : elementListLink;

  const recorderLink = useMemo(() => {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    query.set("page_code", normalizedPageCode);
    const pageName = String(pageObject.page_name || "").trim();
    const pageUrl = String(pageObject.page_url || pageObject.route_pattern || "").trim();
    if (pageName) {
      query.set("page_name", pageName);
    }
    if (pageUrl) {
      query.set("url", pageUrl);
    }
    return `/assets/page-objects/recorder?${query.toString()}`;
  }, [normalizedPageCode, pageObject.page_name, pageObject.page_url, pageObject.route_pattern, projectCode]);

  function buildElementDetailLink(elementCode: string, mode: ElementPanelMode = "detail"): string {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    if (mode !== "detail") {
      query.set("mode", mode);
    }
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements/${encodeURIComponent(elementCode)}?${query.toString()}`;
  }

  function buildCandidateGroupDetailLink(groupKey: string): string {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    if (sessionFilter) {
      query.set("session_id", sessionFilter);
    }
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements/candidates/${encodeURIComponent(groupKey)}?${query.toString()}`;
  }

  function buildPlaybackDetailLink(sessionId: string): string {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements/history/${encodeURIComponent(sessionId)}?${query.toString()}`;
  }

  function buildCandidateSessionLink(sessionId: string): string {
    const query = new URLSearchParams();
    query.set("project", normalizeProjectCode(projectCode));
    query.set("tab", "candidates");
    query.set("session_id", sessionId);
    return `/assets/page-objects/${encodeURIComponent(normalizedPageCode)}/elements?${query.toString()}`;
  }

  function toggleSelection(value: string, selectedValues: string[], setter: (values: string[]) => void) {
    const normalized = value.trim();
    if (!normalized) {
      return;
    }
    setter(selectedValues.includes(normalized) ? selectedValues.filter((item) => item !== normalized) : [...selectedValues, normalized]);
  }

  function toggleAllSelection(values: string[], checked: boolean, setter: (values: string[]) => void) {
    setter(checked ? Array.from(new Set(values)) : []);
  }

  function setDetailMode(mode: ElementPanelMode) {
    setElementPanelMode(mode);
    if (!isElementDetailRoute) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("project", normalizeProjectCode(projectCode));
    if (mode === "detail") {
      next.delete("mode");
    } else {
      next.set("mode", mode);
    }
    setSearchParams(next, { replace: true });
  }

  function switchTab(tab: TabId) {
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    next.set("project", normalizeProjectCode(projectCode));
    if (tab === "formal") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    if (sessionFilter) {
      next.set("session_id", sessionFilter);
    } else {
      next.delete("session_id");
    }
    setSearchParams(next, { replace: true });
  }

  async function reload() {
    if (!normalizedPageCode) {
      setLoading(false);
      setErrorText("页面编码缺失，无法加载元素列表。");
      setPageObject({});
      setElements([]);
      setCandidateGroups([]);
      setHistoryRows([]);
      return;
    }
    setLoading(true);
    setErrorText("");
    try {
      const [objectPayload, elementPayload, groupPayload, historyPayload] = await Promise.all([
        getPageObject(normalizedPageCode, { project_code: projectCode, client: "web" }),
        listPageElements(normalizedPageCode, { project_code: projectCode, client: "web" }),
        listCandidateGroups(normalizedPageCode, {
          project_code: projectCode,
          client: "web",
          promotion_status: promotionStatus,
          session_id: sessionFilter,
        }),
        listRecorderSessions({
          project_code: projectCode,
          client: "web",
          page_code: normalizedPageCode,
          status: historyStatus,
          limit: 50,
          offset: 0,
        }),
      ]);
      setPageObject(asRecord(objectPayload.item));
      const nextElements = asRecordList(elementPayload.items);
      const nextGroups = asRecordList(groupPayload.items);
      const nextHistoryRows = asRecordList(historyPayload.items);
      setElements(nextElements);
      setCandidateGroups(nextGroups);
      setHistoryRows(nextHistoryRows);
      const nextElementCodes = new Set(nextElements.map((item) => elementApiCode(item)).filter(Boolean));
      const nextGroupKeys = new Set(nextGroups.map((item) => String(item.group_key || "").trim()).filter(Boolean));
      const nextSessionIds = new Set(nextHistoryRows.map((item) => String(item.session_id || "").trim()).filter(Boolean));
      setSelectedElementCodes((prev) => prev.filter((item) => nextElementCodes.has(item)));
      setSelectedGroupKeys((prev) => prev.filter((item) => nextGroupKeys.has(item)));
      setSelectedHistorySessionIds((prev) => prev.filter((item) => nextSessionIds.has(item)));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "元素治理数据加载失败");
      setPageObject({});
      setElements([]);
      setCandidateGroups([]);
      setHistoryRows([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadElementDetail(elementCode: string, mode: ElementPanelMode) {
    const normalizedElementCode = elementCode.trim();
    if (!normalizedElementCode) {
      setSelectedElement({});
      setElementVersions([]);
      setElementRefs([]);
      return;
    }
    setElementDetailLoading(true);
    setElementPanelMode(mode);
    setFeedback("");
    try {
      const [detailPayload, versionPayload, refPayload] = await Promise.all([
        getPageElement(normalizedPageCode, normalizedElementCode, { project_code: projectCode, client: "web" }),
        listPageElementVersions(normalizedPageCode, normalizedElementCode, { project_code: projectCode, client: "web" }),
        listPageObjectRefs(normalizedPageCode, normalizedElementCode, { project_code: projectCode, client: "web" }),
      ]);
      const detail = asRecord(detailPayload.item);
      setSelectedElement(detail);
      setSemanticForm(defaultSemanticForm(detail));
      setAliasForm(defaultAliasForm(detail));
      setElementVersions(asRecordList(versionPayload.items));
      setElementRefs(asRecordList(refPayload.items));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "元素详情加载失败");
      setSelectedElement({});
      setElementVersions([]);
      setElementRefs([]);
    } finally {
      setElementDetailLoading(false);
    }
  }

  function openElementPanel(item: Record<string, unknown>, mode: ElementPanelMode) {
    const code = elementApiCode(item);
    if (!code) {
      setFeedback("该元素缺少真实 element_code，无法打开详情。");
      return;
    }
    navigate(buildElementDetailLink(code, mode));
  }

  async function submitSemanticForm() {
    const code = elementApiCode(selectedElement);
    if (!code || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在保存元素语义...");
    try {
      const payload = await updatePageElement(
        normalizedPageCode,
        code,
        {
          ...semanticForm,
          changed_by: "admin",
          change_summary: "更新元素语义与治理字段",
        },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(payload.item);
      const updatedCode = elementApiCode(item) || code;
      setSelectedElement(item);
      setSemanticForm(defaultSemanticForm(item));
      setFeedback("元素语义已保存。");
      await reload();
      navigate(buildElementDetailLink(updatedCode, "detail"), { replace: true });
      await loadElementDetail(updatedCode, "detail");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "保存元素语义失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitAliasForm() {
    const code = elementApiCode(selectedElement);
    if (!code || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在保存别名与语义标签...");
    try {
      const payload = await updatePageElement(
        normalizedPageCode,
        code,
        {
          aliases_json: asStringList(aliasForm.aliases_text),
          semantic_tags_json: asStringList(aliasForm.semantic_tags_text),
          changed_by: "admin",
          change_summary: "更新元素别名与语义标签",
        },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(payload.item);
      const updatedCode = elementApiCode(item) || code;
      setSelectedElement(item);
      setAliasForm(defaultAliasForm(item));
      setFeedback("元素别名已保存。");
      await reload();
      navigate(buildElementDetailLink(updatedCode, "aliases"), { replace: true });
      await loadElementDetail(updatedCode, "aliases");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "保存别名失败");
    } finally {
      setBusy(false);
    }
  }

  async function markElementPending(item: Record<string, unknown>) {
    const code = elementApiCode(item);
    if (!code || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在标记元素为待治理...");
    try {
      const payload = await updatePageElement(
        normalizedPageCode,
        code,
        {
          review_status: "pending",
          stability_level: "low",
          governance_note: "人工标记待治理，需要重新确认语义、定位器稳定性和测试点映射资格。",
          changed_by: "admin",
          change_summary: "标记待治理",
        },
        { project_code: projectCode, client: "web" },
      );
      const updated = asRecord(payload.item);
      const updatedCode = elementApiCode(updated) || code;
      setSelectedElement(updated);
      setSemanticForm(defaultSemanticForm(updated));
      setFeedback("已标记为待治理。");
      await reload();
      navigate(buildElementDetailLink(updatedCode, "semantic"));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "标记待治理失败");
    } finally {
      setBusy(false);
    }
  }

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopReplayPreview() {
    clearTimer();
    setIsPlaying(false);
  }

  function resetReplayPreview() {
    stopReplayPreview();
    setPlaybackCursor(0);
  }

  function startReplayPreview() {
    if (playbackSteps.length <= 0) {
      setFeedback("该录制会话没有可回放步骤。");
      return;
    }
    stopReplayPreview();
    setPlaybackCursor(0);
    setIsPlaying(true);
    let nextCursor = 0;
    const runNext = () => {
      nextCursor += 1;
      setPlaybackCursor(nextCursor);
      if (nextCursor >= playbackSteps.length) {
        setIsPlaying(false);
        timerRef.current = null;
        return;
      }
      timerRef.current = window.setTimeout(runNext, 900);
    };
    timerRef.current = window.setTimeout(runNext, 280);
  }

  async function loadPlayback(targetSessionId: string) {
    const normalizedSessionId = targetSessionId.trim();
    if (!normalizedSessionId) {
      return;
    }
    setPlaybackLoading(true);
    setFeedback("正在加载录制回放...");
    try {
      const response = await getRecorderSessionPlayback(normalizedSessionId);
      setPlaybackPayload(asRecord(response.item));
      setPlaybackCursor(0);
      setIsPlaying(false);
      setFeedback("录制回放已加载。");
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "加载录制回放失败");
    } finally {
      setPlaybackLoading(false);
    }
  }

  async function loadGroupDetail(group: Record<string, unknown>) {
    const groupKey = String(group.group_key || "").trim();
    if (!groupKey) {
      return;
    }
    setDetailLoading(true);
    setSelectedGroup(group);
    setFeedback("");
    try {
      const payload = await getCandidateGroup(normalizedPageCode, groupKey, { project_code: projectCode, client: "web" });
      const item = asRecord(payload.item);
      const nextRows = asRecordList(item.candidates);
      setSelectedGroup(item);
      setCandidateRows(nextRows);
      const nextCandidateKeys = new Set(nextRows.map((row) => String(row.candidate_key || "").trim()).filter(Boolean));
      setSelectedCandidateKeys((prev) => prev.filter((key) => nextCandidateKeys.has(key)));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "候选详情加载失败");
      setCandidateRows([]);
      setSelectedCandidateKeys([]);
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadProjectOptions() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          setProjectCodes(projectOptions([...projects.codes, projectCode]));
        }
      } catch {
        // Keep default option.
      }
    }
    void loadProjectOptions();
    return () => {
      cancelled = true;
    };
  }, [projectCode]);

  useEffect(() => () => clearTimer(), []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedPageCode, projectCode, promotionStatus, sessionFilter, historyStatus]);

  useEffect(() => {
    if (!isElementDetailRoute) {
      setSelectedElement({});
      setElementVersions([]);
      setElementRefs([]);
      return;
    }
    void loadElementDetail(routeElementCode, routePanelMode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isElementDetailRoute, routeElementCode, normalizedPageCode, projectCode]);

  useEffect(() => {
    if (isElementDetailRoute) {
      setElementPanelMode(routePanelMode);
    }
  }, [isElementDetailRoute, routePanelMode]);

  useEffect(() => {
    if (!isCandidateGroupRoute) {
      setSelectedGroup({});
      setCandidateRows([]);
      return;
    }
    void loadGroupDetail({ group_key: routeGroupKey });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCandidateGroupRoute, routeGroupKey, normalizedPageCode, projectCode]);

  useEffect(() => {
    if (!isPlaybackRoute) {
      setPlaybackPayload({});
      setPlaybackCursor(0);
      stopReplayPreview();
      return;
    }
    void loadPlayback(routeSessionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaybackRoute, routeSessionId]);

  async function submitPromote() {
    const groupKey = String(promoteGroup.group_key || "").trim();
    if (!groupKey || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在提升候选分组...");
    try {
      await promoteCandidateGroup(normalizedPageCode, groupKey, { ...promoteForm }, { project_code: projectCode, client: "web" });
      setPromoteGroup({});
      setFeedback("候选分组已提升为正式元素。");
      await reload();
      await loadGroupDetail({ group_key: groupKey });
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "提升失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitMerge() {
    const groupKey = String(mergeGroup.group_key || "").trim();
    if (!groupKey || !mergeTargetCode.trim() || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在合并候选分组...");
    try {
      await mergeCandidateGroup(
        normalizedPageCode,
        groupKey,
        {
          target_element_code: mergeTargetCode.trim(),
          review_note: "候选分组合并到已有正式元素",
          operator: "admin",
          write_locator: true,
        },
        { project_code: projectCode, client: "web" },
      );
      setMergeGroup({});
      setMergeTargetCode("");
      setFeedback("候选分组已合并到正式元素，已进入正式元素定位器页查看同步结果。");
      await reload();
      navigate(buildElementDetailLink(mergeTargetCode.trim(), "locators"));
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "合并失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitRejectGroup() {
    const groupKey = String(rejectGroupTarget.group_key || "").trim();
    if (!groupKey || !rejectNote.trim() || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在拒绝候选分组...");
    try {
      await rejectCandidateGroup(
        normalizedPageCode,
        groupKey,
        { review_note: rejectNote.trim(), operator: "admin" },
        { project_code: projectCode, client: "web" },
      );
      setRejectGroupTarget({});
      setRejectNote("");
      setFeedback("候选分组已拒绝。");
      await reload();
      await loadGroupDetail({ group_key: groupKey });
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "拒绝失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRejectCandidateGroups() {
    if (!selectedGroupKeys.length || busy) {
      return;
    }
    setRejectNote("");
    setBatchRejectOpen(true);
  }

  async function confirmBatchRejectCandidateGroups() {
    const note = rejectNote.trim();
    if (!selectedGroupKeys.length || !note || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在批量拒绝候选分组...");
    try {
      for (const groupKey of selectedGroupKeys) {
        await rejectCandidateGroup(
          normalizedPageCode,
          groupKey,
          { review_note: note, operator: "admin" },
          { project_code: projectCode, client: "web" },
        );
      }
      setSelectedGroupKeys([]);
      setRejectNote("");
      setBatchRejectOpen(false);
      setFeedback(`候选分组已批量拒绝：${selectedGroupKeys.length} 组。`);
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量拒绝候选分组失败");
    } finally {
      setBusy(false);
    }
  }

  async function rejectOneCandidate(candidate: Record<string, unknown>) {
    const candidateKey = String(candidate.candidate_key || "").trim();
    if (!candidateKey || busy) {
      return;
    }
    setCandidateRejectTarget(candidate);
    setRejectNote("");
  }

  async function confirmRejectOneCandidate() {
    const candidateKey = String(candidateRejectTarget.candidate_key || "").trim();
    const note = rejectNote.trim();
    if (!candidateKey || !note || busy) {
      return;
    }
    setBusy(true);
    setFeedback("正在拒绝候选...");
    try {
      await rejectCandidateElement(
        normalizedPageCode,
        candidateKey,
        { review_note: note, operator: "admin" },
        { project_code: projectCode, client: "web" },
      );
      setCandidateRejectTarget({});
      setRejectNote("");
      setFeedback("候选已拒绝。");
      if (selectedGroup.group_key) {
        await loadGroupDetail(selectedGroup);
      }
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "拒绝候选失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemoveElements() {
    if (!selectedElementCodes.length || busy) {
      return;
    }
    setDeleteTarget("elements");
  }

  async function confirmBatchRemoveElements() {
    setBusy(true);
    setFeedback("正在物理删除正式元素...");
    try {
      const response = await batchDeletePageElements(
        normalizedPageCode,
        { element_codes: selectedElementCodes },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(response.item);
      setFeedback(`正式元素已物理删除：${text(item.deleted_count)} 条。`);
      setSelectedElementCodes([]);
      setDeleteTarget("");
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量删除正式元素失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemoveCandidateGroups() {
    if (!selectedGroupKeys.length || busy) {
      return;
    }
    setDeleteTarget("groups");
  }

  async function confirmBatchRemoveCandidateGroups() {
    setBusy(true);
    setFeedback("正在物理删除候选分组...");
    try {
      const response = await batchDeleteCandidateGroups(
        normalizedPageCode,
        { group_keys: selectedGroupKeys },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(response.item);
      setFeedback(`候选分组已物理删除：${text(item.deleted_group_count)} 组，候选 ${text(item.deleted_candidate_count)} 条。`);
      setSelectedGroupKeys([]);
      setDeleteTarget("");
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量删除候选分组失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemoveCandidateRows() {
    if (!selectedCandidateKeys.length || busy) {
      return;
    }
    setDeleteTarget("candidates");
  }

  async function confirmBatchRemoveCandidateRows() {
    const currentGroupKey = String(selectedGroup.group_key || routeGroupKey || "").trim();
    setBusy(true);
    setFeedback("正在物理删除候选明细...");
    try {
      const response = await batchDeleteCandidateElements(
        normalizedPageCode,
        { candidate_keys: selectedCandidateKeys },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(response.item);
      setFeedback(`候选明细已物理删除：${text(item.deleted_candidate_count)} 条。`);
      setSelectedCandidateKeys([]);
      setDeleteTarget("");
      await reload();
      if (Number(item.empty_group_deleted_count || 0) > 0) {
        navigate(candidateListLink);
      } else if (currentGroupKey) {
        await loadGroupDetail({ group_key: currentGroupKey });
      }
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量删除候选明细失败");
    } finally {
      setBusy(false);
    }
  }

  async function batchRemoveHistoryRows() {
    if (!selectedHistorySessionIds.length || busy) {
      return;
    }
    setDeleteTarget("history");
  }

  async function confirmBatchRemoveHistoryRows() {
    setBusy(true);
    setFeedback("正在物理删除录制历史...");
    try {
      const response = await batchDeleteRecorderSessions(
        { session_ids: selectedHistorySessionIds, delete_artifacts: true },
        { project_code: projectCode, client: "web" },
      );
      const item = asRecord(response.item);
      setFeedback(`录制历史已物理删除：${text(item.deleted_session_count)} 条。`);
      setSelectedHistorySessionIds([]);
      setDeleteTarget("");
      await reload();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "批量删除录制历史失败");
    } finally {
      setBusy(false);
    }
  }

  function openPromote(group: Record<string, unknown>) {
    setPromoteGroup(group);
    setPromoteForm(defaultPromoteForm(group));
    setFeedback("");
  }

  function openMerge(group: Record<string, unknown>) {
    setMergeGroup(group);
    const businessType = String(group.business_type_guess || "").trim();
    const matched = elements.find((item) => String(item.business_type || "").trim() === businessType);
    setMergeTargetCode(String(matched?.element_code || elements[0]?.element_code || "").trim());
    setFeedback("");
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>
            {isCandidateGroupRoute ? "候选分组详情" : isPlaybackRoute ? "录制回放详情" : isElementDetailRoute ? "元素详情" : pageDisplayName(pageObject) !== "-" ? pageDisplayName(pageObject) : "元素治理"}
            <span className="page-title-code"> / {text(normalizedPageCode)}</span>
          </h1>
          <p className="muted">
            {isCandidateGroupRoute
              ? "在候选分组详情页查看明细，并完成提升、合并或拒绝。"
              : isPlaybackRoute
                ? "在录制回放详情页查看步骤、脚本和回放进度。"
                : isElementDetailRoute
                  ? "在详情页完成编码修复、语义审核、别名维护、定位器和引用查看。"
                  : "正式元素、候选元素和录制历史在这里统一治理，审核后再进入测试点映射链路。"}
          </p>
          <div className="asset-pill-strip page-meta-strip">
            <span className="asset-pill">项目：{text(projectCode)}</span>
            <span className="asset-pill">URL：{text(pageObject.page_url || pageObject.route_pattern)}</span>
            <span className={statusClass("page-status", pageObject.status)}>{statusText(pageObject.status, PAGE_OBJECT_STATUS_LABELS)}</span>
            <span className={statusClass("governance", pageObject.governance_status)}>{statusText(pageObject.governance_status, PAGE_OBJECT_GOVERNANCE_STATUS_LABELS)}</span>
          </div>
        </div>
        <div className="header-actions">
          {!isDrilldownRoute ? (
            <Link className="button" to={recorderLink}>
              开始录制
            </Link>
          ) : null}
          <button type="button" className="button secondary" onClick={() => void reload()} disabled={loading || busy}>
            刷新数据
          </button>
          {isDrilldownRoute ? (
            <Link className="button secondary" to={drilldownBackLink}>
              返回元素列表
            </Link>
          ) : null}
          <Link className="button secondary" to={backLink}>
            返回页面对象
          </Link>
        </div>
      </header>

      <FilterBar className="governance-filter-strip">
        <label>
          项目
          <select value={projectCode} onChange={(event) => setProjectCode(normalizeProjectCode(event.target.value))}>
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <div className="header-actions">
          {sessionFilter ? (
            <button type="button" className="button secondary" onClick={() => setSessionFilter("")} disabled={loading || busy}>
              清除 session 筛选
            </button>
          ) : null}
        </div>
      </FilterBar>

      {!loading && !errorText ? (
        <section className="governance-metrics compact">
          <article className="governance-metric-card">
            <span>正式元素数</span>
            <strong>{governanceSummary.formalCount}</strong>
            <em>当前正式资产</em>
          </article>
          <article className="governance-metric-card">
            <span>审核通过数</span>
            <strong className="tone-good">{governanceSummary.approvedCount}</strong>
            <em>可进入映射候选池</em>
          </article>
          <article className="governance-metric-card">
            <span>待审候选组</span>
            <strong className={governanceSummary.pendingCandidateCount > 0 ? "tone-warn" : ""}>{governanceSummary.pendingCandidateCount}</strong>
            <em>需要治理处理</em>
          </article>
          <article className="governance-metric-card">
            <span>关键元素数</span>
            <strong>{governanceSummary.keyCount}</strong>
            <em>已标记关键元素</em>
          </article>
          <article className="governance-metric-card progress-card">
            <span>关键元素覆盖率</span>
            <strong className={`tone-${scoreTone(governanceSummary.keyCoverage)}`}>{governanceSummary.keyCoverage}%</strong>
            <div className={`mini-progress tone-${scoreTone(governanceSummary.keyCoverage)}`}><em><i style={{ width: `${governanceSummary.keyCoverage}%` }} /></em></div>
          </article>
          <article className="governance-metric-card progress-card">
            <span>可测试性评分</span>
            <strong className={`tone-${scoreTone(governanceSummary.testabilityScore)}`}>{governanceSummary.testabilityScore}</strong>
            <div className={`mini-progress tone-${scoreTone(governanceSummary.testabilityScore)}`}><em><i style={{ width: `${percentValue(governanceSummary.testabilityScore)}%` }} /></em></div>
          </article>
        </section>
      ) : null}

      {!isDrilldownRoute ? (
        <section className="panel tabs">
          <button type="button" className={`tab ${activeTab === "formal" ? "active" : ""}`} onClick={() => switchTab("formal")}>
            正式元素
          </button>
          <button type="button" className={`tab ${activeTab === "candidates" ? "active" : ""}`} onClick={() => switchTab("candidates")}>
            候选元素{governanceSummary.pendingCandidateCount > 0 ? <span className="tab-count">{governanceSummary.pendingCandidateCount}</span> : null}
          </button>
          <button type="button" className={`tab ${activeTab === "history" ? "active" : ""}`} onClick={() => switchTab("history")}>
            录制历史
          </button>
        </section>
      ) : null}

      {loading ? <section className="panel">正在加载元素治理数据...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {feedback ? <section className="panel">{feedback}</section> : null}

      {!loading && !errorText && (isElementDetailRoute || (!isDrilldownRoute && activeTab === "formal")) ? (
        <>
          {!isDrilldownRoute ? (
          <>
          <FilterBar className="formal-filter-grid">
            <label className="grow">
              关键词
              <input value={elementKeyword} onChange={(event) => setElementKeyword(event.target.value)} placeholder="搜索编码、名称、别名或定位器" />
            </label>
            <label>
              业务类型
              <select value={elementBusinessTypeFilter} onChange={(event) => setElementBusinessTypeFilter(event.target.value)}>
                <option value="">全部</option>
                {BUSINESS_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              审核状态
              <select value={elementReviewFilter} onChange={(event) => setElementReviewFilter(event.target.value)}>
                <option value="">全部</option>
                {REVIEW_STATUSES.map((item) => <option key={item} value={item}>{statusText(item, REVIEW_STATUS_LABELS)}</option>)}
              </select>
            </label>
            <label>
              稳定等级
              <select value={elementStabilityFilter} onChange={(event) => setElementStabilityFilter(event.target.value)}>
                <option value="">全部</option>
                {STABILITY_LEVELS.map((item) => <option key={item} value={item}>{statusText(item, STABILITY_LABELS)}</option>)}
              </select>
            </label>
            <label>
              定位来源
              <select value={elementLocatorSourceFilter} onChange={(event) => setElementLocatorSourceFilter(event.target.value)}>
                <option value="">全部</option>
                {LOCATOR_SOURCES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              关键元素
              <select value={elementKeyFilter} onChange={(event) => setElementKeyFilter(event.target.value)}>
                <option value="">全部</option>
                <option value="true">关键</option>
                <option value="false">非关键</option>
              </select>
            </label>
            <div className="header-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setElementKeyword("");
                  setElementBusinessTypeFilter("");
                  setElementReviewFilter("");
                  setElementStabilityFilter("");
                  setElementLocatorSourceFilter("");
                  setElementKeyFilter("");
                }}
              >
                重置
              </button>
            </div>
          </FilterBar>
          <FormalElementsTable
            rows={filteredElements}
            selectedCodes={selectedElementCodes}
            visibleCodes={visibleElementCodes}
            allSelected={allElementsSelected}
            busy={busy}
            normalizedPageCode={normalizedPageCode}
            labels={{ stability: STABILITY_LABELS, review: REVIEW_STATUS_LABELS }}
            text={text}
            elementApiCode={elementApiCode}
            elementCodePolicyHint={elementCodePolicyHint}
            inferDisplayElementCode={inferDisplayElementCode}
            inferDisplayElementName={inferDisplayElementName}
            buildElementDetailLink={buildElementDetailLink}
            toggleSelection={toggleSelection}
            toggleAllSelection={toggleAllSelection}
            setSelectedCodes={setSelectedElementCodes}
            batchRemoveElements={() => void batchRemoveElements()}
            openElementPanel={openElementPanel}
          />
          </>
          ) : null}

          {isElementDetailRoute ? (
            <section className="panel element-detail-page">
              <div className="table-head">
                <div>
                  <h2>元素详情：{text(selectedElement.element_name)}</h2>
                  <p className={`mono ${selectedCodeHint ? "element-code-invalid" : "muted"}`}>{text(selectedElement.element_code || routeElementCode)}</p>
                </div>
                <div className="header-actions">
                  <button type="button" className={`button ${elementPanelMode === "detail" ? "" : "secondary"}`} onClick={() => setDetailMode("detail")}>
                    详情
                  </button>
                  <button type="button" className={`button ${elementPanelMode === "semantic" ? "" : "secondary"}`} onClick={() => setDetailMode("semantic")}>
                    语义/审核
                  </button>
                  <button type="button" className={`button ${elementPanelMode === "aliases" ? "" : "secondary"}`} onClick={() => setDetailMode("aliases")}>
                    别名
                  </button>
                  <button type="button" className={`button ${elementPanelMode === "locators" ? "" : "secondary"}`} onClick={() => setDetailMode("locators")}>
                    定位器
                  </button>
                  <button type="button" className={`button ${elementPanelMode === "refs" ? "" : "secondary"}`} onClick={() => setDetailMode("refs")}>
                    引用
                  </button>
                  <Link className="button secondary" to={elementListLink}>
                    返回列表
                  </Link>
                  <button type="button" className="button secondary" onClick={() => void markElementPending(selectedElement)} disabled={busy || !selectedElement.element_code}>
                    标记待治理
                  </button>
                </div>
              </div>

              {elementDetailLoading ? <p className="muted">正在加载元素详情...</p> : null}
              {!elementDetailLoading && !selectedElement.element_code ? (
                <p className="muted">暂时没有加载到该元素，请确认元素编码和项目是否匹配。</p>
              ) : null}

              {selectedCodeHint && selectedElement.element_code ? (
                <div className="element-governance-callout danger">
                  <strong>这个元素编码需要先修复</strong>
                  <p>当前编码不能进入测试点映射，也不能安全审核通过。请点击“修复编码”，把编码改成业务语义的 snake_case，例如 product_sn_input、search_button、password_toggle。</p>
                  <p className="mono">命名校验：{selectedCodeHint}</p>
                  <div className="header-actions">
                    <button
                      type="button"
                      className="button"
                      onClick={() => {
                        setSemanticForm((prev) => ({ ...prev, element_code: selectedSuggestedCode || prev.element_code }));
                        setDetailMode("semantic");
                      }}
                    >
                      修复编码
                    </button>
                    {selectedSuggestedCode ? (
                      <span className="muted">推荐编码：<span className="mono">{selectedSuggestedCode}</span></span>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {selectedReviewStatus === "pending" && selectedElement.element_code ? (
                <div className="element-governance-callout warning">
                  <strong>这个元素还处于待审核状态</strong>
                  <p>审核入口就在“语义/审核”页：确认元素编码、业务类型、定位来源和稳定等级后，把审核状态改为“已审核”并保存。只有已审核且稳定等级为 high/medium 的元素才会进入新的测试点映射链路。</p>
                  <button type="button" className="button secondary" onClick={() => setDetailMode("semantic")}>
                    去审核
                  </button>
                </div>
              ) : null}

              {selectedElement.element_code && elementPanelMode === "detail" ? (
                <>
                  <div className="summary-grid">
                    <div>
                      <strong>主定位器</strong>
                      <span className="mono">{text(selectedElement.locator_type)} = {text(selectedElement.locator_value)}</span>
                    </div>
                    <div>
                      <strong>备选定位器</strong>
                      <span className="mono">{text(selectedElement.backup_locator)}</span>
                    </div>
                    <div>
                      <strong>业务类型</strong>
                      <span>{text(selectedElement.business_type)}</span>
                    </div>
                    <div>
                      <strong>业务域</strong>
                      <span>{text(selectedElement.business_domain)}</span>
                    </div>
                    <div>
                      <strong>匹配策略</strong>
                      <span>{text(selectedElement.match_strategy)}</span>
                    </div>
                    <div>
                      <strong>route_scope</strong>
                      <span>{text(selectedElement.route_scope)}</span>
                    </div>
                    <div>
                      <strong>前端契约</strong>
                      <span>testid: {text(selectedElement.testid_value)} / qa: {text(selectedElement.qa_value)}</span>
                    </div>
                    <div>
                      <strong>锚点上下文</strong>
                      <span>{selectedElement.anchor_required ? "需要" : "不需要"}</span>
                    </div>
                    <div>
                      <strong>来源候选</strong>
                      <span className="mono">{text(selectedElement.origin_candidate_key)}</span>
                    </div>
                    <div>
                      <strong>别名</strong>
                      <span>{displayList(selectedElement.aliases_json)}</span>
                    </div>
                    <div>
                      <strong>语义标签</strong>
                      <span>{displayList(selectedElement.semantic_tags_json)}</span>
                    </div>
                    <div>
                      <strong>审核说明</strong>
                      <span>{text(selectedElement.governance_note)}</span>
                    </div>
                  </div>
                </>
              ) : null}

              {selectedElement.element_code && elementPanelMode === "semantic" ? (
                <>
                  <div className="form-grid">
                    <label>
                      元素编码
                      <input value={semanticForm.element_code} onChange={(event) => setSemanticForm((prev) => ({ ...prev, element_code: event.target.value }))} />
                    </label>
                    <label>
                      元素名称
                      <input value={semanticForm.element_name} onChange={(event) => setSemanticForm((prev) => ({ ...prev, element_name: event.target.value }))} />
                    </label>
                    <label>
                      业务类型
                      <select value={semanticForm.business_type} onChange={(event) => setSemanticForm((prev) => ({ ...prev, business_type: event.target.value }))}>
                        <option value="">请选择</option>
                        {BUSINESS_TYPES.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      业务域
                      <select value={semanticForm.business_domain} onChange={(event) => setSemanticForm((prev) => ({ ...prev, business_domain: event.target.value }))}>
                        <option value="">请选择</option>
                        {BUSINESS_DOMAINS.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      定位来源
                      <select value={semanticForm.locator_source} onChange={(event) => setSemanticForm((prev) => ({ ...prev, locator_source: event.target.value }))}>
                        <option value="">请选择</option>
                        {LOCATOR_SOURCES.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      匹配策略
                      <select value={semanticForm.match_strategy} onChange={(event) => setSemanticForm((prev) => ({ ...prev, match_strategy: event.target.value }))}>
                        {MATCH_STRATEGIES.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      稳定等级
                      <select value={semanticForm.stability_level} onChange={(event) => setSemanticForm((prev) => ({ ...prev, stability_level: event.target.value }))}>
                        {STABILITY_LEVELS.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      审核状态
                      <select value={semanticForm.review_status} onChange={(event) => setSemanticForm((prev) => ({ ...prev, review_status: event.target.value }))}>
                        {REVIEW_STATUSES.map((item) => (
                          <option key={item} value={item}>{statusText(item, REVIEW_STATUS_LABELS)}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      元素状态
                      <select value={semanticForm.status} onChange={(event) => setSemanticForm((prev) => ({ ...prev, status: event.target.value }))}>
                        {ELEMENT_STATUSES.map((item) => (
                          <option key={item} value={item}>{statusText(item, PAGE_ELEMENT_STATUS_LABELS)}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      关键元素
                      <select value={semanticForm.is_key_element ? "true" : "false"} onChange={(event) => setSemanticForm((prev) => ({ ...prev, is_key_element: event.target.value === "true" }))}>
                        <option value="false">否</option>
                        <option value="true">是</option>
                      </select>
                    </label>
                    <label>
                      需要页面锚点
                      <select value={semanticForm.anchor_required ? "true" : "false"} onChange={(event) => setSemanticForm((prev) => ({ ...prev, anchor_required: event.target.value === "true" }))}>
                        <option value="false">否</option>
                        <option value="true">是</option>
                      </select>
                    </label>
                    <label>
                      testid_value
                      <input value={semanticForm.testid_value} onChange={(event) => setSemanticForm((prev) => ({ ...prev, testid_value: event.target.value }))} />
                    </label>
                    <label>
                      qa_value
                      <input value={semanticForm.qa_value} onChange={(event) => setSemanticForm((prev) => ({ ...prev, qa_value: event.target.value }))} />
                    </label>
                    <label className="span-2">
                      route_scope
                      <input value={semanticForm.route_scope} onChange={(event) => setSemanticForm((prev) => ({ ...prev, route_scope: event.target.value }))} />
                    </label>
                    <label className="span-3">
                      审核说明
                      <textarea rows={3} value={semanticForm.governance_note} onChange={(event) => setSemanticForm((prev) => ({ ...prev, governance_note: event.target.value }))} />
                    </label>
                  </div>
                  {semanticCodeHint ? <p className="muted">命名校验：{semanticCodeHint}</p> : null}
                  <div className="header-actions">
                    <button type="button" className="button" onClick={() => void submitSemanticForm()} disabled={busy || !semanticForm.element_code.trim() || !semanticForm.element_name.trim() || Boolean(semanticCodeHint)}>
                      保存语义
                    </button>
                    <button type="button" className="button secondary" onClick={() => setSemanticForm(defaultSemanticForm(selectedElement))} disabled={busy}>
                      重置
                    </button>
                  </div>
                </>
              ) : null}

              {selectedElement.element_code && elementPanelMode === "aliases" ? (
                <>
                  <div className="form-grid">
                    <label className="span-3">
                      别名列表
                      <textarea rows={5} value={aliasForm.aliases_text} onChange={(event) => setAliasForm((prev) => ({ ...prev, aliases_text: event.target.value }))} placeholder="一行一个别名，或用逗号分隔" />
                    </label>
                    <label className="span-3">
                      语义标签
                      <textarea rows={4} value={aliasForm.semantic_tags_text} onChange={(event) => setAliasForm((prev) => ({ ...prev, semantic_tags_text: event.target.value }))} placeholder="例如：login, password, toggle" />
                    </label>
                  </div>
                  <div className="header-actions">
                    <button type="button" className="button" onClick={() => void submitAliasForm()} disabled={busy}>
                      保存别名
                    </button>
                    <button type="button" className="button secondary" onClick={() => setAliasForm(defaultAliasForm(selectedElement))} disabled={busy}>
                      重置
                    </button>
                  </div>
                </>
              ) : null}

              {selectedElement.element_code && elementPanelMode === "locators" ? (
                <>
                  <div className="summary-grid">
                    <div>
                      <strong>当前主定位器</strong>
                      <span className="mono">{text(selectedElement.locator_type)} = {text(selectedElement.locator_value)}</span>
                    </div>
                    <div>
                      <strong>role</strong>
                      <span>{text(selectedElement.role)}</span>
                    </div>
                    <div>
                      <strong>定位来源</strong>
                      <span>{text(selectedElement.locator_source)}</span>
                    </div>
                    <div>
                      <strong>备选定位器</strong>
                      <span className="mono">{text(selectedElement.backup_locator)}</span>
                    </div>
                    <div>
                      <strong>最新版本</strong>
                      <span>{text(selectedElement.latest_version_no || selectedElement.version)}</span>
                    </div>
                    <div>
                      <strong>更新时间</strong>
                      <span>{formatDateTime(selectedElement.updated_at)}</span>
                    </div>
                  </div>
                  <div className="table-panel">
                    <h3>正式元素定位器</h3>
                    <table>
                      <thead>
                        <tr>
                          <th>类型</th>
                          <th>定位值</th>
                          <th>role</th>
                          <th>来源</th>
                          <th>优先级</th>
                          <th>主定位器</th>
                          <th>健康状态</th>
                          <th>验证状态</th>
                          <th>创建人</th>
                          <th>更新时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        {elementLocators.length ? (
                          elementLocators.map((locator, index) => (
                            <tr key={String(locator.id || index)}>
                              <td>{text(locator.locator_type)}</td>
                              <td className="mono">{text(locator.locator_value)}</td>
                              <td>{text(locator.role)}</td>
                              <td>{text(locator.locator_source)}</td>
                              <td>{text(locator.priority)}</td>
                              <td>{locator.is_primary ? "是" : "否"}</td>
                              <td>{text(locator.health_status)}</td>
                              <td>{text(locator.verification_status)}</td>
                              <td>{text(locator.created_by)}</td>
                              <td>{formatDateTime(locator.updated_at || locator.created_at)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={10}>暂无扩展定位器。候选合并后会在这里同步为备选定位器。</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                    <h3>定位器版本快照</h3>
                    <table>
                      <thead>
                        <tr>
                          <th>版本</th>
                          <th>locator_type</th>
                          <th>locator_value</th>
                          <th>role</th>
                          <th>状态</th>
                          <th>变更人</th>
                          <th>变更说明</th>
                          <th>时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        {elementVersions.length ? (
                          elementVersions.map((version, index) => (
                            <tr key={String(version.id || index)}>
                              <td>{text(version.version_no)}</td>
                              <td>{text(version.locator_type)}</td>
                              <td className="mono">{text(version.locator_value)}</td>
                              <td>{text(version.role)}</td>
                              <td>{text(version.status)}</td>
                              <td>{text(version.changed_by)}</td>
                              <td>{text(version.change_summary)}</td>
                              <td>{formatDateTime(version.created_at)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={8}>暂无定位器版本快照。</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}

              {selectedElement.element_code && elementPanelMode === "refs" ? (
                <div className="table-panel">
                  <h3>元素引用</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>引用类型</th>
                        <th>引用键</th>
                        <th>来源</th>
                        <th>创建人</th>
                        <th>创建时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {elementRefs.length ? (
                        elementRefs.map((ref, index) => (
                          <tr key={String(ref.id || index)}>
                            <td>{text(ref.reference_type)}</td>
                            <td className="mono">{text(ref.reference_key)}</td>
                            <td>{text(ref.source)}</td>
                            <td>{text(ref.created_by)}</td>
                            <td>{formatDateTime(ref.created_at)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5}>暂无引用记录。</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
          ) : null}
        </>
      ) : null}

      {!loading && !errorText && !isDrilldownRoute && activeTab === "candidates" ? (
        <>
          <FilterBar>
            <label>
              候选状态
              <select value={promotionStatus} onChange={(event) => setPromotionStatus(event.target.value)}>
                <option value="">全部</option>
                <option value="pending">待审核</option>
                <option value="partially_promoted">部分处理</option>
                <option value="promoted">已处理</option>
                <option value="rejected">已拒绝</option>
              </select>
            </label>
            <label>
              session_id
              <input value={sessionFilter} onChange={(event) => setSessionFilter(event.target.value)} placeholder="可从录制历史带入" />
            </label>
          </FilterBar>

          <CandidateGroupsTable
            rows={candidateGroups}
            selectedKeys={selectedGroupKeys}
            visibleKeys={visibleGroupKeys}
            allSelected={allGroupsSelected}
            busy={busy}
            canMerge={Boolean(elements.length)}
            labels={{ action: RECOMMENDED_ACTION_LABELS, promotion: PROMOTION_STATUS_LABELS }}
            text={text}
            qualityTone={qualityTone}
            buildCandidateGroupDetailLink={buildCandidateGroupDetailLink}
            toggleSelection={toggleSelection}
            toggleAllSelection={toggleAllSelection}
            setSelectedKeys={setSelectedGroupKeys}
            batchRejectCandidateGroups={() => void batchRejectCandidateGroups()}
            batchRemoveCandidateGroups={() => void batchRemoveCandidateGroups()}
            openPromote={openPromote}
            openMerge={openMerge}
            openReject={(group) => {
              setRejectGroupTarget(group);
              setRejectNote("");
            }}
          />
        </>
      ) : null}

      {!loading && !errorText && isCandidateGroupRoute ? (
        <CandidateGroupDetailTable
          group={selectedGroup}
          rows={candidateRows}
          routeGroupKey={routeGroupKey}
          detailLoading={detailLoading}
          selectedCandidateKeys={selectedCandidateKeys}
          visibleCandidateKeys={visibleCandidateKeys}
          allSelected={allCandidatesSelected}
          busy={busy}
          canMerge={Boolean(elements.length)}
          candidateListLink={candidateListLink}
          labels={{ candidate: CANDIDATE_STATUS_LABELS, action: RECOMMENDED_ACTION_LABELS }}
          text={text}
          displayList={displayList}
          qualityTone={qualityTone}
          riskBar={riskBar}
          toggleSelection={toggleSelection}
          toggleAllSelection={toggleAllSelection}
          setSelectedCandidateKeys={setSelectedCandidateKeys}
          batchRemoveCandidateRows={() => void batchRemoveCandidateRows()}
          openPromote={openPromote}
          openMerge={openMerge}
          openReject={(group) => {
            setRejectGroupTarget(group);
            setRejectNote("");
          }}
          rejectOneCandidate={(candidate) => void rejectOneCandidate(candidate)}
        />
      ) : null}

      {!loading && !errorText && !isDrilldownRoute && activeTab === "history" ? (
        <>
          <FilterBar>
            <label>
              录制状态
              <select value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value)}>
                <option value="">全部</option>
                <option value="active">录制中</option>
                <option value="stopped">已停止</option>
                <option value="failed">失败</option>
              </select>
            </label>
          </FilterBar>
          <RecorderHistoryTable
            rows={historyRows}
            selectedSessionIds={selectedHistorySessionIds}
            visibleSessionIds={visibleHistorySessionIds}
            allSelected={allHistorySelected}
            busy={busy}
            recorderLink={recorderLink}
            labels={RECORDER_STATUS_LABELS}
            text={text}
            asRecord={asRecord}
            buildPlaybackDetailLink={buildPlaybackDetailLink}
            buildCandidateSessionLink={buildCandidateSessionLink}
            toggleSelection={toggleSelection}
            toggleAllSelection={toggleAllSelection}
            setSelectedSessionIds={setSelectedHistorySessionIds}
            batchRemoveHistoryRows={() => void batchRemoveHistoryRows()}
          />
        </>
      ) : null}

      {!loading && !errorText && isPlaybackRoute ? (
        <section className="panel">
          <div className="table-head">
            <div>
              <h2>录制回放</h2>
              <p className="muted">
                当前会话：<span className="mono">{text(playbackSession.session_id || routeSessionId)}</span>
                {playbackSession.status ? `（${text(playbackSession.status)}）` : ""}
              </p>
            </div>
            <div className="header-actions">
              <button type="button" className="button secondary" disabled={!playbackSteps.length || isPlaying} onClick={startReplayPreview}>
                播放步骤预览
              </button>
              <button type="button" className="button secondary" disabled={!isPlaying} onClick={stopReplayPreview}>
                停止
              </button>
              <button type="button" className="button secondary" disabled={!playbackSteps.length} onClick={resetReplayPreview}>
                重置
              </button>
              <Link className="button secondary" to={historyListLink}>
                返回录制历史
              </Link>
            </div>
          </div>
          <p className="muted">
            回放进度：{playbackSteps.length ? `${Math.min(playbackCursor, playbackSteps.length)}/${playbackSteps.length}` : "-"}
          </p>
          <ol className="recorder-steps">
            {playbackSteps.length ? (
              playbackSteps.map((step, index) => {
                const isActive = playbackCursor === index + 1;
                const isDone = playbackCursor > index + 1;
                return (
                  <li key={`history-playback-step-${index + 1}`} className={`recorder-step${isActive ? " active" : ""}${isDone ? " done" : ""}`}>
                    <span className="mono">#{text(step.index || index + 1)}</span>
                    <span>{describeStep(step)}</span>
                  </li>
                );
              })
            ) : (
              <li className="recorder-step">{playbackLoading ? "正在加载回放..." : "该录制会话暂无可回放步骤。"}</li>
            )}
          </ol>
          <h3>录制脚本</h3>
          <pre className="json-block">{playbackScript || "暂无脚本内容"}</pre>
          {playbackStderr ? (
            <>
              <h3>stderr</h3>
              <pre className="json-block">{playbackStderr}</pre>
            </>
          ) : null}
        </section>
      ) : null}

      {Object.keys(promoteGroup).length ? (
        <section className="governance-modal-backdrop" role="dialog" aria-label="提升候选元素">
          <div className="panel governance-modal large">
          <div className="modal-head">
            <div>
              <h2>提升为正式元素</h2>
              <p className="muted">确认编码、语义和主定位器后，候选才会进入正式元素资产。</p>
            </div>
            <button type="button" className="button secondary" onClick={() => setPromoteGroup({})} disabled={busy}>关闭</button>
          </div>
          <div className="modal-two-column">
            <aside className="candidate-summary-card">
              <strong>候选摘要</strong>
              <p>建议编码：<span className="mono">{text(promoteGroup.proposed_element_code)}</span></p>
              <p>建议名称：{text(promoteGroup.proposed_element_name)}</p>
              <p>类型猜测：{text(promoteGroup.business_type_guess)}</p>
              <p>主定位：<span className="mono">{text(promoteGroup.top_locator_type)} = {text(promoteGroup.top_locator_value)}</span></p>
              <p>route_scope：{text(promoteGroup.route_scope)}</p>
            </aside>
          <div className="form-grid">
            <label>
              元素编码
              <input value={promoteForm.element_code} onChange={(event) => setPromoteForm((prev) => ({ ...prev, element_code: event.target.value }))} />
            </label>
            <label>
              元素名称
              <input value={promoteForm.element_name} onChange={(event) => setPromoteForm((prev) => ({ ...prev, element_name: event.target.value }))} />
            </label>
            <label>
              业务类型
              <select value={promoteForm.business_type} onChange={(event) => setPromoteForm((prev) => ({ ...prev, business_type: event.target.value }))}>
                <option value="">请选择</option>
                {BUSINESS_TYPES.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              业务域
              <select value={promoteForm.business_domain} onChange={(event) => setPromoteForm((prev) => ({ ...prev, business_domain: event.target.value }))}>
                <option value="">请选择</option>
                {BUSINESS_DOMAINS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              定位类型
              <input value={promoteForm.locator_type} onChange={(event) => setPromoteForm((prev) => ({ ...prev, locator_type: event.target.value }))} />
            </label>
            <label className="span-2">
              定位值
              <input value={promoteForm.locator_value} onChange={(event) => setPromoteForm((prev) => ({ ...prev, locator_value: event.target.value }))} />
            </label>
            <label>
              role
              <input value={promoteForm.role} onChange={(event) => setPromoteForm((prev) => ({ ...prev, role: event.target.value }))} />
            </label>
            <label>
              定位来源
              <input value={promoteForm.locator_source} onChange={(event) => setPromoteForm((prev) => ({ ...prev, locator_source: event.target.value }))} />
            </label>
            <label>
              route_scope
              <input value={promoteForm.route_scope} onChange={(event) => setPromoteForm((prev) => ({ ...prev, route_scope: event.target.value }))} />
            </label>
            <label>
              关键元素
              <select
                value={promoteForm.is_key_element ? "true" : "false"}
                onChange={(event) => setPromoteForm((prev) => ({ ...prev, is_key_element: event.target.value === "true" }))}
              >
                <option value="false">否</option>
                <option value="true">是</option>
              </select>
            </label>
            <label>
              testid_value
              <input value={promoteForm.testid_value} onChange={(event) => setPromoteForm((prev) => ({ ...prev, testid_value: event.target.value }))} />
            </label>
            <label>
              qa_value
              <input value={promoteForm.qa_value} onChange={(event) => setPromoteForm((prev) => ({ ...prev, qa_value: event.target.value }))} />
            </label>
            <label className="span-3">
              审核说明
              <textarea rows={3} value={promoteForm.governance_note} onChange={(event) => setPromoteForm((prev) => ({ ...prev, governance_note: event.target.value }))} />
            </label>
          </div>
          </div>
          <div className="validation-list">
            {promoteValidationItems.map((item) => (
              <span key={item.label} className={item.ok ? "validation-ok" : "validation-blocked"}>
                {item.ok ? "通过" : "阻断"}：{item.label}
              </span>
            ))}
            {promoteCodeHint && promoteSuggestedCode ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => setPromoteForm((prev) => ({ ...prev, element_code: promoteSuggestedCode }))}
                disabled={busy}
              >
                使用推荐编码
              </button>
            ) : null}
          </div>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitPromote()} disabled={busy || promoteHasBlockingIssue}>
              确认提升
            </button>
            <button type="button" className="button secondary" onClick={() => setPromoteGroup({})} disabled={busy}>
              取消
            </button>
          </div>
          </div>
        </section>
      ) : null}

      {Object.keys(mergeGroup).length ? (
        <section className="governance-modal-backdrop" role="dialog" aria-label="合并候选元素">
          <div className="panel governance-modal">
          <h2>合并到已有正式元素</h2>
          <p className="muted">默认不覆盖主定位器，仅把候选定位器保存为正式元素的备选定位器。</p>
          <div className="form-grid">
            <label>
              目标正式元素
              <select value={mergeTargetCode} onChange={(event) => setMergeTargetCode(event.target.value)}>
                <option value="">请选择</option>
                {elements.map((item) => {
                  const code = String(item.element_code || "").trim();
                  return <option key={code} value={code}>{code} / {text(item.element_name)}</option>;
                })}
              </select>
            </label>
          </div>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitMerge()} disabled={busy || !mergeTargetCode.trim()}>
              确认合并
            </button>
            <button type="button" className="button secondary" onClick={() => setMergeGroup({})} disabled={busy}>
              取消
            </button>
          </div>
          </div>
        </section>
      ) : null}

      {Object.keys(rejectGroupTarget).length ? (
        <section className="governance-modal-backdrop" role="dialog" aria-label="拒绝候选分组">
          <div className="panel governance-modal small">
          <h2>拒绝候选分组</h2>
          <label>
            拒绝原因
            <select value={rejectNote.startsWith("低质量候选") || rejectNote.startsWith("重复候选") || rejectNote.startsWith("非业务元素") ? rejectNote : ""} onChange={(event) => setRejectNote(event.target.value)}>
              <option value="">请选择常用原因</option>
              <option value="低质量候选，暂不提升。">低质量候选</option>
              <option value="重复候选，已有正式元素覆盖。">重复候选</option>
              <option value="非业务元素，不参与测试点映射。">非业务元素</option>
            </select>
          </label>
          <label>
            审核说明
            <textarea rows={3} value={rejectNote} onChange={(event) => setRejectNote(event.target.value)} />
          </label>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitRejectGroup()} disabled={busy || !rejectNote.trim()}>
              确认拒绝
            </button>
            <button type="button" className="button secondary" onClick={() => setRejectGroupTarget({})} disabled={busy}>
              取消
            </button>
          </div>
          </div>
        </section>
      ) : null}
      {batchRejectOpen ? (
        <ConfirmDialog
          title="批量拒绝候选分组"
          description="拒绝后候选会保留审计记录，但不会进入正式元素资产。"
          busy={busy}
          confirmText="确认拒绝"
          details={[`将拒绝 ${selectedGroupKeys.length} 个候选分组`, "请填写审核说明，便于后续回溯。"]}
          noteLabel="审核说明"
          noteValue={rejectNote}
          noteRequired
          notePlaceholder="例如：低质量候选，暂不提升。"
          onNoteChange={setRejectNote}
          onCancel={() => {
            setBatchRejectOpen(false);
            setRejectNote("");
          }}
          onConfirm={() => void confirmBatchRejectCandidateGroups()}
        />
      ) : null}
      {Object.keys(candidateRejectTarget).length ? (
        <ConfirmDialog
          title="拒绝候选明细"
          description="该候选明细会标记为已拒绝，并保留审核原因。"
          busy={busy}
          confirmText="确认拒绝"
          details={[`候选 Key：${text(candidateRejectTarget.candidate_key)}`]}
          noteLabel="拒绝原因"
          noteValue={rejectNote}
          noteRequired
          notePlaceholder="请说明为什么该候选不可提升。"
          onNoteChange={setRejectNote}
          onCancel={() => {
            setCandidateRejectTarget({});
            setRejectNote("");
          }}
          onConfirm={() => void confirmRejectOneCandidate()}
        />
      ) : null}
      {deleteTarget ? (
        <ConfirmDialog
          title="确认物理删除"
          description="该操作会从资产库物理删除数据，请确认这些记录不再需要继续治理。"
          danger
          busy={busy}
          confirmText="确认删除"
          details={
            deleteTarget === "elements"
              ? [`将删除 ${selectedElementCodes.length} 个正式元素`, "相关版本、引用、健康检查和扩展定位器会一起删除"]
              : deleteTarget === "groups"
                ? [`将删除 ${selectedGroupKeys.length} 个候选分组`, "组内候选明细会一起删除"]
                : deleteTarget === "candidates"
                  ? [`将删除 ${selectedCandidateKeys.length} 条候选明细`, "如果分组没有剩余候选，分组也会被删除"]
                  : [`将删除 ${selectedHistorySessionIds.length} 条录制历史`, "关联候选和本地录制脚本产物会一起删除"]
          }
          onCancel={() => setDeleteTarget("")}
          onConfirm={() => {
            if (deleteTarget === "elements") {
              void confirmBatchRemoveElements();
            } else if (deleteTarget === "groups") {
              void confirmBatchRemoveCandidateGroups();
            } else if (deleteTarget === "candidates") {
              void confirmBatchRemoveCandidateRows();
            } else {
              void confirmBatchRemoveHistoryRows();
            }
          }}
        />
      ) : null}
    </main>
  );
}
