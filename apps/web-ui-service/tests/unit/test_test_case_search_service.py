from __future__ import annotations

import sys
from pathlib import Path


WEB_UI_ROOT = Path(__file__).resolve().parents[2]
if str(WEB_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_ROOT))
existing_app = sys.modules.get("app")
if existing_app is not None and not getattr(existing_app, "__path__", None):
    sys.modules.pop("app", None)

from app.services.test_case_search_service import parse_test_case_search_query  # noqa: E402


def test_parse_search_query_supports_structured_aliases() -> None:
    parsed = parse_test_case_search_query('订单回归 类型:接口 状态:启用 创建人:"qa team" 结果:失败')

    assert parsed.keyword == "订单回归"
    assert parsed.test_type == "api"
    assert parsed.status == "active"
    assert parsed.creator == "qa team"
    assert parsed.last_result == "failed"


def test_parse_search_query_keeps_invalid_structured_token_in_keyword() -> None:
    parsed = parse_test_case_search_query("商品 状态:未知态")

    assert parsed.keyword == "商品 状态:未知态"
    assert parsed.status == ""
