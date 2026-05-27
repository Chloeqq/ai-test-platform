# 测试用例命名规范 v1.0

**文档版本**：v1.0  
**适用范围**：AI 自动化测试平台 / 测试用例管理平台 / 自动化测试资产管理  
**目标**：统一测试用例命名、编码、结构化字段和生成规则，提升测试资产的可读性、可检索性、可维护性和可统计性。

---

## 1. 背景与目标

当前测试用例命名存在以下问题：

- 用例 ID 无法体现所属页面、模块和测试目标
- 无法区分冒烟、回归、功能、异常等测试类型
- 无法区分 AI 生成、人工编写、人工复核等来源
- 命名自由度过高，导致风格不统一、难以批量检索
- 用例数量增长后，维护成本和分析成本显著增加

本规范旨在建立统一的测试用例标识规则，并约束 AI 与人工录入行为，使测试资产满足以下要求：

- **唯一**：每条用例有唯一标识
- **可读**：一眼可判断所属系统、页面、模块、类型、来源
- **可筛选**：支持按页面、模块、类型、来源、优先级等维度检索
- **可扩展**：支持新增页面、模块、业务线
- **可自动化**：便于 AI 生成、平台校验和批量迁移

---

## 2. 设计原则

### 2.1 Case ID 不承载全部信息

Case ID 用于唯一标识和分类索引，不承载过细的业务语义。

### 2.2 用例标题负责表达“测试什么”

具体测试条件、操作步骤和预期结果应主要体现在标题与结构化字段中，而不是全部挤进 ID。

### 2.3 AI 只能在受控字典内生成

页面编码、模块编码、测试类型、来源类型必须从预定义字典中选择，不允许自由造词。

### 2.4 平台必须具备强校验

仅靠提示词不足以保障长期规范，平台必须通过正则、字典和唯一性规则进行入库校验。

---

## 3. 测试用例标识规范

### 3.1 Case ID 格式

统一格式如下：

```text
[项目]-[端]-[页面]-[模块]-[类型]-[来源]-[序号]
```

示例：

```text
ATP-WEB-RET-ORD-SM-AI-0001
ATP-WEB-RET-SUBM-RG-MN-0002
ATP-API-REF-CALC-RG-AI-0003
ATP-WEB-LOGIN-AUTH-SM-CV-0001
```

### 3.2 字段说明

#### 3.2.1 项目（Project）

用于标识所属系统或项目。

示例：

- `ATP` = AI Test Platform
- `OMS` = Order Management System
- `CRM` = Customer Relationship Management

规范要求：

- 全大写英文或数字
- 长度建议 2 到 10 位
- 项目编码一旦确定，不应频繁修改

#### 3.2.2 端（Client）

用于标识测试对象所属端或入口。

枚举建议：

- `WEB` = Web端
- `APP` = App端
- `API` = 接口层
- `ADMIN` = 管理后台
- `H5` = H5页面

#### 3.2.3 页面（Page）

用于标识所属页面或业务域页面。

规范要求：

- 采用固定编码字典
- 建议使用 3 到 8 位全大写英文字母
- 同一页面仅允许一个标准编码

示例：

- `LOGIN` = 登录页
- `HOME` = 首页
- `RET` = 退货申请页
- `REF` = 退款页
- `ORD` = 订单页

#### 3.2.4 模块（Module）

用于标识页面下的功能模块。

规范要求：

- 采用固定编码字典
- 建议使用 3 到 8 位全大写英文字母
- 模块编码必须具有明确业务含义

示例：

- `AUTH` = 登录认证
- `ORD` = 订单查询
- `SUBM` = 提交申请
- `UPLD` = 图片上传
- `LIST` = 列表展示
- `DETAIL` = 详情展示

#### 3.2.5 类型（Case Type）

用于标识测试分类。

建议枚举：

- `SM` = 冒烟测试
- `RG` = 回归测试
- `FN` = 功能测试
- `EX` = 异常测试
- `INT` = 集成测试
- `E2E` = 端到端测试

对于初期落地，建议先使用以下 4 类：

- `SM`
- `RG`
- `FN`
- `EX`

#### 3.2.6 来源（Source）

用于标识测试用例的产出来源。

建议枚举：

- `AI` = AI 自动生成
- `MN` = 人工编写
- `CV` = AI 生成后人工复核
- `IMP` = 历史迁移导入

#### 3.2.7 序号（Sequence）

用于保证同一分类下的唯一性。

规范要求：

- 固定 4 位数字，如 `0001`
- 按同一项目 + 端 + 页面 + 模块 + 类型 + 来源维度递增
- 不允许跳号回收
- 删除用例后序号不复用

---

