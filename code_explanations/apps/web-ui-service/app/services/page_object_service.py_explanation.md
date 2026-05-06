# 📘 代码说明书
## 一句话概括
这是一个为自动化测试“页面对象（Page Object）”提供全生命周期管理的后端服务模块，专门负责网页中可交互元素（如按钮、输入框）的创建、审核、归档、合并、删除等操作，并确保每个元素的定位方式（如 `data-testid`）、业务含义（如“登录按钮”）、稳定性等级（高/中/低）都符合质量规范。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `page_object_service.py` | 提供所有与“页面对象”和“页面元素”相关的数据库操作、数据校验、状态流转、日志记录和指标同步功能，是整个页面对象治理系统的“大脑” |

## 🔍 核心函数/类说明
- **`_normalize_xxx()` 系列函数（如 `_normalize_page_element_status`, `_normalize_locator_type`）**：作用是把用户传来的各种字符串（比如 `"ACTIVE"`、`"  XPATH  "`、`"DATA-TESTID"`）统一转成小写、去空格、校验是否合法，并在不合法时直接报错（如 HTTP 400）。  
  - 输入：原始字符串（可能带空格、大小写混用、拼写错误）  
  - 输出：标准化后的合法字符串（如 `"active"`、`"xpath"`、`"data-testid"`）  
  - 大白话解释：就像收快递时，快递员不会因为单子上写了“北京市朝阳区建国路81号（隔壁楼）”就拒收——他会先“标准化”地址（查地图、问门牌），如果发现根本没这地方，才打电话告诉你填错了。这些函数就是干这个“智能纠错+标准化”的活。

- **`_validate_formal_element_governance_qualification()`**：作用是检查一个已批准（`approved`）的页面元素是否真的“够格”被批准——比如高稳定性的元素必须用 `data-testid` 定位，且必须填上 `testid_value`；中稳定性元素如果用 `id` 定位，就不能乱写成 `css`。  
  - 输入：一个 `PageElement` 数据库对象  
  - 输出：无（校验失败就抛出 HTTP 400 错误）  
  - 大白话解释：就像公司给员工发“高级工程师”职称，不能只看工龄，还得看有没有通过架构师考试、有没有主导过核心项目。这个函数就是 HR 的“职称评审委员会”，严格把关谁有资格挂“approved”标签。

- **`_purge_duplicate_page_elements()`**：作用是自动清理同一个页面里重复的页面元素（比如两个元素都叫 `login_btn` 且定位方式完全一样），只保留最新修改的那个，其余全部删掉。  
  - 输入：数据库会话 `db` 和页面 ID  
  - 输出：一个字典，含“保留几个”“删了几个”等统计信息  
  - 大白话解释：就像整理衣柜，发现两件一模一样的 T 恤（同品牌、同颜色、同尺码、同洗标），只留最新买/最新洗的那件，另一件直接捐掉——避免以后改样式时改漏一个。

- **`promote_candidate_group()`**：作用是把一组被 AI 或人工发现的“候选元素”（比如录制脚本时抓到的 5 个相似的搜索框），正式升级为一个标准页面元素（如 `search_input`），并写入主表、生成版本快照、更新关联日志。  
  - 输入：候选分组 ID、新元素名、定位方式、业务类型等  
  - 输出：包含新元素详情和分组更新结果的字典  
  - 大白话解释：就像选秀节目，海选阶段一堆候选人（candidate），评委（这里是测试工程师）挑出最稳的一个，给他发正式工牌（`PageElement`）、签劳动合同（`PageElementVersion`）、记入公司花名册（`governance_log`）。

- **`merge_candidate_group()`**：作用是把一组候选元素“合并”进一个已有的页面元素（比如已有 `header_logo` 元素），给它新增备用定位器（比如原来用 `id="logo"`，现在加一个 `css=".header-logo"` 作为备胎），增强鲁棒性。  
  - 输入：目标元素编码、候选分组 ID、是否写入新定位器等  
  - 输出：目标元素更新后详情 + 新增定位器数量  
  - 大白话解释：就像给汽车加装备用轮胎——主轮胎（原定位器）还在用，但多备一个不同品牌/尺寸的（新 locator），万一主胎爆了，立刻换上不耽误赶路。

- **`_sync_page_object_metrics()`**：作用是每次增删改元素后，自动刷新所属页面对象的统计数字：总元素数、已批准数、关键元素数、待审核候选数、健康状态（是否有坏元素）等。  
  - 输入：数据库会话 `db` 和页面 ID  
  - 输出：无（直接更新数据库里的 `PageObject` 记录）  
  - 大白话解释：就像微信运动，你每走一步，手机后台默默算好“今日步数”“排名”“距离好友还差多少”，不用你手动点“刷新”。这个函数就是页面对象的“健康手环”。

- **`PageElementMutationResult`（dataclass）**：作用是封装“元素变更操作”的结果，固定携带两个字段：变更后的元素对象 + 当前最新版本号。  
  - 输入：无（只是个容器）  
  - 输出：一个不可变的数据包（`frozen=True`）  
  - 大白话解释：就像外卖小哥送餐后，给你一张带二维码的小票——上面只有两样东西：① 你点的那份饭（`element`），② 这单的订单号（`latest_version_no`）。清晰、不可涂改、方便溯源。

