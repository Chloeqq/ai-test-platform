from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace


def test_requirement_parser_subprocess_timeout_defaults_follow_llm_config(monkeypatch) -> None:
    import sys

    src_root = Path(__file__).resolve().parents[2] / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from services.requirement_parse_support import RequirementParseSupport

    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        captured["env"] = kwargs.get("env", {})
        return SimpleNamespace(
            returncode=0,
            stdout='{"page":"login","priority":"P1","parse_confidence":0.9,"test_intents":[{"title":"t","intent_type":"functional","priority":"P1","steps":["s"],"expected_result":"ok","involved_elements":[]}],"business_rules":[],"ambiguities":[],"parser_runtime":{"mode":"llm","model":"fake","prompt_version":"p","instructions_version":"i"}}',
            stderr="",
        )

    monkeypatch.delenv("REQUIREMENT_PARSER_SUBPROCESS_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("REQUIREMENT_PARSER_LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("REQUIREMENT_PARSER_LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("REQUIREMENT_PARSER_MODE", "llm")
    monkeypatch.setattr("services.requirement_parse_support.run_logged_subprocess", fake_run)

    support = RequirementParseSupport(
        repo_root=Path("/tmp"),
        requirement_parser_root=Path("/tmp/requirement-parser-agent"),
        build_fallback_multisource_context=lambda **_kwargs: {"source_inputs": []},
        harmonize_requirement_spec=lambda **kwargs: kwargs["requirement_spec"],
        infer_page_from_text=lambda **_kwargs: "login",
        rank_page_candidates=lambda **_kwargs: [],
    )

    result = support.parse_requirement_spec(requirement="验证登录功能", page="login", source="manual")

    assert captured["timeout"] == 405
    assert result["page"] == "login"
    assert captured["env"]["PYTHONUNBUFFERED"] == "1"


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
