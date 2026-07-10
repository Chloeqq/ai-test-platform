"""Quality Gate — 实现层。

提供 CaseQualityGate、ScoreEngine 和 17 条质量校验规则。
"""

# 导入 rules 包以触发 @register_rule 装饰器执行
from . import rules  # noqa: F401
from .gate import CaseQualityGate
from .pipeline_gate import evaluate_case_quality
from .scoring import ScoreEngine

__all__ = [
    "CaseQualityGate",
    "ScoreEngine",
    "evaluate_case_quality",
]
