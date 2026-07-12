"""Regression tests for the strict execution compiler pipeline contract."""
from __future__ import annotations

import pytest
from shared_backend.execution_compiler import (
    ExecutionCompilerError,
    compile_execution_steps,
    normalize_test_points,
    normalize_test_points_to_actions,
    build_execution_ir,
    bind_targets,
    render_execution_steps,
)


_SAMPLE_PAGE_OBJECT = {
    "elements": {
        "search_input": {"selector": "#search", "type": "css"},
        "product_list_title": {"selector": ".list-title", "type": "css"},
        "product_menu": {"selector": "[data-testid='product-menu']", "type": "css"},
    }
}


class TestIntentIdPrimary:
    """RC-1: intent_id is required and key must not backfill it."""

    def test_extract_intent_id_requires_intent_id_field(self) -> None:
        """intent_id must come from the intent_id field, not fall back to key."""
        points = [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "action": "fill",
                "target": "search_input",
                "value": "test",
                "description": "填写搜索框",
                "steps": [{"action": "fill", "target": "search_input", "value": "test", "raw_text": "填写搜索框"}],
                "involved_elements": ["search_input"],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["intent_id"] == "intent-01"

    def test_missing_intent_id_raises(self) -> None:
        """Points without intent_id must fail fast."""
        points = [
            {
                "key": "old-key",
                "action": "fill",
                "target": "search_input",
                "value": "test",
                "description": "填写搜索框",
                "steps": [{"action": "fill", "target": "search_input", "value": "test", "raw_text": "填写搜索框"}],
                "involved_elements": ["search_input"],
            }
        ]
        with pytest.raises(ExecutionCompilerError):
            normalize_test_points(points)

    def test_extract_intent_id_prefers_intent_id_over_key(self) -> None:
        points = [
            {
                "key": "old-key",
                "intent_id": "intent-02",
                "action": "click",
                "target": "product_menu",
                "description": "点击菜单",
                "steps": [{"action": "click", "target": "product_menu", "raw_text": "点击菜单"}],
                "involved_elements": ["product_menu"],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["intent_id"] == "intent-02"

    def test_intent_id_points_produce_resolved_ir(self) -> None:
        points = [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "action": "fill",
                "target": "search_input",
                "value": "test query",
                "description": "搜索商品",
                "steps": [{"action": "fill", "target": "search_input", "value": "test query", "raw_text": "搜索商品"}],
                "involved_elements": ["search_input"],
            }
        ]
        normalized = normalize_test_points(points)
        actions = normalize_test_points_to_actions(normalized)
        ir = build_execution_ir(actions)

        has_resolved = False
        for step in ir["steps"]:
            if step["meta"]["compiler_status"] == "resolved":
                has_resolved = True
            assert step["intent_id"] == "intent-01"
        assert has_resolved, "at least one step should be resolved when intent_id is explicitly provided"

    def test_compile_end_to_end_with_intent_id(self) -> None:
        points = [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "action": "fill",
                "target": "search_input",
                "value": "test",
                "description": "填写搜索",
                "steps": [{"action": "fill", "target": "search_input", "value": "test", "raw_text": "填写搜索"}],
                "involved_elements": ["search_input"],
            }
        ]
        steps = compile_execution_steps(points, _SAMPLE_PAGE_OBJECT)
        assert len(steps) > 0
        resolved_count = sum(
            1 for s in steps
            if s.get("traceability", {}).get("status") == "resolved"
            or s.get("traceability", {}).get("compiler_status") == "resolved"
        )
        assert resolved_count > 0, f"expected resolved steps, got: {steps}"

    def test_unknown_action_is_rejected(self) -> None:
        points = [
            {
                "key": "intent-strict-01",
                "intent_id": "intent-strict-01",
                "action": "unknown_action_xyz",
                "description": "不可识别的操作",
                "steps": [{"action": "unknown_action_xyz", "raw_text": "不可识别的操作"}],
                "involved_elements": ["search_input"],
            }
        ]
        with pytest.raises(ExecutionCompilerError):
            compile_execution_steps(points, {"elements": {}})


class TestInvolvedElements:
    """RC-2: compiler reads involved_elements only."""

    def test_involved_elements_are_read_directly(self) -> None:
        points = [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "action": "click",
                "involved_elements": ["product_menu"],
                "description": "点击产品菜单",
                "steps": [{"action": "click", "target": "product_menu", "raw_text": "点击产品菜单"}],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["involved_elements"] == ["product_menu"]

    def test_missing_involved_elements_yields_empty(self) -> None:
        """Without involved_elements, the list is empty."""
        points = [
            {
                "intent_id": "intent-01",
                "action": "click",
                "description": "搜索",
                "steps": [{"action": "click", "target": "product_menu", "raw_text": "搜索"}],
            }
        ]
        normalized = normalize_test_points(points)
        assert normalized[0]["involved_elements"] == []


class TestStepsStructurePassthrough:
    """RC-4: points with explicit steps list should be compiled as-is."""

    def test_explicit_steps_list_preserved(self) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "steps": [
                    {"action": "fill", "target": "search_input", "value": "query"},
                    {"action": "click", "target": "product_menu"},
                ],
            }
        ]
        normalized = normalize_test_points(points)
        assert len(normalized[0]["steps"]) == 2

    def test_action_step_passthrough_when_no_steps(self) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "action": "click",
                "target": "product_menu",
                "description": "点击菜单",
                "steps": [{"action": "click", "target": "product_menu", "raw_text": "点击菜单"}],
            }
        ]
        normalized = normalize_test_points(points)
        assert len(normalized[0]["steps"]) == 1
        assert normalized[0]["steps"][0]["action"] == "click"

    def test_multi_step_point_produces_multiple_ir_steps(self) -> None:
        points = [
            {
                "intent_id": "intent-01",
                "steps": [
                    {"action": "fill", "target": "search_input", "value": "query"},
                    {"action": "click", "target": "product_menu"},
                ],
            }
        ]
        normalized = normalize_test_points(points)
        actions = normalize_test_points_to_actions(normalized)
        ir = build_execution_ir(actions)
        assert len(ir["steps"]) >= 2


