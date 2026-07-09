# YAML Schema v5 - 融合设计

> **版本**: v5.0.0
> **创建日期**: 2026-03-21
> **目标**: 融合当前项目简洁性与参考方案完整性
> **原则**: 保持 UI 测试简洁，增强 API 测试能力，向后兼容 v4
> **文档性质**: 远期蓝图，当前仓库尚未按此 Schema 实现

---

## 0. 现实边界说明（2026-03-21）

当前仓库真实生效的 Runner 契约仍是 `runners/web-playwright-python/schemas/yaml_testcase.schema.json`，其核心特征是：

- 单 `execution.page`
- 单 `runner=playwright`
- 单浏览器上下文
- 动作集合有限：`login / click / fill / wait_for / assert_visible / assert_url / goto`

因此，本文件应理解为未来可选演进方向，而不是当前实施标准。尤其下面这些能力，当前仓库都还没有正式落地：

- `global_config`
- `api_definitions`
- `pages / flow`
- `api_ref`
- `depends_on`
- `execution_config`
- `data_factories`
- `concurrency`

当前如果直接推进整套 `v5`，会明显超过项目现实成熟度，并增加回归主链不确定性。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **向后兼容** | v4 YAML 无需修改可直接在 v5 运行 |
| **渐进增强** | 简单用例保持简洁，复杂用例支持完整能力 |
| **UI/API 统一** | 同一 Schema 支持 UI 和 API 测试 |
| **契约优先** | 支持先定义契约，再写测试用例 |
| **灵活断言** | 支持多种断言操作符和逻辑表达式 |

---

## 2. 完整 Schema 结构

```yaml
# ============================================================================
# YAML Schema v5 - 完整结构
# ============================================================================

# 1. 元数据（新增）
_metadata:
  version: "1.0.0"
  last_updated: "2026-03-21"
  author: "测试团队"
  description: "测试用例描述"
  tags: ["smoke", "regression"]
  requirements: ["REQ-001", "REQ-002"]

# 2. 全局配置（新增）
global_config:
  base_url: "https://api.example.com"
  timeout: 10000
  retry:
    count: 3
    interval: 1000
  default_headers:
    Content-Type: "application/json"
  auth:
    type: "Bearer"
    token: "${auth_token}"

# 3. API 契约定义（新增，仅 API 测试需要）
api_definitions:
  - name: "api_name"
    display_name: "接口显示名称"
    version: "v1"
    description: "接口描述"
    request:
      method: "GET|POST|PUT|DELETE"
      path: "/api/path"
      path_params: [...]
      query_params: [...]
      headers: {...}
      body: {...}
    response:
      success:
        status_code: 200
        headers: {...}
        body_schema: {...}  # JSON Schema
      errors: [...]

# 4. 测试用例（v4 兼容增强）
test_cases:
  - id: "TC-001"
    name: "用例名称"
    priority: "P0|P1|P2|P3"
    description: "用例描述"
    status: "active|deprecated|draft"
    owner: "负责人"
    tags: ["tag1", "tag2"]
    
    # v4 兼容：简写模式
    page: "page_name"  # 单页面模式
    steps: [...]
    
    # v5 新增：多页面模式
    pages: [...]
    flow: [...]
    
    # v5 新增：API 测试模式
    api_ref: "api_name"
    request: {...}
    
    # v5 新增：完整期望定义
    expectations:
      status_code: 200
      headers: {...}
      body:
        structure_match: true
        fields: [...]
        logic_checks: [...]
      performance: {...}
      security_checks: [...]
    
    # v5 新增：依赖定义
    depends_on: [...]
    inputs: {...}
    outputs: {...}
    
    # v5 新增：数据驱动
    data_source: [...]
    test_template: {...}
    
    # v5 新增：并发配置
    concurrency: {...}

# 5. 执行配置（新增）
execution_config:
  environment: "staging"
  strategy:
    parallel: true
    max_workers: 3
    continue_on_failure: true
  reporting:
    formats: ["html", "json", "junit"]
    output_dir: "./test-reports"
  on_failure:
    save_request_response: true
    notify: {...}

# 6. 页面对象（v4 兼容）
# 保持在单独的 .page-object.yaml 文件中

# 7. 数据工厂（新增）
data_factories:
  - name: "user_factory"
    type: "api"
    endpoint: "/api/users"
    template: {...}
```

