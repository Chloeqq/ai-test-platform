import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { authFetch } from "../lib/http";

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

async function getJson<T>(url: string): Promise<T> {
  const resp = await authFetch(url);
  if (!resp.ok) throw new Error(`${resp.status}`);
  return resp.json();
}

async function postJson(url: string, body: unknown): Promise<Response> {
  return authFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function deleteJson(url: string): Promise<Response> {
  return authFetch(url, { method: "DELETE" });
}

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
      const data = await getJson<{items: Behavior[]}>(`/api/behavior-registry/behaviors?page_code=${pageCode}`);
      setBehaviors(data.items);
    } finally { setLoading(false); }
  };

  const loadTemplates = async (id: number) => {
    const data = await getJson<{templates: Template[]}>(`/api/behavior-registry/behaviors/${id}`);
    setTemplates(data.templates || []);
  };

  useEffect(() => { loadBehaviors(); }, [pageCode]);

  const selectBehavior = async (b: Behavior) => {
    setSelected(b);
    await loadTemplates(b.id);
  };

  return (
    <div className="panel">
      <h1>断言模板管理</h1>
      <p>页面: <strong>{pageCode}</strong> — 基于 Behavior Registry 的断言配置</p>
      <p style={{ fontSize: "0.85rem", color: "#666" }}>
        当前为演示页面。完整 CRUD 功能可扩展。访问 /assets/behavior-registry?page_code=ORDER 可查看其他页面。
      </p>

      <div style={{ display: "flex", gap: "1.5rem", marginTop: "1rem" }}>
        <div style={{ flex: 1, maxWidth: "360px" }}>
          <h2>行为列表</h2>
          {loading ? <p>加载中...</p> : (
            <table className="data-table">
              <thead><tr><th>行为编码</th><th>场景</th><th>状态</th></tr></thead>
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

        <div style={{ flex: 2 }}>
          {selected ? (
            <>
              <h2>{selected.behavior_code}</h2>
              <p style={{ fontSize: "0.85rem" }}>
                {selected.label} | intent={selected.intent_type} | scenario={selected.scenario} | v{selected.version} | {selected.scope}
              </p>
              <table className="data-table" style={{ marginTop: "1rem" }}>
                <thead><tr><th>层</th><th>动作</th><th>目标</th><th>值</th><th>说明</th></tr></thead>
                <tbody>
                  {templates.map(t => (
                    <tr key={t.id}>
                      <td><span className="badge">{t.execution_layer}</span></td>
                      <td className="mono">{t.action}</td>
                      <td className="mono">{text(t.target)}</td>
                      <td className="mono">{text(t.value)}</td>
                      <td style={{ fontSize: "0.85rem" }}>{text(t.description)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {templates.length === 0 && <p style={{ color: "#999" }}>该行为暂无断言模板</p>}
            </>
          ) : (
            <p>选择一个行为查看断言模板</p>
          )}
        </div>
      </div>
    </div>
  );
}
