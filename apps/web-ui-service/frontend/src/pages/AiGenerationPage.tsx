import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  getPreviewTestPointDiagnostics,
  listProjects,
  precheckSelectedIntents,
  saveTestPointAssets,
  type PrecheckSelectedIntentsItem,
  previewTestPoints,
  type PreviewTestPointsResponse,
  type ProjectItem,
  uploadRequirementDocument,
} from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

interface GenerationForm {
  project: string;
  source: string;
  page: string;
  priority: string;
  title: string;
  requirement: string;
}

interface PipelineCandidate {
  key: string;
  intentId: string;
  title: string;
  summary: string;
  intentType: string;
  priority: string;
  expected: string;
  stepsSummary: string;
  detailUrl: string;
}

interface CandidatePrecheckState {
  status: "ok" | "warn" | "block";
  reasons: string[];
}

interface PipelineEvent {
  id: string;
  stage: "input" | "extract" | "candidate" | "generate";
  level: "info" | "success" | "error";
  message: string;
  at: string;
}

type StageState = "pending" | "running" | "success" | "error" | "block";
type StepId = 1 | 2 | 3 | 4;

const DEFAULT_FORM: GenerationForm = {
  project: DEFAULT_PROJECT_CODE,
  source: "manual",
  page: "",
  priority: "P1",
  title: "",
  requirement: "",
};

function nowText(): string {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function toText(value: unknown): string {
  return String(value || "").trim();
}

// 文档解析结果与用户手动补充用分隔符区分，便于追溯哪些是文档原文。
const DOC_RESULT_MARKER = "--- 文档解析结果 ---";
const USER_SUPPLEMENT_MARKER = "--- 用户补充 ---";

function mergeDocumentIntoRequirement(existing: string, parsedText: string): string {
  const supplementIndex = existing.indexOf(USER_SUPPLEMENT_MARKER);
  // 保留用户补充段：若已存在标记，取其后内容；否则把原有整段视作用户补充。
  const supplement =
    supplementIndex >= 0
      ? existing.slice(supplementIndex + USER_SUPPLEMENT_MARKER.length).replace(/^\s+/, "").trimEnd()
      : existing.trim();
  return `${DOC_RESULT_MARKER}\n${parsedText.trim()}\n\n${USER_SUPPLEMENT_MARKER}\n${supplement}`;
}

function normalizeSteps(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows: string[] = [];
  value.forEach((row) => {
    if (typeof row === "string") {
      const text = toText(row);
      if (text) {
        rows.push(text);
      }
      return;
    }
    if (row && typeof row === "object") {
      const record = row as Record<string, unknown>;
      const text = toText(record.raw_text || record.description || record.summary || record.action);
      if (text) {
        rows.push(text);
      }
    }
  });
  return rows;
}

function readPreviewItem(payload: PreviewTestPointsResponse): Record<string, unknown> {
  if (payload.item && typeof payload.item === "object") {
    return payload.item as Record<string, unknown>;
  }
  return payload as Record<string, unknown>;
}

function readPreviewId(payload: PreviewTestPointsResponse | null): string {
  if (!payload) {
    return "";
  }
  const item = readPreviewItem(payload);
  return toText(item.preview_id || (payload as Record<string, unknown>).preview_id);
}

function normalizeCandidates(payload: PreviewTestPointsResponse): PipelineCandidate[] {
  const item = readPreviewItem(payload);
  const requirementSpec = item.requirement_spec && typeof item.requirement_spec === "object"
    ? (item.requirement_spec as Record<string, unknown>)
    : {};
  const intents = Array.isArray(item.test_intents)
    ? item.test_intents
    : Array.isArray(requirementSpec.test_intents)
      ? requirementSpec.test_intents
      : [];
  const candidates: PipelineCandidate[] = [];

  intents.forEach((raw, index) => {
    if (!raw || typeof raw !== "object") {
      return;
    }
    const intent = raw as Record<string, unknown>;
    const intentId = toText(intent.intent_id) || `intent-${index + 1}`;
    const title = toText(intent.title) || toText(intent.summary) || `测试点 ${index + 1}`;
    const stepRows = normalizeSteps(intent.steps);
    const stepsSummary = toText(intent.steps_summary) || stepRows.slice(0, 2).join("，") || toText(intent.summary) || title;
    const summary = toText(intent.summary) || stepsSummary || title;
    candidates.push({
      key: `${intentId}-${index}`,
      intentId,
      title,
      summary,
      intentType: toText(intent.intent_type) || "functional",
      priority: toText(intent.priority) || "P1",
      expected: toText(intent.expected_result || intent.expected),
      stepsSummary,
      detailUrl: toText(intent.detail_url),
    });
  });

  return candidates;
}

function readQualityDecision(payload: PreviewTestPointsResponse | null): string {
  if (!payload) {
    return "unknown";
  }
  const item = readPreviewItem(payload);
  const requirementSpec = item.requirement_spec && typeof item.requirement_spec === "object"
    ? (item.requirement_spec as Record<string, unknown>)
    : {};
  const qualityGate = item.quality_gate && typeof item.quality_gate === "object"
    ? (item.quality_gate as Record<string, unknown>)
    : requirementSpec.quality_gate && typeof requirementSpec.quality_gate === "object"
      ? (requirementSpec.quality_gate as Record<string, unknown>)
      : {};
  return toText(qualityGate.decision).toLowerCase() || "unknown";
}

function clampStep(step: number): StepId {
  if (step <= 1) {
    return 1;
  }
  if (step >= 4) {
    return 4;
  }
  return step as StepId;
}

function stateText(state: StageState): string {
  if (state === "running") {
    return "执行中";
  }
  if (state === "success") {
    return "已完成";
  }
  if (state === "error") {
    return "失败";
  }
  if (state === "block") {
    return "阻断";
  }
  return "待执行";
}

function stateIcon(state: StageState): string {
  if (state === "success") {
    return "✓";
  }
  if (state === "running") {
    return "…";
  }
  if (state === "error" || state === "block") {
    return "X";
  }
  return "";
}

function sourceLabel(value: string): string {
  if (value === "manual") {
    return "手动输入";
  }
  if (value === "prd_text") {
    return "需求文档";
  }
  if (value === "openapi_spec") {
    return "接口文档";
  }
  if (value === "git_diff") {
    return "代码变更";
  }
  return value || "-";
}

function intentTypeLabel(value: string): string {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "功能";
  }
  const mapping: Record<string, string> = {
    functional: "功能",
    normal: "正常",
    abnormal: "异常",
    negative: "负向",
    boundary: "边界",
    format: "格式",
    api: "接口",
    security: "安全",
    performance: "性能",
    compatibility: "兼容",
    regression: "回归",
    smoke: "冒烟",
    interaction_exception: "交互异常",
    business_exception: "业务异常",
    non_empty: "非空校验",
    unknown: "未知",
  };
  if (mapping[normalized]) {
    return mapping[normalized];
  }
  if (["功能", "正常", "异常", "负向", "边界", "格式", "接口", "安全", "性能", "兼容", "回归", "冒烟", "交互异常", "业务异常", "非空校验", "未知"].includes(value)) {
    return value;
  }
  return value;
}