---

## 3. 元数据规范

### 3.1 _metadata 字段

```yaml
_metadata:
  # 版本号（语义化版本）
  version: "1.0.0"  # required
  
  # 最后更新时间
  last_updated: "2026-03-21"  # required, ISO8601
  
  # 作者/团队
  author: "测试团队"  # optional
  
  # 用例描述
  description: "详细的测试用例描述"  # optional
  
  # 标签（用于筛选）
  tags: ["smoke", "regression", "checkout"]  # optional
  
  # 关联需求
  requirements: ["REQ-001", "REQ-002"]  # optional
  
  # 变更历史
  changelog:  # optional
    - version: "1.0.0"
      date: "2026-03-21"
      author: "张三"
      changes:
        - "初始版本"
        - "添加边界值测试"
  
  # 评审状态
  review_status: "pending|approved|rejected"  # optional
  reviewed_by: "李四"  # optional
  reviewed_at: "2026-03-21"  # optional
```

---

## 4. 全局配置规范

### 4.1 global_config 字段

```yaml
global_config:
  # 基础 URL
  base_url: "https://api.example.com"  # optional
  
  # 超时时间（毫秒）
  timeout: 10000  # optional, default: 30000
  
  # 重试配置
  retry:  # optional
    count: 3  # 重试次数
    interval: 1000  # 重试间隔（毫秒）
    conditions:  # 重试条件
      - "network_error"
      - "timeout"
  
  # 默认请求头
  default_headers:  # optional
    Content-Type: "application/json"
    Accept: "application/json"
    User-Agent: "API-Contract-Tester/1.0"
  
  # 认证配置
  auth:  # optional
    type: "Bearer|Basic|ApiKey"
    token: "${auth_token}"  # 运行时变量
    header: "Authorization"
  
  # 环境变量
  variables:  # optional
    env: "staging"
    region: "cn-east"
```

---

## 5. API 契约定义

### 5.1 api_definitions 字段

```yaml
api_definitions:
  - name: "get_seckill_activities"  # required, 唯一标识
    display_name: "获取秒杀活动列表"  # optional
    version: "v1"  # optional
    description: "分页查询秒杀活动列表"  # optional
    
    # 请求定义
    request:  # required
      method: "GET"  # required
      path: "/api/v1/marketing/seckill/activities"  # required
      
      # 路径参数
      path_params:  # optional
        - name: "id"
          type: "integer"
          required: true
          description: "活动 ID"
          example: 14
      
      # 查询参数
      query_params:  # optional
        - name: "activity_name"
          type: "string"
          required: false
          description: "活动名称"
          example: "双 11"
          constraints:
            - type: "max_length"
              value: 100
            - type: "pattern"
              value: "^[\\u4e00-\\u9fa5a-zA-Z0-9\\s]+$"
      
      # 请求头
      headers:  # optional
        X-Request-ID: "${request_id}"
      
      # 请求体
      body:  # optional
        content_type: "application/json"
        schema:
          type: "object"
          properties: {...}
    
    # 响应定义
    response:  # required
      # 成功响应
      success:  # required
        status_code: 200  # required
        
        # 响应头
        headers:  # optional
          Content-Type:
            - "application/json;charset=UTF-8"
        
        # 响应体 Schema
        body_schema:  # required
          type: "object"
          required: ["code", "message", "data"]
          properties:
            code:
              type: "integer"
              enum: [0]
            message:
              type: "string"
            data:
              type: "object"
              properties: {...}
      
      # 错误响应
      errors:  # optional
        - status_code: 400
          description: "请求参数错误"
          body_schema: {...}
        - status_code: 401
          description: "未授权"
          body_schema: {...}
        - status_code: 500
          description: "服务器内部错误"
          body_schema: {...}
```

