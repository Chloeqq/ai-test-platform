"""测试 RULE_001 — TITLE_DATA_MISMATCH。"""

from __future__ import annotations

from shared_backend.quality_gate import GateContext, Severity
from app.services.quality_gate.rules.rule_001_title_data_mismatch import (
    TitleDataMismatchRule,
)
from app.services.quality_gate.seed_data_provider import SimpleSeedDataProvider


def _ctx(case_yaml: dict) -> GateContext:
    return GateContext(case_yaml=case_yaml, project="mall")


def _ctx_with_provider(case_yaml: dict, pools: dict | None = None) -> GateContext:
    """构造带 seed_data_provider 的 GateContext。"""
    if pools is None:
        pools = {
            "login": {
                "username_admin": {"username": "admin", "password": "macro123"},
                "password_macro": {"username": "admin", "password": "macro123"},
            },
        }
    return GateContext(
        case_yaml=case_yaml,
        project="mall",
        seed_data_provider=SimpleSeedDataProvider(pools),
    )


class TestRule001Mismatches:
    """标题声称场景与 data 值不一致 → 应检测到 mismatch。"""

    def test_spaces_title_but_no_space_in_value(self) -> None:
        ctx = _ctx({
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False
        assert "空格" in result.message

    def test_empty_title_but_value_not_empty(self) -> None:
        ctx = _ctx({
            "title": "用户名空时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False

    def test_illegal_chars_title_but_clean_value(self) -> None:
        ctx = _ctx({
            "title": "用户名包含非法字符登录",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False

    def test_wrong_title_but_known_correct_value(self) -> None:
        """标题说"用户名错误"，但 data 值是已知正确值 admin → mismatch。"""
        ctx = _ctx_with_provider({
            "title": "用户名错误时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False, f"Expected mismatch but got passed: {result.message}"

    def test_pool_ref_with_mismatch(self) -> None:
        """pool 引用解析后值不满足标题场景 → mismatch。"""
        ctx = _ctx_with_provider({
            "title": "用户名仅空格时点击登录提示错误",
            "data": {
                "username": {"source_type": "pool", "value": "username_admin"},
            },
        })
        result = TitleDataMismatchRule().validate(ctx)
        # username_admin 解析为 {"username": "admin"}，不含空格 → mismatch
        assert result.passed is False
        assert "空格" in result.message

    def test_empty_title_but_value_has_spaces(self) -> None:
        """标题说"空"，data 值是空格 → _v_empty 返回 False → mismatch。"""
        ctx = _ctx({
            "title": "用户名空时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "   "}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False
        assert "空" in result.message


class TestRule001Matches:
    """标题声称场景与 data 值一致 → 应通过。"""

    def test_spaces_title_with_space_value(self) -> None:
        ctx = _ctx({
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "   "}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_empty_title_with_empty_value(self) -> None:
        """标题说"空"，data 值为空字符串 → _v_empty 被调用且匹配。"""
        ctx = _ctx({
            "title": "用户名空时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": ""}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed
        # 验证 _v_empty 真正被调用：message 中应显示 username='' 而非 username='None'
        assert "username=''" in result.message, f"Expected empty string in message, got: {result.message}"

    def test_illegal_chars_with_special_value(self) -> None:
        ctx = _ctx({
            "title": "用户名包含非法字符登录",
            "data": {"username": {"source_type": "inline", "value": "admin<script>"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_too_short_boundary(self) -> None:
        ctx = _ctx({
            "title": "用户名长度小于最小边界值登录",
            "data": {"username": {"source_type": "inline", "value": "a"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_too_long_boundary(self) -> None:
        ctx = _ctx({
            "title": "密码长度大于最大边界值登录",
            "data": {"password": {"source_type": "inline", "value": "a" * 51}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_wrong_value_different_from_known_correct(self) -> None:
        """标题说"用户名错误"，data 值不是已知正确值 → 一致，通过。"""
        ctx = _ctx_with_provider({
            "title": "用户名错误时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "wronguser"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_pool_ref_resolved_and_matches(self) -> None:
        """pool 引用解析后值满足标题场景 → 通过。"""
        ctx = _ctx_with_provider({
            "title": "用户名仅空格时点击登录提示错误",
            "data": {
                "username": {"source_type": "pool", "value": "username_spaces"},
            },
        }, pools={
            "login": {
                "username_spaces": {"username": "   ", "password": "x"},
            },
        })
        result = TitleDataMismatchRule().validate(ctx)
        # username_spaces 解析为 {"username": "   "} → 含空格 → 匹配
        assert result.passed

    def test_pool_ref_resolved_empty_matches(self) -> None:
        """pool 引用解析为空字符串，标题说"空" → 匹配。"""
        ctx = _ctx_with_provider({
            "title": "用户名空时点击登录提示错误",
            "data": {
                "username": {"source_type": "pool", "value": "username_empty"},
            },
        }, pools={
            "login": {
                "username_empty": {"username": "", "password": "x"},
            },
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed
        assert "username=''" in result.message


class TestRule001EdgeCases:
    def test_no_title(self) -> None:
        ctx = _ctx({"data": {"username": {"source_type": "inline", "value": "x"}}})
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_no_recognized_field_skips(self) -> None:
        ctx = _ctx({
            "title": "重复点击登录按钮",
            "data": {},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed

    def test_pool_ref_without_provider_skips(self) -> None:
        """pool 引用但无 seed_data_provider → 无法解析，跳过。"""
        ctx = _ctx({
            "title": "用户名空时点击登录提示错误",
            "data": {
                "username": {"source_type": "pool", "value": "username_admin"},
            },
        })
        result = TitleDataMismatchRule().validate(ctx)
        # 无法解析 pool 引用 → _extract_value 返回 None → 跳过该 data_key
        # 所有 data_keys 被跳过 → 无 mismatch → passed
        assert result.passed

    def test_v_wrong_skipped_without_provider(self) -> None:
        """无 provider 时 '错误' 检查被跳过，passed 消息中应有警告。"""
        ctx = _ctx({
            "title": "用户名错误时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        # 无 provider → _v_wrong 无法判断 "admin" 是否为正确值 → 跳过检查 → passed
        # 但 message 中应包含警告
        assert result.passed
        assert "seed_data_provider 缺失" in result.message

    def test_mismatch_has_evidence(self) -> None:
        ctx = _ctx({
            "title": "用户名仅空格时点击登录提示错误",
            "data": {"username": {"source_type": "inline", "value": "admin"}},
        })
        result = TitleDataMismatchRule().validate(ctx)
        assert result.passed is False
        assert result.evidence["mismatches"]
        assert result.evidence["mismatches"][0]["data_key"] == "username"
