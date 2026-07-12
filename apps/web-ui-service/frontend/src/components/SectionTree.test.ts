/**
 * SectionTree reducer 单元测试 (vitest)。
 * 运行: cd apps/web-ui-service/frontend && npx vitest run src/components/SectionTree.test.ts
 */

import { describe, expect, it } from "vitest";
import {
  type SectionNode,
  createInitialState,
  sectionTreeReducer,
} from "./SectionTree.reducer";

// ---------------------------------------------------------------------------
// test data — 模拟登录模块文档的章节树
// ---------------------------------------------------------------------------
function makeTestTree(): SectionNode[] {
  return [
    {
      id: "sec-1", title: "登录模块", level: 2, char_count: 500, block_ids: [],
      children: [
        { id: "sec-1-1", title: "账号密码登录", level: 3, char_count: 200, block_ids: [], children: [] },
        { id: "sec-1-2", title: "验证码登录", level: 3, char_count: 150, block_ids: [], children: [] },
        { id: "sec-1-3", title: "第三方登录", level: 3, char_count: 150, block_ids: [], children: [] },
      ],
    },
    {
      id: "sec-2", title: "用户管理", level: 2, char_count: 800, block_ids: [],
      children: [
        { id: "sec-2-1", title: "用户列表", level: 3, char_count: 400, block_ids: [], children: [] },
        { id: "sec-2-2", title: "权限管理", level: 3, char_count: 400, block_ids: [], children: [] },
      ],
    },
  ];
}

const allIds = ["sec-1", "sec-1-1", "sec-1-2", "sec-1-3", "sec-2", "sec-2-1", "sec-2-2"];
const parentIds = ["sec-1", "sec-2"];

function initState() {
  return sectionTreeReducer(createInitialState(), { type: "INIT", nodes: makeTestTree() });
}

// ---------------------------------------------------------------------------
describe("SectionTree reducer", () => {
  it("CHECK_ALL: 全选所有节点", () => {
    let state = initState();
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1-1" });
    expect(state.checkedIds.size).toBeLessThan(allIds.length);

    state = sectionTreeReducer(state, { type: "CHECK_ALL" });
    expect(state.checkedIds.size).toBe(allIds.length);
    expect(state.indeterminateIds.size).toBe(0);
    for (const id of allIds) expect(state.checkedIds.has(id)).toBe(true);
  });

  it("UNCHECK_ALL: 取消所有选中", () => {
    let state = initState();
    expect(state.checkedIds.size).toBe(allIds.length);

    state = sectionTreeReducer(state, { type: "UNCHECK_ALL" });
    expect(state.checkedIds.size).toBe(0);
    expect(state.indeterminateIds.size).toBe(0);
  });

  it("TOGGLE 部分子节点 → 父节点半选 → 全勾选 → 父节点全选", () => {
    let state = initState();
    state = sectionTreeReducer(state, { type: "UNCHECK_ALL" });
    expect(state.checkedIds.size).toBe(0);

    // 只勾选 sec-1-1
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1-1" });
    expect(state.checkedIds.has("sec-1-1")).toBe(true);
    expect(state.checkedIds.has("sec-1-2")).toBe(false);
    expect(state.checkedIds.has("sec-1")).toBe(false);
    expect(state.indeterminateIds.has("sec-1")).toBe(true);

    // 再勾选全部子节点
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1-2" });
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1-3" });
    expect(state.checkedIds.has("sec-1")).toBe(true);
    expect(state.indeterminateIds.has("sec-1")).toBe(false);
    expect(state.checkedIds.size).toBe(4);
  });

  it("TOGGLE 父节点 → 级联全选/取消子节点", () => {
    let state = initState();
    state = sectionTreeReducer(state, { type: "UNCHECK_ALL" });
    expect(state.checkedIds.size).toBe(0);

    // 选中 sec-1
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1" });
    expect(state.checkedIds.has("sec-1")).toBe(true);
    expect(state.checkedIds.has("sec-1-1")).toBe(true);
    expect(state.checkedIds.has("sec-1-2")).toBe(true);
    expect(state.checkedIds.has("sec-1-3")).toBe(true);
    expect(state.checkedIds.size).toBe(4);

    // 取消 sec-1
    state = sectionTreeReducer(state, { type: "TOGGLE", nodeId: "sec-1" });
    expect(state.checkedIds.has("sec-1")).toBe(false);
    expect(state.checkedIds.has("sec-1-1")).toBe(false);
    expect(state.checkedIds.size).toBe(0);
  });

  it("EXPAND_ALL / COLLAPSE_ALL", () => {
    let state = initState();
    expect(state.expandedIds.size).toBe(allIds.length);

    state = sectionTreeReducer(state, { type: "COLLAPSE_ALL" });
    expect(state.expandedIds.size).toBe(0);

    state = sectionTreeReducer(state, { type: "EXPAND_ALL" });
    expect(state.expandedIds.size).toBe(allIds.length);
  });

  it("TOGGLE_EXPAND toggle single node", () => {
    let state = initState();
    state = sectionTreeReducer(state, { type: "COLLAPSE_ALL" });

    state = sectionTreeReducer(state, { type: "TOGGLE_EXPAND", nodeId: "sec-1" });
    expect(state.expandedIds.has("sec-1")).toBe(true);
    expect(state.expandedIds.has("sec-2")).toBe(false);

    state = sectionTreeReducer(state, { type: "TOGGLE_EXPAND", nodeId: "sec-1" });
    expect(state.expandedIds.has("sec-1")).toBe(false);
  });
});
