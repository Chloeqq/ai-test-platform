import { useEffect, useState } from "react";

import { getReportAllure, refreshReportAllure, type AllureEnvironmentItem, type AllureExecutorItem, type ReportAllureResponse } from "../api/report";
import { ReportTabs } from "./ReportTabs";

function asText(value: unknown): string {
  const text = String(value || "").trim();
  return text || "-";
}

function environmentValue(items: AllureEnvironmentItem[] | undefined, name: string): string {
  const target = String(name || "").trim().toLowerCase();
  const item = (items || []).find((row) => String(row.name || "").trim().toLowerCase() === target);
  return (item?.values || []).map((value) => String(value || "").trim()).filter(Boolean).join("、") || "-";
}

function executorValue(item: AllureExecutorItem | undefined, key: keyof AllureExecutorItem): string {
  return asText(item?.[key]);
}

export function ReportAllurePage() {
  const [payload, setPayload] = useState<ReportAllureResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
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
  const reportName = asText(payload.report_name || payload.summary?.reportName || "AI 自动化测试执行报告");
  const displayVersion = asText(payload.display_version || payload.version);
  const environment = Array.isArray(payload.environment) ? payload.environment : [];
  const executors = Array.isArray(payload.executors) ? payload.executors : [];
  const executor = executors[0];
  const statistic = (payload.summary?.statistic || {}) as Record<string, unknown>;
  const total = Number(statistic.total || 0);
  const passed = Number(statistic.passed || 0);
  const failed = Number(statistic.failed || 0) + Number(statistic.broken || 0);
  const passRate = total > 0 ? `${Math.round((passed / total) * 1000) / 10}%` : "-";
  const isAvailable = Boolean(payload.available);
  const pendingMessage = asText(payload.message || (!isAvailable ? "暂无本次执行报告，请先在用例中心执行用例。" : ""));

  async function refreshAllure() {
    if (refreshing) {
      return;
    }
    setRefreshing(true);
    setErrorText("");
    try {
      const response = await refreshReportAllure();
      setPayload(response || {});
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "Allure 报告刷新失败");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>Allure 报告</h1>
          <p className="muted">统一入口到企业级执行报告快照，展示环境、执行器和可追溯版本。</p>
        </div>
        <button type="button" className="button secondary" disabled={loading || refreshing} onClick={() => void refreshAllure()}>
          {refreshing ? "正在刷新..." : "刷新报告"}
        </button>
      </header>
      <ReportTabs />

      {loading ? <section className="panel">正在加载 Allure 信息...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}
      {!loading && !errorText && !isAvailable ? (
        <section className="panel warning">
          <h2>暂无本次 Allure 执行报告</h2>
          <p>{pendingMessage}</p>
          {payload.legacy_available ? (
            <p className="muted">检测到历史全局 Allure 报告，但为避免混入旧执行结果，当前页面不会继续展示该旧报告。</p>
          ) : null}
          <p className="muted">请先到用例中心点击“执行用例”，执行完成后再返回本页或点击“刷新报告”。</p>
        </section>
      ) : null}
      {!loading && !errorText ? (
        <section className="panel info-grid">
          <article className="info-card">
            <h2>{reportName}</h2>
            <p>
              <strong>报告状态：</strong> {isAvailable ? "可用" : "等待执行"}
            </p>
            <p>
              <strong>报告版本：</strong> {displayVersion}
            </p>
            <p>
              <strong>缓存版本：</strong> <span className="mono">{asText(payload.cache_version)}</span>
            </p>
            <p>
              <strong>报告地址：</strong> <span className="mono">{allureIndex}</span>
            </p>
            <p>
              <strong>执行摘要：</strong> 共 {total || 0} 条，通过 {passed || 0} 条，失败 {failed || 0} 条，通过率 {passRate}
            </p>
            <p>
              {isAvailable ? (
                <a className="button" href={allureIndex} target="_blank" rel="noreferrer">
                  打开 Allure 报告
                </a>
              ) : (
                <span className="button disabled" aria-disabled="true">等待执行后生成</span>
              )}
            </p>
          </article>
          <article className="info-card">
            <h2>环境信息</h2>
            <p><strong>项目：</strong>{environmentValue(environment, "Project")}</p>
            <p><strong>环境：</strong>{environmentValue(environment, "Environment")}</p>
            <p><strong>测试地址：</strong><span className="mono">{environmentValue(environment, "Base_URL")}</span></p>
            <p><strong>浏览器：</strong>{environmentValue(environment, "Browser")}</p>
            <p><strong>页面：</strong>{environmentValue(environment, "Page")}</p>
          </article>
          <article className="info-card">
            <h2>执行器</h2>
            <p><strong>名称：</strong>{executorValue(executor, "name")}</p>
            <p><strong>类型：</strong>{executorValue(executor, "type")}</p>
            <p><strong>构建：</strong><span className="mono">{executorValue(executor, "buildName")}</span></p>
            <p><strong>报告：</strong>{executorValue(executor, "reportName")}</p>
          </article>
          <article className="info-card">
            <h2>调试信息</h2>
            <details>
              <summary>展开 Allure 原始摘要</summary>
              <pre className="json-block">{JSON.stringify(payload.summary || {}, null, 2)}</pre>
            </details>
          </article>
        </section>
      ) : null}
    </main>
  );
}
