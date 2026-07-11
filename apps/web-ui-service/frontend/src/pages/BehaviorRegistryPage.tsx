import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import http from "../utils/http";

interface Behavior {
  id: number; behavior_code: string; intent_type: string; scenario: string;
  scope: string; page_code: string; domain: string; version: number;
  status: string; priority: number; label: string; capabilities: string[];
}

interface Template {
  id: number; capability: string; execution_layer: string;
  action: string; target: string; operator: string; value: string; description: string;
}

function text(v: unknown): string { return String(v ?? "").trim() || "-"; }

export function BehaviorRegistryPage() {
  const [searchParams] = useSearchParams();
  const pageCode = searchParams.get("page_code") || "login";
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [selected, setSelected] = useState<Behavior | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);

  const loadBehaviors = async () => {
    setLoading(true);
    try {
      const res = await http.get<{items: Behavior[]}>(`/api/behavior-registry/behaviors?page_code=${pageCode}`);
      setBehaviors(res.data.items);
    } finally { setLoading(false); }
  };

  const loadTemplates = async (id: number) => {
    const res = await http.get<{templates: Template[]}>(`/api/behavior-registry/behaviors/${id}`);
    setTemplates(res.data.templates || []);
  };

  useEffect(() => { loadBehaviors(); }, [pageCode]);

  const selectBehavior = async (b: Behavior) => {
    setSelected(b);
    await loadTemplates(b.id);
  };

  const addTemplate = async () => {
    if (!selected) return;
    await http.post(`/api/behavior-registry/behaviors/${selected.id}/templates`, {
      capability: "", execution_layer: "ui",
      action: "assert_visible", target: "", operator: "exists", value: "", description: ""
    });
    await loadTemplates(selected.id);
  };

  const deleteTemplate = async (id: number) => {
    await http.delete(`/api/behavior-registry/templates/${id}`);
    if (selected) await loadTemplates(selected.id);
  };

  return (
    <div className="panel">
      <h1>断言模板管理</h1>
      <p>页面: <strong>{pageCode}</strong> — 基于 Behavior Registry 的断言配置</p>

      <div style={{ display: "flex", gap: "1.5rem", marginTop: "1rem" }}>
        {/* Left: behavior list */}
        <div style={{ flex: 1, maxWidth: "360px" }}>
          <h2>行为列表</h2>
          {loading ? <p>加载中...</p> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>行为编码</th><th>场景</th><th>状态</th>
                </tr>
              </thead>
              <tbody>
                {behaviors.map(b => (
                  <tr key={b.id}
                    onClick={() => selectBehavior(b)}
                    style={{ cursor: "pointer", background: selected?.id === b.id ? "#e8f4fd" : "" }}
                  >
                    <td className="mono">{b.behavior_code}</td>
                    <td>{b.scenario}</td>
                    <td><span className={`status-badge ${b.status}`}>{b.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Right: templates */}
        <div style={{ flex: 2 }}>
          {selected ? (
            <>
              <h2>{selected.behavior_code} — {selected.label}</h2>
              <p className="mono" style={{ fontSize: "0.85rem", color: "#666" }}>
                intent={selected.intent_type} | scenario={selected.scenario} | v{selected.version} | {selected.scope}
              </p>
              {selected.capabilities.length > 0 && (
                <p style={{ fontSize: "0.85rem" }}>
                  能力: {selected.capabilities.map(c => <span key={c} className="tag">{c}</span>)}
                </p>
              )}

              <table className="data-table" style={{ marginTop: "1rem" }}>
                <thead>
                  <tr>
                    <th>层</th><th>动作</th><th>目标</th><th>值</th><th>操作符</th><th>说明</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map(t => (
                    <tr key={t.id}>
                      <td><span className="badge">{t.execution_layer}</span></td>
                      <td className="mono">{t.action}</td>
                      <td className="mono">{text(t.target)}</td>
                      <td className="mono">{text(t.value)}</td>
                      <td>{t.operator}</td>
                      <td style={{ fontSize: "0.85rem" }}>{text(t.description)}</td>
                      <td>
                        <button className="link-button danger-text" onClick={() => deleteTemplate(t.id)}>删除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button className="button" onClick={addTemplate} style={{ marginTop: "0.5rem" }}>
                + 添加断言模板
              </button>
            </>
          ) : (
            <p>选择一个行为查看断言模板</p>
          )}
        </div>
      </div>
    </div>
  );
}
