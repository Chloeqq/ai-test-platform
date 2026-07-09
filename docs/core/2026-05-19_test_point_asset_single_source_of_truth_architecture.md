# 2026-05-19 测试点资产唯一事实源架构方案

文档日期：2026-05-19

适用范围：测试点资产、测试点审核、用例生成、生成用例状态、YAML 用例、数据库用例、Runner 执行判定。

本文只定义架构方案、代码规范、影响范围、风险与验收标准，不代表已经修改业务代码或历史数据。

## 1. 背景与铁律

`mall-web-login-auth-fn-ai-0021` 的登录测试点曾由测试人员维护过账号密码，但后续查看时又恢复为旧值 `test001 / 123456`。同时，`mall-web-login-auth-fn-ai-0001` 作为“首次登录成功”用例，在缺少真实断言的情况下仍可能被判定成功。

这暴露出两个独立但相关的问题：

- 测试点资产数据存在多份可写副本，当前系统没有强制唯一事实源。
- 执行结果判定依赖动作是否报错，而不是依赖业务断言，导致“假通过”风险。

必须确立以下铁律：

- 测试点资产的当前业务内容只能有一个唯一事实源。
- 任何缓存、快照、生成产物、历史记录、YAML、数据库用例都不得反向覆盖唯一事实源。
- 被测系统地址是不可变业务事实，`http://localhost:5174/#/login` 不允许被 DSL、Docker、Runner、页面对象导入或生成链路改写。
- `expected_result` 只能作为业务预期描述和报告展示，不得单独作为执行通过依据。
- 登录成功、提交成功、跳转成功、保存成功等正向用例必须有真实可执行断言。

## 2. 当前事实源分叉

当前同一个测试意图的数据可能存在于以下位置：

| 数据位置 | 当前用途 | 是否可作为事实源 | 风险 |
|---|---|---:|---|
| `web-ui/state/test-points/{project}/{asset_id}.json` | 测试点资产根文件 | 是，但应只作为资产容器 | 与 `plans` 文件重复保存，可能不同步 |
| `web-ui/state/test-points/{project}/plans/{asset_id}.json` | 测试点计划文件 | 是，建议作为 v1 唯一事实源 | 需要防止根文件反向覆盖 |
| `plan.points[]` | 当前测试点业务内容 | 是，建议作为测试点唯一事实源 | 需要明确字段级权威 |
| `plan.points[].steps` | 当前可编辑步骤 | 是，建议作为步骤唯一事实源 | 如果编辑页只改其它字段，会丢失人工修改 |
| `plan.points[].expected_result` | 当前业务预期 | 是，建议作为预期唯一事实源 | 不能代替执行断言 |
| `plan.points[].metadata.candidate_snapshot` | 候选生成快照 | 否 | 旧账号密码可能从这里回流 |
| `plan.metadata.selected_candidates` | 批量候选缓存 | 否 | 旧候选可能在重新生成时覆盖当前步骤 |
| `web-ui/state/generated-cases/{project}` | 生成用例状态 | 否 | 只能是输出产物，不能回写测试点资产 |
| `assets/test-cases/ai-generated/*.yaml` | Runner 输入产物 | 否 | 只能由测试点事实源生成 |
| `test_cases.script_code/test_steps` | 用例中心执行输入 | 否 | 只能由 YAML 或生成链路写入，不应成为资产事实源 |
| Allure/执行报告 | 执行证据 | 否 | 只能记录结果，不能回写资产 |

## 3. 唯一事实源定义

### 3.1 v1 事实源

在当前文件存储架构不做大迁移的前提下，v1 唯一事实源定义为：

```text
web-ui/state/test-points/{project}/plans/{asset_id}.json
  -> points[]
    -> intent_id/key
    -> title/summary/intent_type/priority
    -> steps[]
    -> expected_result/expected
    -> involved_elements/involved_element_codes
    -> precondition
    -> review_status
```

根资产文件 `web-ui/state/test-points/{project}/{asset_id}.json` 只允许作为资产容器和索引副本，其内部 `plan` 必须由上述 plan 文件派生。若二者冲突，以 `plans/{asset_id}.json` 为准。

### 3.2 字段级权威

测试点当前业务内容的字段级权威如下：

