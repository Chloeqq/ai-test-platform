import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getFailureClusters, type FailureClustersResponse } from "../api/governance";
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

export function QualityClustersPage() {
  const [payload, setPayload] = useState<FailureClustersResponse>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setLoading(true);
      setErrorText("");
      try {
        const data = await getFailureClusters({ limit: 200, max_clusters: 20 });
        if (!cancelled) {
          setPayload(data || {});
          if (data?.error) {
            setErrorText(String(data.error));
          }
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "失败聚类加载失败");
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

  const clusters = Array.isArray(payload.clusters) ? payload.clusters : [];

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>失败聚类</h1>
          <p className="muted">按故障模式聚合失败，提升排障效率。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/quality/gates">
            质量门禁
          </Link>
          <Link className="button" to="/defects">
            缺陷管理
          </Link>
        </div>
      </header>

      <section className="panel stat-grid">
        <article className="stat-card">
          <span className="label">失败总数</span>
          <strong>{numberValue(payload.total_failed_reports)}</strong>
        </article>
        <article className="stat-card">
          <span className="label">聚类数</span>
          <strong>{numberValue(payload.total_clusters)}</strong>
        </article>
      </section>

      <DataTable loading={loading} loadingText="正在加载失败聚类..." errorText={errorText}>
          <table>
            <thead>
              <tr>
                <th>Cluster ID</th>
                <th>Failure Class</th>
                <th>Queue</th>
                <th>Severity</th>
                <th>出现次数</th>
                <th>人工复核</th>
                <th>最近时间</th>
              </tr>
            </thead>
            <tbody>
              {clusters.length ? (
                clusters.map((item, index) => (
                  <tr key={String(item.cluster_id || index)}>
                    <td className="mono">{text(item.cluster_id)}</td>
                    <td>{text(item.failure_class)}</td>
                    <td>{text(item.queue)}</td>
                    <td>{text(item.severity)}</td>
                    <td>{numberValue(item.occurrence_count)}</td>
                    <td>{numberValue(item.requires_manual_review_count)}</td>
                    <td>{formatDateTime(item.last_seen_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>
                    <EmptyState title="暂无聚类数据" description="当执行失败积累到一定数量后，系统会在这里沉淀失败聚类。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </DataTable>
    </main>
  );
}
