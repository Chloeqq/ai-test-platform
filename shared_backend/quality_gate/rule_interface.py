"""Rule 抽象接口。

所有质量校验规则的基类。规则应该是无副作用的——
不修改 case，不写 DB，不发网络请求。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import GateContext, RuleCategory, RuleResult, Severity


class Rule(ABC):
    """所有质量校验规则的抽象基类。

    子类必须实现 validate() 方法。
    """

    rule_id: str = ""
    rule_name: str = ""
    category: RuleCategory = RuleCategory.DATA
    severity: Severity = Severity.ERROR
    description: str = ""

    @abstractmethod
    def validate(self, context: GateContext) -> RuleResult:
        """检查用例，返回规则结果。

        不应抛出异常——异常由 RuleEngine 捕获并转换为 ERROR RuleResult。
        """
        ...