| 业务含义 | 唯一事实字段 | 说明 |
|---|---|---|
| 测试意图 ID | `points[].intent_id` 或 `points[].key` | `intent_id` 优先，`key` 只兼容旧数据 |
| 测试点标题 | `points[].title` 或 `points[].description` | 展示和生成标题从这里读取 |
| 测试步骤 | `points[].steps` | 测试人员编辑后的步骤必须落在这里 |
| 结构化步骤提示 | 运行时从 `points[].steps` 派生 | 不再信任旧 `steps_hint` 作为当前值 |
| 预期结果 | `points[].expected_result` 或 `points[].expected` | 只描述业务预期，不等于断言 |
| 审核状态 | `points[].review_status` | 审核状态以点级字段为准 |
| 元素范围 | `points[].involved_elements` 和 `points[].involved_element_codes` | 生成时用于元素绑定 |

### 3.3 非事实字段

以下字段只能作为历史快照、审计或兼容缓存：

- `metadata.candidate_snapshot`
- `metadata.selected_candidates`
- `candidate_snapshot.steps_hint`
- `selected_candidates[].steps_hint`
- `generated-cases` 下的所有 JSON
- YAML 用例文件
- 数据库 `test_cases`
- 执行报告和 Allure 产物

这些字段不得直接覆盖 `points[].steps`、`points[].expected_result`、`points[].review_status`。

## 4. 为什么会出现数据源不统一

### 4.1 历史设计把候选、资产、生成产物混在了一条链路里

测试点资产从 AI 候选演进而来，系统为了保留候选上下文，把 `candidate_snapshot` 和 `selected_candidates` 一起保存到了资产内。这在“生成后只读”场景下问题不大，但一旦测试人员在页面上人工编辑步骤，这些候选快照就变成了旧副本。

### 4.2 保存链路没有统一派生策略

人工编辑测试点时，如果只更新了 `points[].steps`，但没有同步或废弃 `candidate_snapshot.steps_hint`，后续生成用例时就可能从旧快照读取旧账号密码。

### 4.3 生成链路为了兼容旧数据，会读取多个来源

当前代码中存在从 `selected_candidates`、`candidate_snapshot`、`steps_hint`、`points[].steps` 多处构造生成候选的逻辑。兼容旧数据本身合理，但缺少优先级约束和反向覆盖禁止规则，导致旧候选可能重新成为输入。

### 4.4 生成用例曾经覆盖过源测试点资产命名空间

此前已有问题记录：生成用例运行态快照曾写入 `web-ui/state/test-points/{project}`，导致源测试点资产被覆盖。虽然已经有状态隔离方向，但这说明边界曾被打穿，必须从架构上禁止输出产物回写输入资产。

### 4.5 执行判定与业务预期没有强绑定

`expected_result` 当前更多是报告文本。如果 Runner 没有执行 `assert_visible`、`assert_url`、`assert_text` 等动作，动作链执行完就可能被判定通过。这会让错误测试数据看起来“成功”。

## 5. 目标架构

### 5.1 数据流

```text
测试点资产唯一事实源
  plans/{asset_id}.json -> points[]
        |
        | 只读派生
        v
生成候选 Candidate DTO
        |
        | 编译
        v
执行 DSL / YAML
        |
        | 落库与执行
        v
test_cases + Runner + Allure
        |
        | 只写结果，不回写资产内容
        v
执行记录 / 报告 / 失败治理
```

### 5.2 写入边界

| 操作 | 允许写入 | 禁止写入 |
|---|---|---|
| 测试点编辑保存 | `plans/{asset_id}.json -> points[]` | `generated-cases`、YAML、DB 用例 |
| 测试点审核 | `points[].review_status` 和审计字段 | 改写步骤、账号密码、URL |
| 生成用例 | `generated-cases`、YAML、`test_cases` | 源测试点资产业务字段 |
| 执行用例 | 执行记录、报告、最后执行状态 | 测试点资产、页面对象 URL |
| 历史恢复 | 只能通过显式恢复入口 | 自动覆盖当前资产 |

### 5.3 派生字段策略

`candidate_snapshot` 和 `selected_candidates` 有两种可选治理方式：

方案 A：保留但只读。

- 保存资产时不依赖它们。
- 生成时优先从 `points[].steps` 重新构造 candidate。
- 快照仅用于展示“原始 AI 建议”。

方案 B：保存时同步重建。

- 每次编辑 `points[]` 后，自动由当前点重建 `candidate_snapshot` 和 `selected_candidates`。
- 快照仍不是事实源，只是与事实源一致的派生缓存。

推荐采用 A + 局部 B：

- 生成链路必须以 `points[].steps` 为准。
- 为兼容页面展示，可以在保存时同步刷新快照，但生成时不能信任快照优先级高于当前点。

