/** 章节选择树组件。useReducer 管理选中/半选/展开状态，性能通过 nodeMap + parentMap 索引保证。 */

import { useCallback, useEffect, useReducer, useState } from "react";
import {
  type ScopedContent,
  getRequirementDocumentScopedContent,
  getRequirementDocumentSections,
} from "../api/workbench";
import {
  type SectionNode,
  type SectionTreeAction,
  type SectionTreeState,
  adaptNodes,
  createInitialState,
  sectionTreeReducer,
} from "./SectionTree.reducer";

const DEBOUNCE_MS = 200;
const INDENT_PX = 20;

const SCOPE_ICONS: Record<string, string> = {
  block: "🚫",
  warn: "⚠️",
  ok: "⚡",
};
const SCOPE_LABELS: Record<string, string> = {
  block: "已超上限",
  warn: "内容较多",
  ok: "可正常生成",
};

// ---------------------------------------------------------------------------
// React component
// ---------------------------------------------------------------------------

interface SectionTreeProps {
  docId: number;
  onChange: (scope: ScopedContent) => void;
}

export function SectionTree({ docId, onChange }: SectionTreeProps) {
  const [state, dispatch] = useReducer(sectionTreeReducer, null, createInitialState);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState<ScopedContent | null>(null);
  const [scopeLoading, setScopeLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getRequirementDocumentSections(docId)
      .then((res) => {
        if (!cancelled) dispatch({ type: "INIT", nodes: adaptNodes(res.sections || []) });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  useEffect(() => {
    if (state.checkedIds.size === 0) {
      setScope(null);
      return;
    }
    const timer = setTimeout(() => {
      setScopeLoading(true);
      const ids = Array.from(state.checkedIds);
      getRequirementDocumentScopedContent(docId, ids)
        .then((res) => {
          setScope(res.item);
          onChange(res.item);
        })
        .catch(() => {})
        .finally(() => setScopeLoading(false));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [state.checkedIds, docId, onChange]);

  if (loading) return <p className="muted">加载章节中...</p>;
  if (!state.nodes || state.nodes.length === 0) return null;

  const checkedCount = state.checkedIds.size;
  const allCount = state.nodeMap.size;

  return (
    <div className="aiw-section-tree">
      <div className="aiw-section-tree-toolbar">
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "CHECK_ALL" })}>全选</button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "UNCHECK_ALL" })}>全不选</button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "EXPAND_ALL" })}>展开</button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "COLLAPSE_ALL" })}>折叠</button>
      </div>

      {state.nodes.map((node) => (
        <SectionNodeItem key={node.id} node={node} state={state} dispatch={dispatch} depth={0} />
      ))}

      <div className="aiw-section-scope">
        <span className="muted">已选 {checkedCount}/{allCount} 节</span>
        {scopeLoading ? (
          <span className="muted"> · 计算中...</span>
        ) : scope ? (
          <span className={`muted aiw-scope-${scope.level}`}>
            {" · "}约 {scope.char_count} 字 · 预估 ~{scope.estimated_tokens} tokens
            {" · "}{SCOPE_ICONS[scope.level] || ""} {SCOPE_LABELS[scope.level] || scope.level}
          </span>
        ) : checkedCount === 0 ? (
          <span className="muted"> · 未选择章节</span>
        ) : null}
      </div>
    </div>
  );
}

function SectionNodeItem({
  node,
  state,
  dispatch,
  depth,
}: {
  node: SectionNode;
  state: SectionTreeState;
  dispatch: React.Dispatch<SectionTreeAction>;
  depth: number;
}) {
  const checked = state.checkedIds.has(node.id);
  const indeterminate = state.indeterminateIds.has(node.id);
  const expanded = state.expandedIds.has(node.id);
  const hasChildren = node.children.length > 0;

  return (
    <div className="aiw-section-node" style={{ paddingLeft: depth * INDENT_PX }}>
      {hasChildren ? (
        <button type="button" className="aiw-section-expand" onClick={() => dispatch({ type: "TOGGLE_EXPAND", nodeId: node.id })}>
          {expanded ? "▼" : "▶"}
        </button>
      ) : (
        <span className="aiw-section-expand aiw-section-expand-spacer" />
      )}
      <label className="aiw-section-label">
        <input
          type="checkbox"
          checked={checked}
          ref={(el) => { if (el) el.indeterminate = indeterminate; }}
          onChange={() => dispatch({ type: "TOGGLE", nodeId: node.id })}
        />
        <span className={checked || indeterminate ? "aiw-section-title-selected" : ""}>{node.title}</span>
        <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>({node.char_count}字)</span>
      </label>
      {expanded && hasChildren && (
        <div className="aiw-section-children">
          {node.children.map((child) => (
            <SectionNodeItem key={child.id} node={child} state={state} dispatch={dispatch} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
