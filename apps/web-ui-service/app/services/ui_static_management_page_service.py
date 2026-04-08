from __future__ import annotations

from typing import Any


def get_console_payload(key: str) -> dict[str, Any]:
    mapping = {
        "tag_management": _tag_management_payload(),
        "page_objects": _page_objects_payload(),
        "api_contracts": _api_contracts_payload(),
        "data_templates": _data_templates_payload(),
        "env_management": _environment_payload(),
        "node_management": _node_payload(),
        "integration_config": _integration_payload(),
    }
    payload = mapping.get(key)
    if payload is None:
        raise KeyError(f"unknown management console key: {key}")
    return payload


def _tag_management_payload() -> dict[str, Any]:
    return {
        "page_title": "标签管理",
        "page_description": "统一维护用例标签、治理标签和回归分层标签，避免标签体系继续在多个页面分叉。",
        "page_responsibility": "本页唯一职责：查看标签列表、适用范围和治理说明，不承担用例生成或执行动作。",
        "breadcrumbs": ["首页", "用例中心", "标签管理"],
        "left_heading": "标签列表",
        "left_items": [
            {"title": "smoke", "meta": "适用：核心链路快速回归", "badge": "Ready", "status": "Ready", "tags": ["核心链路", "默认标签"]},
            {"title": "regression", "meta": "适用：版本发布前全量回归", "badge": "Review", "status": "Review", "tags": ["发布前", "治理"]},
            {"title": "ai-generated", "meta": "适用：AI 生成 Draft 初始标记", "badge": "Draft", "status": "Draft", "tags": ["AI", "Draft"]},
        ],
        "detail_panels": [
            {"title": "smoke", "description": "用于标记主链路、快反馈和高优先级回归集合。", "bullets": ["建议配合 P0/P1 使用", "进入日常烟测计划", "不承载治理级长尾场景"]},
            {"title": "regression", "description": "用于标记发布前、缺陷回归和跨模块联动验证。", "bullets": ["建议绑定执行计划", "支持批量打标与筛选", "后续接入覆盖率分析"]},
            {"title": "ai-generated", "description": "用于标记 AI 生成的 Draft 初稿，帮助审核与版本治理区分来源。", "bullets": ["配合 Draft / Review 状态使用", "保留 trace_id 与 prompt_version", "进入待审核队列后再决定是否发布"]},
        ],
        "primary_action": {"label": "查看用例列表", "href": "/cases"},
        "secondary_action": {"label": "查看待审核用例", "href": "/cases/review"},
    }


def _page_objects_payload() -> dict[str, Any]:
    return {
        "page_title": "页面对象",
        "page_description": "统一维护页面元素映射、可复用动作与稳定定位策略，避免页面对象散落在调试页和脚本里。",
        "page_responsibility": "本页唯一职责：管理页面对象与关键元素说明，不承担运行调试或 AI 生成。",
        "breadcrumbs": ["首页", "资产与配置", "页面对象"],
        "left_heading": "页面对象列表",
        "left_items": [
            {"title": "returnapply.query", "meta": "页面：退货申请查询页", "badge": "Ready", "status": "Ready", "tags": ["oms", "query"]},
            {"title": "product.list", "meta": "页面：商品列表页", "badge": "Review", "status": "Review", "tags": ["pms", "list"]},
            {"title": "brand.list", "meta": "页面：品牌列表页", "badge": "Draft", "status": "Draft", "tags": ["sms", "list"]},
        ],
        "detail_panels": [
            {"title": "returnapply.query", "description": "重点维护查询条件、结果表格和详情入口，支撑回归与失败复现。", "bullets": ["统一元素命名", "绑定稳定 selector", "记录页面语义与关键动作"]},
            {"title": "product.list", "description": "覆盖商品列表的搜索、筛选、排序和跳转入口。", "bullets": ["高频变更页面", "建议接入覆盖矩阵", "与测试点资产联动"]},
            {"title": "brand.list", "description": "新收口页面对象，当前仍需补齐列表操作和详情交互。", "bullets": ["先完成关键元素基线", "补齐断言建议", "进入 Review 后再放开复用"]},
        ],
        "primary_action": {"label": "开始页面录制", "href": "/assets/page-objects/recorder"},
        "secondary_action": {"label": "查看测试点资产", "href": "/assets/test-points"},
    }


