import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getDashboardGovernance, type DashboardGovernanceResponse } from "../api/governance";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";

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

export function QualityFlakyPage() {
  const [payload, setPayload] = useState<DashboardGovernanceResponse>({});
  const [keyword, setKeyword] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const data = await getDashboardGovernance();
        if (!cancelled) {
          setPayload(data || {});
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "Flaky 分析加载失败");
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

  const items = Array.isArray(payload.flaky_analysis?.items) ? payload.flaky_analysis?.items : [];
  const normalizedKeyword = keyword.trim().toLowerCase();
  const filtered = items.filter((item) => {
    if (!normalizedKeyword) {
      return true;
    }
    const haystack = [
      text(item.case_id),
      text(item.name),
      text(item.module),
      text(item.page),
      text(item.reason),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalizedKeyword);
  });

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>Flaky 分析</h1>
          <p className="muted">识别不稳定任务和风险重叠，优先处理高波动项。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/quality/failure-clusters">
            失败聚类
          </Link>
          <Link className="button" to="/execution/runs">
            执行任务
          </Link>
        </div>
      </header>

      <FilterBar>
        <label className="grow">
          关键词
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="case_id / 名称 / 模块 / 原因" />
        </label>
      </FilterBar>

      <DataTable title={`命中 ${filtered.length} 项`} loading={loading} loadingText="正在加载 flaky 分析..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>名称</th>
                <th>模块</th>
                <th>Flaky Rate</th>
                <th>稳定分</th>
                <th>风险重叠</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length ? (
                filtered.map((item, index) => (
                  <tr key={String(item.case_id || index)}>
                    <td className="mono">{text(item.case_id)}</td>
                    <td>{text(item.name)}</td>
                    <td>{text(item.module)}</td>
                    <td>{numberValue(item.flaky_rate)}%</td>
                    <td>{numberValue(item.stability_score)}</td>
                    <td>{numberValue(item.matched_risk_task_count)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="没有 Flaky 数据" description="当前筛选条件下没有波动用例，可以调整关键词或查看失败聚类。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
