/** Prompt 模板管理页面：列表 + 编辑 + 测试 + 恢复默认（DB 为唯一事实源）。 */

import { useCallback, useEffect, useState } from "react";

import {
  type PromptTemplateItem,
  listPromptTemplates,
  updatePromptTemplate,
  testPromptTemplate,
  resetPromptTemplate,
} from "../api/workbench";

function toText(v: unknown): string {
  return String(v || "").trim();
}

function extractVariableNames(template: string): string[] {
  const re = /\{\{\s*(\w+)\s*\}\}/g;
  const names = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = re.exec(template)) !== null) {
    names.add(m[1]);
  }
  return Array.from(names).sort();
}

export function PromptManagementPage() {
  const [templates, setTemplates] = useState<PromptTemplateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editSys, setEditSys] = useState("");
  const [editUser, setEditUser] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  const [testVars, setTestVars] = useState<Record<string, string>>({});
  const [testResult, setTestResult] = useState<{ system: string; user: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const selected = templates.find((t) => t.id === selectedId) ?? null;
  const varNames = editUser ? extractVariableNames(editUser) : [];

  useEffect(() => {
    let cancelled = false;
    listPromptTemplates()
      .then((res) => {
        if (!cancelled) setTemplates(res.items || []);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const selectTemplate = useCallback((t: PromptTemplateItem) => {
    setSelectedId(t.id);
    setEditSys(t.system_prompt || "");
    setEditUser(t.user_prompt_template || "");
    setEditDesc(t.description || "");
    setTestVars({});
    setTestResult(null);
    setSaveMsg("");
  }, []);

  const handleSave = useCallback(async () => {
    if (selectedId === null) return;
    setSaving(true);
    setSaveMsg("");
    try {
      await updatePromptTemplate(selectedId, {
        system_prompt: editSys,
        user_prompt_template: editUser,
        description: editDesc,
      });
      setSaveMsg("保存成功");
      const res = await listPromptTemplates();
      setTemplates(res.items || []);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [selectedId, editSys, editUser, editDesc]);

  const handleTest = useCallback(async () => {
    if (selectedId === null) return;
    setTesting(true);
    try {
      const result = await testPromptTemplate(selectedId, testVars);
      setTestResult({ system: result.system_prompt, user: result.user_prompt });
    } catch (e) {
      setTestResult({ system: "渲染失败", user: e instanceof Error ? e.message : "未知错误" });
    } finally {
      setTesting(false);
    }
  }, [selectedId, testVars]);

  const handleReset = useCallback(async () => {
    if (selectedId === null || !selected) return;
    if (!window.confirm(`确认恢复「${selected.name}」为默认版本？自定义修改将丢失。`)) return;
    try {
      await resetPromptTemplate(selectedId);
      const res = await listPromptTemplates();
      setTemplates(res.items || []);
      const restored = res.items?.find((t) => t.code === selected.code);
      if (restored) selectTemplate(restored);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "恢复失败");
    }
  }, [selectedId, selected, selectTemplate]);

  if (loading) return <section className="panel aiw-panel"><p className="muted">加载中...</p></section>;

  return (
    <section className="panel aiw-panel">
      <header className="aiw-panel-header">
        <h2>Prompt 模板管理</h2>
        <p className="muted">DB 为唯一事实源。编辑后保存 → 即时生效（下次 LLM 调用使用新模板）。空列表表示 DB 中尚无模板。</p>
      </header>

      <div className="aiw-prompt-layout">
        <aside className="aiw-prompt-list">
          {templates.map((t) => (
            <div
              key={t.id}
              className={`aiw-prompt-item${selectedId === t.id ? " aiw-prompt-item-active" : ""}`}
              onClick={() => selectTemplate(t)}
            >
              <div className="aiw-prompt-item-name">
                {t.name}
                {!t.is_default && <span className="aiw-tag aiw-tag-yellow" style={{ marginLeft: 6 }}>已修改</span>}
              </div>
              <div className="muted" style={{ fontSize: 11 }}>code: {t.code} · v{t.version}</div>
            </div>
          ))}
          {templates.length === 0 && <p className="muted" style={{ padding: 12 }}>暂无模板（DB 为空）。请先通过 API 或 dev seed 创建模板。</p>}
        </aside>

        <main className="aiw-prompt-editor">
          {selected ? (
            <>
              <div className="aiw-prompt-editor-header">
                <h3>{selected.name}</h3>
                <span className="muted">code: {selected.code} · 场景: {selected.scene_type} · v{selected.version}</span>
              </div>

              <label className="aiw-prompt-field">
                描述
                <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="模板用途说明" />
              </label>

              <label className="aiw-prompt-field">
                System Prompt
                <textarea rows={4} value={editSys} onChange={(e) => setEditSys(e.target.value)} />
              </label>

              <label className="aiw-prompt-field">
                User Prompt 模板 (Jinja2 语法: {"{{ variable }}"})
                <textarea rows={8} value={editUser} onChange={(e) => setEditUser(e.target.value)} />
              </label>

              {varNames.length > 0 && (
                <div className="aiw-prompt-vars">
                  <span className="muted">模板变量: </span>
                  {varNames.map((v) => (
                    <span key={v} className="aiw-tag aiw-tag-gray">{v}</span>
                  ))}
                </div>
              )}

              <div className="aiw-prompt-actions">
                <button className="button" onClick={handleSave} disabled={saving}>
                  {saving ? "保存中..." : "保存"}
                </button>
                <button className="button" onClick={handleReset} disabled={selected.is_default}>
                  恢复默认
                </button>
                {saveMsg && <span className={saveMsg.includes("成功") ? "muted" : "error"} style={{ marginLeft: 10 }}>{saveMsg}</span>}
              </div>

              <details className="aiw-prompt-test">
                <summary>测试模板</summary>
                {varNames.length > 0 && (
                  <div className="aiw-prompt-test-vars">
                    {varNames.map((v) => (
                      <label key={v} className="aiw-prompt-test-var">
                        {v}
                        <input
                          value={testVars[v] || ""}
                          onChange={(e) => setTestVars((prev) => ({ ...prev, [v]: e.target.value }))}
                          placeholder={selected.variables?.[v]?.required ? "[必填]" : "[可选]"}
                        />
                      </label>
                    ))}
                  </div>
                )}
                <button className="button" onClick={handleTest} disabled={testing}>
                  {testing ? "测试中..." : "发送测试"}
                </button>

                {testResult && (
                  <div className="aiw-prompt-test-result">
                    <div className="aiw-prompt-test-block">
                      <strong>System Prompt:</strong>
                      <pre>{testResult.system}</pre>
                    </div>
                    <div className="aiw-prompt-test-block">
                      <strong>User Prompt:</strong>
                      <pre>{testResult.user}</pre>
                    </div>
                  </div>
                )}
              </details>
            </>
          ) : (
            <p className="muted" style={{ padding: 20 }}>请从左侧选择一个模板</p>
          )}
        </main>
      </div>
    </section>
  );
}
