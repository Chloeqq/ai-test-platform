import { startTransition, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import {
  type ExecutionTask,
  listExecutionTasks,
  listProjects,
  type ProjectItem,
} from "../api/workbench";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { projectOptions } from "../config/projects";

interface TaskFilters {
  project_code: string;
  status: string;
  source: string;
  keyword: string;
}

const DEFAULT_FILTERS: TaskFilters = {
  project_code: "",
  status: "",
  source: "",
  keyword: "",
};

function matchesKeyword(task: ExecutionTask, keyword: string): boolean {
  const normalized = keyword.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const fields = [
    task.task_id,
    task.run_id,
    task.case_id,
    task.project_code,
    task.status,
    task.queue_status,
    task.source,
    task.execution_record_path,
    task.manifest_path,
  ]
    .map((item) => String(item || "").toLowerCase())
    .join(" ");
  return fields.includes(normalized);
}

export function ExecutionRunsPage() {
  const [searchParams] = useSearchParams();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [tasks, setTasks] = useState<ExecutionTask[]>([]);
  const [filters, setFilters] = useState<TaskFilters>({
    ...DEFAULT_FILTERS,
    keyword: searchParams.get("keyword") || "",
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");
  const [lastUpdated, setLastUpdated] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const [projectData, taskData] = await Promise.all([
          listProjects(),
          listExecutionTasks({ limit: 200 }),
        ]);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          const sourceItems = Array.isArray(projectData.items) ? projectData.items : [];
          const payloadCodes = Array.isArray(projectData.codes) ? projectData.codes : [];
          const codes = projectOptions(payloadCodes.length ? payloadCodes : sourceItems.map((item) => item.project_code));
          setProjects(codes.map((code) => sourceItems.find((item) => String(item.project_code || "").trim() === code) || { project_code: code }));
          setTasks(Array.isArray(taskData.items) ? taskData.items : []);
          setLastUpdated(formatDateTime(new Date().toISOString()));
        });
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "执行任务加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (filters.project_code && String(task.project_code || "").trim().toLowerCase() !== filters.project_code) {
        return false;
      }
      if (filters.status && String(task.status || "").trim().toLowerCase() !== filters.status) {
        return false;
      }
      if (filters.source && String(task.source || "").trim().toLowerCase() !== filters.source) {
        return false;
      }
      return matchesKeyword(task, filters.keyword);
    });
  }, [filters, tasks]);

  const total = visibleTasks.length;

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>执行任务</h1>
          <p className="muted">执行中心页面已切换到 TypeScript + React 主链。</p>
        </div>
        <div className="header-actions">
          <span className="muted">最后刷新：{lastUpdated || "-"}</span>
          <Link className="button secondary" to="/execution/runs">
            刷新当前页
          </Link>
        </div>
      </header>

      <FilterBar>
        <label>
          项目
          <select
            value={filters.project_code}
            onChange={(event) => {
              const value = String(event.target.value || "").trim().toLowerCase();
              setFilters((prev) => ({ ...prev, project_code: value }));
            }}
          >
            <option value="">全部项目</option>
            {projects.map((project) => {
              const projectCode = String(project.project_code || "").trim().toLowerCase();
              return (
                <option key={projectCode} value={projectCode}>
                  {projectCode || "-"} {project.status ? `(${project.status})` : ""}
                </option>
              );
            })}
          </select>
        </label>

        <label>
          状态
          <select
            value={filters.status}
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value.trim().toLowerCase() }))}
          >
            <option value="">全部</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="passed">passed</option>
            <option value="failed">failed</option>
            <option value="error">error</option>
          </select>
        </label>

        <label>
          来源
          <select
            value={filters.source}
            onChange={(event) => setFilters((prev) => ({ ...prev, source: event.target.value.trim().toLowerCase() }))}
          >
            <option value="">全部</option>
            <option value="manual">manual</option>
            <option value="case_center">case_center</option>
            <option value="case_detail">case_detail</option>
            <option value="rerun">rerun</option>
            <option value="healed-rerun">healed-rerun</option>
          </select>
        </label>

        <label className="grow">
          关键词
          <input
            value={filters.keyword}
            placeholder="task_id / case_id / run_id"
            onChange={(event) => setFilters((prev) => ({ ...prev, keyword: event.target.value }))}
          />
        </label>
      </FilterBar>

      <DataTable title={`命中任务：${total}`} loading={loading} loadingText="正在加载执行任务..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Run ID</th>
                <th>Case ID</th>
                <th>项目</th>
                <th>状态</th>
                <th>队列</th>
                <th>来源</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {visibleTasks.length ? (
                visibleTasks.map((task) => (
                  <tr key={String(task.task_id || task.run_id || Math.random())}>
                    <td className="mono">{task.task_id || "-"}</td>
                    <td className="mono">{task.run_id || "-"}</td>
                    <td className="mono">{task.case_id || "-"}</td>
                    <td>{task.project_code || "-"}</td>
                    <td>{task.status || "-"}</td>
                    <td>{task.queue_status || "-"}</td>
                    <td>{task.source || "-"}</td>
                    <td>{formatDateTime(task.updated_at || task.created_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>
                    <EmptyState title="没有执行任务" description="可以调整筛选条件，或先从执行计划/AI 生成链路发起一次执行。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