## 4. 用例标题命名规范

### 4.1 标题格式

统一格式如下：

```text
[页面名称]-[模块名称]-[测试条件]-[操作]-[预期结果]
```

示例：

```text
退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息
退货申请页-提交申请-必填项完整-点击提交-提交成功
登录页-登录认证-输入错误密码-点击登录-提示账号或密码错误
退款页-金额计算-退款金额超过订单金额-提交申请-提示金额非法
```

### 4.2 标题规范要求

- 使用中文描述，方便业务和测试人员理解
- 至少包含“页面、模块、条件、操作、预期”五段中的四段以上
- 不允许标题过短，如“退货申请测试”
- 不允许标题与 ID 重复编码化，如 `RET-ORD-EX-AI-0001`
- 标题必须体现本条用例验证的核心场景

---

## 5. 结构化字段规范

建议每条测试用例至少包含以下字段：

```json
{
  "case_id": "ATP-WEB-RET-ORD-SM-AI-0001",
  "case_title": "退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
  "project": "ATP",
  "client": "WEB",
  "page_code": "RET",
  "page_name": "退货申请页",
  "module_code": "ORD",
  "module_name": "订单查询",
  "case_type": "SM",
  "case_type_name": "冒烟测试",
  "source": "AI",
  "source_name": "AI自动生成",
  "priority": "P1",
  "status": "Ready",
  "precondition": [
    "用户已登录系统",
    "用户存在可退货订单"
  ],
  "steps": [
    "进入退货申请页",
    "输入有效订单号",
    "点击查询按钮"
  ],
  "expected_result": [
    "系统展示订单信息",
    "订单状态允许申请退货"
  ],
  "tags": [
    "smoke",
    "ai_generated",
    "return_apply",
    "order_query"
  ],
  "created_by": "AI",
  "reviewer": "",
  "automation_level": "UI"
}
```

---

## 6. 编码字典模板

建议在平台侧维护标准字典，AI 生成时只能从字典中选择。

### 6.1 页面编码字典模板

```json
[
  { "page_code": "LOGIN", "page_name": "登录页", "biz_domain": "USER", "enabled": true },
  { "page_code": "HOME", "page_name": "首页", "biz_domain": "COMMON", "enabled": true },
  { "page_code": "RET", "page_name": "退货申请页", "biz_domain": "AFTERSALE", "enabled": true },
  { "page_code": "REF", "page_name": "退款页", "biz_domain": "AFTERSALE", "enabled": true },
  { "page_code": "ORD", "page_name": "订单页", "biz_domain": "ORDER", "enabled": true }
]
```

### 6.2 模块编码字典模板

```json
[
  { "module_code": "AUTH", "module_name": "登录认证", "enabled": true },
  { "module_code": "ORD", "module_name": "订单查询", "enabled": true },
  { "module_code": "SUBM", "module_name": "提交申请", "enabled": true },
  { "module_code": "UPLD", "module_name": "图片上传", "enabled": true },
  { "module_code": "LIST", "module_name": "列表展示", "enabled": true },
  { "module_code": "DETAIL", "module_name": "详情展示", "enabled": true },
  { "module_code": "CALC", "module_name": "金额计算", "enabled": true }
]
```

### 6.3 类型字典模板

```json
[
  { "case_type": "SM", "case_type_name": "冒烟测试", "enabled": true },
  { "case_type": "RG", "case_type_name": "回归测试", "enabled": true },
  { "case_type": "FN", "case_type_name": "功能测试", "enabled": true },
  { "case_type": "EX", "case_type_name": "异常测试", "enabled": true },
  { "case_type": "INT", "case_type_name": "集成测试", "enabled": true },
  { "case_type": "E2E", "case_type_name": "端到端测试", "enabled": true }
]
```

### 6.4 来源字典模板

```json
[
  { "source": "AI", "source_name": "AI自动生成", "enabled": true },
  { "source": "MN", "source_name": "人工编写", "enabled": true },
  { "source": "CV", "source_name": "AI生成后人工复核", "enabled": true },
  { "source": "IMP", "source_name": "历史迁移导入", "enabled": true }
]
```

---

## 7. 正则校验规则

### 7.1 Case ID 格式正则

推荐基础正则：

```regex
^[A-Z0-9]+-(WEB|APP|API|ADMIN|H5)-[A-Z0-9]+-[A-Z0-9]+-(SM|RG|FN|EX|INT|E2E)-(AI|MN|CV|IMP)-\d{4}$
```

说明：

- 适用于格式层面的合法性校验
- 不能替代字典校验
- 平台需结合页面字典、模块字典做二次校验

### 7.2 标题格式校验建议

标题不建议只靠正则做强约束，但可做基础校验：

