# 页面对象 data-testid 清单导入维护实现方案

更新时间：2026-05-18

适用范围：

- 页面对象中心：`/assets/page-objects`
- 页面对象导入页：`/assets/page-objects/import`
- 页面对象元素治理页：`/assets/page-objects/{page_code}/elements`
- 后端导入接口：`/api/page-objects/imports/*`
- 被测系统源码扫描产物：`data-testid-guidelines.md`

## 1. 背景与目标

测试人员已经能够从被测系统源码中获取真实落地的 `data-testid` 清单。相比人工录制和候选提升，这类数据具备更高稳定性，应成为页面对象正式元素的重要维护入口。

本方案目标是新增“页面对象导入维护”能力，让测试人员通过上传源码扫描产物，批量创建或升级页面对象元素。

核心目标：

- 降低测试人员维护页面对象的成本。
- 把真实已落地的 `data-testid` 自动纳入正式元素库。
- 减少录制候选、源码语义、人工审核之间的重复工作。
- 保证已有页面对象 URL、引用关系和治理审计链路不被破坏。
- 为后续测试点生成、脚本编译、失败治理提供更稳定的元素契约。

## 2. 核心原则

### 2.1 被测系统地址不可改写

被测系统原始地址是业务事实，导入流程不得修改或替换。

铁律：

- 不允许把 `http://localhost:5174/#/login` 写成平台地址。
- 不允许把页面对象中的原始 URL 改写为 Docker 内部访问地址。
- Docker 访问映射只能存在于运行时配置，例如 `RUNNER_URL_REWRITE_MAP`。
- 页面对象、测试报告、用例脚本中的用户可见 URL 必须保留原始地址。

导入策略：

- 新建页面对象时，`page_url` 默认留空。
- 已存在页面对象时，不覆盖原有 `page_url`。
- 如果后续需要补 URL，必须走页面对象编辑入口，由测试人员显式维护。

### 2.2 data-testid 是高可信输入

`data-testid-guidelines.md` 的“已落地清单”来自被测系统源码，记录的是真实已添加 ID。

因此 v1 策略为：

- 默认导入为正式元素。
- 默认 `review_status=approved`。
- 默认 `stability_level=high`。
- 默认 `locator_type=data-testid`。
- 默认 `locator_source=testid`。

### 2.3 Upsert 优先，不删除重建

导入不能把已有元素删除后重建。

原因：

- 已有元素可能被测试点、用例、脚本、失败治理引用。
- 删除重建会丢失引用关系、版本记录和治理历史。

导入策略：

```text
同一 page_object_id + element_code 不存在 -> 创建正式元素
同一 page_object_id + element_code 已存在 -> 原地升级 locator 与治理字段
```

### 2.4 runtime-dom-selectors 只做辅助

`runtime-dom-selectors.json` 记录运行态 DOM 选择器，但 v1 不把它作为主导入源。

原因：

- 运行态 DOM 可能受权限、数据、弹窗状态影响。
- 运行态选择器容易混入 CSS/XPath 噪音。
- 当前最可信输入是源码中真实落地的 `data-testid`。

v1 处理方式：

- `data-testid-guidelines.md` 必填。
- `runtime-dom-selectors.json` 可选上传。
- 可选文件只记录 hash 和来源，用于后续校验能力扩展。

## 3. 当前实现状态

当前已完成 v1 最小闭环。

已实现能力：

- 页面对象中心新增“导入页面对象”入口。
- 页面对象元素治理页新增“导入本页面元素”入口。
- 新增三步式导入向导：上传文件、解析预览、确认入库。
- 新增后端预览接口、应用接口和导入批次查询接口。
- 支持解析 `data-testid-guidelines.md` 的“已落地清单”章节。
- 支持新增页面对象。
- 支持新增正式元素。
- 支持已有正式元素原地升级为 `data-testid` 定位。
- 支持动态行级模板识别。
- 支持导入批次 JSON 留存。
- 支持版本快照和治理日志写入。
- 支持前端构建后同步生产静态资源。

已验证结果：

- 真实清单解析结果：52 个页面、835 个元素、165 个动态模板。
- 后端页面对象集成测试通过。
- 前端生产构建通过。

## 4. 页面入口设计

### 4.1 页面对象中心入口

入口位置：

```text
测试资产 / 页面对象
```

新增按钮：

```text
[导入页面对象] [新建页面对象]
```

交互意图：

- `导入页面对象` 是批量维护入口。
- `新建页面对象` 是人工创建入口。
- 两者并列，但导入更适合已具备源码扫描产物的项目。

### 4.2 页面对象详情局部入口

入口位置：

```text
测试资产 / 页面对象 / 元素治理
```

新增按钮：

```text
[开始录制] [导入本页面元素] [编辑页面信息] [刷新数据] [返回页面对象]
```

