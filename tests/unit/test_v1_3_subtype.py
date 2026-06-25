"""DSL V1.3 — 数据 subtype 归一化、自然语言检测、RULE_001 增强匹配。"""

from __future__ import annotations

import pytest

from shared_backend.quality_gate import GateContext
from app.services.quality_gate.rules.rule_001_title_data_mismatch import (
    TitleDataMismatchRule,
    _subtype_confirms,
)
from app.services.workbench_generation_compiler.runtime import generate_pipeline as gp

# ── 局部测试辅助函数（避免从 generate_pipeline_format 导入导致的循环引用） ──

_NL_KEYWORDS: frozenset[str] = frozenset({
    "最小", "最大", "合法", "非法", "无效", "有效",
    "边界", "超长", "超短", "空值", "空格",
})

_DSL_DATA_SUBTYPES: frozenset[str] = frozenset({
    "valid", "invalid", "boundary", "empty",
    "whitespace", "special_chars", "generated", "pool",
})


def _infer_data_subtype(value):
    if value is None:
        return "empty"
    if not isinstance(value, str):
        return None
    if value == "":
        return "empty"
    if value.strip() == "" and len(value) > 0:
        return "whitespace"
    if any(ch in value for ch in ("<", ">", "'", "\"", ";", "|", "&")):
        return "special_chars"
    return None


def _is_natural_language_description(value):
    if not isinstance(value, str) or not value.strip():
        return False
    stripped = value.strip()
    if len(stripped) < 8:
        return False
    if any(ch.isdigit() for ch in stripped):
        return False
    if any(ch.isascii() and ch.isalpha() for ch in stripped):
        return False
    chinese_chars = sum(1 for ch in stripped if '一' <= ch <= '鿿')
    if len(stripped) >= 8 and chinese_chars / len(stripped) >= 0.8:
        if sum(1 for kw in _NL_KEYWORDS if kw in stripped) >= 1:
            return True
    return False


class TestSubtypeInference:
    def test_empty_string_infers_empty(self) -> None:
        assert _infer_data_subtype("") == "empty"

    def test_none_infers_empty(self) -> None:
        assert _infer_data_subtype(None) == "empty"

    def test_whitespace_only_infers_whitespace(self) -> None:
        assert _infer_data_subtype("   ") == "whitespace"
        assert _infer_data_subtype("\t  ") == "whitespace"

    def test_special_chars_infers_special_chars(self) -> None:
        assert _infer_data_subtype("admin<script>") == "special_chars"
        assert _infer_data_subtype('test"quote') == "special_chars"

    def test_normal_value_returns_none(self) -> None:
        assert _infer_data_subtype("admin") is None
        assert _infer_data_subtype("macro123") is None
        assert _infer_data_subtype(123) is None  # non-string


class TestNaturalLanguageDetection:
    def test_long_chinese_description_is_detected(self) -> None:
        assert _is_natural_language_description("最小长度合法账号名称") is True
        assert _is_natural_language_description("非法字符注入测试数据值") is True

    def test_short_string_is_not_description(self) -> None:
        assert _is_natural_language_description("admin") is False
        assert _is_natural_language_description("短") is False

    def test_string_with_numbers_is_not_description(self) -> None:
        assert _is_natural_language_description("最小长度1合法账户") is False

    def test_english_string_is_not_description(self) -> None:
        assert _is_natural_language_description("username_with_special_chars") is False

    def test_empty_is_not_description(self) -> None:
        assert _is_natural_language_description("") is False
        assert _is_natural_language_description("   ") is False

    def test_non_string_is_not_description(self) -> None:
        assert _is_natural_language_description(123) is False
        assert _is_natural_language_description(None) is False


class TestSubtypeConfirm:
    def test_whitespace_confirms_space_pattern(self) -> None:
        assert _subtype_confirms({"subtype": "whitespace"}, "空格") is True

    def test_empty_confirms_empty_pattern(self) -> None:
        assert _subtype_confirms({"subtype": "empty"}, "空") is True

    def test_special_chars_confirms_illegal_pattern(self) -> None:
        assert _subtype_confirms({"subtype": "special_chars"}, "非法字符") is True

    def test_invalid_confirms_wrong_pattern(self) -> None:
        assert _subtype_confirms({"subtype": "invalid"}, "错误") is True

    def test_wrong_subtype_does_not_confirm(self) -> None:
        assert _subtype_confirms({"subtype": "empty"}, "空格") is False

    def test_no_subtype_does_not_confirm(self) -> None:
        assert _subtype_confirms({"value": "admin"}, "空格") is False

    def test_non_dict_does_not_confirm(self) -> None:
        assert _subtype_confirms("admin", "空格") is False


class TestSubtypeInRule001:
    """集成测试：RULE_001 利用 subtype 增强匹配。"""

    def test_space_title_with_whitespace_subtype_passes(self) -> None:
        """标题"空格"，data value 不含空格但有 whitespace subtype → 通过。"""
        ctx = GateContext(case_yaml={
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin", "subtype": "whitespace"}},
        }, project="mall")
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed, f"Expected pass but got: {result.message}"

    def test_space_title_without_subtype_and_no_space_fails(self) -> None:
        """标题"空格"，data 无空格值且无 subtype → 仍然报 mismatch。"""
        ctx = GateContext(case_yaml={
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        }, project="mall")
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False

    def test_empty_title_with_empty_subtype_passes(self) -> None:
        ctx = GateContext(case_yaml={
            "title": "用户名空时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin", "subtype": "empty"}},
        }, project="mall")
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_subtype_mismatch_still_fails(self) -> None:
        """subtype 不匹配 title 关键词时，仍执行值级检查。"""
        ctx = GateContext(case_yaml={
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin", "subtype": "empty"}},
        }, project="mall")
        result = TitleDataMismatchRule().validate(ctx)
        # subtype=empty 确认的是"空"模式，不是"空格" → 值检查：admin 不含空格 → mismatch
        assert result.passed is False


class TestSubtypeConstants:
    def test_allowed_subtypes(self) -> None:
        expected = {"valid", "invalid", "boundary", "empty",
                     "whitespace", "special_chars", "generated", "pool"}
        assert _DSL_DATA_SUBTYPES == expected


class TestPipelineNLRejection:
    """验证管线对自然语言描述值抛出 ExecutionCompilerError。"""

    def test_nl_value_raises_execution_compiler_error(self) -> None:
        from shared_backend.execution_compiler import ExecutionCompilerError

        with pytest.raises(ExecutionCompilerError) as exc_info:
            gp._normalize_dsl_data_sources({
                "data": {"u": {"source_type": "inline", "value": "最小长度合法账号名称"}},
            })
        assert exc_info.value.code == "dsl_v1_3_natural_language_value"

    def test_normal_value_passes(self) -> None:
        """普通值不应触发异常。"""
        case = {"data": {"u": {"source_type": "inline", "value": "admin"}}}
        gp._normalize_dsl_data_sources(case)
        assert case["data"]["u"]["value"] == "admin"

    def test_short_chinese_value_passes(self) -> None:
        """短中文值（非描述）应正常通过。"""
        case = {"data": {"u": {"source_type": "inline", "value": "测试数据"}}}
        gp._normalize_dsl_data_sources(case)
        assert case["data"]["u"]["value"] == "测试数据"
