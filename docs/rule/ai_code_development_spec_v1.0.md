# AI辅助开发代码规范 v1.0

**版本**：v1.0  
**适用范围**：AI 辅助开发场景（Codex / Agent / Copilot / 内部代码生成工具）  
**目标**：约束 AI 生成代码的目录结构、文件粒度、模块职责、变更边界和重构策略，避免项目逐步失控、目录架构混乱、单文件过大、耦合过深，降低持续重构成本。

---

# 1. 背景与目标

AI 辅助开发带来的常见问题包括：

- 目录结构不稳定，新增功能时随意创建文件和目录
- 单个文件不断膨胀，出现上千行代码
- 组件、服务、工具函数混杂在一起
- 相同逻辑重复出现在多个模块
- 接口层、业务层、数据层没有边界
- AI 为了“快完成”倾向于直接改现有大文件
- 命名风格不统一，导致长期维护困难
- 重构总是滞后发生，且代价越来越高

本规范的目标是：

- 让 AI 在固定架构下产出代码
- 控制单文件复杂度和模块职责
- 让新增功能优先扩展模块，而不是堆积代码
- 把“重构”前置为日常约束，而不是后期补救
- 为 Codex 提供可执行的开发边界

---

# 2. 核心原则

## 2.1 先有架构边界，再让 AI 写代码
AI 只能在既定目录和模块职责内生成代码，不允许自由扩展架构。

## 2.2 单文件不能承载多个层级职责
一个文件只能承载一个主要职责，不允许页面、业务编排、请求封装、数据转换、工具函数混写。

## 2.3 优先新增小模块，不优先扩写大文件
当现有文件已接近上限时，应拆分为新模块，而不是继续往原文件追加。

## 2.4 先拆边界，再写功能
新增功能前必须先判断属于哪一层、哪一模块、哪一目录。

## 2.5 AI 输出必须可审查、可替换、可测试
禁止生成“只能工作但难以理解”的拼接式代码。

---

# 3. 项目目录治理规范

## 3.1 顶层目录必须稳定

推荐顶层目录如下：

```text
src/
  app/                # 应用启动、路由装配、全局配置
  pages/              # 页面级模块
  modules/            # 领域业务模块
  components/         # 通用组件
  services/           # API 请求与后端交互
  stores/             # 状态管理
  hooks/              # 通用 hooks
  utils/              # 纯工具函数
  constants/          # 常量
  types/              # 类型定义
  schemas/            # 校验 schema
  tests/              # 单元/集成测试
  styles/             # 全局样式
```

规则：

- 顶层目录数量应稳定，不允许 AI 随意新增同义目录
- 禁止同时出现 `utils`, `helper`, `helpers`, `common-utils` 这类重复语义目录
- 禁止同时出现 `api`, `service`, `services`, `request` 多套并行网络层目录
- 新目录必须经过人工确认，不允许 AI 自由创建

---

## 3.2 页面与业务模块分离

### 页面目录 `pages/`
只负责：
- 路由页面入口
- 页面布局组织
- 页面级数据装配
- 页面生命周期协调

不负责：
- 复杂业务规则
- API 细节
- 大量数据转换
- 可复用组件实现

### 业务模块目录 `modules/`
只负责：
- 业务域内的能力封装
- 领域逻辑
- 业务编排
- 页面无关的业务规则

示例：

```text
src/
  pages/
    return-apply/
      index.tsx
      ReturnApplyPage.tsx
  modules/
    return-apply/
      services/
      model/
      components/
      utils/
      types/
```

规则：

- 页面文件不超过页面装配职责
- 可复用业务逻辑必须沉淀到 `modules/`
- 跨页面共用逻辑不得长期停留在 `pages/`

---

## 3.3 组件分层

组件分为三层：

### 1）页面私有组件
目录：
```text
pages/<page>/components/
```

适用于：
- 仅当前页面使用
- 强依赖当前页面布局和交互

### 2）业务模块组件
目录：
```text
modules/<domain>/components/
```

