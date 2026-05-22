import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getWorkbenchCaseDictionaries, listTestCasesDb } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function normalizeDictionaryItems(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (typeof item === "string") {
        return item.trim();
      }
      if (item && typeof item === "object") {
        const payload = item as Record<string, unknown>;
        return String(payload.label || payload.name || payload.code || payload.value || "").trim();
      }
      return "";
    })
    .filter(Boolean);
}

export function DataTemplatesPage() {
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [dictionaryGroups, setDictionaryGroups] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetProject = project, targetKeyword = keyword) {
    setLoading(true);
    setErrorText("");
    try {
      const [dictPayload, casePayload] = await Promise.all([
        getWorkbenchCaseDictionaries(),
        listTestCasesDb({
          project_code: targetProject || "",
          q: targetKeyword.trim(),
          sort_field: "updated_at",
          sort_order: "desc",
          page: 1,
          page_size: 100,
        }),
      ]);
      setDictionaryGroups((dictPayload.items || {}) as Record<string, unknown>);
      setItems(Array.isArray(casePayload.items) ? casePayload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "数据模板页加载失败");
      setDictionaryGroups({});
      setItems([]);
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
          setProjectCodes(projectOptions(projects.codes));
        }
      } catch {
        // Ignore.
      }
      if (!cancelled) {
        await reload();
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const configuredItems = useMemo(
    () => items.filter((item) => Boolean(item.data_config_enabled) || String(item.case_type || "").toLowerCase().includes("ddt")),
    [items],
  );
  const dictionaryEntries = useMemo(() => Object.entries(dictionaryGroups), [dictionaryGroups]);
  const totalDictionaryValues = dictionaryEntries.reduce((sum, [, value]) => sum + normalizeDictionaryItems(value).length, 0);

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>数据模板与字典</h1>
            <p className="muted">统一查看用例字典资产与数据驱动模板覆盖，支撑快速新建。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to="/cases">
              用例中心
            </Link>
            <Link className="button secondary" to="/assets/test-points">
              测试点资产
            </Link>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card metric-tone-info">
            <span>字典分组</span>
            <strong>{dictionaryEntries.length}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-cyan">
            <span>字典项总数</span>
            <strong>{totalDictionaryValues}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-accent">
            <span>可用例总数</span>
            <strong>{items.length}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>数据模板用例</span>
            <strong>{configuredItems.length}</strong>
          </article>
        </section>

        <section className="asset-toolbar">
          <label>
            项目
            <select value={project} onChange={(event) => setProject(normalizeProjectCode(event.target.value))}>
              {projectCodes.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>
          <label className="grow">
            关键词
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="按 case_id / 名称 / 模块筛选模板用例" />
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reload()}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setKeyword("");
                setItems([]);
                setDictionaryGroups({});
                void reload(DEFAULT_PROJECT_CODE, "");
              }}
            >
              重置全部
            </button>
          </div>
        </section>
        <p className="asset-hint">提示：可先按项目与关键词缩小范围，再查看字典分组和数据模板用例，便于快速新建配置。</p>

        {loading ? <section className="asset-card">正在加载数据模板资产...</section> : null}
        {errorText ? <section className="asset-card error">{errorText}</section> : null}

        {!loading && !errorText ? (
          <section className="asset-grid-2">
            <article className="asset-card">
              <h2>字典分组</h2>
              <div className="asset-dictionary-grid">
                {dictionaryEntries.length ? (
                  dictionaryEntries.map(([group, rawItems]) => {
                    const values = normalizeDictionaryItems(rawItems);
                    return (
                      <div key={group} className="asset-dictionary-card">
                        <h3>{group}</h3>
                        <p className="muted">共 {values.length} 项</p>
                        <div className="asset-pill-strip">
                          {values.length ? (
                            values.map((item) => (
                              <span key={`${group}-${item}`} className="asset-pill">
                                {item}
                              </span>
                            ))
                          ) : (
                            <span className="muted">暂无配置</span>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <p className="asset-empty">暂无字典分组数据。</p>
                )}
              </div>
            </article>

            <article className="asset-card">
              <h2>数据模板用例</h2>
              <div className="asset-list-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Case ID</th>
                      <th>名称</th>
                      <th>类型</th>
                      <th>状态</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {configuredItems.length ? (
                      configuredItems.map((item, index) => {
                        const caseId = String(item.case_id || "").trim();
                        return (
                          <tr key={caseId || String(index)}>
                            <td className="mono">{text(caseId)}</td>
                            <td>{text(item.case_title || item.name)}</td>
                            <td>{text(item.case_type || item.test_type)}</td>
                            <td>{text(item.lifecycle_status || item.status)}</td>
                            <td>{formatDateTime(item.updated_at)}</td>
                            <td>
                              <Link to={`/cases/${encodeURIComponent(caseId)}`}>详情</Link>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={6} className="asset-empty">
                          当前项目下暂无数据模板用例。
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        ) : null}
      </section>
    </main>
  );
}
