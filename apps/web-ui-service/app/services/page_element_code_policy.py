from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status

FORMAL_ELEMENT_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,79}$")

STRICT_LOCATOR_NOISE_TOKENS = {
    "css",
    "xpath",
    "path",
    "index",
    "idx",
    "nth",
    "button1",
    "input1",
    "icon1",
    "div",
    "span",
    "el",
    "node",
    "temp",
    "tmp",
    "locator",
}

SUGGESTION_NOISE_TOKENS = STRICT_LOCATOR_NOISE_TOKENS | {"role", "text"}
BUSINESS_SUFFIX_BY_TYPE = {
    "button": "button",
    "input": "input",
    "link": "link",
    "menu": "menu",
    "tab": "tab",
    "switch": "switch",
    "checkbox": "checkbox",
    "radio": "radio",
    "dialog": "dialog",
    "table": "table",
    "metric_label": "metric_label",
    "metric_value": "metric_value",
}
SEMANTIC_PHRASES = (
    ("查询结果", "search_result"),
    ("重置", "reset"),
    ("添加", "add"),
    ("新增", "add"),
    ("确定", "confirm"),
    ("取消", "cancel"),
    ("删除", "delete"),
    ("编辑", "edit"),
    ("保存", "save"),
    ("提交", "submit"),
    ("输入搜索", "search"),
    ("搜索", "search"),
    ("查询", "search"),
    ("筛选", "filter"),
    ("用户名", "username"),
    ("用户名称", "username"),
    ("账号", "account"),
    ("密码", "password"),
    ("登录", "login"),
    ("列表", "list"),
    ("菜单", "menu"),
    ("菜单项", "menu_item"),
    ("未审核", "pending_review"),
    ("审核通过", "review_approved"),
    ("审核", "review"),
    ("通过", "approved"),
    ("上架", "publish"),
    ("下架", "unpublish"),
    ("全部", "all"),
    ("按钮", "button"),
    ("输入框", "input"),
    ("链接", "link"),
)


@dataclass(frozen=True)
class ElementCodePolicyResult:
    valid: bool
    normalized_code: str
    suggested_code: str
    errors: tuple[str, ...]


def _snake(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _page_token(page_code: str) -> str:
    return _snake(page_code)


def _strip_page_prefix(code: str, page_code: str) -> str:
    page_token = _page_token(page_code)
    if not page_token:
        return code
    if code.startswith(f"page_{page_token}_"):
        return code[len(f"page_{page_token}_") :]
    return code


def _append_business_suffix(code: str, business_type: str) -> str:
    normalized_business_type = str(business_type or "").strip().lower()
    if normalized_business_type == "password_toggle":
        return "password_toggle"
    suffix = BUSINESS_SUFFIX_BY_TYPE.get(normalized_business_type, "")
    if not code or not suffix:
        return code
    if code == suffix or code.endswith(f"_{suffix}"):
        return code
    return f"{code}_{suffix}"


def _semantic_code_from_text(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("CSS定位元素", "XPath定位元素")):
        return ""
    compact = re.sub(r"[：:，,。.;；/\\|()（）【】\[\]{}<>]+", "", raw)
    compact = re.sub(r"\s+", "", compact)
    if not compact:
        return ""

    def scan(text: str) -> list[str]:
        tokens: list[str] = []
        index = 0
        phrases = sorted(SEMANTIC_PHRASES, key=lambda item: len(item[0]), reverse=True)
        while index < len(text):
            matched = False
            for phrase, token in phrases:
                if text.startswith(phrase, index):
                    if token not in tokens:
                        tokens.extend(part for part in token.split("_") if part and part not in tokens)
                    index += len(phrase)
                    matched = True
                    break
            if not matched:
                index += 1
        return tokens

    tokens = scan(compact)
    if not tokens:
        trimmed = re.sub(r"^(请)?(输入|选择|请输入|请选择)", "", compact)
        tokens = scan(trimmed)
    if not tokens:
        return ""
    return "_".join(tokens)


def suggest_element_code(value: str, *, page_code: str = "", business_type: str = "") -> str:
    normalized = _strip_page_prefix(_snake(value), page_code)
    page_token = _page_token(page_code)
    parts = [
        part
        for part in normalized.split("_")
        if part
        and part != page_token
        and len(part) > 1
        and part not in SUGGESTION_NOISE_TOKENS
        and not part.isdigit()
    ]
    suggestion = "_".join(parts)
    suggestion = _append_business_suffix(suggestion, business_type)
    if suggestion and suggestion[0].isdigit():
        suggestion = f"element_{suggestion}"
    return suggestion if FORMAL_ELEMENT_CODE_PATTERN.fullmatch(suggestion or "") else ""


def suggest_business_element_code(value: str, *, page_code: str = "", business_type: str = "") -> str:
    raw = str(value or "").strip()
    if raw.startswith(("CSS定位元素", "XPath定位元素")):
        return ""
    semantic_code = _semantic_code_from_text(raw)
    if semantic_code:
        semantic_code = _append_business_suffix(semantic_code, business_type)
        return semantic_code if FORMAL_ELEMENT_CODE_PATTERN.fullmatch(semantic_code or "") else ""
    return suggest_element_code(raw, page_code=page_code, business_type=business_type)


def validate_element_code_policy(value: str, *, page_code: str = "", business_type: str = "") -> ElementCodePolicyResult:
    raw = str(value or "").strip()
    normalized_business_type = str(business_type or "").strip().lower()
    suggested_code = suggest_business_element_code(raw, page_code=page_code, business_type=normalized_business_type)
    errors: list[str] = []

    if not FORMAL_ELEMENT_CODE_PATTERN.fullmatch(raw):
        errors.append("元素编码必须使用 snake_case，格式为小写字母开头，仅包含小写字母、数字、下划线，长度 3-80。")

    parts = [part for part in raw.split("_") if part]
    banned_hits = sorted({part for part in parts if part in STRICT_LOCATOR_NOISE_TOKENS})
    if banned_hits:
        errors.append(f"元素编码不能包含 locator/DOM 噪音词：{', '.join(banned_hits)}。")

    if parts and parts[-1].isdigit():
        errors.append("元素编码不能用纯数字后缀作为主要区分方式。")

    page_token = _page_token(page_code)
    if page_token:
        if raw.startswith(f"page_{page_token}_"):
            errors.append("元素编码不能包含 page_页面名前缀，页面归属应由页面对象承载。")

    if normalized_business_type == "password_toggle" and raw != "password_toggle":
        errors.append("business_type=password_toggle 时，元素编码必须统一为 password_toggle。")

    if normalized_business_type == "metric_label" and not raw.endswith("_metric_label"):
        errors.append("business_type=metric_label 时，元素编码必须以 _metric_label 结尾。")

    if normalized_business_type == "metric_value" and not raw.endswith("_metric_value"):
        errors.append("business_type=metric_value 时，元素编码必须以 _metric_value 结尾。")

    return ElementCodePolicyResult(
        valid=not errors,
        normalized_code=raw,
        suggested_code=suggested_code,
        errors=tuple(errors),
    )


def require_valid_element_code(value: str, *, page_code: str = "", business_type: str = "") -> str:
    result = validate_element_code_policy(value, page_code=page_code, business_type=business_type)
    if result.valid:
        return result.normalized_code
    suggestion = f" 推荐编码：{result.suggested_code}。" if result.suggested_code else ""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invalid_element_code",
            "message": f"正式元素编码不符合命名规范。{suggestion}",
            "errors": list(result.errors),
            "suggested_code": result.suggested_code,
        },
    )
