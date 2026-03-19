# 当前架构与调用链

本文档描述仓库当前阶段已经落地的架构分层、目录依赖关系，以及“从需求到测试执行”的真实调用链。

说明：

- 重点基于当前已有实现，不按 README 的理想蓝图虚构未落地能力。
- 当前最可信的主链路是 `agents/test-design-agent` 与 `runners/web-playwright-python`。

## 1. 架构分层图

```mermaid
flowchart TB
    A["输入源层
    PRD / 原型图 / OpenAPI / Git Diff / 缺陷单 / 线上日志"]

    B["测试资产中心
    assets/
    用例库 / Page Objects / API Contracts / 数据模板 / 标签规则"]

    C["AI 编排层
    agents/
    requirement-parser / test-design / script-generation
    failure-triage / risk-evaluation / planner / self-healing"]

    D["自动化执行层
    runners/
    Web Playwright / API / Mobile"]

    E["执行与调度中心
    apps/
    ai-orchestrator / scheduler / runner-service / gateway"]

    F["证据采集层
    evidence/
    screenshot / html / trace / video / logs / network"]

    G["质量分析层
    analytics/
    flaky-analysis / clustering / trend-analysis / risk-scoring / reports"]

    H["发布治理层
    release gate / dashboard / notification / regression recommendation"]

    I["基础设施与共享能力
    infra/ configs/ shared/ integrations/"]

    A --> B
    B --> C
    C --> D
    D --> F
    F --> G
    G --> H

    E --> C
    E --> D
    E --> F

    I --> C
    I --> D
    I --> E
    I --> G
    I --> H
```

## 2. 当前项目的模块依赖图（按目录）

```mermaid
flowchart LR
    subgraph Input["输入与配置"]
        ENV[".env / .env.example"]
        DOCS["README.md / docs/"]
    end

    subgraph Assets["测试资产层"]
        ASSETS["assets/"]
        TC["assets/test-cases/"]
        PO["assets/page-objects/"]
        DATA["assets/test-data-templates/ 等"]
    end

    subgraph Agents["AI 生成层"]
        TDA["agents/test-design-agent/"]
    end

    subgraph Runners["执行层"]
        RPY["runners/web-playwright-python/"]
        RTS["runners/web-playwright/"]
        RAPI["runners/api-pytest / api-restassured"]
        RMOB["runners/mobile-appium"]
    end

    subgraph Platform["平台骨架层"]
        APPS["apps/"]
        ANALYTICS["analytics/"]
        EVIDENCE["evidence/"]
        INTEGRATIONS["integrations/"]
        CONFIGS["configs/"]
        SHARED["shared/"]
        INFRA["infra/"]
        TESTS["tests/"]
    end

    ENV --> TDA
    ENV --> RPY

    ASSETS --> TDA
    TDA --> TC

    TC --> RPY
    PO --> RPY
    DATA --> RPY

    RPY --> EVIDENCE
    RPY --> TESTS

    CONFIGS --> APPS
    CONFIGS --> ANALYTICS
    CONFIGS --> EVIDENCE
    CONFIGS --> RPY

    SHARED --> APPS
    SHARED --> ANALYTICS
    SHARED --> EVIDENCE

    INTEGRATIONS --> APPS
    INTEGRATIONS --> ANALYTICS

    INFRA --> APPS
    INFRA --> EVIDENCE
    INFRA --> ANALYTICS

    DOCS -.定义目标与分层.-> APPS
    DOCS -.定义目标与分层.-> Agents
    DOCS -.定义目标与分层.-> Runners

    RTS -.规划中/不稳定.-> ASSETS
    RAPI -.规划中.-> ASSETS
    RMOB -.规划中.-> ASSETS
    APPS -.大多仍是占位.-> RPY
    ANALYTICS -.大多仍是占位.-> EVIDENCE
```

说明：

- 当前真正有强依赖关系的主链路是 `agents/test-design-agent -> assets/test-cases -> runners/web-playwright-python`。
- `assets/` 是当前最核心的共享层，AI 生成结果和执行输入都在这里汇聚。
- `apps/`、`analytics/`、`evidence/`、`integrations/`、`infra/` 主要还是平台化预留目录。

## 3. 当前实际调用关系图

```mermaid
flowchart LR
    A["需求文本"]
    B["test-design-agent
    agents/test-design-agent/src/agent.py"]
    C["LLM(OpenAI-compatible API)
    OPENAI_BASE_URL / OPENAI_MODEL"]
    D["生成 YAML 测试用例
    assets/test-cases/ai-generated"]
    E["已有 YAML 用例
    assets/test-cases/smoke"]
    F["pytest 入口
    runners/web-playwright-python/tests/test_yaml_smoke.py"]
    G["YAML Loader + Schema Validator
    yaml_loader.py / schema_validator.py"]
    H["Data Expander
    data_expander.py"]
    I["YamlExecutor
    yaml_executor.py"]
    J["Page Object
    assets/page-objects/web/*.page-object.yaml"]
    K["Action Registry / Locator Resolver
    action_registry.py / locator_resolver.py"]
    L["Playwright Page"]
    M["测试产物
    screenshots / html / meta / videos"]

    A --> B
    B --> C
    C --> B
    B --> D

    D --> F
    E --> F

    F --> G
    G --> H
    H --> I
    I --> J
    I --> K
    K --> L
    L --> M
```

## 4. 从需求到测试执行落地的时序图

```mermaid
sequenceDiagram
    participant U as 用户/测试人员
    participant A as TestDesignAgent
    participant L as LLM(OpenAI兼容接口)
    participant Y as assets/test-cases/ai-generated
    participant P as pytest入口
    participant LD as YAML Loader
    participant SD as Schema Validator
    participant DX as Data Expander
    participant XE as YamlExecutor
    participant PO as Page Object
    participant PW as Playwright Browser
    participant EV as Artifacts/Evidence

    U->>A: 输入自然语言需求
    A->>A: 读取页面元素与目标约束
    A->>L: 发送 prompt 生成 YAML
    L-->>A: 返回 YAML 文本
    A->>A: 清洗、归一化、target 重写、Pydantic 校验
    A->>Y: 保存 YAML 用例

    U->>P: 执行 pytest
    P->>LD: 读取 smoke/ai-generated 下的 YAML
    LD->>SD: 校验 YAML schema
    SD-->>LD: 校验通过
    LD-->>P: 返回测试用例

    P->>DX: 按 data 字段展开参数化用例
    DX-->>P: 返回展开后的 case 列表

    loop 对每条测试用例
        P->>XE: execute(test_case)
        XE->>PO: 加载对应 page-object
        PO-->>XE: 返回元素定位定义
        XE->>PW: 执行 login/click/fill/wait/assert
        PW-->>XE: 返回页面状态
    end

    alt 测试失败
        P->>EV: 保存 screenshot/html/meta/video
    else 测试通过
        P-->>U: 返回通过结果
    end
```

## 5. 当前主链路对应目录

- AI 测试设计：`agents/test-design-agent/`
- 测试资产：`assets/test-cases/`、`assets/page-objects/`
- Python Web Runner：`runners/web-playwright-python/`
- 平台骨架：`apps/`、`analytics/`、`evidence/`、`integrations/`、`infra/`

## 6. 当前结论

- 已形成的核心闭环：`需求 -> AI 生成 YAML -> YAML 进入资产层 -> Python Playwright Runner 执行 -> 输出测试证据`
- 目前“平台骨架”层次完整，但实际代码主要集中在 Python runner 和单个 Python agent。
- 后续如果要让平台真正跑起来，需要优先补齐 orchestrator、统一工程构建、证据流转与分析链路。
