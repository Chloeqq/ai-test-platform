# Allure 报告专业化整改方案

## 结论

当前判断属实，但根因需要更精确地表述：

- 平台页面里展示的 `version: 1778566103555927300` 不是前端 `Date.now()` 生成的，而是后端读取 Allure 报告文件的 `st_mtime_ns` 纳秒级文件修改时间后直接作为版本号返回。
- Allure 报告标题仍是默认的 `Allure Report`，没有被替换为业务可读的报告名称。
- Allure 的 `environment.json`、`executors.json` 为空，导致报告首页显示“没有环境变量”“没有运行器的信息”。
- Allure 的 suites 维度只有默认包名 `tests`，feature 维度只有页面级 `login`，还没有形成“项目 -> 业务域 -> 功能 -> 场景 -> 用例”的报告结构。

因此，这个问题不是单纯的视觉样式问题，而是报告元数据、快照版本、业务分组和平台展示结构共同缺失导致的“信息空洞”。

## 证据

### 1. 快照版本来自文件修改时间

位置：`apps/web-ui-service/app/services/workbench_reporting_service.py`

当前逻辑：

```python
def get_allure_index_version(*, allure_report_root: Path) -> int:
    candidates = [
        allure_report_root / "index.html",
        allure_report_root / "widgets" / "summary.json",
        allure_report_root / "history" / "history-trend.json",
    ]
    versions: list[int] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            versions.append(int(path.stat().st_mtime_ns))
        except Exception:
            continue
    return max(versions) if versions else 0
```

这里返回的是文件系统纳秒级 mtime，例如 `1778566103555927300`。它适合作为缓存失效标识，但不适合直接展示给用户作为报告版本。

### 2. 快照目录也使用该数字

位置：`apps/web-ui-service/app/services/workbench_reporting_service.py`

当前逻辑：

```python
target = allure_snapshots_root / str(version)
return f"/allure-snapshots/{version}/index.html"
```

这会让快照 URL 也变成不可读的数字目录。技术上可用，但产品表达不专业。

### 3. Allure 报告摘要仍是默认名称

当前 `runners/web-playwright-python/allure-report/widgets/summary.json`：

```json
{
  "reportName": "Allure Report",
  "testRuns": [],
  "statistic": {
    "failed": 0,
    "broken": 1,
    "skipped": 0,
    "passed": 2,
    "unknown": 0,
    "total": 3
  }
}
```

说明报告生成阶段还没有注入业务报告名称。

### 4. 环境与执行器信息为空

当前文件状态：

```json
// runners/web-playwright-python/allure-report/widgets/environment.json
[]

// runners/web-playwright-python/allure-report/widgets/executors.json
[]
```

这对应截图里的“环境：没有环境变量”“运行器：没有运行器的信息”。

## 产品目标

把 Allure 从“默认工具报告”升级为平台内的“企业级执行报告”，目标如下：

- 用户一眼知道这份报告属于哪个项目、哪个页面、哪次执行、哪个用例版本。
- 报告版本不再显示纳秒时间戳，而是显示可追溯、可沟通的业务版本。
- 环境、浏览器、Runner、执行来源、Git 信息、目标地址完整可见。
- 报告结构从 `tests/login` 升级为业务可读分组，例如 `商城后台 / 权限与认证 / 登录与身份验证 / 首次登录成功`。
- 平台内 Allure 页不再暴露原始 JSON 为主，而是展示经过产品化整理的摘要卡片。

## 版本号规范

### 展示版本

推荐格式：

```text
TC-LOGIN-0001-v1.r3
```

含义：

- `TC-LOGIN-0001`：用例编码或短编码。
- `v1`：用例中心版本号，来源于 `TestCaseVersion.version_no`。
- `r3`：该用例第 3 次执行，来源于执行历史计数。

如果是多用例聚合报告：

```text
mall-login-2026-05-13-Run03
```

含义：

- `mall-login`：项目与页面。
- `2026-05-13`：报告日期。
- `Run03`：当天第 3 次聚合执行。

### 技术缓存版本

仍允许保留文件 mtime/ns 作为内部缓存版本，但必须改名为：

```json
{
  "cache_version": 1778566103555927300,
  "display_version": "TC-LOGIN-0001-v1.r3"
}
```

