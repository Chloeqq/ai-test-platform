"""验证 generate_pipeline 子模块的 _svc() 惰性导入链完整性。

每个子模块通过 _svc() 惰性查找主模块来访问关键符号。
如果某个符号被重命名/删除/忘记 re-export，_svc() 调用会在运行时崩溃。
此测试确保所有依赖链上的符号都不会断裂。
"""
from __future__ import annotations

import pytest


def _assert_svc_resolves(module, expected_symbols: list[str], source_module: str):
    """验证 module._svc() 返回的对象拥有所有 expected_symbols。"""
    svc = module._svc()
    missing = [s for s in expected_symbols if not hasattr(svc, s)]
    if missing:
        pytest.fail(
            f"{source_module}._svc() 缺少 {len(missing)} 个符号:\n  "
            + "\n  ".join(missing)
        )


# ---- generate_pipeline_format ----


def test_format_direct_imports_product_symbols():
    """format 模块不使用 _svc()，改为验证直接导入的符号可用。"""
    from app.services.workbench_generation_compiler.runtime import (
        generate_pipeline_format as fmt,
    )

    expected = [
        "_product_description", "_product_locator", "_product_element_meta",
        "_format_product_execution_steps", "_enrich_product_case_yaml_v1_1",
        "_enrich_dsl_v1_1_data_bindings", "_normalize_dsl_data_sources",
        "_product_step_expected", "_append_login_success_assertion",
        "_step_element_code",
    ]
    missing = [s for s in expected if not hasattr(fmt, s)]
    if missing:
        pytest.fail(f"format 模块缺少符号:\n  " + "\n  ".join(missing))


# ---- generate_pipeline_orchestrate ----


def test_orchestrate_svc_resolves_resolve_symbols():
    from app.services.workbench_generation_compiler.runtime import (
        generate_pipeline_orchestrate as orch,
    )

    _assert_svc_resolves(
        orch,
        [
            "_normalized_text",
            "_is_qualified_formal_element",
            "_element_display_name",
            "_infer_element_aliases",
            "_list_text",
            "_resolve_page_object_from_db",
            "_resolve_page_object_from_assets",
            "resolve_page_object",
            "_extract_selected_intent_ids",
            "_execution_intent_ids",
            "_find_candidate_snapshot_by_intent",
            "_intent_product_metadata",
            "SessionLocal",
        ],
        "generate_pipeline_orchestrate",
    )


# ---- generate_pipeline_steps ----


def test_steps_svc_resolves_pipeline_symbols():
    from app.services.workbench_generation_compiler.runtime import (
        generate_pipeline_steps as steps,
    )

    _assert_svc_resolves(
        steps,
        [
            "_normalized_text",
            "_LOGGER",
            "_COMPILER_ERROR_CODES",
            "_log_generation_failure",
            "_redact_generation_payload",
            "_resolve_page_object_from_db",
            "_load_page_object_from_db",
            "_resolve_page_object_from_assets",
            "resolve_page_object",
            "_extract_selected_intent_ids",
            "_format_product_case_yaml",
            "_enrich_product_case_yaml_v1_1",
            "_build_direct_candidate_orchestrator_result",
            "_extract_candidate_snapshots",
            "_enrich_test_points_with_candidate_snapshots",
            "SessionLocal",
        ],
        "generate_pipeline_steps",
    )
