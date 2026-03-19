import importlib.util
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
