# 📘 代码说明书
## 一句话概括
这个文件定义了四个「标准化的快递单模板」，用来规范前端（比如网页或App）往后台发送测试用例生成请求时，必须填哪些字段、哪些是必填/选填、哪些值不能乱写（比如数字要在合理范围内）。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `workbench_generation_api/payloads.py` | 定义了4种不同场景下，用户向AI测试生成服务提交请求时所用的「数据结构模板」（就像不同快递公司要求的运单格式） |

## 🔍 核心函数/类说明
- **`class FullChainRunPayload(BaseModel)`**：作用——描述一次“端到端全自动测试生成+执行”的完整请求参数。  
  - 输入：一堆带默认值的字段（比如项目名、页面名、需求描述、最大生成用例数、覆盖类型等）。  
  - 输出：无（它本身不干活，只负责“检查你填得对不对”和“帮你自动补默认值”）。  
  - 大白话解释：就像你去点一份「豪华全家桶套餐」，这个类就是菜单+点餐表单：它告诉你“必须选1个主食（page_urls 至少1个？不，这里没强制，但 run_after_generate 默认开）、可选加料（如 openapi_spec）、甜品数量不能超10个（max_cases ≤20）、辣度只能选微辣/中辣/特辣（priority 只能是 P1/P2…？虽然代码没限制，但实际业务会约定），而且系统会自动帮你填好“默认口味：微辣、默认饮料：可乐”（所有 Field(default=...) 就是这些默认值）”。

- **`class GenerateCasePayload(BaseModel)`**：作用——描述一次“只生成测试用例，不自动运行”的轻量请求。  
  - 输入：和 FullChainRunPayload 很像，但少了 `page_urls`、`combination_mode`、`coverage_profile` 等偏“执行策略”的字段。  
  - 输出：同上，只是校验+补全数据的“智能表单”。  
  - 大白话解释：相当于点「单人简餐」——只要求你填“吃啥项目（project）、哪页功能（page）、想测啥（requirement）”，其他都按最常用配置自动搞定，不折腾你选“要不要打包、要不要加急配送”。

- **`class PrecheckSelectedIntentsPayload(BaseModel)`**：作用——描述一次“提前检查用户勾选的测试意图是否合法”的请求。  
  - 输入：只需 `project`（项目名）、`preview_id`（预览ID，类似订单号）、`selected_intent_ids`（用户勾选的意图ID列表）、`selected_candidates`（勾选的候选方案）。  
  - 输出：纯校验用途，后续由后端用它查数据库确认这些ID是否存在、是否属于该项目。  
  - 大白话解释：就像你网购时“把商品加入购物车后，点击‘检查库存’按钮”——它不下单，只快速问仓库：“我挑的这几样（selected_intent_ids），现在还有货吗？是不是我家的货？”

- **`class AutoRunPayload(BaseModel)`**：作用——描述一次“根据页面URL自动识别+生成+运行”的极简请求（常用于CI/CD流水线）。  
  - 输入：强调 `page_urls`（必须至少1个URL）、`wait_seconds`（最长等待时间）、去掉 `page`/`title` 等人工填写字段。  
  - 输出：同为校验模板，但约束更“机器友好”（比如 `page_urls` 有 `min_length=1`，防止空列表提交）。  
  - 大白话解释：相当于“扫码点餐”——你只扫一个或多个网页链接（page_urls），机器人就自动识别这是哪家店（project）、卖什么（通过URL分析），然后一键下单+配送（生成+运行），连“备注不要香菜”都不用你打字（所以没 requirement 字段）。

## 🧩 调用关系与数据流转
这4个类**彼此独立，不互相调用**，它们的关系是：  
```
前端（React页面） 
    ↓ 提交JSON数据（比如用户点了“生成并运行”按钮）
    → FastAPI接口（如 /v1/generate/full-chain） 
        ↓ 接口函数声明：def full_chain_run(payload: FullChainRunPayload)
            → Pydantic 自动做三件事：
                ① 校验字段类型（如 page_urls 必须是字符串列表）✅  
                ② 补全默认值（用户没填 priority → 自动设为 "P1"）✅  
                ③ 转成Python对象（payload.project, payload.max_cases...）✅  
            ↓ 这个 payload 对象传给真正的业务逻辑函数（比如 generate_and_run()）
                → 后者用 payload.page_urls 去爬页面、用 payload.coverage_profile 决定生成哪些用例...
```
→ 所以数据流向是：**前端 → FastAPI路由 → Pydantic模型（校验+补全）→ 业务函数**

## 💡 值得学习的写法
- 用 `Field(default_factory=list)` 而不是 `Field(default=[])`：避免所有实例共享同一个空列表（Python里可变默认参数是经典陷阱，这里完美避开）。  
- 用 `Field(ge=1, le=20)` 直接在字段定义里写数值范围：不用额外写 if 判断，Pydantic 自动拦截超限输入（比如 max_cases=100 会直接报错）。  
- `tags: list[str] = Field(default_factory=lambda: ["ai-generated"])`：既保证默认值是新列表，又让默认值语义清晰（一眼看出这是AI生成的用例）。  
- 同一类字段（如 prd_text/prd_url/user_story/git_diff…）高度复用：减少重复代码，也方便未来统一加校验（比如某天要求 prd_url 必须是 https 开头，改一处就行）。

## ⚠️ 需要注意的地方
- `openapi_spec: dict[str, Any] | None = None`：这个字段允许为 `None`，但后端业务逻辑如果直接 `.get("paths")` 会报错！必须先判空（⚠️ 实际代码里容易漏掉 `if payload.openapi_spec:`）。  
- `page_urls: list[str] = Field(default_factory=list)` 在 `FullChainRunPayload` 和 `AutoRunPayload` 中都有，但 `AutoRunPayload` 加了 `min_length=1`，而 `FullChainRunPayload` 没加——意味着前者必须传 URL，后者可以不传（靠 `page` 字段兜底）。新手可能混淆“什么时候该填 URL，什么时候填 page”，需看接口文档。  
- `source: str = Field(default="manual")`：虽然默认是 manual，但业务上可能支持 "git-pr", "jira-ticket" 等来源，如果前端传了非法值（如 "wechat"），Pydantic 不会拦（因为没加 `Literal["manual", "git-pr"]`），错误会延后到业务层才发现。  
- 所有 `list[dict[str, Any]]` 类型（如 `input_sources`, `selected_candidates`）都没做深层校验：比如 dict 里必须有 `"type"` 和 `"content"` 键？Pydantic 只管“是字典列表”，不管字典里长啥样——容易导致运行时报 KeyError，建议未来升级为嵌套 Pydantic 模型。