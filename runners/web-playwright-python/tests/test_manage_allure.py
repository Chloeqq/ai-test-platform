import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.contract]


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "manage_allure.py"
SPEC = importlib.util.spec_from_file_location("web_playwright_python_manage_allure", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_format_info_renders_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(MODULE, "get_allure_binary", lambda: "/usr/local/bin/allure")

    text = MODULE.format_info(tmp_path / "allure-results", tmp_path / "allure-report")

    assert "Allure CLI: /usr/local/bin/allure" in text
    assert "allure-results" in text
    assert "allure-report" in text


def test_generate_allure_report_invokes_cli(monkeypatch, tmp_path: Path):
    commands = []

    def fake_run(cmd, text, capture_output, check):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="generated", stderr="")

    monkeypatch.setattr(MODULE, "ensure_allure_available", lambda: "/usr/local/bin/allure")
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    result = MODULE.generate_allure_report(tmp_path / "results", tmp_path / "report")

    assert result.returncode == 0
    assert commands[0] == [
        "/usr/local/bin/allure",
        "generate",
        str((tmp_path / "results").resolve()),
        "-o",
        str((tmp_path / "report").resolve()),
        "--clean",
    ]
    assert (tmp_path / "results" / "categories.json").exists()


def test_report_identity_uses_run_id_and_case_version(monkeypatch):
    monkeypatch.setenv("WORKBENCH_RUN_ID", "abcdef123456")
    result = {
        "name": "fallback",
        "labels": [
            {"name": "case_id", "value": "mall-web-login-auth-fn-ai-0001"},
            {"name": "case_title", "value": "首次登录成功"},
            {"name": "case_version", "value": "v2"},
            {"name": "page", "value": "login"},
        ],
    }

    identity = MODULE._build_report_identity(result)

    assert identity["display_version"] == "mall-web-login-auth-fn-ai-0001-v2.run-abcdef12"
    assert identity["report_name"] == "首次登录成功 - 回归执行报告 (mall-web-login-auth-fn-ai-0001-v2.run-abcdef12)"


def test_write_allure_metadata_writes_business_categories(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("WORKBENCH_RUN_ID", "run123456")
    result = {
        "name": "test_yaml_ai_generated[case]",
        "labels": [
            {"name": "case_id", "value": "tc-login-001"},
            {"name": "case_title", "value": "首次登录成功"},
            {"name": "project", "value": "mall"},
            {"name": "base_url", "value": "http://localhost:5174/#/login"},
        ],
    }
    (tmp_path / "case-result.json").write_text(json.dumps(result), encoding="utf-8")

    MODULE.write_allure_metadata(tmp_path)

    env_text = (tmp_path / "environment.properties").read_text(encoding="utf-8")
    categories = json.loads((tmp_path / "categories.json").read_text(encoding="utf-8"))
    assert "Base_URL=http://localhost:5174/#/login" in env_text
    assert "Run_ID=run123456" in env_text
    assert any(item["name"] == "元素定位失败" for item in categories)


def test_open_allure_report_invokes_cli(monkeypatch, tmp_path: Path):
    commands = []

    def fake_run(cmd, text, capture_output, check):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="opened", stderr="")

    monkeypatch.setattr(MODULE, "ensure_allure_available", lambda: "/usr/local/bin/allure")
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    result = MODULE.open_allure_report(tmp_path / "report")

    assert result.returncode == 0
    assert commands[0] == [
        "/usr/local/bin/allure",
        "open",
        str((tmp_path / "report").resolve()),
    ]
