"""runner_registry_support 纯函数单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_root = Path(__file__).resolve().parents[2] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from services.runner_registry_support import RunnerRegistrySupport


@pytest.fixture
def registry() -> RunnerRegistrySupport:
    return RunnerRegistrySupport(repo_root=Path("/tmp"))


class TestListRunners:
    def test_returns_catalog_with_default(self, registry: RunnerRegistrySupport) -> None:
        result = registry.list_runners()
        assert "items" in result
        assert "default_runner" in result
        assert result["default_runner"] == "playwright"
        assert len(result["items"]) >= 1


class TestResolveRunnerProfile:
    def test_resolves_playwright_by_name(self, registry: RunnerRegistrySupport) -> None:
        profile = registry.resolve_runner_profile("playwright")
        assert profile["runner"] == "playwright"

    def test_resolves_case_insensitive(self, registry: RunnerRegistrySupport) -> None:
        profile = registry.resolve_runner_profile("PLAYWRIGHT")
        assert profile["runner"] == "playwright"

    def test_resolves_with_whitespace(self, registry: RunnerRegistrySupport) -> None:
        profile = registry.resolve_runner_profile("  playwright  ")
        assert profile["runner"] == "playwright"

    def test_raises_for_unknown_runner(self, registry: RunnerRegistrySupport) -> None:
        with pytest.raises(ValueError, match="unsupported runner"):
            registry.resolve_runner_profile("nonexistent_runner")
