# 📘 代码说明书
## 一句话概括  
这是一个“网页元素治理系统”的数据库模型定义文件，用来**系统化地记录、管理、追踪一个网页上所有可交互元素（比如按钮、输入框、导航栏）的完整生命周期**——从自动识别候选元素，到人工审核、版本控制、健康检查，再到关联测试用例和变更日志，就像给每个网页元素建了一份带身份证、体检报告、成长档案和操作记录的“电子户口本”。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `page_object.py` | 定义了网页自动化测试中“页面”和“页面元素”相关的一整套数据库表结构，是整个页面对象模型（Page Object Model）在数据库里的“蓝图”或“地图”。 |

## 🔍 核心函数/类说明  
- **`class PageObject`**：代表一个“网页页面”本身（比如“商品详情页”“购物车页”）。  
  - 输入：无（它是数据模型，不接收参数）  
  - 输出：无（它只是告诉数据库“这个表长什么样”）  
  - 大白话解释：就像给每个网页办一张“身份证”，记录它的项目名（`project_code`）、终端类型（`client`，如 web/app）、页面唯一编码（`page_code`）、URL、名称、状态等。还自带“出生时间”（`created_at`）和“最后更新时间”（`updated_at`），方便知道这个页面什么时候上线、什么时候改版。

- **`class PageElement`**：代表网页上的一个具体“可操作元素”（比如“加入购物车按钮”“商品标题文字”）。  
  - 输入/输出：同上，是数据模型。  
  - 大白话解释：这是真正的“主角”。它不仅存元素名字（`element_name`）和定位方式（`locator_type` + `locator_value`，比如 CSS 选择器 `"button#add-to-cart"`），还记录了它的业务属性（`business_type` 如“下单按钮”）、稳定性评级（`stability_level`）、是否关键元素（`is_key_element`）、审核状态（`review_status`），甚至谁负责（`owner`）、当前是否启用（`status`）。相当于给每个按钮/输入框建了一张“员工档案”。

- **`class PageElementVersion`**：专门记录某个元素的“历史版本”。  
  - 大白话解释：当一个按钮的定位方式被修改（比如从 CSS 改成 data-testid），系统不会直接覆盖旧数据，而是新增一条“第2版”记录。这样就能回溯：“这个按钮上个月是怎么找的？为什么现在找不到了？”——就像 Git 提交记录，但专为网页元素设计。

- **`class PageObjectCandidateGroup` & `PageObjectCandidateElement`**：代表“自动扫描发现的待审核元素候选组/单个候选”。  
  - 大白话解释：想象有个机器人每天自动逛网站，截图+分析 DOM，发现10个长得像“登录按钮”的新元素。它不会直接入库，而是先打包成一个“候选组”（`CandidateGroup`），再把每个疑似按钮单独列为“候选元素”（`CandidateElement`），附上质量分（`quality_score`）、风险标签（`risk_tags_json`）、截图文本样本（`sample_texts_json`）等证据，供人工判断：“这到底是不是我们要管的那个登录按钮？”——这是自动化与人工协作的关键桥梁。

- **`class PageElementLocator`**：代表一个元素的“多种定位方式”（备用方案）。  
  - 大白话解释：好司机开车都备着导航APP、纸质地图、问路三套方案。这个类就是给一个按钮存多个“找法”：主用 CSS、备用 testid、再备一个 XPath。还标了优先级（`priority`）和是否主用（`is_primary`），并记录每次验证是否成功（`verification_status`）——让自动化脚本更抗变化、更健壮。

- **`class PageObjectRef`**：记录“这个元素被哪些测试用例/其他系统用到了”。  
  - 大白话解释：就像查一个人的“社会关系网”——这个“提交订单按钮”被哪些测试脚本（`reference_type="test_case"`）、哪些监控任务调用了？方便影响分析：“如果我改了这个按钮的定位，会影响多少测试？”

- **`class PageElementHealthCheck`**：记录“这个元素最近体检结果如何”。  
  - 大白话解释：定期自动运行检查（比如“页面加载后它还在不在？”“点击后有没有报错？”），把结果（`check_status`）和详细日志（`detail`）记下来。相当于给按钮做“血压+心电图”监测，及时发现“亚健康”元素。

- **`class PageObjectRecorderSession`**：记录“谁在什么时候启动了一次自动扫描任务”。  
  - 大白话解释：就像录像机的“录制日志”——谁（`started_by`）、什么时间（`started_at`）、扫哪个项目哪页（`project_code`/`page_code`）、进程号（`process_pid`）、有没有报错（`error_message`）、最后心跳时间（`heartbeat_at`）……便于排查“为什么这次没扫出新按钮？”。

