import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { createTestProject, deleteTestProject, listTestProjects, updateTestProject } from "../api/workbench";
import { DEFAULT_PROJECT_CODE } from "../config/projects";
import { formatDateTime } from "../lib/datetime";

interface ProjectForm {
  project_code: string;
  project_name: string;
  description: string;
  source_roots_text: string;
  source_terms_text: string;
}

const EMPTY_FORM: ProjectForm = {
  project_code: "",
  project_name: "",
  description: "",
  source_roots_text: "",
  source_terms_text: "",
};

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function normalizeProjectCodeInput(value: string): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function parseSourceRoots(value: string): string[] {
  return String(value || "")
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSourceTerms(value: string): Record<string, string> {
  const raw = String(value || "").trim();
  if (!raw) {
    return {};
  }
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  const terms: Record<string, string> = {};
  Object.entries(parsed || {}).forEach(([key, item]) => {
    const phrase = String(key || "").trim();
    const code = String(item || "").trim();
    if (phrase && code) {
      terms[phrase] = code;
    }
  });
  return terms;
}

function formatSourceTerms(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

interface ProjectsPageProps {
  mode?: "project" | "source";
}

export function ProjectsPage({ mode = "project" }: ProjectsPageProps) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [form, setForm] = useState<ProjectForm>({ ...EMPTY_FORM, project_code: DEFAULT_PROJECT_CODE, project_name: "Mall" });
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [editingProjectCode, setEditingProjectCode] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<Record<string, unknown> | null>(null);

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listTestProjects();
      setItems(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "项目列表加载失败");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  async function submitCreate() {
    if (saving) {
      return;
    }
    const projectCode = normalizeProjectCodeInput(form.project_code);
    const projectName = String(form.project_name || "").trim();
    if (!projectCode || projectCode.length < 2) {
      setErrorText("项目编码至少 2 位，只允许小写字母和数字。");
      return;
    }
    if (!projectName) {
      setErrorText("项目名称不能为空。");
      return;
    }
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      const sourceTerms = parseSourceTerms(form.source_terms_text);
      const payload = {
        project_name: projectName,
        description: String(form.description || "").trim(),
        source_roots: parseSourceRoots(form.source_roots_text),
        source_terms: sourceTerms,
      };
      if (editingProjectCode) {
        await updateTestProject(editingProjectCode, payload);
        setFeedback(`项目 ${editingProjectCode} 已更新。`);
      } else {
        await createTestProject({
          project_code: projectCode,
          ...payload,
          created_by: "admin",
        });
        setFeedback(`项目 ${projectCode} 已创建。`);
      }
      setEditingProjectCode("");
      setForm(EMPTY_FORM);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "项目创建失败");
    } finally {
      setSaving(false);
    }
  }

  async function editSourceConfig(item: Record<string, unknown>) {
    const projectCode = String(item.project_code || "").trim();
    if (!projectCode || saving) {
      return;
    }
    setErrorText("");
    setFeedback("");
    setEditingProjectCode(projectCode);
    setForm({
      project_code: projectCode,
      project_name: String(item.project_name || "").trim(),
      description: String(item.description || "").trim(),
      source_roots_text: Array.isArray(item.source_roots) ? item.source_roots.join("\n") : "",
      source_terms_text: formatSourceTerms(item.source_terms),
    });
  }

  async function toggleStatus(item: Record<string, unknown>) {
    const projectCode = String(item.project_code || "").trim();
    if (!projectCode || saving) {
      return;
    }
    const currentStatus = String(item.status || "").trim().toLowerCase();
    const nextStatus = currentStatus === "inactive" ? "active" : "inactive";
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      await updateTestProject(projectCode, { status: nextStatus });
      setFeedback(`项目 ${projectCode} 已${nextStatus === "active" ? "启用" : "停用"}。`);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "项目状态更新失败");
    } finally {
      setSaving(false);
    }
  }

  async function removeProject(item: Record<string, unknown>) {
    const projectCode = String(item.project_code || "").trim();
    if (!projectCode || saving) {
      return;
    }
    setDeleteTarget(item);
  }

  async function confirmRemoveProject() {
    const projectCode = String(deleteTarget?.project_code || "").trim();
    if (!projectCode || saving) {
      return;
    }
    setSaving(true);
    setErrorText("");
    setFeedback("");
    try {
      await deleteTestProject(projectCode);
      setFeedback(`项目 ${projectCode} 已删除。`);
      setDeleteTarget(null);
      await reload();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "项目删除失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>{mode === "source" ? "源码管理" : "项目管理"}</h1>
          <p className="muted">
            {mode === "source"
              ? "按项目维护被测系统源码目录和业务术语，用于录制候选元素的语义增强。"
              : "统一维护项目编码，后续用例、测试点、页面对象和录制资产都会按项目隔离。"}
          </p>
        </div>
        <div className="header-actions">
          {mode === "source" ? (
            <Link className="button secondary" to="/system/projects">
              返回项目管理
            </Link>
          ) : (
            <Link className="button secondary" to="/system/source-config">
              源码管理
            </Link>
          )}
        </div>
      </header>

      {mode === "source" ? (
        <section className="panel">
          <h2>如何填写源码配置</h2>
          <p className="muted">
            源码目录必须是 web-ui-service 运行环境能访问到的路径。Docker 部署时通常填写容器内路径，例如
            <code> /workspace/mall-admin-web</code>。项目术语使用 JSON，例如 <code>{'{"商品名称":"product_name"}'}</code>。
          </p>
        </section>
      ) : null}

      <section className="panel form-grid">
        <label>
          项目编码
          <input
            value={form.project_code}
            onChange={(event) => setForm((prev) => ({ ...prev, project_code: normalizeProjectCodeInput(event.target.value) }))}
            placeholder="例如 mall"
            disabled={saving || Boolean(editingProjectCode)}
          />
        </label>
        <label>
          项目名称
          <input
            value={form.project_name}
            onChange={(event) => setForm((prev) => ({ ...prev, project_name: event.target.value }))}
            placeholder="例如 Mall Admin Web"
            disabled={saving}
          />
        </label>
        <label className="span-3">
          项目描述
          <textarea
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            placeholder="补充项目背景、被测系统地址或负责人信息"
            disabled={saving}
            rows={3}
          />
        </label>
        <label className="span-3">
          源码目录
          <textarea
            value={form.source_roots_text}
            onChange={(event) => setForm((prev) => ({ ...prev, source_roots_text: event.target.value }))}
            placeholder="一行一个源码根目录。Docker 环境示例：/workspace/mall-admin-web"
            disabled={saving}
            rows={3}
          />
        </label>
        <label className="span-3">
          项目术语 JSON
          <textarea
            value={form.source_terms_text}
            onChange={(event) => setForm((prev) => ({ ...prev, source_terms_text: event.target.value }))}
            placeholder='例如 {"商品名称":"product_name"}'
            disabled={saving}
            rows={3}
          />
        </label>
        <div className="span-3 header-actions">
          <button type="button" className="button" onClick={() => void submitCreate()} disabled={saving}>
            {editingProjectCode ? "保存项目配置" : "新建项目"}
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setEditingProjectCode("");
              setForm(EMPTY_FORM);
            }}
            disabled={saving}
          >
            {editingProjectCode ? "取消编辑" : "清空"}
          </button>
          <button type="button" className="button secondary" onClick={() => void reload()} disabled={saving || loading}>
            刷新
          </button>
        </div>
      </section>

      {errorText ? <section className="panel error">{errorText}</section> : null}
      {feedback ? <section className="panel">{feedback}</section> : null}

      <DataTable title="项目列表" loading={loading} loadingText="正在加载项目列表..." actions={<span className="muted">默认项目：{DEFAULT_PROJECT_CODE}</span>}>
          <table>
            <thead>
              <tr>
                <th>项目编码</th>
                <th>项目名称</th>
                <th>状态</th>
                <th>描述</th>
                <th>源码目录</th>
                <th>术语数</th>
                <th>创建人</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item, index) => {
                  const projectCode = String(item.project_code || "").trim();
                  const status = String(item.status || "").trim().toLowerCase();
                  const isDefault = projectCode === DEFAULT_PROJECT_CODE;
                  return (
                    <tr key={projectCode || String(index)}>
                      <td className="mono">{text(projectCode)}</td>
                      <td>{text(item.project_name)}</td>
                      <td>{status === "inactive" ? "停用" : "启用"}</td>
                      <td>{text(item.description)}</td>
                      <td>{Array.isArray(item.source_roots) && item.source_roots.length ? item.source_roots.join("，") : "-"}</td>
                      <td>{item.source_terms && typeof item.source_terms === "object" ? Object.keys(item.source_terms as Record<string, unknown>).length : 0}</td>
                      <td>{text(item.created_by)}</td>
                      <td>{formatDateTime(item.updated_at)}</td>
                      <td>
                        <div className="header-actions">
                          <button type="button" className="button secondary" onClick={() => void toggleStatus(item)} disabled={saving || isDefault}>
                            {status === "inactive" ? "启用" : "停用"}
                          </button>
                          <button type="button" className="button secondary" onClick={() => void editSourceConfig(item)} disabled={saving}>
                            源码配置
                          </button>
                          <details className="action-menu">
                            <summary>更多</summary>
                            <button type="button" className="danger-text" onClick={() => void removeProject(item)} disabled={saving || isDefault}>
                              删除
                            </button>
                          </details>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9}>
                    <EmptyState title="暂无项目" description="可以在上方创建项目，并为项目配置源码目录与术语表。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
      {deleteTarget ? (
        <ConfirmDialog
          title="确认删除项目"
          description="删除项目会移除项目配置；已有资产或默认项目会被后端拦截。"
          danger
          busy={saving}
          confirmText="确认删除"
          details={[`项目编码：${text(deleteTarget.project_code)}`, "请确认该项目不再承载测试资产。"]}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => void confirmRemoveProject()}
        />
      ) : null}
    </main>
  );
}
