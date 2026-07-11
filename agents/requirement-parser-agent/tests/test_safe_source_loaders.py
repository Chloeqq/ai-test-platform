"""回归测试：修复 _safe_fetch_document / _safe_read_local_file 的调用签名 bug。

修复前的缺陷（会被宽 except 静默吞掉）：
- fetch_document(url) 违反 keyword-only 签名 → TypeError → 静默返回 {}
- read_local_file(path, base_dir=...) 参数名错误 → TypeError → 静默返回 ""
- read_local_file 返回 dict，却被当作 str 使用
本测试直接 monkeypatch 两个工具函数，断言 agent 以正确的关键字参数调用它们，
并正确地从返回 dict 中取出 text。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

src_pkg = ModuleType("src")
src_pkg.__path__ = [str(AGENT_ROOT / "src")]
sys.modules["src"] = src_pkg

spec = importlib.util.spec_from_file_location("src.agent", AGENT_ROOT / "src" / "agent.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
RequirementParserAgent = module.RequirementParserAgent


def test_safe_fetch_document_calls_with_url_kwarg(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_fetch_document(*, url: str, timeout_seconds: int = 12) -> dict[str, str]:
        captured["url"] = url
        return {"url": url, "text": "PRD 正文内容", "parsed": None}

    monkeypatch.setattr(module, "fetch_document", fake_fetch_document)
    agent = RequirementParserAgent()

    result = agent._safe_fetch_document("https://example.com/prd.txt")

    assert captured["url"] == "https://example.com/prd.txt"
    assert result.get("text") == "PRD 正文内容"


def test_safe_fetch_document_swallows_error_returns_empty(monkeypatch) -> None:
    def boom(*, url: str, timeout_seconds: int = 12):
        raise module.DocumentFetchError("network down")

    monkeypatch.setattr(module, "fetch_document", boom)
    agent = RequirementParserAgent()

    assert agent._safe_fetch_document("https://example.com/x") == {}


def test_safe_read_local_file_uses_path_and_repo_root_kwargs(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_read_local_file(*, path: str, repo_root) -> dict[str, str]:
        captured["path"] = path
        captured["repo_root"] = repo_root
        return {"path": path, "text": "diff --git a b"}

    monkeypatch.setattr(module, "read_local_file", fake_read_local_file)
    agent = RequirementParserAgent()

    result = agent._safe_read_local_file("changes.diff")

    assert captured["path"] == "changes.diff"
    assert captured["repo_root"] == agent.repo_root
    # 返回 dict 中的 text 被正确提取为 str
    assert result == "diff --git a b"
    assert isinstance(result, str)


def test_safe_read_local_file_swallows_error_returns_empty_str(monkeypatch) -> None:
    def boom(*, path: str, repo_root):
        raise module.LocalFileReadError("outside repo")

    monkeypatch.setattr(module, "read_local_file", boom)
    agent = RequirementParserAgent()

    assert agent._safe_read_local_file("../etc/passwd") == ""


def test_real_tool_signatures_are_compatible() -> None:
    """回归核心：用真实（未 mock）的工具函数验证调用签名兼容。

    修复前 fetch_document(url) / read_local_file(path, base_dir=...) 会抛 TypeError
    并被宽 except 吞掉 → 静默返回空。修复后应能正常调用到函数体内部：
    - fetch_document 收到非法 scheme，抛 DocumentFetchError（被捕获返回 {}）而非 TypeError
    - read_local_file 收到仓库外路径，抛 LocalFileReadError（被捕获返回 ""）而非 TypeError
    若签名仍不兼容，会命中 except Exception 分支——但返回值一致，故用 caplog 无法区分；
    这里改为直接调用真实工具函数并断言其 keyword-only 签名可用。
    """
    from src.tools.document_fetcher import DocumentFetchError, fetch_document
    from src.tools.local_file_reader import LocalFileReadError, read_local_file

    agent = RequirementParserAgent()

    # 非法 scheme → DocumentFetchError（证明 url= 关键字调用到了函数体）
    import pytest

    with pytest.raises(DocumentFetchError):
        fetch_document(url="ftp://example.com/x")

    # 仓库外路径 → LocalFileReadError（证明 path=/repo_root= 关键字调用到了函数体）
    with pytest.raises(LocalFileReadError):
        read_local_file(path="/nonexistent/outside.diff", repo_root=agent.repo_root)

    # agent 封装：非法输入被优雅降级，返回空（不抛 TypeError）
    assert agent._safe_fetch_document("ftp://example.com/x") == {}
    assert agent._safe_read_local_file("/nonexistent/outside.diff") == ""

