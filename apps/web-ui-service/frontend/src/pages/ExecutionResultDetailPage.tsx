import { startTransition, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getExecutionReportDetail, type ExecutionReportItem } from "../api/report";
import { DataTable } from "../components/DataTable";
import { authFetch } from "../lib/http";
import { buildRuntimeDesktopUrl } from "../lib/runtimeDesktop";
import { ReportTabs } from "./ReportTabs";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

export function ExecutionResultDetailPage() {
  const { executionId = "" } = useParams();
  const location = useLocation();
  const runId = new URLSearchParams(location.search).get("run_id") || "";
  const [detail, setDetail] = useState<ExecutionReportItem>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");
  const [videoUrl, setVideoUrl] = useState<string>("");
  const runtimeDesktopUrl = buildRuntimeDesktopUrl();

  async function openRunArtifact(kind: "log" | "video") {
    if (!runId) {
      return;
    }
    try {
      const endpoint =
        kind === "video"
          ? `/api/workbench/runs/${encodeURIComponent(runId)}/video`
          : `/api/workbench/download-log/${encodeURIComponent(runId)}`;
      const response = await authFetch(endpoint);
      if (!response.ok) {
        throw new Error(kind === "video" ? "执行录屏暂不可用" : "执行日志暂不可用");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      if (kind === "video") {
        setVideoUrl(url);
        return;
      }
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${runId}.log`;
      anchor.click();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 30_000);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "执行留痕暂不可用");
    }
  }

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

  useEffect(() => {
    return () => {
      if (videoUrl) {
        window.URL.revokeObjectURL(videoUrl);
      }
    };
  }, [videoUrl]);

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
                  <th>运行ID</th>
                  <td className="mono">{text(runId)}</td>
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
            <div className="execution-visibility-hint">
              <span>执行过程会在容器桌面中可视化运行；错过实时过程时，可在本页回放录屏。</span>
              <a href={runtimeDesktopUrl} target="_blank" rel="noreferrer">
                打开实时桌面
              </a>
            </div>
            <ul>
              <li>本页展示执行元数据，作为执行报告稳定入口。</li>
              {runId ? (
                <li>
                  执行录屏：
                  <button type="button" className="link-button" onClick={() => void openRunArtifact("video")}>
                    加载录屏预览
                  </button>
                  {videoUrl ? (
                    <a className="subtle-link" href={videoUrl} target="_blank" rel="noreferrer">
                      新窗口打开
                    </a>
                  ) : null}
                </li>
              ) : null}
              {runId ? (
                <li>
                  运行日志：
                  <button type="button" className="link-button" onClick={() => void openRunArtifact("log")}>
                    下载执行日志
                  </button>
                </li>
              ) : null}
              {runId ? <li>执行记录：<Link to={`/execution/runs?keyword=${encodeURIComponent(runId)}`}>查看运行记录</Link></li> : null}
              <li>Allure 报告：<Link to="/execution/results/allure">查看最新 Allure 报告</Link></li>
              <li>后续可扩展截图、日志、网络请求和失败分析摘要。</li>
              <li>历史链接统一收敛到 React 路由，避免旧模板分叉。</li>
            </ul>
            {videoUrl ? (
              <video className="execution-video-preview" src={videoUrl} controls preload="metadata">
                当前浏览器不支持播放执行录屏。
              </video>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}