交互意图：

- 在某个页面对象内导入时，默认带上 `page_code`。
- 解析预览只展示当前页面相关元素。
- 适合测试人员局部修复某个页面的元素库。

## 5. 导入向导设计

导入向导采用三步流程。

### 5.1 第一步：上传文件

字段：

| 字段 | 说明 |
|---|---|
| 项目编码 | 默认 `mall`，可由入口 query 带入 |
| 端类型 | v1 固定 `web` |
| 仅导入指定页面 | 可选，例如 `login`、`product` |
| 权威清单 | 必填，上传 `data-testid-guidelines.md` |
| 运行态 DOM 校验 | 可选，上传 `runtime-dom-selectors.json` |

用户提示：

```text
被测系统原始地址不会在导入中被改写。
```

### 5.2 第二步：解析预览

页面级摘要：

| 字段 | 说明 |
|---|---|
| 页面编码 | 解析出的 `page_code` |
| 页面名称 | 从章节标题或源码路径推导 |
| 源码路径 | 例如 `src/views/pms/product/index.vue` |
| 元素数 | 当前页面解析出的元素数量 |
| 新增 | 正式库中不存在，需要创建 |
| 升级 | 已存在但 locator 不是当前 data-testid |
| 冲突 | 同页同编码重复，需要人工处理 |
| 动态模板 | 包含 `${id}`、`${index}` 等变量 |

元素级差异：

| 字段 | 说明 |
|---|---|
| 动作 | 新增、升级、跳过、冲突 |
| 页面 | `page_code` |
| 元素编码 | `element_code` |
| data-testid | 原始 `data-testid` |
| 类型 | `business_type` |
| 策略 | `exact` 或 `template` |
| 关键元素 | 是否参与关键元素覆盖 |
| 说明 | 差异原因 |

### 5.3 第三步：确认入库

默认策略：

```text
auto_approve=true
upsert_policy=upgrade_existing
operator=admin
```

入库结果展示：

- 新建页面数
- 更新页面数
- 新增元素数
- 升级元素数
- 跳过元素数
- 冲突元素数

冲突处理：

- 如果预览存在冲突，前端禁用“确认入库”。
- 测试人员需要修正清单后重新上传。

## 6. 后端接口设计

### 6.1 预览接口

```http
POST /api/page-objects/imports/preview
Content-Type: multipart/form-data
```

表单参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| project_code | string | 否 | 默认 `mall` |
| client | string | 否 | 默认 `web` |
| source_type | string | 否 | v1 固定 `data_testid_guidelines` |
| page_code | string | 否 | 局部导入时使用 |
| data_testid_guidelines | file | 是 | `data-testid-guidelines.md` |
| runtime_dom_selectors | file | 否 | 可选校验材料 |

返回结构：

```json
{
  "item": {
    "import_id": "uuid",
    "project_code": "mall",
    "client": "web",
    "source_type": "data_testid_guidelines",
    "status": "previewed",
    "files": {},
    "summary": {},
    "pages": [],
    "elements": []
  }
}
```

### 6.2 查询导入批次

```http
GET /api/page-objects/imports/{import_id}
```

用途：

- 查看导入批次。
- 查看原始文件摘要。
- 查看解析报告。
- 查看入库结果。

### 6.3 应用导入

```http
POST /api/page-objects/imports/{import_id}/apply
```

Query 参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| auto_approve | `true` | v1 只支持自动通过 |
| upsert_policy | `upgrade_existing` | v1 只支持升级已有 |
| operator | `admin` | 写入版本和治理日志的操作人 |

返回结构：

```json
{
  "item": {
    "status": "applied",
    "apply_result": {
      "created_page_count": 0,
      "updated_page_count": 0,
      "created_element_count": 0,
      "upgraded_element_count": 0,
      "skipped_element_count": 0,
      "conflict_element_count": 0
    }
  }
}
```

## 7. 解析规则

### 7.1 权威章节

只解析：

```md
## 3. 已落地清单（首批高频核心页面）
```

遇到下一章停止：

```md
## 4. 待落地清单
```

明确不解析：

- 命名规范中的示例。
- 落地原则中的示例。
- 自动化建议中的示例。
- 待落地清单中的建议。

### 7.2 页面识别

页面识别顺序：

1. 当前章节标题中的源码路径，例如 `src/views/pms/product/index.vue`。
2. 当前清单块中的 `*-page` 元素，例如 `product-page`。
3. 根据 `data-testid` 前缀推导，例如 `product-search-submit-btn` 推导为 `product`。

示例：

| data-testid | page_code |
|---|---|
| `login-submit-btn` | `login` |
| `product-search-submit-btn` | `product` |
| `order-detail-close-btn` | `order-detail` |
| `return-apply-search-id-input` | `return-apply` |

