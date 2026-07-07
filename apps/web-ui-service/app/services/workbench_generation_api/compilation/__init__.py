"""测试点编译子模块。

将 AI 生成的候选测试点编译为 TestPointPlanV1.points 可存储条目。
"""

from .point_builder import build_point
from .precondition import fallback_precondition

__all__ = ["build_point", "fallback_precondition"]