适用于：
- 同一业务域内多个页面共用
- 含有明确业务语义

### 3）全局通用组件
目录：
```text
components/
```

适用于：
- 不绑定具体业务
- 具有通用 UI 或交互能力

规则：

- 不允许把业务组件放入全局 `components/`
- 不允许把纯 UI 组件放进 `pages/`
- 组件必须按复用范围进入正确层级

---

# 4. 单文件规模与拆分规范

## 4.1 单文件行数上限

建议上限如下：

- 工具函数文件：**≤ 200 行**
- 普通 service 文件：**≤ 250 行**
- React/Vue 组件文件：**≤ 300 行**
- 页面入口文件：**≤ 200 行**
- 复杂模块编排文件：**≤ 350 行**
- 类型定义文件：**≤ 200 行**

强制规则：

- **超过 500 行必须拆分**
- **超过 800 行视为严重违规**
- **禁止出现 1000+ 行业务文件**

---

## 4.2 文件拆分触发条件

满足任一条件必须拆分：

- 文件超过行数阈值
- 一个文件出现多个导出主对象
- 同时包含 UI、请求、状态、转换逻辑
- 一个组件中出现 3 个以上弹窗/表单/列表子块
- 一个 service 文件同时负责 5 个以上业务动作
- 一个 hook 内承担页面级流程编排
- 文件修改频率过高，且多人频繁冲突

---

## 4.3 推荐拆分方式

### 页面组件拆分
把以下内容拆出去：

- 表单区块
- 列表区块
- 弹窗区块
- 过滤器区块
- 表格列配置
- 页面专用 hooks
- 页面专用 constants
- 页面专用 types

示例：

```text
pages/return-apply/
  index.tsx
  ReturnApplyPage.tsx
  components/
    ReturnApplyFilter.tsx
    ReturnApplyTable.tsx
    ReturnApplyDialog.tsx
  hooks/
    useReturnApplyPage.ts
  constants.ts
  types.ts
```

### service 拆分
把以下内容拆出去：

- 请求封装
- DTO 转换
- 业务编排
- mock 数据
- 错误处理映射

示例：

```text
modules/return-apply/services/
  returnApply.api.ts
  returnApply.mapper.ts
  returnApply.service.ts
  returnApply.mock.ts
```

---

# 5. 模块职责边界规范

## 5.1 分层职责

推荐分层如下：

### 1）表现层
负责：
- UI 渲染
- 用户交互
- 展示状态

目录示例：
- `pages/`
- `components/`

### 2）应用编排层
负责：
- 页面流程组织
- 调用业务能力
- 协调多个模块

目录示例：
- `pages/<page>/hooks`
- `modules/<domain>/orchestrators`

### 3）领域逻辑层
负责：
- 业务规则
- 状态转换
- 校验逻辑
- 场景决策

目录示例：
- `modules/<domain>/model`
- `modules/<domain>/domain`

### 4）基础设施层
负责：
- API 请求
- 存储访问
- 第三方 SDK 调用

目录示例：
- `services/`
- `modules/<domain>/services`

---

## 5.2 禁止跨层污染

禁止行为：

- 页面层直接写复杂请求拼装
- 组件内直接写业务规则判断树
- service 层直接操作 UI 状态
- utils 中写领域业务逻辑
- hook 中无限堆积页面编排 + API + 校验 + 提交流程

---

# 6. 命名规范

## 6.1 目录命名
- 使用小写短横线或统一约定
- 示例：`return-apply`, `order-center`
- 禁止混用：`returnApply`, `ReturnApply`, `return_apply`

## 6.2 文件命名
建议规则：

- 组件：`PascalCase.tsx`
- hook：`useXxx.ts`
- service：`xxx.service.ts`
- api：`xxx.api.ts`
- mapper：`xxx.mapper.ts`
- type：`xxx.types.ts`
- schema：`xxx.schema.ts`
- constant：`xxx.constants.ts`

示例：

```text
ReturnApplyPage.tsx
ReturnApplyTable.tsx
useReturnApplyPage.ts
returnApply.api.ts
returnApply.service.ts
returnApply.mapper.ts
returnApply.types.ts
returnApply.constants.ts
```

