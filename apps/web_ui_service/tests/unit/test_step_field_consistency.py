"""跨函数一致性测试：确保 step 字典重建函数不会静默丢弃 DSL 字段。

背景见 shared_backend/step_fields.py 的模块说明：项目里有多处独立维护
"按固定字段重建 step 字典"的代码，2026-06-29 debug 密码可见性切换用例时
因为漏改其中一处（_productize_workbench_steps_for_script），导致用例能
生成、quality gate 也通过，但实际执行报 schema 校验失败——中间隔了好几层
才暴露问题。这个测试把同一个"全字段"step 喂给每个已知的重建函数，断言
非定位类字段都被保留，新增字段忘改某处时这里会直接报错。
"""
from __future__ import annotations

from app.services import test_case_data_service
from app.services.test_case_service import _productize_workbench_steps_for_script
from app.services.workbench_generation_compiler.runtime import generate_pipeline as generate_pipeline_module
from shared_backend.step_fields import STEP_FIELD_NAMES

# 这些字段在"产品化"步骤里故意不出现：locator_type/locator_value/role/
# page/element_code/selector 是绑定前的定位信息，到 bind_targets 阶段会
# 被 page_object 的治理结果覆盖；intent_id/traceability 是编译期 IR 内部
# 记账字段，不应该出现在面向人/runner 的最终步骤里。
_LOCATOR_RESOLVED_FIELDS = frozenset(
    {"locator_type", "locator_value", "role", "page", "element_code", "selector", "intent_id", "traceability"}
)


def _full_step() -> dict[str, object]:
    """包含 STEP_FIELD_NAMES 里每个字段的 assert_attribute 步骤样本。"""
    return {
        "action": "assert_attribute",
        "target": "element:login-password-input",
        "target_name": "密码输入框",
        "value": "password",
        "expected": "密码从明文变为密文显示",
        "expected_result": "密码从明文变为密文显示",
        "description": "校验密码框已切回密文",
        "page": "login",
        "selector": "login-password-input",
        "locator_type": "data-testid",
        "locator_value": "login-password-input",
        "role": "",
        "intent_id": "intent-27",
        "element_code": "login-password-input",
        "count": "",
        "metric_rule": "",
        "rule": "",
        "extract_regex": "",
        "metric_label": "",
        "attribute": "type",
        "data_ref": "",
        "raw_text": "assert_attribute:密码输入框.type=password",
        "source_point_key": "intent-27",
        "traceability": {},
    }


def test_step_field_names_covers_full_sample() -> None:
    """样本字典必须覆盖 STEP_FIELD_NAMES 的全集，否则下面的断言没意义。"""
    assert set(_full_step().keys()) == set(STEP_FIELD_NAMES)


def test_normalize_test_steps_preserves_non_empty_fields() -> None:
    normalized = test_case_data_service.normalize_test_steps([_full_step()])
    assert len(normalized) == 1
    row = normalized[0]
    for field_name in STEP_FIELD_NAMES:
        original_value = _full_step()[field_name]
        if str(original_value or "").strip():
            assert field_name in row, f"normalize_test_steps 丢掉了字段 {field_name!r}"


def test_format_product_execution_steps_preserves_non_locator_fields() -> None:
    step = _full_step()
    rendered = generate_pipeline_module._format_product_execution_steps(
        compiled_steps=[step],
        page="login",
        page_url="http://localhost:5174/#/login",
        page_object={"elements": {}},
        expected_by_intent={},
    )
    assert len(rendered) == 1
    row = rendered[0]
    for field_name in STEP_FIELD_NAMES - _LOCATOR_RESOLVED_FIELDS - {"description", "expected", "data_ref", "raw_text"}:
        original_value = step[field_name]
        if str(original_value or "").strip():
            assert field_name in row, f"_format_product_execution_steps 丢掉了字段 {field_name!r}"
    # attribute 是这次真实踩坑的字段，单独断言具体值，不只是断言"key 存在"。
    assert row.get("attribute") == "type"


def test_productize_workbench_steps_for_script_preserves_attribute() -> None:
    """这正是 2026-06-29 真实踩坑的位置——script_code 是实际执行读取的那份文本。"""
    step = _full_step()
    case_yaml = {"execution": {"steps": [step]}, "expected_result": ""}
    product_steps = _productize_workbench_steps_for_script(case_yaml)
    assert len(product_steps) == 1
    row = product_steps[0]
    for field_name in STEP_FIELD_NAMES - _LOCATOR_RESOLVED_FIELDS - {"description", "expected", "data_ref", "raw_text", "intent_id"}:
        original_value = step[field_name]
        if str(original_value or "").strip():
            assert field_name in row, f"_productize_workbench_steps_for_script 丢掉了字段 {field_name!r}"
    assert row.get("attribute") == "type"