#### 最少段数校验

以 `-` 分隔后，段数不少于 4 段。

#### 长度校验

- 最小长度建议 >= 12
- 最大长度建议 <= 100

#### 禁止项校验

禁止标题仅为编码拼接，如：

- `RET-ORD-SM-AI-0001`
- `returnapply-returnapply-001`

### 7.3 平台强校验建议

除正则外，还应增加以下规则：

#### 规则 1：页面编码必须命中字典

`page_code` 必须存在于页面字典中。

#### 规则 2：模块编码必须命中字典

`module_code` 必须存在于模块字典中。

#### 规则 3：页面码与模块码禁止无意义重复

例如：

- `RET-RET`
- `LOGIN-LOGIN`

若页面和模块确实业务上同名，应通过更精确的模块字典命名解决，如页面 `RET`、模块 `SUBM`。

#### 规则 4：序号必须在分组内唯一

唯一键建议为：

```text
project + client + page_code + module_code + case_type + source + sequence
```

#### 规则 5：标题不能为空且需满足段数要求

#### 规则 6：创建来源与来源字段保持一致

例如 AI 生成时，`source` 默认应为 `AI` 或 `CV`，不可误写为 `MN`。

---

## 8. AI 生成提示词模板

以下模板可直接放入 Codex、Agent 或测试用例生成链路中。

```text
你是企业级测试用例生成助手。请严格按照以下规则生成测试用例，不允许自由发挥命名格式。

一、Case ID 格式
[项目]-[端]-[页面]-[模块]-[类型]-[来源]-[四位序号]

示例：
ATP-WEB-RET-ORD-SM-AI-0001

二、字段定义
1. 项目：
- ATP = AI Test Platform

2. 端：
- WEB / APP / API / ADMIN / H5

3. 页面编码（必须从以下字典中选）：
- LOGIN = 登录页
- HOME = 首页
- RET = 退货申请页
- ORD = 订单页
- REF = 退款页

4. 模块编码（必须从以下字典中选）：
- AUTH = 登录认证
- ORD = 订单查询
- SUBM = 提交申请
- UPLD = 图片上传
- LIST = 列表展示
- DETAIL = 详情展示
- CALC = 金额计算

5. 用例类型：
- SM = 冒烟
- RG = 回归
- FN = 功能
- EX = 异常
- INT = 集成
- E2E = 端到端

6. 来源：
- AI = AI生成
- MN = 人工编写
- CV = AI生成后人工复核
- IMP = 历史迁移导入

三、标题格式
[页面名称]-[模块名称]-[测试条件]-[操作]-[预期结果]

示例：
退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息

四、输出要求
每条测试用例必须包含以下字段：
- case_id
- case_title
- project
- client
- page_code
- page_name
- module_code
- module_name
- case_type
- source
- priority
- precondition
- steps
- expected_result
- tags

五、命名约束
- page_code 和 module_code 必须来自给定字典
- 不允许 page 和 module 无意义重复，如 RET-RET
- case_id 中不得出现中文、空格、特殊字符
- 不允许使用 returnapply-returnapply-001 这类无层次命名
- “测试什么”主要写在 case_title 中
- case_id 只负责唯一标识和分类索引
- 同一页面同一模块同一类型同一来源下序号递增

六、输出格式
请严格输出 JSON 数组，不要输出说明文字。
```

---

## 9. 旧用例迁移方案

对于已存在的历史用例，需要进行标准化迁移。建议采用“分阶段清洗”方式。

### 9.1 迁移目标

将历史用例统一补齐以下信息：

- 标准 `case_id`
- 标准 `case_title`
- 页面编码
- 模块编码
- 测试类型
- 来源类型
- 标签
- 优先级
- 状态

### 9.2 迁移原则

#### 原则 1：旧 ID 不直接删除

保留 `legacy_case_id` 字段，避免历史链路丢失。

示例：

```json
{
  "legacy_case_id": "returnapply-returnapply-001",
  "case_id": "ATP-WEB-RET-ORD-SM-IMP-0001"
}
```

#### 原则 2：无法自动识别的条目进入人工待确认池

对页面、模块、类型无法确定的历史用例，标记为 `NEED_REVIEW`。

#### 原则 3：迁移来源统一标记为 `IMP`

历史批量导入统一使用 `source=IMP`，避免与实时 AI 生成或人工新建混淆。

### 9.3 迁移步骤

#### 第一步：抽取历史用例

导出现有平台中的：

- 用例 ID
- 用例名称
- 用例描述
- 创建时间
- 创建人
- 所属页面
- 所属目录
- 标签

#### 第二步：建立映射表

建立以下映射关系：

