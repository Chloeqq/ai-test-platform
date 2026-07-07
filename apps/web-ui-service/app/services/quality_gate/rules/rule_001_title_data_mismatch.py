"""TITLE_DATA_MISMATCH — 标题声称的测试场景与 data 实际值不一致。

检查 title 中的场景关键词（空格/超长/非法/错误等）是否与
data 段中对应字段的实际值语义一致。

例如：title 含"用户名仅空格"，但 data.username = "admin"（无空格）→ 不匹配。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

import re
from typing import Any, Callable

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

def _extract_value(data_entry: Any, *, field: str = "", provider: Any = None) -> str | None:
    """从 data 条目中提取实际数据值。

    支持三种格式：
    - inline dict:  {"source_type": "inline", "value": "admin"} → "admin"
    - pool 引用:    {"source_type": "pool", "value": "valid_username"} → 通过 provider 解析
    - 扁平字符串:   "admin" → "admin"

    返回 None 表示无法提取（字段缺失、pool 引用无法解析等）。
    inline 值保留原始字符串不做 strip，以保证空格等语义信息不丢失。
    """
    if isinstance(data_entry, dict):
        source_type = str(data_entry.get("source_type", "inline")).strip().lower()
        raw = data_entry.get("value")
        if not isinstance(raw, str):
            return None  # value 字段缺失或类型错误

        if source_type == "pool":
            # pool 引用中 value 字段存的是 item_key，需通过 provider 解析为实际值
            item_key = raw.strip()
            if not item_key:
                return None  # item_key 为空无意义
            if provider is not None and hasattr(provider, "resolve_value"):
                resolved = provider.resolve_value(item_key, field=field)  # type: ignore[union-attr]
                if resolved is not None:
                    return resolved
            # 无 provider 或解析失败 → 返回 None，由调用方决定如何处理
            return None

        # inline 或其他：value 字段即实际值（保留原始值，不 strip）
        return raw

    if isinstance(data_entry, str):
        # 扁平字符串：保留原始值
        return data_entry
    return None


# ---------------------------------------------------------------------------
# 中文字段名 → data key 映射
# 新模块需在此扩展。当前覆盖 login 模块的 username/password。
# ---------------------------------------------------------------------------

_SUBJECT_TO_DATA_KEY: dict[str, str] = {
    "用户名": "username",
    "密码": "password",
    "账号": "username",
}


def _find_data_keys(title: str) -> list[str]:
    """从标题中识别所有被测试的字段，返回 data key 列表。"""
    found: list[str] = []
    for subject, dk in _SUBJECT_TO_DATA_KEY.items():
        if subject in title and dk not in found:
            found.append(dk)
    return found


# ---------------------------------------------------------------------------
# 语义校验器
# ---------------------------------------------------------------------------

def _v_space(val: str) -> bool:
    return " " in val or "\t" in val


def _v_too_long(val: str) -> bool:
    return len(val) > 20


def _v_too_short(val: str) -> bool:
    """值长度 < 5 且非空（与 Rule Catalog 一致）。"""
    return 0 < len(val) < 5


def _v_empty(val: str) -> bool:
    return val == ""


def _v_special_chars(val: str) -> bool:
    return any(ch in val for ch in ("<", ">", "'", '"', ";", "|", "&"))


# ---------------------------------------------------------------------------
# 字段级语义检查：keyword 紧邻字段名（如"用户名错误"），非泛化"提示错误"
# 使用 regex 避免"账号锁定时登录提示错误"中的"错误"误判为数据值错误
# ---------------------------------------------------------------------------

def _build_field_patterns(data_keys: list[str], keyword: str) -> re.Pattern | None:
    """构建字段名+关键词的 regex 模式。

    例：data_keys=["username","password"], keyword="错误"
    → 匹配"用户名错误"或"密码错误"，不匹配"登录提示错误"。
    """
    subjects = [s for s, dk in _SUBJECT_TO_DATA_KEY.items() if dk in data_keys]
    if not subjects:
        return None
    escaped = "|".join(re.escape(s) for s in subjects)
    return re.compile(f"({escaped})\\s*{re.escape(keyword)}")


def _v_wrong(val: str, *, data_key: str, context: GateContext) -> bool:
    """检查值是否为与正确值不同的"错误值"。

    完全依赖 seed_data_provider 判断值是否为已知正确值。
    无 provider 时无法判断，返回 True（跳过此检查）。
    """
    stripped = val.strip()
    provider = context.seed_data_provider
    if provider is not None and hasattr(provider, "has_value_in_any_pool"):
        if provider.has_value_in_any_pool(stripped, field=data_key):  # type: ignore[union-attr]
            return False  # 值在 seed data 中 → 是已知正确值 → 标题说"错误"但值是对的 → 不匹配
    # 无 provider 时无法判断何为"正确值"，跳过此检查
    return True


# ── V1.3 subtype → title pattern 映射 ──
# 如果 data 条目的 subtype 已声明语义，title 含对应关键词时优先信任 subtype，
# 跳过值级检查。例如：subtype=whitespace 时标题"空格"不要求值真的含空格。
_SUBTYPE_CONFIRMS_PATTERN: dict[str, str] = {
    "whitespace": "空格",
    "empty": "空",
    "special_chars": "非法字符",
    "invalid": "错误",
}


def _subtype_confirms(data_entry: Any, pattern: str) -> bool:
    """检查 data 条目的 subtype 是否已确认与 title 关键词一致。"""
    if not isinstance(data_entry, dict):
        return False
    subtype = str(data_entry.get("subtype", "")).strip().lower()
    expected = _SUBTYPE_CONFIRMS_PATTERN.get(subtype)
    return expected == pattern


# (title 关键词模式, 中文描述, 校验函数, 是否为 regex, 是否需要字段级匹配)
# _v_wrong 签名不同(val, *, data_key, context)，不由通用路径 validator(value) 调用，
# validate() 中对 "错误" 做特判直接调用 _v_wrong。在 tuple 中注册 None 以保持结构一致。
_SEMANTIC_CHECKS: list[tuple[str, str, Callable[..., bool] | None, bool, bool]] = [
    ("空格",     "值含空格",            _v_space,         False, False),
    (r"大于.*边界", "超长值(>20字符)",   _v_too_long,      True,  False),
    (r"小于.*边界", "超短值(<5字符)",    _v_too_short,     True,  False),
    ("空",       "空值",               _v_empty,         False, False),
    ("非法字符",  "含特殊字符",          _v_special_chars, False, False),
    ("错误",     "与正确值不同",         None,             False, True),  # _v_wrong 由特判调用
]


@register_rule(
    rule_id="RULE_001",
    rule_name="TITLE_DATA_MISMATCH",
    category=RuleCategory.SEMANTIC,
    severity=Severity.ERROR,
    description="标题声称的测试场景与 data 实际值不一致",
)
class TitleDataMismatchRule(Rule):
    """检查 title 声称的测试场景是否与 data 实际值一致。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        title = case.get("title", "")
        if not title:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message="无用例标题", passed=True,
            )

        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        data_keys = _find_data_keys(title)
        if not data_keys:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"标题中未识别到已知字段，跳过: '{title[:60]}'",
                passed=True,
            )

        all_mismatches: list[dict[str, Any]] = []
        for data_key in data_keys:
            value = _extract_value(data.get(data_key), field=data_key, provider=context.seed_data_provider)
            if value is None:
                continue

            mismatches: list[str] = []
            for pattern, desc, validator, is_regex, needs_field_match in _SEMANTIC_CHECKS:
                # 关键词匹配
                if is_regex:
                    if not re.search(pattern, title):
                        continue
                else:
                    if pattern not in title:
                        continue

                # "空" 会误匹配 "空格"
                if pattern == "空" and any(w in title for w in ("空格", "空白")):
                    continue

                # 字段级匹配：关键词须紧邻字段名（如"用户名错误"）
                if needs_field_match:
                    field_re = _build_field_patterns(data_keys, pattern)
                    if field_re and not field_re.search(title):
                        continue

                # 执行校验
                if pattern == "错误":
                    ok = _v_wrong(value, data_key=data_key, context=context)
                else:
                    ok = validator(value)
                if not ok:
                    # V1.3: subtype 已声明语义 → 信任 subtype，跳过值级检查
                    if _subtype_confirms(data.get(data_key), pattern):
                        continue
                    mismatches.append(
                        f"标题含'{pattern}'({desc})，"
                        f"但 {data_key}='{value[:30]}' 不满足"
                    )

            if mismatches:
                all_mismatches.append({
                    "data_key": data_key,
                    "value": value[:60],
                    "mismatches": mismatches,
                })

        if all_mismatches:
            summary = "; ".join(
                f"{m['data_key']}: " + ", ".join(m["mismatches"])
                for m in all_mismatches
            )
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"标题声称的测试场景与 data 实际值不一致: {summary}",
                suggestion="修正 data 值使其与标题声称的场景匹配，或修正标题描述",
                evidence={"title": title[:120], "mismatches": all_mismatches},
                passed=False,
            )

        checked = ", ".join(
            f"{dk}='{(_extract_value(data.get(dk), field=dk, provider=context.seed_data_provider) or '')[:26]}'"
            for dk in data_keys
        )
        message = f"标题场景与 data 值一致: {checked}"
        # P1: 无 provider 且标题含"错误"时，提示 '错误值'检查已跳过
        if context.seed_data_provider is None and "错误" in title:
            message += " (seed_data_provider 缺失，'错误值'检查已跳过)"
        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=message,
            evidence={"title": title[:120], "checked_keys": data_keys},
            passed=True,
        )
