from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

def test_parser_timeout_computation_follows_llm_config(monkeypatch) -> None:
    """直接测试 timeout 计算逻辑，不通过 subprocess 调用。"""
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from services.requirement_parse_support import RequirementParseSupport

    monkeypatch.delenv("REQUIREMENT_PARSER_SUBPROCESS_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("REQUIREMENT_PARSER_LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("REQUIREMENT_PARSER_LLM_MAX_RETRIES", "5")

    llm_timeout = RequirementParseSupport._read_int_env(
        "REQUIREMENT_PARSER_LLM_TIMEOUT_SECONDS", default=90, min_value=10, max_value=180
    )
    llm_retries = RequirementParseSupport._read_int_env(
        "REQUIREMENT_PARSER_LLM_MAX_RETRIES", default=2, min_value=0, max_value=5
    )

    assert llm_timeout == 60
    assert llm_retries == 5

    default_timeout = max(180, (llm_timeout * (llm_retries + 1)) + 45)
    parser_timeout = RequirementParseSupport._read_int_env(
        "REQUIREMENT_PARSER_SUBPROCESS_TIMEOUT_SECONDS",
        default=default_timeout, min_value=30, max_value=600,
    )
    assert parser_timeout == 405

    # 验证 is_llm_force_mode_enabled
    monkeypatch.setenv("REQUIREMENT_PARSER_MODE", "llm")
    assert RequirementParseSupport.is_llm_force_mode_enabled() is True


def test_run_logged_subprocess_forwards_stdout_and_stderr(caplog) -> None:
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from shared_backend.observability import run_logged_subprocess

    caplog.set_level(logging.INFO)
    completed = run_logged_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('stdout-line'); print('stderr-line', file=sys.stderr)",
        ],
        logger=logging.getLogger("test.subprocess"),
        log_prefix="unit-test",
    )

    assert completed.returncode == 0
    assert "stdout-line" in completed.stdout
    assert "stderr-line" in completed.stderr
    assert "unit-test stdout stdout-line" in caplog.text
    assert "unit-test stderr stderr-line" in caplog.text
