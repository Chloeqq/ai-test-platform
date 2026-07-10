"""AI 测试质量评估中心 — Service 层。

六维评估引擎：
  CoverageEvaluator       — 测试覆盖率
  AssertionQualityEvaluator — 断言质量（复用 Quality Gate 规则）
  ExecutabilityEvaluator   — 可执行性（DSL 编译 + Gate 决策 + 执行结果）
  ConsistencyEvaluator     — 输出一致性（多次生成对比）
  RobustnessEvaluator      — 抗扰动性（原需求 vs 扰动需求）
  HallucinationEvaluator   — AI 幻觉检测（复用 rule_016）

评估器采用策略模式，统一接口 QualityEvaluator.evaluate()。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from app.models.quality_eval import (
    QualityEvalItem,
    QualityEvalResult,
)
from app.repositories.quality_eval_repository import QualityEvalRepository

LOGGER = logging.getLogger(__name__)


class EvaluationExecutionError(Exception):
    """评估执行错误 — 由 Router 层转换为 HTTP 500。"""
    pass

# ── 评分权重（可配置）─────────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, float] = {
    "coverage": 0.25,
    "assertion_quality": 0.25,
    "executability": 0.25,
    "consistency": 0.10,
    "robustness": 0.10,
    "hallucination": 0.05,
}


# ── 数据结构 ─────────────────────────────────────────────────

@dataclass
class GeneratedCase:
    """AI 生成的测试用例结构。"""

    case_id: str = ""
    name: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    page_codes: list[str] = field(default_factory=list)
    scenario_types: list[str] = field(default_factory=list)
    script_text: str = ""
    compilation_passed: bool = True
    compilation_errors: list[str] = field(default_factory=list)
    gate_decision: str = "PASS"
    gate_rule_hits: list[str] = field(default_factory=list)
    execution_passed: bool = True
    execution_failed_step: int = 0


@dataclass
class EvalScores:
    """六维度评分结果。"""

    coverage_score: float = 0.0
    coverage_detail: dict[str, Any] = field(default_factory=dict)
    assertion_score: float = 0.0
    assertion_detail: dict[str, Any] = field(default_factory=dict)
    executability_score: float = 0.0
    executability_detail: dict[str, Any] = field(default_factory=dict)
    consistency_score: float = 0.0
    robustness_score: float = 0.0
    hallucination_flags: list[str] = field(default_factory=list)
    hallucination_score: float = 0.0
    weighted_score: float = 0.0

    def compute_weighted(self, weights: dict[str, float] | None = None) -> float:
        w = weights or DEFAULT_WEIGHTS
        self.weighted_score = round(
            self.coverage_score * w.get("coverage", 0.25)
            + self.assertion_score * w.get("assertion_quality", 0.25)
            + self.executability_score * w.get("executability", 0.25)
            + self.consistency_score * w.get("consistency", 0.10)
            + self.robustness_score * w.get("robustness", 0.10)
            + self.hallucination_score * w.get("hallucination", 0.05),
            1,
        )
        return self.weighted_score


# ── 幻觉标记定义 ───────────────────────────────────────────
_HALLUCINATION_FLAG_DEFS = {
    "FAKE_PAGE": {"label": "假页面引用", "severity": "high"},
    "UNVERIFIED_LOCATOR": {"label": "未验证元素定位", "severity": "medium"},
    "DATA_FABRICATION": {"label": "数据捏造", "severity": "high"},
    "INCONSISTENT_ELEMENT": {"label": "元素不一致", "severity": "medium"},
    "ORPHAN_REFERENCE": {"label": "孤立引用", "severity": "low"},
}


def _add_flag(flag_codes: set[str], flags: list[str], code: str, message: str) -> None:
    """向 flag 列表添加标记，用 code 去重。"""
    if code not in flag_codes:
        flag_codes.add(code)
        flags.append(message)

class QualityEvaluator(ABC):
    """评估器抽象基类。"""

    evaluator_type: str = "rule_based"
    evaluator_name: str = "base"

    @abstractmethod
    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        """评估 AI 生成的测试资产质量。返回评分。"""
        ...


# ── 评估器实现 ───────────────────────────────────────────────

class CoverageEvaluator(QualityEvaluator):
    """测试覆盖率评估器。

    逻辑：
      1. 从 item.expected_coverage 获取预期覆盖场景
      2. 从 generated.scenario_types 获取 AI 实际覆盖场景
      3. 覆盖率 = matched / expected
      4. 额外加分：AI 自主发现的合理边界场景
    """

    evaluator_type = "rule_based"
    evaluator_name = "coverage"

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        expected = [s.strip().lower() for s in item.expected_coverage]
        actual = [s.strip().lower() for s in generated.scenario_types]

        if not expected:
            return EvalScores(coverage_score=100.0, coverage_detail={"note": "no expected coverage defined"})

        matched = [s for s in expected if any(self._fuzzy_match(s, a) for a in actual)]
        missed = [s for s in expected if s not in matched]
        extra = [a for a in actual if not any(self._fuzzy_match(e, a) for e in expected)]

        rate = len(matched) / len(expected)
        # 额外场景加分（最多 +10 分）
        bonus = min(10, len(extra) * 2)

        score = round(min(100, rate * 90 + bonus), 1)

        return EvalScores(
            coverage_score=score,
            coverage_detail={
                "covered_scenarios": matched,
                "missed_scenarios": missed,
                "extra_scenarios": extra,
                "coverage_rate": round(rate, 2),
                "total_expected": len(expected),
                "total_covered": len(matched),
            },
        )

    @staticmethod
    def _fuzzy_match(a: str, b: str) -> bool:
        """简单的模糊匹配：包含关系。"""
        return a in b or b in a or SequenceMatcher(None, a, b).ratio() > 0.6


class AssertionQualityEvaluator(QualityEvaluator):
    """断言质量评估器。

    逻辑：
      1. 统计断言总数 / 强断言数 / 弱断言数
      2. 强断言：url / visible / text / attribute / element_state
      3. 弱断言：title / not_empty / exists
      4. 对照 Quality Gate 规则检测断言问题
      5. 分数 = 强断言占比 * 100，规则命中扣分
    """

    evaluator_type = "rule_based"
    evaluator_name = "assertion_quality"

    STRONG_ASSERT_TYPES = frozenset({"url", "visible", "text", "attribute", "element_state", "assert_url",
                                      "assert_visible", "assert_text", "assert_attribute"})
    WEAK_ASSERT_TYPES = frozenset({"title", "not_empty", "exists", "assert_title", "assert_exists"})

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        assertions = generated.assertions or []
        total = len(assertions)

        if total == 0:
            return EvalScores(
                assertion_score=0.0,
                assertion_detail={
                    "total_assertions": 0,
                    "strong_assertions": 0,
                    "weak_assertions": 0,
                    "issues": ["zero_assertion_count"],
                },
            )

        strong = sum(1 for a in assertions
                     if isinstance(a, dict) and a.get("type", "") in self.STRONG_ASSERT_TYPES)
        weak = sum(1 for a in assertions
                   if isinstance(a, dict) and a.get("type", "") in self.WEAK_ASSERT_TYPES)

        issues: list[str] = []
        if total == 0:
            issues.append("zero_assertion_count")
        if weak > strong:
            issues.append("weak_assertion_dominant")
        if total < len(generated.steps) * 0.5:
            issues.append("low_assertion_ratio")

        # Gate 规则命中扣分
        gate_penalty = len([h for h in generated.gate_rule_hits
                            if h in ("rule_003", "rule_008", "rule_009")]) * 10

        score = round(min(100, max(0, (strong / total) * 100 - gate_penalty)), 1)

        return EvalScores(
            assertion_score=score,
            assertion_detail={
                "total_assertions": total,
                "strong_assertions": strong,
                "weak_assertions": weak,
                "issues": issues,
                "gate_rule_hits": generated.gate_rule_hits,
            },
        )


class ExecutabilityEvaluator(QualityEvaluator):
    """可执行性评估器。

    逻辑：
      1. DSL 编译是否通过（0 或 20 分）
      2. Quality Gate 决策（PASS=30, REVIEW=15, REJECT=0）
      3. 实际执行结果（全部通过=50, 部分=25, 全部失败=0）
      4. 额外扣分：失败步骤数
    """

    evaluator_type = "rule_based"
    evaluator_name = "executability"

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        score = 0.0
        detail: dict[str, Any] = {}

        # 编译
        detail["compile_passed"] = generated.compilation_passed
        detail["compile_errors"] = generated.compilation_errors
        score += 20 if generated.compilation_passed else 0

        # Gate
        detail["gate_decision"] = generated.gate_decision
        detail["gate_rule_hits"] = generated.gate_rule_hits
        gate_score = {"PASS": 30, "REVIEW": 15, "REJECT": 0}
        score += gate_score.get(generated.gate_decision, 0)

        # 执行
        detail["execution_passed"] = generated.execution_passed
        detail["failed_step"] = generated.execution_failed_step
        if generated.execution_passed:
            score += 50
        elif generated.execution_failed_step > 0:
            score += max(0, 25 - generated.execution_failed_step * 5)

        score = min(100, score)

        return EvalScores(
            executability_score=round(score, 1),
            executability_detail=detail,
        )


class ConsistencyEvaluator(QualityEvaluator):
    """输出一致性评估器。

    逻辑：
      对比多次生成的用例结构特征向量（场景数/步骤数/断言数/涉及页面数），
      计算两两余弦相似度平均值。
    """

    evaluator_type = "embedding"
    evaluator_name = "consistency"

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        # MVP: 简化实现。实际应在 run_evaluation 中收集多次生成结果后计算。
        # 这里返回占位分数，真实计算在 quality_eval 编排层完成。
        return EvalScores(consistency_score=100.0)

    @staticmethod
    def compute_consistency(cases: list[GeneratedCase]) -> float:
        """计算多次生成的用例一致性分数。"""
        if len(cases) < 2:
            return 100.0

        vectors = [
            [len(c.steps), len(c.assertions), len(c.page_codes), len(c.scenario_types)]
            for c in cases
        ]

        similarities: list[float] = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sim = ConsistencyEvaluator._cosine_sim(vectors[i], vectors[j])
                similarities.append(sim)

        return round(sum(similarities) / len(similarities) * 100, 1) if similarities else 100.0

    @staticmethod
    def _cosine_sim(a: list[int], b: list[int]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = (sum(x * x for x in a)) ** 0.5
        norm_b = (sum(x * x for x in b)) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class RobustnessEvaluator(QualityEvaluator):
    """需求抗扰动性评估器。

    逻辑：
      原始需求用例 vs 扰动需求用例的结构差异。
      差异越小 → 鲁棒性越高。
    """

    evaluator_type = "embedding"
    evaluator_name = "robustness"

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        # MVP: 简化实现。仅当有 perturbed_requirement 时触发。
        return EvalScores(robustness_score=100.0)

    @staticmethod
    def compute_robustness(original: GeneratedCase, perturbed: GeneratedCase) -> float:
        """计算原用例和扰动用例的结构相似度。"""
        orig_vec = [len(original.steps), len(original.assertions), len(original.scenario_types)]
        pert_vec = [len(perturbed.steps), len(perturbed.assertions), len(perturbed.scenario_types)]
        sim = ConsistencyEvaluator._cosine_sim(orig_vec, pert_vec)
        return round(sim * 100, 1)


class HallucinationEvaluator(QualityEvaluator):
    """AI 幻觉检测器。

    逻辑：
      1. 提取生成用例中引用的页面/元素/数据
      2. 与 expected_page_codes + known_issues 对比
      3. 标记假页面、幻觉元素、数据捏造
      4. 无幻觉=100，每发现一类扣 25 分
    """

    evaluator_type = "rule_based"
    evaluator_name = "hallucination"

    def evaluate(self, item: QualityEvalItem, generated: GeneratedCase) -> EvalScores:
        flags: list[str] = []
        flag_codes: set[str] = set()
        expected_pages = set(item.expected_page_codes or [])
        actual_pages = set(generated.page_codes or [])

        # 检测假页面引用
        fake_pages = actual_pages - expected_pages
        for fp in fake_pages:
            _add_flag(flag_codes, flags, "FAKE_PAGE", f"假页面引用:{fp}")

        # 检测未验证的元素定位
        for step in generated.steps:
            target = step.get("target", "") if isinstance(step, dict) else ""
            if isinstance(target, str) and target.startswith("element:") and not any(
                pc in target for pc in expected_pages
            ):
                _add_flag(flag_codes, flags, "UNVERIFIED_LOCATOR", "未验证元素定位")

        # 从 known_issues 补充
        for issue in item.known_issues or []:
            issue_lower = issue.lower()
            if any(kw in issue_lower for kw in ("假", "不存在", "fake")):
                _add_flag(flag_codes, flags, "FAKE_PAGE", issue)
            elif any(kw in issue_lower for kw in ("幻觉", "hallucination")):
                _add_flag(flag_codes, flags, "DATA_FABRICATION", issue)
            elif any(kw in issue_lower for kw in ("捏造", "fabricat")):
                _add_flag(flag_codes, flags, "DATA_FABRICATION", issue)

        score = max(0, 100 - len(flags) * 20)

        return EvalScores(
            hallucination_flags=flags,
            hallucination_score=round(float(score), 1),
        )


# ── 评估编排 ─────────────────────────────────────────────────

# 默认评估器注册表
_DEFAULT_EVALUATORS: dict[str, type[QualityEvaluator]] = {
    "coverage": CoverageEvaluator,
    "assertion_quality": AssertionQualityEvaluator,
    "executability": ExecutabilityEvaluator,
    "consistency": ConsistencyEvaluator,
    "robustness": RobustnessEvaluator,
    "hallucination": HallucinationEvaluator,
}


# ID 生成器 — 从 app.core.id_gen 重导出，避免调用方同时 import 两个模块
from app.core.id_gen import (  # noqa: E402
    generate_case_id,
    generate_result_id,
    hash_text_slug,
)


def _simulate_ai_generation(item: QualityEvalItem) -> GeneratedCase:
    """模拟 AI 生成测试用例（MVP 用静态数据，可替换为真实 LLM 调用）。"""
    req = item.requirement_text.lower()
    req_hash = hash_text_slug(item.requirement_text)

    # 基于需求关键词推断覆盖场景
    is_login = any(kw in req for kw in ("登录", "login", "sign in"))
    is_search = any(kw in req for kw in ("搜索", "search"))
    is_password = any(kw in req for kw in ("密码", "password", "重置", "reset"))

    scenarios: list[str] = []
    if is_login:
        scenarios.extend(["正确登录", "错误密码", "验证码验证"])
    if is_search:
        scenarios.extend(["关键词搜索", "模糊匹配", "无结果提示"])
    if is_password:
        scenarios.extend(["发送重置邮件", "新密码设置"])
    if not scenarios:
        scenarios = ["正常流程", "异常处理"]

    # 模拟断言生成
    assertions: list[dict[str, str]] = [
        {"type": "url", "target": "/dashboard", "expected": "/dashboard"},
        {"type": "visible", "target": "欢迎文本", "expected": ""},
    ]

    # 模拟脚本
    script = f"# Generated test script for: {item.requirement_text[:60]}\n"
    script += "from playwright.sync_api import Page\n\n"
    script += "def test_generated(page: Page):\n"
    script += "    page.goto('/login')\n"
    script += "    page.fill('[name=username]', 'testuser')\n"
    script += "    page.click('button[type=submit]')\n"

    # 步骤
    steps = [
        {"action": "goto", "target": "/login", "value": ""},
        {"action": "fill", "target": "element:username_input", "value": "testuser"},
        {"action": "click", "target": "element:submit_btn", "value": ""},
    ]

    # Gate 模拟
    gate_hits: list[str] = []
    if len(assertions) < 3:
        gate_hits.append("rule_008")  # missing_assertion
    if len(scenarios) < len(item.expected_coverage):
        gate_hits.append("rule_017")  # case_incomplete

    return GeneratedCase(
        case_id=generate_case_id(),
        name=f"TC-{req_hash}",
        steps=steps,
        assertions=assertions,
        preconditions=["用户未登录"],
        page_codes=item.expected_page_codes or ["login", "dashboard"],
        scenario_types=scenarios,
        script_text=script,
        compilation_passed=True,
        gate_decision="REVIEW" if gate_hits else "PASS",
        gate_rule_hits=gate_hits,
        execution_passed=True,
    )


def _run_single_evaluation(
    item: QualityEvalItem,
    generated: GeneratedCase,
    dimensions: list[str],
    evaluators: dict[str, type[QualityEvaluator]] | None = None,
) -> EvalScores:
    """对单条 item 执行指定维度的评估。"""
    registry = evaluators or _DEFAULT_EVALUATORS
    scores = EvalScores()

    for dim in dimensions:
        evaluator_cls = registry.get(dim)
        if evaluator_cls is None:
            continue
        evaluator = evaluator_cls()
        dim_scores = evaluator.evaluate(item, generated)
        # 合并维度分数
        if dim == "coverage":
            scores.coverage_score = dim_scores.coverage_score
            scores.coverage_detail = dim_scores.coverage_detail
        elif dim == "assertion_quality":
            scores.assertion_score = dim_scores.assertion_score
            scores.assertion_detail = dim_scores.assertion_detail
        elif dim == "executability":
            scores.executability_score = dim_scores.executability_score
            scores.executability_detail = dim_scores.executability_detail
        elif dim == "consistency":
            scores.consistency_score = dim_scores.consistency_score
        elif dim == "robustness":
            scores.robustness_score = dim_scores.robustness_score
        elif dim == "hallucination":
            scores.hallucination_flags = dim_scores.hallucination_flags
            scores.hallucination_score = dim_scores.hallucination_score

    scores.compute_weighted()
    return scores


def execute_evaluation_run(
    db: Session,
    run_id: str,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """执行一次完整的质量评估运行。

    1. 加载 run + dataset + items
    2. 遍历每个 item：模拟生成 → 多维度评估 → 保存结果
    3. 汇总统计 → 更新 run 状态
    """
    repo = QualityEvalRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    items = repo.list_items(run.dataset_id)
    if not items:
        run.status = "failed"
        run.summary_json = {"error": "no items in dataset"}
        db.flush()
        return {"status": "failed", "error": "no items"}

    run.status = "running"
    run.total_items = len(items)
    db.flush()

    dimensions = run.eval_dimensions or list(_DEFAULT_EVALUATORS.keys())
    evaluators = _DEFAULT_EVALUATORS
    all_generated: list[GeneratedCase] = []
    results: list[QualityEvalResult] = []

    for idx, item in enumerate(items):
        try:
            generated = _simulate_ai_generation(item)
            all_generated.append(generated)

            scores = _run_single_evaluation(item, generated, dimensions, evaluators)

            result = QualityEvalResult(
                result_id=generate_result_id(),
                run_id=run_id,
                item_id=item.item_id,
                generated_case_json={
                    "case_id": generated.case_id,
                    "name": generated.name,
                    "steps": generated.steps,
                    "assertions": generated.assertions,
                    "scenario_types": generated.scenario_types,
                },
                generated_script=generated.script_text,
                coverage_score=scores.coverage_score,
                coverage_detail=scores.coverage_detail,
                assertion_score=scores.assertion_score,
                assertion_detail=scores.assertion_detail,
                executability_score=scores.executability_score,
                executability_detail=scores.executability_detail,
                consistency_score=scores.consistency_score,
                robustness_score=scores.robustness_score,
                hallucination_flags=scores.hallucination_flags,
                hallucination_score=scores.hallucination_score,
                weighted_score=scores.weighted_score,
            )
            results.append(result)

        except (ValueError, RuntimeError) as exc:
            # 预期的运行时错误（数据格式问题、评分计算异常）→ 标记本条失败，继续
            LOGGER.warning("Evaluation failed for item %s: %s", item.item_id, exc)
            results.append(QualityEvalResult(
                result_id=generate_result_id(),
                run_id=run_id,
                item_id=item.item_id,
                weighted_score=0.0,
                error_message=str(exc)[:500],
            ))
        # AttributeError / TypeError / NameError / KeyError → 代码 bug，不吞，直接 fail fast

        if progress_callback:
            progress_callback(idx + 1, len(items))

    repo.save_results(results)
    run.completed_items = len(results)

    # ── 事后计算一致性（需要所有生成结果） ──
    if "consistency" in dimensions or "robustness" in dimensions:
        _post_process_consistency_robustness(results, items, all_generated, dimensions)

    # ── 汇总统计 ──
    result_count = len(results)
    if result_count > 0:
        run.overall_score = round(sum(r.weighted_score for r in results) / result_count, 1)
        run.coverage_score = round(sum(r.coverage_score for r in results) / result_count, 1)
        run.assertion_score = round(sum(r.assertion_score for r in results) / result_count, 1)
        run.executability_score = round(sum(r.executability_score for r in results) / result_count, 1)
        run.consistency_score = round(sum(r.consistency_score for r in results) / result_count, 1)
        run.robustness_score = round(sum(r.robustness_score for r in results) / result_count, 1)
        run.hallucination_risk = round(sum(r.hallucination_score for r in results) / result_count, 1)

        # 问题分布
        all_flags: list[str] = []
        for r in results:
            all_flags.extend(r.hallucination_flags)
        issue_breakdown: dict[str, int] = {}
        for flag in all_flags:
            issue_breakdown[flag] = issue_breakdown.get(flag, 0) + 1

        worst = sorted(results, key=lambda r: r.weighted_score)[:5]
        run.summary_json = {
            "issue_breakdown": issue_breakdown,
            "worst_items": [
                {"result_id": r.result_id, "item_id": r.item_id, "score": r.weighted_score}
                for r in worst
            ],
        }

    run.status = "completed"
    run.finished_at = datetime.now(UTC)
    db.flush()

    return {
        "status": "completed",
        "run_id": run_id,
        "overall_score": run.overall_score,
        "total_items": run.total_items,
        "completed_items": run.completed_items,
    }


def _post_process_consistency_robustness(
    results: list[QualityEvalResult],
    items: list[QualityEvalItem],
    generated_cases: list[GeneratedCase],
    dimensions: list[str],
) -> None:
    """事后处理：计算一致性和鲁棒性。

    一致性：所有生成用例两两对比。
    鲁棒性：检查 item 是否有 perturbed_requirement，如有则模拟生成并对比。
    """
    if "consistency" in dimensions and len(generated_cases) >= 2:
        consistency = ConsistencyEvaluator.compute_consistency(generated_cases)
        for r in results:
            r.consistency_score = consistency

    if "robustness" in dimensions:
        for i, item in enumerate(items):
            if item.perturbed_requirement and i < len(results):
                orig = generated_cases[i]
                perturbed = _simulate_ai_generation(item)
                # 修改 perturbed 的需求文本为扰动版本
                perturbed.name = f"TC-PERT-{hash_text_slug(item.perturbed_requirement)}"
                robustness = RobustnessEvaluator.compute_robustness(orig, perturbed)
                results[i].robustness_score = robustness
                results[i].perturbed_output = {
                    "perturbed_requirement": item.perturbed_requirement,
                    "perturbed_scenarios": perturbed.scenario_types,
                }


def build_run_report(db: Session, run_id: str) -> dict[str, Any]:
    """构建评测报告。"""
    repo = QualityEvalRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    dataset = repo.get_dataset(run.dataset_id)

    # 查找上一次同 dataset 的运行做对比
    all_runs = repo.list_runs(project_code=run.project_code, dataset_id=run.dataset_id)
    previous = None
    for r in all_runs:
        if r.run_id != run_id and r.status == "completed":
            previous = r
            break

    compared = None
    if previous:
        delta = round(run.overall_score - previous.overall_score, 1)
        compared = {
            "previous_run_id": previous.run_id,
            "previous_overall_score": previous.overall_score,
            "delta": f"+{delta}" if delta > 0 else str(delta),
        }

    return {
        "run_id": run.run_id,
        "dataset_name": dataset.name if dataset else "",
        "task_type": run.task_type,
        "agent_version": run.agent_version,
        "llm_model": run.llm_model,
        "status": run.status,
        "overall_score": run.overall_score,
        "dimension_scores": {
            "coverage": run.coverage_score,
            "assertion_quality": run.assertion_score,
            "executability": run.executability_score,
            "consistency": run.consistency_score,
            "robustness": run.robustness_score,
            "hallucination_risk": run.hallucination_risk,
        },
        "issue_breakdown": run.summary_json.get("issue_breakdown", {}),
        "compared_to_previous": compared,
        "worst_items": run.summary_json.get("worst_items", []),
    }
