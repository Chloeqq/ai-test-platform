"""元素识别 — 将自然语言步骤中的元素名解析为规范 element_code。

替代原 _login_element_from_text + _LOGIN_ELEMENT_RULES 的硬编码方案。
"""

from __future__ import annotations

from shared_backend.element_binding import resolve_element_code
from shared_backend.element_naming import element_data_key, element_display_name
from shared_backend.type_utils import str_value as _normalized_text


class ElementResolver:
    """从自然语言步骤文本中解析页面元素。

    用法::

        resolver = ElementResolver(alias_map)
        result = resolver.resolve("在用户名输入框输入admin")
        if result:
            code, name, key = result
            # code="login-username-input", name="用户名输入框", key="username"
    """

    def __init__(self, alias_map: dict[str, str] | None = None) -> None:
        if alias_map:
            self._alias_map = dict(alias_map)
        else:
            # 回退：login 页面最小映射（过渡期安全网）
            from .loader import _FALLBACK_LOGIN_PAGE_MAP
            self._alias_map = dict(_FALLBACK_LOGIN_PAGE_MAP)

    @property
    def alias_map(self) -> dict[str, str]:
        return self._alias_map

    def resolve(self, text: str) -> tuple[str, str, str] | None:
        """从步骤文本中识别元素，返回 (element_code, display_name, data_key)。

        匹配策略：
        1. 优先：通过 alias_map 精确匹配（element_binding 的规范键查找）
        2. 降级：alias_map 中子串匹配（旧行为兼容，含歧义风险）
        3. 都不匹配返回 None

        展示名和 data_key 从 element_naming 统一推导。
        """
        normalized = _normalized_text(text)
        if not self._alias_map:
            return None
        code = resolve_element_code(normalized, self._alias_map)
        if code:
            name = element_display_name(code)
            key = element_data_key(code)
            return code, name, key
        # 降级：子串匹配
        for key_str, code in self._alias_map.items():
            if key_str and key_str in normalized:
                name = element_display_name(code)
                data_key = element_data_key(code)
                return code, name, data_key
        return None


def _data_ref_for_element(element_code: str, fallback_key: str) -> str:
    """从 element_code 推导 data 段引用键。

    委托 element_naming.element_data_key 从 element_code 推导语义 key
    （如 login-username-input → "username"），推导失败则回退到手动规则。
    """
    from .. import constants as _c
    key = element_data_key(element_code)
    return key or _normalized_text(fallback_key).removesuffix("_input").removesuffix("-input") or _c.FALLBACK_DATA_KEY
