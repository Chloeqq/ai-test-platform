"""Quality Gate — 公共层。

提供 Severity、Decision、RuleCategory、CaseStatus 等核心枚举，
RuleResult、ValidationReport、GateContext、CaseScore 等数据模型，
以及 Rule 抽象接口、RuleRegistry、RuleEngine、RuleConfigLoader。

两个服务（web-ui-service 和 ai-orchestrator）均从本包导入共享契约。
"""

from .config import RuleConfigLoader
from .domain.case_lifecycle import (
    CaseStatus,
    allowed_transitions,
    can_transition,
    is_forbidden,
    transition,
)
from .engine import RuleEngine
from .models import (
    IMPLEMENTED_PRECONDITION_TYPES,
    PRECONDITION_TYPES,
    RESERVED_PRECONDITION_TYPES,
    CaseScore,
    Decision,
    GateContext,
    RuleCategory,
    RuleConfig,
    RuleResult,
    SeedDataProvider,
    Severity,
    ValidationReport,
)
from .registry import RuleRegistry, get_registry, register_rule
from .rule_interface import Rule

__all__ = [
    # Enums
    "Severity",
    "Decision",
    "RuleCategory",
    "CaseStatus",
    # Domain constants
    "PRECONDITION_TYPES",
    "IMPLEMENTED_PRECONDITION_TYPES",
    "RESERVED_PRECONDITION_TYPES",
    # Models
    "RuleResult",
    "CaseScore",
    "GateContext",
    "ValidationReport",
    "RuleConfig",
    "SeedDataProvider",
    # Core
    "Rule",
    "RuleRegistry",
    "RuleEngine",
    "RuleConfigLoader",
    # Registry
    "get_registry",
    "register_rule",
    # Lifecycle
    "can_transition",
    "is_forbidden",
    "transition",
    "allowed_transitions",
]