### 7.3 元素编码

普通元素：

```text
element_code = data-testid
```

示例：

```text
login-submit-btn -> login-submit-btn
product-search-keyword-input -> product-search-keyword-input
```

动态模板元素：

```text
原始 data-testid = product-row-${id}-edit-btn
element_code = product-row-id-edit-btn
testid_value = product-row-${id}-edit-btn
locator_value = product-row-${id}-edit-btn
match_strategy = template
```

说明：

- `element_code` 使用可存储、可路由、可展示的安全编码。
- 原始模板保留在 `testid_value` 和 `locator_value`。
- 动态模板不会作为普通测试点默认候选。

### 7.4 元素类型推导

| 后缀或模式 | business_type |
|---|---|
| `-btn` | `button` |
| `-input` | `input` |
| `-select` | `input` |
| `-cascader` | `input` |
| `-picker` | `input` |
| `-switch` | `switch` |
| `-radio` | `radio` |
| `-checkbox` | `checkbox` |
| `-dialog` | `dialog` |
| `-table` | `table` |
| `-menu` | `menu` |
| 其他容器类 | `container` |

### 7.5 关键元素推导

默认非关键元素：

- `*-page`
- `*-form`
- `*-card`
- `*-table`
- `*-bar`
- `*-pagination`
- `*-panel`
- `*-steps`
- `*-tree`
- `*-widget`

默认关键元素：

- 输入框
- 按钮
- 开关
- 单选
- 复选
- 业务链接
- 弹窗确认/取消按钮
- 行级操作按钮

## 8. 入库字段映射

### 8.1 页面对象字段

新建页面对象：

| 字段 | 值 |
|---|---|
| project_code | 表单传入 |
| client | `web` |
| page_code | 解析结果 |
| page_name | 章节标题或源码文件名 |
| page_url | 空字符串 |
| route_pattern | 空字符串 |
| governance_status | `active` |
| status | `published` |
| testability_score | `90` |
| created_by | operator |

已有页面对象：

- 只补充缺失的 `page_name`。
- 可把 `status` 修正为 `published`。
- 可把空或草稿治理状态修正为 `active`。
- 绝不覆盖已有 `page_url`。

### 8.2 页面元素字段

| 字段 | 值 |
|---|---|
| element_code | 普通元素等于 data-testid，模板元素使用安全编码 |
| element_name | 根据编码和类型生成展示名 |
| locator_type | `data-testid` |
| locator_value | 原始 data-testid |
| locator_source | `testid` |
| testid_value | 原始 data-testid |
| stability_level | `high` |
| review_status | `approved` |
| status | `active` |
| match_strategy | `exact` 或 `template` |
| semantic_tags_json | `data-testid-import`，模板附加 `dynamic-row-template` |
| is_key_element | 根据类型推导 |
| governance_note | 记录来源文件和源码路径 |

### 8.3 扩展定位器

导入会同步主定位器到 `page_element_locators`。

主定位器字段：

| 字段 | 值 |
|---|---|
| locator_type | `data-testid` |
| locator_value | 原始 data-testid |
| locator_source | `testid` |
| priority | `1` |
| is_primary | `true` |

## 9. Upsert 与审计策略

### 9.1 新增元素

流程：

```text
创建 PageElement
-> 写入 PageElementVersion
-> 写入 PageElementLocator
-> 写入 PageObjectGovernanceLog(import_create)
-> 同步页面对象指标
```

### 9.2 升级元素

流程：

```text
读取已有 PageElement
-> 保存治理前快照
-> 更新 locator 与治理字段
-> 校验 approved/high 合规性
-> 写入 PageElementVersion
-> 写入 PageElementLocator
-> 写入 PageObjectGovernanceLog(import_upgrade)
-> 同步页面对象指标
```

### 9.3 跳过元素

跳过条件：

- 已存在元素。
- 已经是 `data-testid` 定位。
- 当前 locator 和导入清单一致。

### 9.4 冲突元素

冲突条件：

- 同一页面内出现重复 `element_code`。

处理策略：

- 预览阶段标记 `conflict`。
- 入库阶段不处理冲突元素。
- 前端禁用确认入库。

## 10. 文件与代码落点

后端：

| 文件 | 说明 |
|---|---|
| `apps/web-ui-service/app/services/page_object_import_service.py` | 导入解析、预览、批次保存、应用入库 |
| `apps/web-ui-service/app/routers/page_objects.py` | 导入接口路由 |
| `apps/web-ui-service/app/services/page_object_service.py` | 增加 `template` 匹配策略支持 |

前端：

