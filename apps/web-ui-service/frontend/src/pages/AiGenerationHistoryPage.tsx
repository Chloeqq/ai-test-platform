import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { listProjects, listWorkbenchHistory, type WorkbenchHistoryItem } from "../api/workbench";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { DEFAULT_PROJECT_CODE, normalizeProjectCode, projectOptions } from "../config/projects";

interface HistoryFilters {
  project_code: string;
  keyword: string;
  action: string;
  status: string;
}

const DEFAULT_FILTERS: HistoryFilters = {
  project_code: DEFAULT_PROJECT_CODE,
  keyword: "",
  action: "",
  status: "",
};

export function AiGenerationHistoryPage() {
  const [filters, setFilters] = useState<HistoryFilters>(DEFAULT_FILTERS);
  const [projectCodes, setProjectCodes] = useState<string[]>([DEFAULT_PROJECT_CODE]);
  const [rows, setRows] = useState<WorkbenchHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload(targetFilters = filters) {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listWorkbenchHistory({
        limit: 300,
        page: 1,
        page_size: 50,
        project_code: normalizeProjectCode(targetFilters.project_code),
        keyword: targetFilters.keyword.trim(),
        action: targetFilters.action.trim(),
        status: targetFilters.status.trim(),
        sort: "timestamp_desc",
      });
      setRows(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "加载生成历史失败");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadProjectOptions() {
      try {
        const projects = await listProjects();
        if (!cancelled) {
          setProjectCodes(projectOptions(projects.codes));
        }
      } catch {
        // Keep the default project option available if the project service is unavailable.
      }
    }
    void loadProjectOptions();
    void reload();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="page shell">
      <header className="header panel unified-topbar">
        <div>
          <h1>生成历史</h1>
          <p className="muted">统一从 `/api/workbench/history` 读取生成与执行链路事件。</p>
        </div>
        <div className="header-actions unified-topbar-actions">
          <Link className="button secondary" to="/ai-generation">
            返回生成页
          </Link>
        </div>
      </header>

      <FilterBar>
        <label>
          项目
          <select
            value={filters.project_code}
            onChange={(event) => setFilters((prev) => ({ ...prev, project_code: normalizeProjectCode(event.target.value) }))}
          >
            {projectCodes.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          关键词
          <input
            value={filters.keyword}
            placeholder="case_id / run_id / detail"
            onChange={(event) => setFilters((prev) => ({ ...prev, keyword: event.target.value }))}
          />
        </label>
        <label>
          动作
          <input
            value={filters.action}
            placeholder="例如 generated / rerun"
            onChange={(event) => setFilters((prev) => ({ ...prev, action: event.target.value }))}
          />
        </label>
        <label>
          状态
          <input
            value={filters.status}
            placeholder="例如 passed / failed"
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
          />
        </label>
        <div className="header-actions">
          <button type="button" className="button" onClick={() => void reload()} disabled={loading}>
            查询
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setFilters(DEFAULT_FILTERS);
              void reload(DEFAULT_FILTERS);
            }}
            disabled={loading}
          >
            重置
          </button>
        </div>
      </FilterBar>

      <DataTable title={`历史条目：${rows.length}`} loading={loading} loadingText="正在加载历史..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>状态</th>
                <th>项目</th>
                <th>Case ID</th>
                <th>Run ID</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((item) => (
                  <tr key={String(item.timestamp || item.run_id || item.case_id || Math.random())}>
                    <td>{formatDateTime(item.timestamp)}</td>
                    <td>{item.action || "-"}</td>
                    <td>{item.status || "-"}</td>
                    <td className="mono">{item.project_code || "-"}</td>
                    <td className="mono">{item.case_id || "-"}</td>
                    <td className="mono">{item.run_id || "-"}</td>
                    <td>{item.detail_summary || "-"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>
                    <EmptyState title="暂无生成历史" description="完成一次测试点提取或用例生成后，系统会在这里记录全过程。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
