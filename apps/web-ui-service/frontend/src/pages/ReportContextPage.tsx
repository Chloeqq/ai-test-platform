import { useEffect, useState } from "react";

import { getReportContext, type ReportContextResponse } from "../api/report";
import { ReportTabs } from "./ReportTabs";

function readText(value: string | undefined): string {
  const text = String(value || "").trim();
  return text || "-";
}

export function ReportContextPage() {
  const [payload, setPayload] = useState<ReportContextResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const response = await getReportContext();
        if (!cancelled) {
          setPayload(response || {});
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "上下文信息加载失败");
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

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>资产与集成（React + TypeScript）</h1>
          <p className="muted">展示当前执行环境、构建与代码版本信息。</p>
        </div>
      </header>
      <ReportTabs />

      {loading ? <section className="panel">正在加载上下文信息...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {!loading && !errorText ? (
        <section className="panel info-grid">
          <article className="info-card">
            <h2>Git 信息</h2>
            <p>
              <strong>Commit:</strong> <span className="mono">{readText(payload.git?.commit_id)}</span>
            </p>
            <p>
              <strong>Branch:</strong> <span className="mono">{readText(payload.git?.branch)}</span>
            </p>
            <p>
              <strong>Message:</strong> {readText(payload.git?.commit_message)}
            </p>
          </article>

          <article className="info-card">
            <h2>构建信息</h2>
            <p>
              <strong>Build Version:</strong> <span className="mono">{readText(payload.build?.build_version)}</span>
            </p>
            <p>
              <strong>Image Tag:</strong> <span className="mono">{readText(payload.build?.image_tag)}</span>
            </p>
            <p>
              <strong>Build Time:</strong> {readText(payload.build?.build_time)}
            </p>
          </article>

          <article className="info-card">
            <h2>执行环境</h2>
            <p>
              <strong>BASE_URL:</strong> <span className="mono">{readText(payload.execution?.base_url)}</span>
            </p>
            <p>
              <strong>Browser:</strong> {readText(payload.execution?.browser)}
            </p>
            <p>
              <strong>Environment:</strong> {readText(payload.execution?.environment)}
            </p>
            <p>
              <strong>Runner:</strong> {readText(payload.execution?.runner)}
            </p>
            <p>
              <strong>Latest Run:</strong> <span className="mono">{readText(payload.execution?.latest_run_id)}</span>
            </p>
          </article>
        </section>
      ) : null}
    </main>
  );
}