class TestBindTargets:
    """Verify selector binding against page object elements."""

    def test_known_target_binds_selector(self) -> None:
        ir = {
            "version": "execution-ir/v1",
            "steps": [
                {
                    "type": "input",
                    "target": "search_input",
                    "value": "test",
                    "assertion": None,
                    "intent_id": "intent-01",
                    "meta": {
                        "raw_text": "fill search",
                        "source_point_index": 0,
                        "source_step_index": 0,
                        "compiler_status": "resolved",
                        "compiler_reason": "",
                        "confidence": 1.0,
                    },
                }
            ],
        }
        bound = bind_targets(ir, _SAMPLE_PAGE_OBJECT)
        step = bound["steps"][0]
        assert step["selector"] == "#search"
        assert step["locator_type"] == "css"

    def test_unknown_target_rejected(self) -> None:
        ir = {
            "version": "execution-ir/v1",
            "steps": [
                {
                    "type": "click",
                    "target": "nonexistent_element",
                    "value": None,
                    "assertion": None,
                    "intent_id": "intent-01",
                    "meta": {
                        "raw_text": "click something",
                        "source_point_index": 0,
                        "source_step_index": 0,
                        "compiler_status": "resolved",
                        "compiler_reason": "",
                        "confidence": 1.0,
                    },
                }
            ],
        }
        with pytest.raises(ExecutionCompilerError):
            bind_targets(ir, _SAMPLE_PAGE_OBJECT)

    def test_human_readable_target_binds_to_canonical_code(self) -> None:
        page_object = {
            "elements": {
                "login_button": {
                    "selector": "登录",
                    "type": "role",
                    "role": "button",
                    "name": "登录按钮",
                }
            }
        }
        ir = {
            "version": "execution-ir/v1",
            "steps": [
                {
                    "type": "click",
                    "target": "登录按钮",
                    "value": None,
                    "assertion": None,
                    "intent_id": "intent-01",
                    "meta": {
                        "raw_text": "点击登录按钮",
                        "source_point_index": 0,
                        "source_step_index": 0,
                        "compiler_status": "resolved",
                        "compiler_reason": "",
                        "confidence": 1.0,
                    },
                }
            ],
        }
        bound = bind_targets(ir, page_object)
        step = bound["steps"][0]
        assert step["target"] == "login_button"
        assert step["selector"] == "登录"