---

## 6. 测试用例规范

### 6.1 基础字段

```yaml
test_cases:
  - id: "TC-001"  # required, 唯一标识
    name: "用例名称"  # required
    priority: "P0|P1|P2|P3"  # required
    description: "用例描述"  # optional
    status: "active|deprecated|draft"  # optional, default: active
    owner: "负责人"  # optional
    tags: ["tag1", "tag2"]  # optional
```

### 6.2 UI 测试模式（v4 兼容）

```yaml
test_cases:
  - id: "TC-UI-001"
    name: "登录测试"
    priority: "P0"
    
    # v4 兼容：单页面模式
    page: "login"  # 引用 login.page-object.yaml
    variables:
      username: "admin"
      password: "123456"
    steps:
      - action: login
      - action: assert_visible
        target: home_menu
    
    # v5 新增：多页面模式
    pages:  # optional, 与 page 互斥
      - name: "login"
        page_object: "login"
      - name: "product"
        page_object: "product"
    
    flow:  # optional, 页面流转定义
      - from: "login"
        action: "login"
        navigate_to: "product"
        on_success:
          next_page: "product"
          wait_for: "product_menu"
```

### 6.3 API 测试模式

```yaml
test_cases:
  - id: "TC-API-001"
    name: "获取秒杀活动列表"
    priority: "P0"
    
    # 引用 API 契约
    api_ref: "get_seckill_activities"  # required
    
    # 请求覆盖（可选）
    request:  # optional
      query_params:
        page: 1
        page_size: 10
      headers:
        X-Test-ID: "test-001"
    
    # 期望定义
    expectations:  # required
      # HTTP 状态码
      status_code: 200
      
      # 响应头
      headers:  # optional
        Content-Type: "application/json;charset=UTF-8"
      
      # 响应体
      body:  # optional
        # 结构匹配
        structure_match: true  # 自动校验 JSON Schema
        
        # 字段校验
        fields:  # optional
          - path: "code"
            operator: "equals"
            value: 0
          - path: "message"
            operator: "equals"
            value: "success"
          - path: "data.total"
            operator: "greater_or_equal"
            value: 0
          - path: "data.page"
            operator: "equals"
            value: 1
          - path: "data.page_size"
            operator: "equals"
            value: 10
          - path: "data.list"
            operator: "type"
            value: "array"
        
        # 逻辑校验
        logic_checks:  # optional
          - name: "列表长度不超过 page_size"
            expression: "data.list.length <= data.page_size"
          - name: "活动 ID 为正整数"
            expression: "data.list.every(item => item.id > 0)"
          - name: "结束时间大于开始时间"
            expression: "data.list.every(item => item.end_time >= item.start_time)"
      
      # 性能校验
      performance:  # optional
        response_time:
          max: 2000  # 最大响应时间（毫秒）
          p95: 1500  # 95% 响应时间
          p99: 1800  # 99% 响应时间
      
      # 安全校验
      security_checks:  # optional
        - name: "无 XSS 风险"
          check: "response_body_not_contains"
          value: "<script>"
        - name: "无敏感信息泄露"
          check: "response_body_not_contains"
          value: "password"
```

### 6.4 依赖定义

```yaml
test_cases:
  - id: "TC-002"
    name: "创建订单"
    priority: "P0"
    
    # 依赖定义
    depends_on:  # optional
      - case_id: "TC-001"
        required: true  # 必须成功
        outputs:  # 需要的输出
          - "user_id"
          - "username"
    
    # 输入映射
    inputs:  # optional
      target_user_id: "{{ TC-001.outputs.user_id }}"
      target_username: "{{ TC-001.outputs.username }}"
    
    # 输出定义
    outputs:  # optional
      order_id:
        source: "response"  # response/request/step/variable
        extractor: "$.data.id"  # JSONPath/CSS/XPath
        attribute: "data-id"  # optional
    
    steps:
      - action: fill
        target: user_id_input
        value: "{{ target_user_id }}"
```

