import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { compareTestCaseVersions, getTestCaseDbDetail, listTestCasesDb, type CaseVersionCompareResponse } from "../api/assets";
import { listProjects } from "../api/workbench";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

function toVersionNo(value: unknown): number {
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? Math.floor(num) : 0;
}

function caseIdOf(item: Record<string, unknown>): string {
  return String(item.case_id || "").trim();
}

export function CaseVersionsPage() {
  const location = useLocation();
  const initialCaseId = useMemo(() => new URLSearchParams(location.search).get("case_id") || "", [location.search]);
  const [project, setProject] = useState<string>(DEFAULT_PROJECT_CODE);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [keyword, setKeyword] = useState<string>("");
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>(initialCaseId);
  const [versions, setVersions] = useState<Array<Record<string, unknown>>>([]);
  const [fromVersion, setFromVersion] = useState<number>(0);
  const [toVersion, setToVersion] = useState<number>(0);
  const [compareResult, setCompareResult] = useState<CaseVersionCompareResponse>({});
  const [loadingCases, setLoadingCases] = useState<boolean>(true);
  const [loadingVersions, setLoadingVersions] = useState<boolean>(false);
  const [comparing, setComparing] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");

  async function reloadCases(targetProject = project, targetKeyword = keyword) {
    setLoadingCases(true);
    setErrorText("");
    try {
      const payload = await listTestCasesDb({
        project_code: targetProject || "",
        q: targetKeyword.trim(),
        sort_field: "updated_at",
        sort_order: "desc",
        page: 1,
        page_size: 60,
      });
      const rows = Array.isArray(payload.items) ? payload.items : [];
      setItems(rows);
      if (!selectedCaseId && rows.length) {
        setSelectedCaseId(caseIdOf(rows[0]));
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例版本列表加载失败");
      setItems([]);
    } finally {
      setLoadingCases(false);
    }
  }

  async function loadCaseVersions(caseId: string) {
    const normalized = String(caseId || "").trim();
    if (!normalized) {
      setVersions([]);
      setFromVersion(0);
      setToVersion(0);
      setCompareResult({});
      return;
    }
    setLoadingVersions(true);
    setErrorText("");
    setCompareResult({});
    try {
      const detail = await getTestCaseDbDetail(normalized);
      const rows = (Array.isArray(detail.versions) ? detail.versions : [])
        .slice()
        .sort((a, b) => toVersionNo(b.version_no) - toVersionNo(a.version_no));
      setVersions(rows);
      const latest = toVersionNo(rows[0]?.version_no);
      const previous = toVersionNo(rows[1]?.version_no) || latest;
      setToVersion(latest);
      setFromVersion(previous);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "用例版本详情加载失败");
      setVersions([]);
      setFromVersion(0);
      setToVersion(0);
    } finally {
      setLoadingVersions(false);
    }
  }

  async function runCompare() {
    if (!selectedCaseId || !fromVersion || !toVersion || comparing) {
      return;
    }
    setComparing(true);
    setErrorText("");
    try {
      const payload = await compareTestCaseVersions(selectedCaseId, {
        from_version: fromVersion,
        to_version: toVersion,
      });
      setCompareResult(payload);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "版本对比失败");
      setCompareResult({});
    } finally {
      setComparing(false);
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
        // Ignore project bootstrap errors.
      }
      if (!cancelled) {
        await reloadCases();
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void loadCaseVersions(selectedCaseId);
  }, [selectedCaseId]);

  const compareDisabled = !selectedCaseId || !fromVersion || !toVersion || fromVersion === toVersion || comparing;

  return (
    <main className="shell">
      <section className="hero-card asset-shell">
        <header className="asset-hero">
          <div>
            <h1>用例版本管理</h1>
            <p className="muted">统一查看版本链路、比对脚本变更并定位差异行。</p>
          </div>
          <div className="asset-actions">
            <Link className="button secondary" to="/cases">
              返回用例中心
            </Link>
            <Link className="button secondary" to="/cases/review">
              待审核队列
            </Link>
          </div>
        </header>

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
            搜索用例
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="输入 case_id / 名称 / 模块" />
          </label>
          <div className="asset-actions">
            <button type="button" className="button" onClick={() => void reloadCases()}>
              查询
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setProject(DEFAULT_PROJECT_CODE);
                setKeyword("");
                setSelectedCaseId("");
                setVersions([]);
                setFromVersion(0);
                setToVersion(0);
                setCompareResult({});
                void reloadCases(DEFAULT_PROJECT_CODE, "");
              }}
            >
              重置全部
            </button>
          </div>
        </section>

        <section className="asset-grid-2">
          <article className="asset-card">
            <h2>用例列表</h2>
            {loadingCases ? <p>正在加载用例列表...</p> : null}
            {errorText ? <p className="error">{errorText}</p> : null}
            {!loadingCases && !errorText ? (
              <div className="asset-list-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Case ID</th>
                      <th>名称</th>
                      <th>状态</th>
                      <th>更新时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.length ? (
                      items.map((item, index) => {
                        const caseId = caseIdOf(item);
                        return (
                          <tr key={caseId || String(index)} className={caseId === selectedCaseId ? "is-active" : ""} onClick={() => setSelectedCaseId(caseId)}>
                            <td className="mono">{text(caseId)}</td>
                            <td>{text(item.case_title || item.name)}</td>
                            <td>{text(item.lifecycle_status || item.status)}</td>
                            <td>{formatDateTime(item.updated_at)}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={4} className="asset-empty">
                          暂无用例数据。
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}
          </article>

          <article className="asset-card">
            <h2>版本详情</h2>
            <p className="muted">
              当前用例: <span className="mono">{text(selectedCaseId)}</span>
            </p>
            {loadingVersions ? <p>正在加载版本信息...</p> : null}
            {!loadingVersions ? (
              <>
                <section className="asset-toolbar">
                  <label>
                    From
                    <select value={fromVersion || ""} onChange={(event) => setFromVersion(Number(event.target.value || 0))}>
                      {versions.map((version) => {
                        const versionNo = toVersionNo(version.version_no);
                        return (
                          <option key={`from-${versionNo}`} value={versionNo}>
                            v{versionNo}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                  <label>
                    To
                    <select value={toVersion || ""} onChange={(event) => setToVersion(Number(event.target.value || 0))}>
                      {versions.map((version) => {
                        const versionNo = toVersionNo(version.version_no);
                        return (
                          <option key={`to-${versionNo}`} value={versionNo}>
                            v{versionNo}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                  <div className="asset-actions">
                    <button type="button" className="button" onClick={() => void runCompare()} disabled={compareDisabled}>
                      对比版本
                    </button>
                  </div>
                </section>
                <p className="asset-hint">提示：优先选择相邻版本（如 v3→v4）定位改动更快，失败时请确认用例存在至少两个版本。</p>

                <div className="asset-pill-strip">
                  {versions.map((version) => {
                    const versionNo = toVersionNo(version.version_no);
                    return (
                      <span key={versionNo} className="asset-pill">
                        v{versionNo} · {text(version.changed_by)} · {formatDateTime(version.created_at)}
                      </span>
                    );
                  })}
                </div>

                <section className="asset-kpi-grid compact">
                  <article className="asset-kpi-card">
                    <span>新增行</span>
                    <strong>{Number(compareResult.added_lines || 0)}</strong>
                  </article>
                  <article className="asset-kpi-card">
                    <span>删除行</span>
                    <strong>{Number(compareResult.removed_lines || 0)}</strong>
                  </article>
                </section>

                <pre className="json-block asset-diff-block">{(compareResult.diff_lines || []).join("\n") || "请选择版本后执行对比。"}</pre>
              </>
            ) : null}
          </article>
        </section>
      </section>
    </main>
  );
}