## 6. 代码规范与实现原则

### 6.1 读模型规范

新增或收敛一个测试点资产读取 helper，例如：

```python
def load_test_point_asset_plan(project: str, asset_id: str) -> TestPointPlan:
    """Read the canonical test point plan.

    Canonical source:
    web-ui/state/test-points/{project}/plans/{asset_id}.json
    """
```

要求：

- 所有生成、审核、展示明细都通过该 helper 读取 canonical plan。
- 若根资产文件和 plan 文件同时存在且内容冲突，返回 plan 文件，并记录 warning。
- 不允许业务代码直接自行拼路径读取多个 JSON 后随意合并。

### 6.2 写模型规范

新增或收敛一个测试点资产写入 helper，例如：

```python
def save_test_point_asset_plan(project: str, asset_id: str, plan: dict, *, operator: str) -> None:
    """Persist the canonical plan and refresh derived asset container."""
```

要求：

- 先写 canonical plan，再刷新根资产容器中的派生 `plan`。
- 写入必须带 `updated_at`、`updated_by`、`version`。
- 写入时校验 `points[].intent_id` 唯一。
- 写入时不得从 `candidate_snapshot` 反向覆盖 `points[]`。

### 6.3 Candidate 构造规范

生成入口必须使用如下优先级：

```text
points[].steps
  > points[].steps_hint
  > metadata.candidate_snapshot.steps
  > metadata.candidate_snapshot.steps_hint
```

但实际目标是：常规路径只使用 `points[].steps`，后三者只作为旧数据兼容。若使用了后三者，必须在响应或日志中标记 `legacy_candidate_fallback=true`。

### 6.4 断言生成规范

正向业务用例必须从 `expected_result` 派生至少一个真实断言，或者由测试点显式提供断言步骤。

登录成功类推荐断言顺序：

1. 校验 URL 已离开 `http://localhost:5174/#/login`。
2. 校验 `home_menu` 或首页菜单可见。
3. 校验用户信息或权限菜单可见。

若无法生成断言，用例不得自动进入 `automated`，应标记为 `needs_assertion` 或生成失败，并在页面上展示原因。

### 6.5 URL 规范

页面对象和测试点资产不得改写被测 URL。

`http://localhost:5174/#/login` 是被测系统地址。Docker 网络访问映射只能存在于 Runner 运行时配置层，不能写回：

- 页面对象 `page_url`
- 测试点资产
- YAML DSL
- 数据库用例
- Allure 元数据中的业务 Base URL

## 7. 修复方案分阶段

### P0：确立事实源并阻断旧快照回流

目标：防止人工编辑后的数据再次被旧候选覆盖。

动作：

- 明确 `plans/{asset_id}.json -> points[]` 为 canonical source。
- 生成用例时由 `points[].steps` 构造 candidate。
- `candidate_snapshot` 和 `selected_candidates` 降级为历史快照。
- 若发现当前步骤和快照步骤不一致，以当前步骤为准，并记录 warning。
- 增加单测覆盖“当前步骤 admin/macro，不被旧 steps_hint test001/123456 覆盖”。

验收：

- 修改测试点资产账号密码后，重新审核、重新生成，不会恢复旧值。
- `mall-web-login-auth-fn-ai-0021 / intent-01` 的当前步骤是唯一输入。
- 生成用例 YAML、DB `script_code/test_steps` 与当前测试点步骤一致。

### P0：阻断假通过

目标：错误账号密码不能被判成登录成功。

动作：

- 登录成功类用例必须生成真实断言步骤。
- `expected_result` 继续保留为报告文本，但不参与通过判定。
- 对缺少断言的正向用例增加生成门禁或降级状态。

验收：

- `admin/macro` 如果不是有效密码，登录成功用例必须失败。
- 用例报告中能看到失败断言步骤，而不是只有输入和点击。
- Runner 结果由断言决定，不由文本预期决定。

### P1：统一保存链路

目标：页面编辑、批量审核、单点审核写入一致。

动作：

- 所有资产编辑入口统一调用 canonical save helper。
- 保存时同步刷新根资产容器。
- 保存时可重建派生快照，但派生快照不再作为生成优先输入。
- 审核接口只改审核字段，不改步骤和测试数据。

验收：

- 单点编辑、批量编辑、审核通过后，账号密码不变化。
- 根资产文件和 plan 文件内容一致，或根文件明确标记为派生副本。

### P1：历史数据治理