## 🧩 调用关系与数据流转
```
外部请求（FastAPI路由） 
    ↓
list_page_objects / get_page_object / create_page_element / promote_candidate_group 等入口函数 
    ↓（调用校验 & 查询）
_normalize_xxx() → _page_object_or_404() → _page_element_or_404() → _candidate_group_or_404() 
    ↓（执行核心逻辑）
→ _validate_formal_element_governance_qualification()（审核前把关）  
→ _snapshot_element()（保存新版本）  
→ _write_governance_log()（记操作日志）  
→ _sync_page_object_metrics()（刷新页面统计）  
→ _purge_duplicate_page_elements()（清理重复项）  
→ _cleanup_page_recorder_assets()（删录制产生的临时文件）  
    ↓（序列化返回）
_serialize_page_object() / _serialize_page_element() / _serialize_candidate_group() 等  
    ↓
返回给前端的 JSON 数据
```
💡 关键流转特点：  
- 所有“写操作”（create/update/promote/merge）最后都会触发 `_sync_page_object_metrics()`，确保页面统计永远最新；  
- 所有“涉及元素状态变更”的操作（尤其是 `approved`），必过 `_validate_formal_element_governance_qualification()` 这道质检关；  
- 日志（`governance_log`）不是可选功能，而是强制记录“谁、什么时候、对什么、做了什么、前后值是什么”，像行车记录仪。

## 💡 值得学习的写法
- **“防御式标准化”模式**：每个 `_normalize_xxx()` 函数都做三件事：① 强制转小写+去空格；② 检查是否在预设白名单里；③ 不合法就立刻 `raise HTTPException`。不返回 `None` 或默认值，杜绝“静默失败”，让错误暴露在最前端。
- **“事务内分阶段提交”技巧**：比如 `promote_candidate_group()` 中，先 `db.flush()` 把新元素写入 DB 获取 ID，再用该 ID 创建关联的 `PageElementVersion` 和 `PageElementLocator`，最后 `db.commit()`。避免因外键 ID 未生成导致插入失败。
- **“语义化枚举常量”集中管理**：所有状态值（如 `PAGE_OBJECT_STATUS_VALUES`）都定义为 `set` 常量，而非散落在 if 判断里。既防拼写错误，又方便全局搜索替换，还让校验逻辑一目了然。
- **“空值安全序列化”工具链**：`_json_dict()` / `_json_list()` / `_json_safe()` 三个函数组成小工具包，自动处理 `None`、`datetime`、嵌套结构，让数据库模型转 JSON 时永不崩溃，比手动 `.dict()` 更健壮。
- **“双保险去重”设计**：`batch_delete_page_elements()` 先用 `_unique_non_empty()` 去重输入列表，再用 SQL `IN` 子句查库确认存在性，最后只删库里真实存在的——防止因传入重复 ID 导致误删或 SQL 报错。

## ⚠️ 需要注意的地方
- **`_normalize_identifier()` 对 `page_code` 和 `element_code` 的长度限制不同**：`page_code` 最大 40 字符（见 `get_page_object` 调用），但 `element_code` 在 `_normalize_formal_element_code()` 里由 `require_valid_element_code()` 控制（代码未贴出，但通常更严）。若前端传超长 `element_code`，错误提示会指向 `page_code` 校验，容易误导排查方向。
- **`_purge_duplicate_page_elements()` 的“role”逻辑易被忽略**：当多个元素 `locator_type="role"` 且 `locator_value` 相同时，它会根据 `role` 值的有无决定保留哪个——如果第一个元素 `role=""`，第二个 `role="search"`，它会删第一个。但业务上可能认为 `role=""` 更通用，需确认此策略是否符合团队约定。
- **`promote_candidate_group()` 中 `testid_value`/`qa_value` 的自动填充有陷阱**：当 `locator_type="data-testid"` 但用户没填 `testid_value` 时，代码会自动把 `locator_value` 当作 `testid_value` 填进去。但如果 `locator_value` 是动态的（如 `search-btn-${timestamp}`），会导致 `testid_value` 也变成动态值，违反 `data-testid` 应该静态不变的原则。
- **`_stability_from_locator_source()` 的“medium”判定缺少 fallback**：当 `locator_source` 是 `"manual"` 时，函数直接返回 `"low"`，但实际人工写的 `css` 或 `xpath` 可能很稳定。这里硬编码为 low，可能低估人工维护定位器的质量。
- **`delete_page_object(..., cascade_elements=False)` 的冲突提示不友好**：当用户忘记加 `cascade_elements=true` 时，报错是 `page object still has X element(s); set cascade_elements=true to delete`，但没告诉用户“怎么加”——前端调用者可能不知道 FastAPI 的 Query 参数如何传布尔值（需传 `cascade_elements=1` 或 `cascade_elements=true` 字符串，后端才能解析为 `True`）。