"""DEPENDENCY_NOT_PREPARED — data 引用的账号/资源未在 seed data 中准备。

检查 data 段中引用的身份标识（username、user、account 等），
是否在 seed data 中存在对应的测试数据。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

# 视为身份标识字段的 data key（精确匹配，避免 user_agent 等误判）
_IDENTITY_KEYS: set[str] = {
    "username",
    "user",
    "account",
    "user_id",
    "customer_id",
    "email",
    "phone",
    "mobile",
    "member_id",
}

# email 字段放宽长度限制（合法邮箱可超过 20 字符）
_EMAIL_KEYS: set[str] = {"email"}

# 始终视为"已准备"的标准测试值（无需 seed data 验证）
# 仅含身份相关值；macro123 是密码不在其中——password 字段不被检查
_KNOWN_PREPARED_VALUES: set[str] = {
    "admin",
    "testuser",
    "vipuser",
    "wronguser",
}


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_value(data_entry: Any) -> str | None:
    """从 data 条目中提取实际值。source_type 非 inline 时返回 None。"""
    if isinstance(data_entry, dict):
        if data_entry.get("source_type") == "inline":
            val = data_entry.get("value")
            if isinstance(val, str):
                return val
        return None
    if isinstance(data_entry, str):
        return data_entry
    return None


def _is_identity_key(data_key: str) -> bool:
    """判断 data key 是否为身份标识字段（精确匹配）。"""
    return _normalized(data_key) in _IDENTITY_KEYS


@register_rule(
    rule_id="RULE_004",
    rule_name="DEPENDENCY_NOT_PREPARED",
    category=RuleCategory.DEPENDENCY,
    severity=Severity.WARNING,
    description="data 引用的账号/资源未在 seed data 中准备，运行时可能因依赖缺失而假通过",
)
class DependencyNotPreparedRule(Rule):
    """检查 data 段中的身份标识是否在 seed data 中有对应测试数据。"""

    # pylint: disable=too-many-branches
    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        data = case.get("data") if isinstance(case.get("data"), dict) else {}
        provider = context.seed_data_provider

        missing: list[dict[str, str]] = []
        identity_fields_found = 0

        for data_key, data_entry in data.items():
            if not _is_identity_key(data_key):
                continue

            value = _extract_value(data_entry)
            if value is None:
                continue
            if not value.strip():
                continue

            identity_fields_found += 1

            # 注入/特殊字符 → 测试载荷，不是真实账号
            if any(ch in value for ch in ("<", ">", "'", '"', ";", "--")):
                continue

            # 边界值 → 测试载荷，不是真实账号
            stripped = value.strip()
            if data_key not in _EMAIL_KEYS:
                if len(stripped) < 3 or len(stripped) > 20 or stripped.isdigit():
                    continue

            # 标准测试值 → 视为已准备
            if _normalized(stripped) in _KNOWN_PREPARED_VALUES:
                continue

            # 无 provider → 无法判断，跳过
            if provider is None:
                continue

            # provider 不支持此查询方式 → 无法判断，跳过（避免静默归入 missing）
            if not hasattr(provider, "has_value_in_any_pool"):
                continue

            # 查询 seed data
            if provider.has_value_in_any_pool(value, field=data_key):  # type: ignore[union-attr]
                continue

            missing.append({"data_key": data_key, "value": value})

        if missing:
            items = ", ".join(
                f"`{m['data_key']}={m['value']}`" for m in missing
            )
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"发现 {len(missing)} 个依赖未准备: {items}。"
                    "该账号/资源在 seed data 中不存在，"
                    "运行时可能因后端返回'不存在'而非预期状态导致假通过。"
                ),
                suggestion=(
                    "在 seed data 中添加对应的测试账号，"
                    "或通过 API 步骤在用例中创建该状态"
                ),
                evidence={
                    "missing": missing,
                    "identity_fields_found": identity_fields_found,
                    "unprepared_count": len(missing),
                },
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=(
                f"已检查 {identity_fields_found} 个身份标识字段，依赖就绪"
            ),
            evidence={
                "identity_fields_found": identity_fields_found,
                "unprepared_count": 0,
            },
            passed=True,
        )