目标：清理或标记已经不一致的历史资产。

动作：

- 扫描 `points[].steps` 与 `candidate_snapshot.steps_hint` 不一致的资产。
- 输出差异报告，不自动覆盖。
- 对确认后的资产执行一次迁移：以 `points[].steps` 为准刷新派生快照。
- 对历史 YAML 和 DB 用例按来源资产和 intent 重新生成或标记过期。

验收：

- 差异资产列表可见。
- 迁移前有备份。
- 迁移后不会再从旧快照读出旧账号密码。

### P2：持久层演进

目标：从 JSON 多副本逐步演进到更清晰的数据库模型。

动作：

- 建议后续引入 `test_point_assets`、`test_point_intents`、`test_point_steps` 表。
- JSON 文件保留为导入导出和审计快照。
- 数据库成为长期 canonical source，文件成为派生物。

验收：

- API 读取不再需要多文件合并。
- 审核、编辑、生成具备事务一致性。
- 历史版本可追溯。

## 8. 当前问题的影响判断

### 8.1 直接影响

- `mall-web-login-auth-fn-ai-0021` 中至少 `intent-01` 存在旧账号密码回流风险。
- 所有从测试点资产生成的登录用例都可能受旧快照影响。
- 用例中心中已生成 YAML 和 DB 用例可能不是测试人员当前维护值。
- 只要正向用例缺少断言，就存在假通过风险。

### 8.2 潜在影响

- 其它页面或项目只要存在人工编辑测试点步骤，也可能被旧 `candidate_snapshot` 覆盖。
- 批量审核、批量生成更容易放大该问题。
- Allure 报告可能展示“预期结果正确”，但实际没有执行对应断言。

### 8.3 不应扩大处理的范围

本问题修复不应顺手修改：

- 被测系统 URL。
- 页面对象 URL。
- Docker 网络地址。
- 非相关页面对象导入规则。
- 未确认的历史用例编号。
- 用户未授权删除的历史报告。

## 9. 风险点

- 如果直接修改 YAML 或 DB，不修事实源，下一次生成仍会复发。
- 如果把 `candidate_snapshot` 直接删除，可能影响历史展示和审计。
- 如果断言生成过于激进，部分原本只适合人工执行的用例会被错误自动化。
- 如果运行时 Docker URL 写回资产，会再次破坏被测地址铁律。
- 如果没有差异报告就批量迁移，可能覆盖测试人员真实维护内容。

## 10. 验证方法

### 10.1 静态一致性检查

检查同一资产内以下字段是否一致：

- `points[].steps`
- `points[].metadata.candidate_snapshot.steps_hint`
- `plan.metadata.selected_candidates[].steps_hint`

如果不一致，必须报告差异，并以 `points[].steps` 为准。

### 10.2 生成一致性检查

对 `mall-web-login-auth-fn-ai-0021 / intent-01` 执行单意图生成：

- 生成输入必须来自 `points[].steps`。
- YAML 中账号密码必须与当前测试点一致。
- DB `test_cases.script_code` 和 `test_steps` 必须与 YAML 一致。

### 10.3 执行判定检查

使用错误密码执行登录成功用例：

- Runner 必须执行真实断言。
- 如果登录失败停留在登录页，结果必须为 failed。
- Allure 报告必须显示失败断言步骤和失败证据。

### 10.4 回归检查

- 批量审核不改变步骤。
- 批量生成不改写测试点资产。
- 生成失败只写失败记录，不覆盖源资产。
- 被测 URL 始终保持 `http://localhost:5174/#/login`。

## 11. 后续实施建议

建议按以下顺序实施：

1. 先增加只读差异扫描能力，列出所有资产的当前步骤和快照不一致项。
2. 再修改生成入口，让 candidate 只从 canonical `points[].steps` 派生。
3. 然后补充保存 helper，统一资产编辑和审核写入。
4. 最后补正向用例断言门禁，阻断假通过。

每一步都必须有单测，且每一步都不能修改被测系统地址。

## 12. 验收标准

- 文档和代码均明确 `plans/{asset_id}.json -> points[]` 是当前 v1 唯一事实源。
- 任何生成产物、缓存、快照、报告都不能反向覆盖测试点资产当前值。
- 人工修改账号密码后，审核、批量生成、重新生成不会恢复旧值。
- `candidate_snapshot` 与 `selected_candidates` 只能作为历史快照或派生缓存。
- 登录成功类用例缺少真实断言时不能被判为可信自动化成功。
- `admin/macro` 这类错误密码执行登录成功用例时，系统必须判失败。
- 被测地址始终保持 `http://localhost:5174/#/login`。