### 6.5 数据驱动测试

```yaml
test_cases:
  - id: "TC-DDT-001"
    name: "搜索功能参数化测试"
    priority: "P1"
    
    # 数据源
    data_source:  # optional
      - name: "精确搜索"
        activity_name: "双 11 特卖活动"
        expected_min_count: 1
      - name: "模糊搜索"
        activity_name: "双 11"
        expected_min_count: 1
      - name: "无结果"
        activity_name: "不存在"
        expected_count: 0
    
    # 测试模板
    test_template:  # required when data_source is present
      request:
        query_params:
          activity_name: "${activity_name}"
          page: 1
          page_size: 10
      
      expectations:
        status_code: 200
        body:
          fields:
            - path: "data.total"
              operator: "greater_or_equal"
              value: "${expected_min_count}"
```

### 6.6 并发测试

```yaml
test_cases:
  - id: "TC-CONCURRENCY-001"
    name: "并发请求测试"
    priority: "P2"
    
    # 并发配置
    concurrency:  # optional
      enabled: true
      threads: 10
      requests_per_thread: 5
      ramp_up_seconds: 10
    
    request:
      query_params:
        page: 1
        page_size: 10
    
    expectations:
      status_code: 200
      
      # 并发性能要求
      performance:
        response_time:
          max: 3000
          p95: 2000
          p99: 2500
        throughput:
          min: 100  # 最小 TPS
        error_rate:
          max: 0.01  # 错误率不超过 1%
```

---

## 7. 断言操作符 Registry

### 7.1 支持的运算符

```yaml
# 比较运算符
- equals: 等于
- not_equals: 不等于
- greater_than: 大于
- greater_or_equal: 大于等于
- less_than: 小于
- less_or_equal: 小于等于

# 字符串运算符
- contains: 包含
- not_contains: 不包含
- starts_with: 以...开始
- ends_with: 以...结束
- matches: 正则匹配

# 类型运算符
- type: 类型检查 (string/integer/number/boolean/array/object/null)
- instance_of: 实例检查

# 集合运算符
- in: 在列表中
- not_in: 不在列表中
- contains_all: 包含所有
- contains_any: 包含任意

# 空值运算符
- is_null: 为空
- is_not_null: 不为空
- is_empty: 为空数组/对象
- is_not_empty: 不为空

# 数组运算符
- length: 长度检查
- length_equals: 长度等于
- length_greater_than: 长度大于
- length_less_than: 长度小于
- unique: 元素唯一

# 对象运算符
- has_key: 包含键
- has_keys: 包含所有键
- has_any_key: 包含任意键
```

### 7.2 使用示例

```yaml
expectations:
  body:
    fields:
      # 比较运算
      - path: "code"
        operator: "equals"
        value: 0
      
      # 字符串运算
      - path: "message"
        operator: "contains"
        value: "success"
      
      # 类型检查
      - path: "data.list"
        operator: "type"
        value: "array"
      
      # 集合运算
      - path: "status"
        operator: "in"
        value: ["active", "pending", "closed"]
      
      # 空值检查
      - path: "deleted_at"
        operator: "is_null"
      
      # 数组长度
      - path: "items"
        operator: "length_greater_than"
        value: 0
      
      # 正则匹配
      - path: "email"
        operator: "matches"
        value: "^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$"
```

---

## 8. 执行配置规范

### 8.1 execution_config 字段

