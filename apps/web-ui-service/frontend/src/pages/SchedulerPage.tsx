import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getSchedulerDispatchPlan, getSchedulerSummary, type SchedulerDispatchPlanResponse, type SchedulerSummaryResponse } from "../api/governance";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";

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

export function SchedulerPage() {
  const [summaryPayload, setSummaryPayload] = useState<SchedulerSummaryResponse>({});
  const [planPayload, setPlanPayload] = useState<SchedulerDispatchPlanResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const [summaryData, planData] = await Promise.all([getSchedulerSummary(100), getSchedulerDispatchPlan(200)]);
        if (!cancelled) {
          setSummaryPayload(summaryData || {});
          setPlanPayload(planData || {});
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "调度中心加载失败");
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

  const summary = (summaryPayload.item || {}) as Record<string, unknown>;
  const queueRows = Array.isArray(summary.queue_distribution) ? summary.queue_distribution : [];
  const recommendations = Array.isArray(summary.recommendations) ? summary.recommendations : [];
  const dispatch = (planPayload.item || {}) as Record<string, unknown>;
  const lanes = Array.isArray(dispatch.dispatch_lanes) ? dispatch.dispatch_lanes : [];

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>调度中心</h1>
          <p className="muted">观察队列压力、资源画像与分发建议。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/execution/runs">
            执行任务
          </Link>
          <Link className="button" to="/execution/plans">
            测试计划
          </Link>
        </div>
      </header>

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">总任务</span>
          <strong>{numberValue(summary.total_tasks)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">活跃任务</span>
          <strong>{numberValue(summary.active_task_count)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">排队任务</span>
          <strong>{numberValue(summary.queued_task_count)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">运行中任务</span>
          <strong>{numberValue(summary.running_task_count)}</strong>
        </article>
      </section>

      <DataTable title="队列分布" loading={loading} loadingText="正在加载调度数据..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Queue</th>
                <th>Queued</th>
                <th>Running</th>
                <th>Pressure</th>
                <th>资源画像</th>
                <th>环境池</th>
              </tr>
            </thead>
            <tbody>
              {queueRows.length ? (
                queueRows.map((item, index) => (
                  <tr key={String(item.queue || index)}>
                    <td>{text(item.queue)}</td>
                    <td>{numberValue(item.queued)}</td>
                    <td>{numberValue(item.running)}</td>
                    <td>{text(item.pressure)}</td>
                    <td>{text(Object.keys((item.resource_profiles as Record<string, unknown>) || {}).join(" / "))}</td>
                    <td>{text(Object.keys((item.environment_pools as Record<string, unknown>) || {}).join(" / "))}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="暂无队列数据" description="调度服务同步执行队列后，会在这里展示队列压力和资源画像。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>

      <section className="panel">
        <h2>调度建议</h2>
        {recommendations.length ? (
          <ul className="simple-list">
            {recommendations.map((item, index) => (
              <li key={String(item.title || index)} className="simple-list-item">
                <div>
                  <strong>{text(item.title)}</strong>
                  <p className="muted">{text(item.summary)}</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂无调度建议。</p>
        )}
      </section>

      <section className="panel">
        <h2>Dispatch Lanes</h2>
        {lanes.length ? (
          <ul className="simple-list">
            {lanes.map((lane, index) => (
              <li key={String(lane.queue || index)} className="simple-list-item">
                <div>
                  <strong>
                    {text(lane.queue)} / {text(lane.runner)}
                  </strong>
                  <p className="muted">
                    resource={text(lane.resource_profile)} ｜ pool={text(lane.environment_pool)} ｜ tasks=
                    {numberValue(lane.task_count)} ｜ concurrency={numberValue(lane.recommended_concurrency)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂无 dispatch lane。</p>
        )}
      </section>
    </main>
  );
}