def _api_contracts_payload() -> dict[str, Any]:
    return {
        "page_title": "API契约",
        "page_description": "统一管理 OpenAPI 与接口契约资产，支撑多源生成、变更分析和回归范围判断。",
        "page_responsibility": "本页唯一职责：查看接口契约列表、变更摘要与治理状态，不承担直接执行。",
        "breadcrumbs": ["首页", "资产与配置", "API契约"],
        "left_heading": "契约列表",
        "left_items": [
            {"title": "oms.order.query.v2", "meta": "域：订单查询", "badge": "Ready", "status": "Ready", "tags": ["openapi", "oms"]},
            {"title": "pms.product.search.v3", "meta": "域：商品搜索", "badge": "Review", "status": "Review", "tags": ["openapi", "pms"]},
            {"title": "refund.ticket.create.v1", "meta": "域：退货申请", "badge": "Warning", "status": "Warning", "tags": ["draft", "refund"]},
        ],
        "detail_panels": [
            {"title": "oms.order.query.v2", "description": "当前契约稳定，可作为执行计划和多源生成的默认基线。", "bullets": ["记录 request/response 关键字段", "保留权限与规则约束", "支持变更域追踪"]},
            {"title": "pms.product.search.v3", "description": "最近有筛选和排序参数调整，建议继续观察回归覆盖。", "bullets": ["关注 changed_areas", "输出推荐回归范围", "与质量趋势联动"]},
            {"title": "refund.ticket.create.v1", "description": "契约仍有告警，适合继续放在 Review/Warning 状态。", "bullets": ["补齐错误结构", "检查 trace_id 字段", "确认门禁是否放行"]},
        ],
        "primary_action": {"label": "返回 AI生成", "href": "/ai-generation"},
    }


def _data_templates_payload() -> dict[str, Any]:
    return {
        "page_title": "数据模板",
        "page_description": "维护稳定可复用的数据模板，支撑同一业务域下的烟测、回归和异常场景快速装配。",
        "page_responsibility": "本页唯一职责：管理模板列表与模板说明，不承担执行、调试和生成。",
        "breadcrumbs": ["首页", "资产与配置", "数据模板"],
        "left_heading": "模板列表",
        "left_items": [
            {"title": "order.base", "meta": "适用：订单查询 / 详情", "badge": "Ready", "status": "Ready", "tags": ["oms", "基础模板"]},
            {"title": "refund.invalid", "meta": "适用：退货异常校验", "badge": "Review", "status": "Review", "tags": ["oms", "异常"]},
            {"title": "product.search.hotwords", "meta": "适用：商品搜索热词", "badge": "Draft", "status": "Draft", "tags": ["pms", "搜索"]},
        ],
        "detail_panels": [
            {"title": "order.base", "description": "基础订单模板可被多个 smoke / regression 用例复用。", "bullets": ["保持字段稳定", "优先复用，不复制", "记录更新时间和 owner"]},
            {"title": "refund.invalid", "description": "聚焦异常值和边界值，用于补齐退货链路的负向覆盖。", "bullets": ["配合失败聚类使用", "适合加入治理任务", "建议继续 Review"]},
            {"title": "product.search.hotwords", "description": "热词模板仍在整理阶段，先限制为 Draft。", "bullets": ["先补齐标签", "确认默认数据来源", "再接入生成页高级输入"]},
        ],
        "primary_action": {"label": "查看用例中心", "href": "/cases"},
    }