## 6.3 禁止命名
- `index2.ts`
- `finalService.ts`
- `newPage.tsx`
- `temp.ts`
- `testFix.ts`
- `common.ts`（语义不清）
- `utils.ts`（过大时禁止）
- `handleData.ts`（语义不清）

---

# 7. 函数与类设计规范

## 7.1 函数长度
建议：

- 普通函数 ≤ 50 行
- 复杂业务函数 ≤ 80 行
- 超过 80 行必须拆子函数

## 7.2 函数职责
一个函数只做一件主要事情，不允许同时：

- 参数清洗
- 业务判断
- 请求发送
- UI 提示
- 日志记录
- 路由跳转

## 7.3 参数控制
- 参数建议 ≤ 4 个
- 超过 4 个使用对象参数
- 禁止布尔参数过多，如 `fn(true, false, true)`

## 7.4 返回值规范
- 返回结构必须稳定
- service 返回统一 Result 对象或 DTO
- 不允许同一函数有时返回 `null`，有时返回对象，有时抛字符串

---

# 8. 状态管理规范

## 8.1 状态归属原则
先判断状态应该放哪：

- 页面短期状态：页面组件 / 页面 hook
- 业务域共享状态：模块 store
- 全局状态：全局 store

## 8.2 禁止
- 所有状态都堆进全局 store
- 页面专属状态进入全局 store
- 一个 store 管理多个无关领域
- store 中直接写大量副作用请求

---

# 9. Service / API 规范

## 9.1 API 层职责
只负责：
- 请求路径
- 请求方法
- 参数传递
- 响应接收

## 9.2 Service 层职责
只负责：
- 业务动作封装
- 多接口编排
- 数据转换协调
- 对上层提供语义化能力

## 9.3 Mapper 层职责
只负责：
- DTO -> ViewModel
- Form -> RequestPayload

## 9.4 禁止
- 页面直接调底层 request
- API 文件写业务判断
- Service 文件包含 UI toast
- Mapper 文件访问 store

---

# 10. Hook 规范

## 10.1 Hook 适用场景
- 复用页面逻辑
- 管理一组相关状态和行为
- 抽离副作用逻辑

## 10.2 禁止
- 一个 hook 管完整页面所有逻辑
- hook 内直接内嵌大段 JSX
- hook 内直接操作多个无关领域
- hook 变成隐藏 service 层

## 10.3 拆分建议
当 hook 过大时拆分为：

- `useReturnApplyFilter`
- `useReturnApplyTable`
- `useReturnApplySubmit`
- `useReturnApplyDialog`

---

# 11. Utils 规范

## 11.1 utils 的定义
utils 只能放：
- 纯函数
- 无副作用逻辑
- 不依赖页面、组件、store、路由的通用能力

## 11.2 禁止
- 把业务规则塞进 utils
- 把请求逻辑塞进 utils
- 把组件拼装逻辑塞进 utils

## 11.3 反模式
```text
utils/
  common.ts
  helper.ts
  business.ts
  formatAll.ts
```

这些通常意味着职责已经失控。

---

# 12. 测试与可测试性规范

## 12.1 可测试优先
代码应设计为便于测试：

- 纯逻辑尽量做成纯函数
- 业务规则不要深埋在组件内部
- 数据转换逻辑独立到 mapper
- service 可单独 mock

## 12.2 最低要求
- 关键业务函数必须可单测
- 核心 mapper 必须可单测
- 复杂表单/提交流程必须有集成测试

---

# 13. AI 开发专用约束

## 13.1 AI 允许做的事
- 在既有目录下新增文件
- 按模板补充模块
- 拆分超长文件
- 按职责迁移代码
- 补充类型、测试、注释

## 13.2 AI 禁止做的事
- 未经确认新增顶层目录
- 随意重命名核心目录
- 在现有大文件中无限追加代码
- 为了完成任务复制粘贴整段旧逻辑
- 跳过类型定义直接返回 any
- 把多个需求一起塞进同一个文件

