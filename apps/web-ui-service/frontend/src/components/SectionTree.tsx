/** 章节选择树组件。用 useReducer 管理选中/半选/展开状态，性能通过 nodeMap + parentMap 索引保证。 */

import { useCallback, useEffect, useReducer, useState } from "react";
import {
  type SectionNode as ApiSectionNode,
  type ScopedContent,
  getRequirementDocumentScopedContent,
  getRequirementDocumentSections,
} from "../api/workbench";

export type SectionNode = {
  id: string;
  title: string;
  level: number;
  char_count: number;
  block_ids: string[];
  children: SectionNode[];
};

/** 将 API 响应转为 reducer 使用的 SectionNode（递归）。 */
function adaptNodes(apiNodes: ApiSectionNode[]): SectionNode[] {
  return apiNodes.map((n) => ({
    id: n.id,
    title: n.title,
    level: n.level,
    char_count: n.char_count,
    block_ids: n.block_ids || [],
    children: n.children ? adaptNodes(n.children) : [],
  }));
}

export type SectionTreeState = {
  nodes: SectionNode[];
  nodeMap: Map<string, SectionNode>;
  parentMap: Map<string, string | null>;
  checkedIds: Set<string>;
  indeterminateIds: Set<string>;
  expandedIds: Set<string>;
};

export type SectionTreeAction =
  | { type: 'INIT'; nodes: SectionNode[] }
  | { type: 'TOGGLE'; nodeId: string }
  | { type: 'CHECK_ALL' }
  | { type: 'UNCHECK_ALL' }
  | { type: 'EXPAND_ALL' }
  | { type: 'COLLAPSE_ALL' }
  | { type: 'TOGGLE_EXPAND'; nodeId: string };

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function buildIndexes(
  nodes: SectionNode[],
): { nodeMap: Map<string, SectionNode>; parentMap: Map<string, string | null> } {
  const nodeMap = new Map<string, SectionNode>();
  const parentMap = new Map<string, string | null>();

  function walk(list: SectionNode[], parentId: string | null) {
    for (const node of list) {
      nodeMap.set(node.id, node);
      parentMap.set(node.id, parentId);
      if (node.children.length > 0) {
        walk(node.children, node.id);
      }
    }
  }

  walk(nodes, null);
  return { nodeMap, parentMap };
}

/** 收集 nodeId 及其所有子孙的 ID（用 nodeMap 迭代,不递归 DFS） */
function getAllDescendantIds(
  nodeId: string,
  nodeMap: Map<string, SectionNode>,
): string[] {
  const result: string[] = [nodeId];
  const stack = [nodeId];
  while (stack.length > 0) {
    const current = stack.pop()!;
    const node = nodeMap.get(current);
    if (node) {
      for (const child of node.children) {
        result.push(child.id);
        stack.push(child.id);
      }
    }
  }
  return result;
}

/** 根据 checkedIds + indeterminateIds 重新计算 nodeId 所有祖先的半选/全选状态 */
function recomputeAncestors(
  nodeId: string,
  parentMap: Map<string, string | null>,
  nodeMap: Map<string, SectionNode>,
  checkedIds: Set<string>,
  indeterminateIds: Set<string>,
): { checkedIds: Set<string>; indeterminateIds: Set<string> } {
  const newChecked = new Set(checkedIds);
  const newIndeterminate = new Set(indeterminateIds);

  let current = parentMap.get(nodeId);
  while (current) {
    const parentNode = nodeMap.get(current);
    if (parentNode && parentNode.children.length > 0) {
      const allChildrenChecked = parentNode.children.every((c) =>
        newChecked.has(c.id),
      );
      const someChildCheckedOrIndeterminate = parentNode.children.some(
        (c) =>
          newChecked.has(c.id) || newIndeterminate.has(c.id),
      );

      if (allChildrenChecked) {
        newChecked.add(current);
        newIndeterminate.delete(current);
      } else if (someChildCheckedOrIndeterminate) {
        newChecked.delete(current);
        newIndeterminate.add(current);
      } else {
        newChecked.delete(current);
        newIndeterminate.delete(current);
      }
    }
    current = parentMap.get(current);
  }

  return { checkedIds: newChecked, indeterminateIds: newIndeterminate };
}

// ---------------------------------------------------------------------------
// reducer
// ---------------------------------------------------------------------------

