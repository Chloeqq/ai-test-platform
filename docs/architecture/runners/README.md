# Runner 专题评估与实施计划

> **适用范围**: `docs/architecture/runners/`
> **最后更新**: 2026-03-21
> **文档性质**: 现实评估 + 分阶段实施计划

---

## 1. 当前现实基线

结合当前仓库实现，Runner 层的现实状态非常明确：

- 真正可运行且相对成熟的只有 `runners/web-playwright-python/`
- `runners/api-pytest/`、`runners/api-restassured/`、`runners/mobile-appium/`、`runners/shared-runner-sdk/` 当前目录存在，但基本为空，不能按已落地 Runner 理解
- 当前 YAML 契约仍是 `v4` 风格，执行器核心是单 runner、单 `execution.page`、单浏览器上下文
- 当前回归主链的确定性主要来自：
  - `runner/yaml_executor.py`
  - `runner/action_registry.py`
  - `runner/schema_validator.py`
  - `schemas/yaml_testcase.schema.json`
  - pytest + Playwright 的实际断言执行

这意味着：Runner 层目前适合做“确定性增强”，不适合直接跃迁到一个覆盖 Web/API/Mobile/依赖编排/多页面流转/数据工厂的超大统一 Schema。

---

## 2. 对目录内文档的评估

### 2.1 `yaml-schema-v5.md`

整体判断：有参考价值，但明显超前于当前项目现实。

合理之处：

- 强调向后兼容，这个方向是对的
- 试图统一 UI/API 契约，这在平台长期演进上有价值
- 引入更丰富的元数据、依赖、期望、执行配置，适合作为远期蓝图

当前不合理或过早的地方：

- 一次性把 `global_config / api_definitions / test_cases / execution_config / data_factories / depends_on / concurrency` 全塞进一个 Schema，跨度过大
- 当前 `web-playwright-python` 甚至还没有 `v5` 解析链、转换器、兼容层、最小可运行测试
- 当前 API/Mobile Runner 并未成型，先统一 Schema 容易形成“文档统一、实现分裂”
- 对回归测试主链来说，Schema 变动过大本身就是风险

结论：

- 可以保留为“远期蓝图”
- 不能作为当前主线改造的直接实施稿
- 当前更适合先演进为 `v4.1 / v4.2` 的渐进增强，而不是一步到 `v5`

### 2.2 `multi-page-dependency-support.md`

整体判断：方向合理，但把 4 类问题揉在了一起，当前不宜整体推进。

文档里同时混合了：

1. Web 多页面流转
2. 用例间依赖
3. API + UI 混合执行
4. 执行顺序 / 依赖调度

其中只有第 1 类最接近当前 `web-playwright-python` 的自然延伸；其余 3 类更像编排层问题，不应先压到 Runner YAML 上。

合理之处：

- 多页面流转确实是当前单 `execution.page` 的真实短板
- `step.page` 或 page registry 这种思路比“每个页面单独起一条用例”更符合复杂业务流

当前不合理或过早的地方：

- `depends_on` 更适合运行编排层，而不是先落在单个 YAML 用例层
- API + UI 混合场景不该在 API runner 为空壳时就设计成统一 YAML 主链
- `flow` DSL、依赖解析、拓扑排序、状态共享一起上，会显著增加 Runner 复杂度和不确定性

结论：

- 可以拆成三个独立演进主题
  - Web 多页面执行
  - 运行级依赖编排
  - 多 Runner 统一契约
- 当前只建议优先推进第一项

---

## 3. 当前最合理的 Runner 演进原则

后续 Runner 层的设计，建议统一遵守这几条边界：

1. Runner 层必须保持强确定性
   - 断言通过/失败只能由确定性代码和执行结果决定
   - AI 不参与最终裁决
2. 先稳住 Web Runner，再谈多 Runner 对齐
   - 当前企业回归可落地性主要依赖 `web-playwright-python`
3. 先做“最小可运行增强”，不要先做“大一统 Schema”
   - Schema 设计应滞后于最小实现验证
4. 用例依赖尽量放编排层，不要急着塞进单用例 YAML
5. API/UI 混合执行是后期能力，不是当前回归链路 P0

---

## 4. 具体计划方案

### P0：稳住当前 v4 Web Runner 主链

目标：保证当前回归链路继续高确定性、可维护、可追溯。

建议项：