## 13.3 AI 生成前必须判断
每次生成代码前，先回答：

1. 这个改动属于哪一层
2. 应该放到哪个目录
3. 是新增文件还是扩展现有文件
4. 是否会让现有文件超过阈值
5. 是否需要先拆分再实现

---

# 14. 重构触发机制

以下情况必须启动重构，而不是继续追加功能：

- 单文件 > 500 行
- 模块职责说不清
- 同类逻辑复制超过 2 处
- 页面文件同时管理列表、表单、弹窗、提交流程
- service 文件同时负责十几个动作
- store 包含多个业务域
- 新人 10 分钟内无法定位改动入口

---

# 15. Code Review 检查清单

每次提交至少检查以下问题：

- [ ] 是否新增了不必要目录
- [ ] 是否破坏现有分层
- [ ] 是否把业务逻辑写进了页面/组件
- [ ] 是否把请求写进了组件
- [ ] 是否产生超长文件
- [ ] 是否有重复逻辑可下沉
- [ ] 是否命名清晰
- [ ] 是否新增了类型定义
- [ ] 是否补充了必要测试
- [ ] 是否可以在 3 分钟内定位主要改动点

---

# 16. 推荐目录模板

## 16.1 前端业务模块模板

```text
src/
  modules/
    return-apply/
      components/
        ReturnApplyForm.tsx
        ReturnApplyTable.tsx
      hooks/
        useReturnApplySubmit.ts
        useReturnApplyFilter.ts
      services/
        returnApply.api.ts
        returnApply.service.ts
        returnApply.mapper.ts
      store/
        returnApply.store.ts
      types/
        returnApply.types.ts
      constants/
        returnApply.constants.ts
      utils/
        returnApplyFormat.ts
```

## 16.2 页面模板

```text
src/
  pages/
    return-apply/
      index.tsx
      ReturnApplyPage.tsx
      components/
        ReturnApplyHeader.tsx
        ReturnApplyToolbar.tsx
      hooks/
        useReturnApplyPage.ts
      types.ts
      constants.ts
```

---

# 17. 给 Codex 的执行提示词模板

```text
你是企业级工程代码助手。请严格遵守以下开发规范：

1. 不允许新增顶层目录。
2. 所有改动必须放入现有分层：pages / modules / components / services / hooks / utils / types。
3. 页面层只负责装配，不写复杂业务逻辑。
4. 业务逻辑放到 modules/<domain>/ 下。
5. API 请求放 api.ts，业务编排放 service.ts，数据转换放 mapper.ts。
6. 单文件超过 300 行时优先拆分，超过 500 行必须拆分。
7. 不允许生成 1000 行以上文件。
8. 不允许使用 temp.ts、common.ts、finalService.ts、newPage.tsx 这类低语义命名。
9. 不允许把多个职责塞进一个文件。
10. 新增功能前先判断该功能属于哪一层、哪一目录、哪个模块。
11. 如现有文件已经过大，先进行拆分，再实现新功能。
12. 输出代码时，优先给出新增/修改文件清单，并说明每个文件职责。
```

---

# 18. 最小落地 Checklist

- [ ] 冻结顶层目录结构
- [ ] 定义页面层/模块层/组件层/服务层职责
- [ ] 设定单文件行数阈值
- [ ] 设定命名规则
- [ ] 设定 AI 禁止行为
- [ ] 设定 Hook / Service / Mapper 规范
- [ ] 建立 Code Review 检查清单
- [ ] 建立“超过阈值必须拆分”机制
- [ ] 对历史超长文件建立拆分治理计划

---

# 19. 结论

避免 AI 把代码写乱的关键，不是“让它聪明一点”，而是：

- 先冻结目录结构
- 先冻结分层职责
- 先冻结文件粒度
- 先冻结命名方式
- 先冻结 AI 的改动边界

真正有效的企业级规范，必须让 AI 在受控边界里工作，而不是允许它自由发挥架构。

---

**文档结束**
