import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listWorkbenchHistory, type WorkbenchHistoryItem } from "../api/workbench";

interface HistoryFilters {
  project_code: string;
  keyword: string;
  action: string;
  status: string;
}

const DEFAULT_FILTERS: HistoryFilters = {
  project_code: "",
  keyword: "",
  action: "",
  status: "",
};

function formatDate(value: string | undefined): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function AiGenerationHistoryPage() {
  const [filters, setFilters] = useState<HistoryFilters>(DEFAULT_FILTERS);
  const [rows, setRows] = useState<WorkbenchHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  async function reload() {
    setLoading(true);
    setErrorText("");
    try {
      const payload = await listWorkbenchHistory({
        limit: 300,
        page: 1,
        page_size: 50,
        project_code: filters.project_code.trim(),
        keyword: filters.keyword.trim(),
        action: filters.action.trim(),
        status: filters.status.trim(),
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
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>生成历史（React + TypeScript）</h1>
          <p className="muted">统一从 `/api/workbench/history` 读取生成与执行链路事件。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/ai-generation">
            返回生成页
          </Link>
        </div>
      </header>

      <section className="panel filters">
        <label>
          项目
          <input
            value={filters.project_code}
            placeholder="project_code"
            onChange={(event) => setFilters((prev) => ({ ...prev, project_code: event.target.value }))}
          />
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
              setTimeout(() => {
                void reload();
              }, 0);
            }}
            disabled={loading}
          >
            重置
          </button>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="table-head">
          <strong>历史条目：{rows.length}</strong>
        </div>
        {loading ? <p>正在加载历史...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
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
                    <td>{formatDate(item.timestamp)}</td>
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
                  <td colSpan={7}>暂无历史记录。</td>
                </tr>
              )}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}