## 13. 2026-05-19 P0 执行记录

本轮已执行 P0 范围，目标是先阻断“旧快照回流”和“登录成功假通过”两类高风险问题。

已落地代码约束：

- `load_test_point_asset_with_root()` 读取测试点资产时，独立 plan 文件 `web-ui/state/test-points/{project}/plans/{asset_id}.json` 永远优先于根资产内嵌 `plan`。
- `_candidate_from_asset_point()` 构造生成候选时，优先读取 `points[].steps`、`points[].expected_result`、`points[].review_status` 等当前点位字段。
- `candidate_snapshot`、`selected_candidates`、旧 `steps_hint` 只作为兼容兜底，不能覆盖当前点位字段。
- 登录成功类用例在页面对象存在 `home_menu` 时自动追加 `assert_visible` 断言，避免只有输入和点击却被判成功。
- role 类型断言步骤显式保留 `role`，避免 Runner 解析 `assert_visible` 时缺少 role。

已补充验证：

- 当前步骤为 `admin/macro`、旧快照为 `test001/123456` 时，生成候选必须输出 `admin/macro`。
- 根资产内嵌旧 plan、独立 plan 文件为新值时，读取结果必须以独立 plan 文件为准。
- 登录成功 YAML 生成结果必须包含 `home_menu` 可见性断言。

本轮未执行事项：

- 未批量迁移历史测试点资产。
- 未物理删除历史 YAML、DB 用例或执行报告。
- 未修改被测系统地址。
- 未把 `mall-web-login-auth-fn-ai-0021` 的现有历史数据直接改成 `admin/macro`，该步骤应在差异扫描和用户确认后单独执行。

## 14. 2026-05-19 补充：测试点资产详情页字段缺失的事实源治理

### 14.1 问题现象

测试点资产详情页中，“前置条件”和“步骤”看起来为空或不完整。

本次只读排查确认：

- `precondition` 在当前 `mall-web-login-auth-fn-ai-0021` 的 `points[]`、`candidate_snapshot`、`selected_candidates` 中均为空，因此前置条件缺失属于源数据未保存。
- `steps` 在 `plan.points[].steps` 中存在。
- `plan.metadata.selected_candidates[]` 中没有 `steps`，只有 `steps_hint`。
- 前端 `TestPointAssetDetailPage.pointRows()` 当前优先读取 `plan.metadata.selected_candidates`，导致它绕过了真正有步骤的 `plan.points[]`。

这说明：生成链路 P0 已经向唯一事实源收敛，但详情页/编辑页仍存在旧读模型，继续把派生候选快照放在当前点位之前。

### 14.2 新增铁律：UI 读写也必须服从唯一事实源

唯一事实源不仅适用于生成链路，也适用于页面展示、筛选、审核、编辑、删除和批量操作。

前端和后端详情接口必须遵守：

```text
展示当前测试点 = plan.points[]
原始候选快照 = metadata.candidate_snapshot / metadata.selected_candidates
```

禁止：

- 禁止详情页优先展示 `selected_candidates`。
- 禁止编辑页把 `selected_candidates` 当成当前测试点列表。
- 禁止删除、审核、批量保存从 `selected_candidates` 反向生成当前 `points[]`。
- 禁止用旧 `steps_hint` 覆盖 `points[].steps`。

允许：

- `selected_candidates` 可以作为“原始 AI 候选快照”单独展示。
- `candidate_snapshot` 可以作为审计辅助信息。
- 当旧资产没有 `points[]` 时，可以短期从快照兜底，但必须标记 `legacy_fallback=true`。

### 14.3 详情页推荐数据模型

后端详情接口应输出一个规范化当前点位列表，避免前端重复推断事实源：

```json
{
  "item": {
    "asset_id": "mall-web-login-auth-fn-ai-0021",
    "plan": {},
    "point_rows": [
      {
        "intent_id": "intent-01",
        "title": "首次登录成功",
        "intent_type": "functional",
        "priority": "P1",
        "precondition": "",
        "steps": [
          "在账号输入框输入正确账号 test001",
          "在密码输入框输入正确密码 123456",
          "点击登录按钮"
        ],
        "expected_result": "页面跳转至平台工作台首页...",
        "review_status": "approved",
        "source_of_truth": "plan.points",
        "legacy_fallback": false
      }
    ],
    "candidate_snapshot_rows": []
  }
}
```

