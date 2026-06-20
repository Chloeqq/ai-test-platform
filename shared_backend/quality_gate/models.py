"""Quality Gate 数据模型。

定义 Severity、Decision、RuleCategory 枚举，
以及 RuleResult、ValidationReport、GateContext、CaseScore、RuleConfig 等核心数据结构。

纯数据层 — 不依赖 FastAPI、SQLAlchemy 或任何服务专属库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """规则检查结果的严重程度。

    FATAL   → REJECT，用例完全无效（如无任何断言）
    ERROR   → REVIEW，确认缺陷（如 data key 缺失）
    WARNING → REVIEW，潜在问题（如弱断言）
    INFO    → PASS，信息提示（如未使用的变量）
    """
    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def is_blocking(self) -> bool:
        return self in {Severity.FATAL, Severity.ERROR}


class Decision(str, Enum):
    """质量门禁的最终决策。

    PASS   → 用例直接入库，status = approved
    REPAIR → 可自动修复（如数据缺失），修复后重新进入 Gate
    REVIEW → 需人工审核，status = review_required
    REJECT → 驳回，status = rejected，落库保留记录
    """
    PASS = "pass"
    REPAIR = "repair"
    REVIEW = "review"
    REJECT = "reject"


class RuleCategory(str, Enum):
    """规则所属的校验维度。"""
    DATA = "data"
    ASSERTION = "assertion"
    SEMANTIC = "semantic"
    STEP = "step"
    DEPENDENCY = "dependency"
    PAGE_OBJECT = "page_object"
    REQUIREMENT = "requirement"
    AI_GENERATION = "ai_generation"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    """单条规则的检查结果。"""
    rule_id: str = ""
    rule_name: str = ""
    severity: Severity = Severity.INFO
    message: str = ""
    suggestion: str = ""
    category: RuleCategory = RuleCategory.DATA
    evidence: dict[str, Any] = field(default_factory=dict)
    passed: bool = True


@dataclass
class CaseScore:
    """用例质量评分。"""
    total_score: int = 100
    data_score: int = 30
    assertion_score: int = 30
    semantic_score: int = 20
    dependency_score: int = 10
    page_object_score: int = 10

    @property
    def grade(self) -> str:
        if self.total_score >= 95:
            return "A"
        if self.total_score >= 80:
            return "B"
        return "C"


class SeedDataProvider(Protocol):
    """惰性查询种子数据的接口。

    规则需要查询种子数据时调用对应方法，而非在 GateContext 构建时全量加载。
    避免大量 seed data 场景下的性能浪费。
    """

    def get_pool(self, pool_name: str) -> dict[str, Any]:
        """获取指定数据池的全部条目。"""
        ...

    def get_item(self, pool_name: str, item_key: str) -> Any:
        """获取数据池中的单个条目值。"""
        ...

    def has_item(self, pool_name: str, item_key: str) -> bool:
        """检查数据池中是否存在指定条目。"""
        ...


@dataclass
class GateContext:
    """质量门禁的生成上下文。

    规则约束：规则不得修改 context 中的任何可变对象（case_yaml、
    requirement、intent、page_object）。所有字段为只读，修改会导致
    管线后续步骤写出被污染的数据。
    """
    case_yaml: dict[str, Any] = field(default_factory=dict)
    requirement: dict[str, Any] = field(default_factory=dict)
    intent: dict[str, Any] = field(default_factory=dict)
    page_object: dict[str, Any] = field(default_factory=dict)
    seed_data_provider: SeedDataProvider | None = None
    project: str = ""


@dataclass
class ValidationReport:
    """质量门禁的完整评估报告。"""
    case_id: str = ""
    results: list[RuleResult] = field(default_factory=list)
    decision: Decision = Decision.PASS
    score: CaseScore = field(default_factory=CaseScore)
    summary: str = ""

    @property
    def passed(self) -> bool:
        return self.decision == Decision.PASS

    @property
    def requires_review(self) -> bool:
        return self.decision == Decision.REVIEW

    @property
    def is_rejected(self) -> bool:
        return self.decision == Decision.REJECT


@dataclass
class RuleConfig:
    """规则的运行时配置（支持降级/禁用）。"""
    rule_id: str
    enabled: bool = True
    severity: Severity | None = None  # 覆盖默认 severity
