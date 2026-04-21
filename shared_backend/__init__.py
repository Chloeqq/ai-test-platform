"""Shared backend contracts and utilities."""

from .case_ids import (
    build_case_id,
    build_case_metadata,
    infer_case_type,
    infer_client_code,
    infer_module_code,
    infer_page_code,
    infer_source_code,
    match_case_id,
    next_case_sequence,
    normalize_case_id,
    slugify_case_part,
    split_run_id,
)
from .case_dictionary import (
    get_alias_code_map,
    get_code_name_map,
    get_dictionary_items,
    load_case_dictionaries,
    resolve_dictionary_code,
    resolve_dictionary_name,
)
from .case_rules import (
    CaseRuleViolation,
    enrich_case_metadata,
    validate_case_description,
    validate_case_payload,
    validate_case_title,
)
from .state_machines import (
    get_run_status_name,
    normalize_run_status,
)
from .execution_compiler import (
    ExecutionCompilerError,
    PreviewTestPointsCompiler,
    compile_execution_steps,
)

__all__ = [
    "build_case_id",
    "build_case_metadata",
    "CaseRuleViolation",
    "compile_execution_steps",
    "enrich_case_metadata",
    "ExecutionCompilerError",
    "get_dictionary_items",
    "get_run_status_name",
    "normalize_case_id",
    "normalize_run_status",
    "PreviewTestPointsCompiler",
    "validate_case_payload",
]
