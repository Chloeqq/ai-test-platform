import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listProjects } from "../api/workbench";
import { listWorkbenchCases, type CasesListResponse } from "../api/assets";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
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

export function CasesPage() {
  const [project, setProject] = useState<string>("default");
  const [projectCodes, setProjectCodes] = useState<string[]>([]);
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [pagination, setPagination] = useState<CasesListResponse["pagination"]>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetProject = project, targetPage = 1) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listWorkbenchCases({
        project: targetProject || "default",
        page: targetPage,
        page_size: 20,
      });
      setItems(Array.isArray(payload.items) ? payload.items : []);
      setPagination(payload.pagination || {});
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例列表加载失败");
      setItems([]);
      setPagination({});
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
        // Ignore project list errors; page can still work with default project.
      }
      if (!cancelled) {
        await reload(project || "default", 1);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleItems = items.filter((item) => {
    const token = keyword.trim().toLowerCase();
    if (!token) {
      return true;
    }
    const corpus = [
      text(item.case_id),
      text(item.title),
      text(item.name),
      text(item.module),
      text(item.page),
      text(item.priority),
    ]
      .join(" ")
      .toLowerCase();
    return corpus.includes(token);
  });

  const totalCount = Number(pagination?.total_items || items.length || 0);
  const failedCount = visibleItems.filter((item) => {
    const status = String(item.last_result || item.status || "").toLowerCase();
    return status.includes("fail") || status.includes("失败");
  }).length;
  const automatedCount = visibleItems.filter((item) => {
    const automation = String(item.automation_status || "").toLowerCase();
    return automation.includes("auto") || automation.includes("自动化");
  }).length;
  const automationRate = visibleItems.length ? Math.round((automatedCount / visibleItems.length) * 100) : 0;

  return (
    <main className="shell">
      <section className="hero-card cases-shell">
        <div className="cases-page-head">
          <div className="cases-page-copy">
            <p className="breadcrumb">
              <span>测试资产</span>
              <span className="crumb-sep">/</span>
              <span>用例中心</span>
            </p>
          </div>
          <div className="cases-page-actions">
            <Link className="button secondary" to="/ai-generation">
              前往 AI 生成
            </Link>
            <Link className="button secondary" to="/assets/test-points">
              测试点资产
            </Link>
          </div>
        </div>

        <section className="cases-reference-layout">
          <aside className="cases-tree-pane">
            <div className="cases-tree-card">
              <div className="cases-tree-head">
                <h2>模块树</h2>
                <span className="cases-tree-total">{visibleItems.length}</span>
              </div>
              <div className="cases-tree-toolbar-actions">
                <button type="button" className="button secondary">
                  展开全部
                </button>
                <button type="button" className="button secondary">
                  收起全部
                </button>
              </div>
              <p className="muted">当前 React 版先保留模块树位置，下一步补齐树节点交互。</p>
            </div>
          </aside>

          <section className="cases-table-pane">
            <div className="cases-table-card">
              <header className="cases-table-header">
                <div className="cases-table-copy">
                  <h2>全部用例</h2>
                </div>
                <button id="btn-new-case" className="button" type="button">
                  手动新建草稿
                </button>
              </header>

              <section className="cases-stats-strip">
                <article className="cases-stat-card">
                  <span className="cases-stat-label">总用例</span>
                  <strong className="cases-stat-value">{totalCount}</strong>
                </article>
                <article className="cases-stat-card">
                  <span className="cases-stat-label">自动化率</span>
                  <strong className="cases-stat-value">{automationRate}%</strong>
                </article>
                <article className="cases-stat-card">
                  <span className="cases-stat-label">通过率</span>
                  <strong className="cases-stat-value">{Math.max(0, 100 - Math.round((failedCount / Math.max(visibleItems.length, 1)) * 100))}%</strong>
                </article>
                <article className="cases-stat-card">
                  <span className="cases-stat-label">失败用例</span>
                  <strong className="cases-stat-value">{failedCount}</strong>
                </article>
              </section>

              <section className="cases-toolbar-card">
                <div className="cases-search-form">
                  <label className="search-field-group cases-project-field">
                    <select
                      value={project}
                      onChange={(event) => {
                        const next = String(event.target.value || "").trim() || "default";
                        setProject(next);
                        void reload(next, 1);
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
                  <label className="search-field-group">
                    <input
                      value={keyword}
                      onChange={(event) => setKeyword(event.target.value)}
                      type="search"
                      placeholder="搜索用例ID、名称、模块"
                    />
                  </label>
                </div>
                <div className="search-command-group">
                  <button type="button" className="button" onClick={() => void reload(project || "default", Number(pagination?.page || 1))}>
                    重新加载
                  </button>
                  <button type="button" className="button secondary" onClick={() => setKeyword("")}>
                    重置搜索
                  </button>
                </div>
              </section>

              <div className="table-wrap cases-table-wrap">
                {loading ? <p>正在加载用例列表...</p> : null}
                {errorText ? <p className="error">{errorText}</p> : null}
                {!loading && !errorText ? (
                  <table className="case-table cases-grid-table">
                    <thead>
                      <tr>
                        <th>用例 ID</th>
                        <th>名称</th>
                        <th>优先级</th>
                        <th>执行状态</th>
                        <th>所属模块</th>
                        <th>更新时间</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleItems.length ? (
                        visibleItems.map((item, index) => (
                          <tr key={String(item.case_id || index)}>
                            <td className="mono">{text(item.case_id)}</td>
                            <td>{text(item.title || item.name)}</td>
                            <td>{text(item.priority)}</td>
                            <td>{text(item.last_result || item.status)}</td>
                            <td>{text(item.module || item.page)}</td>
                            <td>{formatDate(item.updated_at)}</td>
                            <td>
                              <Link to={`/cases/${encodeURIComponent(String(item.case_id || ""))}`}>查看</Link>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7}>当前项目下暂无用例。</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                ) : null}
              </div>

              <div className="case-list-footer">
                <div className="case-list-footer-meta">
                  <span>当前页 {visibleItems.length} 条</span>
                  <span className="case-list-footer-sep">·</span>
                  <span>
                    第 {Number(pagination?.page || 1)} / {Number(pagination?.total_pages || 1)} 页
                  </span>
                </div>
              </div>
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}
