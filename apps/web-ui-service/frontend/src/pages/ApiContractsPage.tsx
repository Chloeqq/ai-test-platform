import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { listTestCasesDb, listTestPointAssets } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function ApiContractsPage() {
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [sourceType, setSourceType] = useState<string>("openapi_spec");
  const [assetItems, setAssetItems] = useState<Array<Record<string, unknown>>>([]);
  const [assetSummary, setAssetSummary] = useState<Record<string, unknown>>({});
  const [apiCases, setApiCases] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetProject = project, targetKeyword = keyword, targetSourceType = sourceType) {
    setLoading(true);
    setErrorText("");
    try {
      const [assetPayload, casePayload] = await Promise.all([
        listTestPointAssets({
          project: normalizeProjectCode(targetProject),
          keyword: targetKeyword.trim(),
          source_type: targetSourceType.trim(),
        }),
        listTestCasesDb({
          project_code: targetProject || "",
          q: targetKeyword.trim(),
          test_type: "api",
          sort_field: "updated_at",
          sort_order: "desc",
          page: 1,
          page_size: 50,
        }),
      ]);
      setAssetItems(Array.isArray(assetPayload.items) ? assetPayload.items : []);
      setAssetSummary((assetPayload.selection_summary || {}) as Record<string, unknown>);
      setApiCases(Array.isArray(casePayload.items) ? casePayload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "API 契约资产加载失败");
      setAssetItems([]);
      setAssetSummary({});
      setApiCases([]);
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

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>API 契约资产</h1>
            <p className="muted">统一查看契约来源测试点资产与 API 自动化用例覆盖情况。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to="/assets/test-points">
              测试点资产
            </Link>
            <Link className="button secondary" to="/cases">
              用例中心
            </Link>
          </div>
        </header>

        <section className="asset-kpi-grid">
          <article className="asset-kpi-card metric-tone-info">
            <span>契约资产数</span>
            <strong>{assetItems.length}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-success">
            <span>就绪</span>
            <strong>{numberValue(assetSummary.ready_count)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-warning">
            <span>待审核</span>
            <strong>{numberValue(assetSummary.needs_review_count)}</strong>
          </article>
          <article className="asset-kpi-card metric-tone-accent">
            <span>API 用例数</span>
            <strong>{apiCases.length}</strong>
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
          <label>
            来源类型
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="openapi_spec">openapi_spec</option>
              <option value="openapi">openapi</option>
              <option value="api_contract">api_contract</option>
              <option value="">全部</option>
            </select>
          </label>
          <label className="grow">
            关键词
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="资产编码 / 用例编码 / 标题 / 页面" />
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
                setSourceType("openapi_spec");
                setAssetItems([]);
                setAssetSummary({});
                setApiCases([]);
                void reload(DEFAULT_PROJECT_CODE, "", "openapi_spec");
              }}
            >
              重置全部
            </button>
          </div>
        </section>
        <p className="asset-hint">提示：source_type 建议先选 openapi_spec；若结果为空可切换“全部”并扩大关键词范围。</p>

        {loading ? <section className="asset-card">正在加载 API 契约资产...</section> : null}
        {errorText ? <section className="asset-card error">{errorText}</section> : null}

        {!loading && !errorText ? (
          <section className="asset-grid-2">
            <article className="asset-card">
              <h2>契约来源测试点资产</h2>
              <div className="asset-list-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>资产编码</th>
                      <th>标题</th>
                      <th>来源</th>
                      <th>点位数</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assetItems.length ? (
                      assetItems.map((item, index) => (
                        <tr key={String(item.asset_id || index)}>
                          <td className="mono">{text(item.asset_id)}</td>
                          <td>{text(item.title)}</td>
                          <td>{text(item.source_type)}</td>
                          <td>{numberValue(item.point_count)}</td>
                          <td>{formatDateTime(item.updated_at)}</td>
                          <td>
                            <Link to={`/assets/test-points/${encodeURIComponent(String(item.asset_id || ""))}`}>详情</Link>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="asset-empty">
                          暂无契约资产记录。
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="asset-card">
              <h2>API 自动化用例覆盖</h2>
              <div className="asset-list-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Case ID</th>
                      <th>名称</th>
                      <th>状态</th>
                      <th>最近结果</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiCases.length ? (
                      apiCases.map((item, index) => {
                        const caseId = String(item.case_id || "").trim();
                        return (
                          <tr key={caseId || String(index)}>
                            <td className="mono">{text(caseId)}</td>
                            <td>{text(item.case_title || item.name)}</td>
                            <td>{text(item.lifecycle_status || item.status)}</td>
                            <td>{text(item.last_execution_result || item.last_result)}</td>
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
                          暂无 API 类型用例。
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
