import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  generateCase,
  listProjects,
  precheckSelectedIntents,
  saveTestPointAssets,
  type GenerateCaseResponse,
  type PrecheckSelectedIntentsItem,
  previewTestPoints,
  type PreviewTestPointsResponse,
  type ProjectItem,
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
  precondition: string;
  expected: string;
  steps: string[];
  stepsHint: string[];
  involvedElements: string[];
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

const MAX_SELECTED = 20;

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

function normalizeComparableText(value: string): string {
  return String(value || "")
    .toLowerCase()
    .replace(/[\s\u3000.,;:!?，。；：、/\\_|\-—()（）\[\]【】{}<>《》"'“”‘’·~`]+/g, "");
}

function isRedundantSummary(title: string, summary: string): boolean {
  const normalizedTitle = normalizeComparableText(title);
  const normalizedSummary = normalizeComparableText(summary);
  if (!normalizedTitle || !normalizedSummary) {
    return true;
  }
  if (normalizedTitle === normalizedSummary) {
    return true;
  }
  return normalizedTitle.includes(normalizedSummary) || normalizedSummary.includes(normalizedTitle);
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

function normalizeStepHints(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows: string[] = [];
  value.forEach((row) => {
    const text = toText(row);
    if (text && !rows.includes(text)) {
      rows.push(text);
    }
  });
  return rows;
}

function readCaseIds(response: GenerateCaseResponse): string[] {
  const items = Array.isArray(response.items) ? response.items : [];
  const fromItems = items
    .map((item) => String((item as Record<string, unknown>).case_id || "").trim())
    .filter(Boolean);
  if (fromItems.length) {
    return fromItems;
  }
  const one = String((response.item as Record<string, unknown> | undefined)?.case_id || "").trim();
  return one ? [one] : [];
}

function readPreviewItem(payload: PreviewTestPointsResponse): Record<string, unknown> {
  if (payload.item && typeof payload.item === "object") {
    return payload.item as Record<string, unknown>;
  }
  return payload as Record<string, unknown>;
}

function normalizeCandidates(payload: PreviewTestPointsResponse): PipelineCandidate[] {
  const item = readPreviewItem(payload);
  const requirementSpec = item.requirement_spec && typeof item.requirement_spec === "object"
    ? (item.requirement_spec as Record<string, unknown>)
    : {};
  const intents = Array.isArray(requirementSpec.test_intents) ? requirementSpec.test_intents : [];
  const candidates: PipelineCandidate[] = [];

  intents.forEach((raw, index) => {
    if (!raw || typeof raw !== "object") {
      return;
    }
    const intent = raw as Record<string, unknown>;
    const intentId = toText(intent.intent_id) || `intent-${index + 1}`;
    const title = toText(intent.title) || toText(intent.summary) || `测试点 ${index + 1}`;
    const summary = toText(intent.summary) || title;
    const involvedElements = Array.isArray(intent.involved_elements)
      ? intent.involved_elements.map((itemValue) => toText(itemValue)).filter(Boolean)
      : [];
    candidates.push({
      key: `${intentId}-${index}`,
      intentId,
      title,
      summary,
      intentType: toText(intent.intent_type) || "functional",
      priority: toText(intent.priority) || "P1",
      precondition: toText(intent.precondition),
      expected: toText(intent.expected_result || intent.expected),
      steps: normalizeSteps(intent.steps),
      stepsHint: normalizeStepHints(intent.steps_hint),
      involvedElements,
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
  const qualityGate = requirementSpec.quality_gate && typeof requirementSpec.quality_gate === "object"
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
  const [generating, setGenerating] = useState<boolean>(false);
  const [previewPayload, setPreviewPayload] = useState<PreviewTestPointsResponse | null>(null);
  const [candidates, setCandidates] = useState<PipelineCandidate[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [generatePayload, setGeneratePayload] = useState<GenerateCaseResponse | null>(null);
  const [extractErrorText, setExtractErrorText] = useState<string>("");
  const [generateErrorText, setGenerateErrorText] = useState<string>("");
  const [resultText, setResultText] = useState<string>("");
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [candidateView, setCandidateView] = useState<"card" | "table">("table");
  const [diagnosticsOpen, setDiagnosticsOpen] = useState<boolean>(false);
  const [prechecking, setPrechecking] = useState<boolean>(false);
  const [precheckErrorText, setPrecheckErrorText] = useState<string>("");
  const [precheckByIntentId, setPrecheckByIntentId] = useState<Record<string, CandidatePrecheckState>>({});
  const [lastSyncedSignature, setLastSyncedSignature] = useState<string>("");

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

  const canExtract = Boolean(form.project.trim() && form.page.trim() && form.requirement.trim());
  const selectedCandidates = candidates.filter((item) => selectedKeys.includes(item.key));
  const selectedIntentIds = selectedCandidates.map((item) => item.intentId).filter(Boolean);

  const previewItem = previewPayload ? readPreviewItem(previewPayload) : {};
  const requirementSpec = previewItem.requirement_spec && typeof previewItem.requirement_spec === "object"
    ? (previewItem.requirement_spec as Record<string, unknown>)
    : {};
  const qualityGate = requirementSpec.quality_gate && typeof requirementSpec.quality_gate === "object"
    ? (requirementSpec.quality_gate as Record<string, unknown>)
    : {};
  const qualityDecision = toText(qualityGate.decision).toLowerCase() || "unknown";
  const qualityBlocked = qualityDecision === "block";
  const blockers = Array.isArray(qualityGate.blockers) ? qualityGate.blockers : [];
  const parseConfidence = Number(requirementSpec.parse_confidence || 0);
  const selectedPrecheckStates = selectedCandidates
    .map((candidate) => precheckByIntentId[candidate.intentId])
    .filter(Boolean);
  const hasPrecheckBlock = selectedPrecheckStates.some((item) => item.status === "block");
  const canGenerate = Boolean(
    selectedCandidates.length
      && previewPayload
      && !qualityBlocked
      && !hasPrecheckBlock
      && !extracting
      && !generating
      && !prechecking,
  );

  const stageInput: StageState = canExtract ? "success" : "pending";
  const stageExtract: StageState = extracting ? "running" : (extractErrorText ? "error" : (previewPayload ? "success" : "pending"));
  const stageCandidate: StageState = qualityBlocked ? "block" : (candidates.length ? "success" : "pending");
  const stageGenerate: StageState = qualityBlocked || hasPrecheckBlock
    ? "block"
    : (generating ? "running" : (generateErrorText ? "error" : (generatePayload ? "success" : "pending")));

  const stepStates = useMemo(
    () => ({
      1: stageInput,
      2: stageExtract,
      3: stageCandidate,
      4: stageGenerate,
    }),
    [stageCandidate, stageExtract, stageGenerate, stageInput],
  );
  const completedStages = [stageInput, stageExtract, stageCandidate, stageGenerate].filter((item) => item === "success").length;
  const progressPercent = Math.round((completedStages / 4) * 100);
  const selectedSignature = selectedIntentIds.slice().sort().join("|");
  const syncSignature = useMemo(
    () => [
      form.project.trim(),
      form.page.trim(),
      form.requirement.trim(),
      form.title.trim(),
      form.priority.trim(),
      form.source.trim(),
      candidates.map((candidate) => candidate.key).join("|"),
    ].join("::"),
    [candidates, form.page, form.priority, form.project, form.requirement, form.source, form.title],
  );

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
          selected_candidates: selectedCandidates.map((candidate) => ({
            intent_id: candidate.intentId,
            title: candidate.title,
            steps: candidate.steps,
            steps_hint: candidate.stepsHint,
            expected_result: candidate.expected,
            involved_elements: candidate.involvedElements,
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
  }, [previewPayload, selectedSignature, form.project, form.page]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (
      extracting
      || generating
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
        const allIntentIds = candidates.map((candidate) => candidate.intentId).filter(Boolean);
        const response = await saveTestPointAssets({
          project: form.project.trim(),
          page: form.page.trim(),
          requirement: form.requirement.trim(),
          title: form.title.trim(),
          priority: form.priority.trim() || "P1",
          source: form.source.trim() || "manual",
          selected_intent_ids: allIntentIds,
          selected_candidates: candidates.map((candidate) => ({
            intent_id: candidate.intentId,
            title: candidate.title,
            summary: candidate.summary,
            intent_type: candidate.intentType,
            priority: candidate.priority,
            precondition: candidate.precondition,
            steps: candidate.steps,
            steps_hint: candidate.stepsHint,
            expected: candidate.expected,
            involved_elements: candidate.involvedElements,
          })),
        });
        if (!cancelled) {
          const savedCount = Number(response.count || 0);
          appendEvent({
            stage: "candidate",
            level: "success",
            message: savedCount ? `已自动同步全部测试点资产 ${savedCount} 条。` : "测试点资产已自动同步。",
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
  }, [extracting, generating, previewPayload, candidates, form.project, form.page, form.requirement, form.title, form.priority, form.source, syncSignature, lastSyncedSignature]); // eslint-disable-line react-hooks/exhaustive-deps

  function getExtractDisabledReason(): string {
    if (extracting) {
      return "系统正在提取测试点，请稍候。";
    }
    if (generating) {
      return "系统正在生成用例，暂不可重复提取。";
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

  function getGenerateDisabledReason(): string {
    if (extracting) {
      return "请等待测试点提取完成。";
    }
    if (generating) {
      return "系统正在生成中，请稍候。";
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
      return "候选预校验存在阻断项，请先修复后再生成。";
    }
    if (!selectedCandidates.length) {
      return "请至少勾选 1 个候选测试点。";
    }
    return "";
  }

  const extractDisabledReason = getExtractDisabledReason();
  const generateDisabledReason = getGenerateDisabledReason();

  async function handleExtractPoints() {
    if (!canExtract || extracting || generating) {
      return;
    }
    setExtracting(true);
    setExtractErrorText("");
    setGenerateErrorText("");
    setPrecheckErrorText("");
    setPrecheckByIntentId({});
    setResultText("正在提取测试点...");
    appendEvent({ stage: "extract", level: "info", message: "已提交需求解析与测试点提取请求。" });
    setActiveStep(2);
    try {
      const response = await previewTestPoints({
        project: form.project.trim(),
        page: form.page.trim(),
        requirement: form.requirement.trim(),
        source: form.source.trim() || "manual",
      });
      const normalized = normalizeCandidates(response);
      const limited = normalized.slice(0, MAX_SELECTED);
      const gateDecision = readQualityDecision(response);
      setPreviewPayload(response);
      setCandidates(normalized);
      setSelectedKeys(limited.map((item) => item.key));
      setGeneratePayload(null);
      setLastSyncedSignature("");
      if (gateDecision === "block") {
        setResultText(`提取完成：识别 ${normalized.length} 个测试点，但质量门禁阻断，需先处理后再生成。`);
      } else {
        setResultText(`提取完成：识别 ${normalized.length} 个测试点，默认选择 ${limited.length} 个用于生成。`);
      }
      appendEvent({ stage: "extract", level: "success", message: `测试点提取完成，识别 ${normalized.length} 项。` });
      if (normalized.length > MAX_SELECTED) {
        appendEvent({
          stage: "candidate",
          level: "info",
          message: `已自动限制为前 ${MAX_SELECTED} 个候选，避免超过后端批量上限。`,
        });
      }
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
      if (prev.length >= MAX_SELECTED) {
        return prev;
      }
      return [...prev, key];
    });
  }

  function selectAllCandidates() {
    setSelectedKeys(candidates.slice(0, MAX_SELECTED).map((item) => item.key));
  }

  function clearAllCandidates() {
    setSelectedKeys([]);
  }

  async function handleGenerateFromSelected() {
    if (!canGenerate) {
      return;
    }
    setGenerating(true);
    setGenerateErrorText("");
    setResultText("正在根据已选测试点生成测试用例...");
    appendEvent({ stage: "generate", level: "info", message: `开始生成 ${selectedCandidates.length} 条候选用例。` });
    setActiveStep(4);
    try {
      const response = await generateCase({
        project: form.project.trim(),
        page: form.page.trim(),
        requirement: form.requirement.trim(),
        title: form.title.trim(),
        priority: form.priority.trim() || "P1",
        source: form.source.trim() || "manual",
        selected_intent_ids: selectedIntentIds,
            selected_candidates: selectedCandidates.map((candidate) => ({
          intent_id: candidate.intentId,
          title: candidate.title,
          summary: candidate.summary,
          intent_type: candidate.intentType,
          priority: candidate.priority,
          precondition: candidate.precondition,
          steps: candidate.steps,
          steps_hint: candidate.stepsHint,
          expected: candidate.expected,
          involved_elements: candidate.involvedElements,
        })),
      });
      const caseIds = readCaseIds(response);
      setGeneratePayload(response);
      setResultText(caseIds.length ? `生成完成：${caseIds.join("、")}` : "生成完成。");
      appendEvent({
        stage: "generate",
        level: "success",
        message: caseIds.length ? `成功生成 ${caseIds.length} 条用例。` : "生成请求成功返回。",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "生成测试用例失败";
      setGenerateErrorText(message);
      setResultText("");
      appendEvent({ stage: "generate", level: "error", message });
    } finally {
      setGenerating(false);
    }
  }

  function handleResetAll() {
    const firstProject = String(projects[0]?.project_code || DEFAULT_PROJECT_CODE).trim();
    setForm({ ...DEFAULT_FORM, project: firstProject });
    setActiveStep(1);
    setPreviewPayload(null);
    setCandidates([]);
    setSelectedKeys([]);
    setGeneratePayload(null);
    setExtractErrorText("");
    setGenerateErrorText("");
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
      disabled: !canExtract || extracting || generating,
    }
    : {
      label: generating ? "生成中..." : "生成用例",
      onClick: handleGenerateFromSelected,
      disabled: !canGenerate,
    };

  const nextDisabled = activeStep === 4
    || (activeStep === 1 && !canExtract)
    || (activeStep === 2 && (!previewPayload || extracting))
    || (activeStep === 3 && (!selectedCandidates.length || qualityBlocked));

  function renderStepMain() {
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
                disabled={loadingProjects || extracting || generating}
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
                disabled={extracting || generating}
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
                disabled={extracting || generating}
              />
            </label>
            <label>
              优先级
              <select
                value={form.priority}
                onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
                disabled={extracting || generating}
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
                disabled={extracting || generating}
              />
            </label>
            <label className="span-3">
              需求描述
              <textarea
                value={form.requirement}
                rows={8}
                placeholder="输入需求文本，至少包含业务目标、关键流程与验收点。"
                onChange={(event) => setForm((prev) => ({ ...prev, requirement: event.target.value }))}
                disabled={extracting || generating}
              />
            </label>
          </div>
          <p className="aiw-inline-hint">输入建议：至少包含业务目标、关键流程和验收点，避免过短句导致测试点不完整。</p>
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
            <button type="button" className="button" onClick={handleExtractPoints} disabled={!canExtract || extracting || generating}>
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
            <article className="metric-card">
              <p>解析置信度</p>
              <strong>{Number.isFinite(parseConfidence) && parseConfidence > 0 ? `${Math.round(parseConfidence * 100)}%` : "-"}</strong>
            </article>
            <article className="metric-card">
              <p>识别测试点</p>
              <strong>{candidates.length}</strong>
            </article>
            <article className="metric-card">
              <p>质量门禁</p>
              <strong className={qualityBlocked ? "metric-bad" : "metric-good"}>
                {qualityDecision === "allow" ? "通过" : qualityBlocked ? "阻断" : "-"}
              </strong>
            </article>
            <article className="metric-card">
              <p>门禁阻断项</p>
              <strong>{blockers.length}</strong>
            </article>
          </div>
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
                全选前 20 条
              </button>
              <button type="button" className="button secondary" onClick={clearAllCandidates} disabled={!selectedCandidates.length}>
                清空
              </button>
            </div>
          </header>

          <p className="muted">当前已选：{selectedCandidates.length}/{MAX_SELECTED}</p>
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
                  const disabled = !selected && selectedKeys.length >= MAX_SELECTED;
                  const precheck = precheckByIntentId[candidate.intentId];
                  const precheckStatus = precheck?.status || "ok";
                  const stepPreview = candidate.steps.slice(0, 3);
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
                              fontWeight: 600,
                              color: "var(--aiw-text-main)",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selected}
                              disabled={disabled || generating || extracting}
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
                                    color: "var(--aiw-text-main)",
                                    fontSize: "18px",
                                    lineHeight: 1.35,
                                    fontWeight: 800,
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
                              fontSize: "12px",
                              fontWeight: 800,
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
                            <span className="candidate-precheck-label" style={{ fontSize: "12px", fontWeight: 800 }}>
                              {precheckStatus === "block" ? "预校验阻断" : "预校验提示"}
                            </span>
                            <p style={{ margin: 0, fontSize: "13px", lineHeight: 1.45, fontWeight: 600 }}>
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
                          <span className="candidate-section-label">前置条件</span>
                          <p className="candidate-section-text" style={{ margin: 0, fontSize: "13px", lineHeight: 1.55 }}>
                            {candidate.precondition || "未返回前置条件。"}
                          </p>
                        </section>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">步骤概览</span>
                          {stepPreview.length ? (
                            <ol className="candidate-step-list" style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "8px" }}>
                              {stepPreview.map((step, stepIndex) => (
                                <li
                                  key={`${candidate.key}-${step}`}
                                  style={{ display: "grid", gridTemplateColumns: "24px minmax(0, 1fr)", gap: "10px", alignItems: "start", fontSize: "13px", lineHeight: 1.5 }}
                                >
                                  <span
                                    className="candidate-step-index"
                                    style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "24px", height: "24px", borderRadius: "999px", background: "#dbeafe", color: "#1d4ed8", fontSize: "12px", fontWeight: 800 }}
                                  >
                                    {stepIndex + 1}
                                  </span>
                                  <span className="candidate-step-text" style={{ minWidth: 0 }}>
                                    {step}
                                  </span>
                                </li>
                              ))}
                            </ol>
                          ) : (
                            <p className="candidate-section-text" style={{ margin: 0, fontSize: "13px", lineHeight: 1.55 }}>
                              未返回结构化步骤。
                            </p>
                          )}
                        </section>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">预期结果</span>
                          <p className="candidate-section-text" style={{ margin: 0, fontSize: "13px", lineHeight: 1.55 }}>
                            {candidate.expected || "未返回预期结果。"}
                          </p>
                        </section>
                        <section
                          className="candidate-module"
                          style={{ display: "grid", gap: "8px", padding: "12px", border: "1px solid #dfe8f5", borderRadius: "8px", background: "#f9fbff", minWidth: 0 }}
                        >
                          <span className="candidate-section-label">涉及元素</span>
                          {candidate.involvedElements.length ? (
                            <div className="candidate-chip-row" style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                              {candidate.involvedElements.map((element) => (
                                <span
                                  key={`${candidate.key}-${element}`}
                                  className="candidate-chip"
                                  style={{ display: "inline-flex", alignItems: "center", minHeight: "26px", padding: "0 10px", borderRadius: "999px", background: "#eff6ff", color: "#1f5fa8", border: "1px solid #d6e2f5", fontSize: "12px", fontWeight: 700 }}
                                >
                                  {element}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <p className="candidate-section-text" style={{ margin: 0, fontSize: "13px", lineHeight: 1.55 }}>
                              未返回涉及元素。
                            </p>
                          )}
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
                    <th>步骤数</th>
                    <th>预期结果</th>
                    <th>涉及元素</th>
                    <th>预校验</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.length ? (
                    candidates.map((candidate) => {
                      const selected = selectedKeys.includes(candidate.key);
                      const disabled = !selected && selectedKeys.length >= MAX_SELECTED;
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
                              disabled={disabled || extracting || generating}
                              onChange={() => toggleCandidate(candidate.key)}
                            />
                          </td>
                          <td className="mono">{candidate.intentId}</td>
                          <td>{candidate.title}</td>
                          <td>{intentTypeLabel(candidate.intentType || "")}</td>
                          <td>{candidate.priority || "P1"}</td>
                          <td>{candidate.steps.length}</td>
                          <td>{candidate.expected || "-"}</td>
                          <td>{candidate.involvedElements.slice(0, 3).join(" / ") || "-"}</td>
                          <td className={`aiw-precheck-cell status-${precheckStatus}`}>
                            {precheckStatus === "ok" ? "通过" : precheckStatus === "block" ? "阻断" : "提示"}
                            {precheck && precheck.reasons.length ? `：${precheck.reasons[0]}` : ""}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={9} className="asset-empty">
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
          <h2>步骤 4：生成用例</h2>
          <p className="muted">生成完成后请继续进入审核与执行闭环。</p>
        </header>
        <div className="aiw-action-row">
          <button type="button" className="button" onClick={handleGenerateFromSelected} disabled={!canGenerate}>
            {generating ? "生成中..." : "生成用例"}
          </button>
          <p className="muted">{generateDisabledReason || "候选准备完成后可执行生成。"}</p>
        </div>

        {resultText ? <p>{resultText}</p> : null}
        {extractErrorText || generateErrorText ? (
          <section className="aiw-error-box aiw-step-error">
            <strong>{generateErrorText ? "生成失败" : "提取失败"}</strong>
            <p className="error">{extractErrorText || generateErrorText}</p>
            <p className="muted">请根据失败原因修正输入后重试。</p>
          </section>
        ) : null}

        {generatePayload ? (
          <div className="generation-next-actions">
            <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(normalizeProjectCode(form.project))}`}>
              查看测试资产
            </Link>
            <Link className="button secondary" to="/cases">查看用例资产</Link>
            <Link className="button secondary" to="/cases/review">进入审核队列</Link>
            <Link className="button secondary" to="/execution/plans">打开执行计划</Link>
          </div>
        ) : null}

        {generatePayload && Array.isArray(generatePayload.items) && generatePayload.items.length ? (
          <div className="generated-list">
            {generatePayload.items.map((item, index) => {
              const row = item as Record<string, unknown>;
              const caseId = toText(row.case_id) || `case-${index + 1}`;
              const path = toText(row.path);
              return (
                <article key={`${caseId}-${index}`} className="generated-card">
                  <h3>{caseId}</h3>
                  <p className="muted">{path || "未返回路径"}</p>
                  <Link className="button secondary" to={`/cases/${encodeURIComponent(caseId)}`}>
                    查看用例详情
                  </Link>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="aiw-empty-state">
            <strong>暂无生成结果</strong>
            <p>先执行测试点提取并完成候选选择，再生成可执行用例。</p>
          </div>
        )}
      </section>
    );
  }

  return (
    <main className="shell aiw-page">
      <header className="panel aiw-top-header unified-topbar">
        <div>
          <h1>需求到用例单链工作台</h1>
          <p className="muted">主链路：输入需求 → 提取测试点 → 筛选候选 → 生成用例</p>
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
          <button type="button" className="button secondary" onClick={handleResetAll} disabled={extracting || generating}>
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
                <summary>查看步骤 2 原始响应（诊断）</summary>
                <pre className="json-block">{JSON.stringify(previewPayload || {}, null, 2)}</pre>
              </details>
              <details>
                <summary>查看步骤 4 原始响应（诊断）</summary>
                <pre className="json-block">{JSON.stringify(generatePayload || {}, null, 2)}</pre>
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
                4: "生成用例",
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
                <span>已选数量</span>
                <strong>{selectedCandidates.length}/{MAX_SELECTED}</strong>
              </li>
            </ul>
          </section>

        </aside>
      </div>

      <section className="aiw-sticky-bar">
        <div className="aiw-sticky-inner">
          <span className="muted">步骤进度 {completedStages}/4 · 已选 {selectedCandidates.length}/{MAX_SELECTED}</span>
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
