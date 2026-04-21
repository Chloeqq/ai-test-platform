import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getTestPointAsset, getTestPointAssetCoverageMatrix } from "../api/assets";

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

export function TestPointAssetDetailPage() {
  const params = useParams<{ assetId: string }>();
  const location = useLocation();
  const assetId = String(params.assetId || "").trim();
  const showMatrixOnly = useMemo(() => location.pathname.endsWith("/matrix"), [location.pathname]);
  const [item, setItem] = useState<Record<string, unknown>>({});
  const [matrix, setMatrix] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!assetId) {
        setErrorText("缺少 asset_id");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorText("");
      try {
        const [detailPayload, matrixPayload] = await Promise.all([
          getTestPointAsset(assetId, "default"),
          getTestPointAssetCoverageMatrix(assetId, "default"),
        ]);
        if (!cancelled) {
          setItem((detailPayload.item || {}) as Record<string, unknown>);
          setMatrix((matrixPayload.item || {}) as Record<string, unknown>);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "测试点资产详情加载失败");
          setItem({});
          setMatrix({});
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
  }, [assetId]);

  const rows = Array.isArray(matrix.rows) ? matrix.rows : [];
  const summary = (matrix.summary || {}) as Record<string, unknown>;

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>测试点资产详情（React + TypeScript）</h1>
          <p className="muted">查看资产摘要与覆盖矩阵。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/assets/test-points">
            返回资产列表
          </Link>
        </div>
      </header>

      {loading ? <section className="panel">正在加载资产详情...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}

      {!loading && !errorText && !showMatrixOnly ? (
        <section className="panel">
          <p>
            <strong>Asset ID:</strong> <span className="mono">{text(item.asset_id)}</span>
          </p>
          <p>
            <strong>标题:</strong> {text(item.title)}
          </p>
          <p>
            <strong>页面:</strong> {text(item.page)}
          </p>
          <p>
            <strong>优先级:</strong> {text(item.priority)}
          </p>
          <p>
            <strong>来源:</strong> {text(item.source_type)}
          </p>
          <p>
            <strong>点位数:</strong> {numberValue(item.point_count)}
          </p>
          <p>
            <strong>置信度:</strong> {numberValue(item.confidence)}
          </p>
          <p>
            <strong>状态:</strong> {text((item.selection_summary as Record<string, unknown> | undefined)?.selection_state)}
          </p>
          <p>
            <Link to={`/assets/test-points/${encodeURIComponent(assetId)}/matrix`}>查看覆盖矩阵</Link>
          </p>
        </section>
      ) : null}

      {!loading && !errorText ? (
        <section className="panel table-panel">
          <div className="table-head">
            <strong>覆盖矩阵</strong>
            <span className="muted">
              status={text(summary.status)} ｜ covered={numberValue(summary.covered_count)} ｜ partial={numberValue(summary.partial_count)} ｜ gap=
              {numberValue(summary.gap_count)} ｜ orphan={numberValue(summary.orphan_count)}
            </span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Row ID</th>
                <th>追溯状态</th>
                <th>source_ids</th>
                <th>intent_ids</th>
                <th>point_keys</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((row, index) => (
                  <tr key={String(row.row_id || index)}>
                    <td className="mono">{text(row.row_id)}</td>
                    <td>{text(row.traceability_status)}</td>
                    <td className="mono">{text((Array.isArray(row.source_ids) ? row.source_ids : []).join(", "))}</td>
                    <td className="mono">{text((Array.isArray(row.intent_ids) ? row.intent_ids : []).join(", "))}</td>
                    <td className="mono">{text((Array.isArray(row.point_keys) ? row.point_keys : []).join(", "))}</td>
                    <td>{text(row.explanation)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>暂无覆盖矩阵数据。</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