| 文件 | 说明 |
|---|---|
| `apps/web-ui-service/frontend/src/pages/PageObjectImportPage.tsx` | 导入向导页 |
| `apps/web-ui-service/frontend/src/pages/PageObjectsPage.tsx` | 页面对象中心入口 |
| `apps/web-ui-service/frontend/src/pages/PageObjectElementsPage.tsx` | 导入本页面元素入口 |
| `apps/web-ui-service/frontend/src/api/assets.ts` | 导入 API helper |
| `apps/web-ui-service/frontend/src/lib/http.ts` | `postFormData` |
| `apps/web-ui-service/frontend/src/App.tsx` | 导入页路由 |

样式：

| 文件 | 说明 |
|---|---|
| `apps/web-ui-service/frontend/src/styles.css` | 补充危险冲突标签色 |

测试：

| 文件 | 说明 |
|---|---|
| `apps/web-ui-service/tests/integration/test_page_objects_api.py` | 导入预览与应用集成测试 |

## 11. 验收标准

### 11.1 解析验收

- 能解析 `data-testid-guidelines.md` 的“已落地清单”。
- 不解析命名规范中的示例。
- 不解析自动化建议中的示例。
- 能识别登录页、商品列表、订单列表、用户列表等页面。
- 能识别普通元素、容器元素、动态模板元素。
- 真实清单解析数量应稳定在合理范围内；当前样例为 52 个页面、835 个元素、165 个动态模板。

### 11.2 预览验收

- 新元素显示为 `create`。
- 旧 CSS/XPath 元素显示为 `upgrade`。
- 已经是相同 `data-testid` 的元素显示为 `skip`。
- 同页重复元素显示为 `conflict`。
- 页面级摘要和元素级差异数量一致。

### 11.3 入库验收

- 新页面对象可自动创建。
- 新元素创建为 `approved/high/data-testid`。
- 已有元素升级后保留原 `element_code` 和引用关系。
- 动态模板保留原始模板值。
- `page_url` 不被导入流程改写。
- 每次新增或升级都有版本记录。
- 每次新增或升级都有治理日志。
- 页面对象元素计数、关键元素数、审核元素数同步刷新。

### 11.4 前端验收

- 页面对象中心能看到“导入页面对象”入口。
- 元素治理页能看到“导入本页面元素”入口。
- 导入页能上传 Markdown 文件并展示预览。
- 有冲突时不能确认入库。
- 入库成功后能看到结果报告。
- 返回页面对象列表后，元素数量和治理状态刷新正确。

### 11.5 回归验收

- 已有页面对象 CRUD 不受影响。
- 已有候选提升、合并、拒绝流程不受影响。
- 已有用例执行仍能通过 `data-testid` locator 解析。
- 被测系统地址仍显示 `http://localhost:5174/#/login` 等原始地址。

## 12. 测试计划

后端编译：

```bash
./.venv/bin/python -m py_compile \
  apps/web-ui-service/app/services/page_object_import_service.py \
  apps/web-ui-service/app/routers/page_objects.py \
  apps/web-ui-service/app/services/page_object_service.py
```

后端集成测试：

```bash
./.venv/bin/python -m pytest apps/web-ui-service/tests/integration/test_page_objects_api.py -q
```

真实清单解析冒烟：

```bash
PYTHONPATH=apps/web-ui-service ./.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
from app.services.page_object_import_service import parse_data_testid_guidelines

source = Path("/Users/bettyhuang/IdeaProjects/mall-admin-web/docs/data-testid-guidelines.md")
rows = parse_data_testid_guidelines(source.read_text(encoding="utf-8"))
print({"pages": len(set(r.page_code for r in rows)), "elements": len(rows), "templates": sum(1 for r in rows if r.match_strategy == "template")})
print(Counter(r.page_code for r in rows).most_common(8))
PY
```

前端构建：

```bash
cd apps/web-ui-service/frontend
npm run build
```

手动验证：

1. 打开页面对象中心。
2. 点击“导入页面对象”。
3. 上传 `data-testid-guidelines.md`。
4. 查看页面级摘要和元素差异。
5. 点击“确认入库”。
6. 返回页面对象列表和元素治理页检查导入结果。
7. 抽查登录页，确认 `page_url` 仍为 `http://localhost:5174/#/login`。

## 13. 风险与边界

### 13.1 动态模板不能盲目自动绑定

动态模板依赖业务 ID 或行索引。

例如：

```text
product-row-${id}-edit-btn
```

如果测试步骤没有明确行 ID，不能默认选择该元素。

当前策略：

- `match_strategy=template`
- `semantic_tags_json` 包含 `dynamic-row-template`
- 不作为普通测试点自动映射的默认候选

### 13.2 页面编码推导仍需持续校准

页面编码依赖命名规范和清单结构。

当前已覆盖：

- 单词页面：`login`
- 业务页面：`product`
- 复合页面：`order-detail`
- 退货页面：`return-apply`
- 首页推荐：`home-subject`

