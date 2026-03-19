import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "analyze.py"
SPEC = importlib.util.spec_from_file_location("failure_analysis_agent_analyze", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rule_based_analysis_uses_meta_file_context(tmp_path: Path):
    meta_path = tmp_path / "meta.txt"
    meta_path.write_text(
        "NodeID: tests/test_yaml_ai_generated.py::test_case\n"
        "CapturedAt: 2026-03-17T12:00:00+00:00\n"
        "URL: http://example.test/product\n"
        "Title: 商品列表\n",
        encoding="utf-8",
    )

    agent = MODULE.FailureAnalysisAgent()
    agent.client = None

    result = agent.analyze(
        {
            "report": {
                "status": "failed",
                "runner_stdout_excerpt": "E AssertionError: expected product list title to be visible",
                "runner_stderr_excerpt": "",
                "evidence": {
                    "screenshots": [],
                    "html_pages": [],
                    "meta_files": [str(meta_path)],
                    "videos": [],
                    "other_files": [],
                    "total_files": 1,
                },
            },
            "stdout": "",
            "stderr": "",
            "error": "expected product list title to be visible",
        }
    )

    assert result["failure_category"] == "assertion"
    assert "url=http://example.test/product" in result["likely_cause"]
    assert "title=商品列表" in result["likely_cause"]
    assert "meta_files" in result["evidence_used"]
