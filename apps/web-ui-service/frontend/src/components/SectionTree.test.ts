/**
 * SectionTree reducer 单元测试。
 * 运行: cd apps/web-ui-service/frontend && npx tsx src/components/SectionTree.test.ts
 *
 * 测试 3 个核心场景：
 *   1. CHECK_ALL  → 全选所有节点
 *   2. UNCHECK_ALL → 取消所有选中
 *   3. TOGGLE 部分子节点 → 父节点半选，再全部选中 → 父节点全选
 */

import {
  type SectionNode,
  createInitialState,
  sectionTreeReducer,
} from './SectionTree';

// ---------------------------------------------------------------------------
// mini assert helper (no dependencies)
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string) {
  if (condition) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg}`);
  }
}

function assertEq<T>(actual: T, expected: T, msg: string) {
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg} — expected ${expected}, got ${actual}`);
  }
}

// ---------------------------------------------------------------------------
// test data — 模拟登录模块文档的章节树
// ---------------------------------------------------------------------------
function makeTestTree(): SectionNode[] {
  return [
    {
      id: 'sec-1',
      title: '登录模块',
      level: 2,
      charCount: 500,
      children: [
        {
          id: 'sec-1-1',
          title: '账号密码登录',
          level: 3,
          charCount: 200,
          children: [],
        },
        {
          id: 'sec-1-2',
          title: '验证码登录',
          level: 3,
          charCount: 150,
          children: [],
        },
        {
          id: 'sec-1-3',
          title: '第三方登录',
          level: 3,
          charCount: 150,
          children: [],
        },
      ],
    },
    {
      id: 'sec-2',
      title: '用户管理',
      level: 2,
      charCount: 800,
      children: [
        {
          id: 'sec-2-1',
          title: '用户列表',
          level: 3,
          charCount: 400,
          children: [],
        },
        {
          id: 'sec-2-2',
          title: '权限管理',
          level: 3,
          charCount: 400,
          children: [],
        },
      ],
    },
  ];
}

const allNodeIds = ['sec-1', 'sec-1-1', 'sec-1-2', 'sec-1-3', 'sec-2', 'sec-2-1', 'sec-2-2'];
const parentIds = ['sec-1', 'sec-2']; // 有子节点的父节点

// ---------------------------------------------------------------------------
// Setup: INIT 后全选（默认行为）
// ---------------------------------------------------------------------------
function initState() {
  return sectionTreeReducer(createInitialState(), {
    type: 'INIT',
    nodes: makeTestTree(),
  });
}

// ---------------------------------------------------------------------------
// Test 1: 全选（INIT 默认就是全选,CHECK_ALL 从部分选到全选）
// ---------------------------------------------------------------------------
function testCheckAll() {
  console.log('\n=== Test 1: CHECK_ALL（从部分选中恢复到全选）===');

  // 先部分取消选中
  let state = initState();
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1-1' });
  assert(state.checkedIds.size < allNodeIds.length, 'TOGGLE 后 checked < total');

  // 再全选
  state = sectionTreeReducer(state, { type: 'CHECK_ALL' });

  assertEq(state.checkedIds.size, allNodeIds.length, 'CHECK_ALL 后全选所有 7 个节点');
  assertEq(state.indeterminateIds.size, 0, 'CHECK_ALL 后半选集合为空');
  for (const id of allNodeIds) {
    assert(state.checkedIds.has(id), `  ${id} 在 checkedIds 中`);
  }
  for (const pid of parentIds) {
    assert(!state.indeterminateIds.has(pid), `  父节点 ${pid} 不在 indeterminateIds 中`);
  }
}

// ---------------------------------------------------------------------------
// Test 2: 取消全选
// ---------------------------------------------------------------------------
function testUncheckAll() {
  console.log('\n=== Test 2: UNCHECK_ALL ===');

  let state = initState();
  assertEq(state.checkedIds.size, allNodeIds.length, 'INIT 后默认全选');

  state = sectionTreeReducer(state, { type: 'UNCHECK_ALL' });

  assertEq(state.checkedIds.size, 0, 'UNCHECK_ALL 后 checkedIds 为空');
  assertEq(state.indeterminateIds.size, 0, 'UNCHECK_ALL 后 indeterminateIds 为空');
}