后续如果出现不规则命名，需要扩展页面编码推导规则或引入项目级映射表。

### 13.3 文件留存目前是 JSON 批次

当前导入批次保存在：

```text
artifacts/page-object-imports/{import_id}.json
```

优点：

- 实现简单。
- 易于排查。
- 不引入迁移。

后续如果要支持列表、审计查询、回滚，应升级为数据库表。

### 13.4 v1 不做真实 DOM 校验

`runtime-dom-selectors.json` 目前只作为辅助文件留存。

后续可以扩展：

- data-testid 是否存在于运行态 DOM。
- 同一个 data-testid 是否多节点匹配。
- 元素是否可见。
- 元素是否可交互。

## 14. 后续迭代计划

### 阶段 2：导入批次中心

目标：

- 新增导入历史列表。
- 支持按项目、页面、操作人、时间查询。
- 支持查看原始文件 hash、解析报告和应用结果。

建议接口：

```http
GET /api/page-objects/imports
```

### 阶段 3：运行态校验

目标：

- 使用 `runtime-dom-selectors.json` 或浏览器探测结果校验导入元素。
- 标记未命中、重复命中、不可见、不可交互。
- 在预览页展示校验状态。

新增字段建议：

| 字段 | 说明 |
|---|---|
| runtime_match_count | 运行态匹配数量 |
| runtime_visible | 是否可见 |
| runtime_interactable | 是否可交互 |
| runtime_warning | 校验告警 |

### 阶段 4：回滚能力

目标：

- 按导入批次回滚新增元素。
- 对升级元素恢复上一版本 locator。
- 保留回滚审计日志。

注意：

- 回滚不能删除已被新用例引用的元素。
- 回滚前必须展示影响范围。

### 阶段 5：项目级页面编码映射

目标：

- 对复杂页面建立 `source_path -> page_code -> page_name` 映射。
- 避免仅靠 testid 前缀推导。
- 支持多项目、多前端仓库。

建议配置：

```json
{
  "src/views/pms/product/index.vue": {
    "page_code": "product",
    "page_name": "商品列表"
  }
}
```

### 阶段 6：测试点生成联动

目标：

- 测试点生成时优先使用 `approved/high/data-testid` 元素。
- 动态模板仅在测试数据提供 ID 时参与绑定。
- 脚本源码中输出 `locator_type=data-testid`。

## 15. 产品建议

### 15.1 文案建议

入口文案：

```text
导入页面对象
```

说明文案：

```text
上传被测系统源码扫描出的 data-testid 清单，自动创建或升级页面对象元素。
```

风险提示：

```text
导入不会改写被测系统原始 URL；已有页面地址会被完整保留。
```

### 15.2 权限建议

建议具备以下权限的用户才能执行确认入库：

- QA 管理员
- 测试资产维护人
- 项目管理员

普通测试人员可以预览，但不一定能应用。

### 15.3 审计建议

导入应用后，应在治理日志中清晰记录：

- 操作人
- 导入批次
- 来源文件
- 文件 hash
- 创建或升级动作
- before / after 字段

## 16. 当前结论

`data-testid-guidelines.md` 已经具备作为 v1 权威输入的条件。

当前实现已经打通：

```text
上传真实清单
-> 解析已落地章节
-> 预览新增/升级/冲突
-> 确认入库
-> 创建或升级正式元素
-> 写版本和治理日志
-> 页面对象指标刷新
```

这条链路可以作为页面对象治理的主入口之一，与录制候选治理形成互补：

- 源码已加 `data-testid`：走导入维护。
- 运行中发现缺失元素：走录制候选。
- 特殊业务语义补充：走人工审核。

最终目标是让测试人员维护的是“稳定业务元素资产”，而不是反复处理 CSS、XPath、截图和模糊匹配噪音。

## 17. 阶段 7：页面归属与中文命名治理方案

更新时间：2026-05-18

### 17.1 问题背景

当前页面对象导入已经能把真实 `data-testid` 写入正式元素库，但从页面列表和元素详情页看，还有两个明显的产品体验问题：

- 页面对象粒度不够业务化，例如 `sidebar`、`layout`、`login` 都显示为“登录与布局”，测试人员无法快速判断它们分别代表什么。
- 元素名称仍偏技术化，例如 `sidebar-link-routename`、`sidebar-submenu-routename` 直接作为元素名称展示，没有转成“侧边栏外链菜单项”“侧边栏父级子菜单”这类中文业务名称。

这两个问题的本质不是前端样式问题，而是页面对象导入时缺少“页面归属策略”和“元素中文命名策略”。

### 17.2 设计目标

本阶段目标：

