"""MISSING_PRECONDITION — precondition 要求的状态在 steps 中无 setup。

检查 precondition 描述的前置状态是否需要步骤来建立，
以及 execution.steps 中是否包含对应的 setup 步骤。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from typing import Any, Callable

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)


def _normalized(value: Any) -> str:
    """标准化文本"""
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# Setup 检查函数 — 每种 check_type 对应一个检查函数
# ---------------------------------------------------------------------------

# 凭证相关字段关键词 — input/fill 步骤的 target 含其中之一视为凭证输入
_LOGIN_CREDENTIAL_KEYWORDS: frozenset[str] = frozenset({
    "username", "password", "login", "credential", "user", "pwd", "email", "account",
})


def _has_login_steps(steps: list[dict[str, Any]]) -> bool:
    """检查步骤中是否包含完整登录 setup。

    判定标准：
    1. 至少一个凭证输入（input/fill 步骤，target 含 _LOGIN_CREDENTIAL_KEYWORDS）
    2. 至少一个 click 步骤

    说明：凭证输入约束已足以排除"搜索框输入+搜索按钮"场景，
    无需对 click 的 target 再加约束，避免因按钮命名差异（btn_proceed、btn_ok 等）
    导致合法登录步骤被漏判。
    """
    has_credential_input = False
    has_click = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        action = _normalized(step.get("action"))
        target = _normalized(step.get("target", ""))

        if action in {"input", "fill"}:
            if any(kw in target for kw in _LOGIN_CREDENTIAL_KEYWORDS):
                has_credential_input = True
        if action == "click":
            has_click = True
        if has_credential_input and has_click:
            return True
    return False


# check_type → 检查函数映射
_CHECK_FN: dict[str, Callable[[list[dict[str, Any]]], bool]] = {
    "login_steps": _has_login_steps,
}

# ---------------------------------------------------------------------------
# 前置条件关键词组 → (check_type, 展示标签)
#
# 格式: (关键词列表, check_type, 面向用户的展示标签)
# 关键词列表中任意一个命中即触发对应检查。
#
# 当前覆盖（substring 匹配）:
#   "已登录"、"登录成功"、"登录状态"、"有效登录态"、"已完成认证"、"已完成登录"
#
# 已知覆盖缺口（需 regex 才能准确匹配）:
#   "以管理员身份登录" — "登录" 在 "未登录" 中也出现，单独匹配误报率高
#   "登录态有效"       — "登录态" 未在关键词列表中
# ---------------------------------------------------------------------------

_PRECONDITION_CHECKS: list[tuple[list[str], str, str]] = [
    (
        ["已登录", "登录成功", "登录状态", "有效登录态", "已完成认证", "已完成登录"],
        "login_steps",
        "登录操作",
    ),
]

# 启动时校验：_PRECONDITION_CHECKS 中所有 check_type 必须在 _CHECK_FN 中注册。
# 新增 check_type 时若忘记注册检查函数，模块加载时立即报错，不会运行时静默跳过。
assert all(ct in _CHECK_FN for _, ct, _ in _PRECONDITION_CHECKS), (
    "PRECONDITION_CHECKS 中存在未注册的 check_type，请在 _CHECK_FN 中添加对应的检查函数"
)


@register_rule(
    rule_id="RULE_005",
    rule_name="MISSING_PRECONDITION",
    category=RuleCategory.STEP,
    severity=Severity.WARNING,
    description="precondition 要求的状态在 steps 中无 setup 步骤",
)
class MissingPreconditionRule(Rule):
    """检查 precondition 要求的 setup 是否在 steps 中存在。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        requirement = case.get("requirement") if isinstance(case.get("requirement"), dict) else {}
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []

        # ── V2.0: structured preconditions block validation ──
        preconditions = case.get("preconditions")
        if isinstance(preconditions, list) and preconditions:
            return self._validate_structured(case, requirement, execution, preconditions)

        precondition_text = _normalized(requirement.get("precondition", ""))
        if not precondition_text:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message="无前置条件声明",
                passed=True,
            )

        missing_setup: list[str] = []
        checked_types: set[str] = set()  # 去重：同一 check_type 只报告一次

        for keywords, check_type, label in _PRECONDITION_CHECKS:
            matched_kw = next(
                (kw for kw in keywords if kw in precondition_text),
                None,
            )
            if not matched_kw:
                continue
            if check_type in checked_types:
                continue
            checked_types.add(check_type)

            # _CHECK_FN[check_type] 由模块级 assert 保证一定存在，无需 .get()
            check_fn = _CHECK_FN[check_type]
            if not check_fn(steps):
                missing_setup.append(
                    f"precondition 含 '{matched_kw}' 但步骤中缺少{label}"
                )

        if missing_setup:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=(
                    f"前置条件声明了需要 setup 的状态，"
                    f"但步骤中缺少对应的准备操作: {'; '.join(missing_setup)}。"
                    "若依赖外部环境或前序用例建立状态，"
                    "CI 中可能因状态不一致而假通过/假失败。"
                ),
                suggestion=(
                    "在步骤开头添加 setup 操作（如 API 调用、登录步骤），"
                    "或将前置条件改为'未登录'等无需 setup 的状态"
                ),
                evidence={
                    "precondition": precondition_text[:120],
                    "missing_setup": missing_setup,
                },
                passed=False,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"前置条件 setup 检查通过: '{precondition_text[:60]}'",
            evidence={"precondition": precondition_text[:120]},
            passed=True,
        )

    # ── V2.0: structured precondition validation ──────────────────────────

    def _validate_structured(
        self,
        case: dict,
        requirement: dict,
        execution: dict,
        preconditions: list,
    ) -> RuleResult:
        from app.services.workbench_generation_compiler.runtime.generate_pipeline_precondition import (
            _PRECONDITION_TYPES as ALLOWED_TYPES,
        )
        """V2.0: 验证结构化 preconditions 块。"""
        issues: list[str] = []

        for i, entry in enumerate(preconditions):
            if not isinstance(entry, dict):
                issues.append(f"preconditions[{i}]: 不是有效的字典对象")
                continue
            pc_type = _normalized(entry.get("type", ""))
            if not pc_type:
                issues.append(f"preconditions[{i}]: 缺少 type 字段")
            elif pc_type not in ALLOWED_TYPES:
                issues.append(
                    f"preconditions[{i}]: 未知 type '{pc_type}'，"
                    f"支持: {sorted(ALLOWED_TYPES)}"
                )

            if pc_type == "login" and not isinstance(entry.get("data_ref"), dict):
                issues.append(
                    f"preconditions[{i}] (login): 缺少 data_ref，"
                    f"无法确定登录凭据来源"
                )

        if issues:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                category=self.category,
                message=f"V2.0 preconditions 块有 {len(issues)} 个问题: {'; '.join(issues)}",
                suggestion="请修正 preconditions 块中的 type 和 data_ref 声明",
                evidence={"issues": issues, "preconditions": preconditions},
                passed=False,
            )

        types_used = [_normalized(e.get("type", "")) for e in preconditions if isinstance(e, dict)]
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            category=self.category,
            message=f"V2.0 preconditions 块验证通过: {types_used}",
            evidence={"preconditions": types_used},
            passed=True,
        )