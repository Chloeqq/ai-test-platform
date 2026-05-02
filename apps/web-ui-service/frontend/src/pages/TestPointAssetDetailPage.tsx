import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getTestPointAsset, getTestPointAssetCoverageMatrix } from "../api/assets";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { normalizeProjectCode } from "../config/projects";

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

function listText(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function stepTextList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows: string[] = [];
  value.forEach((raw) => {
    if (typeof raw === "string") {
      const text = raw.trim();
      if (text) {
        rows.push(text);
      }
      return;
    }
    if (raw && typeof raw === "object") {
      const row = raw as Record<string, unknown>;
      const text = String(row.raw_text || row.value || row.description || row.action || "").trim();
      if (text) {
        rows.push(text);
      }
    }
  });
  return rows;
}

function pointRows(item: Record<string, unknown>): Array<Record<string, unknown>> {
  const plan = (item.plan || {}) as Record<string, unknown>;
  const metadata = (plan.metadata || {}) as Record<string, unknown>;
  const candidates = Array.isArray(metadata.selected_candidates) ? metadata.selected_candidates : [];
  if (candidates.length) {
    return candidates.filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"));
  }
  const points = Array.isArray(plan.points) ? plan.points : [];
  return points
    .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
    .map((point) => {
      const snapshot = ((point.metadata as Record<string, unknown> | undefined)?.candidate_snapshot || {}) as Record<string, unknown>;
      return {
        intent_id: String(snapshot.intent_id || point.intent_id || point.key || "").trim(),
        title: String(snapshot.title || snapshot.summary || point.description || point.intent_id || "").trim(),
        summary: String(snapshot.summary || point.description || "").trim(),
        intent_type: String(snapshot.intent_type || point.point_type || "functional").trim(),
        priority: String(snapshot.priority || point.priority || "P1").trim(),
        precondition: String(snapshot.precondition || point.precondition || "").trim(),
        steps: Array.isArray(snapshot.steps) && snapshot.steps.length ? snapshot.steps : stepTextList(point.steps),
        expected: String(snapshot.expected || point.expected_result || "").trim(),
        involved_elements: Array.isArray(snapshot.involved_elements) && snapshot.involved_elements.length
          ? snapshot.involved_elements
          : listText(point.involved_elements),
      };
    });
}

export function TestPointAssetDetailPage() {
  const params = useParams<{ assetId: string }>();
  const location = useLocation();
  const assetId = String(params.assetId || "").trim();
  const project = useMemo(() => {
    const query = new URLSearchParams(location.search);
    return normalizeProjectCode(query.get("project"));
  }, [location.search]);
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
          getTestPointAsset(assetId, project),
          getTestPointAssetCoverageMatrix(assetId, project),
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
  }, [assetId, project]);

  const rows = Array.isArray(matrix.rows) ? matrix.rows : [];
  const summary = (matrix.summary || {}) as Record<string, unknown>;
  const detailRows = pointRows(item);
  const requirementText = listText(item.requirement).join("\n");

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>测试点资产详情</h1>
          <p className="muted">查看资产摘要与覆盖矩阵。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to={`/assets/test-points?project=${encodeURIComponent(project)}`}>
            返回资产列表
          </Link>
        </div>
      </header>

      {loading ? <section className="panel">正在加载资产详情...</section> : null}
      {errorText ? <section className="panel error">{errorText}</section> : null}

      {!loading && !errorText && !showMatrixOnly ? (
        <section className="panel">
          <p>
            <strong>资产编码:</strong> <span className="mono">{text(item.asset_id)}</span>
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
            <strong>需求:</strong>
          </p>
          <pre className="json-block">{requirementText || "-"}</pre>
          <p>
            <Link to={`/assets/test-points/${encodeURIComponent(assetId)}/matrix?project=${encodeURIComponent(project)}`}>查看覆盖矩阵</Link>
          </p>
        </section>
      ) : null}

      {!loading && !errorText && !showMatrixOnly ? (
        <DataTable title="测试点明细（与候选预览对齐）" actions={<span className="muted">共 {detailRows.length} 条</span>}>
          <table>
            <thead>
              <tr>
                <th>intent_id</th>
                <th>标题</th>
                <th>类型</th>
                <th>优先级</th>
                <th>前置条件</th>
                <th>步骤</th>
                <th>预期结果</th>
                <th>涉及元素</th>
              </tr>
            </thead>
            <tbody>
              {detailRows.length ? (
                detailRows.map((row, index) => {
                  const steps = stepTextList(row.steps);
                  const elements = listText(row.involved_elements);
                  return (
                    <tr key={`${String(row.intent_id || index)}-${index}`}>
                      <td className="mono">{text(row.intent_id)}</td>
                      <td>{text(row.title || row.summary)}</td>
                      <td>{text(row.intent_type)}</td>
                      <td>{text(row.priority)}</td>
                      <td>{text(row.precondition)}</td>
                      <td>{steps.length ? steps.join(" / ") : "-"}</td>
                      <td>{text(row.expected)}</td>
                      <td className="mono">{elements.length ? elements.join(", ") : "-"}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8}>
                    <EmptyState title="暂无测试点明细" description="当前资产还没有保存完整测试点明细，请回到测试点资产页检查生成结果。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTable>
      ) : null}

      {!loading && !errorText ? (
        <DataTable
          title="覆盖矩阵"
          actions={(
            <span className="muted">
              status={text(summary.status)} ｜ covered={numberValue(summary.covered_count)} ｜ partial={numberValue(summary.partial_count)} ｜ gap=
              {numberValue(summary.gap_count)} ｜ orphan={numberValue(summary.orphan_count)}
            </span>
          )}
        >
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
                  <td colSpan={6}>
                    <EmptyState title="暂无覆盖矩阵数据" description="生成或同步测试点资产后，覆盖矩阵会展示测试点与来源意图的追溯关系。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTable>
      ) : null}
    </main>
  );
}