- 让页面对象列表中的页面名称更符合测试人员认知。
- 让公共布局元素归入统一页面对象，避免被拆成多个伪页面。
- 让正式元素名称默认展示中文语义，而不是裸 `data-testid`。
- 对历史已导入数据提供安全修复路径。
- 不删除已有引用，不覆盖被测系统原始 URL。

验收后的体验应为：

```text
页面编码     页面名称
login        登录页
layout       全局布局
product      商品列表
order        订单列表
coupon       优惠券列表
```

元素示例：

```text
元素编码                         元素名称
login-username-input             用户名输入框
login-password-input             密码输入框
login-submit-btn                 登录按钮
sidebar-link-routename           侧边栏外链菜单项
sidebar-submenu-routename        侧边栏父级子菜单
layout-navbar-user-dropdown      顶部用户下拉菜单
```

### 17.3 页面对象归属策略

页面对象不应完全等同于 `data-testid` 的第一个前缀。需要区分“业务页面”和“全局公共组件”。

#### 17.3.1 业务页面

业务页面继续按页面前缀生成独立页面对象。

示例：

| data-testid | page_code | page_name |
|---|---|---|
| `login-submit-btn` | `login` | 登录页 |
| `product-search-submit-btn` | `product` | 商品列表 |
| `order-search-submit-btn` | `order` | 订单列表 |
| `coupon-search-name-input` | `coupon` | 优惠券列表 |
| `order-detail-close-btn` | `order-detail` | 订单详情 |

#### 17.3.2 全局布局组件

以下前缀不再作为独立页面对象，而是归入 `layout` 页面对象：

```text
layout
sidebar
breadcrumb
hamburger
```

归属规则：

| 原始 data-testid | 归属 page_code | page_name |
|---|---|---|
| `layout-navbar` | `layout` | 全局布局 |
| `layout-navbar-user-dropdown` | `layout` | 全局布局 |
| `sidebar-menu-routename` | `layout` | 全局布局 |
| `sidebar-submenu-routename` | `layout` | 全局布局 |
| `sidebar-link-routename` | `layout` | 全局布局 |
| `breadcrumb-item-${index}` | `layout` | 全局布局 |
| `hamburger-icon` | `layout` | 全局布局 |

理由：

- `sidebar`、`breadcrumb`、`hamburger` 不是业务页面。
- 它们是布局组件，生命周期与主框架一致。
- 测试人员通常会在“全局布局”下维护这些元素，而不是在多个伪页面里查找。

#### 17.3.3 登录页与布局分离

`data-testid-guidelines.md` 中“登录与布局”是文档章节名，不应直接成为所有元素的页面名。

应拆分为：

| 元素前缀 | page_code | page_name |
|---|---|---|
| `login-*` | `login` | 登录页 |
| `layout-*` | `layout` | 全局布局 |
| `sidebar-*` | `layout` | 全局布局 |

### 17.4 页面名称映射规则

导入器应优先使用项目级页面名称映射，其次使用源码章节标题，最后才使用源码文件名。

推荐优先级：

```text
项目级 page_code 映射
-> 特殊公共组件归属映射
-> add/update 壳页面映射
-> Markdown 中文章节标题
-> 源码文件名
-> page_code
```

内置基础映射：

| page_code | page_name |
|---|---|
| `login` | 登录页 |
| `layout` | 全局布局 |
| `home` | 首页 |
| `product` | 商品列表 |
| `order` | 订单列表 |
| `admin` | 用户列表 |
| `role` | 角色列表 |
| `brand` | 品牌列表 |
| `coupon` | 优惠券列表 |
| `menu` | 权限菜单 |
| `resource` | 权限资源 |

add/update 壳页面映射：

| data-testid | page_code | page_name |
|---|---|---|
| `product-add-page` | `product-add` | 商品新增页 |
| `product-update-page` | `product-update` | 商品编辑页 |
| `brand-add-page` | `brand-add` | 品牌新增页 |
| `brand-update-page` | `brand-update` | 品牌编辑页 |
| `menu-add-page` | `menu-add` | 菜单新增页 |
| `menu-update-page` | `menu-update` | 菜单编辑页 |

### 17.5 元素中文命名策略

元素名称是给测试人员看的，不应直接等于 `element_code`。

#### 17.5.1 字段边界

| 字段 | 用途 | 示例 |
|---|---|---|
| `element_code` | 稳定机器编码，可用于引用和脚本绑定 | `sidebar-link-routename` |
| `element_name` | 中文展示名，给测试人员阅读 | 侧边栏外链菜单项 |
| `locator_value` | 原始 `data-testid` | `sidebar-link-routename` |
| `testid_value` | 原始 `data-testid` | `sidebar-link-routename` |

注意：

- 不应为了中文展示名修改 `element_code`。
- `element_code` 可以保留真实 `data-testid` 的 kebab-case。
- 中文化只作用于 `element_name`。

