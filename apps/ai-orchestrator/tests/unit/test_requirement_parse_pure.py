"""requirement_parse_support 纯函数测试（无 DB/LLM/子进程依赖）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_root = Path(__file__).resolve().parents[2] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from services.requirement_parse_support import RequirementParseSupport


class TestInferPageFromText:
    def test_matches_login_keyword(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="用户输入账号密码进行登录"
        )
        assert result == "login"

    def test_matches_order_keyword(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="用户查看订单列表"
        )
        assert result == "order"

    def test_matches_product_keyword(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="浏览商品详情页"
        )
        assert result == "product"

    def test_matches_home_keyword(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="返回首页"
        )
        assert result == "home"

    def test_returns_empty_for_unknown(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="一些无关文本"
        )
        assert result == ""

    def test_case_insensitive(self) -> None:
        result = RequirementParseSupport.infer_page_from_text(
            requirement="用户 LOGIN 系统"
        )
        assert result == "login"

    def test_returnapply_matches_first_in_mapping_order(self) -> None:
        # "退货" 在映射中最靠前，先被匹配
        result = RequirementParseSupport.infer_page_from_text(
            requirement="用户申请退货退款"
        )
        assert result == "returnapply"


class TestExtractJsonObject:
    def test_extracts_valid_json(self) -> None:
        result = RequirementParseSupport._extract_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extracts_json_with_surrounding_text(self) -> None:
        result = RequirementParseSupport._extract_json_object(
            'some prefix text {"result": "ok"} some suffix'
        )
        assert result == {"result": "ok"}

    def test_returns_empty_dict_for_invalid(self) -> None:
        result = RequirementParseSupport._extract_json_object("not json")
        assert result == {}

    def test_returns_empty_dict_for_empty(self) -> None:
        result = RequirementParseSupport._extract_json_object("")
        assert result == {}


class TestCompactSubprocessError:
    def test_returns_last_line_when_json_extraction_fails(self) -> None:
        result = RequirementParseSupport._compact_subprocess_error(
            stdout="line one\nline two\nline three",
            stderr="",
            default_message="default",
        )
        assert "line three" in result

    def test_falls_back_to_stderr_when_stdout_empty(self) -> None:
        result = RequirementParseSupport._compact_subprocess_error(
            stdout="",
            stderr="Error: something failed\n",
            default_message="default",
        )
        assert "Error: something failed" in result

    def test_falls_back_to_default_when_both_empty(self) -> None:
        result = RequirementParseSupport._compact_subprocess_error(
            stdout="",
            stderr="",
            default_message="no output captured",
        )
        assert result == "no output captured"


class TestEstimateInputScope:
    def test_empty_text_is_ok(self) -> None:
        result = RequirementParseSupport.estimate_input_scope("")
        assert result["level"] == "ok"
        assert result["estimated_input_tokens"] == 0
        assert result["version"] == "RequirementScopeEstimateV1"

    def test_short_chinese_is_ok(self) -> None:
        result = RequirementParseSupport.estimate_input_scope("登录功能需求描述")
        assert result["level"] == "ok"
        assert result["cjk_char_count"] == 8

    def test_cjk_uses_1_6_divisor(self) -> None:
        # 1600 CJK chars / 1.6 = 1000 tokens
        result = RequirementParseSupport.estimate_input_scope("需" * 1600)
        assert result["estimated_input_tokens"] == 1000

    def test_non_cjk_uses_4_0_divisor(self) -> None:
        # 4000 ascii chars / 4.0 = 1000 tokens
        result = RequirementParseSupport.estimate_input_scope("a" * 4000)
        assert result["estimated_input_tokens"] == 1000

    def test_warn_level_at_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIREMENT_SCOPE_WARN_TOKENS", "8000")
        monkeypatch.setenv("REQUIREMENT_SCOPE_BLOCK_TOKENS", "16000")
        # 20000 CJK / 1.6 = 12500 → warn
        result = RequirementParseSupport.estimate_input_scope("需" * 20000)
        assert result["level"] == "warn"

    def test_block_level_over_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIREMENT_SCOPE_WARN_TOKENS", "8000")
        monkeypatch.setenv("REQUIREMENT_SCOPE_BLOCK_TOKENS", "16000")
        # 30000 CJK / 1.6 = 18750 → block
        result = RequirementParseSupport.estimate_input_scope("需" * 30000)
        assert result["level"] == "block"
        assert "超上限" in result["message"]

    def test_thresholds_env_overridable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIREMENT_SCOPE_WARN_TOKENS", "100")
        monkeypatch.setenv("REQUIREMENT_SCOPE_BLOCK_TOKENS", "200")
        result = RequirementParseSupport.estimate_input_scope("需" * 320)  # 200 tokens → block
        assert result["level"] == "block"

    def test_block_falls_back_when_le_warn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # block <= warn 时自动取 warn*2，避免配置错误导致 block 永远命中
        monkeypatch.setenv("REQUIREMENT_SCOPE_WARN_TOKENS", "8000")
        monkeypatch.setenv("REQUIREMENT_SCOPE_BLOCK_TOKENS", "1000")
        result = RequirementParseSupport.estimate_input_scope("需" * 1600)  # 1000 tokens
        assert result["block_tokens"] == 16000
        assert result["level"] == "ok"


class TestBuildScopeText:
    def test_joins_all_sources(self) -> None:
        text = RequirementParseSupport.build_scope_text(
            requirement="需求正文",
            prd_text="PRD 内容",
            input_sources=[{"content": "额外来源"}, {"no_content": "x"}],
        )
        assert "需求正文" in text
        assert "PRD 内容" in text
        assert "额外来源" in text

    def test_skips_empty_and_non_str(self) -> None:
        text = RequirementParseSupport.build_scope_text(
            requirement="仅此一段",
            prd_text="   ",
            input_sources=[{"content": 123}],
        )
        assert text == "仅此一段"