字段含义：

| 字段 | 来源 | 是否事实源 | 说明 |
|---|---|---:|---|
| `point_rows[]` | `plan.points[]` | 是 | 当前测试点详情页、编辑页、审核和生成入口都使用它 |
| `point_rows[].steps` | `points[].steps` | 是 | 展示和生成均使用当前步骤 |
| `point_rows[].precondition` | `points[].precondition` | 是 | 若为空，显示“未维护” |
| `candidate_snapshot_rows[]` | `candidate_snapshot / selected_candidates` | 否 | 只用于查看原始候选 |
| `source_of_truth` | 后端生成 | 否 | 给 UI 和验收明确来源 |
| `legacy_fallback` | 后端生成 | 否 | 旧资产兜底标记 |

### 14.4 前端治理规范

`TestPointAssetDetailPage` 应调整为：

- `pointRows(item)` 优先读取 `item.point_rows`。
- 若后端暂未返回 `point_rows`，前端退回读取 `item.plan.points[]`。
- 只有当 `plan.points[]` 为空时，才允许读取 `metadata.selected_candidates`。
- 页面上如果使用了快照兜底，必须显示“历史候选快照兜底”提示。
- 步骤列只展示 `points[].steps` 派生后的当前步骤，不展示旧 `steps_hint` 覆盖值。
- 前置条件为空时显示“未维护”，不要显示成加载失败或空白。

前端禁止继续使用以下优先级：

```text
selected_candidates > points[]
```

前端必须改为：

```text
item.point_rows > plan.points[] > selected_candidates(legacy fallback only)
```

### 14.5 保存/编辑治理规范

测试点资产详情页涉及这些写操作：

- 单条审核。
- 批量审核。
- 单条删除。
- 批量删除。
- 编辑后保存。
- 生成已通过用例。

这些写操作的目标必须是 `plan.points[]`。

保存请求中可以继续携带 `selected_candidates` 以兼容旧接口，但服务端必须把它转换成 `points[]` 后保存，并在保存后把 `selected_candidates` 当作派生快照重建或保留为历史。

更推荐的后续接口形态：

```json
{
  "asset_id": "mall-web-login-auth-fn-ai-0021",
  "project": "mall",
  "page": "login",
  "points": [
    {
      "intent_id": "intent-01",
      "title": "首次登录成功",
      "precondition": "用户未登录，处于登录页面",
      "steps": [
        "在账号输入框输入正确账号 admin",
        "在密码输入框输入正确密码 macro",
        "点击登录按钮"
      ],
      "expected_result": "登录失败，仍停留在登录页"
    }
  ]
}
```

### 14.6 前置条件缺失的修复策略

前置条件当前为空，不应由页面臆造。

推荐分三类处理：

- 如果用户人工维护过前置条件，保存时必须写入 `points[].precondition`。
- 如果 AI 候选或需求解析结果有前置条件，导入/保存时必须落入 `points[].precondition`。
- 如果确实没有前置条件，页面显示“未维护”，并允许测试人员编辑补充。

不要把以下内容自动当成前置条件：

- `expected_result`。
- `steps_hint`。
- 页面 URL。
- 用例标题。

### 14.7 代码规范要求

后端：

- 新增规范化 helper，例如 `build_test_point_asset_point_rows(asset)`。
- helper 必须从 `plan.points[]` 构造当前点位行。
- helper 内允许读取 `candidate_snapshot` 补充缺失标题或旧资产兼容字段，但不得覆盖 `points[].steps`、`points[].precondition`、`points[].expected_result`。
- helper 输出必须包含 `source_of_truth` 和 `legacy_fallback`。
- 所有详情页、编辑页、生成入口使用同一 helper 或同一字段优先级。

前端：

- `pointRows()` 不得优先读取 `metadata.selected_candidates`。
- `candidatePayloadFromRow()` 只能基于当前点位行构造保存 payload。
- 表格展示和批量操作必须以 `intent_id` 定位 `plan.points[]`。
- 对空前置条件使用 `未维护` 文案，避免误导为系统加载失败。

测试：

- 单测：`selected_candidates` 有 22 条但无 `steps`，`plan.points[]` 有 `steps` 时，详情页/后端行必须返回步骤。
- 单测：`candidate_snapshot.steps_hint` 是旧账号密码，`points[].steps` 是新账号密码时，详情页显示新账号密码。
- 单测：`points[].precondition` 为空时，API 返回空字符串，前端显示“未维护”。
- 单测：保存编辑后，`points[].precondition` 和 `points[].steps` 不被 `selected_candidates` 覆盖。

