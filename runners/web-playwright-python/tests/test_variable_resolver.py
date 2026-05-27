import pytest

from runner.variable_resolver import resolve_variables


pytestmark = [pytest.mark.contract]


def test_resolve_variables_supports_nested_lookup_and_native_value_passthrough():
    context = {
        "keyword": "手机",
        "upstream": {
            "outputs": {
                "count": 3,
                "enabled": True,
            }
        },
    }

    assert resolve_variables("{{keyword}}", context) == "手机"
    assert resolve_variables("{{upstream.outputs.count}}", context) == 3
    assert resolve_variables("{{upstream.outputs.enabled}}", context) is True


def test_resolve_variables_keeps_string_interpolation_behavior_for_partial_templates():
    context = {
        "keyword": "手机",
        "upstream": {
            "outputs": {
                "count": 3,
            }
        },
    }

    assert resolve_variables("搜索词: {{keyword}}", context) == "搜索词: 手机"
    assert resolve_variables("数量={{upstream.outputs.count}}", context) == "数量=3"
    assert resolve_variables("缺失={{missing.value}}", context) == "缺失={{missing.value}}"
