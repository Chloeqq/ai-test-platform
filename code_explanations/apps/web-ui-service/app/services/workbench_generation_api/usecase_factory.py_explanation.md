# 📘 代码说明书
## 一句话概括  
这个文件就像一个“智能餐厅的点单调度员”，它不直接做菜（不处理业务逻辑），而是根据客人（API接口）的需求，快速搭配好厨师、食材和工具（服务类 + 上下文），把准备好的“套餐”（服务实例）递出去。

## 📂 文件总览
| 文件 | 作用 |
|------|------|
| `usecase_factory.py` | 负责“组装并交付”各种业务服务对象（比如生成测试用例、跑完整流程等），每次调用都创建一个**干净、带数据库连接的新服务实例**，确保各任务互不干扰。 |

## 🔍 核心函数/类说明
- **`build_generate_case_usecase(db: Session) -> GenerateCaseService`**：  
  - 输入：一个 SQLAlchemy 的数据库会话 `db`（可以理解成“一把专属的数据库钥匙”）  
  - 输出：一个配置好上下文的 `GenerateCaseService` 实例（即“能生成测试用例的专用小助手”）  
  - 大白话解释：当你想让系统帮你**自动生成一条测试用例**时，就找它要一个“生成小助手”。它会先用数据库钥匙配好工作环境（`build_workbench_context(db)`），再把这个环境塞进 `GenerateCaseService` 里，打包交给你——就像奶茶店员按你的要求（少冰、三分糖）现做一杯，而不是端出隔夜的。  

- **`build_full_chain_usecase(db: Session) -> FullChainService`**：  
  - 输入：数据库钥匙 `db`  
  - 输出：一个 `FullChainService` 实例（“能跑完整测试链路的高级管家”）  
  - 大白话解释：当你想**从头到尾走一遍完整流程**（比如：选意图 → 生成用例 → 运行 → 存结果），就找它要一个“管家”。它会先配好工作环境，再用这个环境造出一个“流水线”（`FullChainPipeline`），最后把流水线交给管家（`FullChainService`）来统一调度——就像组装好一条乐高传送带，再配上一个遥控器。  

- **`build_auto_run_usecase(db: Session) -> AutoRunService`**：  
  - 输入：数据库钥匙 `db`  
  - 输出：一个 `AutoRunService` 实例（“一键自动运行的小能手”）  
  - 大白话解释：当你想**跳过中间步骤，直接让系统跑起来**（比如自动执行已有的测试点），就找它要一个“小能手”。它同样先配好环境，再把环境交给 `AutoRunService`——就像给扫地机器人装上电量满格的电池和地图，一按开关就干活。  

- **`build_precheck_selected_intents_usecase(db: Session) -> PrecheckSelectedIntentsService`**：  
  - 输入：数据库钥匙 `db`  
  - 输出：一个 `PrecheckSelectedIntentsService` 实例（“意图预检小哨兵”）  
  - 大白话解释：当你在界面上勾选了一堆用户意图（比如“登录”“搜索”“下单”），但不确定它们是否合法/可执行，就找它当“哨兵”提前检查——它会拿着数据库钥匙去查证，再返回检查结果。  

- **`build_save_test_point_assets_usecase(db: Session) -> SaveTestPointAssetsService`**：  
  - 输入：数据库钥匙 `db`  
  - 输出：一个 `SaveTestPointAssetsService` 实例（“测试资产收纳员”）  
  - 大白话解释：当你生成了测试点、脚本、数据等“资产”，需要**安全存进数据库**，就找它来收纳整理——它负责把东西分类、贴标签、锁进数据库保险柜。  

## 🧩 调用关系与数据流转  
```
外部调用（如 FastAPI 路由）
        ↓
usecase_factory 中的 build_xxx_usecase() 函数  
        ↓ 每次都调用 → build_workbench_context(db)  
        ↓ 得到统一的工作环境（含数据库连接、配置、工具等）  
        ↙         ↘             ↘              ↘               ↘  
GenerateCaseService   FullChainPipeline   AutoRunService   Precheck...Service   SaveTestPointAssetsService  
（接收环境，专注生成） （接收环境，组装流水线）（接收环境，专注运行）（接收环境，专注校验） （接收环境，专注保存）
```
✅ 数据流转核心：**所有服务都共享同一套“工作环境”（context），而这个环境每次都用同一个 `db` 新建，保证每次请求独立、线程安全、无状态污染。**

## 💡 值得学习的写法
- ✅ **工厂函数命名清晰直白**：`build_xxx_usecase` 让人一眼看懂这是“构建某个用例的服务”，比 `get_xxx_service` 或 `create_xxx` 更贴近业务语义。  
- ✅ **复用 `build_workbench_context(db)`**：避免每个函数重复写初始化逻辑，像“统一发工牌+工位+电脑”，既省事又保证所有人用同一套装备。  
- ✅ **返回具体服务类（而非抽象基类）**：调用方拿到的就是能直接 `.run()` 或 `.generate()` 的实例，不用再二次初始化，符合“开箱即用”原则。  
- ✅ **类型提示精准**：`-> GenerateCaseService` 明确告诉 IDE 和开发者“你拿到的是什么”，大幅提升可读性和自动补全体验。

## ⚠️ 需要注意的地方
- ⚠️ **`db: Session` 必须是“新鲜”的**：如果传入的是已被提交/关闭/复用的 session（比如从上层路由里直接传了个用过的 `db`），会导致后续操作报错或数据混乱——就像拿一把断齿的钥匙去开门，打不开还可能卡住锁芯。✅ 正确做法：FastAPI 依赖注入中应确保每次请求新建一个 `Session`。  
- ⚠️ **没有错误兜底**：这些函数假设 `build_workbench_context(db)` 总能成功。如果数据库连不上、配置缺失，会直接抛异常中断，前端看到 500。💡 建议后续可在工厂函数内加简单日志或包装 try/except（视项目稳定性要求而定）。  
- ⚠️ **容易误以为“服务是单例”**：名字叫 `build_xxx_usecase`，但它是每次调用都新建实例（不是全局共享），这点对初学者容易误解——它不是“造一个永久工牌”，而是“每次来人都发一张新工牌”。