前端只展示 `display_version`，不再展示 `cache_version`。

## 后端整改计划

### 阶段 1：拆分技术版本与展示版本

新增报告快照元数据构建函数：

```python
def build_allure_report_identity(*, latest_run, latest_case, summary):
    return {
        "cache_version": get_allure_index_cache_version(),
        "display_version": build_display_version(latest_run, latest_case),
        "report_name": build_report_name(latest_run, latest_case, summary),
        "snapshot_slug": build_snapshot_slug(latest_run, latest_case),
    }
```

接口返回结构从：

```json
{
  "available": true,
  "version": 1778566103555927300,
  "allure_index": "/allure-snapshots/1778566103555927300/index.html"
}
```

调整为：

```json
{
  "available": true,
  "version": "TC-LOGIN-0001-v1.r3",
  "cache_version": 1778566103555927300,
  "report_name": "首次登录成功 - 回归执行报告 (TC-LOGIN-0001-v1.r3)",
  "allure_index": "/allure-snapshots/TC-LOGIN-0001-v1-r3/index.html"
}
```

兼容策略：

- `version` 字段改为展示版本。
- 新增 `cache_version` 字段用于前端缓存判断。
- 快照目录使用安全 slug，不使用纯纳秒数字。

### 阶段 2：生成 Allure 元数据文件

在执行 pytest 前或 Allure generate 前写入：

- `environment.properties`
- `executor.json`
- 可选 `categories.json`

建议内容：

```properties
Project=mall
Environment=local-demo
Base URL=http://localhost:5174/#/login
Browser=Chromium
Runner=pytest + playwright
Run Source=case_center
Case ID=mall-web-login-auth-fn-ai-0001
Case Version=v1
```

`executor.json` 示例：

```json
{
  "name": "AI 自动化测试平台",
  "type": "pytest-playwright",
  "url": "http://127.0.0.1:8013",
  "buildName": "首次登录成功 - v1.r3",
  "buildUrl": "/react/execution/results/15",
  "reportName": "首次登录成功 - 回归执行报告"
}
```

### 阶段 3：补齐业务分组标签

当前 runner 已经设置：

```python
allure.dynamic.title(title)
allure.dynamic.feature(page_name)
allure.dynamic.story(case_id)
```

需要升级为：

```python
allure.dynamic.epic(project_name)
allure.dynamic.feature(business_domain)
allure.dynamic.story(test_point_title)
allure.dynamic.label("page", page_name)
allure.dynamic.label("priority", priority)
allure.dynamic.label("source_asset", source_asset_title)
allure.dynamic.tag(priority, intent_type, "ai-generated")
```

推荐映射：

| YAML / 用例字段 | Allure 字段 |
|---|---|
| project | epic |
| module/page | feature |
| title | story/title |
| priority | severity/tag |
| source_asset_title | label |
| selected_intent_ids | label/tag |

### 阶段 4：平台 Allure 页产品化展示

当前平台页主要展示原始状态和 JSON 摘要。应调整为：

```text
┌─ Allure 报告 ───────────────────────────────┐
│ 首次登录成功 - 回归执行报告                  │
│ 版本：TC-LOGIN-0001-v1.r3                    │
│ 项目：mall   页面：login   环境：local-demo   │
│ 执行：3 条，通过 2，失败 1，通过率 66.7%        │
│ [打开 Allure 报告] [刷新报告]                 │
└────────────────────────────────────────────┘

┌─ 环境信息 ─────────────┐ ┌─ 执行器 ─────────────┐
│ Browser: Chromium      │ │ pytest + playwright  │
│ Base URL: ...          │ │ Run Source: case_center│
│ Git: a3f2b1c           │ │ Run ID: ...           │
└────────────────────────┘ └──────────────────────┘
```

JSON 原文保留为“调试信息”折叠区，不作为默认视觉重点。

### 阶段 5：视觉统一

Allure 嵌入页采用平台字体和柔和状态色：

```css
body {
  font-family: var(--font-ui);
}

.status-passed {
  background: #ecfdf3;
  color: #027a48;
}

.status-failed,
.status-broken {
  background: #fef2f2;
  color: #b42318;
}

.status-skipped {
  background: #f8fafc;
  color: #475569;
}
```