export function sectionTreeReducer(
  state: SectionTreeState,
  action: SectionTreeAction,
): SectionTreeState {
  switch (action.type) {
    case 'INIT': {
      const { nodeMap, parentMap } = buildIndexes(action.nodes);
      const allIds = Array.from(nodeMap.keys());
      return {
        nodes: action.nodes,
        nodeMap,
        parentMap,
        checkedIds: new Set(allIds),         // 默认全选
        indeterminateIds: new Set(),
        expandedIds: new Set(allIds),         // 默认全展开
      };
    }

    case 'TOGGLE': {
      const node = state.nodeMap.get(action.nodeId);
      if (!node) return state;

      const isCurrentlyChecked = state.checkedIds.has(action.nodeId);
      const descendantIds = getAllDescendantIds(action.nodeId, state.nodeMap);
      const newChecked = new Set(state.checkedIds);
      const newIndeterminate = new Set(state.indeterminateIds);

      if (isCurrentlyChecked) {
        // 取消选中: 移除节点及所有子孙
        for (const id of descendantIds) {
          newChecked.delete(id);
          newIndeterminate.delete(id);
        }
      } else {
        // 选中: 添加节点及所有子孙
        for (const id of descendantIds) {
          newChecked.add(id);
          newIndeterminate.delete(id);
        }
      }

      // 向上冒泡重算祖先
      const { checkedIds, indeterminateIds } = recomputeAncestors(
        action.nodeId,
        state.parentMap,
        state.nodeMap,
        newChecked,
        newIndeterminate,
      );

      return { ...state, checkedIds, indeterminateIds };
    }

    case 'CHECK_ALL': {
      const allIds = Array.from(state.nodeMap.keys());
      return {
        ...state,
        checkedIds: new Set(allIds),
        indeterminateIds: new Set(),
      };
    }

    case 'UNCHECK_ALL': {
      return {
        ...state,
        checkedIds: new Set(),
        indeterminateIds: new Set(),
      };
    }

    case 'EXPAND_ALL': {
      const allIds = Array.from(state.nodeMap.keys());
      return { ...state, expandedIds: new Set(allIds) };
    }

    case 'COLLAPSE_ALL': {
      return { ...state, expandedIds: new Set() };
    }

    case 'TOGGLE_EXPAND': {
      const newExpanded = new Set(state.expandedIds);
      if (newExpanded.has(action.nodeId)) {
        newExpanded.delete(action.nodeId);
      } else {
        newExpanded.add(action.nodeId);
      }
      return { ...state, expandedIds: newExpanded };
    }

    default:
      return state;
  }
}

export function createInitialState(): SectionTreeState {
  return {
    nodes: [],
    nodeMap: new Map(),
    parentMap: new Map(),
    checkedIds: new Set(),
    indeterminateIds: new Set(),
    expandedIds: new Set(),
  };
}

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

  // load sections on docId change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getRequirementDocumentSections(docId)
      .then((res) => {
        if (!cancelled) {
          dispatch({ type: "INIT", nodes: adaptNodes(res.sections || []) });
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  // debounced fetch scoped content on selection change
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
    }, 200);
    return () => clearTimeout(timer);
  }, [state.checkedIds, docId, onChange]);

  if (loading) return <p className="muted">加载章节中...</p>;
  if (!state.nodes || state.nodes.length === 0) return null;

  const checkedCount = state.checkedIds.size;
  const allCount = state.nodeMap.size;

  return (
    <div className="aiw-section-tree">
      <div className="aiw-section-tree-toolbar">
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "CHECK_ALL" })}>
          全选
        </button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "UNCHECK_ALL" })}>
          全不选
        </button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "EXPAND_ALL" })}>
          展开
        </button>
        <button type="button" className="aiw-btn-sm" onClick={() => dispatch({ type: "COLLAPSE_ALL" })}>
          折叠
        </button>
      </div>

      {state.nodes.map((node) => (
        <SectionNodeItem
          key={node.id}
          node={node}
          state={state}
          dispatch={dispatch}
          depth={0}
        />
      ))}

      <div className="aiw-section-scope">
        <span className="muted">
          已选 {checkedCount}/{allCount} 节
        </span>
        {scopeLoading ? (
          <span className="muted"> · 计算中...</span>
        ) : scope ? (
          <span className={`muted aiw-scope-${scope.level}`}>
            {" · "}约 {scope.char_count} 字 · 预估 ~{scope.estimated_tokens} tokens
            {" · "}
            {scope.level === "block" ? "🚫 已超上限" : scope.level === "warn" ? "⚠️ 内容较多" : "⚡ 可正常生成"}
          </span>
        ) : checkedCount === 0 ? (
          <span className="muted"> · 未选择章节</span>
        ) : null}
      </div>
    </div>
  );
}

// recursive node renderer
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
    <div className="aiw-section-node" style={{ paddingLeft: depth * 20 }}>
      {hasChildren ? (
        <button
          type="button"
          className="aiw-section-expand"
          onClick={() => dispatch({ type: "TOGGLE_EXPAND", nodeId: node.id })}
        >
          {expanded ? "▼" : "▶"}
        </button>
      ) : (
        <span className="aiw-section-expand aiw-section-expand-spacer" />
      )}
      <label className="aiw-section-label">
        <input
          type="checkbox"
          checked={checked}
          ref={(el) => {
            if (el) el.indeterminate = indeterminate;
          }}
          onChange={() => dispatch({ type: "TOGGLE", nodeId: node.id })}
        />
        <span className={checked || indeterminate ? "aiw-section-title-selected" : ""}>
          {node.title}
        </span>
        <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>
          ({node.char_count}字)
        </span>
      </label>
      {expanded && hasChildren && (
        <div className="aiw-section-children">
          {node.children.map((child) => (
            <SectionNodeItem
              key={child.id}
              node={child}
              state={state}
              dispatch={dispatch}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
