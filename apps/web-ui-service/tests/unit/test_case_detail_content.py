from __future__ import annotations

from pathlib import Path

from app.models.test_case import TestCase as DbTestCase
from app.services import test_case_mapper


GENERIC_EXPECTED = "系统应给出符合业务规则的反馈。"


def _write_case_yaml(path: Path, requirement_block: str, *, title: str, description: str) -> None:
    path.write_text(
        "\n".join(
            [
                f"title: {title}",
                f"description: {description}",
                "requirement:",
                f"  - |-\n{''.join(f'      {line}\n' for line in requirement_block.splitlines())}".rstrip(),
                "  - '[P0] 首次登录成功'",
                "  - '[P1] 用户名空登录提示'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _build_case(source_ref: Path, *, case_id: str, name: str) -> DbTestCase:
    return DbTestCase(
        case_id=case_id,
        name=name,
        case_type="fn",
        test_type="ui",
        source_ref=str(source_ref),
        expected_result=GENERIC_EXPECTED,
        test_steps=[],
        test_steps_text="",
    )


def test_detail_content_restores_timeout_case_from_source_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "timeout.yaml"
    _write_case_yaml(
        yaml_path,
        "\n".join(
            [
                "登录功能：",
                "- 正确账号密码可登录成功",
                "- 未登录不能访问首页",
                "测试意图：登录超时提示",
                "测试类型：interaction_exception",
                "前置条件：用户处于未登录状态，登录页面已打开，模拟弱网环境",
                "操作步骤：",
                "1. 在用户名输入框输入正确用户名 test001",
                "2. 在密码输入框输入正确密码 123456",
                "3. 点击登录按钮",
                "涉及元素：用户名输入框、密码输入框、登录按钮",
            ]
        ),
        title="登录超时提示",
        description="在模拟弱网环境下，验证登录超时提示功能。前置条件：用户处于未登录状态，登录页面已打开，模拟弱网环境。",
    )

    detail = test_case_mapper._build_detail_content(
        _build_case(yaml_path, case_id="atp-web-login-auth-fn-ai-0088", name="登录超时提示")
    )

    assert detail["test_intent"] == "登录超时提示"
    assert detail["test_type"] == "interaction_exception"
    assert detail["precondition"] == ["用户处于未登录状态", "登录页面已打开", "模拟弱网环境"]
    assert detail["operation_steps"] == [
        "在用户名输入框输入正确用户名 test001",
        "在密码输入框输入正确密码 123456",
        "点击登录按钮",
    ]
    assert detail["involved_elements"] == ["用户名输入框", "密码输入框", "登录按钮"]
    assert detail["overall_expected"] == []
    assert detail["assertion_points"] == []
    assert "overall_expected" in detail["missing_sections"]
    assert "assertion_points" in detail["missing_sections"]


def test_detail_content_keeps_negative_lock_case_negative(tmp_path: Path) -> None:
    yaml_path = tmp_path / "locked.yaml"
    _write_case_yaml(
        yaml_path,
        "\n".join(
            [
                "登录功能：",
                "- 正确账号密码可登录成功",
                "测试意图：账号锁定登录提示",
                "测试类型：negative",
                "前置条件：用户账号处于锁定状态，登录页面已打开",
                "操作步骤：",
                "1. 在用户名输入框输入正确用户名 test001",
                "2. 在密码输入框输入正确密码 123456",
                "3. 点击登录按钮",
                "涉及元素：用户名输入框、密码输入框、登录按钮",
            ]
        ),
        title="账号锁定登录提示",
        description="验证锁定账号登录时是否给出明确提示。",
    )

    detail = test_case_mapper._build_detail_content(
        _build_case(yaml_path, case_id="atp-web-login-auth-fn-ai-0099", name="账号锁定登录提示")
    )

    assert detail["test_intent"] == "账号锁定登录提示"
    assert detail["test_type"] == "negative"
    assert detail["overall_expected"] == []
    assert detail["assertion_points"] == []
    assert "overall_expected" in detail["missing_sections"]


def test_detail_content_filters_requirement_blob_from_expected_result(tmp_path: Path) -> None:
    yaml_path = tmp_path / "blob.yaml"
    _write_case_yaml(
        yaml_path,
        "\n".join(
            [
                "登录功能：",
                "- 正确账号密码可登录成功",
                "测试意图：登录超时提示",
                "测试类型：interaction_exception",
            ]
        ),
        title="登录超时提示",
        description="登录超时提示描述",
    )

    case = _build_case(yaml_path, case_id="atp-web-login-auth-fn-ai-0100", name="登录超时提示")
    case.expected_result = (
        "登录功能：\n- 正确账号密码可登录成功\n测试意图：登录超时提示\n测试类型：interaction_exception\n"
    )

    detail = test_case_mapper._build_detail_content(case)

    assert detail["overall_expected"] == []