class TestEndToEndCompile:
    """Full pipeline: orchestrator-like points → compiled executable steps."""

    def test_orchestrator_style_points_compile_successfully(self) -> None:
        """Simulates the exact shape produced by build_test_points_from_requirement_spec."""
        points = [
            {
                "key": "intent-01",
                "intent_id": "intent-01",
                "point_type": "action",
                "action": "fill",
                "target": "search_input",
                "value": "3",
                "description": "搜索商品",
                "priority": "P1",
                "involved_elements": ["search_input"],
                "steps": [{"action": "fill", "target": "search_input", "value": "3", "raw_text": "搜索商品"}],
                "metadata": {
                    "traceability": {
                        "intent_ids": ["intent-01"],
                        "source_ids": [],
                        "origin": "requirement_intent",
                    }
                },
            },
            {
                "key": "intent-02",
                "intent_id": "intent-02",
                "point_type": "action",
                "action": "assert_visible",
                "target": "product_list_title",
                "description": "验证列表标题可见",
                "priority": "P1",
                "involved_elements": ["product_list_title"],
                "steps": [{"action": "assert_visible", "target": "product_list_title", "raw_text": "验证列表标题可见"}],
                "metadata": {
                    "traceability": {
                        "intent_ids": ["intent-02"],
                        "source_ids": [],
                        "origin": "requirement_intent",
                    }
                },
            },
        ]
        steps = compile_execution_steps(points, _SAMPLE_PAGE_OBJECT)
        assert len(steps) >= 2

        resolved_steps = [
            s for s in steps
            if s.get("traceability", {}).get("status") == "resolved"
        ]
        assert len(resolved_steps) >= 1, f"expected at least 1 resolved step, got: {steps}"

        for step in resolved_steps:
            assert step.get("selector"), f"resolved step missing selector: {step}"
            assert step.get("intent_id"), f"resolved step missing intent_id: {step}"

    def test_assert_metric_compiles_to_runner_action(self) -> None:
        points = [
            {
                "intent_id": "intent-metric-01",
                "steps": [
                    {
                        "action": "assert_metric",
                        "target": "product_list_title",
                        "value": ">=1000",
                        "metric_label": "本周销售总额",
                        "extract_regex": r"(\d+(?:\.\d+)?)",
                        "raw_text": "验证本周销售总额大于等于1000",
                    }
                ],
            }
        ]
        steps = compile_execution_steps(points, _SAMPLE_PAGE_OBJECT)
        assert len(steps) == 1
        step = steps[0]
        assert step["action"] == "assert_metric"
        assert step["target"] == "product_list_title"
        assert step["value"] == ">=1000"
        assert step["metric_label"] == "本周销售总额"
        assert step["extract_regex"] == r"(\d+(?:\.\d+)?)"

    def test_assert_number_alias_is_normalized_to_assert_metric(self) -> None:
        points = [
            {
                "intent_id": "intent-metric-02",
                "steps": [
                    {
                        "action": "assert_number",
                        "target": "product_list_title",
                        "value": "positive",
                        "raw_text": "验证统计值为正数",
                    }
                ],
            }
        ]
        steps = compile_execution_steps(points, _SAMPLE_PAGE_OBJECT)
        assert len(steps) == 1
        assert steps[0]["action"] == "assert_metric"
        assert steps[0]["value"] == "positive"

    def test_password_toggle_business_type_can_be_clicked(self) -> None:
        page_object = {
            "elements": {
                "password_toggle": {
                    "selector": ".eye-toggle",
                    "type": "css",
                    "business_type": "password_toggle",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-password-toggle",
                "steps": [{"action": "click", "target": "密码显隐", "raw_text": "点击密码显隐"}],
                "involved_elements": ["密码显隐"],
            }
        ]

        steps = compile_execution_steps(points, page_object)

        assert steps[0]["action"] == "click"
        assert steps[0]["target"] == "password_toggle"

    def test_metric_label_business_type_can_be_assert_metric_target(self) -> None:
        page_object = {
            "elements": {
                "sales_total_metric_label": {
                    "selector": ".sales-total",
                    "type": "css",
                    "business_type": "metric_label",
                    "aliases": ["销售总额"],
                }
            }
        }
        points = [
            {
                "intent_id": "intent-metric-label",
                "steps": [
                    {
                        "action": "assert_metric",
                        "target": "销售总额",
                        "value": ">=1000",
                        "raw_text": "验证销售总额大于等于1000",
                    }
                ],
                "involved_elements": ["销售总额"],
            }
        ]

        steps = compile_execution_steps(points, page_object)

        assert steps[0]["action"] == "assert_metric"
        assert steps[0]["target"] == "sales_total_metric_label"

    def test_metric_value_business_type_cannot_be_clicked(self) -> None:
        page_object = {
            "elements": {
                "sales_total_metric_value": {
                    "selector": ".sales-total-value",
                    "type": "css",
                    "business_type": "metric_value",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-metric-value-click",
                "steps": [{"action": "click", "target": "sales_total_metric_value", "raw_text": "点击指标值"}],
                "involved_elements": ["sales_total_metric_value"],
            }
        ]

        with pytest.raises(ExecutionCompilerError) as exc:
            compile_execution_steps(points, page_object)

        assert exc.value.code == "target_binding_failed"
        assert "metric_value" in exc.value.reason

    def test_metric_value_business_type_cannot_be_assert_metric_target(self) -> None:
        page_object = {
            "elements": {
                "sales_total_metric_value": {
                    "selector": ".sales-total-value",
                    "type": "css",
                    "business_type": "metric_value",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-metric-value-assert",
                "steps": [
                    {
                        "action": "assert_metric",
                        "target": "sales_total_metric_value",
                        "value": ">=1000",
                        "raw_text": "验证指标值",
                    }
                ],
                "involved_elements": ["sales_total_metric_value"],
            }
        ]

        with pytest.raises(ExecutionCompilerError) as exc:
            compile_execution_steps(points, page_object)

        assert exc.value.code == "target_binding_failed"
        assert "metric_value" in exc.value.reason

    def test_button_business_type_cannot_be_assert_text_target(self) -> None:
        page_object = {
            "elements": {
                "login_submit_button": {
                    "selector": "login-submit-btn",
                    "type": "data-testid",
                    "role": "button",
                    "business_type": "button",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-04",
                "steps": [
                    {
                        "action": "assert_text",
                        "target": "login_submit_button",
                        "value": "请输入账号",
                        "raw_text": "页面提示请输入账号",
                    }
                ],
                "involved_elements": ["login_submit_button"],
            }
        ]

        with pytest.raises(ExecutionCompilerError) as exc:
            compile_execution_steps(points, page_object)

        assert exc.value.code == "target_binding_failed"
        assert "button" in exc.value.reason

    def test_button_role_without_business_type_cannot_be_assert_text_target(self) -> None:
        page_object = {
            "elements": {
                "login_submit_button": {
                    "selector": "login-submit-btn",
                    "type": "data-testid",
                    "role": "button",
                    "business_type": "",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-04",
                "steps": [
                    {
                        "action": "assert_text",
                        "target": "login_submit_button",
                        "value": "请输入账号",
                    }
                ],
                "involved_elements": ["login_submit_button"],
            }
        ]

        with pytest.raises(ExecutionCompilerError) as exc:
            compile_execution_steps(points, page_object)

        assert exc.value.code == "target_binding_failed"
        assert "role `button`" in exc.value.reason

    def test_non_button_role_without_business_type_can_be_assert_text_target(self) -> None:
        page_object = {
            "elements": {
                "login_username_error": {
                    "selector": ".el-form-item__error",
                    "type": "css",
                    "role": "alert",
                    "business_type": "",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-04",
                "steps": [
                    {
                        "action": "assert_text",
                        "target": "login_username_error",
                        "value": "请输入正确的用户名",
                    }
                ],
                "involved_elements": ["login_username_error"],
            }
        ]

        steps = compile_execution_steps(points, page_object)

        assert len(steps) == 1
        assert steps[0]["action"] == "assert_text"
        assert steps[0]["target"] == "login_username_error"

    def test_text_business_type_can_be_assert_text_target(self) -> None:
        page_object = {
            "elements": {
                "login_username_error": {
                    "selector": ".el-form-item__error",
                    "type": "css",
                    "role": "alert",
                    "business_type": "text",
                }
            }
        }
        points = [
            {
                "intent_id": "intent-04",
                "steps": [
                    {
                        "action": "assert_text",
                        "target": "login_username_error",
                        "value": "请输入正确的用户名",
                        "raw_text": "验证用户名错误提示",
                    }
                ],
                "involved_elements": ["login_username_error"],
            }
        ]

        steps = compile_execution_steps(points, page_object)

        assert len(steps) == 1
        assert steps[0]["action"] == "assert_text"
        assert steps[0]["target"] == "login_username_error"
        assert steps[0]["role"] == "alert"
        assert steps[0]["value"] == "请输入正确的用户名"


class TestStrictCompilerFailures:
    """Compiler must fail hard instead of returning partial output."""

    def test_unknown_action_is_rejected_in_compile(self) -> None:
        points = [
            {
                "key": "strict-01",
                "intent_id": "strict-01",
                "action": "nonexistent_action_xyz",
                "description": "unresolvable action",
                "steps": [{"action": "nonexistent_action_xyz", "raw_text": "unresolvable action"}],
                "involved_elements": ["search_input"],
            }
        ]
        with pytest.raises(ExecutionCompilerError):
            compile_execution_steps(points, {"elements": {}})

    def test_known_points_compile_strictly(self) -> None:
        points = [
            {
                "key": "ok-01",
                "intent_id": "ok-01",
                "action": "fill",
                "target": "search_input",
                "value": "x",
                "description": "ok",
                "steps": [{"action": "fill", "target": "search_input", "value": "x", "raw_text": "ok"}],
                "involved_elements": ["search_input"],
            },
            {
                "key": "ok-02",
                "intent_id": "ok-02",
                "action": "click",
                "target": "product_menu",
                "description": "ok",
                "steps": [{"action": "click", "target": "product_menu", "raw_text": "ok"}],
                "involved_elements": ["product_menu"],
            },
            {
                "key": "ok-03",
                "intent_id": "ok-03",
                "action": "assert_visible",
                "target": "product_list_title",
                "description": "ok",
                "steps": [{"action": "assert_visible", "target": "product_list_title", "raw_text": "ok"}],
                "involved_elements": ["product_list_title"],
            },
        ]
        steps = compile_execution_steps(points, _SAMPLE_PAGE_OBJECT)
        assert len(steps) == 3
        assert all((s.get("traceability") or {}).get("status") == "resolved" for s in steps)