```yaml
execution_config:
  # 测试环境
  environment: "staging"  # dev/staging/prod
  
  # 执行策略
  strategy:  # optional
    parallel: true  # 是否并行
    max_workers: 3  # 最大并发数
    continue_on_failure: true  # 失败后继续
    stop_on_critical: true  # P0 失败停止
    
    # 执行顺序
    order: "defined|priority|random"  # optional
    
    # 过滤配置
    filter:  # optional
      tags:
        include: ["smoke"]
        exclude: ["deprecated"]
      priorities: ["P0", "P1"]
  
  # 报告配置
  reporting:  # optional
    formats: ["html", "json", "junit", "allure"]
    output_dir: "./test-reports"
    includes:
      - "test_summary"
      - "failed_cases"
      - "performance_metrics"
      - "coverage_report"
    
    # 自定义报告
    custom:  # optional
      - name: "业务报告"
        template: "./templates/business-report.html"
  
  # 失败处理
  on_failure:  # optional
    # 保存请求响应
    save_request_response: true
    
    # 截图（UI 测试）
    screenshot: true
    
    # 录屏（UI 测试）
    video: true
    
    # 日志级别
    log_level: "debug"
    
    # 通知配置
    notify:
      enabled: true
      channels: ["email", "slack", "webhook"]
      on: "failure|always"
      recipients: ["test-team@example.com"]
      webhook_url: "${SLACK_WEBHOOK}"
  
  # 清理配置
  cleanup:  # optional
    enabled: true
    on_exit: "always|failure|never"
    test_data: true
    sessions: true
```

---

## 9. 向后兼容 v4

### 9.1 v4 → v5 自动转换

```yaml
# v4 输入
version: v4
id: TC-LOGIN-001
title: 管理员登录验证
execution:
  page: login
  steps:
    - action: login
    - action: assert_visible
      target: home_menu

# v5 内部转换（自动）
version: v5
id: TC-LOGIN-001
name: 管理员登录验证  # title → name
test_cases:
  - id: TC-LOGIN-001
    page: login  # 保持兼容
    steps:
      - action: login
      - action: assert_visible
        target: home_menu
```

### 9.2 v4 字段映射

| v4 字段 | v5 字段 | 说明 |
|--------|--------|------|
| `title` | `name` | 自动映射 |
| `execution.page` | `page` | 保持兼容 |
| `execution.steps` | `steps` | 保持兼容 |
| `execution.variables` | `variables` | 保持兼容 |
| `data` | `data_source` | 升级 |
| `tags` | `tags` | 保持兼容 |
| `priority` | `priority` | 保持兼容 |

---

## 10. 完整示例

### 10.1 UI 测试示例

```yaml
# ============================================================================
# 测试用例：完整购物流程
# ============================================================================

_metadata:
  version: "1.0.0"
  last_updated: "2026-03-21"
  author: "电商测试团队"
  description: "验证用户从登录到下单的完整流程"
  tags: ["smoke", "checkout", "e2e"]
  requirements: ["REQ-CHECKOUT-001"]

global_config:
  base_url: "https://staging.example.com"
  timeout: 30000

test_cases:
  - id: "TC-CHECKOUT-001"
    name: "完整购物流程"
    priority: "P0"
    description: "登录 → 浏览商品 → 加入购物车 → 下单"
    
    # 多页面流转
    pages:
      - name: "login"
        page_object: "login"
      - name: "product"
        page_object: "product"
      - name: "cart"
        page_object: "cart"
      - name: "checkout"
        page_object: "checkout"
    
    flow:
      - from: "login"
        action: "login"
        navigate_to: "product"
      
      - from: "product"
        action: "click"
        target: "first_product"
        navigate_to: "product-detail"
      
      - from: "product-detail"
        action: "click"
        target: "add_to_cart"
      
      - from: "product-detail"
        action: "click"
        target: "cart_icon"
        navigate_to: "cart"
      
      - from: "cart"
        action: "click"
        target: "checkout_button"
        navigate_to: "checkout"
    
    variables:
      expected_total: "199.00"
    
    steps:
      - action: "fill"
        target: "address_input"
        value: "测试地址"
      
      - action: "click"
        target: "submit_order_button"
      
      - action: "assert_visible"
        target: "order_success_message"
      
      - action: "assert_text"
        target: "order_total"
        expected: "{{expected_total}}"
    
    outputs:
      order_id:
        source: "response"
        extractor: "css:.order-id"
    
    expectations:
      performance:
        response_time:
          max: 5000

execution_config:
  environment: "staging"
  reporting:
    formats: ["html", "allure"]
  on_failure:
    screenshot: true
    video: true
```