### 14.8 修复优先级

P0：

- 后端详情接口返回 `point_rows`，以 `plan.points[]` 为唯一事实源。
- 前端详情页优先读取 `point_rows` 或 `plan.points[]`，不再优先读取 `selected_candidates`。
- 前置条件为空显示“未维护”。

P1：

- 编辑/删除/审核操作全部改为基于 `points[]`。
- 保存接口将 `selected_candidates` 降级为派生快照。
- 增加差异扫描，列出 `points[]` 与 `selected_candidates` 不一致的资产。

P2：

- UI 增加“原始候选快照”折叠区，单独展示 `candidate_snapshot_rows`。
- 长期迁移到数据库表：`test_point_assets`、`test_point_intents`、`test_point_steps`。

### 14.9 验收标准

- `mall-web-login-auth-fn-ai-0021` 详情页能显示 `plan.points[].steps` 中的步骤。
- 当前 `precondition` 为空时，页面显示“未维护”。
- 存在 `metadata.selected_candidates` 时，详情页仍以 `plan.points[]` 为准。
- 任何旧 `selected_candidates[].steps_hint` 都不能覆盖当前步骤。
- 前端保存、删除、审核后，`plans/{asset_id}.json -> points[]` 仍是唯一事实源。
- 被测地址仍保持 `http://localhost:5174/#/login`，不得被 UI、保存或生成流程改写。

## 15. 2026-05-19 测试点资产详情页唯一事实源 Bug 修复实施指导

### 15.1 本次 Bug 根因

本次问题表现为：测试点资产详情页的“前置条件”和“步骤”看起来没有数据。

只读排查结论：

- 前置条件缺失：当前资产源数据中没有保存 `precondition`，包括 `points[]`、`candidate_snapshot`、`selected_candidates` 都为空。
- 步骤缺失：`plan.points[].steps` 实际存在，但前端详情页优先读取了 `plan.metadata.selected_candidates`。
- `selected_candidates` 只有 `steps_hint`，没有 `steps`，因此页面绕过了真正的当前步骤。

因此，这不是单纯展示问题，而是详情页仍在使用派生候选快照作为优先数据源，违背了唯一事实源铁律。

### 15.2 修复目标

修复后必须满足：

- 详情页、编辑页、审核、删除、生成入口都以 `plan.points[]` 为当前事实源。
- `metadata.selected_candidates` 和 `metadata.candidate_snapshot` 只作为历史候选快照或旧资产兜底。
- 旧 `steps_hint` 不能覆盖 `points[].steps`。
- 前置条件为空时显示“未维护”，不得臆造前置条件。
- 被测地址继续保持 `http://localhost:5174/#/login`，不得被任何 UI、保存或生成流程改写。

### 15.3 需要改动的文件

本轮实施应只聚焦以下文件：

- `apps/web-ui-service/app/api/workbench/facade.py`
- `apps/web-ui-service/frontend/src/pages/TestPointAssetDetailPage.tsx`
- `apps/web-ui-service/tests/test_test_point_asset_candidate_sync.py`

如前端构建产物纳入仓库，还需要在完成代码修复后执行前端构建并检查静态产物；否则不手工修改 `app/static/react`。

### 15.4 后端修复指导

在 `apps/web-ui-service/app/api/workbench/facade.py` 中新增规范化 helper：

```python
def build_test_point_asset_point_rows(asset: dict[str, Any]) -> list[dict[str, Any]]:
    plan = asset.get("plan") if isinstance(asset.get("plan"), dict) else {}
    points = plan.get("points") if isinstance(plan.get("points"), list) else []
    if points:
        return [_point_row_from_plan_point(point) for point in points if isinstance(point, dict)]

    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    candidates = metadata.get("selected_candidates") if isinstance(metadata.get("selected_candidates"), list) else []
    return [_point_row_from_legacy_candidate(candidate) for candidate in candidates if isinstance(candidate, dict)]
```

实现要求：

- `_point_row_from_plan_point()` 从 `point` 读取当前字段。
- `steps` 必须来自 `point.steps`，并统一转换为字符串数组。
- `precondition` 必须来自 `point.precondition`，为空则返回空字符串。
- `expected_result` 必须优先来自 `point.expected_result` 或 `point.expected`。
- `review_status` 必须优先来自 `point.review_status`。
- `candidate_snapshot` 只允许补充缺失的标题、类型、优先级等非核心字段。
- helper 输出 `source_of_truth: "plan.points"`。
- 只有无 `plan.points[]` 的旧资产兜底时，才输出 `legacy_fallback: true`。

