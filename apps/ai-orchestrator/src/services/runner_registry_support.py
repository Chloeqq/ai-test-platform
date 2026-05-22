"""Runner 注册表：列举与解析 Playwright/API/Mobile 等执行配置。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


class RunnerRegistrySupport:
    """维护内置 Runner 目录及默认 runner 解析。"""

    def __init__(self, *, repo_root: Path) -> None:
        self._runner_catalog = [
            {
                "runner": "playwright",
                "display_name": "Web Playwright Runner",
                "channel": "web",
                "framework": "playwright",
                "language": "python",
                "execution_supported": True,
                "generation_supported": True,
                "environment_pool": "web-browser-default",
                "artifact_mode": "manifest_first",
                "root_path": str((repo_root / "runners" / "web-playwright-python").resolve()),
            },
            {
                "runner": "api",
                "display_name": "API Runner",
                "channel": "api",
                "framework": "requests",
                "language": "python",
                "execution_supported": False,
                "generation_supported": True,
                "environment_pool": "api-sandbox",
                "artifact_mode": "generation_only",
                "root_path": "",
            },
            {
                "runner": "mobile",
                "display_name": "Mobile Runner",
                "channel": "mobile",
                "framework": "appium",
                "language": "python",
                "execution_supported": False,
                "generation_supported": True,
                "environment_pool": "mobile-device-farm",
                "artifact_mode": "generation_only",
                "root_path": "",
            },
        ]

    def list_runners(self) -> dict[str, Any]:
        """返回 Runner 目录副本及默认 runner 名称。"""
        return {
            "items": [deepcopy(item) for item in self._runner_catalog],
            "default_runner": "playwright",
        }

    def resolve_runner_profile(self, runner: str) -> dict[str, Any]:
        """按名称解析 Runner 配置；未知 runner 抛出 ValueError。"""
        normalized = str(runner or "").strip().lower() or "playwright"
        for item in self._runner_catalog:
            if str(item.get("runner", "")).strip().lower() == normalized:
                return deepcopy(item)
        raise ValueError(f"unsupported runner: {normalized}")