### 10.2 API 测试示例

```yaml
# ============================================================================
# 测试用例：秒杀活动列表 API
# ============================================================================

_metadata:
  version: "1.0.0"
  last_updated: "2026-03-21"
  author: "API 测试团队"
  description: "秒杀活动列表接口契约测试"
  tags: ["api", "contract", "seckill"]

global_config:
  base_url: "https://api.example.com"
  timeout: 10000
  auth:
    type: "Bearer"
    token: "${auth_token}"

api_definitions:
  - name: "get_seckill_activities"
    display_name: "获取秒杀活动列表"
    request:
      method: "GET"
      path: "/api/v1/marketing/seckill/activities"
      query_params:
        - name: "page"
          type: "integer"
          default: 1
        - name: "page_size"
          type: "integer"
          default: 10
    response:
      success:
        status_code: 200
        body_schema:
          type: "object"
          required: ["code", "message", "data"]
          properties: {...}

test_cases:
  - id: "TC-API-001"
    name: "获取秒杀活动列表 - 基本查询"
    priority: "P0"
    api_ref: "get_seckill_activities"
    
    request:
      query_params:
        page: 1
        page_size: 10
    
    expectations:
      status_code: 200
      body:
        structure_match: true
        fields:
          - path: "code"
            operator: "equals"
            value: 0
          - path: "data.page"
            operator: "equals"
            value: 1
          - path: "data.page_size"
            operator: "equals"
            value: 10
        logic_checks:
          - name: "列表长度不超过 page_size"
            expression: "data.list.length <= data.page_size"
      performance:
        response_time:
          max: 2000

  - id: "TC-API-002"
    name: "获取秒杀活动列表 - 边界值"
    priority: "P1"
    api_ref: "get_seckill_activities"
    
    request:
      query_params:
        page_size: 101  # 超出最大值
    
    expectations:
      status_code: 400
      body:
        fields:
          - path: "code"
            operator: "equals"
            value: 400
          - path: "data.error_code"
            operator: "equals"
            value: "INVALID_PARAMETER"

execution_config:
  environment: "staging"
  strategy:
    parallel: true
    max_workers: 3
  reporting:
    formats: ["html", "json", "junit"]
```

---

## 11. 实施计划

| 阶段 | 任务 | 预计 | 状态 |
|------|------|------|------|
| Phase 1 | Schema 定义与文档 | 2 天 | ⏳ |
| Phase 2 | v4→v5 转换器 | 3 天 | ⏳ |
| Phase 3 | 断言操作符 registry | 3 天 | ⏳ |
| Phase 4 | API 契约解析器 | 4 天 | ⏳ |
| Phase 5 | 多页面执行器 | 4 天 | ⏳ |
| Phase 6 | 依赖解析器 | 3 天 | ⏳ |
| Phase 7 | 完整测试与文档 | 3 天 | ⏳ |

**总计**: 22 天（约 4-5 周）

---

## 12. 迁移指南

### 12.1 v4 自动迁移

```bash
# 运行迁移工具
python scripts/migrate_v4_to_v5.py --input assets/test-cases --output assets/test-cases-v5

# 迁移报告
# - 成功：150 个用例
# - 警告：5 个用例（需要手动调整）
# - 失败：0 个用例
```

### 12.2 手动调整项

| 情况 | v4 | v5 | 调整 |
|------|----|----|------|
| 字段名 | `title` | `name` | 自动 |
| API 测试 | 不支持 | `api_ref` | 手动添加 |
| 多页面 | 不支持 | `pages` + `flow` | 手动添加 |
| 依赖 | 不支持 | `depends_on` | 手动添加 |

---

*文档版本：1.0*
*创建日期：2026-03-21*
*维护团队：AI Quality Assurance Platform Core Team*
