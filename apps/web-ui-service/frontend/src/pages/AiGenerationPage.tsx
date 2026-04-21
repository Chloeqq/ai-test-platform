import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  generateCase,
  listProjects,
  runFullChain,
  type GenerateCaseResponse,
  type FullChainRunResponse,
  type ProjectItem,
} from "../api/workbench";

interface GenerationForm {
  project: string;
  page: string;
  requirement: string;
  title: string;
  priority: string;
}

const DEFAULT_FORM: GenerationForm = {
  project: "",
  page: "",
  requirement: "",
  title: "",
  priority: "P1",
};

function asText(value: unknown): string {
  const text = String(value || "").trim();
  return text || "-";
}

function readCaseIds(response: GenerateCaseResponse): string[] {
  const items = Array.isArray(response.items) ? response.items : [];
  const fromItems = items
    .map((item) => String((item as Record<string, unknown>)?.case_id || "").trim())
    .filter(Boolean);
  if (fromItems.length) {
    return fromItems;
  }
  const one = String((response.item as Record<string, unknown> | undefined)?.case_id || "").trim();
  return one ? [one] : [];
}

export function AiGenerationPage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [form, setForm] = useState<GenerationForm>(DEFAULT_FORM);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [resultText, setResultText] = useState<string>("");
  const [resultPayload, setResultPayload] = useState<GenerateCaseResponse | FullChainRunResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoadingProjects(true);
      try {
        const payload = await listProjects();
        if (cancelled) {
          return;
        }
        const items = Array.isArray(payload.items) ? payload.items : [];
        setProjects(items);
        if (!form.project && items.length) {
          setForm((prev) => ({ ...prev, project: String(items[0].project_code || "").trim() }));
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "加载项目列表失败");
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

  const canSubmit = useMemo(
    () => Boolean(form.project.trim() && form.page.trim() && form.requirement.trim()),
    [form.page, form.project, form.requirement],
  );

  async function handleGenerateDraft() {
    if (!canSubmit || submitting) {
      return;
    }
    setSubmitting(true);
    setErrorText("");
    setResultText("正在生成 Draft...");
    try {
      const response = await generateCase({
        project: form.project.trim(),
        page: form.page.trim(),
        requirement: form.requirement.trim(),
        title: form.title.trim(),
        priority: form.priority.trim() || "P1",
        source: "manual",
      });
      const caseIds = readCaseIds(response);
      setResultPayload(response);
      setResultText(caseIds.length ? `Draft 生成成功：${caseIds.join(", ")}` : "Draft 生成成功");
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "Draft 生成失败");
      setResultText("");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleFullChainRun() {
    if (!canSubmit || submitting) {
      return;
    }
    setSubmitting(true);
    setErrorText("");
    setResultText("正在执行全链路（测试点 -> 用例 -> 执行）...");
    try {
      const response = await runFullChain({
        project: form.project.trim(),
        page: form.page.trim(),
        requirement: form.requirement.trim(),
        source: "manual",
        max_cases: 5,
        run_after_generate: true,
        wait_seconds: 240,
      });
      const summary = (response.summary || {}) as Record<string, unknown>;
      const executedCount = Number(summary.executed_count || 0);
      const generatedCount = Number(summary.generated_case_count || 0);
      setResultPayload(response);
      setResultText(`全链路完成：生成 ${generatedCount} 条，执行 ${executedCount} 条。`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "全链路执行失败");
      setResultText("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>AI 生成（React + TypeScript）</h1>
          <p className="muted">从需求输入到生成用例，已切换到 React 主链入口。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/ai-generation/history">
            查看生成历史
          </Link>
        </div>
      </header>

      <section className="panel form-grid">
        <label>
          项目
          <select
            value={form.project}
            onChange={(event) => setForm((prev) => ({ ...prev, project: event.target.value }))}
            disabled={loadingProjects || submitting}
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
          页面
          <input
            value={form.page}
            placeholder="例如 login"
            onChange={(event) => setForm((prev) => ({ ...prev, page: event.target.value }))}
            disabled={submitting}
          />
        </label>
        <label>
          优先级
          <select
            value={form.priority}
            onChange={(event) => setForm((prev) => ({ ...prev, priority: event.target.value }))}
            disabled={submitting}
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
            disabled={submitting}
          />
        </label>
        <label className="span-3">
          需求描述
          <textarea
            value={form.requirement}
            rows={7}
            placeholder="输入需求文本，至少包含业务目标、关键流程与验收点。"
            onChange={(event) => setForm((prev) => ({ ...prev, requirement: event.target.value }))}
            disabled={submitting}
          />
        </label>
      </section>

      <section className="panel header-actions">
        <button type="button" className="button secondary" onClick={handleGenerateDraft} disabled={!canSubmit || submitting}>
          生成 Draft
        </button>
        <button type="button" className="button" onClick={handleFullChainRun} disabled={!canSubmit || submitting}>
          全链路执行
        </button>
      </section>

      <section className="panel">
        <p className="muted">状态：{submitting ? "执行中" : "空闲"}</p>
        {resultText ? <p>{resultText}</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {resultPayload ? <pre className="json-block">{JSON.stringify(resultPayload, null, 2)}</pre> : null}
      </section>

      <section className="panel">
        <p className="muted">
          旧入口兼容：<a href="/ai-generation">/ai-generation</a>（会 307 到当前 React 页面）
        </p>
        <p className="muted">当前选择项目：{asText(form.project)}</p>
      </section>
    </main>
  );
}
