from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.page_element_code_policy import (
    require_valid_element_code,
    suggest_business_element_code,
    suggest_element_code,
    validate_element_code_policy,
)


def test_policy_accepts_business_snake_case_code() -> None:
    result = validate_element_code_policy("username_input", page_code="login", business_type="input")

    assert result.valid is True
    assert result.normalized_code == "username_input"
    assert result.errors == ()


def test_policy_accepts_real_data_testid_kebab_case_with_testid_context() -> None:
    result = validate_element_code_policy(
        "login-submit-btn",
        page_code="login",
        business_type="button",
        locator_source="testid",
        locator_type="data-testid",
        testid_value="login-submit-btn",
    )

    assert result.valid is True
    assert result.errors == ()


def test_policy_rejects_kebab_case_without_testid_context() -> None:
    result = validate_element_code_policy("login-submit-btn", page_code="login", business_type="button")

    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    ("code", "page_code", "business_type"),
    [
        ("order_no_column", "order", "table"),
        ("product_name_input", "product", "input"),
        ("user_role_select", "user", "input"),
        ("rich_text_editor", "article", "input"),
    ],
)
def test_policy_accepts_business_terms_that_overlap_page_or_locator_words(
    code: str,
    page_code: str,
    business_type: str,
) -> None:
    result = validate_element_code_policy(code, page_code=page_code, business_type=business_type)

    assert result.valid is True
    assert result.errors == ()


@pytest.mark.parametrize(
    ("code", "business_type"),
    [
        ("login-css-i-path-3", ""),
        ("text_2", ""),
        ("button_1", "button"),
        ("page_login_username_input", "input"),
        ("eye_icon", "password_toggle"),
        ("sales_text", "metric_value"),
    ],
)
def test_policy_rejects_dirty_formal_element_codes(code: str, business_type: str) -> None:
    result = validate_element_code_policy(code, page_code="login", business_type=business_type)

    assert result.valid is False
    assert result.errors


def test_policy_suggests_password_toggle_for_password_semantics() -> None:
    assert suggest_element_code("login-css-i-path-3", page_code="login", business_type="password_toggle") == "password_toggle"


def test_policy_does_not_suggest_invalid_leftover_noise() -> None:
    assert suggest_element_code("login-css-i-path-3", page_code="login") == ""


def test_policy_suggests_metric_suffix_for_metric_semantics() -> None:
    assert suggest_element_code("sales_text", page_code="home", business_type="metric_value") == "sales_metric_value"


@pytest.mark.parametrize(
    ("text", "business_type", "expected"),
    [
        ("查询结果", "button", "search_result_button"),
        ("审核通过", "button", "review_approved_button"),
        ("请输入用户名", "input", "username_input"),
        ("请输入密码", "input", "password_input"),
    ],
)
def test_policy_suggests_business_codes_for_chinese_candidates(
    text: str,
    business_type: str,
    expected: str,
) -> None:
    assert suggest_business_element_code(text, page_code="product", business_type=business_type) == expected


def test_policy_does_not_embed_mall_domain_terms_globally() -> None:
    assert suggest_business_element_code("商品货号：", page_code="product", business_type="input") == ""


def test_require_valid_element_code_raises_readable_payload() -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_valid_element_code("page_login_username_input", page_code="login", business_type="input")

    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "invalid_element_code"
    assert "username_input" in str(detail.get("suggested_code", ""))
