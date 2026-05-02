import { startTransition, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getExecutionReportDetail, type ExecutionReportItem } from "../api/report";
import { DataTable } from "../components/DataTable";
import { ReportTabs } from "./ReportTabs";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

export function ExecutionResultDetailPage() {
  const { executionId = "" } = useParams();
  const [detail, setDetail] = useState<ExecutionReportItem>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const payload = await getExecutionReportDetail(executionId);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setDetail((payload.item || {}) as ExecutionReportItem);
        });
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "执行报告加载失败");
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
  }, [executionId]);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>执行报告 #{text(detail.execution_id || executionId)}</h1>
          <p className="muted">执行留痕详情页已切换到 React 主链。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/execution/results">
            返回执行结果
          </Link>
        </div>
      </header>
      <ReportTabs />

      {loading ? <section className="panel">正在加载执行报告...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}

      {!loading && !errorText ? (
        <>
          <DataTable title="执行摘要">
            <table>
              <tbody>
                <tr>
                  <th>执行ID</th>
                  <td className="mono">#{text(detail.execution_id)}</td>
                </tr>
                <tr>
                  <th>关联用例</th>
                  <td>{text(detail.case_name)}</td>
                </tr>
                <tr>
                  <th>执行结果</th>
                  <td>{text(detail.status)}</td>
                </tr>
                <tr>
                  <th>执行耗时</th>
                  <td>{text(detail.duration_ms)} ms</td>
                </tr>
                <tr>
                  <th>执行时间</th>
                  <td>{formatDateTime(detail.executed_at)}</td>
                </tr>
              </tbody>
            </table>
          </DataTable>

          <section className="panel">
            <h2>留痕信息</h2>
            <ul>
              <li>本页展示执行元数据，作为执行报告稳定入口。</li>
              <li>后续可扩展截图、日志、网络请求和失败分析摘要。</li>
              <li>历史链接统一收敛到 React 路由，避免旧模板分叉。</li>
            </ul>
          </section>
        </>
      ) : null}
    </main>
  );
}
