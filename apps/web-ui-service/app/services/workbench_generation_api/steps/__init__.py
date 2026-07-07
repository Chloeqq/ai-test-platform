"""步骤结构化子模块。

将 AI 生成的自然语言步骤治理为 DSL V1.1 可消费的结构化步骤。
"""

from .structurer import structured_steps_from_candidate

__all__ = ["structured_steps_from_candidate"]