#### 17.5.2 精确短语映射

优先使用精确短语映射，保证核心高频元素名称自然。

示例：

| data-testid 后缀 | element_name |
|---|---|
| `username-input` | 用户名输入框 |
| `password-input` | 密码输入框 |
| `login-submit-btn` | 登录按钮 |
| `trial-account-btn` | 试用账号按钮 |
| `trial-dialog-confirm-btn` | 试用账号弹窗确认按钮 |
| `navbar-user-dropdown` | 顶部用户下拉菜单 |
| `navbar-user-avatar` | 顶部用户头像 |
| `navbar-home-item` | 顶部首页菜单项 |
| `navbar-logout-item` | 顶部退出登录菜单项 |
| `sidebar-menu-routename` | 侧边栏菜单项 |
| `sidebar-submenu-routename` | 侧边栏父级子菜单 |
| `sidebar-link-routename` | 侧边栏外链菜单项 |
| `search-keyword-input` | 关键词搜索输入框 |
| `search-submit-btn` | 搜索按钮 |
| `search-reset-btn` | 重置按钮 |
| `dialog-cancel-btn` | 弹窗取消按钮 |
| `dialog-confirm-btn` | 弹窗确认按钮 |

#### 17.5.3 Token 组合兜底

如果没有命中精确短语，再按 token 翻译组合。

示例 token：

| token | 中文 |
|---|---|
| `sidebar` | 侧边栏 |
| `submenu` | 子菜单 |
| `link` | 链接 |
| `routename` | 路由名 |
| `navbar` | 顶部导航 |
| `dropdown` | 下拉菜单 |
| `avatar` | 头像 |
| `input` | 输入框 |
| `btn` | 按钮 |
| `switch` | 开关 |
| `table` | 表格 |

组合示例：

```text
product-search-keyword-input
-> 商品搜索关键词输入框
```

### 17.6 元素编码校验策略调整

当前页面对象治理页仍按旧规则提示：

```text
需修复编码
```

原因是旧规则只接受 snake_case：

```text
username_input
```

但真实 `data-testid` 通常是 kebab-case：

```text
login-username-input
sidebar-link-routename
```

阶段 7 应调整为：

- 页面对象导入来源为 `data-testid` 时，允许小写 kebab-case。
- 人工新建元素仍推荐 snake_case 或项目统一规范。
- `locator_source=testid` 且 `locator_type=data-testid` 且 `testid_value` 非空时，不应标红“需修复编码”。

建议规则：

```text
if locator_source == "testid" and locator_type == "data-testid":
    allow pattern: ^[a-z][a-z0-9-]{2,119}$
else:
    use formal snake_case policy
```

### 17.7 历史数据治理方案

历史数据分三类处理。

#### 17.7.1 页面名英文但页面归属正确

示例：

```text
order-logistics / logisticsDialog
coupon-history / history
```

处理方式：

- 重新导入同一份 `data-testid-guidelines.md`。
- 导入器发现旧页面名无中文、新页面名有中文时，自动更新 `page_name`。
- 不覆盖 `page_url`。
- 不删除元素。

#### 17.7.2 公共组件被拆成伪页面

示例：

```text
sidebar / 登录与布局
breadcrumb / 通用上传/富文本/布局组件
hamburger / 通用上传/富文本/布局组件
```

目标归属：

```text
layout / 全局布局
```

处理方式：

1. 新导入规则把 `sidebar-*`、`breadcrumb-*`、`hamburger-*` 归入 `layout`。
2. 导入时在 `layout` 页面对象下创建或升级对应元素。
3. 对历史 `sidebar`、`breadcrumb`、`hamburger` 页面对象做迁移评估。
4. 若历史元素无引用，则可物理删除旧伪页面对象。
5. 若历史元素有引用，则迁移引用到 `layout` 下同名元素后再删除旧元素。

#### 17.7.3 元素名称是英文编码

示例：

```text
element_code = sidebar-link-routename
element_name = sidebar-link-routename
```

目标：

```text
element_code = sidebar-link-routename
element_name = 侧边栏外链菜单项
```

处理方式：

- 再次导入时，如果 `element_name` 等于 `element_code` 或不包含中文，则自动升级为中文名称。
- 写入版本记录和治理日志。
- 不修改 `element_code`。
- 不修改 locator。

### 17.8 修复执行计划

#### P0：规则修复

- 调整页面归属策略：`sidebar/breadcrumb/hamburger -> layout`。
- 调整页面名称映射：`login -> 登录页`，`layout -> 全局布局`。
- 调整元素中文命名：引入短语映射和 token 组合。
- 调整导入 upsert：已有元素名称可从英文升级为中文。
- 调整编码校验：`data-testid` 来源允许 kebab-case，不再标红。

