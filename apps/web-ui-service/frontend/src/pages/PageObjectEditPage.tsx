import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  createPageObject,
  getPageObject,
  updatePageObject,
} from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

interface PageObjectEditorState {
  pageCode: string;
  pageName: string;
  pageUrl: string;
  preconditionState: string;
  moduleId: string;
  description: string;
  status: string;
}

const EMPTY_EDITOR: PageObjectEditorState = {
  pageCode: "",
  pageName: "",
  pageUrl: "",
  preconditionState: "",
  moduleId: "0",
  description: "",
  status: "draft",
};

interface PageObjectEditPageProps {
  mode: "create" | "edit";
}

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function listLink(projectCode: string): string {
  return `/assets/page-objects?project=${encodeURIComponent(projectCode)}`;
}

function elementsLink(pageCode: string, projectCode: string): string {
  return `/assets/page-objects/${encodeURIComponent(pageCode)}/elements?project=${encodeURIComponent(projectCode)}`;
}

export function PageObjectEditPage({ mode }: PageObjectEditPageProps) {
  const { pageCode = "" } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [projectCode, setProjectCode] = useState<string>(normalizeProjectCode(searchParams.get("project") || DEFAULT_PROJECT_CODE));
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [editor, setEditor] = useState<PageObjectEditorState>(EMPTY_EDITOR);
  const [loading, setLoading] = useState<boolean>(mode === "edit");
  const [saving, setSaving] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");

  const editing = mode === "edit";
  const normalizedPageCode = String(pageCode || editor.pageCode || "").trim();

  useEffect(() => {
    let cancelled = false;
    async function loadProjectOptions() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          const codes = projectOptions(projects.codes);
          setProjectCodes(codes);
          if (codes.length && !codes.includes(projectCode)) {
            setProjectCode(codes[0]);
          }
        }
      } catch {
        // Keep default project option.
      }
    }
    void loadProjectOptions();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDetail(targetProject = projectCode) {
    if (!editing || !pageCode) {
      return;
    }
    setLoading(true);
    setErrorText("");
    setFeedback("");
    try {
      const payload = await getPageObject(pageCode, { project_code: targetProject, client: "web" });
      const item = payload.item || {};
      setEditor({
        pageCode: String(item.page_code || pageCode || "").trim(),
        pageName: String(item.page_name || "").trim(),
        pageUrl: String(item.page_url || "").trim(),
        preconditionState: String(item.precondition_state || "").trim(),
        moduleId: String(item.module_id || "0").trim() || "0",
        description: String(item.description || "").trim(),
        status: String(item.status || "draft").trim() || "draft",
      });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDetail(projectCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectCode, pageCode, mode]);

  async function submitEditor() {
    const nextPageCode = String(editor.pageCode || "").trim();
    const nextPageName = String(editor.pageName || "").trim();
    const nextPageUrl = String(editor.pageUrl || "").trim();
    if (!nextPageCode) {
      setErrorText("页面编码不能为空。");
      return;
    }
    if (!nextPageName) {
      setErrorText("页面名称不能为空。");
      return;
    }
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      if (editing) {
        const response = await updatePageObject(
          nextPageCode,
          {
            page_name: nextPageName,
            page_url: nextPageUrl,
            precondition_state: String(editor.preconditionState || "").trim(),
            module_id: Number(editor.moduleId || 0) || 0,
            description: String(editor.description || "").trim(),
            status: String(editor.status || "draft").trim() || "draft",
          },
          { project_code: projectCode, client: "web" },
        );
        const savedItem = response.item || {};
        setEditor((prev) => ({
          ...prev,
          pageUrl: String(savedItem.page_url ?? nextPageUrl).trim(),
          pageName: String(savedItem.page_name ?? nextPageName).trim(),
          status: String(savedItem.status ?? prev.status).trim() || "draft",
        }));
        setFeedback(`页面对象已更新，当前 URL：${text(savedItem.page_url || nextPageUrl)}`);
      } else {
        const response = await createPageObject({
          project_code: projectCode,
          client: "web",
          page_code: nextPageCode,
          page_name: nextPageName,
          page_url: nextPageUrl,
          precondition_state: String(editor.preconditionState || "").trim(),
          module_id: Number(editor.moduleId || 0) || 0,
          description: String(editor.description || "").trim(),
          status: String(editor.status || "draft").trim() || "draft",
          created_by: "web-ui",
        });
        const createdPageCode = String(response.item?.page_code || nextPageCode).trim();
        navigate(`/assets/page-objects/${encodeURIComponent(createdPageCode)}/edit?project=${encodeURIComponent(projectCode)}`, {
          replace: true,
        });
        setFeedback(`页面对象已创建，当前 URL：${text(response.item?.page_url || nextPageUrl)}`);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "页面对象保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>{editing ? "编辑页面对象" : "新建页面对象"}</h1>
          <p className="muted">在独立页面维护页面对象基础信息，保存后会直接持久化到 PageObject。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={listLink(projectCode)}>
            返回页面对象列表
          </Link>
          {editing && normalizedPageCode ? (
            <Link className="button secondary" to={elementsLink(normalizedPageCode, projectCode)}>
              查看元素
            </Link>
          ) : null}
        </div>
      </header>

      {loading ? <section className="panel">正在加载页面对象...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {feedback ? <section className="panel">{feedback}</section> : null}

      {!loading ? (
        <section className="panel">
          <div className="form-grid">
            <label>
              项目
              <select value={projectCode} onChange={(event) => setProjectCode(normalizeProjectCode(event.target.value))} disabled={saving || editing}>
                {projectCodes.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </label>
            <label>
              页面编码（page_code）
              <input
                value={editor.pageCode}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageCode: event.target.value }))}
                disabled={saving || editing}
              />
            </label>
            <label>
              页面名称（page_name）
              <input
                value={editor.pageName}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageName: event.target.value }))}
                disabled={saving}
              />
            </label>
            <label>
              状态
              <select
                value={editor.status}
                onChange={(event) => setEditor((prev) => ({ ...prev, status: event.target.value }))}
                disabled={saving}
              >
                <option value="draft">草稿</option>
                <option value="review">评审中</option>
                <option value="published">已发布</option>
                <option value="retired">已下线</option>
              </select>
            </label>
            <label className="span-2">
              页面地址（page_url）
              <input
                value={editor.pageUrl}
                onChange={(event) => setEditor((prev) => ({ ...prev, pageUrl: event.target.value }))}
                placeholder="例如：http://localhost:8013/login 或 /login"
                disabled={saving}
              />
            </label>
            <label>
              模块
              <input
                value={editor.moduleId}
                onChange={(event) => setEditor((prev) => ({ ...prev, moduleId: event.target.value }))}
                placeholder="默认模块可填 0"
                disabled={saving}
              />
            </label>
            <label className="span-3">
              前置状态（precondition_state）
              <textarea
                rows={3}
                value={editor.preconditionState}
                onChange={(event) => setEditor((prev) => ({ ...prev, preconditionState: event.target.value }))}
                disabled={saving}
              />
            </label>
            <label className="span-3">
              说明（description）
              <textarea
                rows={3}
                value={editor.description}
                onChange={(event) => setEditor((prev) => ({ ...prev, description: event.target.value }))}
                disabled={saving}
              />
            </label>
          </div>
          <div className="header-actions">
            <button type="button" className="button" onClick={() => void submitEditor()} disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </button>
            <Link className="button secondary" to={listLink(projectCode)}>
              取消
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
