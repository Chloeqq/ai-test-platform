"""元素解析子模块。

提供从数据库/资产文件加载页面对象（含页面级配置），以及将自然语言
步骤中的元素名解析为规范 element_code 的能力。
"""

from .loader import load_alias_map, load_page_config, PageConfig
from .resolver import ElementResolver

__all__ = ["load_alias_map", "load_page_config", "PageConfig", "ElementResolver"]
