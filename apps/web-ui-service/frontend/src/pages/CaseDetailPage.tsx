import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { formatDateTime } from "../lib/datetime";

import { getWorkbenchCase } from "../api/assets";
import { DEFAULT_PROJECT_CODE } from "../config/projects";

function text(value: unknown): string {
  const normalized = String(value || "").trim();
  return normalized || "-";
}

export function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = String(params.caseId || "").trim();
  const [item, setItem] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!caseId) {
        setErrorText("缺少 case_id");
        setLoading(false);
        return;
      }
      setLoading(true);
      setErrorText("");
      try {
        const payload = await getWorkbenchCase(caseId, DEFAULT_PROJECT_CODE);
        if (!cancelled) {
          setItem((payload.item || {}) as Record<string, unknown>);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "用例详情加载失败");
          setItem({});
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
  }, [caseId]);

  return (
    <main className="page shell">
      <header className="header panel">
        <div>
          <h1>用例详情</h1>
          <p className="muted">查看 YAML 与核心元信息。</p>
        </div>
        <div className="header-actions">
          <Link className="button secondary" to="/cases">
            返回用例列表
          </Link>
        </div>
      </header>

      <section className="panel">
        {loading ? <p>正在加载用例详情...</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
        {!loading && !errorText ? (
          <>
            <p>
              <strong>Case ID:</strong> <span className="mono">{text(item.case_id)}</span>
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
              <strong>更新时间:</strong> {formatDateTime(item.updated_at)}
            </p>
            <p>
              <strong>路径:</strong> <span className="mono">{text(item.path)}</span>
            </p>
          </>
        ) : null}
      </section>

      {!loading && !errorText ? (
        <section className="panel">
          <h2>YAML</h2>
          <pre className="json-block">{String(item.yaml_content || "").trim() || "-"}</pre>
        </section>
      ) : null}
    </main>
  );
}
