"""测试 RULE_009 — ASSERTION_TARGET_INVALID 和 RULE_010 — STEP_DATA_INCONSISTENCY。"""

from __future__ import annotations

from shared_backend.quality_gate import GateContext
from app.services.quality_gate.rules.rule_009_assertion_target_invalid import (
    AssertionTargetInvalidRule,
)
from app.services.quality_gate.rules.rule_010_step_data_inconsistency import (
    StepDataInconsistencyRule,
)

PAGE_OBJECT = {
    "page": "login",
    "elements": {
        "username_input": {"business_type": "input", "name": "用户名输入框"},
        "password_input": {"business_type": "input", "name": "密码输入框"},
        "login_button": {"business_type": "button", "name": "登录按钮"},
        "error_toast": {"business_type": "message", "name": "错误提示"},
        "home_menu": {"business_type": "menu", "name": "首页菜单"},
        "volume_slider": {"business_type": "slider", "name": "音量滑块"},
        "loading_bar": {"business_type": "progressbar", "name": "加载进度条"},
    },
}


class TestRule009:
    def test_element_not_in_page_object_is_skipped(self) -> None:
        """元素不存在由 RULE_006 负责，RULE_009 静默跳过不重复报告。"""
        ctx = GateContext(case_yaml={
            "title": "登录成功",
            "execution": {"steps": [
                {"action": "assert_text", "target": "element:nonexistent"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed
        assert "assert_text" in result.message

    def test_assert_text_on_button_is_allowed(self) -> None:
        """button 可含可读文本("登录")，白名单思路下放行。"""
        ctx = GateContext(case_yaml={
            "title": "验证按钮文本",
            "execution": {"steps": [
                {"action": "assert_text", "target": "element:login_button"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed

    def test_assert_text_on_slider_is_blocked(self) -> None:
        """slider 是纯视觉控件，不可能含文本 → 拦截。"""
        ctx = GateContext(case_yaml={
            "title": "验证滑块",
            "execution": {"steps": [
                {"action": "assert_text", "target": "element:volume_slider"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed is False
        assert any("slider" in i for i in result.evidence.get("issues", []))

    def test_assert_text_on_progressbar_is_blocked(self) -> None:
        """progressbar 是纯视觉控件 → 拦截。"""
        ctx = GateContext(case_yaml={
            "title": "验证进度条",
            "execution": {"steps": [
                {"action": "assert_text", "target": "element:loading_bar"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed is False

    def test_assert_text_on_message_is_compatible(self) -> None:
        ctx = GateContext(case_yaml={
            "title": "验证错误提示",
            "execution": {"steps": [
                {"action": "assert_text", "target": "element:error_toast"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed

    def test_assert_visible_not_checked(self) -> None:
        """assert_visible 适用于所有元素类型，不检查 business_type。"""
        ctx = GateContext(case_yaml={
            "title": "验证可见性",
            "execution": {"steps": [
                {"action": "assert_visible", "target": "element:volume_slider"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed

    def test_assert_url_not_checked(self) -> None:
        """assert_url 不绑定 element，不在检查范围。"""
        ctx = GateContext(case_yaml={
            "title": "验证 URL",
            "execution": {"steps": [
                {"action": "assert_url", "target": "element:home_menu"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed

    def test_no_assertion_steps_passes(self) -> None:
        ctx = GateContext(case_yaml={
            "title": "仅输入操作",
            "execution": {"steps": [
                {"action": "input", "target": "element:username_input", "value": "admin"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = AssertionTargetInvalidRule().validate(ctx)
        assert result.passed


class TestRule010:
    def test_dangling_var_referenced_by_step_is_error(self) -> None:
        """被步骤引用的悬挂变量 → ERROR（运行时必然失败）。"""
        ctx = GateContext(case_yaml={
            "title": "登录",
            "data": {"username": "admin"},
            "execution": {
                "variables": {
                    "login_username": "{{username}}",
                    "login_password": "{{password}}",  # ← 悬挂引用，且被步骤使用
                },
                "steps": [
                    {"action": "input", "target": "element:username_input", "value": "{{login_username}}"},
                    {"action": "input", "target": "element:password_input", "value": "{{login_password}}"},
                ],
            },
        }, page_object=PAGE_OBJECT)
        result = StepDataInconsistencyRule().validate(ctx)
        assert result.passed is False
        assert "ERROR" in result.message or result.severity.value == "error"
        assert any("login_password" in i for i in result.evidence.get("errors", []))

    def test_dangling_var_unreferenced_is_warning(self) -> None:
        """声明但未被任何步骤引用的悬挂变量 → WARNING（死代码）。"""
        ctx = GateContext(case_yaml={
            "title": "登录",
            "data": {"username": "admin"},
            "execution": {
                "variables": {
                    "login_username": "{{username}}",
                    "unused_var": "{{nonexistent}}",  # ← 悬挂且未使用
                },
                "steps": [
                    {"action": "input", "target": "element:username_input", "value": "{{login_username}}"},
                ],
            },
        }, page_object=PAGE_OBJECT)
        result = StepDataInconsistencyRule().validate(ctx)
        assert result.passed is False
        assert len(result.evidence.get("errors", [])) == 0  # 无 ERROR
        assert any("unused_var" in i for i in result.evidence.get("warnings", []))

    def test_clean_chain_passes(self) -> None:
        ctx = GateContext(case_yaml={
            "title": "登录",
            "data": {"username": "admin", "password": "xxx"},
            "execution": {
                "variables": {
                    "login_username": "{{username}}",
                    "login_password": "{{password}}",
                },
                "steps": [
                    {"action": "input", "target": "element:username_input", "value": "{{login_username}}"},
                    {"action": "input", "target": "element:password_input", "value": "{{login_password}}"},
                ],
            },
        }, page_object=PAGE_OBJECT)
        result = StepDataInconsistencyRule().validate(ctx)
        assert result.passed

    def test_no_data_or_variables_passes(self) -> None:
        ctx = GateContext(case_yaml={
            "title": "仅点击操作",
            "execution": {"steps": [
                {"action": "click", "target": "element:login_button"},
            ]},
        }, page_object=PAGE_OBJECT)
        result = StepDataInconsistencyRule().validate(ctx)
        assert result.passed
        assert "无需检查" in result.message

    def test_input_step_count_vs_data_key_imbalance(self) -> None:
        """3 个 input 步骤但只解析到 1 个 data key → WARNING。"""
        ctx = GateContext(case_yaml={
            "title": "重复输入",
            "data": {"username": "admin"},
            "execution": {
                "variables": {"u": "{{username}}"},
                "steps": [
                    {"action": "input", "target": "element:username_input", "value": "{{u}}"},
                    {"action": "input", "target": "element:password_input", "value": "{{u}}"},
                    {"action": "input", "target": "element:username_input", "value": "{{u}}"},
                ],
            },
        }, page_object=PAGE_OBJECT)
        result = StepDataInconsistencyRule().validate(ctx)
        assert result.passed is False
        assert any("步骤与数据不匹配" in i or "同 key 合理复用" in i
                   for i in result.evidence.get("warnings", []))