// ---------------------------------------------------------------------------
// Test 3: 部分子节点勾选 → 父节点半选 → 再补选 → 父节点全选
// ---------------------------------------------------------------------------
function testPartialCheckGoesIndeterminateThenFull() {
  console.log('\n=== Test 3: 部分勾选 → 父节点半选 → 全勾选 → 父节点全选 ===');

  // 3a: 先全不选
  let state = initState();
  state = sectionTreeReducer(state, { type: 'UNCHECK_ALL' });
  assertEq(state.checkedIds.size, 0, '初始全不选');

  // 3b: 只勾选 sec-1-1（登录模块的一个子节点）
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1-1' });
  assert(state.checkedIds.has('sec-1-1'), 'sec-1-1 被选中');
  assert(!state.checkedIds.has('sec-1-2'), 'sec-1-2 未被选中');
  assert(!state.checkedIds.has('sec-1-3'), 'sec-1-3 未被选中');
  assert(!state.checkedIds.has('sec-1'), '父节点 sec-1 不在 checkedIds 中（只有部分子节点选中）');
  assert(
    state.indeterminateIds.has('sec-1'),
    '父节点 sec-1 在 indeterminateIds 中（部分子节点选中）',
  );
  assert(
    !state.indeterminateIds.has('sec-2'),
    'sec-2 不在 indeterminateIds 中（所有子节点未选中）',
  );

  // 3c: 再勾选 sec-1-2 和 sec-1-3 → sec-1 的所有子节点全部选中
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1-2' });
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1-3' });
  assert(state.checkedIds.has('sec-1-1'), 'sec-1-1 仍选中');
  assert(state.checkedIds.has('sec-1-2'), 'sec-1-2 选中');
  assert(state.checkedIds.has('sec-1-3'), 'sec-1-3 选中');
  assert(
    state.checkedIds.has('sec-1'),
    '父节点 sec-1 现在在 checkedIds 中（所有子节点选中）',
  );
  assert(
    !state.indeterminateIds.has('sec-1'),
    '父节点 sec-1 退出 indeterminateIds（不再是部分选中）',
  );
  assert(
    !state.checkedIds.has('sec-2'),
    'sec-2 未被选中（它的子节点都没选）',
  );

  // 3d: 确认根节点没有 indeterminateId（不是树根，没有更高父节点）
  assertEq(state.checkedIds.size, 4, 'checkedIds 共 4 个（sec-1 + 3 个子节点）');
}

// ---------------------------------------------------------------------------
// Bonus: TOGGLE 父节点 → 级联全选/取消子节点
// ---------------------------------------------------------------------------
function testToggleParentCascades() {
  console.log('\n=== Bonus: TOGGLE 父节点 → 级联全选/取消子节点 ===');

  let state = initState();
  state = sectionTreeReducer(state, { type: 'UNCHECK_ALL' });
  assertEq(state.checkedIds.size, 0, '初始全不选');

  // TOGGLE sec-1 → 应级联选中 sec-1, sec-1-1, sec-1-2, sec-1-3
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1' });
  assert(state.checkedIds.has('sec-1'), 'sec-1 选中');
  assert(state.checkedIds.has('sec-1-1'), 'sec-1-1 级联选中');
  assert(state.checkedIds.has('sec-1-2'), 'sec-1-2 级联选中');
  assert(state.checkedIds.has('sec-1-3'), 'sec-1-3 级联选中');
  assertEq(state.checkedIds.size, 4, 'checkedIds 共 4 个');
  assertEq(state.indeterminateIds.size, 0, '无半选');

  // TOGGLE sec-1 再次 → 应级联取消 sec-1 + 所有子节点
  state = sectionTreeReducer(state, { type: 'TOGGLE', nodeId: 'sec-1' });
  assert(!state.checkedIds.has('sec-1'), 'sec-1 取消选中');
  assert(!state.checkedIds.has('sec-1-1'), 'sec-1-1 级联取消');
  assertEq(state.checkedIds.size, 0, '所有节点取消选中');
}

// ---------------------------------------------------------------------------
// run
// ---------------------------------------------------------------------------
testCheckAll();
testUncheckAll();
testPartialCheckGoesIndeterminateThenFull();
testToggleParentCascades();

console.log(`\n========================================`);
console.log(`  ${passed} passed, ${failed} failed`);
console.log(`========================================`);

// 返回 exit code
if (failed > 0) {
  process.exitCode = 1;
}