- **`class PageObjectGovernanceLog`**：记录“谁对哪个页面/元素做了什么操作”。  
  - 大白话解释：系统的“操作流水账”——比如“张三把‘搜索框’的稳定性等级从 low 改成了 high”，这条日志会存下操作前（`before_payload`）和操作后（`after_payload`）的完整数据快照。审计、回滚、问题复盘全靠它。

## 🧩 调用关系与数据流转  
（这是数据层面的“血缘关系”，不是函数调用）  
```
PageObjectRecorderSession ──(触发)──→ PageObjectCandidateElement  
　　↓（扫描生成）　　　　　　　　　　　　↓（分组聚合）  
PageObjectCandidateGroup ←──────────────┘  
　　↓（人工审核后）  
PageElement ──┬─→ PageElementVersion （每次修改定位，就新增一版）  
　　　　　　 ├─→ PageElementLocator （一个元素可配多个定位方式）  
　　　　　　 ├─→ PageElementHealthCheck （定期给它做健康检查）  
　　　　　　 ├─→ PageObjectRef （记录谁在用它）  
　　　　　　 └─→ PageObjectGovernanceLog （所有增删改操作都记日志）  
　　　　　　　　　↑  
PageObject ←───────┘ （一个页面包含多个元素，通过 foreign key 关联）
```  
✅ 简单说：**扫描任务 → 产生候选 → 人工确认 → 落库成正式元素 → 后续所有操作（改定位、加备用、做检查、被引用、被修改）都围绕这个元素展开，并全程留痕。**

## 💡 值得学习的写法  
- **复合唯一约束 + 多维度索引**：比如 `PageObject` 的 `uq_page_objects_identity` 约束（`project_code+client+page_code` 三者组合唯一），确保同一项目同一终端下的页面编码不重复；同时为高频查询字段（如 `governance_status`, `created_at`, `page_code`）建了大量 `Index`，就像图书馆给书按“作者”“出版年”“分类号”都贴上标签，查起来飞快。  
- **JSON 字段的合理使用**：`anchor_config_json`、`aliases_json`、`risk_tags_json` 等用 `JSON` 类型存储灵活结构（如列表、嵌套字典），避免为每个小配置建一堆字段，又保持查询灵活性（SQLAlchemy 支持 JSON 查询）。  
- **软删除友好设计**：所有表都含 `status` 字段（如 `"active"/"draft"/"archived"`），配合 `index=True`，方便逻辑删除而不删数据，符合治理系统“留痕”刚需。  
- **时间戳全自动管理**：`created_at` 和 `updated_at` 全部用 `server_default=func.now()` 和 `onupdate=func.now()`，数据库自动填，程序员完全不用操心——就像智能水表，用水即记录，绝不漏抄。

## ⚠️ 需要注意的地方  
- **外键级联删除（`ondelete="CASCADE"`）要格外小心**：`PageElement` 表的 `page_object_id` 字段设置了级联删除，意味着“删掉一个页面，它下面所有元素、所有版本、所有健康检查记录……全被清空！”——开发时务必确认这是预期行为，否则可能误删大量关联数据。建议关键操作加二次确认或改用软删除。  
- **`JSON` 字段无法做传统 SQL 模糊查询**：虽然能存数组/对象，但想查“所有 risk_tags 包含 'dynamic-id' 的元素”，不能直接用 `WHERE risk_tags_json LIKE '%dynamic-id%'`（不可靠且慢），需用数据库特定 JSON 函数（如 PostgreSQL 的 `@>` 操作符），代码里要显式处理，否则查不到。  
- **`DateTime(timezone=True)` 依赖数据库时区支持**：`server_default=func.now()` 在不同数据库（SQLite/MySQL/PostgreSQL）行为可能不同，尤其 SQLite 默认不存时区。若部署环境时区配置不一致，可能导致 `created_at` 时间错乱（比如显示成 UTC 时间但前端按本地时区解析）。建议统一用 UTC 存储，应用层转换显示。  
- **`default=dict` / `default=list` 是陷阱！**：Python 中 `default=dict` 看似安全，但其实是**可变默认参数**——如果多个实例共享了同一个空字典对象，修改一个会意外影响另一个！正确写法应为 `default=lambda: {}` 或 `default_factory=dict`（SQLAlchemy 2.0+ 推荐）。当前代码存在潜在并发风险（虽概率低，但治理系统讲求严谨）。