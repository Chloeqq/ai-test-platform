from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "assets" / "test-cases"


PAGE_NAME_FALLBACK = {
    "login": "登录页",
    "home": "首页",
    "product": "商品页",
    "product/list": "商品列表页",
    "order": "订单页",
    "returnapply": "退货申请页",
    "refund": "退款页",
    "payment": "支付页",
    "permission": "权限管理页",
    "brand": "品牌管理页",
    "coupon": "优惠券管理页",
    "flash": "秒杀活动页",
    "addproduct": "新增商品页",
    "oms/order-setting": "订单设置页",
}

MODULE_NAME_FALLBACK = {
    "auth": "登录认证",
    "permission": "权限管理",
    "product": "商品管理",
    "product-list": "列表展示",
    "order": "订单列表",
    "brand": "品牌管理",
    "coupon": "优惠券管理",
    "flash": "秒杀活动",
    "returnapply": "查询检索",
    "payment": "支付处理",
    "oms-order-setting": "配置管理",
    "sms-brand": "品牌管理",
    "sms-coupon": "优惠券管理",
    "oms-return-apply": "查询检索",
    "addproduct": "商品新增",
}


TEXT_REPLACEMENTS = {
    "Verify ": "验证",
    "verify ": "验证",
    "Fallback ": "回退",
    "fallback ": "回退",
    "AI Generated ": "AI生成",
    "AI generated ": "AI生成",
    "generated because": "生成失败，原因是",
    "generated from requirement": "根据需求生成",
    "page": "页面",
    "Page": "页面",
    "accessible": "可访问",
    "accessibility": "可访问性",
    "visible": "可见",
    "Visibility": "可见性",
    "key elements": "关键元素",
    "key areas": "关键区域",
    "core interactions executable": "核心交互可执行",
    "core interactions": "核心交互",
    "login baseline": "登录基线",
    "flow baseline": "流程基线",
    "order": "订单",
    "product": "商品",
    "brand": "品牌",
    "coupon": "优惠券",
    "flash": "秒杀",
    "payment": "支付",
    "permission": "权限",
    "returnapply": "退货申请",
    "addproduct": "商品新增",
    "smoke": "冒烟",
    "regression": "回归",
    "functional": "功能",
    "fallback": "回退",
    "openapi": "接口契约",
    "OpenAPI": "接口契约定义",
    "user story": "用户故事",
    "User Story": "用户故事",
    "git diff": "代码变更",
    "Git Diff": "代码变更",
    "runtime logs": "运行日志",
    "Runtime Logs": "运行日志",
    "user_story": "用户故事",
    "git_diff": "代码变更",
    "defect_ticket": "缺陷单",
    "runtime_logs": "运行日志",
}


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def contains_ascii_word(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", text))


def clean_text(text: str) -> str:
    cleaned = str(text or "").strip().replace("_", " ").replace("  ", " ")
    for old, new in TEXT_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace(" - ", "-").replace("： ", "：")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned


def is_human_summary(text: str) -> bool:
    normalized = clean_text(text)
    lowered = normalized.lower()
    banned_tokens = [
        "http://",
        "https://",
        "statement:",
        "acceptance:",
        "测试点(",
        "原始需求:",
        "api:",
        "get /",
        "post /",
        "[",
        "]",
    ]
    return bool(normalized) and not any(token in lowered for token in banned_tokens)


def chinese_page_name(payload: dict[str, Any]) -> str:
    page_name = str(payload.get("page_name", "")).strip()
    if page_name:
        return page_name
    page = str(((payload.get("execution") or {}).get("page", ""))).strip()
    return PAGE_NAME_FALLBACK.get(page, "页面")


def chinese_module_name(payload: dict[str, Any]) -> str:
    module_name = str(payload.get("module_name", "")).strip()
    if module_name:
        return module_name
    module = str(payload.get("module", "")).strip()
    return MODULE_NAME_FALLBACK.get(module, "核心流程")


def case_scene_label(payload: dict[str, Any]) -> str:
    case_type_name = str(payload.get("case_type_name", "")).strip()
    if case_type_name:
        return case_type_name
    case_type = str(payload.get("case_type", "")).strip().lower()
    return {
        "sm": "冒烟测试",
        "rg": "回归测试",
        "fn": "功能测试",
        "ex": "异常测试",
        "int": "集成测试",
        "e2e": "端到端测试",
    }.get(case_type, "测试场景")


def normalize_title(payload: dict[str, Any]) -> str:
    page_name = chinese_page_name(payload)
    module_name = chinese_module_name(payload)
    description = clean_text(str(payload.get("description", "")).strip())
    title = clean_text(str(payload.get("title", "")).strip())
    requirements = payload.get("requirement") if isinstance(payload.get("requirement"), list) else []

    if contains_cjk(title) and not contains_ascii_word(title) and is_human_summary(title):
        segments = [segment.strip() for segment in title.split("-") if segment.strip()]
        if len(segments) >= 4:
            return title

    def structured_title(condition: str, action: str, expected: str) -> str:
        return f"{page_name}-{module_name}-{condition}-{action}-{expected}"

    for item in requirements:
        text = clean_text(str(item).strip())
        if not text or not is_human_summary(text):
            continue
        if contains_cjk(text) and len(text) >= 8:
            return structured_title("需求追溯", "执行校验", text[:24])

    if contains_cjk(description) and len(description) >= 8 and not contains_ascii_word(description) and is_human_summary(description):
        return structured_title("基础场景", "执行验证", description[:24])

    if "回退" in title or "回退" in description or "fallback" in str(payload.get("title", "")).lower():
        return structured_title("回退生成", "执行基础冒烟", "关键结果正确")

    if "查询" in description or "search" in str(payload.get("title", "")).lower():
        return structured_title("输入查询条件", "执行查询", "展示匹配结果")

    if "登录" in description or "login" in str(payload.get("title", "")).lower():
        return structured_title("登录前置准备", "执行登录校验", "基线状态正常")

    if "可访问" in description or "visible" in str(payload.get("description", "")).lower():
        return structured_title("页面可访问", "检查关键元素", "关键元素可见")

    return structured_title(case_scene_label(payload), "执行验证", "关键结果正确")


def normalize_description(payload: dict[str, Any], title: str) -> str:
    page_name = chinese_page_name(payload)
    module_name = chinese_module_name(payload)
    raw = clean_text(str(payload.get("description", "")).strip())
    if contains_cjk(raw) and not contains_ascii_word(raw) and is_human_summary(raw):
        return raw

    raw_lower = str(payload.get("description", "")).lower()
    title_lower = str(payload.get("title", "")).lower()
    if "fallback" in raw_lower or "fallback" in title_lower:
        return f"由于测试设计生成失败，系统采用回退策略生成该用例，用于验证{page_name}的{module_name}基础场景可正常执行。"
    if "login baseline" in raw_lower or "login baseline" in title_lower:
        return f"验证进入{page_name}前的登录基线状态正常，确保后续{module_name}断言具备稳定前置条件。"
    if "search" in raw_lower or "query" in raw_lower:
        return f"验证{page_name}的{module_name}场景可正常执行，查询输入、结果展示和关键元素状态符合预期。"
    return f"验证{page_name}的{module_name}场景可正常执行，页面访问、关键元素展示及基础交互符合预期。"


def normalize_requirement(payload: dict[str, Any], title: str, description: str) -> list[str]:
    requirements = payload.get("requirement") if isinstance(payload.get("requirement"), list) else []
    if not requirements:
        return [description]

    normalized: list[str] = []
    for index, item in enumerate(requirements):
        text = clean_text(str(item).strip())
        if not text:
            continue
        lowered = text.lower()
        if lowered.startswith("url:"):
            text = "关联地址：" + text.split(":", 1)[1].strip()
        elif lowered.startswith("page:"):
            text = "目标页面：" + text.split(":", 1)[1].strip()
        elif lowered.startswith("statement:"):
            text = "场景说明：" + text.split(":", 1)[1].strip()
        elif lowered.startswith("acceptance:"):
            text = "验收条件：" + text.split(":", 1)[1].strip()
        elif lowered.startswith("原始需求:"):
            text = "原始需求追溯：" + text.split(":", 1)[1].strip()
        if index == 0 and (contains_ascii_word(text) or not contains_cjk(text)):
            normalized.append(description)
            continue
        normalized.append(text)

    if not normalized:
        normalized.append(description)
    return normalized


def main() -> None:
    updated = 0
    for path in sorted(CASE_ROOT.rglob("*.yaml")):
        payload = read_yaml(path)
        if not payload:
            continue
        title = normalize_title(payload)
        description = normalize_description(payload, title)
        requirements = normalize_requirement(payload, title, description)

        changed = False
        if str(payload.get("title", "")).strip() != title:
            payload["title"] = title
            changed = True
        if str(payload.get("description", "")).strip() != description:
            payload["description"] = description
            changed = True
        if payload.get("requirement") != requirements:
            payload["requirement"] = requirements
            changed = True
        if changed:
            write_yaml(path, payload)
            updated += 1

    print(f"normalized_case_texts={updated}")


if __name__ == "__main__":
    main()
