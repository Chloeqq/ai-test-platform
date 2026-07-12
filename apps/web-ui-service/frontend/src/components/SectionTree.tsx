/** 章节选择树组件。用 useReducer 管理选中/半选/展开状态，性能通过 nodeMap + parentMap 索引保证。 */

export type SectionNode = {
  id: string;
  title: string;
  level: number;
  charCount: number;
  children: SectionNode[];
};

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