注意：Allure 原生 HTML 是静态生成产物，不建议直接手改生成后的文件作为长期方案。应通过报告生成后的统一注入脚本或平台外层容器样式进行增强。

## 验收标准

- 平台 Allure 页不再展示 `1778...` 这类时间戳版本号。
- `version` 展示为 `TC-LOGIN-0001-v1.rN` 或 `mall-login-YYYY-MM-DD-RunNN`。
- `summary.reportName` 不再是 `Allure Report`，而是业务可读名称。
- Allure 首页 Environment 区域有项目、环境、Base URL、浏览器、Runner、Run ID。
- Allure 首页 Executor 区域有执行器名称、执行来源、平台链接。
- suites 不再只显示 `tests`，至少能按项目/页面/用例标题识别。
- 平台内 Allure 页默认展示摘要卡片，原始 JSON 折叠。

## 实施优先级

1. P0：拆分 `cache_version` 与 `display_version`，消除时间戳展示。
2. P0：写入 `environment.properties` 与 `executor.json`，补齐环境/运行器信息。
3. P1：生成业务化 `report_name`，替换默认 `Allure Report`。
4. P1：增强 Allure 动态标签，形成业务分组。
5. P2：平台 Allure 页 UI 产品化，隐藏原始 JSON 噪音。
6. P2：统一嵌入页字体、状态色、卡片圆角。

## 风险与兼容

- 如果前端或缓存逻辑依赖 `version` 为数字，需要保留 `cache_version` 并逐步迁移。
- 快照目录从数字改为 slug 后，需要保留旧数字快照访问能力，避免历史链接失效。
- Allure 原生报告的深层样式不宜过度魔改，否则升级 Allure CLI 时维护成本较高。
- 多用例聚合报告无法绑定单一用例版本时，应使用项目/页面/日期/序号格式，而不是硬套某个 case version。

## 建议下一步

先做后端最小闭环：

1. 新增 `build_allure_report_identity()`。
2. 将接口返回的 `version` 改为展示版本，新增 `cache_version`。
3. `ensure_allure_snapshot()` 支持 `snapshot_slug`。
4. 在生成 Allure 前写入 `environment.properties` 和 `executor.json`。
5. 补一组单元测试，验证不再返回纳秒时间戳。

## 阶段 6：Allure 原生报告 UI 与品牌化

### 目标

让 `/allure/index.html` 与 `/allure-snapshots/.../index.html` 打开的 Allure 原生报告，与平台主站视觉规范保持一致。

核心目标：

- 字体统一为平台 UI 字体栈。
- 状态色从 Allure 默认高饱和色调整为平台柔和状态色。
- 卡片、面板、表格增加统一圆角和轻量边框。
- 不直接修改 Allure 生成后的静态文件，避免 Allure 升级或重新生成报告后样式丢失。
- 保留 Allure 原生交互能力，避免影响 JS/CSS/图片等静态资源加载。

### 当前入口判断

当前 Allure 静态资源在 `apps/web-ui-service/app/main.py` 中通过 `StaticFiles` 直接挂载：

```python
app.mount("/allure", StaticFiles(directory=str(ALLURE_DIR)), name="allure")
app.mount("/allure-snapshots", StaticFiles(directory=str(ALLURE_SNAPSHOTS_DIR)), name="allure-snapshots")
```

因此，品牌化不能只在 reporting service 中写函数，还需要让 HTML 响应经过自定义静态服务。

### 实现方案

新增 HTML 注入函数：

```python
def inject_allure_branding(html_content: str) -> str:
    if "data-atp-allure-branding" in html_content:
        return html_content

    custom_style = """
    <style data-atp-allure-branding>
      :root {
        --atp-font-ui: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "Noto Sans SC", sans-serif;
        --atp-success-bg: #ecfdf3;
        --atp-success-text: #027a48;
        --atp-danger-bg: #fef2f2;
        --atp-danger-text: #b42318;
        --atp-muted-bg: #f8fafc;
        --atp-muted-text: #475569;
        --atp-card-radius: 10px;
      }

      body,
      button,
      input,
      select,
      textarea {
        font-family: var(--atp-font-ui) !important;
      }

      .status-passed,
      .status-passed span {
        background: var(--atp-success-bg) !important;
        color: var(--atp-success-text) !important;
      }

      .status-failed,
      .status-broken,
      .status-failed span,
      .status-broken span {
        background: var(--atp-danger-bg) !important;
        color: var(--atp-danger-text) !important;
      }

      .status-skipped,
      .status-unknown {
        background: var(--atp-muted-bg) !important;
        color: var(--atp-muted-text) !important;
      }

      .pane,
      .widget,
      .card,
      .table,
      .side-nav {
        border-radius: var(--atp-card-radius);
      }
    </style>
    """

    if "</head>" not in html_content:
        return html_content + custom_style

    return html_content.replace("</head>", f"{custom_style}\n</head>")
```

