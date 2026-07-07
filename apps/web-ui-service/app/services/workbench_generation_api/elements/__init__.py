"""元素解析子模块。

提供从数据库/资产文件加载页面对象，以及将自然语言步骤中的元素名
解析为规范 element_code 的能力。
"""

from .loader import load_alias_map
from .resolver import ElementResolver

__all__ = ["load_alias_map", "ElementResolver"]