#### P1：修复性重导入

- 使用最新 `data-testid-guidelines.md` 重新导入。
- 检查 `layout` 页面对象是否包含导航、侧边栏、面包屑等公共元素。
- 检查 `login` 页面对象是否只包含登录页表单和弹窗元素。
- 确认页面对象数量不再因为公共组件拆分而膨胀。

#### P1：历史伪页面清理

清理对象候选：

```text
sidebar
breadcrumb
hamburger
```

清理前检查：

- 页面对象下元素是否已经在 `layout` 中有同名元素。
- 旧元素是否有 `PageObjectRef` 引用。
- 旧元素是否被测试点或用例脚本使用。

清理策略：

- 无引用：可物理删除旧页面对象及其元素。
- 有引用：先迁移引用，再删除旧元素。

#### P2：项目级术语表

将页面名和元素名映射抽为项目级配置。

示例：

```json
{
  "page_names": {
    "layout": "全局布局",
    "login": "登录页"
  },
  "element_phrases": {
    "sidebar-link-routename": "侧边栏外链菜单项"
  }
}
```

### 17.9 验收标准

页面对象列表：

- 不再出现 `sidebar` 独立页面对象，除非项目明确配置为业务页面。
- `layout` 页面名称显示为“全局布局”。
- `login` 页面名称显示为“登录页”。
- 公共导航、侧边栏、面包屑元素归到 `layout`。

元素列表：

- `sidebar-link-routename` 的元素名称显示“侧边栏外链菜单项”。
- `sidebar-submenu-routename` 的元素名称显示“侧边栏父级子菜单”。
- `login-username-input` 的元素名称显示“用户名输入框”。
- `login-password-input` 的元素名称显示“密码输入框”。
- `login-submit-btn` 的元素名称显示“登录按钮”。
- `data-testid` 来源元素不再被标记“需修复编码”。

数据安全：

- 不覆盖任何已有 `page_url`。
- 不删除有引用的元素。
- 不修改已有 `element_code`。
- 不破坏测试点和用例引用关系。
- 每次自动升级元素名称都写入版本记录和治理日志。

### 17.10 风险与取舍

#### 风险 1：公共组件是否都应归 layout

默认将 `sidebar/breadcrumb/hamburger` 归入 `layout` 是更符合测试资产管理的方案。

如果后续某项目把 `sidebar` 作为独立业务页面，需要项目级配置覆盖默认策略。

#### 风险 2：元素中文名可能不够自然

自动翻译只能覆盖大部分通用语义。

解决方式：

- 高频元素使用精确短语映射。
- 低频元素允许人工在“编辑语义”中调整。
- 后续沉淀项目级术语表。

#### 风险 3：历史伪页面清理不能一次性盲删

即使当前看起来无引用，也需要在清理前再次检查引用和脚本使用情况。

建议先做迁移预览，再执行删除。

### 17.11 结论

阶段 7 的核心不是简单“翻译中文”，而是把页面对象资产从“源码结构视角”进一步升级为“测试人员视角”。

推荐最终模型：

```text
业务页面元素 -> 归业务页面
公共布局元素 -> 归全局布局
机器稳定编码 -> 保留 data-testid
人工展示名称 -> 中文业务语义
历史错误归属 -> 先迁移再清理
```

这样页面对象中心才能真正成为测试资产库，而不是源码 ID 的平铺清单。

### 17.12 本阶段落地记录

本阶段按“页面归属、中文命名、编码校验、预览透明”四条线落地。

已执行规则：

- `login-*` 统一归属 `login / 登录页`。
- `layout-*`、`sidebar-*`、`breadcrumb-*`、`hamburger-*` 统一归属 `layout / 全局布局`。
- 导入预览返回并展示 `element_name`，测试人员可在确认入库前看到中文名称。
- 导入预览返回 `name_action=rename`，用于提示历史技术名元素会被中文名升级。
- 已存在元素在重导入时，如 `element_name` 为空、等于 `element_code`、等于 `data-testid` 或不含中文，会安全升级为中文名。
- `data-testid` 来源元素允许 kebab-case 编码，前端不再误标“需修复编码”。
- 普通人工维护元素仍保持 snake_case 校验，不放宽到全局 kebab-case。

仍需作为后续运维动作执行：

- 使用最新 `data-testid-guidelines.md` 重新导入一次，让 `layout / 登录页` 与中文元素名落库。
- 对历史伪页面 `sidebar`、`breadcrumb`、`hamburger` 做引用扫描。
- 无引用伪页面可物理删除；有引用伪页面必须先迁移引用到 `layout` 下同名元素，再删除。
- 全程不得覆盖已有 `page_url`，尤其不得改写被测系统原始地址。