新增自定义静态服务：

```python
class BrandedAllureStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if path.endswith(".html"):
            file_path = Path(self.directory) / path
            if file_path.exists() and file_path.is_file():
                html = file_path.read_text(encoding="utf-8")
                return HTMLResponse(inject_allure_branding(html))
        return await super().get_response(path, scope)
```

挂载方式调整为：

```python
if ALLURE_DIR.exists():
    app.mount("/allure", BrandedAllureStaticFiles(directory=str(ALLURE_DIR)), name="allure")

app.mount(
    "/allure-snapshots",
    BrandedAllureStaticFiles(directory=str(ALLURE_SNAPSHOTS_DIR)),
    name="allure-snapshots",
)
```

### Allure Labels 增强

当前 `conftest.py` 已经有基础动态标签注入。下一步继续补齐业务层级：

```python
allure.dynamic.epic("商城后台 (mall)")
allure.dynamic.feature("登录与身份验证")
allure.dynamic.story("首次登录成功")
allure.dynamic.label("page", "login")
allure.dynamic.label("priority", "P0")
allure.dynamic.label("source_asset", "登录页身份验证测试点集")
allure.dynamic.tag("P0", "冒烟测试", "ai-generated")
```

字段来源约定：

| 业务含义 | Allure 字段 | 来源 |
|---|---|---|
| 项目 | epic | project / project_code / 项目显示名 |
| 功能域 | feature | 页面对象业务域、页面名或资产标题推导 |
| 测试点标题 | story | requirement.title 或 case title |
| 页面 | label(page) | execution.page |
| 优先级 | label(priority), severity, tag | case.priority |
| 来源资产 | label(source_asset) | source_asset_title 优先，source_asset_id 兜底 |
| 意图追踪 | label(intent_id) | requirement.intent_id / selected_intent_ids |

### 验收标准

- `/allure/index.html` 注入 `data-atp-allure-branding` 样式。
- `/allure-snapshots/.../index.html` 注入同样品牌样式。
- `.js`、`.css`、`.png`、`.json` 等静态资源仍由原生 `StaticFiles` 返回，不被注入逻辑影响。
- Allure 页面字体与平台主站一致。
- Passed / Failed / Broken / Skipped 状态色变为平台柔和状态色。
- 重新执行 `allure generate` 后，不需要手改生成文件，品牌样式仍生效。
- 新生成用例报告中能看到 `epic / feature / story / priority / source_asset` 等业务标签。

### 测试计划

- 单测 `inject_allure_branding()`：可注入、不会重复注入、缺少 `</head>` 时安全追加。
- 单测 `BrandedAllureStaticFiles`：HTML 返回包含品牌样式，非 HTML 资源不被修改。
- Runner 测试：验证 `extract_allure_test_metadata()` 与 `apply_allure_test_metadata()` 不破坏已有标签测试。
- 手动验证：打开 `/execution/results/allure`，点击“打开 Allure 报告”，确认原生报告样式与平台主站一致。

## 阶段 7：Allure 报告可信化与专业化问题修复计划

### 背景

阶段 1 到阶段 6 已经完成或规划了版本号可读化、报告元数据补齐、平台摘要页产品化、原生 Allure HTML 品牌化等能力。但当前实际报告仍存在“数据可信度”和“测试人员可读性”问题。

本阶段目标不是继续增加视觉皮肤，而是修复报告执行链路中的核心质量问题：确保每份报告只代表本次执行，隐藏敏感参数，展示业务化步骤，并让失败分类和业务树真正可用于测试复盘。

### 当前剩余问题