function normalizePrecheckStatus(value: unknown): "ok" | "warn" | "block" {
  const text = String(value || "").trim().toLowerCase();
  if (text === "block") {
    return "block";
  }
  if (text === "warn") {
    return "warn";
  }
  return "ok";
}

function toPrecheckState(item: PrecheckSelectedIntentsItem): CandidatePrecheckState {
  const status = normalizePrecheckStatus(item.status);
  const reasons = Array.isArray(item.reasons)
    ? item.reasons.map((row) => String(row || "").trim()).filter(Boolean)
    : [];
  return { status, reasons };
}

export function AiGenerationPage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [form, setForm] = useState<GenerationForm>(DEFAULT_FORM);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const [activeStep, setActiveStep] = useState<StepId>(1);
  const [extracting, setExtracting] = useState<boolean>(false);
  const [previewPayload, setPreviewPayload] = useState<PreviewTestPointsResponse | null>(null);
  const [candidates, setCandidates] = useState<PipelineCandidate[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [extractErrorText, setExtractErrorText] = useState<string>("");
  const [resultText, setResultText] = useState<string>("");
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [candidateView, setCandidateView] = useState<"card" | "table">("table");
  const [diagnosticsOpen, setDiagnosticsOpen] = useState<boolean>(false);
  const [previewDiagnostics, setPreviewDiagnostics] = useState<Record<string, unknown> | null>(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState<boolean>(false);
  const [prechecking, setPrechecking] = useState<boolean>(false);
  const [precheckErrorText, setPrecheckErrorText] = useState<string>("");
  const [precheckByIntentId, setPrecheckByIntentId] = useState<Record<string, CandidatePrecheckState>>({});
  const [lastSyncedSignature, setLastSyncedSignature] = useState<string>("");
  const [uploadingDoc, setUploadingDoc] = useState<boolean>(false);
  const [uploadDocError, setUploadDocError] = useState<string>("");
  const [uploadDocNote, setUploadDocNote] = useState<string>("");
  const [parsedText, setParsedText] = useState<string>("");   // 文档解析结果（只读,由 SectionTree 驱动）

  function appendEvent(event: Omit<PipelineEvent, "id" | "at">) {
    setEvents((prev) => [
      {
        ...event,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        at: nowText(),
      },
      ...prev,
    ]);
  }

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoadingProjects(true);
      try {
        const payload = await listProjects();
        if (cancelled) {
          return;
        }
        const sourceItems = Array.isArray(payload.items) ? payload.items : [];
        const payloadCodes = Array.isArray(payload.codes) ? payload.codes : [];
        const codes = projectOptions(payloadCodes.length ? payloadCodes : sourceItems.map((item) => item.project_code));
        const items = codes.map((code) => sourceItems.find((item) => String(item.project_code || "").trim() === code) || { project_code: code });
        setProjects(items);
        setForm((prev) => (codes.includes(prev.project) ? prev : { ...prev, project: codes[0] || DEFAULT_PROJECT_CODE }));
      } catch (error) {
        if (!cancelled) {
          setExtractErrorText(error instanceof Error ? error.message : "加载项目列表失败");
        }
      } finally {
        if (!cancelled) {
          setLoadingProjects(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const requirementText = parsedText || form.requirement.trim();
  const canExtract = Boolean(form.project.trim() && form.page.trim() && requirementText);
  const selectedCandidates = candidates.filter((item) => selectedKeys.includes(item.key));
  const selectedIntentIds = selectedCandidates.map((item) => item.intentId).filter(Boolean);

  const previewItem = previewPayload ? readPreviewItem(previewPayload) : {};
  const previewId = readPreviewId(previewPayload);
  const requirementSpec = previewItem.requirement_spec && typeof previewItem.requirement_spec === "object"
    ? (previewItem.requirement_spec as Record<string, unknown>)
    : {};
  const qualityGate = previewItem.quality_gate && typeof previewItem.quality_gate === "object"
    ? (previewItem.quality_gate as Record<string, unknown>)
    : requirementSpec.quality_gate && typeof requirementSpec.quality_gate === "object"
      ? (requirementSpec.quality_gate as Record<string, unknown>)
      : {};
  const qualityDecision = toText(qualityGate.decision).toLowerCase() || "unknown";
  const qualityBlocked = qualityDecision === "block";
  const blockers = Array.isArray(qualityGate.blockers) ? qualityGate.blockers : [];
  const scopeEstimate = previewItem.scope_estimate && typeof previewItem.scope_estimate === "object"
    ? (previewItem.scope_estimate as Record<string, unknown>)
    : {};
  const scopeLevel = toText(scopeEstimate.level).toLowerCase();
  const scopeMessage = toText(scopeEstimate.message);
  const parseConfidence = Number(previewItem.parse_confidence || requirementSpec.parse_confidence || 0);
  const selectedPrecheckStates = selectedCandidates
    .map((candidate) => precheckByIntentId[candidate.intentId])
    .filter(Boolean);
  const hasPrecheckBlock = selectedPrecheckStates.some((item) => item.status === "block");
  const canOpenAssetGovernance = Boolean(
    previewPayload
      && candidates.length
      && !qualityBlocked
      && !hasPrecheckBlock
      && !extracting
      && !prechecking,
  );

  const stageInput: StageState = canExtract ? "success" : "pending";
  const stageExtract: StageState = extracting ? "running" : (extractErrorText ? "error" : (previewPayload ? "success" : "pending"));
  const stageCandidate: StageState = qualityBlocked ? "block" : (candidates.length ? "success" : "pending");
  const stageAssetGovernance: StageState = qualityBlocked || hasPrecheckBlock
    ? "block"
    : (canOpenAssetGovernance ? "success" : "pending");

  const stepStates = useMemo(
    () => ({
      1: stageInput,
      2: stageExtract,
      3: stageCandidate,
      4: stageAssetGovernance,
    }),
    [stageAssetGovernance, stageCandidate, stageExtract, stageInput],
  );
  const completedStages = [stageInput, stageExtract, stageCandidate, stageAssetGovernance].filter((item) => item === "success").length;
  const progressPercent = Math.round((completedStages / 4) * 100);
  const selectedSignature = selectedIntentIds.slice().sort().join("|");
  const syncSignature = useMemo(
    () => [
      previewId,
      form.project.trim(),
      form.page.trim(),
      form.requirement.trim(),
      form.title.trim(),
      form.priority.trim(),
      form.source.trim(),
      selectedSignature,
      candidates.map((candidate) => candidate.key).join("|"),
    ].join("::"),
    [candidates, form.page, form.priority, form.project, form.requirement, form.source, form.title, previewId, selectedSignature],
  );

  useEffect(() => {
    if (!diagnosticsOpen || !previewId) {
      setPreviewDiagnostics(null);
      setLoadingDiagnostics(false);
      return;
    }
    let cancelled = false;
    async function loadDiagnostics() {
      setLoadingDiagnostics(true);
      try {
        const payload = await getPreviewTestPointDiagnostics(previewId);
        if (!cancelled) {
          setPreviewDiagnostics(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setPreviewDiagnostics({
            error: error instanceof Error ? error.message : "诊断信息加载失败",
          });
        }
      } finally {
        if (!cancelled) {
          setLoadingDiagnostics(false);
        }
      }
    }
    void loadDiagnostics();
    return () => {
      cancelled = true;
    };
  }, [diagnosticsOpen, previewId]);

  useEffect(() => {
    if (!previewPayload || !selectedCandidates.length || !form.project.trim() || !form.page.trim()) {
      setPrecheckByIntentId({});
      setPrecheckErrorText("");
      setPrechecking(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPrechecking(true);
      setPrecheckErrorText("");
      try {
        const response = await precheckSelectedIntents({
          project: form.project.trim(),
          page: form.page.trim(),
          preview_id: previewId,
          selected_intent_ids: selectedIntentIds,
          selected_candidates: previewId
            ? []
            : selectedCandidates.map((candidate) => ({
              intent_id: candidate.intentId,
              title: candidate.title,
              summary: candidate.summary,
              intent_type: candidate.intentType,
              priority: candidate.priority,
              steps: candidate.stepsSummary ? [candidate.stepsSummary] : [],
              expected_result: candidate.expected,
            })),
        });
        if (cancelled) {
          return;
        }
        const rows = Array.isArray(response.items) ? response.items : [];
        const nextMap: Record<string, CandidatePrecheckState> = {};
        rows.forEach((item) => {
          const intentId = toText(item.intent_id);
          if (!intentId) {
            return;
          }
          nextMap[intentId] = toPrecheckState(item);
        });
        setPrecheckByIntentId(nextMap);
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "候选预校验失败";
          setPrecheckErrorText(message);
        }
      } finally {
        if (!cancelled) {
          setPrechecking(false);
        }
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [previewPayload, previewId, selectedSignature, form.project, form.page]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (
      extracting
      || !previewPayload
      || !candidates.length
      || !form.project.trim()
      || !form.page.trim()
      || !syncSignature
      || syncSignature === lastSyncedSignature
    ) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const candidatesToSync = candidates;
        const allIntentIds = candidatesToSync.map((candidate) => candidate.intentId).filter(Boolean);
        const response = await saveTestPointAssets({
          project: form.project.trim(),
          page: form.page.trim(),
          requirement: parsedText
            ? `${parsedText}\n\n--- 用户补充 ---\n${form.requirement.trim()}`
            : form.requirement.trim(),
          title: form.title.trim(),
          priority: form.priority.trim() || "P1",
          source: form.source.trim() || "manual",
          preview_id: previewId,
          selected_intent_ids: allIntentIds,
          selected_candidates: previewId
            ? []
            : candidatesToSync.map((candidate) => ({
              intent_id: candidate.intentId,
              title: candidate.title,
              summary: candidate.summary,
              intent_type: candidate.intentType,
              priority: candidate.priority,
              steps: candidate.stepsSummary ? [candidate.stepsSummary] : [],
              expected: candidate.expected,
            })),
        });
        if (!cancelled) {
          const savedCount = Number(response.count || 0);
          appendEvent({
            stage: "candidate",
            level: "success",
            message: savedCount
              ? `已自动同步测试点资产 ${savedCount} 个资产，包含 ${allIntentIds.length} 条测试点。`
              : "测试点资产已自动同步。",
          });
          setLastSyncedSignature(syncSignature);
        }
      } catch (error) {
        if (!cancelled) {
          appendEvent({
            stage: "candidate",
            level: "error",
            message: error instanceof Error ? error.message : "测试点资产保存失败",
          });
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [extracting, previewPayload, previewId, candidates, form.project, form.page, form.requirement, form.title, form.priority, form.source, syncSignature, lastSyncedSignature]); // eslint-disable-line react-hooks/exhaustive-deps

  function getExtractDisabledReason(): string {
    if (extracting) {
      return "系统正在提取测试点，请稍候。";
    }
    if (!form.project.trim()) {
      return "请先选择项目。";
    }
    if (!form.page.trim()) {
      return "请先填写页面标识。";
    }
    if (!form.requirement.trim()) {
      return "请先输入需求描述。";
    }
    return "";
  }

  function getAssetGovernanceDisabledReason(): string {
    if (extracting) {
      return "请等待测试点提取完成。";
    }
    if (prechecking) {
      return "候选预校验中，请稍候。";
    }
    if (!previewPayload) {
      return "请先执行步骤 2 提取测试点。";
    }
    if (qualityBlocked) {
      return "质量门禁阻断，请先修复阻断项后再生成。";
    }
    if (hasPrecheckBlock) {
      return "候选预校验存在阻断项，请先修复后再进入资产生成。";
    }
    if (!candidates.length) {
      return "请先提取候选测试点。";
    }
    return "";
  }

  const extractDisabledReason = getExtractDisabledReason();
  const assetGovernanceDisabledReason = getAssetGovernanceDisabledReason();

  async function handleExtractPoints() {
    if (!canExtract || extracting) {
      return;
    }
    setExtracting(true);
    setExtractErrorText("");
    setPrecheckErrorText("");
    setPrecheckByIntentId({});
    setPreviewDiagnostics(null);
    setResultText("正在提取测试点...");
    appendEvent({ stage: "extract", level: "info", message: "已提交需求解析与测试点提取请求。" });
    setActiveStep(2);
    try {
      const response = await previewTestPoints({
        project: form.project.trim(),
        page: form.page.trim(),
        requirement: parsedText
          ? `${parsedText}\n\n--- 用户补充 ---\n${form.requirement.trim()}`
          : form.requirement.trim(),
        source: form.source.trim() || "manual",
      });
      const normalized = normalizeCandidates(response);
      const gateDecision = readQualityDecision(response);
      setPreviewPayload(response);
      setCandidates(normalized);
      setSelectedKeys(normalized.map((item) => item.key));
      setLastSyncedSignature("");
      if (gateDecision === "block") {
        setResultText(`提取完成：识别 ${normalized.length} 个测试点，但质量门禁阻断，需先处理后再进入资产治理。`);
      } else {
        setResultText(`提取完成：识别 ${normalized.length} 个测试点，已全部同步到测试点资产；请到资产中心审核后生成用例。`);
      }
      appendEvent({ stage: "extract", level: "success", message: `测试点提取完成，识别 ${normalized.length} 项。` });
      setActiveStep(3);
    } catch (error) {
      const message = error instanceof Error ? error.message : "测试点提取失败";
      setExtractErrorText(message);
      setPreviewPayload(null);
      setCandidates([]);
      setSelectedKeys([]);
      setLastSyncedSignature("");
      setPrecheckByIntentId({});
      setResultText("");
      appendEvent({ stage: "extract", level: "error", message });
    } finally {
      setExtracting(false);
    }
  }

  function toggleCandidate(key: string) {
    setSelectedKeys((prev) => {
      if (prev.includes(key)) {
        return prev.filter((item) => item !== key);
      }
      return [...prev, key];
    });
  }

  function selectAllCandidates() {
    setSelectedKeys(candidates.map((item) => item.key));
  }

  function clearAllCandidates() {
    setSelectedKeys([]);
  }

  function handleResetAll() {
    const firstProject = String(projects[0]?.project_code || DEFAULT_PROJECT_CODE).trim();
    setForm({ ...DEFAULT_FORM, project: firstProject });
    setActiveStep(1);
    setPreviewPayload(null);
    setPreviewDiagnostics(null);
    setCandidates([]);
    setSelectedKeys([]);
    setExtractErrorText("");
    setResultText("");
    setLastSyncedSignature("");
    setEvents([]);
    setCandidateView("table");
    setPrechecking(false);
    setPrecheckErrorText("");
    setPrecheckByIntentId({});
  }

  function goStepPrev() {
    setActiveStep((prev) => clampStep(prev - 1));
  }

  function goStepNext() {
    setActiveStep((prev) => clampStep(prev + 1));
  }

  const stickyPrimaryAction = activeStep <= 2
    ? {
      label: extracting ? "提取中..." : "提取测试点",
      onClick: handleExtractPoints,
      disabled: !canExtract || extracting,
    }
    : {
      label: "进入资产治理",
      onClick: () => setActiveStep(4),
      disabled: !canOpenAssetGovernance,
    };

  const nextDisabled = activeStep === 4
    || (activeStep === 1 && !canExtract)
    || (activeStep === 2 && (!previewPayload || extracting))
    || (activeStep === 3 && (!candidates.length || qualityBlocked));

  async function handleRequirementFileUpload(file: File | null): Promise<void> {
    if (!file) {
      return;
    }
    const projectCode = form.project.trim();
    if (!projectCode) {
      setUploadDocError("请先选择项目再上传需求文档。");
      setUploadDocNote("");
      return;
    }
    setUploadingDoc(true);
    setUploadDocError("");
    setUploadDocNote("");
    try {
      const response = await uploadRequirementDocument(projectCode, file);
      const item = response.item;
      const parsed = toText(item.parsed_text);
      if (parsed) {
        setParsedText(parsed);
      } else {
        setParsedText("");
      }
      if (item.parse_status === "parsed") {
        setUploadDocNote(`已解析并填入需求描述：${toText(item.filename) || "文档"}`);
      } else if (item.parse_status === "partial") {
        setUploadDocNote("部分解析成功，请检查解析结果后再提取测试点。");
      } else {
        setUploadDocError("未能从文档提取到有效内容，原始文件已存档，可手动输入需求。");
      }
    } catch (error) {
      setUploadDocError(error instanceof Error ? error.message : "需求文档上传失败");
    } finally {
      setUploadingDoc(false);
    }
  }

  function renderStepMain() {
    const uploadDisabled = uploadingDoc || extracting || !form.project.trim();
    if (activeStep === 1) {
      return (
        <section className="panel aiw-panel">
          <header className="aiw-panel-header">
            <h2>步骤 1：输入需求</h2>
            <p className="muted">请先补齐核心字段，系统才会启用提取能力。</p>
          </header>
          <div className="form-grid">
            <label>
              项目
              <select
                value={form.project}
                onChange={(event) => setForm((prev) => ({ ...prev, project: event.target.value }))}
                disabled={loadingProjects || extracting}
              >
                <option value="">请选择项目</option>
                {projects.map((project) => {
                  const code = String(project.project_code || "").trim();
                  return (
                    <option key={code} value={code}>
                      {code} {project.status ? `(${project.status})` : ""}
                    </option>
                  );
                })}
              </select>
            </label>
            <label>
              需求来源
              <select
                value={form.source}
                onChange={(event) => setForm((prev) => ({ ...prev, source: event.target.value }))}
                disabled={extracting}
              >
                <option value="manual">{sourceLabel("manual")}</option>
                <option value="prd_text">{sourceLabel("prd_text")}</option>
                <option value="openapi_spec">{sourceLabel("openapi_spec")}</option>
                <option value="git_diff">{sourceLabel("git_diff")}</option>
              </select>
            </label>
            <label>
              页面
              <input
                value={form.page}
                placeholder="例如 登录页"
                onChange={(event) => setForm((prev) => ({ ...prev, page: event.target.value }))}
                disabled={extracting}
              />
            </label>
            <label>
              优先级
              <select
                value={form.priority}
                onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
                disabled={extracting}
              >
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
              </select>
            </label>
            <label className="span-2">
              标题（可选）
              <input
                value={form.title}
                placeholder="例如 登录基础校验"
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                disabled={extracting}
              />
            </label>
            <div className="span-3 aiw-doc-upload">
              <label className={`button aiw-doc-upload-btn${uploadDisabled ? " is-disabled" : ""}`}>
                {uploadingDoc ? "解析中…" : "上传需求文档"}
                <input
                  type="file"
                  accept=".docx,.pdf,.md"
                  style={{ display: "none" }}
                  disabled={uploadDisabled}
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    void handleRequirementFileUpload(file);
                    event.target.value = "";
                  }}
                />
              </label>
              <span className="muted aiw-doc-upload-hint">
                支持 .docx / .pdf / .md，≤20MB；解析为结构化 Markdown 后填入下方需求描述
              </span>
              {uploadDocError ? <p className="error aiw-doc-upload-msg">{uploadDocError}</p> : null}
              {uploadDocNote ? <p className="muted aiw-doc-upload-msg">{uploadDocNote}</p> : null}
            </div>
            {parsedText ? (
              <div className="span-3 aiw-parsed-preview">
                <div className="aiw-parsed-label">文档解析结果（由章节选择控制，不可编辑）</div>
                <pre className="aiw-parsed-text">{parsedText}</pre>
              </div>
            ) : null}
            <label className="span-3">
              需求描述
              <textarea
                value={form.requirement}
                rows={8}
                placeholder="输入需求文本，至少包含业务目标、关键流程与验收点。"
                onChange={(event) => setForm((prev) => ({ ...prev, requirement: event.target.value }))}
                disabled={extracting}
              />
            </label>
          </div>
        </section>
      );
    }

    if (activeStep === 2) {
      return (
        <section className="panel aiw-panel">
          <header className="aiw-panel-header">
            <h2>步骤 2：提取测试点</h2>
            <p className="muted">调用解析能力生成需求规格与候选测试点。</p>
          </header>
          <div className="aiw-action-row">
            <button type="button" className="button" onClick={handleExtractPoints} disabled={!canExtract || extracting}>
              {extracting ? "提取中..." : "提取测试点"}
            </button>
            <p className="muted">{extractDisabledReason || "输入完整后可执行提取。"}</p>
          </div>
          {extractErrorText ? (
            <section className="aiw-error-box">
              <strong>提取失败</strong>
              <p className="error">{extractErrorText}</p>
              <p className="muted">请检查需求输入、页面标识及解析服务状态后重试。</p>
            </section>
          ) : null}
          <div className="stage-metrics">
            <article className="metric-card metric-tone-info">
              <p>解析置信度</p>
              <strong>{Number.isFinite(parseConfidence) && parseConfidence > 0 ? `${Math.round(parseConfidence * 100)}%` : "-"}</strong>
            </article>
            <article className="metric-card metric-tone-accent">
              <p>识别测试点</p>
              <strong>{candidates.length}</strong>
            </article>
            <article className={`metric-card ${qualityBlocked ? "metric-tone-danger" : "metric-tone-success"}`}>
              <p>质量门禁</p>
              <strong className={qualityBlocked ? "metric-bad" : "metric-good"}>
                {qualityDecision === "allow" ? "通过" : qualityBlocked ? "阻断" : "-"}
              </strong>
            </article>
            <article className="metric-card metric-tone-warning">
              <p>门禁阻断项</p>
              <strong>{blockers.length}</strong>
            </article>
          </div>
          {scopeMessage && (scopeLevel === "warn" || scopeLevel === "block") ? (
            <section className={`aiw-warning-box ${scopeLevel === "block" ? "" : "aiw-warning-box-soft"}`}>
              <strong>{scopeLevel === "block" ? "输入范围超上限" : "输入范围偏大"}</strong>
              <p className="muted">{scopeMessage}</p>
            </section>
          ) : null}
          {qualityBlocked ? (
            <section className="aiw-warning-box">
              <strong>门禁阻断，当前不可进入生成阶段。</strong>
              {blockers.length ? (
                <ul className="candidate-list">
                  {blockers.map((item, index) => {
                    const row = item as Record<string, unknown>;
                    return <li key={`gate-${index}`}>{toText(row.message || row.reason || row.code || `阻断项 ${index + 1}`)}</li>;
                  })}
                </ul>
              ) : (
                <p className="muted">未返回详细阻断项，请检查需求输入完整性。</p>
              )}
            </section>
          ) : null}
        </section>
      );
    }

    if (activeStep === 3) {
      return (
        <section className="panel aiw-panel">
          <header className="aiw-panel-header aiw-panel-header-row">
            <div>
              <h2>步骤 3：候选测试点可视化</h2>
              <p className="muted">默认表格视图，适合批量筛选与快速决策。</p>
            </div>
            <div className="header-actions">
              <button
                type="button"
                className={`button secondary ${candidateView === "card" ? "is-selected-view" : ""}`}
                onClick={() => setCandidateView("card")}
              >
                卡片视图
              </button>
              <button
                type="button"
                className={`button secondary ${candidateView === "table" ? "is-selected-view" : ""}`}
                onClick={() => setCandidateView("table")}
              >
                表格视图
              </button>
              <button type="button" className="button secondary" onClick={selectAllCandidates} disabled={!candidates.length}>
                全选预校验
              </button>
              <button type="button" className="button secondary" onClick={clearAllCandidates} disabled={!selectedCandidates.length}>
                清空
              </button>
            </div>
          </header>

          <p className="muted">当前已选用于预校验：{selectedCandidates.length}；测试点资产会保存全部 {candidates.length} 条。</p>
          {selectedCandidates.length ? (
            precheckErrorText ? (
              <section className="aiw-error-box aiw-step-error">
                <strong>预校验失败</strong>
                <p className="error">{precheckErrorText}</p>
              </section>
            ) : (
              <p className="muted">预校验：{prechecking ? "校验中..." : "已完成"}</p>
            )
          ) : null}

          {candidateView === "card" ? (
            <section className="candidate-grid">
              {candidates.length ? (
                candidates.map((candidate, index) => {
                  const selected = selectedKeys.includes(candidate.key);
                  const precheck = precheckByIntentId[candidate.intentId];
                  const precheckStatus = precheck?.status || "ok";
                  return (
                    <article
                      key={candidate.key}
                      className={`candidate-card ${selected ? "is-selected" : ""} ${precheckStatus === "block" ? "is-precheck-block" : precheckStatus === "warn" ? "is-precheck-warn" : ""}`}
                      style={{
                        position: "relative",
                        display: "flex",
                        flexDirection: "column",
                        gap: "14px",
                        minHeight: "380px",
                        padding: "16px",
                        overflow: "hidden",
                        background: "linear-gradient(180deg, #ffffff 0%, #fbfdff 100%)",
                      }}
                    >
                      <header
                        className="candidate-header"
                        style={{
                          display: "grid",
                          gridTemplateColumns: "minmax(0, 1fr) auto",
                          gap: "12px",
                          alignItems: "start",
                        }}
                      >
                        <div className="candidate-header-main" style={{ display: "flex", minWidth: 0 }}>
                          <label
                            className="candidate-check"
                            style={{
                              display: "flex",
                              flex: "1 1 auto",
                              gap: "12px",
                              alignItems: "flex-start",
                              minWidth: 0,
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selected}
                              disabled={extracting}
                              onChange={() => toggleCandidate(candidate.key)}
                              style={{
                                width: "20px",
                                height: "20px",
                                marginTop: "2px",
                                flex: "0 0 20px",
                                accentColor: "#2563eb",
                              }}
                            />
                            <span className="candidate-title-wrap" style={{ display: "flex", flex: "1 1 auto", minWidth: 0 }}>
                              <span className="candidate-title-line" style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0, width: "100%" }}>
                                <strong
                                  className="candidate-title"
                                  style={{
                                    display: "block",
                                    minWidth: 0,
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {candidate.title}
                                </strong>
                              </span>
                            </span>
                          </label>
                        </div>
                        <div
                          className="candidate-header-meta"
                          style={{ display: "inline-flex", alignItems: "center", justifyContent: "flex-end", gap: "8px", flexWrap: "wrap", alignSelf: "start" }}
                        >
                          <span className="candidate-meta-chip candidate-meta-chip-compact" style={{ minHeight: "24px", padding: "0 8px" }}>
                            {candidate.priority || "P1"}
                          </span>
                          <span
                            className={`candidate-status-chip status-${precheckStatus}`}
                            style={{
                              minHeight: "24px",
                              padding: "0 10px",
                              borderRadius: "999px",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {precheckStatus === "block" ? "阻断" : precheckStatus === "warn" ? "提示" : "通过"}
                          </span>
                        </div>
                      </header>
                      {precheckStatus !== "ok" ? (
                        <section
                          className={`candidate-precheck-banner status-${precheckStatus}`}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            justifyContent: "space-between",
                            gap: "12px",
                            padding: "12px",
                            borderRadius: "8px",
                          }}
                        >
                          <div className="candidate-precheck-flag" style={{ display: "grid", gap: "4px", minWidth: 0 }}>
                            <span className="candidate-precheck-label">
                              {precheckStatus === "block" ? "预校验阻断" : "预校验提示"}
                            </span>
                            <p style={{ margin: 0 }}>
                              {precheck?.reasons?.[0] || "当前候选存在需要处理的预校验问题。"}
                            </p>
                          </div>
                          {precheck && precheck.reasons.length > 1 ? (
                            <span
                              className="candidate-precheck-count"
                              style={{ flex: "0 0 auto", minHeight: "24px", padding: "0 8px", borderRadius: "999px", display: "inline-flex", alignItems: "center" }}
                            >
                              +{precheck.reasons.length - 1}
                            </span>
                          ) : null}
                        </section>
                      ) : null}
                      <div className="candidate-modules" style={{ display: "grid", gap: "14px" }}>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">测试意图</span>
                          <p className="candidate-section-text">
                            {candidate.summary || candidate.title}
                          </p>
                        </section>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">步骤概览</span>
                          <p className="candidate-section-text">
                            {candidate.stepsSummary || "完整步骤已在服务端保留，生成时按测试点 ID 读取。"}
                          </p>
                        </section>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">预期结果</span>
                          <p className="candidate-section-text">
                            {candidate.expected || "未返回预期结果。"}
                          </p>
                        </section>
                      </div>
                      {precheck && precheck.reasons.length ? (
                        <details className="candidate-reason-toggle">
                          <summary>查看预校验原因（{precheck.reasons.length}）</summary>
                          <ul className="candidate-reason-list">
                            {precheck.reasons.slice(0, 3).map((reason) => (
                              <li key={`${candidate.key}-${reason}`}>{reason}</li>
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </article>
                  );
                })
              ) : (
                <p className="muted">尚未提取测试点。请先完成步骤 2。</p>
              )}
            </section>
          ) : (
            <section className="table-panel">
              <table className="candidate-table">
                <thead>
                  <tr>
                    <th>选择</th>
                    <th>意图 ID</th>
                    <th>标题</th>
                    <th>类型</th>
                    <th>优先级</th>
                    <th>步骤概览</th>
                    <th>预期结果</th>
                    <th>预校验</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.length ? (
                    candidates.map((candidate) => {
                      const selected = selectedKeys.includes(candidate.key);
                      const precheck = precheckByIntentId[candidate.intentId];
                      const precheckStatus = precheck?.status || "ok";
                      return (
                        <tr
                          key={`row-${candidate.key}`}
                          className={`${selected ? "is-active" : ""} ${precheckStatus === "block" ? "is-precheck-block" : precheckStatus === "warn" ? "is-precheck-warn" : ""}`}
                        >
                          <td>
                            <input
                              type="checkbox"
                              checked={selected}
                              disabled={extracting}
                              onChange={() => toggleCandidate(candidate.key)}
                            />
                          </td>
                          <td className="mono">{candidate.intentId}</td>
                          <td>{candidate.title}</td>
                          <td>{intentTypeLabel(candidate.intentType || "")}</td>
                          <td>{candidate.priority || "P1"}</td>
                          <td>{candidate.stepsSummary || "-"}</td>
                          <td>{candidate.expected || "-"}</td>
                          <td className={`aiw-precheck-cell status-${precheckStatus}`}>
                            {precheckStatus === "ok" ? "通过" : precheckStatus === "block" ? "阻断" : "提示"}
                            {precheck && precheck.reasons.length ? `：${precheck.reasons[0]}` : ""}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={8} className="asset-empty">
                        <div className="aiw-empty-state">
                          <strong>暂无候选测试点</strong>
                          <p>请先完成步骤 2 提取测试点。</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          )}
        </section>
      );
    }

    return (
      <section className="panel aiw-panel">
        <header className="aiw-panel-header">
          <h2>步骤 4：进入资产治理</h2>
          <p className="muted">直接生成入口已下线。正式用例必须从测试点资产中心的已通过测试点生成。</p>
        </header>
        <div className="aiw-action-row">
          <Link className="button" to={`/assets/test-points?project=${encodeURIComponent(normalizeProjectCode(form.project))}`}>
            打开测试点资产中心
          </Link>
          <p className="muted">{assetGovernanceDisabledReason || "请在资产中心完成审核，再使用“生成已通过用例”。"}</p>
        </div>

        {resultText ? <p>{resultText}</p> : null}
        {extractErrorText ? (
          <section className="aiw-error-box aiw-step-error">
            <strong>提取失败</strong>
            <p className="error">{extractErrorText}</p>
            <p className="muted">请根据失败原因修正输入后重试。</p>
          </section>
        ) : null}

        <div className="generation-next-actions">
          <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(normalizeProjectCode(form.project))}`}>
            查看测试点资产
          </Link>
          <Link className="button secondary" to="/cases/review">进入审核队列</Link>
          <Link className="button secondary" to="/cases">查看用例中心</Link>
        </div>

        <div className="aiw-empty-state">
          <strong>生成入口已收口</strong>
          <p>当前页面只负责需求解析和测试点资产同步；用例生成统一在测试点资产中心完成。</p>
        </div>
      </section>
    );
  }

  return (
    <main className="shell aiw-page">
      <header className="panel aiw-top-header unified-topbar">
        <div>
          <h1>需求到用例单链工作台</h1>
          <p className="muted">主链路：输入需求 → 提取测试点 → 同步测试点资产 → 审核后生成用例</p>
        </div>
        <div className="header-actions unified-topbar-actions">
          <button type="button" className="button" onClick={stickyPrimaryAction.onClick} disabled={stickyPrimaryAction.disabled}>
            {stickyPrimaryAction.label}
          </button>
          <Link className="button secondary" to="/ai-generation/history">
            查看生成历史
          </Link>
          <button type="button" className="button secondary" onClick={() => setDiagnosticsOpen((prev) => !prev)}>
            {diagnosticsOpen ? "收起诊断面板" : "打开诊断面板"}
          </button>
          <button type="button" className="button secondary" onClick={handleResetAll} disabled={extracting}>
            重置全部
          </button>
        </div>
      </header>

      {diagnosticsOpen ? (
        <section className="panel aiw-diagnostics-overlay" role="dialog" aria-label="诊断面板">
          <header className="aiw-diagnostics-header">
            <h2>诊断面板</h2>
            <button type="button" className="button secondary" onClick={() => setDiagnosticsOpen(false)}>
              关闭
            </button>
          </header>
          <div className="aiw-diagnostics-grid">
            <section>
              <h3>事件时间线</h3>
              {events.length ? (
                <ul className="pipeline-events">
                  {events.slice(0, 10).map((event) => (
                    <li key={event.id} className={`event-${event.level}`}>
                      <span className="event-time">{event.at}</span>
                      <span className="event-stage">{event.stage}</span>
                      <span>{event.message}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">尚未触发链路动作。</p>
              )}
            </section>
            <section>
              <h3>原始响应</h3>
              <details>
                <summary>查看步骤 2 轻量响应</summary>
                <pre className="json-block">{JSON.stringify(previewPayload || {}, null, 2)}</pre>
              </details>
              <details>
                <summary>按需查看解析诊断</summary>
                <pre className="json-block">
                  {loadingDiagnostics
                    ? "诊断信息加载中..."
                    : JSON.stringify(previewDiagnostics || { message: previewId ? "暂无诊断信息" : "请先提取测试点" }, null, 2)}
                </pre>
              </details>
            </section>
          </div>
        </section>
      ) : null}

      <div className="aiw-layout">
        <aside className="panel aiw-step-rail">
          <h2>执行步骤</h2>
          <div className="aiw-step-list">
            {[1, 2, 3, 4].map((id) => {
              const stepId = id as StepId;
              const titles: Record<StepId, string> = {
                1: "输入需求",
                2: "提取测试点",
                3: "筛选候选",
                4: "资产治理",
              };
              const state = stepStates[stepId];
                return (
                  <button
                    key={`step-${stepId}`}
                    type="button"
                    className={`aiw-step-item ${activeStep === stepId ? "is-active" : ""} is-${state}`}
                    onClick={() => setActiveStep(stepId)}
                  >
                    <span className="aiw-step-no">步骤 {stepId}</span>
                    <strong>{titles[stepId]}</strong>
                    <em>{stateText(state)}</em>
                    <span className={`aiw-step-icon is-${state}`} aria-hidden="true">{stateIcon(state)}</span>
                  </button>
                );
              })}
            </div>
          </aside>

        <section className="aiw-main">
          <section className="panel aiw-progress-card">
            <div className="aiw-progress-track" aria-hidden>
              <div className="aiw-progress-fill" style={{ width: `${progressPercent}%` }} />
            </div>
          </section>

          {renderStepMain()}
        </section>

        <aside className="panel aiw-context-rail">
          <section className="aiw-context-card">
            <h3>质量门禁</h3>
            <p className={`aiw-context-kpi ${qualityBlocked ? "metric-bad" : "metric-good"}`}>
              {qualityDecision === "allow" ? "通过" : qualityBlocked ? "阻断" : "-"}
            </p>
            <p className="muted">阻断项：{blockers.length}</p>
          </section>

          <section className="aiw-context-card">
            <h3>关键指标</h3>
            <ul className="simple-list">
              <li className="simple-list-item">
                <span>解析置信度</span>
                <strong>{Number.isFinite(parseConfidence) && parseConfidence > 0 ? `${Math.round(parseConfidence * 100)}%` : "-"}</strong>
              </li>
              <li className="simple-list-item">
                <span>候选总数</span>
                <strong>{candidates.length}</strong>
              </li>
              <li className="simple-list-item">
                <span>预校验已选</span>
                <strong>{selectedCandidates.length}</strong>
              </li>
            </ul>
          </section>

        </aside>
      </div>

      <section className="aiw-sticky-bar">
        <div className="aiw-sticky-inner">
          <span className="muted">步骤进度 {completedStages}/4 · 已选用于预校验 {selectedCandidates.length}</span>
          <div className="header-actions">
            <button type="button" className="button secondary" onClick={goStepPrev} disabled={activeStep === 1}>
              上一步
            </button>
            <button type="button" className="button secondary" onClick={goStepNext} disabled={nextDisabled}>
              下一步
            </button>
            <button type="button" className="button" onClick={stickyPrimaryAction.onClick} disabled={stickyPrimaryAction.disabled}>
              {stickyPrimaryAction.label}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
