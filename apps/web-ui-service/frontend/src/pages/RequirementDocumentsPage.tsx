/** 需求文档管理页面：列表 + 筛选 + 搜索 + 内联展开详情 */

import { useEffect, useMemo, useState } from "react";

import {
  type RequirementDocumentDetail,
  type RequirementDocumentItem,
  getRequirementDocument,
  listRequirementDocuments,
  listProjects,
  type ProjectItem,
} from "../api/workbench";
import { DEFAULT_PROJECT_CODE } from "../config/projects";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(iso: string | undefined): string {
  if (!iso) return "-";
  return iso.replace("T", " ").slice(0, 19);
}

const STATUS_LABELS: Record<string, { text: string; cls: string }> = {
  parsed: { text: "已解析", cls: "aiw-tag-green" },
  pending: { text: "待处理", cls: "aiw-tag-gray" },
  partial: { text: "部分成功", cls: "aiw-tag-yellow" },
  failed: { text: "失败", cls: "aiw-tag-red" },
};

// ---------------------------------------------------------------------------
// page
// ---------------------------------------------------------------------------
export function RequirementDocumentsPage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectCode, setProjectCode] = useState(DEFAULT_PROJECT_CODE);
  const [statusFilter, setStatusFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState<RequirementDocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RequirementDocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // load projects
  useEffect(() => {
    let cancelled = false;
    listProjects().then((p) => {
      if (!cancelled) {
        const src = Array.isArray(p.items) ? p.items : [];
        setProjects(src);
        if (src.length > 0) {
          setProjectCode(
            String(src[0].project_code || DEFAULT_PROJECT_CODE).trim(),
          );
        }
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // load list
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listRequirementDocuments(projectCode, statusFilter !== "all" ? statusFilter : undefined)
      .then((res) => {
        if (!cancelled) setItems(res.items || []);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    setExpandedId(null);
    setDetail(null);
    return () => {
      cancelled = true;
    };
  }, [projectCode, statusFilter]);

  // load detail when expand
  function toggleExpand(docId: number) {
    if (expandedId === docId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(docId);
    setDetailLoading(true);
    getRequirementDocument(docId)
      .then((res) => setDetail(res.item))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  // client-side search
  const filtered = useMemo(() => {
    if (!keyword.trim()) return items;
    const kw = keyword.trim().toLowerCase();
    return items.filter((item) => (item.filename || "").toLowerCase().includes(kw));
  }, [items, keyword]);

  const statusOptions = ["all", "parsed", "partial", "failed", "pending"];

  return (
    <section className="panel aiw-panel">
      <header className="aiw-panel-header">
        <h2>需求文档管理</h2>
        <p className="muted">管理已上传的需求文档，可查看详情、下载或重新解析。</p>
      </header>

      {/* filters */}
      <div className="aiw-toolbar" style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
        <select value={projectCode} onChange={(e) => setProjectCode(e.target.value)}>
          {projects.map((p) => (
            <option key={String(p.project_code)} value={String(p.project_code)}>
              {String(p.project_code)}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {statusOptions.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "全部状态" : STATUS_LABELS[s]?.text || s}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="搜索文件名..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ minWidth: 200 }}
        />
      </div>

      {/* empty */}
      {!loading && filtered.length === 0 && (
        <div className="aiw-empty">
          <p className="muted">暂无上传的需求文档</p>
          <p className="muted">在 AI 生成页面步骤 1 上传文档后，可在此管理和复用。</p>
        </div>
      )}

      {/* loading */}
      {loading && <p className="muted">加载中...</p>}

      {/* table */}
      {filtered.length > 0 && (
        <table className="aiw-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>大小</th>
              <th>状态</th>
              <th>上传时间</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => {
              const st = STATUS_LABELS[doc.parse_status] || {
                text: doc.parse_status,
                cls: "",
              };
              return (
                <tr
                  key={doc.id}
                  className={expandedId === doc.id ? "aiw-row-selected" : ""}
                  style={{ cursor: "pointer" }}
                  onClick={() => toggleExpand(doc.id)}
                >
                  <td>{doc.filename}</td>
                  <td>{doc.source_type}</td>
                  <td>{formatSize(doc.file_size)}</td>
                  <td>
                    <span className={`aiw-tag ${st.cls}`}>{st.text}</span>
                    {doc.parse_status === "failed" && doc.parse_error ? (
                      <span className="muted" title={doc.parse_error} style={{ marginLeft: 6, fontSize: 12 }}>
                        ⓘ
                      </span>
                    ) : null}
                  </td>
                  <td>{formatTime(doc.created_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {/* detail panel */}
      {expandedId !== null && (
        <div className="aiw-detail-panel">
          {detailLoading ? (
            <p className="muted">加载详情中...</p>
          ) : detail ? (
            <>
              <h4>📄 {detail.filename}</h4>
              <div className="aiw-detail-grid">
                <div><strong>类型:</strong> {detail.source_type}</div>
                <div><strong>大小:</strong> {formatSize(detail.file_size)}</div>
                <div>
                  <strong>状态:</strong>{" "}
                  <span className={`aiw-tag ${STATUS_LABELS[detail.parse_status]?.cls || ""}`}>
                    {STATUS_LABELS[detail.parse_status]?.text || detail.parse_status}
                  </span>
                </div>
                <div><strong>上传时间:</strong> {formatTime(detail.created_at)}</div>
                <div><strong>上传者:</strong> {detail.created_by || "-"}</div>
              </div>
              {detail.parse_error && (
                <p className="error">解析错误: {detail.parse_error}</p>
              )}
              {detail.parsed_preview && (
                <div className="aiw-detail-preview">
                  <strong>文本预览(前 500 字):</strong>
                  <pre>{detail.parsed_preview}</pre>
                </div>
              )}
              <div className="aiw-detail-actions" style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <button className="button" onClick={() => window.open(`/api/workbench/requirement-documents/${detail.id}/download`, "_blank")}>
                  下载原始文件
                </button>
              </div>
            </>
          ) : (
            <p className="error">加载详情失败</p>
          )}
        </div>
      )}
    </section>
  );
}
