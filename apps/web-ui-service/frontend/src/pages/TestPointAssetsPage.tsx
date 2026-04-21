import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listTestPointAssets } from "../api/assets";
import { listProjects } from "../api/workbench";

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

function formatDate(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

export function TestPointAssetsPage() {
  const [project, setProject] = useState<string>("default");
  const [projectCodes, setProjectCodes] = useState<string[]>([]);
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectionSummary, setSelectionSummary] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetProject = project) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listTestPointAssets({
        project: targetProject || "default",
        keyword: keyword.trim(),
      });
      setItems(Array.isArray(payload.items) ? payload.items : []);
      setSelectionSummary((payload.selection_summary || {}) as Record<string, unknown>);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "测试点资产加载失败");
      setItems([]);
      setSelectionSummary({});
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          const codes = Array.isArray(projects.codes) ? projects.codes : [];
          setProjectCodes(codes);
          if (codes.length && !project) {
            setProject(codes[0]);
          }
        }
      } catch {
        // Ignore project list errors.
      }
      if (!cancelled) {
        await reload(project || "default");
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>测试点资产（React + TypeScript）</h1>
          <p className="muted">查看测试点资产、可回归状态和门禁准备度。</p>
        </div>
      </header>

      <section className="panel filters">
        <label>
          项目
          <select
            value={project}
            onChange={(event) => {
              const next = String(event.target.value || "").trim() || "default";
              setProject(next);
              void reload(next);
            }}
          >
            <option value="default">default</option>
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          关键词
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="asset_id / title / requirement" />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload(project || "default")}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setKeyword("");
              void reload(project || "default");
            }}
          >
            重置
          </button>
        </div>
      </section>

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">资产总数</span>
          <strong>{numberValue(selectionSummary.total_assets)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">Ready</span>
          <strong>{numberValue(selectionSummary.ready_count)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">Needs Review</span>
          <strong>{numberValue(selectionSummary.needs_review_count)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">Blocked</span>
          <strong>{numberValue(selectionSummary.blocked_count)}</strong>
        </article>
      </section>

      <section className="panel table-panel">
        {loading ? <p>正在加载测试点资产...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
          <table>
            <thead>
              <tr>
                <th>Asset ID</th>
                <th>标题</th>
                <th>页面</th>
                <th>来源</th>
                <th>点位数</th>
                <th>置信度</th>
                <th>更新时间</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item, index) => (
                  <tr key={String(item.asset_id || index)}>
                    <td className="mono">{text(item.asset_id)}</td>
                    <td>{text(item.title)}</td>
                    <td>{text(item.page)}</td>
                    <td>{text(item.source_type)}</td>
                    <td>{numberValue(item.point_count)}</td>
                    <td>{numberValue(item.confidence)}</td>
                    <td>{formatDate(item.updated_at)}</td>
                    <td>
                      <Link to={`/assets/test-points/${encodeURIComponent(String(item.asset_id || ""))}`}>查看</Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>暂无测试点资产。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}