- 旧页面名 -> 新 `page_code`
- 旧模块名 -> 新 `module_code`
- 旧标签 -> 新 `case_type`
- 旧创建方式 -> 新 `source`

示例：

```json
[
  {
    "legacy_keyword": "returnapply",
    "page_code": "RET",
    "page_name": "退货申请页"
  },
  {
    "legacy_keyword": "upload",
    "module_code": "UPLD",
    "module_name": "图片上传"
  }
]
```

#### 第三步：规则识别

利用关键词、目录、标签、描述文本自动推断：

- 页面
- 模块
- 类型
- 来源

#### 第四步：生成新 ID

按规范生成：

```text
ATP-WEB-RET-ORD-SM-IMP-0001
```

#### 第五步：人工审核灰区数据

以下情况必须进入人工复核池：

- 页面和模块冲突
- 页面无法识别
- 同一旧用例匹配多个模块
- 标题缺失或过于模糊
- 类型无法判断

#### 第六步：双写过渡

平台迁移初期建议同时展示：

- 新 `case_id`
- 旧 `legacy_case_id`

过渡期建议保留 1 到 3 个月。

### 9.4 迁移字段建议

```json
{
  "legacy_case_id": "returnapply-returnapply-001",
  "legacy_case_title": "退货申请测试",
  "case_id": "ATP-WEB-RET-ORD-SM-IMP-0001",
  "case_title": "退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
  "migration_status": "MIGRATED",
  "migration_remark": ""
}
```

对于无法自动识别的情况：

```json
{
  "legacy_case_id": "case-123",
  "legacy_case_title": "测试退款",
  "migration_status": "NEED_REVIEW",
  "migration_remark": "无法识别模块编码"
}
```

---

## 10. MySQL 表结构设计

### 10.1 测试用例主表 `test_case`

