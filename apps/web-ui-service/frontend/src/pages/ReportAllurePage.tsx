import { useEffect, useState } from "react";

import { getReportAllure, type ReportAllureResponse } from "../api/report";
import { ReportTabs } from "./ReportTabs";

function asText(value: unknown): string {
  const text = String(value || "").trim();
  return text || "-";
}

export function ReportAllurePage() {
  const [payload, setPayload] = useState<ReportAllureResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const response = await getReportAllure();
        if (!cancelled) {
          setPayload(response || {});
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "Allure 信息加载失败");
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

  const allureIndex = String(payload.allure_index || "/allure/index.html").trim() || "/allure/index.html";

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>Allure 报告（React + TypeScript）</h1>
          <p className="muted">统一入口到 Allure 报告快照。</p>
        </div>
      </header>
      <ReportTabs />

      {loading ? <section className="panel">正在加载 Allure 信息...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {!loading && !errorText ? (
        <section className="panel info-grid">
          <article className="info-card">
            <h2>状态</h2>
            <p>
              <strong>available:</strong> {payload.available ? "true" : "false"}
            </p>
            <p>
              <strong>version:</strong> {asText(payload.version)}
            </p>
            <p>
              <strong>index:</strong> <span className="mono">{allureIndex}</span>
            </p>
            <p>
              <a className="button" href={allureIndex} target="_blank" rel="noreferrer">
                打开 Allure 报告
              </a>
            </p>
          </article>
          <article className="info-card">
            <h2>摘要</h2>
            <pre className="json-block">{JSON.stringify(payload.summary || {}, null, 2)}</pre>
          </article>
        </section>
      ) : null}
    </main>
  );
}