def _environment_payload() -> dict[str, Any]:
    return {
        "page_title": "环境管理",
        "page_description": "统一管理测试环境、基础地址和运行参数，避免环境入口散落在执行页、调试页和脚本配置里。",
        "page_responsibility": "本页唯一职责：查看环境列表和选中环境的配置摘要，不承担执行编排。",
        "breadcrumbs": ["首页", "系统管理", "环境管理"],
        "left_heading": "环境列表",
        "left_items": [
            {"title": "staging-web", "meta": "适用：Web 主回归", "badge": "Ready", "status": "Ready", "tags": ["staging", "web"]},
            {"title": "pre-release-api", "meta": "适用：接口发布前验证", "badge": "Review", "status": "Review", "tags": ["pre", "api"]},
            {"title": "legacy-compat", "meta": "适用：兼容性回放", "badge": "Warning", "status": "Warning", "tags": ["compat", "legacy"]},
        ],
        "detail_panels": [
            {"title": "staging-web", "description": "默认 Web 回归环境，适合 smoke 和日常回归。", "bullets": ["维护 base_url", "记录账号与租户说明", "与节点池绑定"]},
            {"title": "pre-release-api", "description": "发布前接口环境，重点关注契约和权限差异。", "bullets": ["绑定 OpenAPI 版本", "配置鉴权方案", "与执行计划联动"]},
            {"title": "legacy-compat", "description": "兼容环境仍有治理风险，建议保留 Warning。", "bullets": ["仅供排查使用", "不要作为默认新手入口", "逐步收口到稳定环境"]},
        ],
        "primary_action": {"label": "查看节点管理", "href": "/system/nodes"},
    }


def _node_payload() -> dict[str, Any]:
    return {
        "page_title": "节点管理",
        "page_description": "管理执行节点状态、资源容量和运行标签，支撑执行中心的任务分发与扩容判断。",
        "page_responsibility": "本页唯一职责：查看节点列表和选中节点的容量/状态信息，不承担调度策略编辑。",
        "breadcrumbs": ["首页", "系统管理", "节点管理"],
        "left_heading": "节点列表",
        "left_items": [
            {"title": "runner-web-01", "meta": "标签：playwright / chrome", "badge": "Running", "status": "Running", "tags": ["runner", "web"]},
            {"title": "runner-api-02", "meta": "标签：api / shared", "badge": "Ready", "status": "Ready", "tags": ["runner", "api"]},
            {"title": "runner-mobile-03", "meta": "标签：mobile / limited", "badge": "Warning", "status": "Warning", "tags": ["runner", "mobile"]},
        ],
        "detail_panels": [
            {"title": "runner-web-01", "description": "当前节点承接 Web 主回归，处于运行中。", "bullets": ["关注并发槽位", "查看最近任务", "与调度中心联动"]},
            {"title": "runner-api-02", "description": "接口节点当前健康，可继续承接发布前验证。", "bullets": ["容量稳定", "可作为默认 lane", "支持 retry"]},
            {"title": "runner-mobile-03", "description": "移动端节点容量偏紧，建议继续标记 Warning。", "bullets": ["优先排队高价值任务", "必要时扩容", "避免新任务堆积"]},
        ],
        "primary_action": {"label": "查看调度中心", "href": "/settings/scheduler"},
    }


def _integration_payload() -> dict[str, Any]:
    return {
        "page_title": "集成配置",
        "page_description": "统一管理代码仓、缺陷系统、通知渠道与外部测试服务的接入状态，避免配置入口散落在各业务页。",
        "page_responsibility": "本页唯一职责：查看集成列表、连接状态和用途说明，不承担复杂的配置编辑向导。",
        "breadcrumbs": ["首页", "系统管理", "集成配置"],
        "left_heading": "集成列表",
        "left_items": [
            {"title": "GitHub / GitLab", "meta": "用途：Diff / PR / 变更追溯", "badge": "Ready", "status": "Ready", "tags": ["code", "traceability"]},
            {"title": "Jira", "meta": "用途：缺陷同步 / 治理闭环", "badge": "Review", "status": "Review", "tags": ["defect", "ticket"]},
            {"title": "Slack / Webhook", "meta": "用途：通知 / 失败播报", "badge": "Draft", "status": "Draft", "tags": ["notify", "ops"]},
        ],
        "detail_panels": [
            {"title": "GitHub / GitLab", "description": "代码仓集成用于 Git Diff、提交追溯和执行上下文聚合。", "bullets": ["记录接入状态", "说明 token 范围", "与多源生成联动"]},
            {"title": "Jira", "description": "缺陷系统集成优先服务缺陷关联、聚类归因和治理闭环。", "bullets": ["明确项目映射", "保留 trace_id", "避免页面层直接写入"]},
            {"title": "Slack / Webhook", "description": "通知集成当前仍在 Draft，适合先收敛使用范围。", "bullets": ["控制通知噪音", "支持失败播报", "后续接入角色权限"]},
        ],
        "primary_action": {"label": "查看权限与角色", "href": "/system/roles"},
    }
