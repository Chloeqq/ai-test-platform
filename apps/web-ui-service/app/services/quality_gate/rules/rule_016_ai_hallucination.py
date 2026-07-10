"""AI_HALLUCINATION — AI 生成了不存在的对象/URL/文本。

仅检查其他规则未覆盖的信号：
1. page_url 与 page object URL 不一致
2. 多个幻觉信号同时出现（空 locator 比例、模板残留、未知 element）

RULE_006/012/014 已覆盖 element/locator 单项检查，本规则不重复。

详见 docs/architecture/2026-06-17_Rule Catalog 规则目录.md
"""

from __future__ import annotations

from shared_backend.quality_gate import (
    GateContext,
    Rule,
    RuleCategory,
    RuleResult,
    Severity,
    register_rule,
)

from ._common import extract_element_code, normalized


@register_rule(
    rule_id="RULE_016",
    rule_name="AI_HALLUCINATION",
    category=RuleCategory.AI_GENERATION,
    severity=Severity.ERROR,
    description="AI 生成了不存在的对象/URL/文本",
)
class AIHallucinationRule(Rule):
    """综合多个信号判断 AI 是否产生了幻觉内容。"""

    def validate(self, context: GateContext) -> RuleResult:
        case = context.case_yaml
        title = normalized(case.get("title", ""))
        execution = case.get("execution") if isinstance(case.get("execution"), dict) else {}
        steps = execution.get("steps") if isinstance(execution.get("steps"), list) else []
        page_object = context.page_object or {}

        signals: list[str] = []

        # ── 信号1: page_url 不一致 ──
        po_url = normalized(page_object.get("page_url", ""))
        case_url = normalized(execution.get("page_url", ""))
        if po_url and case_url and po_url != case_url:
            signals.append(f"page_url 与页面对象不一致 (case={case_url}, po={po_url})")

        # ── 信号2: 模板残留 (如 {{intent_title}} 未被替换) ──
        if "${{" in title or "{{intent" in title.lower():
            signals.append(f"标题含未替换模板残留: '{title[:80]}'")

        # ── 信号3: 空 locator 比例过高 ──
        if steps:
            empty_loc = sum(
                1 for s in steps
                if isinstance(s, dict) and not normalized(s.get("locator_type", ""))
            )
            if empty_loc >= max(1, len(steps) * 0.5):
                signals.append(f"空 locator 比例过高 ({empty_loc}/{len(steps)})")

        # ── 信号4: 未知 element 引用 ──
        elements = page_object.get("elements") if isinstance(page_object, dict) else None
        if isinstance(elements, dict) and elements:
            unknown = [
                extract_element_code(s.get("target", ""))
                for s in steps
                if isinstance(s, dict)
                and extract_element_code(s.get("target", ""))
                and extract_element_code(s.get("target", "")) not in elements
            ]
            if unknown:
                signals.append(f"引用了 {len(unknown)} 个未知 element: {', '.join(unknown[:5])}")

        if len(signals) >= 2:
            return RuleResult(
                rule_id=self.rule_id, rule_name=self.rule_name,
                severity=self.severity, category=self.category,
                message=f"检测到 {len(signals)} 个 AI 幻觉信号: {'; '.join(signals)}",
                suggestion="请人工确认 AI 生成的内容是否正确，修正不存在的引用",
                evidence={"signals": signals, "title": title[:120]},
                passed=False,
            )

        if signals:
            msg = f"发现 {len(signals)} 个孤立的幻觉信号（不足 2 个不判定为幻觉）: {'; '.join(signals)}"
        else:
            msg = "未检测到 AI 幻觉信号"
        return RuleResult(
            rule_id=self.rule_id, rule_name=self.rule_name,
            severity=self.severity, category=self.category,
            message=msg,
            passed=True,
        )