```sql
CREATE TABLE `test_case` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `case_id` VARCHAR(64) NOT NULL COMMENT '标准用例ID，如 ATP-WEB-RET-ORD-SM-AI-0001',
  `legacy_case_id` VARCHAR(128) DEFAULT NULL COMMENT '历史用例ID，如 returnapply-returnapply-001',
  `case_title` VARCHAR(255) NOT NULL COMMENT '用例标题',
  `project_code` VARCHAR(32) NOT NULL COMMENT '项目编码，如 ATP',
  `client_code` VARCHAR(16) NOT NULL COMMENT '端编码，如 WEB/API/APP',
  `page_code` VARCHAR(32) NOT NULL COMMENT '页面编码',
  `page_name` VARCHAR(64) NOT NULL COMMENT '页面名称',
  `module_code` VARCHAR(32) NOT NULL COMMENT '模块编码',
  `module_name` VARCHAR(64) NOT NULL COMMENT '模块名称',
  `case_type_code` VARCHAR(16) NOT NULL COMMENT '用例类型，如 SM/RG/FN/EX',
  `case_type_name` VARCHAR(32) NOT NULL COMMENT '用例类型名称',
  `source_code` VARCHAR(16) NOT NULL COMMENT '来源编码，如 AI/MN/CV/IMP',
  `source_name` VARCHAR(64) NOT NULL COMMENT '来源名称',
  `priority` VARCHAR(8) NOT NULL DEFAULT 'P2' COMMENT '优先级 P0/P1/P2/P3',
  `status` VARCHAR(16) NOT NULL DEFAULT 'Draft' COMMENT '状态 Draft/Ready/Review/Deprecated',
  `automation_level` VARCHAR(16) DEFAULT 'UI' COMMENT '自动化层级 UI/API/E2E/UNIT',
  `precondition_json` JSON DEFAULT NULL COMMENT '前置条件JSON数组',
  `steps_json` JSON DEFAULT NULL COMMENT '步骤JSON数组',
  `expected_result_json` JSON DEFAULT NULL COMMENT '预期结果JSON数组',
  `tags_json` JSON DEFAULT NULL COMMENT '标签JSON数组',
  `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人或创建来源',
  `reviewer` VARCHAR(64) DEFAULT NULL COMMENT '审核人',
  `migration_status` VARCHAR(32) DEFAULT NULL COMMENT '迁移状态 MIGRATED/NEED_REVIEW',
  `migration_remark` VARCHAR(255) DEFAULT NULL COMMENT '迁移备注',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记 0否1是',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_case_id` (`case_id`),
  KEY `idx_project_client_page_module` (`project_code`, `client_code`, `page_code`, `module_code`),
  KEY `idx_case_type_source` (`case_type_code`, `source_code`),
  KEY `idx_priority_status` (`priority`, `status`),
  KEY `idx_legacy_case_id` (`legacy_case_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试用例主表';
```

### 10.2 页面字典表 `dict_page`

```sql
CREATE TABLE `dict_page` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `project_code` VARCHAR(32) NOT NULL COMMENT '项目编码',
  `page_code` VARCHAR(32) NOT NULL COMMENT '页面编码',
  `page_name` VARCHAR(64) NOT NULL COMMENT '页面名称',
  `biz_domain` VARCHAR(32) DEFAULT NULL COMMENT '业务域，如 AFTERSALE/ORDER/USER',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用 1是0否',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_project_page_code` (`project_code`, `page_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='页面字典表';
```

### 10.3 模块字典表 `dict_module`

```sql
CREATE TABLE `dict_module` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `project_code` VARCHAR(32) NOT NULL COMMENT '项目编码',
  `page_code` VARCHAR(32) NOT NULL COMMENT '所属页面编码',
  `module_code` VARCHAR(32) NOT NULL COMMENT '模块编码',
  `module_name` VARCHAR(64) NOT NULL COMMENT '模块名称',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用 1是0否',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_project_page_module_code` (`project_code`, `page_code`, `module_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模块字典表';
```

### 10.4 类型字典表 `dict_case_type`

```sql
CREATE TABLE `dict_case_type` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `case_type_code` VARCHAR(16) NOT NULL COMMENT '类型编码',
  `case_type_name` VARCHAR(32) NOT NULL COMMENT '类型名称',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_case_type_code` (`case_type_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试类型字典表';
```

### 10.5 来源字典表 `dict_case_source`

```sql
CREATE TABLE `dict_case_source` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `source_code` VARCHAR(16) NOT NULL COMMENT '来源编码',
  `source_name` VARCHAR(64) NOT NULL COMMENT '来源名称',
  `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_source_code` (`source_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试来源字典表';
```

---

## 11. 初始化字典 SQL

### 11.1 页面字典

```sql
INSERT INTO `dict_page` (`project_code`, `page_code`, `page_name`, `biz_domain`, `enabled`, `sort_order`) VALUES
('ATP', 'LOGIN', '登录页', 'USER', 1, 1),
('ATP', 'HOME', '首页', 'COMMON', 1, 2),
('ATP', 'RET', '退货申请页', 'AFTERSALE', 1, 3),
('ATP', 'REF', '退款页', 'AFTERSALE', 1, 4),
('ATP', 'ORD', '订单页', 'ORDER', 1, 5);
```

### 11.2 模块字典

```sql
INSERT INTO `dict_module` (`project_code`, `page_code`, `module_code`, `module_name`, `enabled`, `sort_order`) VALUES
('ATP', 'LOGIN', 'AUTH', '登录认证', 1, 1),
('ATP', 'RET', 'ORD', '订单查询', 1, 2),
('ATP', 'RET', 'SUBM', '提交申请', 1, 3),
('ATP', 'RET', 'UPLD', '图片上传', 1, 4),
('ATP', 'RET', 'LIST', '列表展示', 1, 5),
('ATP', 'RET', 'DETAIL', '详情展示', 1, 6),
('ATP', 'REF', 'CALC', '金额计算', 1, 7);
```

### 11.3 类型字典

```sql
INSERT INTO `dict_case_type` (`case_type_code`, `case_type_name`, `enabled`, `sort_order`) VALUES
('SM', '冒烟测试', 1, 1),
('RG', '回归测试', 1, 2),
('FN', '功能测试', 1, 3),
('EX', '异常测试', 1, 4),
('INT', '集成测试', 1, 5),
('E2E', '端到端测试', 1, 6);
```

### 11.4 来源字典

```sql
INSERT INTO `dict_case_source` (`source_code`, `source_name`, `enabled`, `sort_order`) VALUES
('AI', 'AI自动生成', 1, 1),
('MN', '人工编写', 1, 2),
('CV', 'AI生成后人工复核', 1, 3),
('IMP', '历史迁移导入', 1, 4);
```

---

## 12. Case ID 自动生成规则

建议不要让前端或 AI 直接拼接完整 `case_id`，应由后端统一生成。

生成逻辑：

```text
case_id = project_code + "-" +
          client_code + "-" +
          page_code + "-" +
          module_code + "-" +
          case_type_code + "-" +
          source_code + "-" +
          sequence(4位左补0)
```

序号生成维度建议按下面分组：

```text
project_code + client_code + page_code + module_code + case_type_code + source_code
```

也就是同一组内从 `0001` 开始递增。

---

## 13. 平台校验伪代码

### 13.1 创建用例流程伪代码

```python
def create_test_case(req):
    validate_required_fields(req)

    validate_client_code(req.client_code)
    validate_page_code(req.project_code, req.page_code)
    validate_module_code(req.project_code, req.page_code, req.module_code)
    validate_case_type(req.case_type_code)
    validate_source(req.source_code)

    validate_page_module_not_duplicate(req.page_code, req.module_code)
    validate_case_title(req.case_title)

    sequence = next_sequence(
        project_code=req.project_code,
        client_code=req.client_code,
        page_code=req.page_code,
        module_code=req.module_code,
        case_type_code=req.case_type_code,
        source_code=req.source_code
    )

    case_id = build_case_id(
        project_code=req.project_code,
        client_code=req.client_code,
        page_code=req.page_code,
        module_code=req.module_code,
        case_type_code=req.case_type_code,
        source_code=req.source_code,
        sequence=sequence
    )

    save_to_db(case_id, req, sequence)

    return case_id
```

### 13.2 Case ID 拼接伪代码

```python
def build_case_id(project_code, client_code, page_code, module_code, case_type_code, source_code, sequence):
    seq = str(sequence).zfill(4)
    return f"{project_code}-{client_code}-{page_code}-{module_code}-{case_type_code}-{source_code}-{seq}"
```

### 13.3 标题校验伪代码

```python
def validate_case_title(case_title):
    if not case_title or len(case_title.strip()) < 12:
        raise ValueError("用例标题过短")

    parts = [p.strip() for p in case_title.split("-") if p.strip()]
    if len(parts) < 4:
        raise ValueError("用例标题至少应包含4段：页面-模块-条件-操作-预期")

    forbidden_patterns = [
        r"^[A-Z0-9\-]+$",
        r"^.*returnapply.*returnapply.*$"
    ]
    for pattern in forbidden_patterns:
        if re.match(pattern, case_title, re.IGNORECASE):
            raise ValueError("用例标题不可为编码式或无语义命名")
```

### 13.4 页面和模块校验伪代码

```python
def validate_page_code(project_code, page_code):
    page = query_page_dict(project_code, page_code)
    if not page or page.enabled != 1:
        raise ValueError(f"页面编码不存在或未启用: {page_code}")


def validate_module_code(project_code, page_code, module_code):
    module = query_module_dict(project_code, page_code, module_code)
    if not module or module.enabled != 1:
        raise ValueError(f"模块编码不存在或未启用: {module_code}")
```

### 13.5 禁止重复编码伪代码

```python
def validate_page_module_not_duplicate(page_code, module_code):
    if page_code == module_code:
        raise ValueError("页面编码与模块编码不能相同，请使用更精确的模块编码")
```

---

## 14. Python 可运行示例

```python
import re
from dataclasses import dataclass


VALID_CLIENT_CODES = {"WEB", "APP", "API", "ADMIN", "H5"}
VALID_CASE_TYPES = {"SM", "RG", "FN", "EX", "INT", "E2E"}
VALID_SOURCES = {"AI", "MN", "CV", "IMP"}

PAGE_DICT = {
    ("ATP", "LOGIN"): "登录页",
    ("ATP", "HOME"): "首页",
    ("ATP", "RET"): "退货申请页",
    ("ATP", "REF"): "退款页",
    ("ATP", "ORD"): "订单页",
}

MODULE_DICT = {
    ("ATP", "LOGIN", "AUTH"): "登录认证",
    ("ATP", "RET", "ORD"): "订单查询",
    ("ATP", "RET", "SUBM"): "提交申请",
    ("ATP", "RET", "UPLD"): "图片上传",
    ("ATP", "RET", "LIST"): "列表展示",
    ("ATP", "RET", "DETAIL"): "详情展示",
    ("ATP", "REF", "CALC"): "金额计算",
}


@dataclass
class CreateCaseRequest:
    project_code: str
    client_code: str
    page_code: str
    module_code: str
    case_type_code: str
    source_code: str
    case_title: str


class SequenceStore:
    def __init__(self):
        self.counters = {}

    def next_sequence(self, key: tuple) -> int:
        current = self.counters.get(key, 0) + 1
        self.counters[key] = current
        return current


sequence_store = SequenceStore()


def validate_client_code(client_code: str):
    if client_code not in VALID_CLIENT_CODES:
        raise ValueError(f"非法端编码: {client_code}")


def validate_case_type(case_type_code: str):
    if case_type_code not in VALID_CASE_TYPES:
        raise ValueError(f"非法用例类型: {case_type_code}")


def validate_source(source_code: str):
    if source_code not in VALID_SOURCES:
        raise ValueError(f"非法来源编码: {source_code}")


def validate_page_code(project_code: str, page_code: str):
    if (project_code, page_code) not in PAGE_DICT:
        raise ValueError(f"页面编码不存在: {project_code}-{page_code}")


def validate_module_code(project_code: str, page_code: str, module_code: str):
    if (project_code, page_code, module_code) not in MODULE_DICT:
        raise ValueError(f"模块编码不存在: {project_code}-{page_code}-{module_code}")


def validate_page_module_not_duplicate(page_code: str, module_code: str):
    if page_code == module_code:
        raise ValueError("页面编码与模块编码不能相同")


def validate_case_title(case_title: str):
    if not case_title or len(case_title.strip()) < 12:
        raise ValueError("用例标题长度不足")

    parts = [x.strip() for x in case_title.split("-") if x.strip()]
    if len(parts) < 4:
        raise ValueError("用例标题至少包含4段")

    if re.fullmatch(r"[A-Z0-9\-]+", case_title):
        raise ValueError("用例标题不能是纯编码")


def build_case_id(
    project_code: str,
    client_code: str,
    page_code: str,
    module_code: str,
    case_type_code: str,
    source_code: str,
    sequence: int,
) -> str:
    return f"{project_code}-{client_code}-{page_code}-{module_code}-{case_type_code}-{source_code}-{str(sequence).zfill(4)}"


def create_case(req: CreateCaseRequest) -> dict:
    validate_client_code(req.client_code)
    validate_case_type(req.case_type_code)
    validate_source(req.source_code)
    validate_page_code(req.project_code, req.page_code)
    validate_module_code(req.project_code, req.page_code, req.module_code)
    validate_page_module_not_duplicate(req.page_code, req.module_code)
    validate_case_title(req.case_title)

    sequence_key = (
        req.project_code,
        req.client_code,
        req.page_code,
        req.module_code,
        req.case_type_code,
        req.source_code,
    )
    sequence = sequence_store.next_sequence(sequence_key)

    case_id = build_case_id(
        req.project_code,
        req.client_code,
        req.page_code,
        req.module_code,
        req.case_type_code,
        req.source_code,
        sequence,
    )

    return {
        "case_id": case_id,
        "case_title": req.case_title,
        "page_name": PAGE_DICT[(req.project_code, req.page_code)],
        "module_name": MODULE_DICT[(req.project_code, req.page_code, req.module_code)],
    }


if __name__ == "__main__":
    req = CreateCaseRequest(
        project_code="ATP",
        client_code="WEB",
        page_code="RET",
        module_code="ORD",
        case_type_code="SM",
        source_code="AI",
        case_title="退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
    )
    result = create_case(req)
    print(result)
```

---

## 15. 推荐的接口设计

### 15.1 AI 生成接口不要直接收完整 `case_id`

建议 AI 只输出这些字段：

```json
{
  "project_code": "ATP",
  "client_code": "WEB",
  "page_code": "RET",
  "module_code": "ORD",
  "case_type_code": "SM",
  "source_code": "AI",
  "case_title": "退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
  "priority": "P1",
  "precondition": ["用户已登录", "存在可退货订单"],
  "steps": ["进入退货申请页", "输入有效订单号", "点击查询"],
  "expected_result": ["展示订单信息"],
  "tags": ["smoke", "ai_generated", "return_apply"]
}
```

然后平台：

- 校验字段
- 自动生成 `case_id`
- 自动填充 `page_name/module_name`
- 入库

这样最稳。

### 15.2 创建用例 API 示例

请求：

```json
POST /api/test-case/create
```

```json
{
  "project_code": "ATP",
  "client_code": "WEB",
  "page_code": "RET",
  "module_code": "ORD",
  "case_type_code": "SM",
  "source_code": "AI",
  "case_title": "退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息",
  "priority": "P1",
  "status": "Ready",
  "precondition": ["用户已登录系统"],
  "steps": ["进入退货申请页", "输入有效订单号", "点击查询按钮"],
  "expected_result": ["展示订单信息"],
  "tags": ["smoke", "ai_generated", "return_apply", "order_query"]
}
```

响应：

```json
{
  "success": true,
  "data": {
    "case_id": "ATP-WEB-RET-ORD-SM-AI-0001"
  }
}
```

---

## 16. 历史用例迁移脚本思路

类似 `returnapply-returnapply-001` 的历史 ID，迁移时不要直接覆盖，建议：

- 保留原字段 `legacy_case_id`
- 新增标准字段 `case_id`

### 16.1 迁移规则思路

#### 先做关键词映射

```python
LEGACY_PAGE_MAPPING = {
    "returnapply": ("RET", "退货申请页"),
    "refund": ("REF", "退款页"),
    "login": ("LOGIN", "登录页"),
}

LEGACY_MODULE_MAPPING = {
    "returnapply": ("ORD", "订单查询"),
    "upload": ("UPLD", "图片上传"),
    "submit": ("SUBM", "提交申请"),
}
```

#### 来源统一设为 `IMP`

历史导入统一：

```text
source_code = IMP
```

#### 类型初期可以默认 `FN`，人工再修

如果旧数据没法判断冒烟/回归：

```text
case_type_code = FN
```

#### 迁移状态字段

- `MIGRATED`
- `NEED_REVIEW`

### 16.2 迁移伪代码

```python
def migrate_legacy_case(legacy_case_id: str, legacy_title: str):
    page_code, page_name = infer_page(legacy_case_id, legacy_title)
    module_code, module_name = infer_module(legacy_case_id, legacy_title)

    if not page_code or not module_code:
        return {
            "migration_status": "NEED_REVIEW",
            "migration_remark": "页面或模块无法识别"
        }

    req = CreateCaseRequest(
        project_code="ATP",
        client_code="WEB",
        page_code=page_code,
        module_code=module_code,
        case_type_code="FN",
        source_code="IMP",
        case_title=normalize_legacy_title(legacy_title, page_name, module_name),
    )

    new_case = create_case(req)
    new_case["legacy_case_id"] = legacy_case_id
    new_case["migration_status"] = "MIGRATED"
    return new_case
```

---

## 17. 平台落地建议

### 17.1 创建链路强约束

新建用例时：

- 页面从下拉框选择
- 模块从下拉框选择
- 类型从枚举中选择
- 来源由系统自动填充
- 序号由系统自动生成
- 用户不可手工直接输入完整 ID

### 17.2 AI 生成链路强约束

AI 不直接输出自由文本 ID，而是输出结构化字段：

```json
{
  "project": "ATP",
  "client": "WEB",
  "page_code": "RET",
  "module_code": "ORD",
  "case_type": "SM",
  "source": "AI"
}
```

由平台统一拼接成 `case_id`。这比“让 AI 直接写完整 ID”更稳。

### 17.3 检索与报表建议

平台应支持按以下字段筛选：

- 项目
- 端
- 页面
- 模块
- 类型
- 来源
- 优先级
- 状态
- 是否自动化
- 创建时间
- 审核状态

---

## 18. 推荐最终落地方案

### Case ID

```text
ATP-WEB-RET-ORD-SM-AI-0001
```

### Case Title

```text
退货申请页-订单查询-输入有效订单号-点击查询-展示订单信息
```

### Metadata

```json
{
  "project": "ATP",
  "client": "WEB",
  "page_code": "RET",
  "module_code": "ORD",
  "case_type": "SM",
  "source": "AI",
  "priority": "P1",
  "status": "Ready"
}
```

---

## 19. 命名好坏对比

### 不推荐

```text
returnapply-returnapply-001
case-001
test_return_01
退货申请测试1
```

问题：

- 无法判断端
- 无法判断模块
- 无法判断类型
- 无法判断来源
- 不利于统计和检索

### 推荐

```text
ATP-WEB-RET-ORD-SM-AI-0001
ATP-WEB-RET-SUBM-RG-MN-0002
ATP-API-REF-CALC-EX-CV-0003
```

优点：

- 结构固定
- 可读可筛选
- 可批量治理
- 适合 AI 与平台联合控制

---

## 20. 版本演进建议

### v1.0

先统一：

- ID 结构
- 标题格式
- 页面/模块字典
- 类型/来源枚举
- 平台正则校验

### v1.1

增加：

- 业务域编码
- 自动化层级编码
- 缺陷关联规则
- 测试套件自动归类

### v1.2

增加：

- AI 自动纠错命名
- 历史用例自动迁移评分
- 命名质量巡检报表

---

## 21. 给 Codex 的使用建议

把本规范提供给 Codex 时，建议遵循以下方式：

1. 不要让 Codex 自由生成完整 `case_id`
2. 让 Codex 输出结构化字段，由平台统一拼接 ID
3. 所有页面、模块、类型、来源都必须从字典中选择
4. 生成结果必须经过平台正则校验、字典校验和唯一性校验
5. 老数据迁移优先保留 `legacy_case_id`，新旧双轨过渡

---

## 22. 最小落地 Checklist

- [ ] 建立页面字典表
- [ ] 建立模块字典表
- [ ] 建立类型字典表
- [ ] 建立来源字典表
- [ ] 平台统一生成 `case_id`
- [ ] 前端禁止手输完整 `case_id`
- [ ] AI 只输出结构化字段
- [ ] 平台增加正则校验
- [ ] 平台增加字典校验
- [ ] 平台增加唯一性校验
- [ ] 建立历史用例迁移规则
- [ ] 建立人工复核池

---

**文档结束**