- Allure results 混入历史结果，导致单条用例报告出现历史 `2 passed + 1 broken` 这类混合统计，报告总数和通过率不可信。
- 参数区暴露完整 `test_case`，包含完整 YAML、locator、账号密码、步骤明细，既不专业也有安全风险。
- 报告缺少业务化执行步骤，测试人员看不到“打开登录页面、输入用户名、输入密码、点击登录按钮、验证跳转”等关键过程。
- 当前报告仍显示技术化 `tests/test_yaml_ai_generated`，业务树没有稳定呈现“商城后台 > 登录与身份验证 > 首次登录成功”。
- `Base_URL` 未稳定展示真实被测页面，容易把平台地址和被测系统地址混淆。
- 失败分类仍是 Allure 默认 `Test defects`，无法区分环境不可达、元素定位失败、断言失败、用例数据问题。
- 单条演示执行与批量执行缺少性能策略区分，演示延迟可能拖慢批量执行。

### 修复优先级

- `P0`：按 `run_id` 隔离 Allure results。每次执行创建独立 results 目录，并只用当前 run 的结果生成本次报告；历史结果只做归档或平台执行历史统计，不再混入新报告。
- `P0`：隐藏完整 `test_case` 参数。pytest 执行仍可传入完整 dict，但 Allure 展示层只保留安全摘要字段，例如 `case_id`、`case_title`、`page`、`priority`、`source_asset`、`target_url`。
- `P1`：为 YAML 执行步骤补充 `allure.step`。步骤标题必须使用测试人员可读文案，密码等敏感值必须脱敏，预期结果可作为步骤附件或说明展示。
- `P1`：补齐并验证 `epic / feature / story / priority / source_asset / intent_id`。新生成报告必须形成稳定业务树，不再依赖默认 pytest 包名作为主要导航。
- `P1`：生成业务化 `categories.json`。至少覆盖“环境/页面不可达”、“元素定位失败”、“断言失败”、“用例数据/前置条件失败”、“执行器异常”等分类。
- `P2`：版本号绑定真实执行次数或 `run_id`。用户可见版本禁止使用时间戳，推荐格式为 `mall-web-login-auth-fn-ai-0001-v1.r3` 或 `Allure-2026-05-13-Run01`。
- `P2`：批量执行关闭演示延迟。单条可视化演示可以保留 slowmo、step delay、final hold；批量执行默认关闭这些等待项。

### 实施原则

- Allure 原生报告代表“一次执行”或“一次批次执行”，不再作为全历史聚合报表使用。
- 历史趋势、执行历史、失败统计由平台自己的执行记录页承载，不依赖全局 Allure results 长期累积。
- 敏感数据默认脱敏，尤其是密码、token、cookie、完整请求头、完整用例 YAML。
- 平台地址和被测系统地址分开表达：被测地址进入环境信息，平台地址进入 executor 的 `url/buildUrl`。
- 本阶段优先修复数据质量和执行链路，再做更细的视觉优化。

### 验收标准

- 单条登录用例报告 `total=1`，结果只反映本次执行。
- 报告中不再出现历史 `2 passed + 1 broken` 混合统计。
- 参数区不出现完整 YAML、locator 明文、密码明文。
- 报告业务树展示“商城后台 > 登录与身份验证 > 首次登录成功”。
- 环境信息展示真实被测页面，例如 `http://localhost:5174/#/login`。
- 失败分类为业务可读名称，而不是默认 `Test defects`。
- 批量执行报告总数等于本批次用例数，不混入其他用户或历史执行结果。
- 单条演示执行耗时可控，批量执行不受可视化 slowmo 和 hold 影响。

### 测试计划

- 单测 run 级 Allure results 目录隔离：连续两次执行不互相污染。
- 单测 Allure 参数安全：结果文件中不包含完整 `test_case`、locator 明文、密码明文。
- 单测 Allure metadata：校验 `epic / feature / story / priority / source_asset / intent_id / base_url` 注入结果。
- 单测 `categories.json`：覆盖元素定位失败、断言失败、环境不可达三类典型异常。
- 集成验证单条用例执行：Allure `summary.json` 中 `total=1`，状态等于本次执行结果。
- 集成验证批量执行：批次级报告总数等于批次用例数，且不读取历史 results。
- 浏览器验证：打开 `/allure-snapshots/.../index.html`，确认报告标题、环境信息、业务树、步骤详情、状态色和品牌样式均符合预期。