- 保持 `yaml_testcase.schema.json` 为当前唯一生效契约
- 补一份 `v4 reality contract` 文档，明确当前支持字段和不支持字段
- 把 `docs/architecture/runners/` 里的目标态文档都标注为“远期设计”
- 为 `YamlExecutor` 增加更清晰的边界测试：
  - 不支持多页面时明确报错
  - 不支持未知 action 时明确报错
  - Page object 缺失、target 缺失、schema 不符时明确报错

验收标准：

- 当前 smoke / AI YAML 用例不受影响
- 文档和代码契约一致
- 团队不会再把 v5 当作已实施标准

### P1：做 Web Runner 的最小多页面增强

目标：只解决当前最真实的 Web 跨页面流转问题，不引入依赖调度和多 runner 混编。

建议实现顺序：

1. `v4.1` 最小扩展
   - 在保持 `execution.page` 的前提下，允许步骤级 `page` 覆盖
   - 可选增加 `execution.pages` 注册表，但先不引入 `flow`
2. 执行器增强
   - 让 `YamlExecutor` 支持按步骤切换页面对象上下文
   - 仍然只使用同一个 Playwright `page`
3. Page Object 校验增强
   - 校验 `step.page` 对应的 page object 是否存在
   - 校验跨页面 target 是否属于对应页面
4. 增加最小回归用例
   - 登录页 -> 列表页
   - 列表页 -> 详情页

不建议此阶段做的事：

- 不做 `depends_on`
- 不做 API + UI 混合 case
- 不做拓扑排序调度
- 不做大而全的 `flow DSL`

验收标准：

- 单 YAML 用例可稳定执行 2-3 个页面切换
- 回归链路仍保持 v4 主兼容
- 错误信息能明确指出“哪个页面/哪个 target”有问题

### P2：把依赖和调度放回编排层

目标：解决“用例之间有前置关系”的问题，但不污染 Runner 核心 YAML。

建议方向：

- 在 orchestrator / execution planner 层增加 run-level dependency graph
- 依赖以“运行任务”为粒度，而不是每个 YAML case 内部描述拓扑
- Runner 只负责执行单个已分配任务

验收标准：

- Runner 不感知复杂调度算法
- 编排层可以表达“先登录初始化，再跑业务回归”

### P3：定义多 Runner 最小统一契约

目标：为未来 API / Mobile Runner 留统一入口，但不假装它们已经成熟。

先统一的不是 YAML 大 schema，而是最小执行契约：

- 执行输入
- execution record
- evidence manifest
- failure category
- artifact path

建议最小接口：

```python
class BaseRunnerContract:
    def execute(self, execution_request: dict) -> dict: ...
    def validate(self, execution_request: dict) -> list[str]: ...
    def collect_evidence(self, run_id: str) -> dict: ...
```

验收标准：

- 即使 API/Mobile 暂未完善，也有清晰对齐目标
- 不影响当前 Web Runner 主链稳定性

### P4：再评估 `yaml-schema-v5`

只有满足下面条件后，才建议重启 `v5`：

- Web 多页面已经稳定
- 至少一个 API Runner 有真实实现
- execution record / evidence manifest 已跨 runner 对齐
- 已有 `v4 -> v4.1/v4.2` 的迁移经验

到那时再决定：

- 是继续扩展 YAML
- 还是把“调度配置、依赖、数据工厂”从用例层分离出去

---

## 5. 建议的文档重构方式

当前 `docs/architecture/runners/` 更像“增强草案集合”，建议重构为：

```text
docs/architecture/runners/
├── README.md                         # 当前现实 + 分阶段计划
├── current-yaml-v4-contract.md       # 当前生效契约
├── multi-page-web-runner-plan.md     # Web 多页面最小增强（后续可从现文档收敛）
├── runner-contract-roadmap.md        # 多 Runner 最小统一契约（后续补）
└── yaml-schema-v5.md                 # 远期蓝图，明确非当前实施标准
```

这样处理后，团队先看现实，再看规划，不容易误把远期设计当当前基线。

### 当前建议阅读顺序

1. [current-yaml-v4-contract.md](./current-yaml-v4-contract.md)
2. [multi-page-web-runner-plan.md](./multi-page-web-runner-plan.md)
3. [execution-module-ownership-matrix.md](./execution-module-ownership-matrix.md)
4. [yaml-schema-v5.md](./yaml-schema-v5.md)

---

## 6. 一句话判断

这组 Runner 文档“方向有价值，但当前明显超前”。最合理的实施路径不是直接上 `YAML v5`，而是：

**先稳住 v4 Web Runner，再做最小多页面增强，然后把依赖调度放编排层，最后才谈多 Runner 统一与 v5。**