在 `get_test_point_asset()` 中，在返回前写入：

```python
item["point_rows"] = build_test_point_asset_point_rows(item)
```

禁止：

- 禁止后端详情接口优先返回 `selected_candidates` 作为当前测试点。
- 禁止从 `candidate_snapshot.steps_hint` 覆盖 `point.steps`。
- 禁止从 `expected_result`、页面 URL、标题推断前置条件。

### 15.5 前端修复指导

在 `apps/web-ui-service/frontend/src/pages/TestPointAssetDetailPage.tsx` 中修改 `pointRows(item)`。

新的读取优先级必须是：

```text
item.point_rows > item.plan.points[] > metadata.selected_candidates(legacy fallback only)
```

实现要求：

- 先读取 `item.point_rows`，如果存在则直接作为当前点位行。
- 若 `item.point_rows` 不存在，再从 `item.plan.points[]` 构造行。
- 只有当 `plan.points[]` 为空时，才允许读取 `metadata.selected_candidates`。
- 读取 `selected_candidates` 时必须标记为历史兜底，不得当成当前事实源。
- `steps` 展示使用当前行的 `steps` 字段。
- 前置条件为空时显示“未维护”。

表格渲染建议：

```tsx
<td>{String(row.precondition || "").trim() ? text(row.precondition) : "未维护"}</td>
```

删除逻辑 `removePoints()` 需要特别注意：

- `remainingRows` 必须来自当前事实源行。
- `selected_candidates: remainingRows.map(candidatePayloadFromRow)` 作为兼容接口可以暂时保留。
- 但 `candidatePayloadFromRow()` 必须输出当前行的 `steps/precondition/expected_result/review_status`。
- 不允许直接把历史 `metadata.selected_candidates` 原样传回保存接口。

### 15.6 保存链路约束

当前 `upsert_test_point_asset()` 仍接收 `selected_candidates` 并转换为 `points[]`。本轮可以保留这个接口形态，但必须保证前端传入的 `selected_candidates` 是从当前点位行重建的派生 payload。

后续更推荐新增 `points` 字段，但不是本轮必须项。

保存后必须满足：

- canonical plan 写入 `points[]`。
- `metadata.selected_candidates` 只是派生快照。
- 再次打开详情页时，展示仍来自 `points[]`。

### 15.7 测试计划

后端单测放在：

`apps/web-ui-service/tests/test_test_point_asset_candidate_sync.py`

必须覆盖：

- `plan.points[].steps` 有数据、`metadata.selected_candidates[].steps` 为空时，`point_rows[].steps` 必须有数据。
- `candidate_snapshot.steps_hint` 是旧账号密码，`points[].steps` 是新账号密码时，`point_rows` 必须显示新账号密码。
- `points[].precondition` 为空时，API 返回空字符串。
- 无 `plan.points[]`、只有 `selected_candidates` 的旧资产允许 `legacy_fallback=true`。

前端验证：

- 打开 `mall-web-login-auth-fn-ai-0021` 详情页，步骤列应显示 `plan.points[].steps`。
- 前置条件为空时显示“未维护”。
- 删除单条测试点并刷新后，剩余测试点步骤仍存在。
- 审核通过/驳回后，步骤和前置条件不发生变化。

### 15.8 验收标准

- `mall-web-login-auth-fn-ai-0021` 详情页能显示步骤。
- `precondition` 为空时显示“未维护”。
- 即使存在 `metadata.selected_candidates`，详情页仍以 `plan.points[]` 为准。
- 旧 `selected_candidates[].steps_hint` 不能覆盖 `points[].steps`。
- 前端删除、审核、保存后，`plans/{asset_id}.json -> points[]` 仍是唯一事实源。
- 被测地址保持 `http://localhost:5174/#/login`，不得改写。

### 15.9 建议执行命令

代码修复后执行：

```bash
python3 -m py_compile apps/web-ui-service/app/api/workbench/facade.py
PYTHONPATH=apps/web-ui-service .venv/bin/python -m pytest -q apps/web-ui-service/tests/test_test_point_asset_candidate_sync.py
npm --prefix apps/web-ui-service/frontend run build
```

若后端容器运行的是挂载代码，完成后重启：

```bash
docker restart ai-quality-platform-web-1
```
