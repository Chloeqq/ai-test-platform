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
