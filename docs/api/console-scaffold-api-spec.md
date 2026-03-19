# Console Scaffold API Spec

## 1. 文档目的

本文档说明 `Scaffold Console` 当前依赖的核心 API、请求字段和返回数据，帮助前端、后端和测试快速对齐。

机器可读契约见：

- [orchestrator-openapi.yaml](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/openapi/orchestrator-openapi.yaml)

本文档是面向人的简化说明。

## 2. 接口总览

控制台当前主要依赖以下接口：

- `GET /health`
- `GET /assets/scaffold/templates`
- `GET /assets/scaffold/templates/{template}`
- `POST /assets/scaffold`

## 3. GET /health

### 3.1 用途

用于判断 orchestrator 服务是否已经启动。

### 3.2 成功响应

示例：

```json
{
  "status": "ok"
}
```

### 3.3 典型使用场景

- 浏览器打不开 `/console` 时先检查服务健康

## 4. GET /assets/scaffold/templates

### 4.1 用途

用于获取当前所有可用的 scaffold 模板列表。

### 4.2 成功响应结构

示例：

```json
{
  "templates": [
    {
      "name": "catalog",
      "summary": "Catalog page scaffold template"
    },
    {
      "name": "list",
      "summary": "List page scaffold template"
    }
  ]
}
```

### 4.3 字段说明

- `templates`
  - 数组
  - 返回可选模板集合

模板项字段：

- `name`
  - 模板名称
- `summary`
  - 模板摘要，用于列表展示

### 4.4 前端用途

- 填充左侧模板列表

## 5. GET /assets/scaffold/templates/{template}

### 5.1 用途

用于获取单个模板的详细定义。

### 5.2 路径参数

- `template`
  - 模板名称，例如 `catalog`

### 5.3 成功响应结构

示例：

```json
{
  "template": {
    "name": "catalog",
    "summary": "Catalog page scaffold template",
    "recommended_title": "商品目录",
    "recommended_requirement": "商品目录页面展示",
    "elements": [
      {
        "name": "catalog_menu",
        "locator_type": "role",
        "role": "menuitem",
        "locator_value": "商品目录",
        "description": "目录入口",
        "smoke_role": "menu"
      }
    ]
  }
}
```

### 5.4 字段说明

- `template.name`
  - 模板名
- `template.summary`
  - 模板摘要
- `template.recommended_title`
  - 推荐标题
- `template.recommended_requirement`
  - 推荐需求文案
- `template.elements`
  - 模板预置元素

### 5.5 错误场景

当模板不存在时，服务会返回错误响应。

当前控制台应在状态区展示错误，不让页面崩溃。

## 6. POST /assets/scaffold

### 6.1 用途

根据页面信息和模板，创建：

- page object
- smoke test case

### 6.2 请求头

```http
Content-Type: application/json
```

### 6.3 请求体字段

示例：

```json
{
  "page": "catalog",
  "title": "商品目录",
  "requirement": "商品目录页面展示",
  "template": "catalog",
  "description": "创建目录页骨架",
  "priority": "P1",
  "elements": [
    {
      "name": "catalog_search_input",
      "locator_type": "css",
      "locator_value": "input[name='keyword']",
      "description": "商品搜索框"
    },
    {
      "name": "catalog_search_button",
      "locator_type": "role",
      "role": "button",
      "locator_value": "搜索",
      "description": "搜索按钮",
      "smoke_role": "assert"
    }
  ]
}
```

### 6.4 请求字段说明

- `page`
  - 必填
  - 页面标识
- `title`
  - 必填
  - 页面标题
- `requirement`
  - 必填
  - 业务需求描述
- `template`
  - 可选
  - 选定的 scaffold 模板名
- `description`
  - 可选
  - 本次 scaffold 描述
- `priority`
  - 可选
  - 默认通常为 `P1`
- `elements`
  - 可选
  - 额外页面元素数组

### 6.5 elements 子字段说明

每个元素对象可包含：

- `name`
  - 元素名称
- `locator_type`
  - 定位类型，例如 `css`、`role`
- `locator_value`
  - 定位值
- `role`
  - 当 `locator_type=role` 时需要提供
- `description`
  - 元素说明
- `smoke_role`
  - 可选
  - 仅支持：
    - `menu`
    - `assert`

### 6.6 前端本地校验约束

在正式发送前，控制台会先做本地 preflight 检查：

- `page` 非空
- `title` 非空
- `requirement` 非空
- `elements` 必须是数组
- 数组项必须是对象
- 元素必须带 `name`
- 元素必须带 `locator_type`
- 元素必须带 `locator_value`
- `locator_type=role` 时必须带 `role`
- `smoke_role` 只能是 `menu` 或 `assert`

### 6.7 成功响应

示例结构：

```json
{
  "page_object": {
    "page": "catalog",
    "elements": {
      "catalog_menu": {
        "locator_type": "role",
        "role": "menuitem",
        "locator_value": "商品目录"
      }
    }
  },
  "test_case": {
    "id": "TC-CATALOG-001",
    "execution": {
      "page": "catalog",
      "steps": [
        {
          "action": "login"
        },
        {
          "action": "click",
          "target": "catalog_menu"
        }
      ]
    }
  },
  "page_object_path": "assets/page-objects/web/catalog.page-object.yaml",
  "test_case_path": "assets/test-cases/smoke/TC-CATALOG-001.yaml"
}
```

### 6.8 成功响应字段说明

- `page_object`
  - 生成后的 page object 内容
- `test_case`
  - 生成后的 smoke case 内容
- `page_object_path`
  - page object 文件路径
- `test_case_path`
  - test case 文件路径

### 6.9 前端使用方式

成功后，控制台会用这些字段分别更新：

- `Result Summary`
- `Generated Steps`
- `Page Elements`
- `Raw Response`
- `Recent Scaffolds`

## 7. 错误响应

### 7.1 基本结构

当前服务错误响应采用统一结构，示例：

```json
{
  "error": {
    "code": "validation_error",
    "message": "template does not exist"
  }
}
```

### 7.2 常见错误类型

- `invalid_json`
- `unsupported_media_type`
- `validation_error`
- `runner_failed`
- `internal_error`

### 7.3 前端处理要求

控制台应：

- 在状态区展示错误信息
- 不清空已填写表单
- 不使页面崩溃

## 8. 典型调用链

### 8.1 模板加载链路

1. 前端请求 `GET /assets/scaffold/templates`
2. 用户点击模板
3. 前端请求 `GET /assets/scaffold/templates/{template}`
4. 页面更新详情与推荐字段

### 8.2 创建链路

1. 用户填写表单
2. 前端本地构造 payload
3. 前端执行 preflight
4. 用户确认预览
5. 前端调用 `POST /assets/scaffold`
6. 后端创建资产
7. 前端展示结果并写入本地历史

## 9. 相关测试

接口相关集成测试位于：

- [test_orchestrate_endpoint.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_orchestrate_endpoint.py)
- [test_openapi_contract.py](/Users/bettyhuang/PycharmProjects/ai-test-platform/apps/ai-orchestrator/tests/integration/test_openapi_contract.py)

## 10. 当前限制

- 当前控制台只覆盖 scaffold 相关接口，不是完整 orchestrator 控制面板
- `elements` 仍然主要通过 JSON 文本输入
- 本地历史记录不经过服务端持久化
