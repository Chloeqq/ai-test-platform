import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listTestCaseGenerationFailures, type TestCaseGenerationFailuresResponse } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode } from "../config/projects";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { formatDateTime } from "../lib/datetime";

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

function projectOptions(codes: unknown): string[] {
  const values = Array.isArray(codes) ? codes.map((item) => normalizeProjectCode(item)).filter(Boolean) : [];
  return Array.from(new Set([DEFAULT_PROJECT_CODE, ...values]));
}

export function CaseGenerationFailuresPage() {
  const [searchParams] = useSearchParams();
  const [project, setProject] = useState<string>(normalizeProjectCode(searchParams.get("project") || DEFAULT_PROJECT_CODE));
  const [assetId, setAssetId] = useState<string>(searchParams.get("asset_id") || searchParams.get("source_asset") || "");
  const [keyword, setKeyword] = useState<string>("");
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [pagination, setPagination] = useState<TestCaseGenerationFailuresResponse["pagination"]>({});
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(
    targetPage = 1,
    targetProject = project,
    targetAssetId = assetId,
    targetKeyword = keyword,
    targetPageSize = pageSize,
  ) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listTestCaseGenerationFailures({
        project: normalizeProjectCode(targetProject),
        asset_id: targetAssetId.trim(),
        keyword: targetKeyword.trim(),
        page_index: targetPage,
        page_size: targetPageSize,
      });
      setItems(Array.isArray(payload.items) ? payload.items : []);
      setSummary(payload.summary || {});
      setPagination(payload.pagination || {});
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "生成失败列表加载失败");
      setItems([]);
      setSummary({});
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
          setProjectCodes(projectOptions(projects.codes));
        }
      } catch {
        // Keep the default project selector usable.
      }
      if (!cancelled) {
        await reload(1);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentPage = Number(pagination?.page || 1);
  const totalPages = Number(pagination?.total_pages || 1);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>用例生成失败</h1>
          <p className="muted">集中呈现已审核测试点在脚本编译阶段的失败原因，便于回到资产或页面对象进行治理。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={`/cases?project=${encodeURIComponent(project)}`}>
            用例中心
          </Link>
          <Link className="button" to={`/assets/test-points?project=${encodeURIComponent(project)}`}>
            测试点资产
          </Link>
        </div>
      </header>

      <section className="panel stat-grid">
        <article className="stat-card metric-tone-danger">
          <span className="label">失败测试点</span>
          <strong>{numberValue(summary.total)}</strong>
        </article>
        <article className="stat-card metric-tone-warning">
          <span className="label">涉及资产</span>
          <strong>{numberValue(summary.asset_count)}</strong>
        </article>
        <article className="stat-card metric-tone-cyan">
          <span className="label">涉及 intent</span>
          <strong>{numberValue(summary.intent_count)}</strong>
        </article>
      </section>

      <FilterBar>
        <label>
          项目
          <select
            value={project}
            onChange={(event) => {
              const nextProject = normalizeProjectCode(event.target.value);
              setProject(nextProject);
              void reload(1, nextProject);
            }}
          >
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label>
          资产编码
          <input value={assetId} onChange={(event) => setAssetId(event.target.value)} placeholder="例如 mall-web-login-auth-fn-ai-0021" />
        </label>
        <label>
          关键词
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="intent、失败原因、页面" />
        </label>
        <label>
          每页
          <select
            value={pageSize}
            onChange={(event) => {
              const nextSize = Number(event.target.value);
              setPageSize(nextSize);
              void reload(1, project, assetId, keyword, nextSize);
            }}
          >
            {[10, 20, 50, 100].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload(1)}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setAssetId("");
              setKeyword("");
              void reload(1, project, "", "");
            }}
          >
            重置
          </button>
        </div>
      </FilterBar>

      <DataTable loading={loading} loadingText="正在加载生成失败列表..." errorText={errorText}>
        <table>
          <thead>
            <tr>
              <th>资产</th>
              <th>intent</th>
              <th>失败类型</th>
              <th>阶段</th>
              <th>原因</th>
              <th>建议动作</th>
              <th>发生时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.length ? (
              items.map((item, index) => {
                const rowAssetId = text(item.asset_id);
                return (
                  <tr key={`${rowAssetId}-${text(item.intent_id)}-${index}`}>
                    <td>
                      <strong>{text(item.asset_title)}</strong>
                      <div className="case-id">{rowAssetId}</div>
                    </td>
                    <td>
                      <span className="mono">{text(item.intent_id)}</span>
                      <div>{text(item.title)}</div>
                    </td>
                    <td>
                      <span className="detail-status detail-status--danger">{text(item.failure_type)}</span>
                    </td>
                    <td className="mono">{text(item.stage)}</td>
                    <td>{text(item.reason || item.message || item.code)}</td>
                    <td>{text(item.suggestion)}</td>
                    <td>{formatDateTime(item.failed_at)}</td>
                    <td>
                      <Link to={`/assets/test-points/${encodeURIComponent(rowAssetId)}?project=${encodeURIComponent(project)}`}>查看资产</Link>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8}>
                  <EmptyState title="暂无生成失败" description="当前筛选条件下没有编译失败记录。若刚刚发生失败，请重新生成后刷新本页。" />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </DataTable>

      <section className="panel pagination-bar">
        <button type="button" className="button secondary" disabled={currentPage <= 1} onClick={() => void reload(currentPage - 1)}>
          上一页
        </button>
        <span>
          第 {currentPage} / {totalPages} 页，共 {numberValue(pagination?.total_items)} 条
        </span>
        <button type="button" className="button secondary" disabled={currentPage >= totalPages} onClick={() => void reload(currentPage + 1)}>
          下一页
        </button>
      </section>
    </main>
  );
}
