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
# Domain Constants
# ---------------------------------------------------------------------------

# 结构化 precondition 支持的 type 集合 — 唯一事实源。
# 生成管线（generate_pipeline_precondition）与 RULE_005 均从此处导入，
# 避免两侧各自维护字面量导致漂移。
PRECONDITION_TYPES: frozenset[str] = frozenset({
    "login", "account_state", "sql", "api_call", "network",
})

# 已实现编译分支的 precondition 类型子集 — 编译器真正能产出 setup 步骤的类型。
# 新增编译分支时必须同步加入此集合。
IMPLEMENTED_PRECONDITION_TYPES: frozenset[str] = frozenset({
    "login", "account_state", "sql", "network",
})

# 预留但未实现的 precondition 类型（已进入契约、暂无编译分支）。
# 编译器遇到这些类型会硬失败（not_implemented），RULE_005 给 WARNING，
# 杜绝「校验通过却静默不执行」。当前 = {"api_call"}（V2.5+ 实现）。
RESERVED_PRECONDITION_TYPES: frozenset[str] = PRECONDITION_TYPES - IMPLEMENTED_PRECONDITION_TYPES


# 负向/错误场景检测关键词 — 预期文本中出现任一即视为负向用例。
# 生成管线断言（generate_pipeline_assertion）与格式（generate_pipeline_format）
# 两侧共用：负向场景不追加登录成功断言，改追加错误提示断言。
NEGATIVE_SCENARIO_KEYWORDS: tuple[str, ...] = (
    "错误", "失败", "提示", "异常", "无效", "非法", "锁定", "禁用",
)


# 登录成功信号关键词 — 预期文本中出现任一才追加"登录后首页可见"断言。
# 仅判断"非负向"不够：密码可见性切换、记住密码勾选等单步交互场景的预期
# 文本也不含负向词，但跟"登录后进入首页"无关，不应被强行追加首页断言。
LOGIN_SUCCESS_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "登录成功", "工作台", "首页", "跳转",
)


# 账号状态检测关键词 → 规范化 state 名。precondition 文本命中后，
# 生成管线据此把身份字段路由为数据池引用，键名约定 {field}_{state}
# （如 username_locked / password_disabled）。dict 插入顺序即匹配优先级。
ACCOUNT_STATE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "locked": ("锁定", "lock", "locked"),
    "disabled": ("禁用", "disabled", "forbidden"),
}


def detect_account_state(text: str) -> str:
    """从文本中检测账号状态，返回规范化 state 名（无命中返回 ""）。

    按 ACCOUNT_STATE_KEYWORDS 的插入顺序匹配（locked 优先于 disabled），
    与历史 if/elif 行为一致。
    """
    lowered = (text or "").lower()
    for state, keywords in ACCOUNT_STATE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return state
    return ""


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
